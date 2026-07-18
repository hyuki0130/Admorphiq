"""re86 L6 frontier probe (R63): reach L6, dump the scene, compare to L5.

Runs the adapter through L1-L5 (clears at ~370 actions), then at L6 entry
(levels_completed == 5) settles and dumps stations / movables / gate colours /
target boxes / cluster structure — the same read that characterised L5 — to see
whether L6 is another N-piece 3→2 set-cover variant (the _decide_l5 FSM may
extend) or introduces a new mechanic. Uses make("re86") = the 8af5384d file
(loader lesson: confirm the loaded hash from the run log).
"""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import (
    Adapter, _station_boxes, _target_boxes, _l5_movables, _l5_gate_colors, _l5_cluster,
)
from admorphiq.adapters25.base import canonical_layer

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
MOV_TAG = "0031cppcuvqlbi"


def sprites(g):
    out = []
    for s in g.current_level.get_sprites_by_tag(MOV_TAG):
        cols = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
        if cols:
            out.append((cols.most_common(1)[0][0], (s.y + s.height // 2, s.x + s.width // 2), s.width, s.height))
    return out


def dump(env, ad, target_lv, label):
    g = env._game
    grid = canonical_layer(env.observation_space)
    stations, sboxes = _station_boxes(grid)
    movs = _l5_movables(grid, set(), sboxes, subtract_boxes=False)
    gc = _l5_gate_colors(grid, sboxes, set(stations), {m["color"] for m in movs})
    gates = {}
    from admorphiq.adapters25.re86 import _l5_scan_gates
    gcells = _l5_scan_gates(grid, sboxes, gc)
    tboxes = _target_boxes(grid)
    tb_by_color = Counter(grid[r][c] for r, c in tboxes)
    print(f"\n===== {label} (levels_completed={target_lv}) =====")
    print(f"  stations={stations}")
    print(f"  movables(frame-parse)={[(m['color'], m['cen'], len(m['cells'])) for m in movs]}")
    print(f"  movables(GT sprite)={sprites(g)}")
    print(f"  gate_colors={gc}")
    for c in sorted(gcells):
        cl = _l5_cluster(gcells[c])
        print(f"    gate colour {c}: {len(gcells[c])} cells in {len(cl)} clusters (sizes {[len(x) for x in cl]})")
    print(f"  target_boxes by colour (raw)={dict(tb_by_color)}")


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    steps = 0
    seen = {}
    while steps < 2500 and not ad.is_done([], obs):
        lv = int(getattr(obs, "levels_completed", 0) or 0)
        if lv == 5 and 5 not in seen:
            # settle then dump L6
            for _ in range(3):
                obs = env.step(A[5]); steps += 1
            dump(env, ad, 5, "L6 ENTRY")
            seen[5] = steps
            break
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    if 5 not in seen:
        print(f"did NOT reach L6 (final levels={int(getattr(obs,'levels_completed',0) or 0)} @ {steps})")


if __name__ == "__main__":
    main()
