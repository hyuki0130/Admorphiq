"""Drive the track tool against a live game and report how deep it gets.

`--level N` starts at a later board, which is dev-time only: it reaches into the environment to
skip ahead so a deep board can be read without paying for the ones before it. The tool itself
never sees anything but the frame.
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "src")

from admorphiq.adapters25.base import canonical_layer  # noqa: E402
from admorphiq.tools.track import (  # noqa: E402
    TrackAlignTool,
    controls_on,
    markers_on,
    read_board,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("title", nargs="?", default="lp85")
    ap.add_argument("--cap", type=int, default=400)
    ap.add_argument("--level", type=int, default=0)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(args.title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    if args.level:
        env._game.set_level(args.level)
        obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})

    tool = TrackAlignTool()
    g = canonical_layer(obs)
    board = read_board(g)
    if board is None:
        print(f"  read: not a tile board  detect={tool.detect([], obs):.2f}")
    else:
        tiles, side, pitch = board
        print(f"  read: {len(tiles)} tiles side={side} pitch={pitch} "
              f"marks={len(markers_on(g, tiles, side))} "
              f"controls={len(controls_on(g, tiles, side))} "
              f"detect={tool.detect([], obs):.2f}")

    done = int(getattr(obs, "levels_completed", 0) or 0)
    base = done
    acted = 0
    idle = 0
    while acted < args.cap and idle < 4:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
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
            if not args.quiet:
                print(f"  board {args.level + new - base}: cleared at {acted} actions")
            done = new
        if "GAME_OVER" in state:
            print(f"     GAME_OVER at {acted} actions")
            break
    print(f"{args.title} track: {done - base} boards from level {args.level} in {acted} actions")


if __name__ == "__main__":
    main()
