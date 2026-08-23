"""R98: what consumes a piece?

Measured twice that a press can destroy the piece it moves — once on a row-3 piece that
shrank cell by cell and ended the run, once on a downward press into plain background.
Neither sighting explains the cause, and a plan that unknowingly destroys its own piece
cannot be repaired by better placement.

This drives ONE piece in ONE direction, step by step, printing the inventory and the
piece's own cells each time, so the step that loses it is visible together with what was
around it.

NON-GATING diagnostic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

_spec = importlib.util.spec_from_file_location("dw", Path(__file__).with_name("depth_walk.py"))
dw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dw)

from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding  # noqa: E402

LEVEL = 3
STEPS = 10


def _inventory(g: FlowGrounding):
    pieces = g.pieces()
    if pieces is UNKNOWN:
        return None
    return [(sorted(cells)[0], len(cells)) for _, cells in pieces.value]


def main() -> int:
    w = dw.Walker()
    for _ in range(LEVEL):
        dw.play_level(w)

    g = FlowGrounding()
    g.observe(0, None, w.obs.frame)
    for a in (1, 1, 2, 3, 4):
        w.act(a, g)
    for a in (1, 2, 3, 4):
        if a in dw.deltas_of(g):
            continue
        w.act(a, g)
        if a not in dw.deltas_of(g):
            w.act(a, g)
    candidates = g.selection_candidates()
    if candidates is not UNKNOWN:
        for cell in candidates.value[:6]:
            w.click(cell, g)
    w.act(5, g)

    start = _inventory(g)
    print(f"idx{LEVEL}: inventory at the start {start}")
    if not start:
        print("  no inventory")
        return 0

    deltas = dw.deltas_of(g)
    want = (1, 0)
    if len(sys.argv) > 2:
        want = {"down": (1, 0), "up": (-1, 0), "left": (0, -1), "right": (0, 1)}[sys.argv[2]]
    down = next((a for a, (dr, dc) in sorted(deltas.items()) if (dr, dc) == want), None)
    if down is None:
        print(f"  no downward action measured; have {sorted(deltas.items())}")
        return 0

    which = int(sys.argv[1]) if len(sys.argv) > 1 else len(start) - 1
    anchor = start[which][0]
    w.click(anchor, g)
    print(f"  driving the piece anchored {anchor} by {want}")
    for step in range(STEPS):
        before = _inventory(g)
        held = g.tracked_region()
        w.act(down, g)
        after = _inventory(g)
        now = g.tracked_region()
        print(f"  step {step}: {len(before or [])} -> {len(after or [])} pieces | "
              f"selected {sorted(held.value)[:2] if held is not UNKNOWN else None} -> "
              f"{sorted(now.value)[:2] if now is not UNKNOWN else None}")
        if after is not None and before is not None and len(after) < len(before):
            print(f"    LOST HERE: {before} -> {after}")
            cells = g._prev_cells
            size = int(round(len(cells) ** 0.5))
            for r in range(size):
                print("      r%-2d " % r + " ".join(f"{cells[(r, c)]:2d}" for c in range(size)))
            break
        if not w.alive:
            print("    game over")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
