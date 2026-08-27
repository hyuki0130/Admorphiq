"""Drive the linkage tool against a live game and report how deep it gets.

    uv run python scripts/linkage_probe.py [title] [cap] [start-level]

``start-level`` is a DEV-TIME shortcut that seats the engine on a deeper board so a wall can be
studied without paying for the levels in front of it; it touches the engine, never the tool.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

import numpy as np  # noqa: E402

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
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 900
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    if start:
        env._game.set_level(start)
        obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})

    tool = LinkageReachTool()
    g = np.asarray(obs.frame)[-1]
    colour = marker_colour(g)
    controls = read_controls(g)
    two = [c for c in controls if len(c["clicks"]) == 2]
    print(f"  read: marker={colour} two-way={len(two)} one-way={len(controls) - len(two)} "
          f"detect={tool.detect([], obs):.2f}")
    if colour is not None:
        m = read_markers(g, colour)
        print(f"        movers={m.movers} places={m.places}")

    acted = 0
    mark = 0
    board = start
    cleared: list[int] = []
    while acted < cap:
        steps = tool.propose([], obs)
        if not steps:
            print(f"  stop: no proposal on board {board} after {acted - mark} actions there")
            break
        for _, xy in steps:
            obs = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
            acted += 1
        state = str(getattr(obs, "state", ""))
        now = env._game.level_index
        if now != board:
            print(f"  board {board} cleared in {acted - mark} actions")
            cleared.append(acted - mark)
            board, mark = now, acted
        if "GAME_OVER" in state or "WIN" in state:
            print(f"  {state} at {acted} actions")
            break
    print(f"{title} linkage: {len(cleared)} boards cleared from level {start} "
          f"in {acted} actions, per board {cleared}")


if __name__ == "__main__":
    main()
