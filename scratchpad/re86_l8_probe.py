"""re86 L8 bounded PROBE (task #88 follow-up): drive the adapter through L1-L7
(now that L7 clears), settle on L8, and dump the scene — stations, obstacle,
targets, movables (colour + shape class + bbox) — to classify the L8 mechanic.
Investigation only, no build.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import (
    Adapter, _station_boxes, _target_boxes, _l6_obstacle_box, _l7_regions, _l7_full_bars,
)
from admorphiq.adapters25.base import canonical_layer

A = {i: getattr(GameAction, f"ACTION{i}") for i in range(1, 6)}


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def dump(tag, g):
    stations, sboxes = _station_boxes(g)
    ob = _l6_obstacle_box(g)
    tby = {}
    for r, c in _target_boxes(g):
        tby.setdefault(g[r][c], []).append((r, c))
    print(f"[{tag}] stations(colour->centre)={stations}")
    print(f"[{tag}] obstacle={ob}")
    print(f"[{tag}] targets={ {k: sorted(v) for k, v in tby.items()} }")
    regs = _l7_regions(g, sboxes)
    print(f"[{tag}] movables ({len(regs)}):")
    for m in regs:
        fc, fr = _l7_full_bars(m["cells"])
        r0, r1, c0, c1 = m["bbox"]
        kind = "outline?" if fc >= 2 and fr >= 2 else "cross?"
        print(f"    colour={m['color']} bbox=({r0},{r1},{c0},{c1}) {r1-r0+1}x{c1-c0+1} "
              f"npix={len(m['cells'])} full(cols,rows)=({fc},{fr}) -> {kind}")


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    win_levels = int(getattr(obs, "win_levels", 0) or 0)
    print(f"win_levels={win_levels}")
    s = 0
    while s < 6000 and int(getattr(obs, "levels_completed", 0) or 0) < 7 and not ad.is_done([], obs):
        obs = step(env, ad.choose_action([], obs)); s += 1
    lv = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"reached levels_completed={lv} in {s} steps, state={getattr(obs,'state',None)}")
    if lv < 7:
        print("did not reach L8 — abort"); return
    for _ in range(3):
        obs = step(env, A[5])
    dump("L8", canonical_layer(obs))


if __name__ == "__main__":
    main()
