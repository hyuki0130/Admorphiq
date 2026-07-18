"""g50t L1 anchoring stability diagnostic (task #83).

Measures which STATIC landmark gives a run-stable 6px cell grid. Prior live runs
parsed spawn as (4,8)/(3,8)/(1,7) — but those parsed at inconsistent settle
states. Here we settle to a byte-stable frame (two consecutive identical frames),
then dump candidate anchors:
  - floor colour-5 bbox top-left  (the maze extent, static)
  - the STATIC colour-9 blob (goal) bbox top-left
and the spawn cell each implies. Run ×N; a stable anchor gives the SAME numbers
every run.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer
from admorphiq.kernels import find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL, FLOOR, MOVER = 6, 5, 9


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def settle_stable(env, obs, max_steps=12):
    """Advance until two consecutive frames are byte-identical (transition gone).
    Issue ACTION1 (up); if blocked it's a no-op, if not the player may move but
    the frame still stabilises once animation ends."""
    prev = canonical_layer(obs)
    for _ in range(max_steps):
        obs = env.step(A[1])
        cur = canonical_layer(obs)
        if cur == prev:
            return obs, cur
        prev = cur
    return obs, prev


def color_bbox(grid, color, min_size=1):
    rows = [r for r, row in enumerate(grid) for c, v in enumerate(row) if v == color]
    cols = [c for r, row in enumerate(grid) for c, v in enumerate(row) if v == color]
    if not rows:
        return None
    return (min(rows), min(cols), max(rows), max(cols))


def blobs(grid, color):
    return [(reg["bbox"], reg["size"], reg["centroid"])
            for reg in find_regions(grid, background=None) if reg["color"] == color]


def run_once(tag):
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print(f"[{tag}] no L1"); return None
    obs, grid = settle_stable(env, obs)
    fb = color_bbox(grid, FLOOR)
    m9 = blobs(grid, MOVER)
    # floor origin: min row/col of colour-5
    forigin = (fb[0], fb[1]) if fb else None
    print(f"[{tag}] floor_bbox={fb} origin={forigin}")
    for bb, sz, ct in sorted(m9, key=lambda x: -x[1]):
        cell_flo = (bb[0] // CELL, bb[1] // CELL) if bb else None
        cell_rel = ((bb[0] - forigin[0]) // CELL, (bb[1] - forigin[1]) // CELL) if forigin else None
        print(f"[{tag}]   c9 blob bbox={bb} size={sz} cell(//6)={cell_flo} cell(rel-floor)={cell_rel}")
    return (fb, tuple(sorted(m9, key=lambda x: -x[1])[:1]))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    results = [run_once(f"run{i}") for i in range(n)]
    fbs = {r[0] for r in results if r}
    print(f"\nfloor_bbox stable across {n} runs: {len(fbs) == 1}  distinct={fbs}")


if __name__ == "__main__":
    main()
