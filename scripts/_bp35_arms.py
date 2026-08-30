"""A/B the three crag changes on bp35, one arm per combination, and score them the runner's way.

Three changes were built from three measurements: `_reanchor` (a window sharing no row with the map
is the board's next strip, not a different board), `_catchers` (the editable cell a reversal would
land on, which the local five cannot name), and `_MAX_EDITS` 6 -> 10 (no win exists on board 6 under
a six-click cap at all). Each is worthless without evidence that it is the one doing the work, so
every combination is run: seed-1 is the bit mask, bit 0 = catchers, bit 1 = the raised cap, bit 2 =
reanchor. Arm 0 is the SHIPPED tool and is the negative control — it must reproduce 5 levels and 726
actions or the harness is not the one the gate measures.

⛔ Scoring mirrors `scripts/score_efficiency.py:run_game` exactly (rule 7aj.1): empty frames list,
`restart_on_game_over` honoured, BREAK on WIN, per-level counts reset on each level-up, and the
game's weight denominator is ALL nine levels.

Expected feedback: an arm that clears board 6 names the change that did it. An arm that clears
nothing more than the control says the diagnosis was wrong, not that the change was small.

Usage: _bp35_arms.py <seed>   seed-1 in 0..7 selects the mask.
"""
from __future__ import annotations

import json
import sys
import time

HUMAN = [21, 48, 44, 38, 33, 87, 86, 131, 163]


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    mask = (seed - 1) % 8

    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools import crag as cragmod

    if not mask & 1:
        cragmod.CragTool._catchers = lambda self, cells, at, gdir: []
    if not mask & 2:
        cragmod._MAX_EDITS = 6
    if not mask & 4:
        cragmod.CragTool._reanchor = lambda self, readings, allow: None

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    env = arcade.make(info.game_id)
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=8000, stall=80, ctx_budget=6000)
    obs = env.observation_space
    restart = bool(getattr(agent, "restart_on_game_over", False))
    win_levels = int(obs.win_levels)
    prev = int(obs.levels_completed)
    per_level: list[int] = []
    here = total = 0
    holders: dict[str, int] = {}
    t0 = time.time()
    while total < budget:
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        if not isinstance(act, GameAction):
            break
        key = f"L{prev}:{agent._current}"
        holders[key] = holders.get(key, 0) + 1
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        if obs is None:
            break
        total += 1
        here += 1
        cur = int(obs.levels_completed)
        if cur > prev:
            for _ in range(cur - prev):
                per_level.append(here)
                here = 0
            prev = cur
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            here += 1
            if obs is None:
                break

    num = 0.0
    scores = []
    for i, acts in enumerate(per_level):
        s = min(HUMAN[i] / acts, 1.0) ** 2 if acts else 0.0
        scores.append(round(s, 4))
        num += (i + 1) * s
    den = win_levels * (win_levels + 1) / 2
    crag = agent.tools.get("crag")
    print(json.dumps({
        "seed": seed, "mask": mask,
        "reanchor": bool(mask & 4), "catchers": bool(mask & 1), "edits": 10 if mask & 2 else 6,
        "levels": len(per_level), "actions": total, "per_level": per_level,
        "level_scores": scores, "game_score": round(num / den, 5),
        "secs": round(time.time() - t0, 1),
        "holders": dict(sorted(holders.items())),
        "crag_note": crag._note, "crag_world": len(crag._world), "crag_mute": crag._mute,
    }))


if __name__ == "__main__":
    main()
