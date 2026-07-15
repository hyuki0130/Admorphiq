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

**This adapter's approach — covering-offset greedy delivery** (composing the
codex-intended primitives): locate the active movable by its selection marker
(colour 0), read its colour and connected shape, enumerate the matching-colour
target boxes, and use ``kernels.covering_offsets`` to find a translation of the
movable's shape that lands a movable pixel on the target cells; step toward the
nearest reachable offset with the MEASURED move directions, cycling ACTION5
between the two movables.

**Measured coverage / BANKED wall**: on the local env (``re86-8af5384d``) this
clears **0/8** (baseline: brittle 6/8, prior generic 0/8). The wall is the win
GEOMETRY, unresolved for a generic solver in the time budget:
  1. **Movable-shape isolation.** A movable shares its colour with a static
     changer LINE and with target-box centres, so ``find_regions`` splits the
     movable at the changer intersection — the extracted "shape" is a 1-wide
     bar sliver, not the full cross. A 1-wide bar cannot cover the level's four
     scattered same-colour targets in one position (``covering_offsets``
     returns a size-4 set, i.e. no single covering translation), so the greedy
     never reaches a winning configuration.
  2. **Backdrop-canvas win model.** The win check scores against a base canvas
     (``pseflysmdl``) that already paints most target boxes; which boxes are
     genuine ``vzuwsebntu`` targets vs backdrop decoration is not
     frame-separable without the tag read the brittle solver used.
**REOPEN** with (a) selection-marker-anchored movable extraction (take the
connected component the marker sits in, gap-bridging across the changer line via
``find_regions(gap=…)`` or ``track_objects`` motion, to recover the FULL cross
shape), and (b) a recolour-delivery model that routes a movable through a
changer to match, then covers each target and treats coverage as the per-target
subgoal. Both are real research increments; the mechanic decode above (movables
/ targets / changers / selection-cycle / recolour) is the banked deliverable —
the prior wiki had only the tag names. No hardcoded coordinates/palettes/
sequences were added; the adapter runs to budget as a clean 0/8 best-effort.

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
    """Centres of colour-bordered target boxes: a non-border, non-background
    pixel enclosed on all four sides by the border colour. Returns
    ``(row, col)`` per box (the colour is ``grid[row][col]``). Frame-only, no
    sprite-tag read."""
    boxes: list[Cell] = []
    h = len(grid)
    w = len(grid[0]) if grid else 0
    for r in range(1, h - 1):
        for c in range(1, w - 1):
            v = grid[r][c]
            if v in (_BORDER_COLOR, _SELECTION_COLOR):
                continue
            if (
                grid[r - 1][c] == _BORDER_COLOR
                and grid[r + 1][c] == _BORDER_COLOR
                and grid[r][c - 1] == _BORDER_COLOR
                and grid[r][c + 1] == _BORDER_COLOR
            ):
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
        """The active movable's colour and full cell set: the connected
        component (colour-4-gap-bridged so the selection-marker hole and any
        changer split don't fragment it) whose bbox contains the marker."""
        bg = most_common_color(grid)
        regions = find_regions(grid, background=(bg, _BORDER_COLOR, _SELECTION_COLOR), gap=1)
        for reg in regions:
            r0, c0, r1, c1 = reg["bbox"]
            if r0 <= marker[0] <= r1 and c0 <= marker[1] <= c1:
                return (reg["color"], reg["cells"])  # type: ignore[return-value]
        return None

    # ── planning ────────────────────────────────────────────────────────

    def _decide(self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], can_cycle: bool) -> GameAction:
        if not move_ids:
            return reset_action()
        marker = self._marker(grid)
        if marker is None:
            return self._probe(marker, move_ids)
        active = self._active_movable(grid, marker)
        if active is None:
            return self._probe(marker, move_ids)
        color, shape = active
        targets = [t for t in _target_boxes(grid) if grid[t[0]][t[1]] == color]
        if not targets:
            # This movable matches no visible target — cycle to the other one.
            return simple_action(5) if can_cycle else self._probe(marker, move_ids)

        move = self._covering_move(shape, targets, marker, move_ids)
        if move is not None:
            self._stall = 0
            return move

        # No reachable covering move under current knowledge. Alternate a probe
        # (to fill dir signs) and a selection cycle so neither movable stalls.
        self._stall += 1
        if can_cycle and self._stall % 2 == 0:
            return simple_action(5)
        return self._probe(marker, move_ids)

    def _covering_move(
        self, shape: frozenset[Cell], targets: list[Cell], marker: Cell, move_ids: list[int]
    ) -> GameAction | None:
        offsets = covering_offsets(list(shape), targets)
        if not offsets:
            return None
        # Aim at the single nearest covering offset (a full solve needs a
        # size-1 set; when the set is larger we still greedily reduce distance
        # toward its nearest member — see the banked-wall note).
        best = min(offsets, key=lambda o: abs(o[0]) + abs(o[1]))
        dr, dc = best
        if dr == 0 and dc == 0:
            return None
        want = (_sign(dr), 0) if abs(dr) >= abs(dc) else (0, _sign(dc))
        move = self._move_for(want, move_ids)
        if move is None:
            return None
        return self._issue(move, marker)

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
