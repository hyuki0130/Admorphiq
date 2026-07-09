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
    ap.add_argument("--draw-warmup", type=int, default=40,
                    help="steps into a level before the --targetgrid draw fires")
    ap.add_argument("--targetgrid", action="store_true",
                    help="graph only: after warmup, ask the LLM for an 8x8 TARGET "
                         "grid of the solved board and inject via set_target_frame")
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

    _draw_done = [False]

    def _llm(prompt: str, npred: int = 200) -> str:
        import json as _json
        import os as _os
        import urllib.request as _u
        model = _os.environ.get("TARGETGRID_MODEL", "gemma4:31b-it-q8_0")
        body = {"model": model, "stream": False, "think": False,
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0.0, "num_ctx": 8192, "num_predict": npred}}
        req = _u.Request("http://localhost:11434/api/chat", data=_json.dumps(body).encode(),
                         headers={"Content-Type": "application/json"}, method="POST")
        with _u.urlopen(req, timeout=150) as r:
            return _json.loads(r.read())["message"]["content"]

    def _maybe_inject_targetgrid(frame):
        """Warmup then ask the LLM to DRAW the solved board as an 8x8 grid and
        inject it via set_target_frame — a goal richer than the GoalSpec vocab."""
        if not a.targetgrid or _draw_done[0] or a.tool != "graph" or steps < a.draw_warmup:
            return
        import os as _os

        from admorphiq.tools.targetgrid import build_target_prompt, parse_and_validate_target
        res = int(_os.environ.get("TARGETGRID_RES", "8"))
        prompt = build_target_prompt(frame, res)
        ncells = res * res

        # Up to 2 attempts: a rejected draw is retried once; still-invalid means
        # NO injection (graph keeps its proven frame-only multi-goal base).
        for attempt in (1, 2):
            try:
                txt = _llm(prompt, npred=100 + 4 * ncells)
            except Exception as exc:  # noqa: BLE001
                print(f"targetgrid infer failed: {exc}", file=sys.stderr)
                break
            tgt, reason = parse_and_validate_target(txt, frame, res)
            if tgt is None:
                print(f"targetgrid attempt {attempt} rejected: {reason}", file=sys.stderr)
                continue
            scale = max(1, 64 // res)
            tool.set_target_frame(
                np.kron(tgt, np.ones((scale, scale), dtype=np.int64)), res=res
            )
            print(f"TARGETGRID injected (attempt {attempt}, res={res}, "
                  f"distinct={len(np.unique(tgt))})", file=sys.stderr)
            break
        _draw_done[0] = True

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
            # A new level has a NEW solved-board target — allow a fresh draw
            # (deep levels carry the RHAE weight; one extra LLM call per level).
            _draw_done[0] = False

        if prev_frame is not None and prev_step is not None and prev_frame.shape == frame.shape:
            changed = bool((prev_frame != frame).any())
            _maybe_inject_targetgrid(frame)
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
