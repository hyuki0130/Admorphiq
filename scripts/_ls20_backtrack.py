"""How much of ls20's level 7 is REVEALING, and how much is walking ground already seen?

The level takes 288 effective moves against a human's 186, and every one of them changes the board,
so the gap is not harness waste — it is the price of exploring under fog. That price has two parts:
steps that uncover new cells, and steps that re-cross ground already uncovered. Only the second is
recoverable, and its size decides whether ls20's +0.0062 headline is worth chasing.

Expected feedback: a large re-crossing share means better routing recovers real points. A small one
means 288 is near the floor for exploring this maze blind, and the headline is not achievable.
"""
from __future__ import annotations

import numpy as np


def main() -> None:
    import sys

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 6

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    seen_cells: set[bytes] = set()
    revealed = 0
    steps = 0
    known = None
    lvl = 0
    counts: dict[int, int] = {}
    banked: dict[int, tuple[int, int]] = {}
    visits: dict = {}
    prev_g = None
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", 0) or 0)
        if now != lvl:
            # ⛔ Bank BEFORE resetting: the first version wiped its own counters on the final
            # level-up and printed zeros, which reads exactly like "the level was never played".
            if steps:
                banked[lvl] = (steps, revealed)
            lvl = now
            known = None
            seen_cells.clear()
            revealed = steps = 0
            continue
        counts[lvl] = counts.get(lvl, 0) + 1
        if lvl != target:
            continue
        g = np.array(obs.frame[-1], dtype=np.int16)
        steps += 1
        # "Revealed" = the set of non-background cells the frame has ever shown. Under fog the map
        # grows only when a step uncovers something, so a step that leaves it unchanged is a step
        # across ground already known.
        if known is None:
            known = set(map(tuple, np.argwhere(g != np.bincount(g.ravel()).argmax())))
            continue
        cells = set(map(tuple, np.argwhere(g != np.bincount(g.ravel()).argmax())))
        fresh = cells - known
        if fresh:
            revealed += 1
            known |= cells
        # ⛔ Re-crossing is only WASTE if the same places keep coming round. The avatar is the one
        # small thing that moves every step, so track the diff between consecutive frames: how many
        # DISTINCT positions the level visits, and how often each is revisited. A route that walks a
        # long corridor once is efficient; one that oscillates over ten cells is not.
        d = np.argwhere(g != prev_g) if prev_g is not None else np.empty((0, 2), int)
        prev_g = g
        if len(d):
            spot = (int(d[:, 0].mean()) // 4, int(d[:, 1].mean()) // 4)
            visits[spot] = visits.get(spot, 0) + 1

    if steps:
        banked[lvl] = (steps, revealed)
    print("steps per levels_completed value:", counts)
    for k, (st, rv) in sorted(banked.items()):
        print(f"  level {k + 1}: {st} steps, {rv} uncovered new, {st - rv} re-crossed"
              f" ({round(100 * (st - rv) / st)}%)")
    if visits:
        top = sorted(visits.values(), reverse=True)
        print(f"  distinct places touched {len(visits)}; most-revisited {top[:8]};"
              f" mean visits per place {sum(top) / len(top):.1f}")
    print(f"ls20 target level: {steps} steps, {revealed} uncovered something new, "
          f"{steps - revealed} re-crossed known ground "
          f"({0 if not steps else round(100 * (steps - revealed) / steps)}%)")


if __name__ == "__main__":
    main()
