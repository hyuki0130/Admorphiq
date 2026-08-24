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

Reading the table
-----------------
A walk is re-detected from each of its own cells, so one four-cell walk shows up as
four rows of decreasing length. That is deliberate — it costs nothing and it makes a
walk that behaves differently partway visible — but it means the ROW COUNT is not an
event count.

Expected feedback
-----------------
A table of (extent, support pattern, fate) per side. A side that walks while supported
and falls the moment it is not needs no rule beyond gravity. A side that STOPS on a
SUPPORTED cell is what a new rule has to explain.
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


def _what(board, cell) -> str:
    """What occupies a cell, by kind — the vocabulary the decision table is cut on."""
    if not (0 <= cell[0] < board.size and 0 <= cell[1] < board.size):
        return "off-board"
    if board.sink_of(cell) is not None:
        return "target"
    if cell in board.absorber_cells:
        return "absorber"
    if cell in board.piece_cells:
        return "piece"
    if cell in board.hazard_cells:
        return "hazard"
    return "empty"


def decision_table() -> int:
    """Every point where a walking droplet could take one more lateral step, and
    whether it did — cut by what it is standing on and what the next cell stands on.

    Purpose: the terminal-cell view says where walks END, which conflates a walk that
    could not continue with one that chose not to. This looks at the CHOICE instead,
    so a property that decides it would show as a clean split.

    Expected feedback: a row that is all STEPPED or all stopped is a rule. A row with
    both is a decision the property does not explain, and the property is eliminated.
    """
    counts: dict[tuple, int] = {}
    distance: dict[tuple, int] = {}
    for path in _captures():
        with open(path) as f:
            payload = json.load(f)
        board = _union_board(_board(payload), payload)
        dr, dc = board.direction
        layers = [{tuple(c) for c in layer} for layer in payload["observed"]]
        seen = set()
        for i in range(1, len(layers)):
            for cell in layers[i - 1]:
                for step in ((-dc, -dr), (dc, dr)):
                    first = (cell[0] + step[0], cell[1] + step[1])
                    if first not in layers[i]:
                        continue
                    run = _walk(layers[i:], first, step, board)
                    if not run or (path.stem, run[-1], step) in seen:
                        continue
                    seen.add((path.stem, run[-1], step))
                    for j, c in enumerate(run):
                        under = _what(board, (c[0] + dr, c[1] + dc))
                        nxt = (c[0] + step[0], c[1] + step[1])
                        if under == "empty" or _what(board, nxt) != "empty":
                            continue
                        under_next = _what(board, (nxt[0] + dr, nxt[1] + dc))
                        took = "STEPPED" if j + 1 < len(run) else "stopped"
                        key = (f"on {under}", f"next over {under_next}", took)
                        counts[key] = counts.get(key, 0) + 1
                        if under_next == "empty":
                            d = (f"had walked {j}", took)
                            distance[d] = distance.get(d, 0) + 1
    print(f"{'standing on':14s} {'the next cell stands over':26s} {'':8s} {'n':>4}")
    for key in sorted(counts):
        print(f"{key[0]:14s} {key[1]:26s} {key[2]:8s} {counts[key]:>4}")
    print("\nthe step OFF the end, by how far the walk had already gone")
    for key in sorted(distance):
        print(f"  {key[0]:16s} {key[1]:8s} {distance[key]:>4}")
    return 0


def events() -> int:
    """DISTINCT step-off events, as opposed to instances of them.

    Purpose: the captures are sibling boards of one level, so the same physical event
    reappears on each. Counting instances makes the evidence look an order of magnitude
    richer than it is, and two rules in a row were fitted to that inflated count.

    Expected feedback: an event is (cell, walk direction); the board count beside it is
    how many captures show it. A handful of events spread across many boards means the
    question cannot be settled from these captures, whatever the instance count says."""
    found: dict[tuple, set] = {}
    for path in _captures():
        with open(path) as f:
            payload = json.load(f)
        board = _union_board(_board(payload), payload)
        dr, dc = board.direction
        layers = [{tuple(c) for c in layer} for layer in payload["observed"]]
        seen = set()
        for i in range(1, len(layers)):
            for cell in layers[i - 1]:
                for step in ((-dc, -dr), (dc, dr)):
                    first = (cell[0] + step[0], cell[1] + step[1])
                    if first not in layers[i]:
                        continue
                    run = _walk(layers[i:], first, step, board)
                    if not run or (path.stem, run[-1], step) in seen:
                        continue
                    seen.add((path.stem, run[-1], step))
                    for j, c in enumerate(run):
                        under = (c[0] + dr, c[1] + dc)
                        nxt = (c[0] + step[0], c[1] + step[1])
                        if _what(board, under) == "empty" or _what(board, nxt) != "empty":
                            continue
                        if _what(board, (nxt[0] + dr, nxt[1] + dc)) != "empty":
                            continue
                        took = "STEPPED" if j + 1 < len(run) else "stopped"
                        found.setdefault((took, c, step), set()).add(path.stem)
    print(f"{'outcome':8s} {'at cell':10s} {'walking':10s} {'boards':>7s}  levels")
    for key in sorted(found, key=lambda k: (k[0], -len(found[k]))):
        boards = found[key]
        levels = sorted({"idx0" if "idx0" in b else "idx3" for b in boards})
        print(f"{key[0]:8s} {str(key[1]):10s} {str(key[2]):10s} "
              f"{len(boards):>7d}  {','.join(levels)}")
    stepped = sum(1 for k in found if k[0] == "STEPPED")
    stopped = sum(1 for k in found if k[0] == "stopped")
    print(f"\nDISTINCT events: {stepped} stepped, {stopped} stopped")
    return 0


def main() -> int:
    print(f"{'board':6s} {'landing':9s} {'left':29s} {'right':29s}")
    print("  (a side with 0 steps did not appear on the layer after the landing)")
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
                if left not in layers[i] and right not in layers[i]:
                    continue
                # BOTH-flank detection was too narrow: it missed every event whose two
                # sides do not appear on the same layer, and those were exactly the
                # boards that refuted the inherited-walk rule. One flank is enough to
                # call it a spread; the other side is then reported as it is, empty
                # included.
                lw = _walk(layers[i:], left, (-dc, -dr), board)
                rw = _walk(layers[i:], right, (dc, dr), board)
                ls = "".join("#" if _supported(board, c) else "." for c in lw)
                rs = "".join("#" if _supported(board, c) else "." for c in rw)
                print(f"{path.stem.split('_')[-1]:6s} {str(cell):9s} "
                      f"{len(lw)} {ls:7s} {_fate(layers[i:], lw, board):19s} "
                      f"{len(rw)} {rs:7s} {_fate(layers[i:], rw, board)}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--events":
        raise SystemExit(events())
    if len(sys.argv) > 1 and sys.argv[1] == "--decision":
        raise SystemExit(decision_table())
    raise SystemExit(main())
