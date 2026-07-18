"""movable-9 reshape+place PROTOTYPE using the measured else-branch control.

State = 25x25 frame (r0,c0) with a vertical bar at frame-rel col ``vrel`` and a
horizontal bar at frame-rel row ``hrel``. Obstacle collision shifts a bar +-3
within the frame (right push -> vrel+3 capped 24 ; left -> vrel-3 floor 0 ; down
-> hrel+3 ; up -> hrel-3). A free (non-colliding) move translates the frame.
Target to cover tips (6,12),(9,9),(9,30),(27,12): frame rows 3-27, cols 6-30,
vrel=6 (vbar abs col 12), hrel=6 (hbar abs row 9).
Plan: (A) set vrel=6 via horizontal collisions (row-align to obstacle so the push
collides), (B) set hrel=6 via vertical collisions (col-align to obstacle), (C)
free-translate the frame to (r0=3,c0=6). Logs coverage throughout.
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
TIPS = [(6, 12), (9, 9), (9, 30), (27, 12)]
OB = (28, 35, 28, 35)  # obstacle r0,r1,c0,c1


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


def state(m):
    cells = set(m["cells"])
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    h, w = r1 - r0 + 1, c1 - c0 + 1
    vcols = [c for c in range(c0, c1 + 1) if sum((r, c) in cells for r in range(r0, r1 + 1)) >= h * 0.7]
    hrows = [r for r in range(r0, r1 + 1) if sum((r, c) in cells for c in range(c0, c1 + 1)) >= w * 0.7]
    vabs = vcols[len(vcols) // 2] if vcols else c0
    habs = hrows[len(hrows) // 2] if hrows else r0
    return {"r0": r0, "r1": r1, "c0": c0, "c1": c1, "vabs": vabs, "habs": habs,
            "vrel": vabs - c0, "hrel": habs - r0, "cells": cells}


def cover(m, mk):
    rel = frozenset((r - mk[0], c - mk[1]) for r, c in m["cells"])
    cur = {(mk[0] + dr, mk[1] + dc) for dr, dc in rel}
    return sum(1 for t in TIPS if t in cur), cur


def sel(env, sb, color, obs):
    for _ in range(12):
        g = canonical_layer(obs); mk = marker(g); m = get(g, sb, color)
        if m and mk and abs(m["cen"][0] - mk[0]) <= 15 and abs(m["cen"][1] - mk[1]) <= 15:
            return obs
        obs = env.step(A[5])
    return obs


def reach(env, ad):
    obs = env.observation_space; steps = 0
    while steps < 2500 and int(getattr(obs, "levels_completed", 0) or 0) < 5 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a); steps += 1
    for _ in range(3):
        obs = env.step(A[5])
    return obs


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = reach(env, ad)
    g = canonical_layer(obs); _st, sb = _station_boxes(g)
    dm = dict(ad._dir_global)
    up = next(a for a, s in dm.items() if s == (-1, 0)); down = next(a for a, s in dm.items() if s == (1, 0))
    left = next(a for a, s in dm.items() if s == (0, -1)); right = next(a for a, s in dm.items() if s == (0, 1))

    def cur():
        obs2 = sel(env, sb, 9, env.observation_space)
        g2 = canonical_layer(obs2); return obs2, g2, get(g2, sb, 9), marker(g2)

    def step(act):
        return env.step(A[act])

    obs = sel(env, sb, 9, obs); g = canonical_layer(obs); m = get(g, sb, 9); mk = marker(g)
    st = state(m)
    print(f"start: {st['r0']}-{st['r1']}x{st['c0']}-{st['c1']} vabs={st['vabs']} habs={st['habs']} "
          f"vrel={st['vrel']} hrel={st['hrel']} cover={cover(m,mk)[0]}/4")

    # (A) set vrel=6: row-align to obstacle centre so a horizontal push collides,
    # then push LEFT/RIGHT to move vrel toward 6.
    for _ in range(40):
        obs = sel(env, sb, 9, obs); g = canonical_layer(obs); m = get(g, sb, 9)
        st = state(m)
        if st["vrel"] == 6:
            break
        # row-align centre to 31 (free vertical move; cols left of obstacle keep it free)
        cr = (st["r0"] + st["r1"]) // 2
        if abs(cr - 31) > 2:
            obs = step(down if cr < 31 else up); continue
        obs = step(left if st["vrel"] > 6 else right)
    obs = sel(env, sb, 9, obs); g = canonical_layer(obs); m = get(g, sb, 9); mk = marker(g)
    st = state(m)
    print(f"after vrel-set: vrel={st['vrel']} frame={st['r0']}-{st['r1']}x{st['c0']}-{st['c1']} cover={cover(m,mk)[0]}/4")

    # (B) set hrel=6: col-align frame to overlap obstacle cols (28-35) so a vertical
    # push collides, then push UP/DOWN to move hrel toward 6.
    for _ in range(40):
        obs = sel(env, sb, 9, obs); g = canonical_layer(obs); m = get(g, sb, 9)
        st = state(m)
        if st["hrel"] == 6:
            break
        cc = (st["c0"] + st["c1"]) // 2
        if abs(cc - 31) > 2:
            obs = step(right if cc < 31 else left); continue
        obs = step(up if st["hrel"] > 6 else down)
    obs = sel(env, sb, 9, obs); g = canonical_layer(obs); m = get(g, sb, 9); mk = marker(g)
    st = state(m)
    print(f"after hrel-set: vrel={st['vrel']} hrel={st['hrel']} frame={st['r0']}-{st['r1']}x{st['c0']}-{st['c1']} cover={cover(m,mk)[0]}/4")

    # (C) free-translate frame to r0=3, c0=6 (no collision: keep away from obstacle
    # on the moving axis). Move cols first to 6 (frame left of obstacle), then rows.
    for _ in range(60):
        obs = sel(env, sb, 9, obs); g = canonical_layer(obs); m = get(g, sb, 9); mk = marker(g)
        st = state(m)
        cov, _ = cover(m, mk)
        if cov == 4:
            print(f"  PLACED 4/4 frame={st['r0']}-{st['r1']}x{st['c0']}-{st['c1']}")
            break
        if st["c0"] != 6:
            obs = step(right if st["c0"] < 6 else left); continue
        if st["r0"] != 3:
            obs = step(down if st["r0"] < 3 else up); continue
        break
    obs = sel(env, sb, 9, obs); g = canonical_layer(obs); m = get(g, sb, 9); mk = marker(g)
    st = state(m); cov, curset = cover(m, mk)
    print(f"FINAL vrel={st['vrel']} hrel={st['hrel']} frame={st['r0']}-{st['r1']}x{st['c0']}-{st['c1']} "
          f"vabs={st['vabs']} habs={st['habs']} cover={cov}/4 missing={[t for t in TIPS if t not in curset]}")


if __name__ == "__main__":
    main()
