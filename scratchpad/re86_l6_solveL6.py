"""Full L6: place movable-9 (top-left, corridor bar-control) then movable-11
(bottom-right, outline reshape+place). Neither disturbs the other; the win is a
simultaneous snapshot of both. Verifies levels_completed -> 6.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _l5_movables, _station_boxes, _target_boxes, _l5_route
from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.kernels import find_regions

from re86_l6_solve9 import solve9  # reuse the verified movable-9 corridor solver

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}


def marker(g):
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == 0:
                return (r, c)
    return None


def getcol(g, sb, color):
    for m in _l5_movables(g, set(), sb, subtract_boxes=False):
        if m["color"] == color:
            return m
    return None


def bbox(m):
    rs = [r for r, _ in m["cells"]]; cs = [c for _, c in m["cells"]]
    return min(rs), max(rs), min(cs), max(cs)


def obstacle_box(g):
    bg = most_common_color(g)
    for reg in find_regions(g, background=bg, gap=1):
        if reg["color"] == 1 and len(reg["cells"]) > 10:
            rs = [r for r, _ in reg["cells"]]; cs = [c for _, c in reg["cells"]]
            return (min(rs), min(cs), max(rs), max(cs))
    return (28, 28, 35, 35)


def sel(env, sb, color, obs):
    for _ in range(12):
        g = canonical_layer(obs); mk = marker(g); m = getcol(g, sb, color)
        if m and mk and abs(m["cen"][0] - mk[0]) <= 15 and abs(m["cen"][1] - mk[1]) <= 15:
            return obs
        obs = env.step(A[5])
    return obs


def solve11(env, sb, dm, ob, tgt, obs):
    """movable-11 outline reshape (row-align + push right to target h) then place
    via _l5_route with the obstacle inflated asymmetrically. Returns (obs, ok)."""
    up = next(a for a, s in dm.items() if s == (-1, 0)); down = next(a for a, s in dm.items() if s == (1, 0))
    right = next(a for a, s in dm.items() if s == (0, 1))
    rs = [r for r, _ in tgt]; cs = [c for _, c in tgt]
    tr0, tr1, tc0, tc1 = min(rs), max(rs), min(cs), max(cs)
    th, tw = tr1 - tr0 + 1, tc1 - tc0 + 1
    obr = (ob[0] + ob[2]) // 2

    obs = sel(env, sb, 11, obs)
    for _ in range(20):
        g = canonical_layer(obs); m = getcol(g, sb, 11)
        if m is None:
            break
        r0, r1, c0, c1 = bbox(m)
        if abs((r0 + r1) // 2 - obr) <= 2:
            break
        obs = env.step(A[up if (r0 + r1) // 2 > obr else down])
    for _ in range(10):
        g = canonical_layer(obs); m = getcol(g, sb, 11)
        if m is None:
            break
        r0, r1, c0, c1 = bbox(m)
        if (r1 - r0 + 1) >= th:
            break
        obs = env.step(A[right])
    half_h = th // 2 + 1
    half_w = tw // 2 + 1
    avoid = (ob[0] - half_h, ob[1] - half_w, ob[2] + half_h, ob[3] + half_w)
    tgt_cen = ((tr0 + tr1) // 2, (tc0 + tc1) // 2)
    shape_rel = None
    walls: set = set()
    last = None
    move_ids = [1, 2, 3, 4]
    for _ in range(300):
        obs = sel(env, sb, 11, obs)
        g = canonical_layer(obs); mk = marker(g); m = getcol(g, sb, 11)
        if m is None or mk is None:
            obs = env.step(A[5]); continue
        if last is not None:
            pm, want = last
            adv = (mk[0] - pm[0]) * want[0] + (mk[1] - pm[1]) * want[1]
            if adv < 2:
                walls.add((pm[0] // 3 + want[0], pm[1] // 3 + want[1]))
        last = None
        if shape_rel is None:
            shape_rel = frozenset((r - mk[0], c - mk[1]) for r, c in m["cells"])
        cur = {(mk[0] + dr, mk[1] + dc) for dr, dc in shape_rel}
        if sum(1 for t in tgt if t in cur) == len(tgt):
            return obs, True
        act = _l5_route(mk, tgt_cen, 0, [avoid], walls, dm, move_ids)
        if act is None:
            obs = env.step(A[5]); continue
        last = (mk, dm[act])
        obs = env.step(A[act])
    return obs, False


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    steps = 0
    while steps < 2500 and int(getattr(obs, "levels_completed", 0) or 0) < 5 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a); steps += 1
    for _ in range(3):
        obs = env.step(A[5])
    g = canonical_layer(obs); _s, sb = _station_boxes(g)
    dm = dict(ad._dir_global)
    ob = obstacle_box(g)
    tb = _target_boxes(g)
    tgt11 = [(r, c) for r, c in tb if g[r][c] == 11]
    lv0 = int(getattr(obs, "levels_completed", 0) or 0)

    obs, ok9 = solve9(env, ad, sb, dm, obs, verbose=True)
    print(f"movable-9 placed = {ok9}  levels={int(getattr(obs,'levels_completed',0) or 0)}")
    obs, ok11 = solve11(env, sb, dm, ob, tgt11, obs)
    lv = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"movable-11 placed = {ok11}  levels={lv} (was {lv0})  L6 CLEARED = {lv > lv0}")


if __name__ == "__main__":
    main()
