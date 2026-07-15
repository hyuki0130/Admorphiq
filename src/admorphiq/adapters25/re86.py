"""script25 quarantined adapter: RE86 (delivery / colour-assignment family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/RE86.md`` (read for reference, not imported) records RE86 as
a brittle 6/8 solve that read three sprite tags — ``vzuwsebntu`` (targets),
``vfaeucgcyr`` (movables), ``ozhohpbjxz`` (changers) — with every generic
attempt at 0/8. Reading the game source (dev-time only; this adapter acts
frame-only) plus live probes (``scratchpad`` traces, offline) decode what those
tags track and their frame-observable equivalents:

**Mechanic (measured — roles/hypothesis declared HERE, not in any kernel)**:
RE86 is a delivery + colour-assignment puzzle.

- ``available_actions`` = ``[1,2,3,4,5]``, no ACTION6. ACTION1-4 move the
  SELECTED movable one 3px cell (``ilmaurgzng=3``); the sign per action is
  MEASURED. **ACTION5 CYCLES the selection** to the next movable (its centre
  is marked with the selection colour ``0``). Measured on level 1: exactly TWO
  movables, selection toggling between them.
- Movables (``vfaeucgcyr``) are shaped sprites (a cross/bar) drawn in a colour
  (measured colours 9 and 11 on level 1); their centre carries the selection
  marker (colour 0) when active.
- Targets (``vzuwsebntu``) are static colour-bordered boxes (a colour-4 border
  around a coloured centre) painted on a backdrop canvas. The win check
  (``cdjxpfqest`` in source) stamps every movable onto that canvas and requires
  each target's coloured pixels to be covered by a MATCHING-colour movable
  pixel at the target's position — a bipartite colour assignment scored by
  position (typology T3 variant).
- Changers (``ozhohpbjxz``) are static coloured lines; a movable of a different
  colour that overlaps one is RECOLOURED to the changer's colour (animated,
  spreading across the movable over several steps). This is how a movable is
  re-coloured to match a target it doesn't already match.

**This adapter's approach — covering-offset delivery** (composing the
codex-intended primitives): locate the active movable by its selection marker
(colour 0); recover its FULL shape as the marker-anchored, colour-4/background-
gap-bridged connected component (``find_regions(gap=1)`` — this reunites the
cross the changer line would otherwise split); LOCK the target-box cells per
colour once while the scene is clean; and use ``kernels.covering_offsets`` for a
single translation of the movable's shape onto its matching-colour targets. Step
toward the nearest offset with MEASURED move directions, switching axis on a
walled move, and — crucially — **never disturb a movable already at offset
(0,0)** (both movables must be covered simultaneously to win), cycling ACTION5
to work the other one instead.

**Measured coverage**: on the local env (``re86-8af5384d``) this clears
**1/8** (``game_score`` 0.028) — the FIRST generic clear of this game (baseline:
brittle 6/8 by sprite-tag read, prior generic 0/8). Level 1 solves cleanly: the
colour-9 cross covers its four targets, the colour-11 cross covers its four, and
the engine wins once both are placed.

**BANKED wall — level 2 (mechanism READ from a gold replay; frame-only
covering blocked by an invisible movable)**: ``_target_boxes`` now detects L2's
gate targets (12 colour-9 + 12 colour-11 cells) and ``_active_movable`` is
anchored on the marker's neighbouring body pixel (fixing a phantom-colour read).
Two hypotheses were tested and killed by observation: (a) RECOLOUR — driving the
surplus movable across the colour-9 changer line for 40 moves left its colour
unchanged; (b) "cover a colour-12 target" — there are none. Then a GOLD-REPLAY
divergence analysis (the brittle solver's recorded trace, ``data/traces/re86.npz``,
which replays 6/6 on this env — v1↔v2 geometry is identical) read the true
mechanism off the winning frames:
  - L2 has THREE movables (colours 9, 12, 13). The colour-9 movable covers the
    colour-9 gates; the SURPLUS colour-12 AND colour-13 movables together cover
    the COLOUR-11 gate region (at the win frame those gates render colour 12/13,
    not 11). So a colour-11 "target" is a COMPOUND gate satisfied by two
    differently-coloured movables — not a single colour match.
  - Gold works each movable via ACTION5 selection cycling, moving each to its
    covering spot. NO recolour anywhere.
  - The colour-13 movable is INVISIBLE EVEN WHEN SELECTED (only its marker
    shows; its body renders as background), so it has NO frame-observable shape
    for ``covering_offsets``.
**Compound-covering implementation plan ALSO falsified (validate-before-build)**:
before building, the covering-offset partition was tested and does NOT hold —
covering_offsets of a surplus colour-12 movable onto the colour-11 gates (or any
top/bottom subset) returns a size-5/6 set (no single-offset cover), and in the
gold play the colour-12 movable moves DOWN to row 48, AWAY from the colour-11
gates (rows 2-18). Per-movable gold journeys (from ``data/traces/re86.npz``):
colour-9 movable → colour-9 gates; the INVISIBLE colour-13 movable → (12,21),
which is the piece that actually covers the colour-11 gate region; the colour-12
movable → row 48 (a target this adapter cannot locate — no colour-12 gate
exists). So the real assignment is NOT "the 12+13 pair covers colour-11 by
covering-offset"; it is per-piece and involves an invisible mover plus a
colour-12 target off the gate grid.
**REOPEN** (precise ground truth now recorded): (a) footprint-probe the invisible
colour-13 movable — drive its marker and read which cells recolour, to recover
its shape, then cover the colour-11 gates; (b) locate the colour-12 movable's
own target (its gold end is row 48; find what it satisfies there); (c) keep the
covering spine for the visible colour-9 movable. This is a genuine multi-piece
build, not a covering-offset extension. No hardcoded coordinates/palettes/
sequences were added; the adapter runs to budget. The working L1 solve, three
falsified hypotheses (recolour / colour-12-target / compound-covering), and the
gold-read per-movable journeys are the deliverables.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments movables / target boxes.
  - :func:`admorphiq.kernels.covering_offsets` finds a translation of the
    active movable's shape onto its matching-colour target cells.
"""

from __future__ import annotations

from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    available_action_ids,
    canonical_layer,
    has_frame,
    most_common_color,
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import covering_offsets, find_regions

GAME_ID = "re86"

Cell = tuple[int, int]
Region = dict[str, Any]

_GIVEUP_DEFAULT = 4000
_SELECTION_COLOR = 0
_BORDER_COLOR = 4
# Move pitch in pixels (measured, ilmaurgzng=3). Only quantises a delta into a
# step count — not a coordinate.
_CELL_PX = 3


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


def _target_boxes(grid: tuple[tuple[int, ...], ...]) -> list[Cell]:
    """Cells of colour-bordered target gates: a non-border, non-background,
    non-selection pixel flanked by the border colour on a PAIR of opposite
    sides — left+right OR top+bottom. This covers both the 3×3 fully-bordered
    box (satisfies either pair) and the taller gate bars used on deeper levels
    (a colour column flanked left/right by the border), which the all-four-
    sides rule missed. Returns ``(row, col)`` per gate cell (the required
    colour is ``grid[row][col]``). Frame-only, no sprite-tag read."""
    boxes: list[Cell] = []
    h = len(grid)
    w = len(grid[0]) if grid else 0
    b = _BORDER_COLOR
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            v = grid[r][c]
            if v in (b, _SELECTION_COLOR):
                continue
            horizontal = grid[r][c - 1] == b and grid[r][c + 1] == b
            vertical = grid[r - 1][c] == b and grid[r + 1][c] == b
            if horizontal or vertical:
                boxes.append((r, c))
    return boxes


class Adapter(GameAdapter):
    """Covering-offset greedy delivery composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # Measured (dr_sign, dc_sign) per move action, like m0r0's dir_map.
        self._dir: dict[int, Cell] = {}
        self._pending_action: int | None = None
        self._pending_marker: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None
        # Rotates through selection cycling when the active movable has no
        # reachable covering move, so both movables get worked.
        self._stall = 0
        # Target-box cells grouped by required colour, LOCKED once at level
        # start while the scene is clean — a movable occludes the target boxes
        # as it arrives on them, so re-reading targets live destabilises the
        # covering offset near the goal (measured: the offset stops shrinking
        # cleanly a couple of cells short). Targets never move, so the locked
        # set stays valid all level (same discipline as m0r0/cn04).
        self._targets_by_color: dict[int, list[Cell]] = {}
        self._targets_locked = False
        # (marker_cell, action) pairs that produced no displacement (blocked by
        # a wall/edge) — the covering planner routes around them by axis.
        self._blocked: set[tuple[Cell, int]] = set()

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._pending_action = None
            self._prev_grid = None
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_action = None
            self._prev_grid = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        self._observe(grid)

        simple_ids, _a6 = available_action_ids(latest_frame)
        move_ids = [a for a in simple_ids if a in (1, 2, 3, 4)]
        action = self._decide(grid, move_ids, 5 in simple_ids)
        self._prev_grid = grid
        return action

    # ── bookkeeping ─────────────────────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._dir = {}
        self._pending_action = None
        self._pending_marker = None
        self._prev_grid = None
        self._stall = 0
        self._targets_by_color = {}
        self._targets_locked = False
        self._blocked = set()

    def _lock_targets(self, grid: tuple[tuple[int, ...], ...]) -> None:
        by_color: dict[int, list[Cell]] = {}
        for r, c in _target_boxes(grid):
            by_color.setdefault(grid[r][c], []).append((r, c))
        self._targets_by_color = by_color
        self._targets_locked = True

    def _observe(self, grid: tuple[tuple[int, ...], ...]) -> None:
        action = self._pending_action
        before_marker = self._pending_marker
        self._pending_action = None
        self._pending_marker = None
        if action is None or action not in (1, 2, 3, 4) or before_marker is None:
            return
        marker = self._marker(grid)
        if marker is None:
            return
        dr = marker[0] - before_marker[0]
        dc = marker[1] - before_marker[1]
        if dr or dc:
            self._dir[action] = (_sign(dr), _sign(dc))
        else:
            # The marker did not move: this action is blocked (a wall / edge)
            # from ``before_marker``. Remember it so the covering planner
            # switches to the other axis instead of hammering the wall.
            self._blocked.add((before_marker, action))

    # ── perception ──────────────────────────────────────────────────────

    def _marker(self, grid: tuple[tuple[int, ...], ...]) -> Cell | None:
        h = len(grid)
        w = len(grid[0]) if grid else 0
        for r in range(h):
            for c in range(w):
                if grid[r][c] == _SELECTION_COLOR:
                    return (r, c)
        return None

    def _active_movable(self, grid: tuple[tuple[int, ...], ...], marker: Cell) -> tuple[int, frozenset[Cell]] | None:
        """The active movable's colour and full cell set: the colour-4-gap-
        bridged connected component whose body TOUCHES the selection marker.

        Anchored on a body pixel ADJACENT to the marker, not merely on bbox
        containment — a large sparse cross's bbox can enclose the marker of a
        DIFFERENT movable, which made the colour read as a phantom (a colour not
        even present in the frame). The region owning one of the marker's own
        neighbours is unambiguously the piece the marker sits inside."""
        bg = most_common_color(grid)
        regions = find_regions(grid, background=(bg, _BORDER_COLOR, _SELECTION_COLOR), gap=1)
        neighbours = {(marker[0] + dr, marker[1] + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
        touching = [reg for reg in regions if reg["cells"] & neighbours]
        if touching:
            reg = max(touching, key=lambda r: r["size"])
            return (reg["color"], reg["cells"])  # type: ignore[return-value]
        return None

    # ── planning ────────────────────────────────────────────────────────

    def _decide(self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], can_cycle: bool) -> GameAction:
        if not move_ids:
            return reset_action()
        if not self._targets_locked:
            self._lock_targets(grid)
        marker = self._marker(grid)
        if marker is None:
            return self._probe(marker, move_ids)
        active = self._active_movable(grid, marker)
        if active is None:
            return self._probe(marker, move_ids)
        color, shape = active
        targets = self._targets_by_color.get(color, [])
        if not targets:
            # This movable matches no locked target — cycle to the other one.
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)

        offsets = covering_offsets(list(shape), targets)
        if not offsets:
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)
        # The single nearest covering translation of the movable's shape onto
        # its locked targets (a full solve reaches offset (0, 0) — the shape
        # then covers every same-colour target).
        dr, dc = min(offsets, key=lambda o: abs(o[0]) + abs(o[1]))
        if dr == 0 and dc == 0:
            # This movable is placed. NEVER disturb it (a move would un-cover
            # it and the two movables must be covered simultaneously to win) —
            # cycle to work the other movable; when both are placed the engine
            # wins.
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)

        move = self._covering_move(dr, dc, marker, move_ids)
        if move is not None:
            return move
        # Every covering axis is blocked or unmeasured: probe an unmeasured
        # move (to learn a direction) else cycle to the other movable.
        want_axes = [(_sign(dr), 0)] if dr else []
        want_axes += [(0, _sign(dc))] if dc else []
        if any(self._move_for(w, move_ids) is None for w in want_axes):
            return self._probe(marker, move_ids)
        return simple_action(5) if can_cycle else self._probe(marker, move_ids)

    def _covering_move(self, dr: int, dc: int, marker: Cell, move_ids: list[int]) -> GameAction | None:
        """The measured move that reduces the larger covering axis and is not
        known-blocked from ``marker``; falls back to the other axis when the
        preferred one is walled."""
        candidates: list[tuple[int, Cell]] = []
        if dr:
            candidates.append((abs(dr), (_sign(dr), 0)))
        if dc:
            candidates.append((abs(dc), (0, _sign(dc))))
        candidates.sort(reverse=True)
        for _mag, want in candidates:
            move = self._move_for(want, move_ids)
            if move is not None and (marker, move) not in self._blocked:
                return self._issue(move, marker)
        return None

    def _move_for(self, want: Cell, move_ids: list[int]) -> int | None:
        for action, sign in self._dir.items():
            if action in move_ids and sign == want:
                return action
        return None

    def _issue(self, action: int, marker: Cell | None) -> GameAction:
        self._pending_action = action
        self._pending_marker = marker
        return simple_action(action)

    def _probe(self, marker: Cell | None, move_ids: list[int]) -> GameAction:
        untried = [a for a in move_ids if a not in self._dir]
        action = untried[0] if untried else move_ids[0]
        return self._issue(action, marker)
