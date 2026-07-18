"""re86 L7 de-risk (sprite-tracked): validate the physics on the live L7 pieces
by tracking sprites via tag 0031 (dev-time read; the real adapter is frame-only).
dir 1=up 2=down 3=left 4=right (source-fixed).

A. colour-12 outline recolour at station-9 (top, col 17) then VERTICAL reshape
   into the obstacle: expect 13x13 -> 10x16 -> 7x19 (perimeter-conserving).
B. colour-10 cross bar-shift: push into the obstacle band, observe bar move.
"""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _l6_obstacle_box
from admorphiq.adapters25.base import canonical_layer

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
MOV = "0031cppcuvqlbi"


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def sprites_by_color(env):
    """{orig_index: (colour, x, y, w, h, selected)} for the 3 movables."""
    lvl = env._game.current_level
    out = {}
    for i, s in enumerate(lvl.get_sprites_by_tag(MOV)):
        cols = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
        col = cols.most_common(1)[0][0] if cols else -1
        sel = int(s.pixels[s.height // 2, s.width // 2]) == 0
        out[i] = {"color": col, "x": s.x, "y": s.y, "w": s.width, "h": s.height, "sel": sel}
    return out


def sel_index(env):
    for i, d in sprites_by_color(env).items():
        if d["sel"]:
            return i
    return None


def drive_to_select(env, obs, idx):
    for _ in range(6):
        if sel_index(env) == idx:
            return obs
        obs = step(env, A[5])
    return obs


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    steps = 0
    while steps < 4000 and int(getattr(obs, "levels_completed", 0) or 0) < 6 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = step(env, a)
        steps += 1
    g = canonical_layer(obs)
    ob = _l6_obstacle_box(g)
    print(f"L7 at {steps}  obstacle={ob}")
    sp = sprites_by_color(env)
    print("movables (sprite):", {i: (d["color"], f"{d['w']}x{d['h']}", f"@({d['y']},{d['x']})") for i, d in sp.items()})
    # identify the outline (colour 12) and a cross (colour 10) index
    idx12 = next(i for i, d in sp.items() if d["color"] == 12)
    idx10 = next(i for i, d in sp.items() if d["color"] == 10)

    # ---- A. recolour colour-12 at station-9 (centre col ~17, top row ~4) ----
    print("--- A. colour-12 recolour @ station-9 then vertical reshape ---")
    obs = drive_to_select(env, obs, idx12)
    for it in range(120):
        d = sprites_by_color(env)[idx12]
        if d["color"] == 9:
            print(f"  RECOLOURED 12->9 at it={it} ({d['w']}x{d['h']} @({d['y']},{d['x']}))")
            break
        if sel_index(env) != idx12:
            obs = step(env, A[5]); continue
        cx = d["x"] + d["w"] // 2
        if abs(cx - 17) > 2:
            obs = step(env, A[4] if cx < 17 else A[3])
        else:
            obs = step(env, A[1])  # up into station
    else:
        print("  colour-12 did NOT recolour ->", sprites_by_color(env)[idx12])

    # vertical reshape: col-align to obstacle (col 31), push DOWN
    last = None
    obc = (ob[1] + ob[3]) // 2
    for it in range(120):
        d = sprites_by_color(env)[idx12]
        cur = (d["w"], d["h"])
        if cur != last:
            print(f"    shape {d['w']}x{d['h']} @({d['y']},{d['x']}) col={d['color']}")
            last = cur
        if d["h"] <= 7:
            print("  -> VERTICAL reshape to h=7 CONFIRMED"); break
        if sel_index(env) != idx12:
            obs = step(env, A[5]); continue
        cx = d["x"] + d["w"] // 2
        if abs(cx - obc) > 2:
            obs = step(env, A[4] if cx < obc else A[3])
        else:
            obs = step(env, A[2])  # down into obstacle

    # ---- B. colour-10 bar-shift ----
    print("--- B. colour-10 bar-shift ---")
    obs = drive_to_select(env, obs, idx10)
    obr = (ob[0] + ob[2]) // 2
    last = None
    for it in range(60):
        d = sprites_by_color(env)[idx10]
        key = (d["x"], d["y"], d["w"], d["h"])
        if key != last:
            print(f"    @({d['y']},{d['x']}) {d['w']}x{d['h']} col={d['color']}")
            last = key
        if sel_index(env) != idx10:
            obs = step(env, A[5]); continue
        cy = d["y"] + d["h"] // 2
        if abs(cy - obr) > 2:
            obs = step(env, A[2] if cy < obr else A[1])
        else:
            obs = step(env, A[4])  # push right into obstacle


if __name__ == "__main__":
    main()
