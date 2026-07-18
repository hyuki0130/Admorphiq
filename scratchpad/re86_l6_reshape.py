"""re86 L6 reshape characterisation (R63 build step 1): the EXACT reshape model.

For each movable, dump its shape (rectangle outline? cross?), then push it into the
central obstacle on each axis and record the precise W×H transition + the pixel
pattern (hollow outline vs cross). Feeds the reshape-and-place planner.
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


def describe(cells):
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    h, w = max(rs) - min(rs) + 1, max(cs) - min(cs) + 1
    area = h * w
    fill = len(cells) / area if area else 0
    # hollow rectangle outline ≈ perimeter/area; cross ≈ two bars
    return f"{h}x{w} @({min(rs)},{min(cs)}) px={len(cells)} fill={fill:.2f}"


def sel(env, ad, sb, color, steps):
    obs = env.observation_space
    for _ in range(8):
        g = canonical_layer(obs); mk = marker(g)
        movs = {m["color"]: m for m in _l5_movables(g, set(), sb, subtract_boxes=False)}
        m = movs.get(color)
        if m and mk and abs(m["cen"][0] - mk[0]) <= 15 and abs(m["cen"][1] - mk[1]) <= 15:
            return obs, steps
        obs = env.step(A[5]); steps += 1
    return obs, steps


def push(env, sb, color, act, n, steps, label):
    obs = env.observation_space
    prev = None
    for k in range(n):
        obs = env.step(A[act]); steps += 1
        g = canonical_layer(obs)
        movs = {m["color"]: m for m in _l5_movables(g, set(), sb, subtract_boxes=False)}
        m = movs.get(color)
        d = describe(m["cells"]) if m else "GONE"
        if d != prev:
            print(f"    {label} step{k}: {d}")
            prev = d
    return obs, steps


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
        obs = env.step(A[5]); steps += 1
    g = canonical_layer(obs); _st, sb = _station_boxes(g)
    movs = _l5_movables(g, set(), sb, subtract_boxes=False)
    for m in movs:
        if m["color"] in (9, 11):
            print(f"movable-{m['color']} initial: {describe(m['cells'])}")
    # dirmap: which action is which world direction
    print(f"dir_global={dict(ad._dir_global)}")
    right = next((a for a, s in ad._dir_global.items() if s == (0, 1)), 4)
    down = next((a for a, s in ad._dir_global.items() if s == (1, 0)), 2)
    for color in (11, 9):
        print(f"\n== movable-{color}: push RIGHT into obstacle (horizontal) ==")
        obs, steps = sel(env, ad, sb, color, steps)
        obs, steps = push(env, sb, color, right, 16, steps, f"c{color}/RIGHT")
        print(f"== movable-{color}: push DOWN into obstacle (vertical) ==")
        obs, steps = sel(env, ad, sb, color, steps)
        obs, steps = push(env, sb, color, down, 16, steps, f"c{color}/DOWN")


if __name__ == "__main__":
    main()
