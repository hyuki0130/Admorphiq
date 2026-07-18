"""re86 L8 CORNER-obstacle reshape measurement (task #88 L8 build, de-risk).

L8's obstacle is a 5x5 blob in the TOP-RIGHT corner (rows 1-5, cols 58-62), not
central. Verify _l6_step_outline's reshape law still holds there — one scripted
push per direction, reading the outline sprite dims (dev-time). Expected law
(source 0036 branch @1956): a HORIZONTAL push (into the obstacle) -> h+3,w-3;
a VERTICAL push -> h-3,w+3. The risk is a board-edge CLAMP (the corner is next to
the right/top edges) masquerading as/blocking the reshape.
"""
from __future__ import annotations
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _l6_obstacle_box
from admorphiq.adapters25.base import canonical_layer

A = {i: getattr(GameAction, f"ACTION{i}") for i in range(1, 6)}
OUTLINE = "0036ilsgwuvbxv"


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def sel_outline(env):
    """The SELECTED outline sprite (centre pixel == marker 0), regardless of its
    current colour (it recolours when crossing a station)."""
    for s in env._game.current_level.get_sprites_by_tag(OUTLINE):
        if int(s.pixels[s.height // 2, s.width // 2]) == 0:
            return s
    return None


def sel_color(env):
    s = sel_outline(env)
    if s is None:
        return None
    cc = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
    return cc.most_common(1)[0][0] if cc else -1


def select(env, obs, color):
    for _ in range(6):
        if sel_color(env) == color:
            return obs
        obs = step(env, A[5])
    return obs


def dims(s):
    return s.x, s.y, s.width, s.height


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    s = 0
    while s < 6000 and int(getattr(obs, "levels_completed", 0) or 0) < 7 and not ad.is_done([], obs):
        obs = step(env, ad.choose_action([], obs)); s += 1
    for _ in range(3):
        obs = step(env, A[5])
    g = canonical_layer(obs)
    ob = _l6_obstacle_box(g)  # (r0,c0,r1,c1)
    print(f"L8 obstacle rows {ob[0]}-{ob[2]} cols {ob[1]}-{ob[3]}")
    COLOR = 10
    obs = select(env, obs, COLOR)  # select once; selection is sticky across moves
    sp = sel_outline(env)
    print(f"spawn outline colour-{COLOR}: x,y,w,h={dims(sp)}")

    def drive(pred, maxsteps=120):
        nonlocal obs
        for _ in range(maxsteps):
            sp = sel_outline(env)
            if sp is None:
                return
            a = pred(dims(sp))
            if a is None:
                return
            obs = step(env, A[a])

    # ---- HORIZONTAL reshape: keep cols CLEAR-LEFT of the obstacle while rising to
    # rows 1-5 (so the rise is free, no premature vertical reshape), then push RIGHT.
    def approachH(d):
        x, y, w, h = d
        if x + w - 1 > ob[1] - 3:  # right edge not clear-left of obstacle cols
            return 3               # left
        if y > ob[0]:              # top below obstacle top -> rise (cols clear -> free)
            return 1
        if y < ob[0] - 2:
            return 2
        return None
    drive(approachH)
    sp = sel_outline(env)
    print(f"H approach: x,y,w,h={dims(sp)} (rows {sp.y}-{sp.y+sp.height-1}) colour={sel_color(env)}")
    print("--- 3 RIGHT pushes into the corner obstacle (expect h+3,w-3) ---")
    for i in range(3):
        obs = step(env, A[4])
        sp = sel_outline(env)
        print(f"  right{i}: x,y,w,h={dims(sp)}")


if __name__ == "__main__":
    main()
