"""DISPOSABLE: confirm the L5 interface-overlay signals (colour-1 leg->body
tendons, colour-10 active-collector halo) and locate the 4 collectibles on the
frame after masking the overlay, to de-risk the Pass-3 perception design."""
from __future__ import annotations

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.adapters25.r11l import _fill, _hazard_cells, _is_hud_band
from admorphiq.adapters25.r11l import Adapter
from admorphiq.kernels import find_regions


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("r11l")
    obs = env.step(GameAction.RESET)
    game = env._game  # noqa: SLF001
    adapter = Adapter()
    steps = 0
    while steps < 6000:
        if adapter.is_done([], obs):
            break
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        if obs is None:
            break
        steps += 1
        if obs.state.name == "GAME_OVER":
            obs = env.step(GameAction.RESET); steps += 1; continue
        if int(getattr(obs, "levels_completed", 0) or 0) >= 4:
            break

    grid = np.array(canonical_layer(obs))
    bg = most_common_color(grid.tolist())
    h, w = grid.shape

    # Ground-truth collectible frame centres (row=sy+2, col=sx+2).
    print("collectible ground-truth frame centres + colour:")
    gt = []
    for c in game.owuypsqbino:
        col = {int(x) for x in np.unique(c.pixels) if x > 0}
        fr, fc = c.y + c.height // 2, c.x + c.width // 2
        gt.append((c.name, col, fr, fc))
        print(f"  {c.name:22s} col={col} frame~({fr},{fc}) actual grid[{fr},{fc}]={int(grid[fr,fc])}")

    print(f"\ncolour-10 (halo) cells: {int((grid==10).sum())}; "
          f"colour-1 (tendon) cells: {int((grid==1).sum())}")

    # Mask overlay (1,10) -> bg, then re-segment and list small solid blobs of
    # collectible colours (8,9,11,14) NOT part of a 7x7 target ring.
    masked = grid.copy()
    masked[(masked == 1) | (masked == 10)] = bg
    print("\nregions of collectible colours (8,9,11,14) after masking overlay:")
    for r in find_regions([tuple(row) for row in masked.tolist()], background=bg, gap=2):
        if r["color"] in (8, 9, 11, 14) and r["size"] >= 3:
            cr, cc = r["centroid"]
            print(f"  col={r['color']} sz={r['size']} fill={_fill(r):.2f} "
                  f"centre=({cr:.1f},{cc:.1f}) bbox={r['bbox']}")


if __name__ == "__main__":
    main()
