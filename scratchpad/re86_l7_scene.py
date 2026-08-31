"""Dump the settled L7 scene geometry (stations, obstacle, targets) + colour-7
spawn state, so the colour-7 leg controller can be designed against real coords.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _station_boxes, _target_boxes, _l6_obstacle_box
from admorphiq.adapters25.base import canonical_layer
from re86_l7_ctrl import marker, l7_regions  # type: ignore

A = {i: getattr(GameAction, f"ACTION{i}") for i in range(1, 6)}


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


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
    stations, sboxes = _station_boxes(g)
    ob = _l6_obstacle_box(g)
    tby = {}
    for r, c in _target_boxes(g):
        tby.setdefault(g[r][c], []).append((r, c))
    print(f"stations(colour->centre r,c) = {stations}")
    print(f"station boxes = {sboxes}")
    print(f"obstacle = {ob}")
    print(f"targets = { {k: sorted(v) for k, v in tby.items()} }")
    regs = l7_regions(g, sboxes)
    print("movable regions:")
    for m in regs:
        print(f"  colour={m['color']} cen={m['cen']} bbox={m['bbox']} npix={len(m['cells'])}")


if __name__ == "__main__":
    main()
