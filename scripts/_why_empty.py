#!/usr/bin/env python3
"""WHY does the STRONG tool go empty? — census, not a build (rule 7bd's open half).

⛔ THE QUESTION. Crossing the solo sweep against the tenure census (rule 7bd) showed that on bp35
the harness spends 486 actions with `graph` (solo depth 0) while `crag` (solo depth 5) is retired
after 229, and on s5i5 it spends 463 with `linkage` (solo depth 2) while `swivel` (solo depth 6) is
retired after 228. Rule 7ac already closed the routing branch — no handover was ever lost to a tie —
so every one of these is an EMPTY retirement: `propose()` returns nothing eight times running
(`loop.py:_EMPTY_TOLERANCE`) and the board goes to whoever is left.

⛔ DO NOT read the reason off the harness's stderr: `_feedback` is the LAST MESSAGE SET, not the
retirement cause (rule 7ac). This asks the TOOL. Three things are recorded per `propose()` call:
  * how many steps it returned, and how many of those survived `loop._legal` — separating
    NOPLAN (returned nothing) from ILLEGAL (returned something the harness refused);
  * the tool's OWN diagnostics — every scalar attribute plus `trace()`, so crag's `_note` (the
    string its `_quit(why)` sets) and swivel's `_dead` are captured at the moment they are set;
  * the LINE the call returned from, by line-tracing only the tool's own shallow methods, which
    names the exact `return []` that fired.

Modes (chosen by seed, so one fan covers every arm):
  pure    — no wrapping at all. CONTROL: must equal the banked per-level counts (rule 7ai).
  census  — wraps `propose` and records. Must ALSO equal the banked counts, or the instrument moved
            the run and nothing read off it is admissible.
  shadow  — after the harness retires the tool, keep calling its `propose` OFF THE RUN and record
            whether it ever speaks again. ⚠️ This MUTATES the tool's own state, so its own score is
            not comparable; it answers "would it recover", not "should we hand it back".
  hold    — the tool is never retired (its empty counter is zeroed each step), so the harness keeps
            asking it and fills the turns with its own probe. This is the "hand it back" arm, and
            per rule 7o measuring the mechanism does not license changing the behaviour.

⛔ MIRRORS `score_efficiency.py:run_game` (rule 7x): the scorer's own `_make_agent`, an EMPTY frames
list, `restart_on_game_over` honoured, BREAK on WIN, per-level action counts recorded the same way.

Usage:  uv run python scripts/_why_empty.py <seed 1..10>
"""

from __future__ import annotations

import inspect
import json
import os
import sys
from collections import Counter

# seed -> (game, tool, mode).  Two controls per game (banked numbers + `pure`).
ARMS = [
    ("bp35", "crag", "pure"),
    ("bp35", "crag", "census"),
    ("bp35", "crag", "census"),
    ("bp35", "crag", "shadow"),
    ("bp35", "crag", "hold"),
    ("s5i5", "swivel", "pure"),
    ("s5i5", "swivel", "census"),
    ("s5i5", "swivel", "census"),
    ("s5i5", "swivel", "shadow"),
    ("s5i5", "swivel", "hold"),
]

#: In `shadow` mode, other tools ALSO asked off-run once the target is retired — rule 7bd's
#: named anomaly (`telescope` clears five levels of s5i5 alone and is never asked for a board).
#: ⚠️ Asking a tool is NOT free (rule 7ah), so this happens only in the perturbing arm and the
#: arm's own per-level counts are printed so the perturbation is visible rather than assumed.
SUCCESSORS = {"s5i5": ["telescope", "linkage"], "bp35": ["graph"]}

_SHALLOW = {"propose", "_next", "_quit", "_begin", "_settle", "_act", "_assemble",
            "_replan", "_stranded", "_take", "_retry_unknown"}


def _snapshot(tool) -> dict:
    """Every scalar the tool carries, plus the length of every container, plus trace()."""
    out: dict = {}
    for k, v in vars(tool).items():
        if isinstance(v, bool) or v is None or isinstance(v, (int, float, str)):
            out[k] = v
        elif isinstance(v, (set, list, dict, tuple)):
            out[k] = f"len={len(v)}"
        else:
            out[k] = type(v).__name__
    tr = getattr(tool, "trace", None)
    if callable(tr):
        try:
            out["_trace"] = str(tr())[:400]
        except Exception as exc:  # noqa: BLE001
            out["_trace"] = f"<raised {exc}>"
    return out


def main() -> None:
    seed = int(sys.argv[1])
    game, tool_name, mode = ARMS[(seed - 1) % len(ARMS)]
    budget = 4000

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "src"))
    sys.path.insert(0, here)

    from arc_agi import Arcade, OperationMode  # type: ignore
    from arcengine import GameAction, GameState  # type: ignore
    from score_efficiency import _make_agent

    from admorphiq.harness.loop import availability

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    want = game.strip().lower()
    game_id = next(
        e.game_id for e in arcade.get_environments()
        if want in f"{e.game_id} {e.title or ''}".lower()
    )
    env = arcade.make(game_id)
    obs = env.observation_space
    adapter = _make_agent("unified", game_id=game_id)
    tool = adapter.tools[tool_name]
    tool_file = inspect.getsourcefile(type(tool))

    calls: list[dict] = []          # one per propose() the harness made of the target tool
    shadow: list[dict] = []         # one per shadow call after retirement
    step_no = {"n": 0}

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
            "level": int(getattr(obs_, "levels_completed", -1)),
            "n_steps": len(steps),
            "n_legal": len(legal),
            "kind": "PLAN" if legal else ("ILLEGAL" if steps else "NOPLAN"),
            "ret_propose_line": in_propose[-1] if in_propose else None,
            "ret_last_line": lines[-1] if lines else None,
            "note": after.get("_note"),
            "changed": changed,
            "after": after,
        })
        return steps

    if mode != "pure":
        tool.propose = wrapped

    tenure: Counter = Counter()
    retired_at: list[dict] = []
    prev_levels = int(obs.levels_completed)
    level_counts: list[int] = []
    this_level = 0
    actions = 0
    was_failed = False

    while actions < budget:
        if adapter.is_done([], obs):
            break
        # `hold`: never let the empty counter reach _EMPTY_TOLERANCE for this tool.
        if mode == "hold" and getattr(adapter, "_current", None) == tool_name:
            adapter._empty_runs = 0
        step_no["n"] = actions
        try:
            action = adapter.choose_action([], obs)
        except Exception as exc:  # noqa: BLE001
            retired_at.append({"step": actions, "crash": repr(exc)[:200]})
            break
        if not isinstance(action, GameAction):
            break

        who = getattr(adapter, "_current", None) or "HARNESS"
        tenure[who] += 1
        now_failed = tool_name in getattr(adapter, "_failed", set())
        if now_failed and not was_failed:
            retired_at.append({"step": actions, "level": prev_levels,
                               "note": getattr(tool, "_note", None),
                               "state": _snapshot(tool)})
        was_failed = now_failed

        # `shadow`: ask the retired tool the same question the harness stopped asking.
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
                       "n_steps": len(st), "n_legal": len(lg),
                       "note": getattr(tool, "_note", None)}
                for other in SUCCESSORS.get(game, []):
                    ot = adapter.tools.get(other)
                    if ot is None:
                        continue
                    try:
                        bid = float(ot.detect([], obs))
                        ost = ot.propose([], obs)
                        olg = [s for s in ost if adapter._legal(s, simple_ids, action6)]
                        rec[other] = [round(bid, 2), len(ost), len(olg)]
                    except Exception as exc:  # noqa: BLE001
                        rec[other] = f"raised {exc!r}"[:120]
                shadow.append(rec)

        obs = env.step(action, data=action.action_data.model_dump()) if action.is_complex() \
            else env.step(action)
        if obs is None:
            break
        actions += 1
        this_level += 1
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
    notes = Counter(str(c["note"]) for c in calls)
    ret_lines = Counter(str(c["ret_propose_line"]) for c in calls)
    last_lines = Counter(str(c["ret_last_line"]) for c in calls)
    # The eight calls that actually retired it, plus the first NOPLAN of that run.
    tail = calls[-40:]

    print(json.dumps({
        "arm": {"game": game, "tool": tool_name, "mode": mode, "seed": seed},
        "levels": prev_levels,
        "actions": actions,
        "level_counts": level_counts,
        "tenure": dict(tenure),
        "n_propose_calls": len(calls),
        "kinds": dict(kinds),
        "notes": dict(notes),
        "ret_propose_line": dict(ret_lines),
        "ret_last_line": dict(last_lines),
        "retired_at": retired_at,
        "shadow_n": len(shadow),
        "shadow_spoke": sum(1 for s in shadow if s.get("n_legal")),
        "shadow_head": shadow[:4],
        "shadow_first_spoke": next((s["step"] for s in shadow if s.get("n_legal")), None),
        "shadow_succ": {
            o: {
                "asked": sum(1 for s in shadow if isinstance(s.get(o), list)),
                "bid_gt0": sum(1 for s in shadow
                               if isinstance(s.get(o), list) and s[o][0] > 0),
                "spoke": sum(1 for s in shadow
                             if isinstance(s.get(o), list) and s[o][2]),
                "first_spoke": next((s["step"] for s in shadow
                                     if isinstance(s.get(o), list) and s[o][2]), None),
            }
            for o in SUCCESSORS.get(game, [])
        },
        "shadow_notes": dict(Counter(str(s.get("note")) for s in shadow)),
        "tail": tail,
    }))


if __name__ == "__main__":
    main()
