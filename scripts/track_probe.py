"""Drive the track tool against a live game and report how deep it gets."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.adapters25.base import canonical_layer  # noqa: E402
from admorphiq.tools.track import TrackAlignTool, loop_order, tiles_of  # noqa: E402


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "lp85"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = TrackAlignTool()
    done = 0
    acted = 0
    idle = 0
    g = canonical_layer(obs)
    blocks, side = tiles_of(g)
    print(f"  read: {len(blocks)} blocks side={side} loop={'yes' if blocks and loop_order(list(blocks), 6) else '?'} "
          f"detect={tool.detect([], obs):.2f}")
    while acted < cap and idle < 3:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            if idle >= 3:
                print(f"     no proposal at level {done} after {acted} actions")
                break
            # The frame following a level-up still shows the board just finished, so a tool that
            # reads it correctly reports "already aligned". One action moves it on.
            obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})
            acted += 1
            continue
        idle = 0
        for _, xy in steps:
            obs = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
            acted += 1
        new = int(getattr(obs, "levels_completed", done) or 0)
        state = str(getattr(obs, "state", ""))
        if new != done:
            print(f"  level {new}: cleared at {acted} actions")
            done = new
            tool.reset()
        if "GAME_OVER" in state:
            print(f"     GAME_OVER at {acted} actions")
            break
    print(f"{title} track: {done} levels in {acted} actions")


if __name__ == "__main__":
    main()
