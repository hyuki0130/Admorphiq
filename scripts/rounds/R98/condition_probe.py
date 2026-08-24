"""R98: vary ONE condition at a time.

Six candidate rules have been struck off around two behaviours the model still gets wrong,
and every one of them was read off boards that differ in many ways at once. This probe
changes a single thing between two spills — one piece, one cell — and prints what the flow
did on each, so a difference in the trail can be attributed to that cell rather than to
whatever else those boards did not share.

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


def _ground(w) -> FlowGrounding:
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
    return g


def _report(g: FlowGrounding, label: str) -> None:
    trail = g.trajectory()
    pieces = g.pieces()
    if trail is UNKNOWN:
        print(f"  {label}: no spill")
        return
    layers = [sorted(layer) for layer in trail.value if layer]
    print(f"  {label}: pieces "
          f"{[(sorted(c)[0], len(c)) for _, c in pieces.value] if pieces is not UNKNOWN else '?'}")
    print(f"    trail {len(layers)} steps; first four {layers[:4]}")
    print(f"    model: emitters {g.embedded_sources()} | lanes {g.falling_sources()}")
    for row in sorted({c[0] for layer in layers for c in layer}):
        cells = sorted(c[1] for layer in layers for c in layer if c[0] == row)
        print(f"      row {row:2d}: {cells}")


def main() -> int:
    which = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    step = sys.argv[2] if len(sys.argv) > 2 else "right"

    w = dw.Walker()
    for _ in range(LEVEL):
        dw.play_level(w)
    g = _ground(w)
    w.act(5, g)
    _report(g, "baseline")

    pieces = g.pieces()
    if pieces is UNKNOWN or which >= len(pieces.value):
        print("  no such piece")
        return 0
    anchor = sorted(pieces.value[which][1])[0]
    deltas = {v: k for k, v in dw.deltas_of(g).items()}
    action = deltas.get({"right": (0, 1), "left": (0, -1),
                         "up": (-1, 0), "down": (1, 0)}[step])
    if action is None:
        print(f"  no measured action for {step}")
        return 0

    w.click(anchor, g)
    w.act(action, g)
    w.act(5, g)
    _report(g, f"piece {which} anchored {anchor} moved {step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
