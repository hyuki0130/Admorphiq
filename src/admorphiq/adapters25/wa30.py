"""script25 quarantined adapter: WA30 (pick-carry-drop delivery puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/WA30.md`` (read for reference, not imported) records
WA30 as a delivery game the legacy ``wa30_analytical`` cleared 2/9 by
reading sprite tags (``wbmdvjhthc`` worker, ``geezpjgiyd`` targets,
``pkbufziase`` pickups) — brittle, non-transferable. The generic R23 8B
agent scored 0/9 on it. ``docs/r57_win_condition_typology_20260715.md``
mines it as a delivery type ("worker navigates pickups and drop-off
zones"). Reading the game source offline (``environment_files/wa30/*/
wa30.py``; dev-time only, the adapter reads only frames at runtime) confirms
the mechanic exactly and — importantly — that it uses NO click:

**Actual mechanic (pick-carry-drop delivery) — 5 simple actions, no
coordinates**:

- A single WORKER moves on a grid. ``ACTION1..4`` move it one cell (with
  collision / pushing). ``ACTION5`` is a context INTERACT: standing next to
  a PICKUP item picks it up (the item disappears / the worker's appearance
  changes to show it is carrying); standing next to a matching TARGET zone
  delivers it.
- WIN (the engine's ``ymzfopzgbq``): every TARGET zone is satisfied
  (delivered to). Read from the source but NEVER hardcoded here — the
  adapter reacts only to the engine's own WIN state.
- A per-level step budget drives a GAME_OVER on exhaustion.

**Why the generic transition-graph explorer FITS here (unlike the click /
continuous-shape games)**: the entire delivery state — worker position,
which pickups remain, which targets are satisfied, and whether the worker is
currently carrying (its pixels change) — is fully visible in the frame, and
the action set is just the 5 simple actions. So canonicalising the
(HUD-masked) frame gives a faithful, DISCRETE state key, and the win is a
reachability target in that state graph rather than a continuous placement.
This is the exact shape the wiki's ``bfs_state_space`` template was meant
for, re-expressed through namespace-safe kernels:

  - Every board state is canonicalised into a hashable key
    (:func:`admorphiq.kernels.canonical_key`, ``mode="exact"``) after the
    edge-pinned HUD band (a bottom-row step counter) is masked
    (:func:`admorphiq.kernels.find_regions` finds it), so the same
    worker/item configuration always maps to the same key.
  - Every observed ``(state, action, next_state)`` transition (moves
    ACTION1-4 and the interact ACTION5) is recorded.
  - The policy is systematic frontier expansion over that graph: an untried
    action from the current state, else route
    (:func:`admorphiq.kernels.transition_shortest_path`) to the nearest
    visited state with an untried action (a small BFS over the same recorded
    edges, :meth:`_nearest_untried` — mirroring
    ``admorphiq.adapters25.tu93``'s reason for not using
    :func:`admorphiq.kernels.reachable_frontier`: its universe is
    already-OBSERVED edges only, so it cannot surface a state's never-
    ATTEMPTED action).

**Measured result — BANKED at 0/9**: Smoke:
- ``--max-actions 1000``: 0/9 levels, game_score 0.0 (deterministic); also
  0/9 at 5000 actions. The win chains SEVERAL deliveries (L0's human
  baseline is 71 moves across multiple target zones), a multi-subgoal
  planning problem blind frontier search does not compose before the
  per-level step budget resets the attempt. The generic explorer clears
  single-goal reachability (as on AR25/SP80/R11L level 0) but not chained
  delivery. This is below the legacy `wa30_analytical` 2/9, which read
  sprite tags + min-cost matching (0/9 generic, non-transferable).

Reopen pointer: a generic delivery/subgoal-planner kernel (the codex
verdict's ``delivery.py`` decomposition — closed-frame detection, size
clustering, bbox/slot tiling, configuration-space BFS, path-to-action) that,
from the detected worker + persistent pickup/target regions and the observed
ACTION5 pick/deliver effect, plans a min-cost pickup→target assignment and
routes via ``grid_shortest_path`` / ``configuration_path``.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` masks the edge-pinned HUD band
    before canonicalisation.
  - :func:`admorphiq.kernels.canonical_key` hashes the masked board (worker,
    pickups, targets, carry-state) into a stable state key.
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

GAME_ID = "wa30"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]

_GIVEUP_DEFAULT = 4000

_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge —
    catches WA30's bottom-row step counter so the state key stays stable
    across the ticking count."""
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
    frame-canonical states (worker/pickup/target/carry state captured in the
    key), composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # An exhausted per-level step budget ends the attempt in GAME_OVER;
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
        # Moves + the context INTERACT (ACTION5). WA30 exposes no coordinate
        # action, so the whole alphabet is these 5 simple ids.
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
