"""script25 quarantined adapter: BP35 (gravity platformer, move + click-destroy).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/BP35.md`` (read for reference, not imported) records
BP35 as a gravity platformer the legacy `bp35_platformer` cleared 1/9 (L0 in
16 actions), generic R23 8B 0/9. ``docs/r57_win_condition_typology_20260715.md``
mines it as a platformer whose win is reaching a fixed `+`-shaped exit
marker. Reading the game source offline (``environment_files/bp35/*/
bp35.py``; dev-time only, the adapter reads only frames at runtime) plus a
live probe establish the mechanic. **CORRECTION CHAIN: the original
"deterministic per-action gravity" claim rested on a flawed ACTION1 no-op probe
(known-bad); R56b then over-corrected to a "MOMENTUM platformer with HIDDEN
velocity" — and R59 OVERTURNS that too.** The R59 re-examination (source read +
faithful ``env._game`` probes) shows BP35 IS deterministic and fully
frame-observable after all — the "acceleration" was fall distances and the
"receding exit" was camera scroll. See "R59 RE-EXAMINATION" below; the adapter
still ships as the frontier explorer (0/9) pending a dedicated solver pass.

**Determinism check (ORIGINAL, now KNOWN-FLAWED)**: a live repeat-probe
issued the same action from a fresh env twice and got byte-identical results,
concluding "deterministic per-action gravity". The flaw: that probe issued
ACTION1, which is NOT in ``available_actions`` ([3,4,6,7]) — a no-op that
trivially reproduces (it only ticks the step counter). It never exercised the
real controls, so it proved nothing about the actual dynamics.

**R59 RE-EXAMINATION (2026-07-16) — the R56b momentum bank is OVERTURNED.**
Reading the source (``pywlvyklps``/``fsvnqdbzrp``/``gwfodrkvzx``/``pbsitubcfd``)
plus faithful ``env._game`` probes shows BP35 is a DETERMINISTIC, fully
FRAME-OBSERVABLE grid platformer (world 11×36, gravity dy=-1):

- ``available_actions = [3, 4, 6, 7]``. ACTION3/ACTION4 move the player EXACTLY
  ONE cell horizontally, then it falls deterministically until landing. The
  R56b "2,6,6,6,6,3 acceleration" was a MISREAD of FALL DISTANCES (1 horizontal
  + N vertical); measured world positions are clean unit steps
  ((3,23)→(4,23)→(5,23)→(6,23)→(7,20)→(8,20)). There is NO velocity — the
  ``(position)→(position)`` graph is NOT aliased.
- The EXIT is FIXED at world (3,7). The R56b "receding exit" was a CAMERA
  artifact: the frame is a scrolling window over the tall level and the camera
  follows the player, so the exit's SCREEN column drifts while its WORLD cell
  never moves.
- Clicks are FUNCTIONAL (R56b "inert" is FALSE): ACTION6 on a colour-14
  ``qclfkhjnaac`` block DESTROYS it (measured 14→5); clicking the block DIRECTLY
  ABOVE the player makes it CLIMB the cleared column (measured (7,20)→(7,16)).
  ``pbsitubcfd`` only relocates the player when the clicked cell is exactly
  ``(px, py-1)`` — other clicks still remove the block but don't move the
  player, which is why the R56b probe (watching only player/exit position)
  called them inert. Screen→world is ``hyntnfvpgl(x, y+camera_y)`` (offset 0,
  scale 6): the adapter clicks the block's FRAME centroid, camera handled
  engine-side.
- WIN = the engine's own WIN signal (never hardcoded).

**Consequence**: BP35 is a clean deterministic planning problem, state =
(player world cell, set of destroyed blocks) — NO hidden state, so the R56b
"aliased hidden-velocity" framing is wrong. The solve is a (position,
destroyed-blocks) BFS/A* over {move+fall, destroy+climb}, the same shape as
sk48's faithful-simulator solve. This adapter still ships as the frontier
explorer (0/9) because that build is a DEDICATED pass: a naive hand model AND a
real-engine replay-BFS both failed to find the known-solvable L0 (the legacy
brittle solver clears it), so the move+fall+destroy dynamics need lockstep
validation against the engine (the sk48 lesson) before a solver can trust them.
See ``.wiki/wiki/games/BP35.md`` "Reopen".

**Why a generic MOVE+CLICK frontier explorer**: BP35 mixes two action
kinds, so this adapter generalises the transition-graph frontier explorer to
a HYBRID action alphabet — the simple move ids PLUS a bounded set of clicks
at the frame's salient region centroids (the destructible blocks), rather
than the unbounded 64x64 click space. Planning the gravity-aware
destroy-then-fall route faithfully would re-implement the platformer physics
(a game-specific "second brain" the R56 codex verdict forbids); instead the
search discovers the transitions:

  - Every board state is canonicalised (:func:`admorphiq.kernels.canonical_key`,
    ``mode="exact"``) after the edge-pinned HUD is masked
    (:func:`admorphiq.kernels.find_regions`).
  - The candidate ACTIONS at a state are the available moves plus a click on
    each salient centroid (recorded per state so routing knows the options).
  - Every observed ``(state, action_label, next_state)`` transition is
    recorded; the policy takes an untried action at the current state, else
    routes (:func:`admorphiq.kernels.transition_shortest_path`) to the
    nearest visited state with an untried action (:meth:`_nearest_untried`,
    a small BFS over the same edges — same rationale as
    ``admorphiq.adapters25.tu93`` for not using
    :func:`admorphiq.kernels.reachable_frontier`).

**Measured result — BANKED at 0/9**: Smoke:
- ``--max-actions 1000``: 0/9 levels, game_score 0.0; also 0/9 at 10000.
  Below the internals-tuned legacy `bp35_platformer` 1/9 (0/9 generic). The
  frontier explorer cannot compose a win: its state key is the raw
  camera-relative frame (the same world position looks different at different
  camera scroll) and it has no model of the climb / block-clearing the solve
  needs. Reopen pointer (R59, CORRECTED — the R56b "hidden velocity" pointer is
  withdrawn): BP35 is DETERMINISTIC and fully observable, so the solve is a
  (player world cell, destroyed-blocks) BFS/A* over {move+fall, destroy+climb} —
  the sk48 faithful-simulator shape. Build a lockstep-validated move+fall+destroy
  simulator (a naive model + real-engine replay-BFS both failed to find the
  known-solvable L0, so the dynamics need validation), a frame parser that
  de-aliases the camera scroll by tracking the player's WORLD position, then
  search to the gem. Open sub-puzzle: the search stays confined to y≥16 because
  the path-opening blocks above the y=15 wall are OFF-SCREEN until the player
  climbs — the correct simulator must resolve this (L0 is winnable; the legacy
  brittle solver proves it).

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` masks the HUD and enumerates the
    destructible-block click candidates.
  - :func:`admorphiq.kernels.canonical_key` hashes the masked board into a
    stable state key.
  - :func:`admorphiq.kernels.transition_shortest_path` routes over the
    incrementally-discovered transition graph.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    available_action_ids,
    canonical_layer,
    click_action,
    has_frame,
    most_common_color,
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import canonical_key, find_regions, transition_shortest_path

GAME_ID = "bp35"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]
# An action label is either a move ("m", action_id) or a click ("c", (row, col)).
Label = tuple[str, Any]

_GIVEUP_DEFAULT = 4000

_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06

# A click candidate must be a small-enough region to be an interactive block,
# not the big terrain slab — a pure "is this a clickable thing" size gate.
_MIN_CAND_SIZE = 1
_MAX_CAND_SIZE = 400


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge —
    catches BP35's bottom-row step counter (the 1-px-per-step autonomous
    change the determinism probe saw) so the state key stays stable."""
    r0, c0, r1, c1 = region["bbox"]
    h, w = r1 - r0 + 1, c1 - c0 + 1
    thickness = max(1, int(height * _HUD_THICKNESS_FRACTION))
    thickness_w = max(1, int(width * _HUD_THICKNESS_FRACTION))
    full_width_thin = w >= width * _HUD_SPAN_FRACTION and h <= thickness
    full_height_thin = h >= height * _HUD_SPAN_FRACTION and w <= thickness_w
    edge_pinned_thin = (h <= thickness and (r0 == 0 or r1 == height - 1)) or (
        w <= thickness_w and (c0 == 0 or c1 == width - 1)
    )
    return full_width_thin or full_height_thin or edge_pinned_thin


def _hud_cells(grid: Grid, bg: int) -> set[Cell]:
    height, width = len(grid), len(grid[0])
    cells: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if _is_hud_band(region, height, width):
            cells |= region["cells"]
    return cells


def _mask_hud(grid: Grid, hud: set[Cell]) -> Grid:
    if not hud:
        return grid
    bg = most_common_color(grid)
    return tuple(
        tuple(bg if (r, c) in hud else grid[r][c] for c in range(len(grid[0])))
        for r in range(len(grid))
    )


def _click_candidates(grid: Grid, hud: set[Cell], bg: int) -> list[Cell]:
    """Deterministic list of click-target cells: the rounded centroid of
    every salient (non-background, non-HUD) region within the size gate."""
    height, width = len(grid), len(grid[0])
    cells: list[Cell] = []
    seen: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if _is_hud_band(region, height, width):
            continue
        if not (_MIN_CAND_SIZE <= region["size"] <= _MAX_CAND_SIZE):
            continue
        cr, cc = region["centroid"]
        cell = (int(round(cr)), int(round(cc)))
        if 0 <= cell[0] < height and 0 <= cell[1] < width and cell not in seen and cell not in hud:
            seen.add(cell)
            cells.append(cell)
    return sorted(cells)


class Adapter(GameAdapter):
    """Generic MOVE+CLICK transition-graph frontier exploration over
    HUD-masked frame-canonical states, composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._pending_label: Label | None = None
        self._pending_key: Any | None = None

        # Transition graph over masked board states. Labels are moves or
        # clicks (see ``Label``). ``_edges`` mirrors ``_transitions`` as an
        # adjacency map kept in step so _nearest_untried stays linear.
        # ``_cands_at`` records each visited state's own action alphabet (it
        # is frame-derived — the click set depends on the current blocks).
        self._transitions: list[tuple[Any, Label, Any]] = []
        self._edges: dict[Any, dict[Label, Any]] = {}
        self._tried_from: dict[Any, set[Label]] = {}
        self._cands_at: dict[Any, list[Label]] = {}

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._on_restart()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_label = None
            self._pending_key = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        bg = most_common_color(grid)
        hud = _hud_cells(grid, bg)
        cur_key = canonical_key(_mask_hud(grid, hud), mode="exact")
        self._observe_result(cur_key)

        cands = self._cands_at.get(cur_key)
        if cands is None:
            cands = self._build_candidates(grid, hud, bg, latest_frame)
            self._cands_at[cur_key] = cands
        if not cands:
            self._pending_label = None
            self._pending_key = None
            return reset_action()

        label = self._decide(cur_key, cands)
        self._pending_label = label
        self._pending_key = cur_key
        return self._to_action(label)

    def _build_candidates(self, grid: Grid, hud: set[Cell], bg: int, latest_frame: Any) -> list[Label]:
        simple_ids, action6_ok = available_action_ids(latest_frame)
        moves: list[Label] = [("m", a) for a in sorted(simple_ids)]
        clicks: list[Label] = (
            [("c", cell) for cell in _click_candidates(grid, hud, bg)] if action6_ok else []
        )
        return moves + clicks

    def _to_action(self, label: Label) -> GameAction:
        kind, payload = label
        if kind == "m":
            return simple_action(int(payload))
        row, col = payload
        return click_action(x=col, y=row)

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._pending_label = None
        self._pending_key = None
        self._transitions = []
        self._edges = {}
        self._tried_from = {}
        self._cands_at = {}

    def _on_restart(self) -> None:
        self._pending_label = None
        self._pending_key = None

    # ── measurement: record the observed transition ─────────────────────

    def _observe_result(self, cur_key: Any) -> None:
        label = self._pending_label
        prev_key = self._pending_key
        self._pending_label = None
        self._pending_key = None
        if label is None or prev_key is None:
            return
        self._transitions.append((prev_key, label, cur_key))
        self._edges.setdefault(prev_key, {})[label] = cur_key
        self._tried_from.setdefault(prev_key, set()).add(label)

    # ── planning ─────────────────────────────────────────────────────────

    def _decide(self, cur_key: Any, cands: list[Label]) -> Label:
        tried = self._tried_from.get(cur_key, set())
        untried = [c for c in cands if c not in tried]
        if untried:
            return untried[0]

        target = self._nearest_untried(cur_key)
        if target is not None and target != cur_key:
            path = transition_shortest_path(self._transitions, cur_key, target)
            if path:
                return path[0]  # type: ignore[return-value]

        return cands[0]

    def _nearest_untried(self, start_key: Any) -> Any | None:
        """BFS over the KNOWN transition graph from ``start_key``; return the
        nearest visited state (including ``start_key``) that still has an
        untried candidate action, or None if every reachable state is fully
        explored. Hand-rolled rather than
        :func:`admorphiq.kernels.reachable_frontier` for the same reason
        ``admorphiq.adapters25.tu93`` gives (its universe is observed edges
        only, so it cannot surface a never-tried candidate)."""
        visited = {start_key}
        queue: deque[Any] = deque([start_key])
        while queue:
            state = queue.popleft()
            cands = self._cands_at.get(state)
            if cands is not None:
                tried = self._tried_from.get(state, set())
                if any(c not in tried for c in cands):
                    return state
            for _label, nxt in self._edges.get(state, {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return None
