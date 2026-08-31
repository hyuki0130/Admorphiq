"""re86 L7 colour-7 (37x19 rectangular cross) CLEAN bar-shift measurement.

The first bs7 pass drove blindly and never put a bar into the obstacle band, so
LEFT produced only a free translation. This version positions colour-7 with
sprite-read feedback so exactly ONE bar sits in the obstacle band, then issues
single scripted pushes and logs the exact (x,y,vbarcol,hbarrow) + the overlap
case so each push's effect is attributable. Sprite read = dev-time measurement.

Cases to measure (source `ucpbzrcoui` horizontal/vertical collision):
  A. hbar-row in obstacle rows, vbar-col OUT  -> LEFT push: vbar shift?
  B. vbar-col in obstacle cols, hbar-row OUT  -> DOWN/UP push: hbar shift?
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
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
    sp = cross_sprite(env, COLOR)
    print(f"spawn bars(x,y,w,h,vbarcol,hbarrow)={bars(sp)}")

    def push(a, label):
        nonlocal obs
        obs = select(env, obs, COLOR)
        obs = step(env, A[a])
        sp = cross_sprite(env, COLOR)
        b = bars(sp)
        x, y, w, h, vc, hr = b
        vin = ob[1] <= vc <= ob[3]
        hin = ob[0] <= hr <= ob[2]
        print(f"  {label}: x={x} y={y} vbarcol={vc}({'IN' if vin else 'out'}) hbarrow={hr}({'IN' if hin else 'out'})")

    def drive(pred, maxsteps=100):
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

    # ---- CASE A: hbar-row in obstacle, vbar-col OUT (left of obstacle) ----
    # Free-translate: move LEFT so vbar col is well left of the obstacle (keeps the
    # vbar out of the obstacle cols during subsequent vertical moves), then move
    # DOWN so the hbar row enters the obstacle rows. With the vbar out, a vertical
    # move is a free translation (no bar through the obstacle), so the frame lowers.
    def posA(b):
        x, y, w, h, vc, hr = b
        if vc > ob[1] - 3:          # vbar col not clear-left of obstacle -> go left
            return 3
        if hr < ob[0] + 1:          # hbar row above the obstacle band -> go down
            return 2
        if hr > ob[2]:              # overshot -> up
            return 1
        return None
    drive(posA)
    sp = cross_sprite(env, COLOR)
    print(f"CASE A positioned: {bars(sp)}")
    print("--- CASE A: 5 LEFT pushes (hbar-in, vbar-out) ---")
    for i in range(5):
        push(3, f"A.left{i}")


if __name__ == "__main__":
    main()
