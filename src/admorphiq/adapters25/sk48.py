"""script25 quarantined adapter: SK48 (snake pattern-matching puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/SK48.md`` (read for reference, not imported) records
SK48 as a snake-style movement game the legacy ``sk48_snake`` cleared 1/8
(later lost to a budget-starvation regression, since restored), and
``docs/r57_win_condition_typology_20260715.md`` mines it as a T1-arrival
type ("head reaches food, region count grows +2"). Reading the game source
offline (``environment_files/sk48/*/sk48.py``; dev-time only, the adapter
reads only frames at runtime) refines that: SK48 is not a plain eat-food
snake — it is a snake SHAPE / PATTERN-MATCHING puzzle.

**Actual mechanic (shape-to-template) — measured**:

- The board is split by a divider into a TOP arena (the controllable
  snake(s) + a row of coloured target cells) and a BOTTOM TEMPLATE showing
  the goal pattern.
- ACTION1-4 move the ACTIVE snake: pressing its facing direction GROWS a new
  head segment, pressing the reverse RETRACTS the tail, and a side press
  pushes the body along. ACTION6 clicks to select which snake is active
  (levels can pair a controllable snake with a template partner); ACTION7
  UNDOES the last move (a real reversible back-edge).
- WIN (the engine's ``gvtmoopqgy``): every controllable snake must be shaped
  so the sequence of coloured cells its body overlaps MATCHES its template
  partner's colour pattern, cell for cell. This is read from the source but
  NEVER hardcoded here — the adapter reacts only to the engine's own WIN
  state.
- Each level grants a fixed MOVE BUDGET (196); exhausting it LOSES
  (GAME_OVER). So blind exploration is dangerous: every wasted move eats the
  shared budget before the shaping is found.

**Why a generic transition-graph explorer, not a bespoke solver**: solving
the shaping requires reasoning about which colour sequence the snake body
traces as it moves, matched against a per-level template — reconstructing
that faithfully would rebuild the game's own overlap/match bookkeeping, the
game-specific "second brain" the R56 codex verdict
(``docs/r56_codex_toolbase_verdict_20260715.md``) forbids in the namespace.
Instead this adapter treats SK48 as a GENERIC state-space search — and a
snake's full body configuration is captured for free by canonicalising the
whole (HUD-masked) frame, which is exactly the state key a growing-body game
needs:

  - Every board state is canonicalised into a hashable key
    (:func:`admorphiq.kernels.canonical_key`, ``mode="exact"``) after the
    edge/divider HUD bands are masked (:func:`admorphiq.kernels.find_regions`
    finds them), so the snake body IS the state.
  - Every observed ``(state, action, next_state)`` transition is recorded
    (moves ACTION1-4 and the UNDO ACTION7; the click-select ACTION6 is
    skipped — its coordinate space is unbounded and the level-1 board has a
    single active snake).
  - The policy is systematic frontier expansion over that graph: an untried
    action from the current state, else route
    (:func:`admorphiq.kernels.transition_shortest_path`) to the nearest
    visited state with an untried action (a small BFS over the same recorded
    edges, :meth:`_nearest_untried` — mirroring
    ``admorphiq.adapters25.tu93``'s reason for not using
    :func:`admorphiq.kernels.reachable_frontier`: its universe is
    already-OBSERVED edges only, so it cannot surface a state's never-
    ATTEMPTED action).

**Measured result — BANKED at 0/8**: Smoke:
- ``--max-actions 1000``: 0/8 levels, game_score 0.0 (deterministic) — the
  explorer does not even shape the level-0 snake (human baseline 61 moves)
  within the smoke budget. This is below the legacy `sk48_snake` 1/8, which
  was itself budget-fragile and read snake internals (see the wiki page).

The shape-matching win is a combinatorial body-configuration target, and the
196-move budget resets the search on every exhaustion, so blind search
clears only shallow levels. The honest characterisation matches the codex
verdict's BP35/DC22 guidance: the lever is LEARNED OBJECT DYNAMICS (how each
press grows/retracts/pushes the body) + configuration-space planning toward
the template-matching colour trace, not blind search. Reopen pointer: a
generic "snake-body operator" model that infers the grow/retract/push
transition from observed moves and lets ``configuration_path`` plan a
template-matching shape — the same shape as the codex-proposed
``learn_point_operators`` / ``plan_overwrites`` pair, generalised to a
growing polyomino body.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` masks the edge/divider HUD bands
    before canonicalisation.
  - :func:`admorphiq.kernels.canonical_key` hashes the masked board (snake
    body included) into a stable state key.
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

GAME_ID = "sk48"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]

_GIVEUP_DEFAULT = 4000

_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge —
    catches SK48's full-width arena divider and any edge-pinned status bar;
    both are static, so masking them only stabilises the state key."""
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
    if not grid or not grid[0]:
        return grid
    height, width = len(grid), len(grid[0])
    bg = most_common_color(grid)
    hud: set[Cell] = set()
    for region in find_regions(grid, background=bg):
        if _is_hud_band(region, height, width):
            hud |= region["cells"]
    if not hud:
        return grid
    return tuple(
        tuple(bg if (r, c) in hud else grid[r][c] for c in range(width))
        for r in range(height)
    )


class Adapter(GameAdapter):
    """Generic transition-graph frontier exploration over HUD-masked
    frame-canonical states (snake body captured in the key), composed from
    admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # An exhausted per-level move budget ends the attempt in GAME_OVER;
        # restart and keep the learned graph so each life compounds.
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._pending_action: int | None = None
        self._pending_key: Any | None = None

        # Incrementally-discovered transition graph over masked board states.
        # ``_edges`` is the same graph as an adjacency map kept in step so
        # _nearest_untried's BFS stays linear. All reset on level-up, kept
        # across a mid-level GAME_OVER restart.
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
        # Moves + UNDO. ACTION6 (click-select) is skipped: its coordinate
        # space is unbounded and the shallow levels have one active snake.
        act_ids = sorted(a for a in simple_ids if a in (1, 2, 3, 4, 7))
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

        return act_ids[0]

    def _nearest_untried(self, start_key: Any, act_ids: list[int]) -> Any | None:
        """BFS over the KNOWN transition graph from ``start_key``; return the
        nearest state (including ``start_key``) that still has an untried
        action, or None if every reachable state is fully explored.
        Hand-rolled rather than :func:`admorphiq.kernels.reachable_frontier`
        for the same reason ``admorphiq.adapters25.tu93`` gives (its universe
        is observed edges only, so it cannot surface a never-attempted
        action)."""
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
