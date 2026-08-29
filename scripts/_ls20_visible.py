"""Are ls20's fuel pickups VISIBLE under the fog, or only once you reach them?

The whole fuel-routing lever assumes a planner can see the six `npxgalaybz` rings and route through
them. If the fog hides a pickup until the avatar is on top of it, there is nothing to plan with and
the lever collapses into ordinary exploration. The ring is a 3x3 of colour 11 with a transparent
centre, so counting colour-11 pixels per frame answers it directly.

Expected feedback: a count that starts near six rings' worth and only falls as they are collected
means they are plannable. A count that starts at zero and rises as the avatar explores means the fog
hides them and a fuel-aware router cannot exist without exploring first anyway.
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
    trace: list = []
    banked: list = []
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", 0) or 0)
        if now != lvl:
            # ⛔ BANK BEFORE RESETTING. Clearing the last level wipes the counter a step before it
            # is printed, and the script then reports "level 7 not observed" — which reads exactly
            # like the level never happened. This exact bug was found and fixed earlier in this same
            # round, in a different file: the fix lived in a script instead of a shared helper.
            if lvl == 6 and trace:
                banked = list(trace)
            lvl = now
            trace = []
            continue
        if lvl != 6:
            continue
        g = np.array(obs.frame[-1], dtype=np.int16)
        # Colour 11 is BOTH the gauge and the pickups. The gauge is a bar pinned to the frame's
        # edge; a pickup is a 3x3 ring out on the board. Split them by position so the tool can
        # read its own fuel AND see where the refills are.
        m = g == 11
        edge = m.copy()
        edge[6:58, 6:58] = False
        board = m.copy()
        board[:6, :] = board[-6:, :] = board[:, :6] = board[:, -6:] = False
        trace.append((int(edge.sum()), int(board.sum())))
    trace = banked or trace
    if not trace:
        print("level 7 not observed")
        return
    print(f"ls20 level 7: colour-11 pixels over {len(trace)} steps")
    print(f"  first 12 (gauge, board): {trace[:12]}")
    gg = [a for a, _ in trace]
    bb = [b for _, b in trace]
    print(f"  gauge: min {min(gg)} max {max(gg)} last {gg[-1]}")
    print(f"  board: min {min(bb)} max {max(bb)} last {bb[-1]}  (a pickup ring is 8 px)")
    print("  a pickup is a 3x3 ring = 8 pixels, so six pickups = 48")


if __name__ == "__main__":
    main()
