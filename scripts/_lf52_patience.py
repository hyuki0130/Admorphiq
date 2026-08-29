#!/usr/bin/env python3
"""lf52 — what does `pegjump`'s SELF-INFLICTED retirement COST? (the census's counterfactual)

⛔ THE CENSUS (scripts/_lf52_tenure.py, R101LF52TEN) measured the mechanism exactly:

    445 PLAN jump (board a piece onto a carrier)      _barren 1   _dirmap {}
    447 PLAN calibration probe for (0,-1)             _plan CLEARED by design
    448 PLAN calibration probe   _barren 1->2         aid 1 excluded for (0,-1)
    450 settle              _dirmap{(1,0)} learned
    451 PLAN calibration probe   _barren 2->3         third probe
    453 settle              _dirmap{(0,-1)} LEARNED — the direction it wanted
    454 NOPLAN  _ensure_plan returns 0.0 because _barren >= 3   <-- one action later

Each calibration probe sets `self._plan = []` by design, so the NEXT `_ensure_plan` must re-plan
the same railhead move from scratch — and re-planning an explore/railhead move is what increments
`_barren`. **The calibration is charged to the patience budget it is calibrating FOR.** `_barren`
only resets when `known` grows, and `known` only grows when a drive scrolls the camera — the very
action the latch forbids. So it is a latch that can only be cleared by the action it prevents,
which is why the `hold` arm measured 203 consecutive NOPLAN and moved nothing.

This asks what removing the latch BUYS, without touching a shared file (rule 7o — measuring the
mechanism does not license changing the behaviour). Two independent levers, monkey-patched:

  nocharge  — a call that fires the calibration branch has its `_barren` restored: the probe is
              not billed to the patience it is buying.
  patient   — `_barren` is never allowed to reach 3, i.e. unlimited barren sweeps.
  hold      — the harness never retires it (composed with either lever).

⛔ MIRRORS `score_efficiency.py:run_game` (rule 7x). Controls (`pure`) must reproduce
[8, 52, 60, 64, 139] / 823 / 0.272727 or nothing read off this is admissible.

Usage:  uv run python scripts/_lf52_patience.py <seed 1..12>
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

ARMS = [
    ("pure", False),
    ("nocharge", False),
    ("nocharge", True),
    ("patient", False),
    ("patient", True),
    ("nocharge+patient", True),
    ("pure", False),
    ("nocharge", True),
    ("patient", True),
    ("nocharge+patient", False),
    ("nocharge+patient", True),
    ("patient", False),
]


def main() -> None:
    seed = int(sys.argv[1])
    lever, hold = ARMS[(seed - 1) % len(ARMS)]
    game, tool_name, budget = "lf52", "pegjump", 4000

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "src"))
    sys.path.insert(0, here)

    from arc_agi import Arcade, OperationMode  # type: ignore
    from arcengine import GameAction, GameState  # type: ignore
    from score_efficiency import _make_agent

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    game_id = next(e.game_id for e in arcade.get_environments()
                   if game in f"{e.game_id} {e.title or ''}".lower())
    env = arcade.make(game_id)
    obs = env.observation_space
    adapter = _make_agent("unified", game_id=game_id)
    tool = adapter.tools[tool_name]

    orig = tool.propose
    probes = {"n": 0, "drives": 0, "kmax": 0}

    def wrapped(frames, obs_):
        barren_before = tool._barren
        pend_before = tool._pending_drive
        steps = orig(frames, obs_)
        # A call that armed a NEW pending drive is a calibration probe: it cleared the plan by
        # design, so the re-plan it forces is not evidence that the board is barren.
        # ⚠️ NOT `is not pend_before`: `_learn_drive` rebuilds the tuple every frame to bump its
        # age, so identity alone counts a settle call as a probe. A calibration probe is the
        # transition from NO pending drive to one.
        fired = pend_before is None and tool._pending_drive is not None
        if fired:
            probes["n"] += 1
            if "nocharge" in lever:
                tool._barren = barren_before
        if "patient" in lever and tool._barren >= 3:
            tool._barren = 2
        probes["kmax"] = max(probes["kmax"], tool._known)
        return steps

    if lever != "pure":
        tool.propose = wrapped

    tenure: dict[int, Counter] = defaultdict(Counter)
    prev_levels = int(obs.levels_completed)
    level_counts: list[int] = []
    this_level = actions = 0

    while actions < budget:
        if adapter.is_done([], obs):
            break
        if hold and getattr(adapter, "_current", None) == tool_name:
            adapter._empty_runs = 0
        try:
            action = adapter.choose_action([], obs)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"crash": repr(exc)[:200], "at": actions}))
            break
        if not isinstance(action, GameAction):
            break
        tenure[prev_levels][getattr(adapter, "_current", None) or "HARNESS"] += 1
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

    print(json.dumps({
        "arm": {"lever": lever, "hold": hold, "seed": seed},
        "levels": prev_levels,
        "actions": actions,
        "level_counts": level_counts,
        "tenure_by_level": {str(k): dict(v) for k, v in sorted(tenure.items())},
        "calib_probes": probes["n"],
        "known_max": probes["kmax"],
        "final": {"barren": tool._barren, "known": tool._known,
                  "dirmap": str(tool._dirmap), "excluded": str(tool._excluded)},
    }))


if __name__ == "__main__":
    main()
