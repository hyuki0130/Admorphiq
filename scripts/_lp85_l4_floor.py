"""What level 4 of lp85 would cost with a PERFECT model — the floor its 18 actions sit above.

Mirrors ``scripts/score_efficiency.py:run_game``. Captures the board as level 4 opens, keeps the
permutations the tool has CONVERGED on by the time the level clears, and re-plans the opening
board with those. Also re-plans with only the controls the executed plan actually used.

Purpose: level 4 costs 4 fresh probes + 6 confirmations + 8 plan presses against a human 16, and
every arm that cut a confirmation was measured a loss. If a perfect model still needs 8 presses
then 12 is the floor and the remaining 6 are the whole question; if it needs fewer, the model —
not the probing — is the lever.
Expected feedback: the printed floor is the smallest total this tool could ever spend on level 4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402


def main() -> None:
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    from score_efficiency import _make_agent

    from admorphiq.tools import cyclepress as cp

    grab: dict = {"level": 0, "open": None, "perm": None, "used": []}
    orig = cp.CyclePressTool.propose

    def propose_wrap(self, frames, obs):
        steps = orig(self, frames, obs)
        if grab["level"] == 3:
            g = self._board_grid(obs)
            board = cp.read_board(g)
            if board is not None:
                tiles, side, _pitch = board
                marks = cp.markers_on(g, tiles, side)
                if marks and grab["open"] is None:
                    grab["open"] = (dict(tiles), list(marks), list(self._slots), self._pitch)
            grab["perm"] = {k: dict(v) for k, v in self._perm.items()}
            if steps:
                grab["used"].append((steps[0][1][1], steps[0][1][0]))
        return steps

    cp.CyclePressTool.propose = propose_wrap

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(e for e in arcade.get_environments()
                if "lp85" in f"{e.game_id} {e.title or ''}".lower())
    agent = _make_agent("unified", game_id=info.game_id)
    env = arcade.make(info.game_id)
    obs = env.observation_space
    prev = int(obs.levels_completed)
    total = 0
    this_level = 0
    per_level: list[int] = []

    while total < budget:
        if agent.is_done([], obs):
            break
        action = agent.choose_action([], obs)
        if not isinstance(action, GameAction):
            break
        obs = (env.step(action, data=action.action_data.model_dump())
               if action.is_complex() else env.step(action))
        if obs is None:
            break
        total += 1
        this_level += 1
        cur = int(obs.levels_completed)
        if cur > prev:
            for _ in range(cur - prev):
                per_level.append(this_level)
                this_level = 0
            prev = cur
            grab["level"] = cur
            if cur == 4:
                break
        if obs.state in (GameState.WIN, GameState.GAME_OVER):
            break

    tiles, marks, _slots, _pitch = grab["open"]
    perm = grab["perm"]
    full = cp.plan_presses(tiles, marks, perm)
    used = {c for c in perm if c in set(grab["used"])}
    part = cp.plan_presses(tiles, marks, {c: perm[c] for c in used}) if used else None
    print(json.dumps({
        "per_level": per_level,
        "controls_modelled": len(perm),
        "controls_pressed_in_plan": sorted(str(c) for c in used),
        "plan_with_converged_model": None if full is None else len(full),
        "plan_with_used_controls_only": None if part is None else len(part),
        "floor_actions": None if full is None else len(perm) + len(full),
    }))


if __name__ == "__main__":
    main()
