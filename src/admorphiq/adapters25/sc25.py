"""script25 quarantined adapter: SC25 (spell-pattern toggle + navigate).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/SC25.md`` (read for reference, not imported) and the R57
typology (`docs/r57_win_condition_typology_20260715.md`) both label SC25 a
"spell_cast" game and flag its win condition as AMBIGUOUS between a
pattern-match (T5/T6) and a navigate (T1). Reading the game source (offline,
for understanding only; never imported) and live probing settle it — the
mechanic is a TWO-PHASE combination per level:

  1. **Pattern phase.** The board shows an interactive 3×3 grid of toggle
     cells plus a target-pattern preview. Clicking (ACTION6) a grid cell
     flips it. When the grid's toggle state EXACTLY matches the (auto-selected
     on levels 0–2) target spell pattern, the game AUTO-CASTS — no separate
     "cast" click is needed; the match itself triggers it.
  2. **Navigate phase.** After the cast, the player sprite must be walked
     (ACTION1-4) into an exit cell to complete the level.

Measured gold solutions are short: L0 = 4 toggles + a few moves, L1 = 3
toggles + 2 moves. `available_actions = [1,2,3,4,6]`. A per-level CLICK budget
(a right-edge fill bar) rises with each toggle; overrun loses a life and
resets the attempt (position + grid) — handled the same way every script25
adapter handles a GAME_OVER (keep the learned graph, the layout is unchanged).

**Design — one frame-keyed transition-graph BFS-from-start (the same planner
as ``admorphiq.adapters25.ls20``), with the two-phase mechanic handled purely
by a PER-KEY action restriction.** The FULL game state (grid toggle colours,
player position) is visible in the frame, so a region-signature key is a
faithful state; the planner just routes to the nearest key with an untried
action. Three pieces make it work here:

  - **Grid detection (`_click_targets`)** — a set of ≥9 equal-size small
    regions whose centroids form a ≥3×3 lattice IS the interactive grid; its
    cell centroids are the ACTION6 click coordinates. No hardcoded pixel
    positions — the lattice is measured from the frame (and cached per level
    for label stability, since the cells stay put while only their colour
    toggles). This is why the adapter is frame-only and version-hash-agnostic.
  - **Per-key action split (`_labels_for_key`)** — a PRE-cast key offers
    CLICKS only, a POST-cast key offers MOVES only. This is the load-bearing
    idea: the player cannot move during the pattern phase, so every pre-cast
    key is a clean toggle state (≤512, no player-position explosion), and one
    BFS-from-start over the whole graph finds the single start →(clicks)→ cast
    →(moves)→ exit path. A flat search over the (position × toggle) product
    drowns (measured: 782 states / 1500 actions, no clear).
  - **State key (`_state_key`)** — the multiset of live-region signatures
    ``(colour, size, bbox)`` EXCLUDING the left/right vertical edge UI strip
    (the click-budget bar and its per-action progress ticks) and thin spanning
    bands. Only the LEFT/RIGHT edges are masked, never top/bottom — the grid's
    bottom row sits on the bottom frame edge and must be kept.

Two measured subtleties the planner needs:
  - **Death-artifact discard** — a click-budget overrun resets the attempt to
    the pristine start; the only way to reach the start key is a reset, so an
    action from a non-start key landing on start is discarded (edge NOT
    recorded, action NOT marked tried) so a fresh-budget life re-attempts it
    directly. Without this, navigation walls off at the budget horizon
    (measured: plateaus at 19 states).
  - **Cast detection (`_looks_like_cast`)** — the match auto-cast redraws
    MULTIPLE grid cells (measured 3–4) while a plain toggle changes exactly 1;
    off-grid changes (the near-match preview widget) are ignored. Cast
    detection is suppressed on the first action of an attempt (a one-frame
    board-settle redraw from the start key).

**Measured: L0 cleared, 1829 actions (human baseline 36) → 1/6.** Generic (no
hardcoded coordinates, palettes, or level solutions).

**Banked wall — L1+ (honest; reopen pointer here).** L1 does NOT clear. Root
cause, isolated by measurement: the game visually HIGHLIGHTS near-matches — a
toggle that brings the grid to within one cell of the target redraws multiple
grid cells, structurally indistinguishable from the exact-match auto-cast by
redraw-span alone. So the frame-only cast signal commits to a non-winning
near-match state and navigates from it (its 15 post-cast states are a closed
region with no path to the exit; the real match + 2 moves would win). The
redraw-span signal is sufficient for L0 (its match is the first multi-cell
event reached) but ambiguous once near-matches highlight. Reopen by reading
the DISPLAYED target pattern (a colour-marked preview) to identify the exact
required 3×3 toggle state, then click precisely the differing cells — a real
perception step, not a search. Separately, L3+ also require first CLICKING a
spell sprite to select the target (levels 0–2 auto-select it), which the
grid-only click set does not yet include.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments each frame into the grid
    cells, the player, static structure, and (excluded) the budget bar.
  - :func:`admorphiq.kernels.configuration_path` BFS-plans the shortest
    known-edge action path from the current key to the nearest key that still
    has an untried action (BFS anchored at the level-start key).
"""

from __future__ import annotations

from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    canonical_layer,
    click_action,
    has_frame,
    most_common_color,
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import configuration_path, find_regions

GAME_ID = "sc25"

Region = dict[str, Any]
StateKey = frozenset[tuple[int, int, int, int, int, int]]
# An action label: a move id (int) or a click at pixel (x, y).
Label = int | tuple[str, int, int]

_GIVEUP_DEFAULT = 4000

# HUD mask: SC25's click-budget UI lives against the RIGHT frame edge — a
# full-height colour bar PLUS small progress ticks that advance per action.
# Both must be excluded or the key fragments every action (and the ticks
# would false-trigger cast detection). Masked as: any region touching the
# left/right extreme column (the vertical edge UI strip), OR a thin spanning
# band. Deliberately only the LEFT/RIGHT edges, never top/bottom — SC25's
# interactive grid's bottom row sits on the bottom frame edge and must be kept.
_THIN_FRACTION = 0.06
_SPAN_FRACTION = 0.4

# A lattice candidate: >= this many equal-size small regions spanning >= 3
# rows and >= 3 columns is an interactive grid. Cells must be small (a real
# toggle cell is a few pixels, never a large play-area region).
_MIN_LATTICE_CELLS = 9
_MAX_LATTICE_CELLS = 25
_MAX_CELL_AREA_FRACTION = 0.02

# Cast detection. A single grid-cell toggle changes exactly ONE cell (its
# old + new region signatures); the pattern-match auto-cast redraws MULTIPLE
# cells / the board. So the cast is told apart STRUCTURALLY — a click whose
# key change touches more than one grid cell (or any area outside the grid) —
# not by raw magnitude, which conflates a real cast with a level-transition
# redraw (measured: toggle 2 sigs, cast 6-8, L-transition 35). A changed
# region belongs to a grid cell when its centre is within this many pixels of
# the cell centre (cells are ~3px, gap-separated).
_CELL_MATCH_RADIUS = 3

_FRONTIER_SEARCH_BUDGET = 100_000


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    r0, c0, r1, c1 = region["bbox"]
    if c0 <= 0 or c1 >= width - 1:
        return True  # touches a left/right frame edge = vertical UI strip
    h, w = r1 - r0 + 1, c1 - c0 + 1
    thin_h = max(1, int(height * _THIN_FRACTION))
    thin_w = max(1, int(width * _THIN_FRACTION))
    return (h <= thin_h and w >= width * _SPAN_FRACTION) or (
        w <= thin_w and h >= height * _SPAN_FRACTION
    )


class Adapter(GameAdapter):
    """Frame-keyed transition-graph BFS-from-start with toggle-click + move actions."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._transitions: list[tuple[StateKey, Label, StateKey]] = []
        self._tried_from: dict[StateKey, set[Label]] = {}

        # The clickable grid cell centres for THIS level, measured once and
        # cached so action LABELS stay stable while cells only toggle colour.
        self._click_cells: list[tuple[int, int]] | None = None

        self._start_key: StateKey | None = None
        self._plan: list[Label] = []
        self._plan_expected: list[StateKey] = []

        # Keys known to be POST-CAST (the pattern has been matched and cast).
        # A pre-cast key offers CLICK actions only (so the player never moves
        # during the pattern phase → the search stays a clean ≤512 toggle
        # space, no player-position explosion); a post-cast key offers MOVE
        # actions only (navigate to the exit). Seeded when a click fires the
        # cast (a large key jump) and propagated forward through move edges.
        # One shared BFS-from-start over the whole graph then finds the single
        # start →(clicks)→ cast →(moves)→ exit path (see _decide).
        self._post_cast_keys: set[StateKey] = set()

        self._pending_label: Label | None = None
        self._pending_key: StateKey | None = None

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._pending_label = None
            self._pending_key = None
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
        cur_key = self._state_key(grid)
        if self._start_key is None:
            self._start_key = cur_key
        self._click_targets(grid)  # cache the grid cells for click labels
        self._observe_result(cur_key)

        labels = self._labels_for_key(cur_key)
        if not labels:
            self._pending_label = None
            self._pending_key = None
            return reset_action()

        label = self._decide(cur_key, labels)
        self._pending_label = label
        self._pending_key = cur_key
        return self._to_action(label)

    # ── level bookkeeping ────────────────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._pending_label = None
        self._pending_key = None
        self._transitions = []
        self._tried_from = {}
        self._click_cells = None
        self._start_key = None
        self._plan = []
        self._plan_expected = []
        self._post_cast_keys = set()

    # ── perception ───────────────────────────────────────────────────────

    def _live_regions(self, grid: tuple[tuple[int, ...], ...]) -> list[Region]:
        if not grid:
            return []
        height, width = len(grid), len(grid[0])
        bg = most_common_color(grid)
        return [r for r in find_regions(grid, background=bg) if not _is_hud_band(r, height, width)]

    def _state_key(self, grid: tuple[tuple[int, ...], ...]) -> StateKey:
        return frozenset((r["color"], r["size"], *r["bbox"]) for r in self._live_regions(grid))

    def _click_targets(self, grid: tuple[tuple[int, ...], ...]) -> list[tuple[int, int]]:
        """The interactive grid's cell centres as ``(x, y)`` click coords —
        a lattice of >= 9 equal-size small regions spanning >= 3 rows and
        columns. Cached per level: the cells stay put while only their colour
        toggles, so the click LABELS must not wobble frame to frame."""
        if self._click_cells is not None:
            return self._click_cells
        if not grid:
            return []
        height, width = len(grid), len(grid[0])
        max_area = _MAX_CELL_AREA_FRACTION * height * width
        by_size: dict[int, list[Region]] = {}
        for r in self._live_regions(grid):
            if r["size"] <= max_area:
                by_size.setdefault(r["size"], []).append(r)
        for _size, members in sorted(by_size.items()):
            if not _MIN_LATTICE_CELLS <= len(members) <= _MAX_LATTICE_CELLS:
                continue
            rows = {round(m["centroid"][0]) for m in members}
            cols = {round(m["centroid"][1]) for m in members}
            if len(rows) >= 3 and len(cols) >= 3:
                self._click_cells = sorted(
                    (round(m["centroid"][1]), round(m["centroid"][0])) for m in members
                )
                return self._click_cells
        return []

    def _labels_for_key(self, key: StateKey) -> list[Label]:
        """The actions offered AT ``key``: MOVES for a post-cast key
        (navigate), CLICKS for a pre-cast key (build the pattern). This
        per-key split is what keeps the search tractable — the player cannot
        move until the cast, so every pre-cast key is a pure toggle state.
        SC25's action set is constant ``[1,2,3,4,6]``, so availability is not
        re-checked per key (only ``choose_action``'s own frame gates it)."""
        if key in self._post_cast_keys:
            return [1, 2, 3, 4]
        if self._click_cells:
            return [("c", x, y) for x, y in self._click_cells]
        return [1, 2, 3, 4]

    def _to_action(self, label: Label) -> GameAction:
        if isinstance(label, int):
            return simple_action(label)
        _tag, x, y = label
        return click_action(x, y)

    # ── measurement ──────────────────────────────────────────────────────

    def _observe_result(self, cur_key: StateKey) -> None:
        label = self._pending_label
        from_key = self._pending_key
        self._pending_label = None
        self._pending_key = None
        if label is None or from_key is None:
            return
        # A click-BUDGET death resets the attempt: run_game issues RESET and
        # the next frame this adapter sees is the pristine level start. The
        # only way to reach the start key is a reset, so an action from a
        # NON-start key landing on the start key is a death artifact — record
        # neither the (spurious) edge NOR the tried mark. Crucially NOT marking
        # it tried lets a fresh-budget life re-attempt the same action DIRECTLY
        # (it only "failed" because that life's budget was already spent, not
        # because the action is invalid); marking it tried would permanently
        # wall off the frontier at the budget horizon (measured: navigation
        # plateaus at 19 states without this).
        if cur_key == self._start_key and from_key != self._start_key:
            return
        self._transitions.append((from_key, label, cur_key))
        self._tried_from.setdefault(from_key, set()).add(label)
        # A CLICK that toggles ONE grid cell changes only that cell; the
        # pattern-match auto-cast redraws MULTIPLE cells / the board. So a
        # click whose change touches more than the single clicked cell IS the
        # cast — tag the resulting key POST-CAST (offers moves henceforth).
        # Propagate the tag forward through MOVE edges so every navigation
        # state stays a move-only, position-varying state. A structural test
        # (cells-touched), not a raw magnitude, so a level-transition redraw
        # can't false-trigger it (measured: L1's transition moves 35 sigs, a
        # real cast 6, a toggle 2 — magnitude alone conflates the first two).
        if not isinstance(label, int):
            # Skip the FIRST action of an attempt (from_key == start): a level
            # draws its target/spell preview on the first interaction, a
            # one-frame board redraw that spans many cells and would otherwise
            # false-trigger the cast (measured: L1's first toggle moves 37
            # sigs, every later toggle exactly 2). A real cast is never one
            # toggle from the pristine start — it needs the full pattern.
            if from_key != self._start_key and self._looks_like_cast(from_key, cur_key):
                self._post_cast_keys.add(cur_key)
        elif from_key in self._post_cast_keys:
            self._post_cast_keys.add(cur_key)

    def _looks_like_cast(self, from_key: StateKey, cur_key: StateKey) -> bool:
        """Whether a click's key change touches MORE than one GRID CELL — the
        structural signature of the auto-cast, which redraws several cells
        (measured: the match click moves 4 cells, a plain toggle exactly 1).
        Changes OUTSIDE the grid cells are ignored, not treated as a cast: a
        near-match toggle updates the target-preview widget (an off-grid
        region), which is not a cast and must not false-trigger it (measured
        on L1, where that false trigger stalled the whole level)."""
        if not self._click_cells:
            return False
        touched: set[tuple[int, int]] = set()
        for _color, _size, r0, c0, r1, c1 in from_key ^ cur_key:
            cr, cc = (r0 + r1) / 2, (c0 + c1) / 2
            nearest = min(self._click_cells, key=lambda xy: abs(xy[0] - cc) + abs(xy[1] - cr))
            if abs(nearest[0] - cc) + abs(nearest[1] - cr) <= _CELL_MATCH_RADIUS:
                touched.add(nearest)
        return len(touched) > 1

    # ── planning: single BFS-from-start over the whole graph (see ls20) ──

    def _decide(self, cur_key: StateKey, labels: list[Label]) -> Label:
        """One BFS anchored at the level-start key, exactly as
        ``admorphiq.adapters25.ls20`` — expand the graph in order of distance
        FROM START, since every click-budget death returns us there for free
        and the winning start→cast→exit path is shallow. The two-phase mechanic
        is handled entirely by :meth:`_labels_for_key` (pre-cast keys offer
        clicks, post-cast keys offer moves), so this planner is game-agnostic:
        it just routes to the nearest key that still has an untried action."""
        successors = self._successors()

        if self._plan_expected and self._plan_expected[0] == cur_key:
            self._plan_expected.pop(0)
            return self._plan.pop(0)
        self._plan = []
        self._plan_expected = []

        target = self._shallowest_frontier(successors)
        if target is not None:
            target_key, from_start = target
            if cur_key == target_key:
                untried = self._untried(cur_key)
                if untried:
                    return untried[0]
            else:
                anchor = self._start_key if cur_key == self._start_key else cur_key
                route = (
                    from_start
                    if anchor == self._start_key
                    else configuration_path(
                        cur_key, lambda k: k == target_key, successors, max_states=_FRONTIER_SEARCH_BUDGET
                    )
                )
                if route:
                    return self._launch(anchor, route, successors)

        untried_here = self._untried(cur_key)
        if untried_here:
            return untried_here[0]
        return labels[self._step % len(labels)]

    def _shallowest_frontier(self, successors):
        if self._start_key is None:
            return None

        def goal_test(key: StateKey) -> bool:
            # Before any cast is found, expand any untried frontier (search
            # the toggle space for the match). AFTER a cast is found, expand
            # ONLY post-cast (navigation) frontiers — otherwise BFS keeps
            # exhausting the large, shallow toggle space (up to 512 states)
            # and never prioritises the deeper navigate-to-exit frontier
            # (measured: without this, exploration plateaus pre-exit).
            if self._post_cast_keys and key not in self._post_cast_keys:
                return False
            return bool(self._untried(key))

        path = configuration_path(
            self._start_key, goal_test, successors, max_states=_FRONTIER_SEARCH_BUDGET
        )
        if path is None:
            return None
        target_key = self._replay(self._start_key, path, successors)
        if target_key is None:
            return None
        return target_key, path

    def _replay(self, anchor: StateKey, path, successors) -> StateKey | None:
        cur = anchor
        for label in path:
            edges = dict(successors(cur))
            if label not in edges:
                return None
            cur = edges[label]
        return cur

    def _launch(self, anchor: StateKey, plan, successors) -> Label:
        self._plan = list(plan)
        expected = [anchor]
        cur = anchor
        for label in plan[:-1]:
            cur = dict(successors(cur))[label]
            expected.append(cur)
        self._plan_expected = expected
        self._plan_expected.pop(0)
        return self._plan.pop(0)

    def _untried(self, key: StateKey) -> list[Label]:
        tried = self._tried_from.get(key, set())
        return [a for a in self._labels_for_key(key) if a not in tried]

    def _successors(self):
        edges: dict[StateKey, dict[Label, StateKey]] = {}
        for from_key, label, to_key in self._transitions:
            edges.setdefault(from_key, {})[label] = to_key

        def successors(key: StateKey):
            return list(edges.get(key, {}).items())

        return successors
