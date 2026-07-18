"""re86 L7 colour-7 (rectangular 37x19 cross) bar-shift measurement.
Measure the horizontal (vbar) shift: position the hbar ROW inside the obstacle
rows and push LEFT/RIGHT, reading the vbar abs col from the sprite each push.
Also confirm the recolour-at-station-8 approach (only the 1-wide vbar tip should
touch the station; the hbar stays below the station rows). Sprite read = dev-time
measurement only.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _l6_obstacle_box
from admorphiq.adapters25.base import canonical_layer
from re86_l7_bs_common import bars, cross_sprite, sel_color  # type: ignore

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def select(env, obs, color):
    for _ in range(6):
        if sel_color(env) == color:
            return obs
        obs = step(env, A[5])
    return obs


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    s = 0
    while s < 4000 and int(getattr(obs, "levels_completed", 0) or 0) < 6 and not ad.is_done([], obs):
        obs = step(env, ad.choose_action([], obs)); s += 1
    for _ in range(3):
        obs = step(env, A[5])
    g = canonical_layer(obs)
    ob = _l6_obstacle_box(g)
    print(f"L7 obstacle rows {ob[0]}-{ob[2]} cols {ob[1]}-{ob[3]}")
    COLOR = 7
    obs = select(env, obs, COLOR)
    obr = (ob[0] + ob[2]) // 2

    def drive(pred, maxsteps=120):
        nonlocal obs
        for _ in range(maxsteps):
            obs = select(env, obs, COLOR)
            sp = cross_sprite(env, COLOR)
            if sp is None:
                return
            a = pred(bars(sp))
            if a is None:
                return
            obs = step(env, A[a])

    # Put the HBAR ROW exactly on an obstacle-band row (30 on the 3px grid) and the
    # vbar col to the RIGHT of the obstacle, then push LEFT (vbar-shift case:
    # hbar-row-in-obstacle + vbar-col-outside -> revert + shift vbar).
    target_hr = ob[0] + 2  # 30
    def approach(b):
        x, y, w, h, vc, hr = b
        if hr != target_hr:
            return 2 if hr < target_hr else 1
        if vc < ob[3] + 3:                  # vbar col just right of the obstacle
            return 4
        if vc > ob[3] + 4:
            return 3
        return None
    drive(approach)
    sp = cross_sprite(env, COLOR)
    if sp is None:
        print("colour-7 lost during approach"); return
    print(f"approach: bars(x,y,w,h,vbarcol,hbarrow)={bars(sp)}")
    print("--- 6 LEFT pushes (hbar row in obstacle) ---")
    for i in range(6):
        obs = select(env, obs, COLOR)
        obs = step(env, A[3])
        sp = cross_sprite(env, COLOR)
        print(f"  left{i}: {bars(sp)}")


if __name__ == "__main__":
    main()
