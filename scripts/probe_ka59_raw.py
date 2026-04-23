"""Round 19 raw-level diagnostic: press each dir action on KA59 L1
start and dump the raw frame diff. Bypasses observation_phase to
confirm whether directional moves produce visible frame changes at
all on this env.
"""

from __future__ import annotations

import numpy as np

from arcengine import GameAction


def main() -> None:
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    gid = None
    for info in arcade.get_environments():
        if (info.title or "").upper() == "KA59":
            gid = info.game_id
            break
    env = arcade.make(gid)
    obs = env.step(GameAction.RESET)
    base = np.array(obs.frame[0], dtype=np.int32)
    print(f"KA59 {gid} base_levels={obs.levels_completed} avail={obs.available_actions}")
    print(f"base frame shape={base.shape} unique_colors={sorted(set(base.flatten().tolist()))}")
    for aid in (1, 2, 3, 4):
        env.step(GameAction.RESET)
        obs = env.step(GameAction.from_id(aid))
        after = np.array(obs.frame[0], dtype=np.int32)
        diff = (base != after)
        ys, xs = np.where(diff)
        print(
            f"  action {aid}: diff_pixels={int(diff.sum())} "
            f"state={obs.state.name} levels={obs.levels_completed}"
        )
        if diff.sum() > 0:
            print(f"    bbox y={ys.min()}..{ys.max()} x={xs.min()}..{xs.max()}")

    # Also sweep sequences: reset + (dir, dir) pairs.
    print("\n-- action-pair sweep --")
    for a1 in (1, 2, 3, 4):
        env.step(GameAction.RESET)
        env.step(GameAction.from_id(a1))
        obs = env.step(GameAction.from_id(a1))
        after = np.array(obs.frame[0], dtype=np.int32)
        diff = (base != after)
        print(f"  {a1},{a1}: diff_pixels={int(diff.sum())} levels={obs.levels_completed}")


if __name__ == "__main__":
    main()
