"""R98 dev-time board reader for the certification scripts.

The mechanics live in ``admorphiq.hypothesis_select.propagate_flow`` — there is
exactly ONE implementation, and this module only adds the colour-reading fixture
the certification scripts need to build a board straight from a frame. Classifying
cells by appearance is a dev-time shortcut for certification; the runtime earns
these classes from probes via ``grounding_flow``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from admorphiq.hypothesis_select.propagate_flow import (  # noqa: E402
    ORACLE,
    Board,
    Cell,
    Prediction,
    ResponseTable,
    predict,
)

SCALE = 4
GRID = 16

BACKGROUND = 12
EMITTER = 4
FLOW = 6
PIECE_IDLE = 8
PIECE_SELECTED = 9
SINK = 11
SINK_SATISFIED = 13
HAZARD = 1

__all__ = ["ORACLE", "Board", "Cell", "Prediction", "ResponseTable", "predict", "read_board",
           "SCALE", "GRID"]


def _components(cells: set[Cell]) -> list[frozenset[Cell]]:
    """4-connected components; sinks are separate entities even when close."""
    out: list[frozenset[Cell]] = []
    todo = set(cells)
    while todo:
        seed = todo.pop()
        comp = {seed}
        stack = [seed]
        while stack:
            r, c = stack.pop()
            for n in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if n in todo:
                    todo.remove(n)
                    comp.add(n)
                    stack.append(n)
        out.append(frozenset(comp))
    return sorted(out, key=lambda s: min(s))


def read_board(frame_layer) -> Board:
    """Classify a pristine change-phase frame into the entity classes the pure
    propagator takes as input."""
    by_colour: dict[int, set[Cell]] = {}
    for r in range(GRID):
        for c in range(GRID):
            v = frame_layer[r * SCALE + SCALE // 2][c * SCALE + SCALE // 2]
            by_colour.setdefault(v, set()).add((r, c))

    piece = by_colour.get(PIECE_SELECTED, set()) | by_colour.get(PIECE_IDLE, set())
    sink_cells = by_colour.get(SINK, set()) | by_colour.get(SINK_SATISFIED, set())
    return Board(
        piece_cells=frozenset(piece),
        sinks=tuple(_components(sink_cells)),
        hazard_cells=frozenset(by_colour.get(HAZARD, set())),
        emitter_cells=frozenset(by_colour.get(EMITTER, set())),
        standing_flow=frozenset(by_colour.get(FLOW, set())),
        size=GRID,
    )
