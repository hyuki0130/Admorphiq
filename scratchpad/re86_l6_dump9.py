"""Dump movable-9's actual pixel pattern at start and through aligned right/down
pushes into the obstacle — to see the true cross arm structure and exactly how a
push moves its pixels (which arm grows/shrinks). Prints a compact ASCII of the
piece's bbox (# = colour-9 pixel, . = empty)."""
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


def ascii_of(m):
    cells = set(m["cells"])
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    lines = [f"  bbox rows {r0}-{r1} cols {c0}-{c1} ({r1-r0+1}x{c1-c0+1}) px={len(cells)}"]
    for r in range(r0, r1 + 1):
        lines.append("  " + "".join("#" if (r, c) in cells else "." for c in range(c0, c1 + 1)))
    return "\n".join(lines)


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
    dirmap = dict(ad._dir_global)
    up = next(a for a, s in dirmap.items() if s == (-1, 0))
    down = next(a for a, s in dirmap.items() if s == (1, 0))
    left = next(a for a, s in dirmap.items() if s == (0, -1))
    right = next(a for a, s in dirmap.items() if s == (0, 1))

    obs = sel(env, sb, 9, obs)
    g = canonical_layer(obs); m = get(g, sb, 9)
    print("=== movable-9 START ===")
    print(ascii_of(m))
    # align rows to obstacle centre (row 31), push right a few times.
    for _ in range(20):
        g = canonical_layer(obs); m = get(g, sb, 9)
        r0 = min(r for r, _ in m["cells"]); r1 = max(r for r, _ in m["cells"])
        if abs((r0 + r1) // 2 - 31) <= 2:
            break
        obs = env.step(A[up if (r0 + r1) // 2 > 31 else down])
    g = canonical_layer(obs); m = get(g, sb, 9)
    print("=== after row-align ===")
    print(ascii_of(m))
    for k in range(4):
        obs = env.step(A[right])
        g = canonical_layer(obs); m = get(g, sb, 9)
        if m is None:
            print(f"=== after right push {k+1}: GONE ==="); continue
        print(f"=== after right push {k+1} ===")
        print(ascii_of(m))
    # re-select, align cols, push down
    obs = sel(env, sb, 9, obs)
    for _ in range(20):
        g = canonical_layer(obs); m = get(g, sb, 9)
        if m is None:
            break
        c0 = min(c for _, c in m["cells"]); c1 = max(c for _, c in m["cells"])
        if abs((c0 + c1) // 2 - 31) <= 2:
            break
        obs = env.step(A[right if (c0 + c1) // 2 < 31 else left])
    g = canonical_layer(obs); m = get(g, sb, 9)
    if m:
        print("=== after col-align ===")
        print(ascii_of(m))
    for k in range(4):
        obs = env.step(A[down])
        g = canonical_layer(obs); m = get(g, sb, 9)
        if m is None:
            print(f"=== after down push {k+1}: GONE ==="); continue
        print(f"=== after down push {k+1} ===")
        print(ascii_of(m))


if __name__ == "__main__":
    main()
