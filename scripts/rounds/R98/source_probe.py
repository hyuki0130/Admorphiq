"""R98: where does the flow ENTER, as the pieces move?

An emergence is an observation under one layout, so a plan that moves the pieces
cannot replay it. If instead a source sits at a FIXED board cell and the flow appears
past whatever covers it, then the entry is predictable for layouts never observed —
which is what planning needs.

This measures the claim directly: commit the spill under several different layouts on
the same level and record where the flow first appears each time, together with what
occupies the candidate source cells.

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
NUDGES = ((), (3,), (3, 3), (4,), (1,), (1, 1))


def _orphans(g: FlowGrounding) -> list[tuple[int, int]]:
    """Every cell the flow appears at with no flow behind or beside it — the whole
    trail, not just its first layer. These are the entries a replay has to reproduce."""
    trail = g.trajectory()
    direction = g.initial_direction()
    if trail is UNKNOWN or direction is UNKNOWN:
        return []
    dr, dc = direction.value
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []
    for layer in trail.value:
        for (r, c) in layer:
            behind = (r - dr, c - dc)
            flanks = ((r - dc, c - dr), (r + dc, c + dr))
            if behind in seen or any(f in seen for f in flanks):
                continue
            out.append((r, c))
        seen |= set(layer)
    return sorted(out)


def _entries(g: FlowGrounding) -> list[tuple[int, int]]:
    trail = g.trajectory()
    if trail is UNKNOWN:
        return []
    for layer in trail.value:
        if layer:
            return sorted(layer)
    return []


def main() -> int:
    w = dw.Walker()
    for _ in range(LEVEL):
        dw.play_level(w)

    g = FlowGrounding()
    g.observe(0, None, w.obs.frame)
    for a in (1, 1, 2, 3, 4):
        w.act(a, g)
    candidates = g.selection_candidates()
    if candidates is not UNKNOWN:
        for cell in candidates.value[:6]:
            w.click(cell, g)

    print(f"level idx{LEVEL}: entry vs layout\n")
    for nudge in NUDGES:
        for action in nudge:
            w.act(action, g)
        w.act(5, g)
        pieces = g.pieces()
        occupied = (frozenset(c for _, cells in pieces.value for c in cells)
                    if pieces is not UNKNOWN else frozenset())
        entry = _entries(g)
        print(f"  after {nudge or '(no move)'}: entry {entry} | "
              f"all orphan entries {_orphans(g)}")
        print(f"    pieces {[(sorted(c)[0], len(c)) for _, c in pieces.value]}"
              if pieces is not UNKNOWN else "    pieces UNKNOWN")
        hidden = g.hidden_sources()
        trail = g.trajectory()
        cells = {c for layer in (trail.value if trail is not UNKNOWN else ()) for c in layer}
        print(f"    hidden sources {'UNKNOWN' if hidden is UNKNOWN else sorted(hidden.value)}"
              f" | flow touching a piece: {sorted(cells & occupied)}")
        if not w.alive:
            print("  game over")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
