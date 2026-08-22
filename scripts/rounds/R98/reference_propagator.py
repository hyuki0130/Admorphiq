"""R98 reference propagator — the hypothesis IS the simulator.

The FlowDeflection family's central design claim is that the transition model is
not a description of the simulator, it *is* the simulator: the response table the
model selects determines the predicted trajectory, so a wrong table yields a plan
the live spill falsifies. This module is that propagator, parameterized by the
response table, plus the frame-only board reader it runs on.

It stays under ``scripts/rounds/R98/`` while the contract is unfrozen; it is the
reference implementation that ``hypothesis_select`` will carry once the contract
freezes, and the certification scripts import it rather than re-deriving it.

The board reader classifies cells by appearance. That is a dev-time certification
shortcut, not the runtime grounding contract -- the runtime must earn these
classes from probes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

Cell = tuple[int, int]
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


@dataclass
class Board:
    """A frame-only reading of one layout."""

    piece_cells: frozenset[Cell]
    sinks: tuple[frozenset[Cell], ...]
    hazard_cells: frozenset[Cell]
    emitter_cells: frozenset[Cell]
    standing_flow: frozenset[Cell]

    def sink_of(self, cell: Cell) -> int | None:
        for i, s in enumerate(self.sinks):
            if cell in s:
                return i
        return None

    def moved(self, dr: int, dc: int) -> "Board":
        return replace(
            self,
            piece_cells=frozenset((r + dr, c + dc) for (r, c) in self.piece_cells),
        )


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
    """Classify the pristine change-phase board into entity classes."""
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
    )


@dataclass
class Prediction:
    frontier: list[list[Cell]]
    satisfied: set[int]
    fatal: bool
    wins: bool


def _in_bounds(cell: Cell) -> bool:
    r, c = cell
    return 0 <= r < GRID and 0 <= c < GRID


def predict(board: Board, table: ResponseTable, max_ticks: int = 80) -> Prediction:
    """Run the spill to a fixpoint under ``table`` and return the trajectory."""
    down = (1, 0)
    occupied: set[Cell] = set(board.standing_flow)
    active: list[tuple[Cell, tuple[int, int]]] = [(c, down) for c in board.standing_flow]
    for (r, c) in sorted(board.emitter_cells):
        below = (r + 1, c)
        if _in_bounds(below) and below not in occupied:
            occupied.add(below)
            active.append((below, down))

    satisfied: set[int] = set()
    fatal = False
    frontier: list[list[Cell]] = [sorted(occupied)]
    piece_cols = sorted({c for (_, c) in board.piece_cells}) or [0]

    for _ in range(max_ticks):
        if not active:
            break
        nxt: list[tuple[Cell, tuple[int, int]]] = []
        born: list[Cell] = []

        def spawn(cell: Cell, direction: tuple[int, int]) -> None:
            if not _in_bounds(cell) or cell in occupied:
                return
            occupied.add(cell)
            born.append(cell)
            nxt.append((cell, direction))

        for (r, c), (dr, dc) in active:
            ahead = (r + dr, c + dc)
            flanks = ((r - dc, c - dr), (r + dc, c + dr))

            if not _in_bounds(ahead) or ahead in board.hazard_cells:
                if ahead in board.hazard_cells:
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
                    targets = ((r, piece_cols[0] - 1), (r, piece_cols[-1] + 1))
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
    return Prediction(frontier=frontier, satisfied=satisfied, fatal=fatal, wins=wins)
