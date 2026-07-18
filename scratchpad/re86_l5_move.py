"""re86 L5 move-physics probe (task #84): is the colour-12 oscillation real engine
physics or a parse artifact? Reach L5, select the colour-12 movable, issue N
consecutive DOWN (ACTION2), and print the TRUE sprite centroid (from GT sprite
x/y/w/h, dev-read) + my frame-parse centroid each step. If GT descends smoothly,
my marker-excluding parse is the culprit; if GT oscillates/bounces under constant
down, the move physics are non-grid (wall bounce / patrol) — a bank-worthy surprise.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _station_boxes
from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.kernels import find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
MOV_TAG = "0031cppcuvqlbi"


def reach_l5(env, ad):
    obs = env.observation_space
    s = 0
    while s < 6000 and int(getattr(obs, "levels_completed", 0) or 0) < 4 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def gt_centroids(g):
    """True per-sprite centroid (r,c) keyed by dominant colour."""
    out = {}
    for s in g.current_level.get_sprites_by_tag(MOV_TAG):
        from collections import Counter
        cols = Counter(int(v) for row in s.pixels for v in row if v != -1 and v != 0)
        if not cols:
            continue
        col = cols.most_common(1)[0][0]
        out[col] = (s.y + s.height // 2, s.x + s.width // 2, s.width, s.height)
    return out


def marker_of(grid):
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v == 0:
                return (r, c)
    return None


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    g = env._game
    ad = Adapter(giveup=6000)
    obs = reach_l5(env, ad)
    if int(getattr(obs, "levels_completed", 0) or 0) != 4:
        print("no L5"); return
    for _ in range(2):
        obs = env.step(A[5])
    # cycle until colour-12 sprite holds the marker (selected)
    for _ in range(6):
        gc = gt_centroids(g)
        grid = canonical_layer(obs)
        mk = marker_of(grid)
        # colour-12 is the largest sprite; check if marker within its bbox
        r0, c0, w, h = gc[12][0] - gc[12][3] // 2, gc[12][1] - gc[12][2] // 2, gc[12][2], gc[12][3]
        if mk and r0 <= mk[0] <= r0 + h and c0 <= mk[1] <= c0 + w:
            break
        obs = env.step(A[5])
    print("selected colour-12; issuing 24 DOWN (ACTION2):")
    print(f"  {'step':>4} {'gt12(r,c,w,h)':>20} {'gt11':>12} {'gt14':>12} marker")
    for k in range(24):
        gc = gt_centroids(g)
        grid = canonical_layer(obs)
        mk = marker_of(grid)
        print(f"  {k:>4} {str(gc.get(12)):>20} {str(gc.get(11)[:2]):>12} {str(gc.get(14)[:2]):>12} {mk}")
        obs = env.step(A[2])


if __name__ == "__main__":
    main()
