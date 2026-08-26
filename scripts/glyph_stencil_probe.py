"""Drive the stencil tool against a live game and report how deep it gets.

The mechanic and every derivation live in `admorphiq.tools.stencil` — ONE implementation. This
file is the driver only: it plays, it does not decide.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.adapters25.base import canonical_layer  # noqa: E402
from admorphiq.tools.stencil import all_tiles, pitch, plan, tiles  # noqa: E402

__all__ = ["all_tiles", "pitch", "plan", "tiles"]


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "ft09"
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    code: dict[int, bool] = {}
    done = 0
    acted = 0
    stale = 0
    while acted < 200 and stale < 3:
        if not (getattr(obs, "frame", None) or []):
            print("     the frame went empty — stopping")
            break
        g = canonical_layer(obs)
        board = tiles(g)
        clicks, code = plan(g, code)
        if not clicks:
            if stale == 0:
                side = next(iter(board.values()))["size"] if board else 0
                stencils = [o for o, v in board.items() if len(v["colours"]) > 1]
                print(f"     stalled at level {done}: tiles={len(board)} side={side} "
                      f"pitch={pitch(list(board), side) if board else 0} stencils={stencils} code={code}")
            stale += 1
            obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})
            acted += 1
            continue
        stale = 0
        y, x = clicks[0]
        obs = env.step(GameAction.ACTION6, data={"x": x, "y": y})
        acted += 1
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new < done:
            print(f"     level RESET ({done} -> {new}) after {acted} actions — stopping")
            break
        if new != done:
            side = next(iter(board.values()))["size"]
            print(f"  level {new}: cleared — {len(board)} tiles, side {side}, "
                  f"pitch {pitch(list(board), side)} ({acted} actions so far)")
            done = new
    print(f"{title} glyph-stencil: {done} levels in {acted} actions")


if __name__ == "__main__":
    main()
