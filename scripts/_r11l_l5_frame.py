"""DISPOSABLE frame-region dump at r11l Level 5, SETTLED, with ground-truth
labels — reveals the frame signatures (size/fill/colour/centroid/bbox) the L5
detector must key on and the frame<->engine coordinate mapping. Frame-only build
uses only the frame; env._game read here for labelling/cross-check."""
from __future__ import annotations

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.adapters25.r11l import Adapter, _fill, _is_hud_band
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
            obs = env.step(GameAction.RESET)
            steps += 1
            continue
        if int(getattr(obs, "levels_completed", 0) or 0) >= 4:
            break

    grid = canonical_layer(obs)
    bg = most_common_color(grid)
    h, w = len(grid), len(grid[0])

    print(f"L5 reached in {steps} steps; grid {h}x{w}; bg={bg}")
    print("\n=== ENGINE GROUND TRUTH (sprite x,y) ===")
    for name, d in game.kacotwgjcyq.items():
        body, tgt, legs = d["roduyfsmiznvg"], d["gosubdcyegamj"], d["lecfirgqbwunn"]
        if body:
            print(f"  body {name}: ({body.x},{body.y}) {body.width}x{body.height}")
        if tgt:
            print(f"  target {name}: ({tgt.x},{tgt.y}) {tgt.width}x{tgt.height} dirwzt={'dirwzt' in name}")
        for lg in legs:
            print(f"  leg {name}: ({lg.x},{lg.y}) {lg.width}x{lg.height}")
    for c in game.owuypsqbino:
        cols = {int(x) for x in np.unique(c.pixels) if x > 0}
        print(f"  collectible {c.name}: ({c.x},{c.y}) {c.width}x{c.height} col={cols}")

    print("\n=== FRAME REGIONS (size>=4, sorted by colour then size) ===")
    print(f"{'col':>4} {'sz':>4} {'fill':>5} {'centroid':>12} {'bbox':>20} {'hud':>4}")
    regs = [r for r in find_regions(grid, background=bg, gap=2) if r["size"] >= 4]
    for r in sorted(regs, key=lambda r: (r["color"], -r["size"])):
        cr, cc = r["centroid"]
        print(f"{r['color']:>4} {r['size']:>4} {_fill(r):>5.2f} ({cr:>4.1f},{cc:>4.1f}) "
              f"{str(r['bbox']):>20} {str(_is_hud_band(r,h,w)):>5}")

    # 7x7-bbox ring detection: regions grouped into ~7x7 bboxes (targets).
    print("\n=== candidate TARGET rings (multi-colour, ~7x7 bbox) ===")
    small = [r for r in regs if r["size"] <= 25 and not _is_hud_band(r, h, w)]
    # group by proximity of bbox centres
    used = [False]*len(small)
    for i, ri in enumerate(small):
        if used[i]:
            continue
        ci = ri["centroid"]
        group = [ri]
        used[i] = True
        for j in range(i+1, len(small)):
            if used[j]:
                continue
            cj = small[j]["centroid"]
            if abs(ci[0]-cj[0]) <= 4 and abs(ci[1]-cj[1]) <= 4:
                group.append(small[j])
                used[j] = True
        cols = {g["color"] for g in group}
        rows = [g["bbox"][0] for g in group]+[g["bbox"][2] for g in group]
        colsb = [g["bbox"][1] for g in group]+[g["bbox"][3] for g in group]
        span = (max(rows)-min(rows), max(colsb)-min(colsb))
        if len(cols) >= 2 or span[0] >= 5 or span[1] >= 5:
            cen = (sum(g["centroid"][0] for g in group)/len(group),
                   sum(g["centroid"][1] for g in group)/len(group))
            print(f"  centre≈({cen[0]:.1f},{cen[1]:.1f}) colours={cols} span={span} nregs={len(group)}")


if __name__ == "__main__":
    main()
