"""Drive the linkage tool against a live game and report how deep it gets."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

import numpy as np  # noqa: E402

from admorphiq.tools.base import frame_2d  # noqa: E402
from admorphiq.tools.linkage import (  # noqa: E402
    LinkageReachTool,
    marker_colour,
    read_controls,
    read_markers,
)


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "s5i5"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = LinkageReachTool()
    g = np.asarray(frame_2d(obs))
    colour = marker_colour(g)
    controls = read_controls(g)
    two_way = [c for c in controls if len(c["clicks"]) == 2]
    print(f"  read: marker={colour} controls={len(controls)} two-way={len(two_way)} "
          f"detect={tool.detect([], obs):.2f}")
    if colour is not None:
        m = read_markers(g, colour)
        print(f"        movers={m.movers} places={m.places}")

    done = 0
    acted = 0
    idle = 0
    marks = [0]
    while acted < cap and idle < 3:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            print(f"     no proposal at level {done} after {acted} actions")
            break
        idle = 0
        for _, xy in steps:
            obs = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
            acted += 1
        new = int(getattr(obs, "levels_completed", done) or 0)
        state = str(getattr(obs, "state", ""))
        if new != done:
            print(f"  level {new}: cleared at {acted} actions (+{acted - marks[-1]})")
            marks.append(acted)
            done = new
            tool.reset()
        if "GAME_OVER" in state or "WIN" in state:
            print(f"     {state} at {acted} actions")
            break
    print(f"{title} linkage: {done} levels in {acted} actions")


if __name__ == "__main__":
    main()
