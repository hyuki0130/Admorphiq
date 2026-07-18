"""re86 L7 decode probe (R65): reach L7 via the adapter clearing L1-L6, then dump
the scene — colour-1 obstacle blobs (count/positions), movables (colour, bbox,
fill, cross-vs-outline by fill), target boxes by colour, and classify each
movable's target set (rectangle corners = OUTLINE, plus = CROSS). Tests the
scale-up hypothesis: is L7 the same reshape-and-place with 6 reshape anchors?
"""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import (
    Adapter, _station_boxes, _target_boxes, _l5_movables, _l6_obstacle_box, _l6_bbox,
)
from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.kernels import find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
MOV_TAG = "0031cppcuvqlbi"


def is_rect(tgts):
    rows = sorted({r for r, _ in tgts}); cols = sorted({c for _, c in tgts})
    cs = set(tgts)
    return len(rows) == 2 and len(cols) == 2 and all((r, c) in cs for r in rows for c in cols)


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    steps = 0
    # clear L1-L6 (adapter reaches L7 = levels_completed 6)
    while steps < 4000 and int(getattr(obs, "levels_completed", 0) or 0) < 6 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    lv = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"reached levels_completed={lv} at {steps} actions")
    if lv != 6:
        print("did NOT reach L7"); return
    for _ in range(3):
        obs = env.step(A[5]); steps += 1
    grid = canonical_layer(obs)
    bg = most_common_color(grid)
    stations, sboxes = _station_boxes(grid)
    print(f"bg={bg}  stations={stations}")

    # colour-1 obstacle blobs (there may be six)
    obst = []
    for reg in find_regions(grid, background=bg, gap=1):
        if reg["color"] == 1 and len(reg["cells"]) >= 6:
            r0, r1, c0, c1 = min(r for r, _ in reg["cells"]), max(r for r, _ in reg["cells"]), \
                min(c for _, c in reg["cells"]), max(c for _, c in reg["cells"])
            obst.append((r0, c0, r1, c1, len(reg["cells"])))
    print(f"colour-1 obstacle blobs ({len(obst)}):")
    for o in obst:
        print(f"   bbox rows {o[0]}-{o[2]} cols {o[1]}-{o[3]} px={o[4]}")
    print(f"_l6_obstacle_box (single) = {_l6_obstacle_box(grid)}")

    # movables (frame parse) + GT sprites
    movs = _l5_movables(grid, set(), [], subtract_boxes=False)
    print(f"movables (frame-parse, {len(movs)}):")
    for m in movs:
        r0, r1, c0, c1 = _l6_bbox(m["cells"])
        area = (r1 - r0 + 1) * (c1 - c0 + 1)
        fill = len(m["cells"]) / area if area else 0
        print(f"   colour={m['color']} bbox {r1-r0+1}x{c1-c0+1} @({r0},{c0}) px={len(m['cells'])} fill={fill:.2f}")
    g = env._game
    gt = []
    for s in g.current_level.get_sprites_by_tag(MOV_TAG):
        cols = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
        if cols:
            gt.append((cols.most_common(1)[0][0], s.width, s.height, s.tags))
    print(f"movables (GT sprite, {len(gt)}):")
    for c, w, h, tags in gt:
        print(f"   colour={c} {w}x{h} tags={tags}")

    # target boxes by colour + classify
    tb = _target_boxes(grid)
    by = {}
    for r, c in tb:
        by.setdefault(grid[r][c], []).append((r, c))
    print(f"target boxes by colour:")
    for col, cells in sorted(by.items()):
        kind = "OUTLINE(rect)" if (len(cells) >= 4 and is_rect(cells)) else ("CROSS(plus)" if len(cells) >= 4 else "partial")
        print(f"   colour={col} n={len(cells)} kind={kind} cells={sorted(cells)}")


if __name__ == "__main__":
    main()
