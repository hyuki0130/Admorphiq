"""movable-9 (else-branch bar-repositioning) empirical control.

movable-9 has ONLY tag 0031cppcuvqlbi (NOT the 0036ilsgwuvbxv reshape tag), so on
obstacle collision it takes the ELSE branch: it SHIFTS its full crossbar
column/row by 3 in a direction set by the push sign. Target = cover the 4 tips
(6,12),(9,9),(9,30),(27,12) = a cross with vbar@col12, hbar@row9. Learn the
control empirically: move the piece LEFT of the obstacle, row-align, push RIGHT
to collide, and log (frame bbox, vbar col, hbar row) each push.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _l5_movables, _station_boxes
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


def bars(m):
    """Return (frame bbox, vbar_cols(full columns), hbar_rows(full rows))."""
    cells = set(m["cells"])
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    vcols = [c for c in range(c0, c1 + 1) if sum((r, c) in cells for r in range(r0, r1 + 1)) >= h * 0.7]
    hrows = [r for r in range(r0, r1 + 1) if sum((r, c) in cells for c in range(c0, c1 + 1)) >= w * 0.7]
    return (r0, r1, c0, c1), vcols, hrows


def cover(m, tips, mk):
    rel = frozenset((r - mk[0], c - mk[1]) for r, c in m["cells"])
    cur = {(mk[0] + dr, mk[1] + dc) for dr, dc in rel}
    return sum(1 for t in tips if t in cur)


def sel(env, sb, color, obs):
    for _ in range(10):
        g = canonical_layer(obs); mk = marker(g); m = get(g, sb, color)
        if m and mk and abs(m["cen"][0] - mk[0]) <= 15 and abs(m["cen"][1] - mk[1]) <= 15:
            return obs
        obs = env.step(A[5])
    return obs


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
    g = canonical_layer(obs); _st, sb = _station_boxes(g)
    dm = dict(ad._dir_global)
    up = next(a for a, s in dm.items() if s == (-1, 0)); down = next(a for a, s in dm.items() if s == (1, 0))
    left = next(a for a, s in dm.items() if s == (0, -1)); right = next(a for a, s in dm.items() if s == (0, 1))
    tips = [(6, 12), (9, 9), (9, 30), (27, 12)]

    obs = sel(env, sb, 9, obs)
    g = canonical_layer(obs); m = get(g, sb, 9); mk = marker(g)
    print(f"start: bbox/vbar/hbar={bars(m)} cover={cover(m,tips,mk)}/4 marker={mk}")
    # move LEFT of the obstacle (cols < 26), rows kept 3-27 (no obstacle row overlap yet -> free)
    for _ in range(20):
        g = canonical_layer(obs); m = get(g, sb, 9)
        cs = [c for _, c in m["cells"]]
        if max(cs) <= 26:
            break
        obs = env.step(A[left])
    g = canonical_layer(obs); m = get(g, sb, 9)
    print(f"left of obstacle: bbox/vbar/hbar={bars(m)}")
    # row-align to obstacle centre (row 31)
    for _ in range(20):
        g = canonical_layer(obs); m = get(g, sb, 9)
        rs = [r for r, _ in m["cells"]]; cr = (min(rs) + max(rs)) // 2
        if abs(cr - 31) <= 2:
            break
        obs = env.step(A[down if cr < 31 else up])
    g = canonical_layer(obs); m = get(g, sb, 9)
    print(f"row-aligned: bbox/vbar/hbar={bars(m)}")
    print("-- push RIGHT into obstacle (log bar shifts) --")
    for k in range(10):
        obs = env.step(A[right])
        g = canonical_layer(obs); m = get(g, sb, 9)
        if m is None:
            print(f"  R{k+1}: GONE"); continue
        bb, vc, hr = bars(m)
        print(f"  R{k+1}: bbox={bb} vbar_cols={vc} hbar_rows={hr} px={len(m['cells'])}")
    print("-- now push UP then DOWN to see hbar shifts --")
    obs = sel(env, sb, 9, obs)
    for tag, act in (("UP", up), ("DOWN", down)):
        for k in range(5):
            obs = env.step(A[act])
            g = canonical_layer(obs); m = get(g, sb, 9)
            if m is None:
                print(f"  {tag}{k+1}: GONE"); continue
            bb, vc, hr = bars(m)
            print(f"  {tag}{k+1}: bbox={bb} vbar_cols={vc} hbar_rows={hr}")


if __name__ == "__main__":
    main()
