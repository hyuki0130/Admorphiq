"""Drive the haul tool against a live game and report how deep it gets.

`--trace N` prints the tool's own reading of the board once level N is reached, which is the
only way to see WHY a plan stops: what it thinks the carrier, the cargo, the bays and the
furniture are, against a board it may be reading wrong.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.base import frame_2d  # noqa: E402
from admorphiq.tools.haul import HaulDeliveryTool  # noqa: E402


def report(tool: HaulDeliveryTool, obs: object) -> str:
    """The tool's own reading of the board, so a stall can be seen rather than guessed."""
    board = tool._read(frame_2d(obs))
    if board is None:
        return "unreadable"
    return (f"carrier={board.carrier} face={board.facing} held={tool._offset} "
            f"cargo={sorted(board.cargo)} bays={sorted(board.bays)} "
            f"walls={len(board.blocked)} porous={len(board.porous)} parked={sorted(tool._parked)} "
            f"hostile={board.hostile} movers={board.movers} marked={sorted(board.marked)} "
            f"roam={sorted(tool._roam)} friendly={sorted(tool._friendly)}")


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "wa30"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    trace_from = int(sys.argv[3]) if len(sys.argv) > 3 else -1
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = HaulDeliveryTool()
    acts = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
            4: GameAction.ACTION4, 5: GameAction.ACTION5}
    done = 0
    acted = 0
    idle = 0
    mark = 0
    print(f"  detect={tool.detect([], obs):.2f}  baseline={info.baseline_actions}")
    while acted < cap and idle < 3:
        if done >= trace_from >= 0:
            print(f"  [{acted}] {report(tool, obs)}")
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            print(f"  idle at {acted} (level {done})")
            continue
        idle = 0
        for aid, _ in steps:
            if done >= trace_from >= 0:
                print(f"        -> {aid}")
            obs = env.step(acts[aid])
            acted += 1
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new != done:
            print(f"  level {new}: cleared at {acted} actions (+{acted - mark})")
            done, mark = new, acted
        if "GAME_OVER" in str(getattr(obs, "state", "")):
            print(f"  GAME_OVER at {acted} (levels={done})")
            break
    print(f"{title} haul: {done} levels in {acted} actions")


if __name__ == "__main__":
    main()
