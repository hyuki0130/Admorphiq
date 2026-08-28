"""Is lf52's level-6 stall a LAUNCH mechanic? Verify the source reading against the live engine.

Read from `lf52.py` (engine never started): when a piece would move into a `kraubslpehi` and is
standing on a `fozwvlovdui`, it is displaced by `(-dx*6, 0)` at levels 5 and 6 instead of moving one
cell. That predicts a SIX-CELL displacement opposite the pressed direction — a magnitude no ordinary
move can produce, so one observation settles it.

Expected feedback: a line reporting displacement 6 confirms the launcher and makes it a tool lever;
displacements of only 0 or 1 refute the reading and the source was misread.
"""
from __future__ import annotations

import sys

import numpy as np


def _pieces(g: np.ndarray) -> set[tuple[int, int]]:
    """Cells of the least-common non-background colour — the pieces, whatever colour they are."""
    vals, counts = np.unique(g, return_counts=True)
    order = [v for _, v in sorted(zip(counts, vals, strict=True))]
    for v in order:
        cells = set(map(tuple, np.argwhere(g == v)))
        if 1 <= len(cells) <= 200:
            return cells
    return set()


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.types import ActionType, GameAction

    target = int(sys.argv[1]) if len(sys.argv) > 1 else 5   # levels_completed to reach

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    for _ in range(4000):
        if int(getattr(obs, "levels_completed", 0) or 0) >= target:
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    lvl = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"reached levels_completed={lvl}", flush=True)
    if lvl < target:
        print("did not reach the level; nothing to say about the mechanic")
        return

    keys = [(1, "UP"), (2, "DOWN"), (3, "LEFT"), (4, "RIGHT")]
    seen: list[int] = []
    for rep in range(60):
        aid, name = keys[rep % 4]
        g0 = np.array(obs.frame[-1], dtype=np.int16)
        obs = env.step(agent._convert(GameAction.simple(ActionType(aid))))
        g1 = np.array(obs.frame[-1], dtype=np.int16)
        ndiff = int((g0 != g1).sum())
        # Assumption-free: how far did each colour's centre of mass move?
        shift = 0.0
        for v in set(np.unique(g0)) & set(np.unique(g1)):
            c0 = np.argwhere(g0 == v).mean(axis=0)
            c1 = np.argwhere(g1 == v).mean(axis=0)
            shift = max(shift, float(np.abs(c0 - c1).max()))
        seen.append(ndiff)
        if ndiff:
            print(f"  {name}: {ndiff} cells changed, max colour-centroid shift {shift:.2f}",
                  flush=True)
    print("changed-cell counts seen:", sorted(set(seen)))


if __name__ == "__main__":
    main()
