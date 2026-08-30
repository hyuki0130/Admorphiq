"""Can lp85's two hard controls be recovered from ONE press by charging for LONG steps?

Mirrors ``scripts/score_efficiency.py:run_game`` and reproduces the banked per-level counts.

`scripts/_lp85_l4_converge.py` measured that level 4's whole loss is DISCOVERY: with the
converged model in hand at the opening the level costs EIGHT actions, and the ten probe presses
leave the plan exactly as long as it was before them. Four of the ten are the fresh presses; the
other six exist only because two controls' single-press recovery is WRONG. The other two controls
are recovered exactly from one press each.

`recover_permutation` picks, among the permutations that replay the press, the one of least TOTAL
Manhattan distance. Its own docstring says the truth is "one long step per cycle" — a cycle's
closing step hands the last slot back to the first. But a SUM does not encode that: a permutation
with two medium steps can beat one with a single long step.

This measures, for every control on every level, the perm recovered from its FIRST press alone
against the perm the tool converges on, under the shipped cost and under a lexicographic cost that
charges a fixed penalty per step longer than one lattice cell.

Expected feedback: if the lexicographic cost recovers the two hard controls of level 4 from one
press each and never disagrees with a converged perm elsewhere, the six confirmations become
unnecessary and level 4 falls to 12 actions. If it does not, the recovery axis is closed too.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402


def recover_v2(cp, slots, pairs, pitch, penalty):
    """`recover_permutation` with a fixed surcharge on any step longer than one lattice cell."""
    if not pairs:
        return None
    cand = cp._candidates(slots, pairs)
    if any(not c for c in cand.values()):
        return None
    fixed, open_slots, changed = {}, set(slots), True
    while changed:
        changed = False
        for s in sorted(open_slots):
            free = cand[s] - set(fixed.values())
            if len(free) == 1:
                fixed[s] = next(iter(free))
                open_slots.discard(s)
                changed = True
            elif not free:
                return None
    rest = sorted(open_slots)
    if rest:
        taken = set(fixed.values())
        targets = sorted({t for s in rest for t in cand[s]} - taken)
        if len(targets) != len(rest):
            return None
        index = {t: j for j, t in enumerate(targets)}
        step = max(1, pitch)
        cost = [[cp._BIG] * len(targets) for _ in rest]
        for i, s in enumerate(rest):
            for t in cand[s]:
                j = index.get(t)
                if j is None:
                    continue
                d = (abs(t[0] - s[0]) + abs(t[1] - s[1])) / step
                cost[i][j] = d + (penalty if d > 1.0 else 0.0)
        picked = cp._assign(cost)
        if picked is None:
            return None
        for i, s in enumerate(rest):
            fixed[s] = targets[picked[i]]
    return fixed


def _shape(perm, pitch):
    if not perm:
        return None
    step = max(1, pitch)
    ds = [(abs(t[0] - s[0]) + abs(t[1] - s[1])) / step for s, t in perm.items() if s != t]
    return {"moved": len(ds), "long": sum(1 for d in ds if d > 1.0),
            "total": round(sum(ds), 2), "max": round(max(ds), 2) if ds else 0}


def main() -> None:
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    from score_efficiency import _make_agent

    from admorphiq.tools import cyclepress as cp

    state = {"level": 0}
    first_pair: dict[int, dict] = {}      # level -> control -> the control's FIRST transition
    geom: dict[int, tuple] = {}           # level -> (slots, pitch)
    finals: dict[int, dict] = {}
    orig = cp.CyclePressTool.propose

    def propose_wrap(self, frames, obs):
        steps = orig(self, frames, obs)
        lvl = state["level"]
        fp = first_pair.setdefault(lvl, {})
        for c, pairs in self._pairs.items():
            if c not in fp and pairs:
                fp[c] = pairs[0]
        geom[lvl] = (list(self._slots), self._pitch)
        finals[lvl] = {c: dict(p) for c, p in self._perm.items()}
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

    penalties = [0.0, 2.0, 8.0, 64.0, 1000.0]
    rows = []
    for lvl in sorted(first_pair):
        slots, pitch = geom.get(lvl, ([], 1))
        fin = finals.get(lvl, {})
        for c, pair in sorted(first_pair[lvl].items()):
            truth = fin.get(c)
            row = {"level": lvl + 1, "control": str(c),
                   "truth_shape": _shape(truth, pitch)}
            for pen in penalties:
                got = recover_v2(cp, slots, [pair], pitch, pen)
                row[f"p{pen:g}"] = (None if truth is None else (got == truth))
                if pen == 0.0:
                    row["shipped_shape"] = _shape(got, pitch)
            rows.append(row)
    print(json.dumps({
        "per_level": per_level, "total_actions": total,
        "summary": {f"p{p:g}": sum(1 for r in rows if r.get(f"p{p:g}") is True)
                    for p in penalties},
        "n_controls": len(rows),
        "rows": rows,
    }))


if __name__ == "__main__":
    main()
