"""re86 L6 movable-11 reshape-and-place PROTOTYPE.

movable-11 is a hollow 19x19 square outline (72 px). Its 4 target cells are the
corners of a 28x10 rectangle (perimeter-conserving match: 2*28+2*10-4 = 72). The
build:
  1. RESHAPE: align the piece's rows to overlap the central obstacle (rows
     28-35), then push RIGHT into it — each right push is perimeter-conserving
     (h+3, w-3): 19x19 -> 22x16 -> 25x13 -> 28x10. Push until h >= target_h.
  2. PLACE: route the piece centre to the target rectangle centre, avoiding the
     obstacle (inflated asymmetrically by the piece half-extent so a translate
     never re-collides + reshapes), marker-anchored, until all 4 corners covered.
Reports coverage of the 4 target-11 cells + final bbox.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _l5_movables, _station_boxes, _target_boxes, _l5_route
from admorphiq.adapters25.base import canonical_layer

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}


def marker(g):
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == 0:
                return (r, c)
    return None


def get(g, sb, color):
    for m in _l5_movables(g, set(), sb, subtract_boxes=False):
        if m["color"] == color:
            return m
    return None


def bbox(m):
    rs = [r for r, _ in m["cells"]]; cs = [c for _, c in m["cells"]]
    return min(rs), max(rs), min(cs), max(cs)


def obstacle_box(g):
    from admorphiq.adapters25.base import most_common_color
    from admorphiq.kernels import find_regions
    bg = most_common_color(g)
    for reg in find_regions(g, background=bg, gap=1):
        if reg["color"] == 1 and len(reg["cells"]) > 10:
            rs = [r for r, _ in reg["cells"]]; cs = [c for _, c in reg["cells"]]
            return (min(rs), min(cs), max(rs), max(cs))
    return (28, 28, 35, 35)


def reach_l6(env, ad):
    obs = env.observation_space
    steps = 0
    while steps < 2500 and int(getattr(obs, "levels_completed", 0) or 0) < 5 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a); steps += 1
    for _ in range(3):
        obs = env.step(A[5])
    return obs


def select(env, sb, color, obs):
    for _ in range(10):
        g = canonical_layer(obs); mk = marker(g); m = get(g, sb, color)
        if m and mk and abs(m["cen"][0] - mk[0]) <= 15 and abs(m["cen"][1] - mk[1]) <= 15:
            return obs, True
        obs = env.step(A[5])
    return obs, False


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = reach_l6(env, ad)
    g = canonical_layer(obs); _st, sb = _station_boxes(g)
    ob = obstacle_box(g)
    tb = _target_boxes(g)
    tgt = [(r, c) for r, c in tb if g[r][c] == 11]
    rs = [r for r, _ in tgt]; cs = [c for _, c in tgt]
    tr0, tr1, tc0, tc1 = min(rs), max(rs), min(cs), max(cs)
    th, tw = tr1 - tr0 + 1, tc1 - tc0 + 1
    print(f"target-11 corners={sorted(tgt)} bbox {th}x{tw} rows {tr0}-{tr1} cols {tc0}-{tc1}")
    print(f"obstacle box (r0,c0,r1,c1)={ob}")
    dirmap = dict(ad._dir_global)
    up = next(a for a, s in dirmap.items() if s == (-1, 0))
    right = next(a for a, s in dirmap.items() if s == (0, 1))
    down = next(a for a, s in dirmap.items() if s == (1, 0))
    obr = (ob[0] + ob[2]) // 2  # obstacle centre row

    obs, ok = select(env, sb, 11, obs)
    # PHASE 1: align rows to obstacle centre (piece stays left of obstacle).
    for _ in range(20):
        g = canonical_layer(obs); m = get(g, sb, 11)
        if m is None:
            break
        r0, r1, c0, c1 = bbox(m)
        if abs((r0 + r1) // 2 - obr) <= 2:
            break
        obs = env.step(A[up if (r0 + r1) // 2 > obr else down])
    # PHASE 2: push right into obstacle until height >= target height.
    for _ in range(10):
        g = canonical_layer(obs); m = get(g, sb, 11)
        if m is None:
            break
        r0, r1, c0, c1 = bbox(m)
        if (r1 - r0 + 1) >= th:
            break
        obs = env.step(A[right])
    g = canonical_layer(obs); m = get(g, sb, 11)
    print(f"after reshape: bbox={bbox(m)} = {bbox(m)[2]-bbox(m)[0]+1}x{bbox(m)[3]-bbox(m)[1]+1} px={len(m['cells'])}")
    # PHASE 3: place — route centre to target-bbox centre, obstacle inflated
    # asymmetrically (rows by half-height, cols by half-width) so a translate
    # never re-collides. half=0 in _l5_route since we pre-inflate the box.
    half_h = th // 2 + 1
    half_w = tw // 2 + 1
    avoid = (ob[0] - half_h, ob[1] - half_w, ob[2] + half_h, ob[3] + half_w)
    tgt_cen = ((tr0 + tr1) // 2, (tc0 + tc1) // 2)
    shape_rel = None
    walls: set = set()
    last = None
    move_ids = [1, 2, 3, 4]
    for it in range(300):
        g = canonical_layer(obs); mk = marker(g); m = get(g, sb, 11)
        if m is None or mk is None:
            obs = env.step(A[5]); continue
        obs2, ok = select(env, sb, 11, obs)
        obs = obs2
        g = canonical_layer(obs); mk = marker(g); m = get(g, sb, 11)
        if m is None or mk is None:
            continue
        if last is not None:
            pm, want = last
            adv = (mk[0] - pm[0]) * want[0] + (mk[1] - pm[1]) * want[1]
            if adv < 2:
                walls.add((pm[0] // 3 + want[0], pm[1] // 3 + want[1]))
        last = None
        if shape_rel is None:
            shape_rel = frozenset((r - mk[0], c - mk[1]) for r, c in m["cells"])
        cur = {(mk[0] + dr, mk[1] + dc) for dr, dc in shape_rel}
        covered = sum(1 for t in tgt if t in cur)
        if covered == len(tgt):
            print(f"  it{it}: PLACED all 4 at marker={mk} bbox={bbox(m)}")
            break
        act = _l5_route(mk, tgt_cen, 0, [avoid], walls, dirmap, move_ids)
        if act is None:
            if it % 20 == 0:
                print(f"  it{it}: no route mk={mk} cov={covered} bbox={bbox(m)}")
            obs = env.step(A[5]); continue
        last = (mk, dirmap[act])
        obs = env.step(A[act])
        if it % 20 == 0:
            print(f"  it{it}: mk={mk} cov={covered}/4 bbox={bbox(m)} act={act}")
    g = canonical_layer(obs); mk = marker(g); m = get(g, sb, 11)
    cur = {(mk[0] + dr, mk[1] + dc) for dr, dc in shape_rel} if (mk and shape_rel) else set()
    print(f"FINAL covered {sum(1 for t in tgt if t in cur)}/4 bbox={bbox(m) if m else None} "
          f"levels={int(getattr(obs,'levels_completed',0) or 0)}")


if __name__ == "__main__":
    main()
