"""R98 STEP (iv-a): the flow propagator — the hypothesis run as a simulator.

The FlowDeflection family's design claim is that the transition model is not a
description of the simulator, it IS the simulator: the response table the model
selects determines the predicted trajectory, so a wrong table yields a plan the
live spill falsifies. That makes this module load-bearing twice over — it is the
verifier's consistency check AND the compiler's search oracle.

It is PURE: a board is passed in as explicit cell sets that grounding measured,
never read from colours. The colour-reading fixture used by the R98 certification
scripts lives in ``scripts/rounds/R98/reference_propagator.py`` and imports this
module, so there is exactly one implementation of the mechanics.

Measured faithfulness: with the oracle response table this reproduces the engine's
outcome on every reachable placement of the criterion level and its CELL-EXACT
trajectory on both probe placements (``scripts/rounds/R98/gated_enums.txt``).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

Cell = tuple[int, int]


@dataclass(frozen=True)
class ResponseTable:
    """The model-selected semantics: one closed choice per encountered class."""

    piece_spawn: str = "empty_flanks_only"     # | both_flanks | none
    piece_direction: str = "preserved"         # | outward_turned
    piece_propagation: str = "cellwise_iterative"  # | edge_teleport
    sink_predicate: str = "same_sink_flanks"   # | contact
    sink_miss: str = "spread_like_piece"       # | stop | absorb
    hazard: str = "terminate_fatal"            # | terminate_local | pass_through
    own_flow: str = "advance_front"            # | overwrite | terminate
    boundary: str = "terminate_harmless"       # | reflect


ORACLE = ResponseTable()


@dataclass(frozen=True)
class Board:
    """One layout, as explicit cell sets. Every field is grounding output."""

    pieces: tuple[frozenset[Cell], ...]
    sinks: tuple[frozenset[Cell], ...]
    hazard_cells: frozenset[Cell]
    emitter_cells: frozenset[Cell]
    standing_flow: frozenset[Cell]
    size: int
    # Measured, never assumed. A board may run its flow in any direction — the
    # criterion level happens to run it downward and the next one runs it upward,
    # so a hardcoded default silently mispredicts every step on half of them.
    direction: Cell = (1, 0)

    @property
    def piece_cells(self) -> frozenset[Cell]:
        """Every cell occupied by any piece — what the flow actually collides with."""
        return frozenset().union(*self.pieces) if self.pieces else frozenset()

    def piece_at(self, cell: Cell) -> int | None:
        for i, piece in enumerate(self.pieces):
            if cell in piece:
                return i
        return None

    def sink_of(self, cell: Cell) -> int | None:
        for i, s in enumerate(self.sinks):
            if cell in s:
                return i
        return None

    def moved(self, dr: int, dc: int, index: int = 0) -> "Board":
        """The board with ONE piece translated. ``index`` selects it; the default
        keeps the single-piece call sites unchanged."""
        if not self.pieces:
            return self
        shifted = frozenset((r + dr, c + dc) for (r, c) in self.pieces[index])
        return replace(
            self, pieces=self.pieces[:index] + (shifted,) + self.pieces[index + 1:]
        )

    def with_offsets(self, offsets: tuple[Cell, ...]) -> "Board":
        """The board with every piece translated by its own offset."""
        return replace(
            self,
            pieces=tuple(
                frozenset((r + dr, c + dc) for (r, c) in piece)
                for piece, (dr, dc) in zip(self.pieces, offsets)
            ),
        )


@dataclass
class Prediction:
    frontier: list[list[Cell]]
    satisfied: set[int]
    fatal: bool
    wins: bool
    # How many streams ended on a barrier. ``fatal`` is the objective's question and
    # is boolean; this is the GRADED version, and a search needs it: on a board where
    # no single placement reaches zero contacts, a boolean gives every candidate the
    # same score and the ranking carries no information at all.
    barrier_hits: int = 0


def _in_bounds(cell: Cell, size: int) -> bool:
    r, c = cell
    return 0 <= r < size and 0 <= c < size


def predict(board: Board, table: ResponseTable, max_ticks: int = 80) -> Prediction:
    """Run the spill to a fixpoint under ``table`` and return the trajectory."""
    heading = board.direction
    occupied: set[Cell] = set(board.standing_flow)
    active: list[tuple[Cell, tuple[int, int]]] = [(c, heading) for c in board.standing_flow]
    for (r, c) in sorted(board.emitter_cells):
        below = (r + heading[0], c + heading[1])
        if _in_bounds(below, board.size) and below not in occupied:
            occupied.add(below)
            active.append((below, heading))

    satisfied: set[int] = set()
    fatal = False
    barrier_hits = 0
    frontier: list[list[Cell]] = [sorted(occupied)]
    def _piece_span(cell: Cell) -> list[int]:
        index = board.piece_at(cell)
        piece = board.pieces[index] if index is not None else board.piece_cells
        return sorted({c for (_, c) in piece}) or [0]

    for _ in range(max_ticks):
        if not active:
            break
        nxt: list[tuple[Cell, tuple[int, int]]] = []
        born: list[Cell] = []

        blocked = board.piece_cells | {c for s in board.sinks for c in s} | board.hazard_cells

        def spawn(cell: Cell, direction: tuple[int, int]) -> None:
            # "Empty" means empty of EVERYTHING, not just of flow. Spreading into a
            # cell that a piece or a target already occupies invents flow the engine
            # never creates, and the error compounds from that tick onward.
            if not _in_bounds(cell, board.size) or cell in occupied or cell in blocked:
                return
            occupied.add(cell)
            born.append(cell)
            nxt.append((cell, direction))

        for (r, c), (dr, dc) in active:
            ahead = (r + dr, c + dc)
            flanks = ((r - dc, c - dr), (r + dc, c + dr))

            if not _in_bounds(ahead, board.size) or ahead in board.hazard_cells:
                if ahead in board.hazard_cells:
                    barrier_hits += 1
                    if table.hazard == "terminate_fatal":
                        fatal = True
                    elif table.hazard == "pass_through":
                        spawn(ahead, (dr, dc))
                    # terminate_local: the droplet just dies
                elif table.boundary == "reflect":
                    spawn((r - dr, c - dc), (-dr, -dc))
                continue

            sink_idx = board.sink_of(ahead)
            if sink_idx is not None:
                same = all(board.sink_of(f) == sink_idx for f in flanks)
                hit = same if table.sink_predicate == "same_sink_flanks" else True
                if hit:
                    satisfied.add(sink_idx)
                    continue
                if table.sink_miss == "spread_like_piece":
                    for f in flanks:
                        spawn(f, (dr, dc))
                # stop / absorb: the droplet dies here
                continue

            if ahead in board.piece_cells:
                if table.piece_spawn == "none":
                    continue
                if table.piece_propagation == "edge_teleport":
                    span = _piece_span(ahead)
                    targets = ((r, span[0] - 1), (r, span[-1] + 1))
                else:
                    targets = flanks
                for i, f in enumerate(targets):
                    if table.piece_direction == "outward_turned":
                        direction = (0, -1) if i == 0 else (0, 1)
                    else:
                        direction = (dr, dc)
                    if table.piece_spawn == "both_flanks" and f in occupied:
                        # re-activate rather than skip
                        nxt.append((f, direction))
                    else:
                        spawn(f, direction)
                continue

            if ahead in occupied:
                if table.own_flow == "advance_front":
                    nxt.append((ahead, (dr, dc)))
                elif table.own_flow == "overwrite":
                    nxt.append((ahead, (dr, dc)))
                # terminate: the droplet dies
                continue

            spawn(ahead, (dr, dc))

        frontier.append(sorted(born))
        # a droplet re-activated on an occupied cell must not loop forever
        seen: set[tuple[Cell, tuple[int, int]]] = set()
        active = [s for s in nxt if not (s in seen or seen.add(s))]

    wins = len(satisfied) == len(board.sinks) and not fatal
    return Prediction(
        frontier=frontier,
        satisfied=satisfied,
        fatal=fatal,
        wins=wins,
        barrier_hits=barrier_hits,
    )
