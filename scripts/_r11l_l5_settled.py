"""DISPOSABLE: clean SETTLED L5 frame perception dump (after the colour-10 entry
artifact clears). Settles with refused wall clicks (no leg moves), then classifies
regions into collectors(legs)/targets/collectibles by frame signature to validate
the Pass-3 detector design. env._game read only to pick a guaranteed-wall click."""
from __future__ import annotations

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.adapters25.r11l import Adapter, _fill, _hazard_cells, _is_hud_band
from admorphiq.kernels import find_regions


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("r11l")
    obs = env.step(GameAction.RESET)
    ad = Adapter()
    steps = 0
    while steps < 6000:
        if ad.is_done([], obs):
            break
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        if obs is None:
            break
        steps += 1
        if obs.state.name == "GAME_OVER":
            obs = env.step(GameAction.RESET)
            steps += 1
            continue
        if int(getattr(obs, "levels_completed", 0) or 0) >= 4:
            break

    # Settle: click a guaranteed WALL cell (refused, no move) until colour-10 clears.
    grid = np.array(canonical_layer(obs))
    for _ in range(4):
        rr, cc = np.where(grid == 10)
        if len(rr) == 0:
            break
        # a wall cell = a corner of the board, always refused
        obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})
        grid = np.array(canonical_layer(obs))
    print(f"settled after {steps} drive steps; colour-10 now {(grid==10).sum()} cells")

    gridt = [tuple(row) for row in grid.tolist()]
    bg = most_common_color(gridt)
    h, w = grid.shape
    hazard = _hazard_cells(gridt, bg)
    regs = [r for r in find_regions(gridt, background=bg, gap=2)
            if r["size"] >= 4 and not _is_hud_band(r, h, w) and not (r["cells"] & hazard)]

    print(f"\n{'col':>4} {'sz':>4} {'fill':>5} {'centroid':>12} {'bbox':>18}")
    for r in sorted(regs, key=lambda r: (r["color"], -r["size"])):
        cr, cc = r["centroid"]
        print(f"{r['color']:>4} {r['size']:>4} {_fill(r):>5.2f} ({cr:>4.1f},{cc:>4.1f}) {str(r['bbox']):>18}")

    # Classify: targets = 2 colours within a ~7x7 bbox; collectibles = lone blobs;
    # legs = colour 3/0 crosses.
    print("\n=== classification attempt ===")
    legs = [r for r in regs if r["color"] in (0, 3, 4) and 8 <= r["size"] <= 16]
    print(f"legs (col 0/3/4, sz8-16): {[(r['color'], (round(r['centroid'][0]),round(r['centroid'][1]))) for r in legs]}")
    colourful = [r for r in regs if r["color"] in (6, 7, 8, 9, 11, 12, 13, 14, 15)]
    # group colourful by proximity into rings/blobs
    used = [False] * len(colourful)
    for i, ri in enumerate(colourful):
        if used[i]:
            continue
        grp = [ri]
        used[i] = True
        for j in range(i + 1, len(colourful)):
            if used[j]:
                continue
            if (abs(ri["centroid"][0] - colourful[j]["centroid"][0]) <= 4
                    and abs(ri["centroid"][1] - colourful[j]["centroid"][1]) <= 4):
                grp.append(colourful[j])
                used[j] = True
        cols = sorted({g["color"] for g in grp})
        cen = (round(sum(g["centroid"][0] for g in grp) / len(grp)),
               round(sum(g["centroid"][1] for g in grp) / len(grp)))
        kind = "TARGET(2-col ring)" if len(cols) >= 2 else "collectible/blob"
        print(f"  {kind}: colours={cols} centre={cen} nregs={len(grp)}")


if __name__ == "__main__":
    main()
