"""What does one click DO to a tile? Measured, not assumed.

ft09 levels 1-2 start from a uniform board, so "click paints it" is indistinguishable from
"click advances it one step round a cycle". Level 3 starts mixed and the two readings give
different plans, so the cycle has to be measured before any level-3 plan is trustworthy.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

from admorphiq.adapters25.base import canonical_layer  # noqa: E402
from glyph_stencil_probe import all_tiles, plan, tiles  # noqa: E402


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith("ft09"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    code: dict[int, bool] = {}
    done = 0
    acted = 0
    while acted < 120 and done < 2:
        clicks, code = plan(canonical_layer(obs), code)
        if not clicks:
            obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})
            acted += 1
            continue
        y, x = clicks[0]
        obs = env.step(GameAction.ACTION6, data={"x": x, "y": y})
        acted += 1
        done = int(getattr(obs, "levels_completed", done) or 0)
    print(f"reached level {done + 1} in {acted} actions")

    def snap(o):
        b = tiles(canonical_layer(o))
        return {k: sorted(v["colours"]) for k, v in sorted(b.items())}

    before = snap(obs)
    print("before:", before)
    y0, x0 = next(k for k, v in before.items() if len(v) == 1)
    obs = env.step(GameAction.ACTION6, data={"x": x0 + 2, "y": y0 + 2})
    after = snap(obs)
    print(f"clicked ({y0},{x0}) -> levels={getattr(obs,'levels_completed',None)} state={getattr(obs,'state',None)}")
    print("after :", after)
    print("gone  :", sorted(set(before) - set(after)))
    print("new   :", sorted(set(after) - set(before)))
    print("moved :", {k: (before[k], after[k]) for k in set(before) & set(after) if before[k] != after[k]})


if __name__ == "__main__":
    main()
