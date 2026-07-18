"""movable-9 full reshape+place via the measured corridor control. Phases:
 1. vrel=6: right corridor (cols≥36), row-overlap obstacle, push LEFT — the vbar
    pins at the obstacle right edge and each further left push shifts vrel−3.
 2. hrel=6: above-obstacle corridor (rows 3-27), move LEFT to col-overlap, push
    DOWN — the hbar pins at the obstacle top and each further down push shifts
    hrel−3 (vbar untouched: vertical collisions never move the vbar).
 3. carry: move UP to r0=3 (free; bars leave the obstacle), then LEFT to c0=6
    (free; rows 3-27 are above the obstacle so horizontal moves never pin the
    vbar) → cross covers all 4 tips.
Reports coverage of (6,12),(9,9),(9,30),(27,12).
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


def marker(g):
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == 0:
                return (r, c)
    return None


def get(g, sb):
    for m in _l5_movables(g, set(), sb, subtract_boxes=False):
        if m["color"] == 9:
            return m
    return None


def st(m):
    cs = set(m["cells"]); rs = [r for r, _ in cs]; cc = [c for _, c in cs]
    r0, r1, c0, c1 = min(rs), max(rs), min(cc), max(cc); h, w = r1 - r0 + 1, c1 - c0 + 1
    vc = [c for c in range(c0, c1 + 1) if sum((r, c) in cs for r in range(r0, r1 + 1)) >= h * 0.7]
    hr = [r for r in range(r0, r1 + 1) if sum((r, c) in cs for c in range(c0, c1 + 1)) >= w * 0.7]
    va = vc[len(vc) // 2] if vc else c0
    ha = hr[len(hr) // 2] if hr else r0
    return {"r0": r0, "r1": r1, "c0": c0, "c1": c1, "va": va, "ha": ha, "vrel": va - c0, "hrel": ha - r0, "cells": cs}


def cover(m, mk):
    rel = frozenset((r - mk[0], c - mk[1]) for r, c in m["cells"])
    cur = {(mk[0] + dr, mk[1] + dc) for dr, dc in rel}
    return sum(1 for t in TIPS if t in cur), cur


def sel(env, sb, obs):
    for _ in range(12):
        g = canonical_layer(obs); mk = marker(g); m = get(g, sb)
        if m and mk and abs(m["cen"][0] - mk[0]) <= 15 and abs(m["cen"][1] - mk[1]) <= 15:
            return obs
        obs = env.step(A[5])
    return obs


def solve9(env, ad, sb, dm, obs, verbose=True):
    up = next(a for a, s in dm.items() if s == (-1, 0)); down = next(a for a, s in dm.items() if s == (1, 0))
    left = next(a for a, s in dm.items() if s == (0, -1)); right = next(a for a, s in dm.items() if s == (0, 1))

    def cur():
        nonlocal obs
        obs = sel(env, sb, obs); g = canonical_layer(obs); return get(g, sb), marker(g)

    def push(act):
        nonlocal obs
        obs = env.step(A[act])

    # PHASE 1 — vrel=6. Position: right corridor (c0>=36) + row-overlap (centre~31).
    for _ in range(60):
        m, mk = cur()
        if m is None:
            push(5); continue
        s = st(m)
        if s["vrel"] == 6:
            break
        cr = (s["r0"] + s["r1"]) // 2
        if s["c0"] < 33:  # got pushed too far left of the right corridor; nudge right (free while above/below overlap band)
            push(right); continue
        if abs(cr - 31) > 3:  # align rows to obstacle band (free vertical move in the right corridor)
            push(down if cr < 31 else up); continue
        push(left if s["vrel"] > 6 else right)
    m, mk = cur(); s = st(m)
    if verbose:
        print(f"P1 vrel={s['vrel']} frame r{s['r0']}-{s['r1']} c{s['c0']}-{s['c1']}")
    if s["vrel"] != 6:
        return obs, False

    # PHASE 2 — hrel=6 without disturbing vrel, in clean sequential sub-steps
    # matching the verified hrel-probe path.
    # 2a: rise to the top corridor (r0<=3) — free (right corridor, bars clear).
    for _ in range(20):
        m, mk = cur()
        if m is None:
            push(5); continue
        if st(m)["r0"] <= 3:
            break
        push(up)
    # 2b: move LEFT to col-overlap the obstacle (c0<=15) — free (above obstacle).
    for _ in range(20):
        m, mk = cur()
        if m is None:
            push(5); continue
        if st(m)["c0"] <= 15:
            break
        push(left)
    # 2c: push DOWN — frame translates down until the hbar pins at the obstacle,
    # then each down push shifts hrel−3; stop at hrel=6 (vbar untouched).
    for _ in range(20):
        m, mk = cur()
        if m is None:
            push(5); continue
        if st(m)["hrel"] == 6:
            break
        push(down)
    m, mk = cur(); s = st(m)
    if verbose:
        print(f"P2 vrel={s['vrel']} hrel={s['hrel']} frame r{s['r0']}-{s['r1']} c{s['c0']}-{s['c1']}")
    if s["hrel"] != 6 or s["vrel"] != 6:
        return obs, False

    # PHASE 3 — carry to frame (r0=3, c0=6). Up first (free), then left (free, above obstacle).
    for _ in range(60):
        m, mk = cur()
        if m is None:
            push(5); continue
        s = st(m); cov, _ = cover(m, mk)
        if cov == 4:
            break
        if s["r0"] > 3:
            push(up); continue
        if s["c0"] > 6:
            push(left); continue
        if s["c0"] < 6:
            push(right); continue
        break
    m, mk = cur(); s = st(m); cov, curset = cover(m, mk)
    if verbose:
        print(f"P3 frame r{s['r0']}-{s['r1']} c{s['c0']}-{s['c1']} va={s['va']} ha={s['ha']} cover={cov}/4 "
              f"missing={[t for t in TIPS if t not in curset]}")
    return obs, cov == 4


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
    obs, ok = solve9(env, ad, sb, dm, obs)
    print(f"RESULT movable-9 placed 4/4 = {ok}  levels={int(getattr(obs,'levels_completed',0) or 0)}")


if __name__ == "__main__":
    main()
