"""g50t L1 frame dump (task #83): print the raw L1 colour grid + region inventory
so we can see the true play-area geometry (border/HUD offset) and derive a static
grid origin. No engine-constant assumptions — pure frame observation.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer
from admorphiq.kernels import find_regions


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    print("levels_completed =", getattr(obs, "levels_completed", None))
    grid = canonical_layer(obs)
    h, w = len(grid), len(grid[0])
    print(f"grid {h}x{w}")
    # colour histogram
    hist = {}
    for row in grid:
        for v in row:
            hist[v] = hist.get(v, 0) + 1
    print("colour histogram:", dict(sorted(hist.items())))
    # per-colour region inventory (bbox pixel extremes + size)
    for reg in sorted(find_regions(grid, background=None), key=lambda r: (r["color"], r["bbox"][0])):
        c = reg["color"]
        if c in (0,):
            continue
        r0, c0, r1, c1 = reg["bbox"]
        print(f"  col={c:2d} bbox=(r{r0}-{r1},c{c0}-{c1}) size={reg['size']}")
    # print the grid compactly (each cell = colour at center of 6px cell)
    print("\ncell-center map (rows 0..10, cols 0..10, sample at k*6+3):")
    for i in range(11):
        line = []
        for j in range(11):
            rr, cc = i * 6 + 3, j * 6 + 3
            line.append(str(grid[rr][cc]) if rr < h and cc < w else ".")
        print(f"  r{i:2d}: " + " ".join(line))


if __name__ == "__main__":
    main()
