#!/usr/bin/env python3
"""lf52 tenure census — WHY does `pegjump` hold only 19 of 500 on level 6? (rule 7bd/7bg shape)

⛔ THE QUESTION, asked of the TOOL and never off the harness's stderr (`_feedback` is the LAST
MESSAGE SET, not the retirement cause — rule 7ac). Three things per `propose()` of the target:

  * how many steps it returned and how many survived `loop._legal` — NOPLAN vs ILLEGAL;
  * every scalar the tool carries (so `pegjump._barren`, `_known`, `_settles`, `_peaked`,
    `_dirmap`, `_excluded`, `_pending_drive` are snapshotted before and after);
  * the LINE the call returned from, by line-tracing only the tool's own shallow methods.

Plus a PER-LEVEL tenure census (who holds which level for how many actions), and for the
successors a novelty count: how many of the actions they spend actually CHANGE the board, and
how many distinct board hashes they visit. That is what "graph does with the 225" means.

Modes (by seed, one fan covers every arm):
  pure    — no wrapping. CONTROL: must reproduce [8,52,60,64,139] / 823 (rule 7ai).
  census  — wrap the target's propose and record. Must ALSO reproduce, or nothing read is admissible.
  shadow  — after retirement keep asking the target OFF THE RUN: would it recover? (mutates it)
  hold    — never retire the target (zero its empty counter). The "hand it back" arm; rule 7bg
            measured this INERT on bp35/s5i5, so the prior is that it does nothing.

⛔ MIRRORS `score_efficiency.py:run_game` (rule 7x).

Usage:  uv run python scripts/_lf52_tenure.py <seed 1..12>
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import sys
from collections import Counter, defaultdict

ARMS = [
    ("pegjump", "pure"),
    ("pegjump", "census"),
    ("pegjump", "census"),
    ("pegjump", "shadow"),
    ("pegjump", "hold"),
    ("railpeg", "census"),
    ("graph", "census"),
    ("world_model", "census"),
    ("railpeg", "hold"),
    ("pegjump", "pure"),
    ("railpeg", "shadow"),
    ("pegjump", "hold"),
]

#: In `shadow`, also ask these off-run once the target is retired. ⚠️ Asking is NOT free (rule
#: 7ah) so it happens only in the perturbing arm and that arm's own counts are printed.
SUCCESSORS = {"pegjump": ["railpeg", "graph"], "railpeg": ["pegjump", "graph"]}

_SHALLOW = {"propose", "detect", "_sync", "_ensure_plan", "_advance", "_learn_drive",
            "_install", "_placed", "_adopt", "_board", "_next", "_quit", "_begin",
            "_settle", "_act", "_plan_now", "_replan"}


def _snapshot(tool) -> dict:
    out: dict = {}
    for k, v in vars(tool).items():
        if isinstance(v, bool) or v is None or isinstance(v, (int, float, str)):
            out[k] = v
        elif isinstance(v, dict):
            out[k] = f"len={len(v)}:{sorted(map(str, v))[:6]}" if len(v) <= 6 else f"len={len(v)}"
        elif isinstance(v, (set, list, tuple, frozenset)):
            out[k] = f"len={len(v)}:{sorted(map(str, v))[:6]}" if len(v) <= 6 else f"len={len(v)}"
        else:
            out[k] = type(v).__name__
    tr = getattr(tool, "trace", None)
    if callable(tr):
        try:
            out["_trace"] = str(tr())[:300]
        except Exception as exc:  # noqa: BLE001
            out["_trace"] = f"<raised {exc}>"
    return out


def main() -> None:
    seed = int(sys.argv[1])
    tool_name, mode = ARMS[(seed - 1) % len(ARMS)]
    game = "lf52"
    budget = 4000

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "src"))
    sys.path.insert(0, here)

    from arc_agi import Arcade, OperationMode  # type: ignore
    from arcengine import GameAction, GameState  # type: ignore
    from score_efficiency import _make_agent

    from admorphiq.harness.loop import availability
    from admorphiq.tools.base import frame_2d

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    want = game
    game_id = next(e.game_id for e in arcade.get_environments()
                   if want in f"{e.game_id} {e.title or ''}".lower())
    env = arcade.make(game_id)
    obs = env.observation_space
    adapter = _make_agent("unified", game_id=game_id)
    tool = adapter.tools[tool_name]
    tool_file = inspect.getsourcefile(type(tool))

    calls: list[dict] = []
    shadow: list[dict] = []
    step_no = {"n": 0, "lvl": 0}

    orig = tool.propose

    def traced(frames, obs_):
        lines: list[tuple[str, int]] = []

        def _local(frame, event, arg):
            if event == "line":
                lines.append((frame.f_code.co_name, frame.f_lineno))
            return _local

        def _global(frame, event, arg):
            if (event == "call" and frame.f_code.co_filename == tool_file
                    and frame.f_code.co_name in _SHALLOW):
                return _local
            return None

        sys.settrace(_global)
        try:
            steps = orig(frames, obs_)
        finally:
            sys.settrace(None)
        return steps, lines

    def wrapped(frames, obs_):
        before = _snapshot(tool)
        steps, lines = traced(frames, obs_)
        after = _snapshot(tool)
        simple_ids, action6 = availability(obs_)
        legal = [s for s in steps if adapter._legal(s, simple_ids, action6)]
        changed = {k: [before.get(k), v] for k, v in after.items() if before.get(k) != v}
        in_propose = [ln for nm, ln in lines if nm == "propose"]
        calls.append({
            "step": step_no["n"],
            "level": step_no["lvl"],
            "n_steps": len(steps),
            "n_legal": len(legal),
            "kind": "PLAN" if legal else ("ILLEGAL" if steps else "NOPLAN"),
            "ret_propose_line": in_propose[-1] if in_propose else None,
            "ret_last_line": lines[-1] if lines else None,
            "changed": changed,
            "after": after,
        })
        return steps

    if mode not in ("pure",):
        tool.propose = wrapped

    # per-level tenure + novelty
    tenure: dict[int, Counter] = defaultdict(Counter)
    novel: dict[str, Counter] = defaultdict(Counter)   # tool -> {acted, changed}
    seen_states: dict[str, set] = defaultdict(set)
    retired_at: list[dict] = []
    prev_levels = int(obs.levels_completed)
    level_counts: list[int] = []
    this_level = 0
    actions = 0
    was_failed = False

    while actions < budget:
        if adapter.is_done([], obs):
            break
        if mode == "hold" and getattr(adapter, "_current", None) == tool_name:
            adapter._empty_runs = 0
        step_no["n"] = actions
        step_no["lvl"] = prev_levels
        try:
            action = adapter.choose_action([], obs)
        except Exception as exc:  # noqa: BLE001
            retired_at.append({"step": actions, "crash": repr(exc)[:200]})
            break
        if not isinstance(action, GameAction):
            break

        who = getattr(adapter, "_current", None) or "HARNESS"
        tenure[prev_levels][who] += 1
        now_failed = tool_name in getattr(adapter, "_failed", set())
        if now_failed and not was_failed:
            retired_at.append({"step": actions, "level": prev_levels,
                               "state": _snapshot(tool)})
        was_failed = now_failed

        if mode == "shadow" and now_failed:
            try:
                st = orig([], obs)
            except Exception as exc:  # noqa: BLE001
                st = []
                shadow.append({"step": actions, "raised": repr(exc)[:160]})
            else:
                simple_ids, action6 = availability(obs)
                lg = [s for s in st if adapter._legal(s, simple_ids, action6)]
                rec = {"step": actions, "level": prev_levels,
                       "n_steps": len(st), "n_legal": len(lg)}
                for other in SUCCESSORS.get(tool_name, []):
                    ot = adapter.tools.get(other)
                    if ot is None:
                        continue
                    try:
                        bid = float(ot.detect([], obs))
                        rec[other] = round(bid, 2)
                    except Exception as exc:  # noqa: BLE001
                        rec[other] = f"raised {exc!r}"[:100]
                shadow.append(rec)

        try:
            g_before = frame_2d(obs)
            h_before = hashlib.md5(g_before.tobytes()).hexdigest()[:12]
        except Exception:  # noqa: BLE001
            h_before = None

        obs = env.step(action, data=action.action_data.model_dump()) if action.is_complex() \
            else env.step(action)
        if obs is None:
            break
        actions += 1
        this_level += 1
        try:
            h_after = hashlib.md5(frame_2d(obs).tobytes()).hexdigest()[:12]
        except Exception:  # noqa: BLE001
            h_after = None
        novel[who]["acted"] += 1
        if h_before is not None and h_after is not None:
            if h_before != h_after:
                novel[who]["changed"] += 1
            seen_states[who].add(h_after)

        cur = int(obs.levels_completed)
        if cur > prev_levels:
            for _ in range(cur - prev_levels):
                level_counts.append(this_level)
                this_level = 0
            prev_levels = cur
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            obs = env.step(GameAction.RESET)
            actions += 1
            this_level += 1
            if obs is None:
                break

    kinds = Counter(c["kind"] for c in calls)
    ret_lines = Counter(str(c["ret_propose_line"]) for c in calls)
    last_lines = Counter(str(c["ret_last_line"]) for c in calls)
    by_level = Counter((c["level"], c["kind"]) for c in calls)

    # The run of empties that retired it, plus the call before it.
    first_empty_run = None
    run = 0
    for c in calls:
        if c["kind"] == "NOPLAN":
            run += 1
            if run == 8:
                i = calls.index(c)
                first_empty_run = calls[max(0, i - 9):i + 1]
                break
        else:
            run = 0

    print(json.dumps({
        "arm": {"game": game, "tool": tool_name, "mode": mode, "seed": seed},
        "levels": prev_levels,
        "actions": actions,
        "level_counts": level_counts,
        "tenure_by_level": {str(k): dict(v) for k, v in sorted(tenure.items())},
        "novelty": {k: {"acted": v["acted"], "changed": v["changed"],
                        "distinct": len(seen_states[k])} for k, v in novel.items()},
        "n_propose_calls": len(calls),
        "kinds": dict(kinds),
        "kinds_by_level": {f"{k[0]}/{k[1]}": v for k, v in sorted(by_level.items())},
        "ret_propose_line": dict(ret_lines),
        "ret_last_line": dict(last_lines),
        "retired_at": retired_at,
        "first_empty_run": first_empty_run,
        "calls_head": calls[:14],
        "shadow_n": len(shadow),
        "shadow_spoke": sum(1 for s in shadow if s.get("n_legal")),
        "shadow_first_spoke": next((s["step"] for s in shadow if s.get("n_legal")), None),
        "shadow_head": shadow[:6],
        "shadow_succ_bids": {
            o: dict(Counter(str(s.get(o)) for s in shadow))
            for o in SUCCESSORS.get(tool_name, [])
        },
    }))


if __name__ == "__main__":
    main()
