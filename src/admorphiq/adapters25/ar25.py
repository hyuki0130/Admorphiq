"""script25 quarantined adapter: AR25 (mirror-reflection coverage puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/AR25.md`` (read for reference, not imported) records
AR25 as the canonical "generic state-space BFS" template: a movement game
the legacy ``strat_bfs_state_space`` cleared 2/8 on BOTH the v1 and v2
hashes by hashing the whole frame into a state key and searching. That
wiki page's "player navigates around walls to a goal cell" model is,
however, WRONG about the actual mechanic — direct reading of the game
source plus a live probe (offline, dev-time only; this adapter reads only
frames at runtime) shows AR25 is not a single-avatar maze at all.

**Actual mechanic (mirror-reflection coverage) — measured, not the wiki's
navigation model**:

- The board has several MOVABLE glyph pieces (distinct colours, e.g. a
  colour-5 shape and a colour-4 shape on level 0) and one or more MIRROR
  BARS (a thin full-height / full-width band, colour 10 on level 0). A
  piece is rendered TOGETHER WITH its reflections across every mirror bar,
  recursively (a kaleidoscope, up to depth 12 in the engine) — so a single
  ACTION1-4 press changes a LARGE number of pixels at once (the piece plus
  all its mirror images move together), measured at 109 changed pixels per
  move on level 0, NOT the ~1-cell diff a single-avatar step produces.
- The WIN condition is COVERAGE: a fixed set of goal cells (a colour-11
  target glyph, 45 cells on level 0) must ALL be covered by some piece
  pixel or one of its reflections. This is read straight from the engine's
  own ``vplrhaovhr`` (all goal cells non-empty) but is NOT hardcoded here —
  the adapter never reads goal geometry; it only reacts to the engine's
  own WIN state.
- Controls: ACTION1-4 move the ACTIVE piece one cell (some pieces are
  axis-constrained). ACTION5 CYCLES which piece is active. ACTION6 selects
  a piece by click. ACTION7 UNDOES the last move (a real back-edge). A
  per-level STEP COUNTER (a shrinking edge bar) ends the attempt in
  GAME_OVER when exhausted.

**Why a generic transition-graph explorer, not a bespoke solver**: the
effective state is the joint configuration of every movable piece PLUS the
mirror bar PLUS which piece is active — and the reflection rule couples a
move to many pixels. Faithfully simulating the kaleidoscope to run a
configuration-space plan would mean re-implementing the game's own
rendering, which is exactly the game-specific "second brain" the R56 codex
verdict (``docs/r56_codex_toolbase_verdict_20260715.md``) forbids in the
namespace. Instead this adapter treats AR25 the way the wiki's own
template intends — a GENERIC state-space search — but re-expressed through
namespace-safe kernels rather than a bespoke BFS:

  - Every visible board state is canonicalised into a hashable key
    (:func:`admorphiq.kernels.canonical_key`, ``mode="exact"``) AFTER the
    edge-pinned HUD bands (step counter, progress bar) are masked out, so
    the same piece configuration always maps to the same key regardless of
    the ticking counter — otherwise every action would look like a brand-
    new state and no graph would ever form.
  - Every observed ``(state, action, next_state)`` transition (ACTION1-5
    and ACTION7 — the click ACTION6 is skipped, since ACTION5 already
    reaches every piece and click-coordinate exploration is an unbounded
    space) is recorded, and the engine's UNDO gives cheap back-edges.
  - The decision policy is systematic frontier expansion over that graph:
    take an untried action from the current state if one exists, else route
    (:func:`admorphiq.kernels.transition_shortest_path`) to the nearest
    already-visited state that still has an untried action (a small BFS over
    the SAME recorded edges, :meth:`_nearest_untried` — mirroring
    ``admorphiq.adapters25.tu93``'s own reason for not using
    :func:`admorphiq.kernels.reachable_frontier` here: that kernel's
    universe is already-OBSERVED edges only, so it cannot surface a state's
    never-ATTEMPTED action, which is exactly what exploration needs).

**Measured result — coverage-parity with the legacy solver, BANKED on
efficiency**: the namespace-safe kernel composition reaches the SAME 2/8
depth the legacy brittle ``strat_bfs_state_space`` reached, generically —
but blind state-space exploration over the joint piece/mirror configuration
is combinatorial, so it needs a huge budget and the RHAE metric (squared
efficiency) scores it ≈ 0 against the 32-233 human action baselines:

- ``--max-actions 1000`` (default ``giveup=4000``): 1/8 levels — L0 cleared
  in 835 actions vs a 32-action human baseline, game_score 4.1e-05
  (deterministic).
- ``--max-actions 3000``: still 1/8 — the extra actions explore level 1's
  reachable states without yet hitting the coverage-WIN configuration.
- Longer exploratory run (``giveup=30000``, NOT the standard smoke): 2/8 —
  L1/level-2 falls after 14791 actions (vs a 50-action human baseline),
  matching the legacy solver's own 2/8 coverage. This confirms the kernels
  are EXPRESSIVE enough to reach the legacy depth without any game-internal
  reads; the gap to the legacy card is budget/efficiency, not capability.

The legacy 2/8 came from ``strat_bfs_state_space`` at a ~500K-state-
expansion budget and also scored ≈ 0 on efficiency. The honest
characterisation matches the codex verdict's BP35/DC22 guidance: the lever
is not more blind search but LEARNED OBJECT DYNAMICS + configuration-space
planning that models the reflection coupling — which cannot be built
namespace-safe without either re-implementing the kaleidoscope (a second
brain) or a much richer generic "learned reflective operator" kernel that
does not yet exist. Reopen pointer: a ``learn_reflection_operators`` motion
kernel that
infers, from observed before/after frames, the mirror axis and the
piece→reflected-image map, then lets ``configuration_path`` plan coverage
in that learned model — the same shape as the codex-proposed
``learn_point_operators``/``plan_overwrites`` pair, generalised to
reflective symmetry.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the board so the
    edge-pinned HUD bands (step counter, progress bar) can be masked before
    canonicalisation.
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

GAME_ID = "ar25"

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
_HUD_THICKNESS_FRACTION = 0.06


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge.

    AR25's step counter (a bottom-row bar that SHRINKS one cell per action)
    and its right-column progress bar are both edge-pinned; the shrinking
    counter escapes the span-fraction test once it drops below the
    threshold, so the edge-pinned test is measured-necessary here exactly as
    in ``admorphiq.adapters25.tu93``."""
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
    background colour, so a canonical key reflects only the play area (the
    piece / mirror configuration) and not the ticking step counter."""
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
        # The step counter ends an attempt in GAME_OVER; restart and keep
        # the learned graph so each life compounds (the board didn't change).
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._pending_action: int | None = None
        self._pending_key: Any | None = None

        # The incrementally-discovered transition graph over masked board
        # states, UNDO back-edges included. ``_transitions`` is the flat
        # triple list ``transition_shortest_path`` consumes; ``_edges`` is the
        # same graph as an adjacency map maintained IN STEP (never rebuilt
        # from scratch) so :meth:`_nearest_untried`'s BFS stays linear in the
        # graph size rather than re-folding every triple each decision — the
        # difference matters once a run explores tens of thousands of states.
        # Both reset on level-up (new board), kept across a mid-level
        # GAME_OVER restart (same board, new attempt).
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
        # ACTION6 (click-select) is skipped: ACTION5 already cycles through
        # every selectable piece, and click-coordinate exploration is an
        # unbounded 64x64 space that would swamp the transition graph.
        act_ids = sorted(a for a in simple_ids if a in (1, 2, 3, 4, 5, 7))
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
        step-counter GAME_OVER, only the current attempt did."""
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
