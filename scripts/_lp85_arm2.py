"""lp85 arm bench, second pass — the constants and cost rules the first pass did not reach.

Mirrors ``scripts/score_efficiency.py:run_game`` (empty frames list, restart_on_game_over,
BREAK on WIN) and reports per-level action counts plus the RHAE game score computed the way the
scorer computes it. Arm per fan seed, so every arm is measured concurrently on the same harness.

Level 4 costs 18 against a human 16 and `scripts/_lp85_l4_converge.py` prices every intermediate
outcome: planning at propose 9 costs 15, at propose 10 costs 17, at propose 11 costs 18 (what
happens). So an arm must save TWO discovery presses to reach the cap and ONE to score anything at
all. `_MAX_PRESSES` 3 and 7 were measured in the first pass (3 loses levels 5 and 6, 7 is
identical); 4, 5 and 6 were not, and 4 is the value at which the harder of the two used controls
leaves the confirmation queue the moment its model is right.

Arm 3 is the recovery cost: `scripts/_lp85_cost.py` shows the shipped least-total-distance rule
recovers 14 of 34 controls exactly from ONE press, and that level 4's two USED controls are not
among them — their truth costs MORE total distance (76) and has FEWER long steps (4) than the
permutation the rule picks (70 / 7). Charging per long step is the objective that would prefer it.

Expected feedback: an arm that takes level 4 to 16 or fewer WITHOUT adding an action to any other
level is a candidate; anything costing an action on levels 1/2/3/5/6/7/8 is a loss, since all
seven sit at the metric's cap with zero headroom.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402

ARMS = ["control", "maxpresses4", "maxpresses6", "longstep8", "longstep2",
        "maxpresses4+longstep8", "maxpresses5", "confirm3"]


def _apply(arm: str, cp) -> None:
    if "maxpresses4" in arm:
        cp._MAX_PRESSES = 4
    if "maxpresses5" in arm:
        cp._MAX_PRESSES = 5
    if "maxpresses6" in arm:
        cp._MAX_PRESSES = 6
    if "confirm3" in arm:
        cp._CONFIRM_STREAK = 3
    pen = 8.0 if "longstep8" in arm else (2.0 if "longstep2" in arm else None)
    if pen is None:
        return
    orig = cp.recover_permutation

    def recover(slots, pairs, pitch, _pen=pen, _o=orig):
        """Least (long-step count, total distance) instead of least total distance."""
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
                    cost[i][j] = d + (_pen if d > 1.0 else 0.0)
            picked = cp._assign(cost)
            if picked is None:
                return None
            for i, s in enumerate(rest):
                fixed[s] = targets[picked[i]]
        return fixed

    cp.recover_permutation = recover
    import admorphiq.tools.cyclepress as mod
    mod.recover_permutation = recover


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    arm = ARMS[(seed - 1) % len(ARMS)]

    from score_efficiency import _make_agent

    from admorphiq.tools import cyclepress as cp
    _apply(arm, cp)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(e for e in arcade.get_environments()
                if "lp85" in f"{e.game_id} {e.title or ''}".lower())
    baseline = list(info.baseline_actions or [])
    agent = _make_agent("unified", game_id=info.game_id)
    env = arcade.make(info.game_id)
    obs = env.observation_space
    win_levels = int(obs.win_levels)
    prev = int(obs.levels_completed)
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

    num = 0.0
    den = float(sum(range(1, win_levels + 1)))
    scores = []
    for i, spent in enumerate(per_level):
        human = baseline[i] if i < len(baseline) else None
        s = 0.0 if not human or not spent else min(human / spent, 1.0) ** 2
        scores.append(round(s, 6))
        num += (i + 1) * s
    print(json.dumps({
        "arm": arm, "per_level": per_level, "total_actions": total,
        "levels": int(prev), "per_level_score": scores,
        "game_score": round(num / den, 6) if den else 0.0,
    }))


if __name__ == "__main__":
    main()
