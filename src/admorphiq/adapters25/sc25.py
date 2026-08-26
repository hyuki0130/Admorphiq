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

**Directed pattern solve (`_directed_click`) — READ the target, don't search
for it.** Blind toggle-search reaches SOME multi-cell redraw first, but the
game HIGHLIGHTS near-matches (a within-one-cell toggle also redraws several
cells), so a search commits to a non-winning near-match. Instead the adapter
reads the DISPLAYED target: the colour-marked preview widget beside the grid.
Its mark centroids are binned to the grid's rows×cols by
:func:`admorphiq.kernels.template_occupancy` (`_read_target`); the target is
locked only after two consecutive equal reads (the level-entry frame still
shows the PREVIOUS level's preview until the first action redraws it). The
matched display is ``base XOR target`` (``base`` = the parity-0 cell colours,
captured on the settled frame AFTER the first action — every level's first
click is eaten by an intro/settle redraw WITHOUT toggling, so that frame is
both settled and parity-0). The solver then clicks exactly the cells whose
shown colour differs from that target display, predicting each click's toggle
so the transient post-click cursor colour can't cause a re-click loop. This is
efficient (≈ the toggle count, not a search) AND lands on the EXACT match, so
the cast is genuine. Falls through to the BFS explorer when the target is not
yet readable (early frames) or on any unseen layout.

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
    board-settle redraw from the start key). Kept as confirmation now that the
    directed solve reaches the EXACT match, not merely a near-match.

**Measured: L0+L1+L2 cleared → 3/6, game_score 0.0427.** L1 clears in 9 actions
(human baseline 6 → per-level RHAE 0.44, near human-efficient — the directed
solve makes the pattern phase ~N clicks). Generic (no hardcoded coordinates,
palettes, or level solutions). Beats the brittle legacy 2/6 (which read sprite
names).

**Banked wall — remaining (honest; reopen pointers here).** Two limiters:
  1. **Navigation efficiency (L0, L2).** The PATTERN phase is now cheap, but
     the post-cast navigate-to-exit is still a blind BFS over the move graph
     (L0 ≈ 460 actions, L2 ≈ 1380) — it clears but far from the ~12/~30-move
     human paths, so those levels barely score. Reopen: detect the player
     (the region that moves under ACTION1-4, identity-by-movement) and the
     exit marker, then ``grid_shortest_path`` straight to it — the same
     efficient navigation ``admorphiq.adapters25.ls20``/``tu93`` use.
  2. **L3+ spell selection.** Levels 0–2 auto-select the target spell; L3+
     require first CLICKING a spell sprite to choose which pattern is the
     target. Reopen by adding the spell-icon regions to the click-target set
     and reading the selected spell's preview.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments each frame into the grid
    cells, the preview marks, the player, static structure, and (excluded)
    the budget bar.
  - :func:`admorphiq.kernels.template_occupancy` reads the colour-marked
    target preview as an ``rows`` x ``cols`` boolean pattern.
  - :func:`admorphiq.kernels.configuration_path` BFS-plans the shortest
    known-edge action path from the current key to the nearest key that still
    has an untried action (BFS anchored at the level-start key).
"""

from __future__ import annotations

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
from admorphiq.kernels import configuration_path, find_regions, template_occupancy

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

# The target-pattern preview sits beside the grid, within roughly the grid's
# own row band; a mark centroid this many rows outside that band is not part
# of the preview (rejects unrelated small UI specks elsewhere on the frame).
_PREVIEW_ROW_MARGIN = 6

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

    @classmethod
    def _detect_mechanic(cls, latest_frame: Any) -> bool:
        """A spell-pattern board: enter a pattern on a toggle lattice that matches the
        one previewed beside it, then walk out.

        Two conditions, and they are the two halves of one mechanic.

        1. **Walk plus a pointer.** The pattern is entered by clicking and the exit is
           reached by walking, so the board offers the four directions AND a click, and
           no fifth action. MEASURED across the 25 public games: three expose that scheme
           (sc25, ka59, dc22), so it narrows and does not decide.
        2. **A COMPLETE toggle lattice AND the target previewed beside it.** A lattice
           with nothing to match is not this mechanic, and a preview with no lattice
           cannot be entered — both members of the pair are required. The preview is mark
           regions SMALLER than a lattice cell, in a colour the lattice does not use,
           sitting in its own block beside the lattice within its row band.

           "Complete" is the load-bearing word, and it is the DEFINITION of a grid rather
           than a size chosen to fit: a pattern you enter cell by cell occupies every
           row-column intersection, so ``rows * cols == cells``. MEASURED — without it
           this fires on dc22, whose 13 marks span 13 distinct rows and 3 distinct
           columns and so clear a ">=3 rows and >=3 columns" bar while forming no grid at
           all (13 != 39). sc25's own lattice is 9 cells in 3 rows and 3 columns.

        ⛔ Not "the parser returned something": the two structures are demanded
        explicitly, and separately. A detector that asks its own solver whether it copes
        inherits the solver's permissiveness — measured in this round, where sb26's
        parser accepted s5i5 and sc25.
        """
        simple_ids, has_click = available_action_ids(latest_frame)
        if set(simple_ids) != {1, 2, 3, 4} or not has_click:
            return False
        grid = canonical_layer(latest_frame)
        probe = cls()
        cells = probe._click_targets(grid)
        rows = len({y for _x, y in cells})
        cols = len({x for x, _y in cells})
        if len(cells) < 9 or rows * cols != len(cells):
            return False
        probe._grid_pos = probe._grid_index()
        return bool(probe._read_target(grid))

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

        # ── directed pattern-solve (read the displayed target, click the
        # differing cells) — the efficient path that replaces blind toggle
        # search. See _directed_click. All reset per level.
        self._cur_grid: tuple[tuple[int, ...], ...] | None = None
        self._grid_pos: dict[tuple[int, int], tuple[int, int]] | None = None
        self._base: dict[tuple[int, int], int] | None = None  # parity-0 cell colours
        self._two: tuple[int, int] | None = None  # the two grid-cell colours
        self._cell_last: dict[tuple[int, int], int] = {}  # last non-cursor colour per cell
        self._target: frozenset[tuple[int, int]] | None = None  # locked target 3x3 ON-set
        self._target_prev: frozenset[tuple[int, int]] | None = None
        self._target_display: dict[tuple[int, int], int] | None = None
        self._cell_size: int | None = None  # the lattice cell size (marks are smaller)
        self._level_frames = 0  # frames seen this level (0 = the transitional entry frame)

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
        self._level_frames += 1
        self._cur_grid = grid
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
        self._cur_grid = None
        self._grid_pos = None
        self._base = None
        self._two = None
        self._cell_last = {}
        self._target = None
        self._target_prev = None
        self._target_display = None
        self._cell_size = None
        self._level_frames = 0

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
                self._cell_size = _size
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

    # ── directed pattern solve (read the displayed target) ───────────────

    def _directed_click(self) -> Label | None:
        """A click on the next grid cell whose SHOWN colour differs from its
        target-matched colour, or ``None`` when the target is not yet readable
        or the grid already matches. This reads the DISPLAYED target (the
        colour-marked preview widget) and drives the grid to it, rather than
        blind-searching the toggle space — so it is efficient AND lands on the
        EXACT match (no near-match false cast). It is self-correcting: it
        compares the live display each frame, so a level's one-frame intro/
        settle offset just costs one extra click."""
        grid = self._cur_grid
        if not grid or not self._click_cells:
            return None
        if self._grid_pos is None:
            self._grid_pos = self._grid_index()
        gp = self._grid_pos
        if not gp:
            return None
        # Capture the parity-0 base colours on the first clean frame (a level
        # start / post-death reset shows every cell in one of two colours, no
        # transient cursor). _two = those two colours.
        if self._base is None and self._level_frames >= 2:
            distinct = sorted({grid[y][x] for (x, y) in gp.values()})
            if len(distinct) <= 2:
                self._base = {pos: grid[y][x] for pos, (x, y) in gp.items()}
                self._two = (distinct[0], distinct[-1])
                self._cell_last = dict(self._base)
        if self._base is None or self._two is None:
            return None  # no clean base frame yet — let BFS act (settle)
        # Each cell's last non-cursor colour (a colour outside _two = the
        # transient click cursor; keep the cell's prior known colour).
        for pos, (x, y) in gp.items():
            if grid[y][x] in self._two:
                self._cell_last[pos] = grid[y][x]
        # Lock the target once two consecutive frames agree (the entry frame
        # shows the PREVIOUS level's preview until the first action redraws it;
        # stability rejects that stale read).
        read = self._read_target(grid)
        if self._target is None and read is not None and read == self._target_prev:
            self._target = read
            flip = {self._two[0]: self._two[1], self._two[1]: self._two[0]}
            self._target_display = {
                pos: (self._base[pos] if pos not in read else flip[self._base[pos]]) for pos in gp
            }
        self._target_prev = read
        if self._target_display is None:
            return None
        flip = {self._two[0]: self._two[1], self._two[1]: self._two[0]}
        for pos in sorted(gp):
            shown = self._cell_last.get(pos)
            if shown is not None and shown != self._target_display[pos]:
                x, y = gp[pos]
                # PREDICT this cell's toggle: next frame the just-clicked cell
                # shows the transient cursor colour (not in _two), so the loop
                # above cannot re-read its true state and would otherwise
                # re-click it forever. On a level's no-op intro click (no
                # toggle) the cell stays visible next frame and the loop
                # overrides this prediction with the true reading — so both the
                # toggle and the no-op case self-correct.
                self._cell_last[pos] = flip.get(shown, shown)
                return ("c", x, y)
        return None  # grid already matches the target — the cast fires now

    def _grid_index(self) -> dict[tuple[int, int], tuple[int, int]]:
        """Map each ``(row_index, col_index)`` of the grid to its ``(x, y)``
        click coordinate, from the detected lattice cells."""
        cells = self._click_cells or []
        ys = sorted({c[1] for c in cells})
        xs = sorted({c[0] for c in cells})
        return {(ys.index(cy), xs.index(cx)): (cx, cy) for cx, cy in cells}

    def _read_target(self, grid: tuple[tuple[int, ...], ...]) -> frozenset[tuple[int, int]] | None:
        """The target ON-positions read from the colour-marked preview: small
        mark regions of a colour not used by the grid cells, in their own
        block beside the grid, binned to the grid's rows x cols by
        :func:`admorphiq.kernels.template_occupancy`."""
        if not grid or not self._click_cells or self._grid_pos is None:
            return None
        height, width = len(grid), len(grid[0])
        cells = self._click_cells
        gc0 = min(c[0] for c in cells)
        gr0, gr1 = min(c[1] for c in cells), max(c[1] for c in cells)
        grid_colours = {grid[y][x] for (x, y) in cells}
        # A preview MARK is a small dot strictly SMALLER than an interactive
        # grid cell — so the preview's own border/interior blocks (which are
        # much larger, and off-grid, and non-grid-coloured) are never mistaken
        # for marks (measured: without this the border binned to a phantom
        # centre mark, corrupting the target).
        mark_max = self._cell_size if self._cell_size else int(_MAX_CELL_AREA_FRACTION * height * width)
        regions = self._live_regions(grid)
        marks = [
            r
            for r in regions
            if r["size"] < mark_max
            and r["color"] not in grid_colours
            and r["centroid"][1] < gc0
            and gr0 - _PREVIEW_ROW_MARGIN <= r["centroid"][0] <= gr1 + _PREVIEW_ROW_MARGIN
        ]
        if not marks:
            return None
        pts = [m["centroid"] for m in marks]
        block = self._enclosing_block(regions, marks, pts)
        rows = max(k[0] for k in self._grid_pos) + 1
        cols = max(k[1] for k in self._grid_pos) + 1
        occ = template_occupancy(pts, block, rows, cols)
        return frozenset((ri, ci) for ri in range(rows) for ci in range(cols) if occ[ri][ci])

    def _enclosing_block(self, regions, marks, pts):
        """The tightest region bbox enclosing every mark centroid (the preview
        block that defines the template's full extent), else the marks' own
        bounding box when no enclosing region exists."""
        markset = {id(m) for m in marks}
        best = None
        for r in regions:
            if id(r) in markset:
                continue
            r0, c0, r1, c1 = r["bbox"]
            if all(r0 <= mr <= r1 and c0 <= mc <= c1 for mr, mc in pts):
                area = (r1 - r0) * (c1 - c0)
                if best is None or area < best[0]:
                    best = (area, r["bbox"])
        if best is not None:
            return best[1]
        boxes = [m["bbox"] for m in marks]
        return (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )

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
        # Pattern phase: if the displayed target is readable, click precisely
        # the cells whose shown colour differs from the target-matched colour
        # (a directed solve, not a search) — clears the pattern in ~N clicks
        # instead of blindly toggling, and lands on the EXACT match (so the
        # cast is genuine, not a near-match false positive). Falls through to
        # BFS exploration when the target is not yet readable (the first frames
        # of a level, before the preview redraws) or on any unseen layout.
        if cur_key not in self._post_cast_keys:
            directed = self._directed_click()
            if directed is not None:
                return directed

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
