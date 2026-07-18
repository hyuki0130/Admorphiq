"""re86 L6 reshape verification v2 — ALIGN to overlap the obstacle, THEN push.

The v1 probe pushed the pieces right/down directly, but at their start
positions neither ROW/COL-overlaps the central colour-1 obstacle (rows 28-35,
cols 28-35), so a horizontal push just TRANSLATES then edge-clamps — it never
triggered the reshape. This probe first aligns the piece so its rows overlap the
obstacle's rows (for a horizontal push) or its cols overlap (for a vertical
push), then pushes INTO the obstacle and records the exact W×H + px transition,
to verify the perimeter-conserving reshape law (horizontal push -> (h+3,w-3)).
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
OBST = (28, 35, 28, 35)  # r0,r1,c0,c1 of the colour-1 obstacle


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


def desc(m):
    if m is None:
        return "GONE"
    r0, r1, c0, c1 = bbox(m)
    return f"{r1-r0+1}x{c1-c0+1} @({r0},{c0}) px={len(m['cells'])}"


def sel(env, ad, sb, color):
    obs = env.observation_space
    for _ in range(10):
        g = canonical_layer(obs); mk = marker(g); m = get(g, sb, color)
        if m and mk and abs(m["cen"][0] - mk[0]) <= 15 and abs(m["cen"][1] - mk[1]) <= 15:
            return obs
        obs = env.step(A[5])
    return obs


def step(env, act):
    return env.step(A[act])


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
    print(f"dir_global={dict(ad._dir_global)}")
    up = next((a for a, s in ad._dir_global.items() if s == (-1, 0)), 1)
    down = next((a for a, s in ad._dir_global.items() if s == (1, 0)), 2)
    left = next((a for a, s in ad._dir_global.items() if s == (0, -1)), 3)
    right = next((a for a, s in ad._dir_global.items() if s == (0, 1)), 4)

    for color in (11, 9):
        obs = sel(env, ad, sb, color)
        g = canonical_layer(obs); m = get(g, sb, color)
        print(f"\n== movable-{color} start: {desc(m)} obstacle rows {OBST[0]}-{OBST[1]} cols {OBST[2]}-{OBST[3]} ==")
        # ALIGN ROWS to obstacle (move the piece so its row-span covers 28-35), then push RIGHT.
        for _ in range(20):
            g = canonical_layer(obs); m = get(g, sb, color)
            if m is None:
                break
            r0, r1, c0, c1 = bbox(m)
            crow = (r0 + r1) // 2
            if abs(crow - 31) <= 2:
                break
            obs = step(env, up if crow > 31 else down)
        g = canonical_layer(obs); m = get(g, sb, color)
        print(f"  aligned rows: {desc(m)}")
        print(f"  -- push RIGHT into obstacle --")
        prev = None
        for k in range(14):
            obs = step(env, right)
            g = canonical_layer(obs); m = get(g, sb, color)
            d = desc(m)
            if d != prev:
                r0, r1, c0, c1 = bbox(m) if m else (0, 0, 0, 0)
                peri = 2 * (r1 - r0 + 1) + 2 * (c1 - c0 + 1) - 4 if m else 0
                print(f"    R{k}: {d} peri={peri}")
                prev = d
        # Re-select and try COL-align + push DOWN for the vertical reshape.
        obs = sel(env, ad, sb, color)
        g = canonical_layer(obs); m = get(g, sb, color)
        if m is not None:
            for _ in range(20):
                g = canonical_layer(obs); m = get(g, sb, color)
                if m is None:
                    break
                r0, r1, c0, c1 = bbox(m); ccol = (c0 + c1) // 2
                if abs(ccol - 31) <= 2:
                    break
                obs = step(env, right if ccol < 31 else left)
            g = canonical_layer(obs); m = get(g, sb, color)
            print(f"  aligned cols: {desc(m)}")
            print(f"  -- push DOWN into obstacle --")
            prev = None
            for k in range(14):
                obs = step(env, down)
                g = canonical_layer(obs); m = get(g, sb, color)
                d = desc(m)
                if d != prev:
                    r0, r1, c0, c1 = bbox(m) if m else (0, 0, 0, 0)
                    peri = 2 * (r1 - r0 + 1) + 2 * (c1 - c0 + 1) - 4 if m else 0
                    print(f"    D{k}: {d} peri={peri}")
                    prev = d


if __name__ == "__main__":
    main()
