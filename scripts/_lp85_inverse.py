"""Is a control's permutation recoverable as the INVERSE of another control's, and WHEN?

Mirrors ``scripts/score_efficiency.py:run_game`` (empty frames list, restart_on_game_over,
BREAK on WIN) and reproduces the banked per-level counts.

lp85 level 4 costs 18 against a human 16, and `scripts/_lp85_l4_converge.py` shows the whole
loss is DISCOVERY: the eight-press solution is eight presses from the OPENING board and still
eight after ten probes, so the ten probes buy only the model. Four of those ten are the fresh
presses; six are re-presses of the two controls whose single-press recovery was WRONG. The two
controls that are never used in the plan converged from ONE press each.

The game's controls are rings x directions, so each control's permutation is the exact inverse of
its opposed twin. `_confirm_inverse` already exploits that, but only when two INDEPENDENTLY
recovered permutations happen to come out exactly inverse; and `_twin` adopts only from a control
already CONFIRMED, which on level 4 never happens for the two instant converges.

This asks the question that decides whether an inverse-adoption rule is worth building: at each
propose, for every control `c` still unconfirmed and every other control `d` with a recovered
permutation, does `inverse(perm[d])` REPLAY every transition `c` has produced — and when it does,
is it the permutation `c` eventually converges on?

Expected feedback: a rule is worth building only if the hits are early AND correct. Every row
printed carries `agrees_with_final`; a single False anywhere in the eight levels says the
constraint is not sound and the arm is dead before it is written.
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

    state = {"level": 0, "k": 0}
    # level -> {"hits": [...], "final": {...}}
    per_level_hits: dict[int, list[dict]] = {}
    finals: dict[int, dict] = {}
    orig = cp.CyclePressTool.propose

    def propose_wrap(self, frames, obs):
        steps = orig(self, frames, obs)
        lvl = state["level"]
        state["k"] += 1
        hits = per_level_hits.setdefault(lvl, [])
        seen = {h["control"] for h in hits}
        for c, pairs in self._pairs.items():
            if str(c) in seen or self._streak.get(c, 0) >= cp._CONFIRM_STREAK:
                continue
            for d, perm in self._perm.items():
                if d == c:
                    continue
                back = {v: k for k, v in perm.items()}
                if all(cp._replays(back, b, a) for b, a in pairs):
                    hits.append({
                        "control": str(c), "from": str(d), "k": state["k"],
                        "presses_of_c": len(pairs),
                        "cand": sorted((list(x), list(y)) for x, y in back.items()),
                    })
                    seen.add(str(c))
                    break
        finals[lvl] = {str(k): sorted((list(a), list(b)) for a, b in v.items())
                       for k, v in self._perm.items()}
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
    total, this_level = 0, 0
    per_level: list[int] = []
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
            state["level"] = cur
            state["k"] = 0
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

    rows = []
    for lvl in sorted(per_level_hits):
        fin = finals.get(lvl, {})
        for h in per_level_hits[lvl]:
            rows.append({
                "level": lvl + 1, "control": h["control"], "from": h["from"],
                "k": h["k"], "presses_of_c": h["presses_of_c"],
                "agrees_with_final": fin.get(h["control"]) == h["cand"],
                "final_known": h["control"] in fin,
            })
    print(json.dumps({
        "per_level": per_level, "total_actions": total,
        "n_hits": len(rows),
        "n_disagree": sum(1 for r in rows if r["final_known"] and not r["agrees_with_final"]),
        "hits": rows,
    }))


if __name__ == "__main__":
    main()
