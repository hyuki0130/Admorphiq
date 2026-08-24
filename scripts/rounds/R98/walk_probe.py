"""R98 walk probe — how far does the ENGINE walk a blocked droplet, each way?

Purpose
-------
The bench residual is a lateral halo: the model spawns on both flanks, which is
measured correct, so the disagreement is in how far each side then travels. The
round has one hand-read example of the asymmetry — four steps one way, one the
other, on the same board — and a rule cannot be written from one board.

This reads the OBSERVED trajectories instead. For every step where two cells appear
either side of the previous cell, it follows each side as far as the observation
carries it and reports the extent together with what the walked cells were standing
on, which is the property the candidate rules turn on.

A straight lateral run is only half the story: a side that shows ONE cell may have
fallen from it rather than stopped there, and those are different mechanisms. So each
side is also reported as `fell` or `STOPPED`, by asking whether its last cell has a
descendant along the flow anywhere later in the observation.

Expected feedback
-----------------
A table of (extent, support pattern, fate) per side. A side that walks while supported
and falls the moment it is not needs no rule beyond gravity. A side that STOPS on a
SUPPORTED cell is the anomaly, and it is the only thing a new rule has to explain.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rule_bench import _board, _captures, _union_board  # noqa: E402


def _supported(board, cell) -> bool:
    """Is the cell one step along the flow from ``cell`` blocked?"""
    dr, dc = board.direction
    below = (cell[0] + dr, cell[1] + dc)
    if not (0 <= below[0] < board.size and 0 <= below[1] < board.size):
        return True
    return (below in board.piece_cells or below in board.absorber_cells
            or below in board.hazard_cells or board.sink_of(below) is not None)


def _walk(layers: list[set], start, step, board) -> list:
    """Follow one side of a spread as far as consecutive layers carry it."""
    out = []
    cell = start
    for i in range(len(layers)):
        if cell in layers[i]:
            out.append(cell)
            cell = (cell[0] + step[0], cell[1] + step[1])
    return out


def _fate(layers: list[set], run: list, board) -> str:
    """Did the side FALL from its last cell, or stop there?

    A single-cell side reads the same either way in a lateral run, and the two are
    different mechanisms: falling needs no rule beyond gravity, stopping does."""
    if not run:
        return "-"
    dr, dc = board.direction
    below = (run[-1][0] + dr, run[-1][1] + dc)
    fell = any(below in layer for layer in layers)
    if fell:
        return "fell"
    return "STOPPED on support" if _supported(board, run[-1]) else "stopped"


def main() -> int:
    print(f"{'board':6s} {'landing':9s} {'left':29s} {'right':29s}")
    for path in _captures():
        with open(path) as f:
            payload = json.load(f)
        board = _union_board(_board(payload), payload)
        dr, dc = board.direction
        layers = [{tuple(c) for c in layer} for layer in payload["observed"]]
        for i in range(1, len(layers)):
            for cell in layers[i - 1]:
                left = (cell[0] - dc, cell[1] - dr)
                right = (cell[0] + dc, cell[1] + dr)
                if left not in layers[i] or right not in layers[i]:
                    continue
                lw = _walk(layers[i:], left, (-dc, -dr), board)
                rw = _walk(layers[i:], right, (dc, dr), board)
                ls = "".join("#" if _supported(board, c) else "." for c in lw)
                rs = "".join("#" if _supported(board, c) else "." for c in rw)
                print(f"{path.stem.split('_')[-1]:6s} {str(cell):9s} "
                      f"{len(lw)} {ls:7s} {_fate(layers[i:], lw, board):19s} "
                      f"{len(rw)} {rs:7s} {_fate(layers[i:], rw, board)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
