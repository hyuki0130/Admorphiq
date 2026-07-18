"""Validate re86_l7_sim.sim_move against the LIVE engine for colour-7 (37x19
cross). Drive a fixed scripted sequence, reading the sprite each step, and
compare live (x,y,vrel,hrel) to the simulator prediction. Sprite read =
dev-time measurement only.
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
from re86_l7_sim import sim_move  # type: ignore

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
DXDY = {1: (0, -3), 2: (0, 3), 3: (-3, 0), 4: (3, 0)}


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def select(env, obs, color):
    for _ in range(6):
        if sel_color(env) == color:
            return obs
        obs = step(env, A[5])
    return obs


def live_state(env, color):
    sp = cross_sprite(env, color)
    if sp is None:
        return None
    x, y, w, h, vc, hr = bars(sp)
    return (x, y, vc - x, hr - y), w, h


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
    print(f"obstacle {ob}")
    COLOR = 7
    obs = select(env, obs, COLOR)
    st, w, h = live_state(env, COLOR)
    print(f"spawn state (x,y,vrel,hrel)={st} w={w} h={h}")

    # Scripted sequence: rise toward the obstacle, then exercise collisions —
    # ups (hbar approaches band, pin), lefts (vbar-set once hbar_in), downs.
    seq = [1] * 9 + [3, 3, 3, 3] + [2, 2] + [4, 4] + [1, 1, 1] + [3, 3]
    sim = st
    mism = 0
    for i, a in enumerate(seq):
        dx, dy = DXDY[a]
        sim = sim_move(sim, dx, dy, w, h, ob)
        obs = select(env, obs, COLOR)
        obs = step(env, A[a])
        ls = live_state(env, COLOR)
        if ls is None:
            print(f"  step{i} act{a}: colour-7 LOST (recoloured?) — stop"); break
        live = ls[0]
        ok = live == sim
        if not ok:
            mism += 1
        print(f"  step{i} act{a}: live={live} sim={sim} {'OK' if ok else 'MISMATCH'}")
    print(f"\n{'ALL MATCH' if mism == 0 else f'{mism} MISMATCHES'} over {len(seq)} pushes")


if __name__ == "__main__":
    main()
