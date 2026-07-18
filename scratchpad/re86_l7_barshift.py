"""re86 L7 bar-shift measurement harness (R66, the re86_l6_hrel.py pattern):
select a cross (colour-10), drive it to a controlled position vs the obstacle, and
issue SINGLE scripted pushes, reading the exact bar positions directly from the
sprite each step to derive the empirical control law. Sprite read is dev-time only
(for measurement); the real controller is frame-only.

Bars from the sprite: vbar = the (near-)full column, hbar = the (near-)full row,
in ABS coords. We log (x,y,w,h, vbar_abs_col, hbar_abs_row) after each push, and
the obstacle box, so each push's effect is attributable to the overlap case.
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
from re86_l7_ctrl import marker, l7_regions  # type: ignore
from admorphiq.adapters25.re86 import _station_boxes

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
MOV = "0031cppcuvqlbi"


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def cross_sprite(env, color):
    from collections import Counter
    for s in env._game.current_level.get_sprites_by_tag(MOV):
        cc = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
        if cc and cc.most_common(1)[0][0] == color:
            return s
    return None


def bars(s):
    """(x,y,w,h, vbar_abs_col, hbar_abs_row) from the sprite pixels."""
    px = s.pixels
    h, w = px.shape
    vcol = max(range(w), key=lambda c: int(np.sum(px[:, c] != -1)))
    hrow = max(range(h), key=lambda r: int(np.sum(px[r, :] != -1)))
    return s.x, s.y, w, h, s.x + vcol, s.y + hrow


def sel_color(env):
    from collections import Counter
    for s in env._game.current_level.get_sprites_by_tag(MOV):
        if int(s.pixels[s.height // 2, s.width // 2]) == 0:
            cc = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
            return cc.most_common(1)[0][0] if cc else -1
    return None


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

    COLOR = 10
    obs = select(env, obs, COLOR)

    def drive_selected(target_bars_pred, maxsteps=80):
        """crude free driver: move the selected cross toward pred(bars)->action."""
        nonlocal obs
        for _ in range(maxsteps):
            obs = select(env, obs, COLOR)
            sp = cross_sprite(env, COLOR)
            if sp is None:
                return
            a = target_bars_pred(bars(sp))
            if a is None:
                return
            obs = step(env, A[a])

    # Goal: cross in the GAP between the station rows (2-6) and the obstacle
    # (rows 28-35) — a 19-tall cross fits at y in [7,8] (spans 7-26). Keep it there
    # while aligning the vbar col into the obstacle cols, so no station recolour and
    # a DOWN push then collides with the vbar-col-in-obstacle case.
    obc = (ob[1] + ob[3]) // 2

    def approach(b):
        x, y, w, h, vc, hr = b
        in_gap = y >= 7 and (y + h - 1) < ob[0]   # below stations, above obstacle rows
        if not in_gap:
            return 1 if (y + h - 1) >= ob[0] else 2  # up if it dips into the obstacle, else down
        if vc < obc - 1:
            return 4                      # move right until vbar col ~ obstacle centre
        if vc > obc + 1:
            return 3
        return None
    drive_selected(approach)
    sp = cross_sprite(env, COLOR)
    if sp is None:
        print("colour-10 lost during approach (recoloured?)"); return
    print(f"approach done: bars(x,y,w,h,vbarcol,hbarrow)={bars(sp)}")

    print("--- 6 DOWN pushes (vbar-col in obstacle, hbar above) ---")
    for i in range(6):
        obs = select(env, obs, COLOR)
        obs = step(env, A[2])
        sp = cross_sprite(env, COLOR)
        print(f"  down{i}: {bars(sp)}")
    print("--- 6 UP pushes ---")
    for i in range(6):
        obs = select(env, obs, COLOR)
        obs = step(env, A[1])
        sp = cross_sprite(env, COLOR)
        print(f"  up{i}: {bars(sp)}")


if __name__ == "__main__":
    main()
