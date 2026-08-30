"""When does lp85 level 4's model become RIGHT, and what would a plan have cost at that moment?

Mirrors ``scripts/score_efficiency.py:run_game`` (empty frames list to is_done/choose_action,
restart_on_game_over honoured, BREAK on WIN) and reproduces the banked per-level counts.

Level 4 costs 18 actions against a human 16: 4 fresh probes + 6 confirmations + 8 plan presses.
The confirmations are NOT optional under the shipped rule — `_next_probe` returns None the moment
a plan exists, so every confirmation is pressed because the model on hand yields NO plan. So the
question is not "can a confirmation be cut" (seven arms say no) but "how wrong is the model at
each action, and what would the level have cost if the FINAL model had been in hand there".

For every action of level 4 this records the board, the model, and afterwards replays the FINAL
model against every recorded board: ``k + len(plan(board_k, final_model))`` is what the level
would have cost had the model converged by action k. The minimum over k is the floor that better
RECOVERY (as opposed to fewer confirmations) could reach.

Expected feedback: if that minimum is >= 17 the level is closed — no recovery improvement reaches
the human 16 and the six confirmations are load-bearing for a second, independent reason. If it
is <= 16 it names the exact action by which the model must be right, and by how much.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402


def _key(perm: dict) -> str:
    return json.dumps(sorted((list(k), list(v)) for k, v in perm.items()))


def main() -> None:
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    from score_efficiency import _make_agent  # the SHIPPED construction, mirrored not re-derived

    from admorphiq.tools import cyclepress as cp

    state = {"level": 0, "n": 0}
    rows: list[dict] = []
    orig = cp.CyclePressTool.propose

    def propose_wrap(self, frames, obs):
        pre_perm = {k: dict(v) for k, v in self._perm.items()}
        board = None
        if cp.has_frame(obs):
            g = self._board_grid(obs)
            rb = cp.read_board(g)
            if rb is not None:
                tiles, side, _pitch = rb
                marks = cp.markers_on(g, tiles, side)
                if marks:
                    board = (dict(tiles), list(marks))
        steps = orig(self, frames, obs)
        if state["level"] == 3:
            state["n"] += 1
            rows.append({
                "k": state["n"],
                "step": steps[0] if steps else None,
                "board": board,
                "perm": pre_perm,
                "streak": {str(k): v for k, v in self._streak.items()},
                "plan_left": len(self._plan),
            })
        return steps

    cp.CyclePressTool.propose = propose_wrap

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(e for e in arcade.get_environments()
                if "lp85" in f"{e.game_id} {e.title or ''}".lower())
    agent = _make_agent("unified", game_id=info.game_id)
    env = arcade.make(info.game_id)
    obs = env.observation_space
    prev = int(obs.levels_completed)
    state["level"] = prev
    total = 0
    this_level = 0
    per_level: list[int] = []
    final_perm: dict = {}
    restart = bool(getattr(agent, "restart_on_game_over", False))

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
            if state["level"] == 3 and rows:
                # The model as of the LAST propose of level 4 — press k is learned at propose
                # k+1, and propose 19 belongs to the next level, which resets the tool.
                final_perm = rows[-1]["perm"]
            state["level"] = cur
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            this_level += 1
            if obs is None:
                break

    final_key = _key(final_perm)
    out = []
    for r in rows:
        board = r["board"]
        with_final = None
        with_own = None
        if board is not None and final_perm:
            tiles, marks = board
            p = cp.plan_presses(tiles, marks, final_perm)
            with_final = None if p is None else len(p)
            po = cp.plan_presses(tiles, marks, r["perm"]) if r["perm"] else None
            with_own = None if po is None else len(po)
        out.append({
            "k": r["k"],
            "step": r["step"],
            "n_perms": len(r["perm"]),
            "perm_matches_final": _key(r["perm"]) == final_key,
            "same_as_final_per_control": sorted(
                str(c) for c in r["perm"]
                if c in final_perm and r["perm"][c] == final_perm[c]),
            "streak": r["streak"],
            "plan_left": r["plan_left"],
            "plan_with_own_model": with_own,
            "plan_with_final_model": with_final,
            "total_if_final_here": None if with_final is None else r["k"] - 1 + with_final,
        })

    print(json.dumps({
        "per_level": per_level,
        "total_actions": total,
        "n_final_perms": len(final_perm),
        "l4": out,
        "best_total_with_final_model": min(
            (r["total_if_final_here"] for r in out if r["total_if_final_here"] is not None),
            default=None),
    }))



if __name__ == "__main__":
    main()
