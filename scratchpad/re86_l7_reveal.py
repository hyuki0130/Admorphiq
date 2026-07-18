"""re86 L7 reveal + decode (R65 build): reach L7, reveal the occluded {8,9,11}
targets by safely nudging each movable, dump the FULL target sets + classify
(rect corners = OUTLINE colour-12; plus tips = a CROSS), and verify the live
mechanics on the L7 pieces:
  - recolour at a matching-colour station (flood),
  - reshape of the colour-12 outline on obstacle collision,
  - bar-shift of a colour-7/10 cross on obstacle collision.
Safe reveal: stations sit on row 4 (top); the obstacle is rows 28-35. Pieces
start in the lower half, so a DOWN/LEFT nudge reveals targets without recolour.
"""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import (
    Adapter, _station_boxes, _target_boxes, _l5_movables, _l6_obstacle_box,
    _l6_bbox, _l6_cross_state,
)
from admorphiq.adapters25.base import canonical_layer, most_common_color

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def is_rect(tgts):
    rows = sorted({r for r, _ in tgts}); cols = sorted({c for _, c in tgts})
    cs = set(tgts)
    return len(rows) == 2 and len(cols) == 2 and all((r, c) in cs for r in rows for c in cols)


def dump_targets(grid, tag):
    tb = _target_boxes(grid)
    by = {}
    for r, c in tb:
        by.setdefault(grid[r][c], []).append((r, c))
    print(f"  [{tag}] targets:")
    for col, cells in sorted(by.items()):
        kind = "RECT" if (len(cells) == 4 and is_rect(cells)) else ("PLUS?" if len(cells) >= 3 else "partial")
        print(f"     colour={col} n={len(cells)} {kind} {sorted(cells)}")
    return by


def marker(grid):
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] == 0:
                return (r, c)
    return None


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
    if int(getattr(obs, "levels_completed", 0) or 0) != 6:
        print("did NOT reach L7"); return
    print(f"reached L7 at {steps} actions")
    for _ in range(3):
        obs = step(env, A[5])
    grid = canonical_layer(obs)
    stations, sboxes = _station_boxes(grid)
    print(f"stations={stations}  obstacle={_l6_obstacle_box(grid)}")
    acc = dump_targets(grid, "initial")

    # accumulate targets over the whole reveal
    acc_by: dict[int, set] = {}
    def accumulate():
        g = canonical_layer(obs)
        for r, c in _target_boxes(g):
            acc_by.setdefault(g[r][c], set()).add((r, c))

    accumulate()
    # Reveal: cycle to each of the 3 pieces and nudge it DOWN then LEFT a few
    # steps (away from top-row stations); accumulate targets each frame.
    for cyc in range(3):
        for _ in range(cyc):
            obs = step(env, A[5])
        for mv in (2, 2, 2, 3, 3):  # down, down, down, left, left
            obs = step(env, A[mv]); accumulate()
        obs = step(env, A[5]); accumulate()  # next piece
    print("accumulated targets:")
    for col, cells in sorted(acc_by.items()):
        cells = sorted(cells)
        kind = "RECT" if (len(cells) == 4 and is_rect(cells)) else "PLUS/other"
        print(f"   colour={col} n={len(cells)} {kind} {cells}")

    # movables now
    g = canonical_layer(obs)
    movs = _l5_movables(g, set(), [], subtract_boxes=False)
    print("movables now:")
    for m in movs:
        r0, r1, c0, c1 = _l6_bbox(m["cells"])
        print(f"   colour={m['color']} {r1-r0+1}x{c1-c0+1} @({r0},{c0}) px={len(m['cells'])}")


if __name__ == "__main__":
    main()
