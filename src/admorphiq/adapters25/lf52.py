"""script25 quarantined adapter: LF52 (cursor-move + click-to-connect puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

LF52 is the LEAST-characterized public game: ``.wiki/wiki/games/LF52.md``
had it as "Unknown post-regression", the legacy card is 0/10 (one
budget-fragile 1/10 via a generic strategy only at total_budget=50000), and
``docs/r57_win_condition_typology_20260715.md`` could only guess "pairwise
elimination/matching (low confidence)". This adapter characterises it from
the source + a live probe (offline, dev-time only) and provides the
first generic frame-only baseline.

**Characterisation (source read + live probe)**:

- Two frame LAYERS that are BYTE-IDENTICAL (same histogram, same per-action
  diff) — the second layer is redundant, so keying on layer 0 (this repo's
  ``canonical_layer`` convention) loses no state.
- ``available_actions = [1, 2, 3, 4, 6, 7]``. ACTION1-4 move a CURSOR one
  cell (a ~1-pixel diff — a small marker relocates). ACTION6 clicks:
  clicking a game object (source names ``fozwvlovdui`` / ``lgbyiaitpdi`` /
  ``cwyrzsciwms``) triggers a CONNECT/LINK operation (``xpcuvjyrgu`` walks
  neighbours and links them, ``oyzpaylqco`` = "attach") — a ~21-pixel diff;
  a click in the bottom-left corner (x<16, y>48) triggers a redraw. ACTION7
  undoes.
- WIN is an internal completion flag (``iajuzrgttrv``); LOSE fires on an
  internal fail flag or a per-level ACTION-COUNT budget that scales with the
  level index (``asqvqzpfdi`` vs 64 / 64*5 / 64*10). So the mechanic is a
  connect/link puzzle (matching-adjacent, consistent with the typology's
  low-confidence guess), NOT plain navigation.

**Why a generic MOVE+CLICK frontier explorer**: the action set mixes cursor
moves and object clicks, so this adapter reuses the hybrid-alphabet
transition-graph explorer (see ``admorphiq.adapters25.bp35``): the candidate
actions at a state are the available simple moves PLUS a click on each
salient region centroid (the game objects), bounded rather than the 64x64
click space. Modelling the connect semantics faithfully would rebuild the
game's own object graph (a game-specific "second brain" the R56 codex
verdict forbids); the explorer instead discovers transitions:

  - :func:`admorphiq.kernels.canonical_key` (``mode="exact"``) over the
    HUD-masked layer-0 frame is the state key.
  - Candidate actions per state = moves + clicks on
    :func:`admorphiq.kernels.find_regions` centroids.
  - :func:`admorphiq.kernels.transition_shortest_path` routes to the nearest
    visited state with an untried action (:meth:`_nearest_untried`, the same
    ``admorphiq.adapters25.tu93`` rationale for not using
    :func:`admorphiq.kernels.reachable_frontier`).

**Measured result — BANKED at 0/10**:
- ``--max-actions 1000``: 0/10 levels, game_score 0.0 (deterministic). The
  first generic frame-only measurement of a game the card had left entirely
  uncharacterised. Matches the legacy 0/10 (a lone 1/10 existed only at a
  50000 ensemble budget and never transferred).

**R56b validation probe (2026-07-15) — the link-operator premise is
FALSIFIED; do NOT build a positional planner.** A validate-first probe (run
BEFORE any build, per the bp35 lesson) established:
- The click effect IS deterministic and frame-observable (two fresh envs
  clicking the same object produce byte-identical frames; re-clicking the
  same object is idle — diffs [21,1,1] — so there is no hidden accumulation).
- BUT the effect is INPUT-POSITION-INDEPENDENT: an ACTION6 click grows a
  fixed colour-9 region at the SAME game-determined location regardless of
  WHERE it clicks (all four directions + far-apart coordinates produce the
  identical +20-cell growth at grid (17-20,16-21)), AND regardless of any
  preceding ACTION1-4 cursor moves (which do not shift the growth at all).
So there is no POSITIONAL click→link operator to learn — ACTION6 is a fixed
predetermined "advance", and the cursor does not steer it. The planner
premise ("learn a positional operator, plan a link sequence via
configuration_path") is therefore falsified: whatever the true control
modality is (timing / a hidden mode / a specific object subset-and-order the
frame does not expose), it is not the frame-derived positional link this
approach assumed. Banked at 0/10 without building — the decisive probe saved
the speculative planner. Reopen pointer (harder): the observable draw is a
side-effect animation; identify the REAL state the game gates the win on
(likely not the colour-9 growth) and what genuinely varies the outcome
before assuming any operator exists.

Composition from ``admorphiq.kernels``: find_regions, canonical_key,
transition_shortest_path (as above).
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

GAME_ID = "lf52"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]
Label = tuple[str, Any]

_GIVEUP_DEFAULT = 4000

_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06

_MIN_CAND_SIZE = 1
_MAX_CAND_SIZE = 400


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge —
    masks any edge-pinned status bar so the state key stays stable."""
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
        untried candidate action, or None if fully explored. Hand-rolled
        rather than :func:`admorphiq.kernels.reachable_frontier` for the same
        reason ``admorphiq.adapters25.tu93`` gives (its universe is observed
        edges only, so it cannot surface a never-tried candidate)."""
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
