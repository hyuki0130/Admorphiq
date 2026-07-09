"""Drive ONE harness tool directly on a game — no LLM, no routing, no swap.

Isolates a tool's raw strength from the orchestration loop: instantiate a single
Tool, and on every turn feed it the observed transition (observe) then take its
proposed action (propose), reviving on GAME_OVER. This answers "can THIS tool
clear THIS game on its own?" — separating tool-quality shortfalls from routing /
stall-detector interactions in the UnifiedAgent.

Usage (on the Kaggle-matched VM):
  uv run python scripts/probe_tool_direct.py --tool graph --game cd82 --budget 2000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402

from admorphiq.tools.base import (  # noqa: E402
    availability,
    frame_2d,
    has_frame,
    levels_completed,
    state_name,
)


def _make_tool(name: str):
    # Instantiate ONLY the requested tool — importing/constructing every tool
    # (default_tools) pulls in the ollama-backed ones, which can block under
    # parallel runs. Direct per-tool construction keeps a probe self-contained.
    ctors = {
        "graph": ("admorphiq.tools.graph_search", "GraphSearchTool"),
        "world_model": ("admorphiq.tools.world_model", "WorldModelTool"),
        "paint": ("admorphiq.tools.paint_flood", "PaintFloodTool"),
        "toggle": ("admorphiq.tools.toggle", "ToggleTool"),
        "dealias": ("admorphiq.tools.dealias", "DealiasTool"),
        "deadsig": ("admorphiq.tools.dead_signature", "DeadSignatureTool"),
        "llm_goal": ("admorphiq.tools.llm_goal", "LLMGoalTool"),
    }
    if name not in ctors:
        raise SystemExit(f"unknown tool {name!r}; have {sorted(ctors)}")
    import importlib
    mod_name, cls_name = ctors[name]
    return getattr(importlib.import_module(mod_name), cls_name)()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--budget", type=int, default=2000)
    ap.add_argument("--hybrid", action="store_true",
                    help="graph only: after warmup, infer a goal via the LLM and "
                         "inject it (set_external_goal) so LLM goal steers search")
    ap.add_argument("--hybrid-warmup", type=int, default=40)
    a = ap.parse_args()

    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction as EngineGameAction

    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.types import ActionType, GameAction

    convert = AdmorphiqAdapter._convert_action
    tool = _make_tool(a.tool)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    want = a.game.strip().lower()
    match = next(
        (e for e in arcade.get_environments()
         if want in f"{e.game_id} {e.title or ''}".lower()),
        None,
    )
    if match is None:
        raise SystemExit(f"no game matching {a.game!r}")
    env = arcade.make(match.game_id)
    obs = env.observation_space

    _hybrid_probe_changes: list = []
    _hybrid_done = [False]

    def _maybe_inject_goal(frame):
        """Warmup then LLM-infer a goal and inject it into the graph tool."""
        if not a.hybrid or _hybrid_done[0] or a.tool != "graph":
            return
        if steps < a.hybrid_warmup:
            return
        import json as _json
        import urllib.request as _u

        from admorphiq.planner.goal_inference import build_goal_prompt, parse_goal_spec
        from admorphiq.tools.base import color_histogram as _ch

        def _llm(prompt: str) -> str:
            body = {"model": "gemma4:31b-it-q8_0", "stream": False, "think": False,
                    "messages": [{"role": "user", "content": prompt}],
                    "options": {"temperature": 0.0, "num_ctx": 8192, "num_predict": 200}}
            req = _u.Request("http://localhost:11434/api/chat", data=_json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
            with _u.urlopen(req, timeout=120) as r:
                return _json.loads(r.read())["message"]["content"]

        hist = {int(c): int(n) for c, n in enumerate(_ch(frame)) if n}
        try:
            prompt = build_goal_prompt(hist, _hybrid_probe_changes, grid_shape=frame.shape)
            goal = parse_goal_spec(_llm(prompt))
        except Exception as exc:  # noqa: BLE001
            print(f"hybrid goal infer failed: {exc}", file=sys.stderr)
            goal = None
        if goal is not None:
            tool.set_external_goal(goal)
            print(f"HYBRID injected goal: {goal.goal_type}", file=sys.stderr)
        _hybrid_done[0] = True

    queue: list = []
    prev_frame = None
    prev_step = None
    steps = 0
    last_levels = 0

    while steps < a.budget:
        if state_name(obs) == "WIN":
            break
        if state_name(obs) in ("GAME_OVER", "NOT_PLAYED") or not has_frame(obs):
            obs = env.step(EngineGameAction.RESET)
            prev_frame = None
            queue.clear()
            steps += 1
            continue

        frame = frame_2d(obs).astype(np.int16)
        lv = levels_completed(obs)
        if lv > last_levels:
            tool.reset()
            last_levels = lv
            queue.clear()
            prev_frame = None

        if prev_frame is not None and prev_step is not None and prev_frame.shape == frame.shape:
            changed = bool((prev_frame != frame).any())
            if a.hybrid and changed:
                d = prev_frame != frame
                new = frame[d]
                if new.size:
                    import numpy as _np
                    vals, cnts = _np.unique(new, return_counts=True)
                    _hybrid_probe_changes.append({
                        "action": prev_step[0], "changed_cells": int(d.sum()),
                        "top_new_color": int(vals[int(cnts.argmax())]),
                    })
            _maybe_inject_goal(frame)
            try:
                tool.observe(prev_frame, prev_step, changed)
            except Exception as exc:  # noqa: BLE001
                print(f"observe error: {exc}", file=sys.stderr)

        if not queue:
            simple_ids, action6 = availability(obs)
            try:
                steps_out = tool.propose([obs], obs)
            except Exception as exc:  # noqa: BLE001
                print(f"propose error: {exc}", file=sys.stderr)
                steps_out = []
            legal = []
            for aid, xy in steps_out:
                if xy is not None and action6 and aid == 6:
                    legal.append((aid, xy))
                elif xy is None and (aid in simple_ids or (aid == 7 and not simple_ids)):
                    legal.append((aid, xy))
            if not legal:
                legal = [(simple_ids[0], None)] if simple_ids else [(6, (32, 32))]
            queue = legal

        aid, xy = queue.pop(0)
        step = (aid, xy)
        internal = GameAction.coordinate(int(xy[0]), int(xy[1])) if xy is not None \
            else GameAction.simple(ActionType(aid))
        action = convert(internal)
        obs = env.step(action) if not action.is_complex() \
            else env.step(action, data=action.action_data.model_dump())
        if obs is None:
            break
        steps += 1
        prev_frame = frame
        prev_step = step

    lv = levels_completed(obs) if obs else last_levels
    print(f"TOOL={a.tool} GAME={a.game} levels={lv} steps={steps}", flush=True)


if __name__ == "__main__":
    main()
