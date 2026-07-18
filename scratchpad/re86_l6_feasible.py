"""re86 L6 feasibility (R63): is L6 the L1/L2 covering spine? Compute covering
offsets per movable onto its same-colour targets, and characterise the colour-1
blob (static obstacle? movable? does it block the covering translation?)."""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _station_boxes, _target_boxes, _l5_movables
from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.kernels import covering_offsets, find_regions

A = {5: GameAction.ACTION5, 1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4}
MOV_TAG = "0031cppcuvqlbi"


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    steps = 0
    while steps < 2500 and int(getattr(obs, "levels_completed", 0) or 0) < 5 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    if int(getattr(obs, "levels_completed", 0) or 0) != 5:
        print("no L6"); return
    for _ in range(3):
        obs = env.step(A[5]); steps += 1
    grid = canonical_layer(obs)
    bg = most_common_color(grid)
    stations, sboxes = _station_boxes(grid)
    tboxes = _target_boxes(grid)
    targets_by = {}
    for r, c in tboxes:
        targets_by.setdefault(grid[r][c], []).append((r, c))
    movs = _l5_movables(grid, set(), sboxes, subtract_boxes=False)
    print(f"bg={bg} stations={stations}")
    print(f"targets_by_color={{k: len(v) for k,v in targets_by.items()}}  cells={targets_by}")
    # GT movable colours (which are the real pieces)
    g = env._game
    gt_cols = set()
    for s in g.current_level.get_sprites_by_tag(MOV_TAG):
        cols = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
        if cols:
            gt_cols.add(cols.most_common(1)[0][0])
    print(f"GT movable colours = {gt_cols}")
    for m in movs:
        col = m["color"]
        role = "MOVABLE" if col in gt_cols else "obstacle/other"
        tg = targets_by.get(col, [])
        offs = covering_offsets(list(m["cells"]), tg) if tg else []
        print(f"  region colour={col} ({role}) size={len(m['cells'])} cen={m['cen']} "
              f"targets={len(tg)} covering_offsets={offs[:4]}")
    # colour-1 blob: static? print its region
    for reg in find_regions(grid, background=bg, gap=1):
        if reg["color"] == 1:
            rs = [r for r, _ in reg["cells"]]; cs = [c for _, c in reg["cells"]]
            print(f"  colour-1 blob: {len(reg['cells'])} cells bbox=({min(rs)},{min(cs)})-({max(rs)},{max(cs)})")


if __name__ == "__main__":
    main()
