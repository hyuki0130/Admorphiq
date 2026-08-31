"""Debug: why only one movable parses. Dump all find_regions + GT movable
sprites + colour histogram at L4 settle."""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _target_boxes
from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.kernels import find_regions

A = {5: GameAction.ACTION5}


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=9000)
    steps = 0
    while steps < 9000 and obs.levels_completed < 3:
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    for _ in range(2):
        obs = env.step(A[5]); steps += 1
    grid = canonical_layer(obs)
    bg = most_common_color(grid)
    print("bg", bg, "hist", Counter(v for row in grid for v in row).most_common(14))
    # GT movables
    lvl = g.current_level
    for m in lvl.get_sprites_by_tag("0031cppcuvqlbi"):
        px = m.pixels
        cols = Counter(int(v) for row in px for v in row if v != -1)
        print(f"GT movable x={m.x} y={m.y} w={m.width} h={m.height} colors={dict(cols)} tags={m.tags}")
    print("--- all regions (gap=1, bg=frame bg only) ---")
    for reg in find_regions(grid, background=bg, gap=1):
        cells = reg["cells"]
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        cols = Counter(grid[r][c] for r, c in cells)
        print(f"  color={reg['color']} size={len(cells)} bbox=({min(rs)},{min(cs)})-({max(rs)},{max(cs)}) colhist={dict(cols)}")
    print("--- regions with bg incl border-4/2/sel-0 ---")
    for reg in find_regions(grid, background=(bg, 4, 2, 0), gap=1):
        cells = reg["cells"]
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        print(f"  color={reg['color']} size={len(cells)} bbox=({min(rs)},{min(cs)})-({max(rs)},{max(cs)})")


if __name__ == "__main__":
    main()
