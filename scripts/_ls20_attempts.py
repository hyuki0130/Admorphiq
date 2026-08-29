"""Does ls20 get FASTER across its three attempts at level 7?

This round concluded the efficiency gap is the irreducible price of discovery. That claim is
falsifiable here: the tool dies twice on level 7 and is thrown back to the start each time. If
discovery is being amortised, attempt 3 should be markedly shorter than attempt 1. If all three cost
about the same, the tool is rediscovering the same board every time and the gap is recoverable
waste after all.

Expected feedback: a falling sequence supports the discovery-cost reading. A flat one refutes it.
"""
from __future__ import annotations

import numpy as np


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    lvl = 0
    prev = None
    attempts: list[int] = []
    run = reveals = 0
    known: set = set()
    banked: list[int] | None = None
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", 0) or 0)
        g = np.array(obs.frame[-1], dtype=np.int16)
        if now != lvl:
            if lvl == 6:
                attempts.append((run, reveals))
                banked = list(attempts)
            lvl, prev, run, attempts = now, None, 0, []
            reveals = 0
            known = set()
            continue
        if lvl != 6:
            prev = g
            continue
        run += 1
        cells = set(map(tuple, np.argwhere(g != int(np.bincount(g.ravel()).argmax()))))
        if cells - known:
            reveals += 1
        known |= cells
        # A death repaints most of the board; it ends one attempt and starts the next.
        if prev is not None and int((g != prev).sum()) > 2048:
            # ⛔ THE DECIDING QUESTION. If a death RE-FOGS the map, repeating the exploration is the
            # game's design and the cost is not the tool's to save. If the map stays lifted, the
            # tool is forgetting what it uncovered. Count the visible (non-background) cells on
            # either side of the death.
            # ⚠️ NOT the visible-cell count at the death frame: the overlay itself adds pixels,
            # so that reading is contaminated by the flash (measured 1068 -> 1292, which says
            # nothing). Count NEW cells uncovered per attempt instead — if attempt two discovers as
            # much as attempt one, the death re-fogged the map and the repetition is the game's.
            attempts.append((run, reveals))
            # ⛔ do NOT clear `known` — clearing it makes attempt two 'rediscover'
            # every cell attempt one already saw, which is a circular measurement.
            run = reveals = 0
        prev = g
    got = banked or attempts
    print("ls20 level 7 attempts (actions, new-discovery steps):", got)
    print("  equal discovery in both attempts = the death re-fogged the map")


if __name__ == "__main__":
    main()
