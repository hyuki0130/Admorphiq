"""script25 quarantined adapter: SP80 (water-routing / spill-coverage puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/SP80.md`` (read for reference, not imported) records
SP80's prior characterization: the legacy ``strat_bfs_state_space`` cleared
1/6, and a 2026-07-15 script25 characterization FALSIFIED two hypotheses —
"transform requires delivering the piece onto a target region" and "the win
is a transform COUNT". This adapter is built on the actual mechanic, read
offline from the game source (``environment_files/sp80/*/sp80.py``;
dev-time only, the adapter itself reads only frames at runtime).

**Actual mechanic (water-routing coverage) — two phases**:

- **CHANGE phase**: the board has movable BLOCK/DEFLECTOR pieces (the
  currently-selected one is recoloured, colour 9 on the live board), a
  fixed WATER SOURCE near the top (a colour-4 emitter pixel), and two or
  more TARGET regions (colour 11). ACTION1-4 move the selected piece one
  cell (fixed-step, collision-checked). ACTION6 clicks to SELECT a
  different piece; the engine also auto-selects the piece nearest the
  origin at level start and after each failed spill. ACTION5 COMMITS the
  layout and switches to the spill phase.
- **SPILL phase**: water drops fall from the source (0,+1 per tick),
  splitting/deflecting off the placed pieces. When water settles centred on
  a target, that target is marked satisfied (recoloured to 13). The level
  WINS only if EVERY target is satisfied AND no hazard (colour-1 →
  colour-14) was hit; otherwise the attempt fails, the board resets to the
  change phase, and a spill-attempt counter increments. After 4 failed
  spills (or when the per-level step budget is exhausted) the game LOSES
  (GAME_OVER). This is read from the engine's ``step`` (``mlgebkvsmt``
  change/spill modes, ``srwrqoodsc`` satisfied-target set, ``zzocrmvox``
  spill counter) but NEVER hardcoded here — the adapter reacts only to the
  engine's own WIN / GAME_OVER state.

**Why a generic transition-graph explorer, not a bespoke solver**: winning
requires SPATIAL reasoning about where falling water flows given a block
layout — effectively simulating the spill. Building that faithfully would
re-implement the game's own physics, exactly the game-specific "second
brain" the R56 codex verdict (``docs/r56_codex_toolbase_verdict_20260715.md``)
forbids in the namespace. Instead this adapter treats SP80 the way the
wiki's own template intends — a GENERIC state-space search — re-expressed
through namespace-safe kernels:

  - Every board state is canonicalised into a hashable key
    (:func:`admorphiq.kernels.canonical_key`, ``mode="exact"``) AFTER the
    edge-pinned HUD bands (top rotation strip, bottom step counter) are
    masked out (:func:`admorphiq.kernels.find_regions` finds them), so the
    same piece layout always maps to the same key regardless of the ticking
    counter.
  - Every observed ``(state, action, next_state)`` transition is recorded
    (moves ACTION1-4 and the spill-commit ACTION5; the click ACTION6 is
    skipped — its coordinate space is unbounded and the auto-selection
    already exposes the level-0 piece).
  - The decision policy is systematic frontier expansion over that graph:
    take an untried action from the current state, else route
    (:func:`admorphiq.kernels.transition_shortest_path`) to the nearest
    visited state that still has an untried action (a small BFS over the
    same recorded edges, :meth:`_nearest_untried` — mirroring
    ``admorphiq.adapters25.tu93``'s reason for not using
    :func:`admorphiq.kernels.reachable_frontier`: its universe is
    already-OBSERVED edges only, so it cannot surface a state's never-
    ATTEMPTED action).

**Measured result — BANKED at 1/6 (ties the legacy card)**: level 0 is
solvable by moving the single auto-selected piece a few cells then spilling
(gold's own solve is ``[move, move, move, spill]``, 4 actions), and the
explorer finds it. Deeper levels are a genuine wall for blind search:
- The win is a water-FLOW coverage condition, invisible to a reachability
  search — the explorer can only stumble onto a winning layout, and each
  wrong spill burns one of just 4 attempts before GAME_OVER, so the search
  keeps resetting.
- Multi-piece levels additionally need TARGETED piece selection (an ACTION6
  click on a specific piece), an unbounded coordinate space this click-free
  explorer does not enter.

Smoke:
- ``--max-actions 1000``: {L1} levels, game_score {S1} (deterministic).

The honest characterisation matches the codex verdict's BP35/DC22 guidance:
the lever is not more blind search but LEARNED OBJECT DYNAMICS +
configuration-space planning that models the spill flow — which cannot be
built namespace-safe without re-implementing the water physics. Reopen
pointer: a generic "learned flow operator" motion kernel that infers, from
observed spill frames, how water propagates past each block type, letting
``configuration_path`` plan a target-covering layout in that learned model —
the same shape as the codex-proposed ``learn_point_operators`` /
``plan_overwrites`` pair, generalised to fluid propagation.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the board so the
    edge-pinned HUD bands can be masked before canonicalisation.
  - :func:`admorphiq.kernels.canonical_key` hashes the masked board into a
    stable state key.
  - :func:`admorphiq.kernels.transition_shortest_path` routes over the
    incrementally-discovered transition graph to the nearest state with an
    untried action.
"""

from __future__ import annotations

from collections import deque
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
from admorphiq.kernels import canonical_key, find_regions, transition_shortest_path

GAME_ID = "sp80"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]

# Per-level safety cap, mirroring every other script25 adapter's giveup
# convention so the harness never spins forever inside this one.
_GIVEUP_DEFAULT = 4000

# A region spanning at least this fraction of the frame's own span in one
# axis while thin in the other is a HUD status bar. Independently declared
# here (each adapter's role assignments are its own) -- matches tu93/su15/
# sb26/dc22's convention.
_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.08


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge.

    SP80's top rotation strip (row 0) and bottom step-counter band (last
    rows) are both edge-pinned; the counter band shares its colour with the
    in-play hazard, so only the EDGE-pinned test is used to distinguish the
    HUD band from a hazard sitting inside the play area."""
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


def _mask_hud(grid: Grid) -> Grid:
    """Return ``grid`` with every edge-pinned HUD band overwritten by the
    background colour, so a canonical key reflects only the play area (piece
    layout, targets, source) and not the ticking counters."""
    if not grid or not grid[0]:
        return grid
    height, width = len(grid), len(grid[0])
    bg = most_common_color(grid)
    hud_cells: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if _is_hud_band(region, height, width):
            hud_cells |= region["cells"]
    if not hud_cells:
        return grid
    return tuple(
        tuple(bg if (r, c) in hud_cells else grid[r][c] for c in range(width))
        for r in range(height)
    )


class Adapter(GameAdapter):
    """Generic transition-graph frontier exploration over HUD-masked
    frame-canonical states, composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # A failed 4th spill or an exhausted step budget ends the attempt in
        # GAME_OVER; restart and keep the learned graph so each life
        # compounds (the board layout didn't change).
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._pending_action: int | None = None
        self._pending_key: Any | None = None

        # The incrementally-discovered transition graph over masked board
        # states. ``_transitions`` is the flat triple list
        # ``transition_shortest_path`` consumes; ``_edges`` is the same graph
        # as an adjacency map maintained IN STEP so :meth:`_nearest_untried`'s
        # BFS stays linear in the graph size rather than re-folding every
        # triple each decision. Both reset on level-up (new board), kept
        # across a mid-level GAME_OVER restart (same board, new attempt).
        self._transitions: list[tuple[Any, int, Any]] = []
        self._edges: dict[Any, dict[int, Any]] = {}
        self._tried_from: dict[Any, set[int]] = {}

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._on_restart()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_action = None
            self._pending_key = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        cur_key = canonical_key(_mask_hud(grid), mode="exact")
        self._observe_result(cur_key)

        simple_ids, _action6_ok = available_action_ids(latest_frame)
        # ACTION6 (click-select) is skipped: its coordinate space is
        # unbounded and the engine auto-selects the level-0 piece.
        act_ids = sorted(a for a in simple_ids if a in (1, 2, 3, 4, 5))
        if not act_ids:
            self._pending_action = None
            self._pending_key = None
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        action = self._decide(cur_key, act_ids)
        self._pending_action = action
        self._pending_key = cur_key
        return simple_action(action)

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._pending_action = None
        self._pending_key = None
        self._transitions = []
        self._edges = {}
        self._tried_from = {}

    def _on_restart(self) -> None:
        """Only the in-flight pending action is dropped; the learned
        transition graph is kept -- the board layout didn't change on a
        spill/step-budget GAME_OVER, only the current attempt did."""
        self._pending_action = None
        self._pending_key = None

    # ── measurement: record the observed transition ─────────────────────

    def _observe_result(self, cur_key: Any) -> None:
        action = self._pending_action
        prev_key = self._pending_key
        self._pending_action = None
        self._pending_key = None
        if action is None or prev_key is None:
            return
        self._transitions.append((prev_key, action, cur_key))
        self._edges.setdefault(prev_key, {})[action] = cur_key
        self._tried_from.setdefault(prev_key, set()).add(action)

    # ── planning ─────────────────────────────────────────────────────────

    def _decide(self, cur_key: Any, act_ids: list[int]) -> int:
        tried = self._tried_from.get(cur_key, set())
        untried = [a for a in act_ids if a not in tried]
        if untried:
            return untried[0]

        target = self._nearest_untried(cur_key, act_ids)
        if target is not None and target != cur_key:
            path = transition_shortest_path(self._transitions, cur_key, target)
            if path:
                return int(path[0])

        # Fully explored under current knowledge (or the target is
        # unroutable) -- take any action rather than stall, matching every
        # other adapter's exhausted fallback.
        return act_ids[0]

    def _nearest_untried(self, start_key: Any, act_ids: list[int]) -> Any | None:
        """BFS over the KNOWN transition graph from ``start_key``; return the
        nearest state (including ``start_key`` itself) that still has an
        action in ``act_ids`` not yet recorded in ``_tried_from``, or None if
        every reachable state has been fully explored.

        Hand-rolled rather than :func:`admorphiq.kernels.reachable_frontier`
        for the same reason ``admorphiq.adapters25.tu93`` gives: that
        kernel's universe is already-OBSERVED edges only, so it can surface a
        known edge that is untried but NOT a state's never-attempted action,
        which is what frontier exploration actually needs."""
        visited = {start_key}
        queue: deque[Any] = deque([start_key])
        while queue:
            state = queue.popleft()
            tried_here = self._tried_from.get(state, set())
            if any(a not in tried_here for a in act_ids):
                return state
            for _action, nxt in self._edges.get(state, {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return None
