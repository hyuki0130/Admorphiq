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

    # The two verbs the source has and the tool never uses: ACTION5 (its own handler,
    # `kuexigxyxw`) and the power-up, which is an ACTION6 in the bottom-left 16x16 corner and is
    # dispatched as a distinct branch rather than as a click.
    # ACTION5 rebuilds the level (`kuexigxyxw` -> `pchvqimdvj`, the level builder), so it gives a
    # FRESH level 6 rather than the dead position the tool left behind. Probe each direction from
    # that fresh state: what the level offers at its start is a different question from what it
    # offers after 500 actions of a tool that does not model the launch.
    keys = [(4, "RIGHT"), (3, "LEFT")]
    seen: list[int] = []
    for rep in range(len(keys)):
        aid, name = keys[rep % len(keys)]
        g0 = np.array(obs.frame[-1], dtype=np.int16)
        if name == "CORNER":
            obs = env.step(agent._convert(GameAction.coordinate(4, 60)),
                           data={"x": 4, "y": 60})
        else:
            obs = env.step(agent._convert(GameAction.simple(ActionType(aid))))
        g1 = np.array(obs.frame[-1], dtype=np.int16)
        ndiff = int((g0 != g1).sum())
        # Assumption-free: how far did each colour's centre of mass move?
        # A LAUNCHER moves one piece; a CAMERA moves everything by the same amount. Reporting the
        # max alone cannot tell them apart, and reporting only the max is how the first reading of
        # this board became a six-cell launcher that does not exist.
        shifts = []
        per = []
        for v in sorted(set(np.unique(g0)) & set(np.unique(g1))):
            n0 = np.argwhere(g0 == v)
            n1 = np.argwhere(g1 == v)
            c0 = n0.mean(axis=0)
            c1 = n1.mean(axis=0)
            d = float(np.abs(c0 - c1).max())
            shifts.append(d)
            per.append(f"c{int(v)}:n{len(n0)}->{len(n1)},d{d:.1f}")
        shift = max(shifts) if shifts else 0.0
        lo = min(shifts) if shifts else 0.0
        seen.append(ndiff)
        print(f"  {name}: {ndiff} cells | " + " ".join(per), flush=True)
        if False:
            print(f"  {name}: {ndiff} cells changed, max colour-centroid shift {shift:.2f}",
                  flush=True)
    print("changed-cell counts seen:", sorted(set(seen)))


if __name__ == "__main__":
    main()
