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

Expected feedback
-----------------
A table of (left extent, right extent) with the support pattern of each. If extents
track support — a walk continuing while blocked and ending where it is not — the
rule is readable off the table. If two events with identical support disagree, the
rule is not about support and the table says so before any code is written.
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


def main() -> int:
    print(f"{'board':6s} {'landing':9s} {'left':26s} {'right':26s}")
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
                      f"{len(lw)} step(s) {ls:15s} {len(rw)} step(s) {rs:15s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
