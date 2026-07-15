"""script25 quarantined adapter: G50T (reactive maze / Adventures-of-Lolo family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/G50T.md`` (read for reference, not imported) called G50T a
"hybrid explore-interact" game with an UNKNOWN mechanic, historically 1/7 via
the generic ``explore_interact`` heuristic. Reading the game source
(dev-time only; this adapter acts frame-only) plus live probes
(``scratchpad`` traces, offline) characterise the real mechanic for the first
time:

**Mechanic (measured — roles/hypothesis declared HERE, not in any kernel)**:
G50T is a reactive grid puzzle in the Sokoban / *Adventures of Lolo* family.

- ``available_actions`` = ``[1,2,3,4,5]`` — NO ACTION6/click. ACTION1-4 move a
  single PLAYER piece one logical cell (the render pitch is 6 px/cell,
  ``jarvstobjt=6``); the sign of each action is MEASURED, never assumed.
  **ACTION5 is UNDO** (it reverts the last move — the controller's
  ``pmlawcgvcp`` pops the move history), not an interact.
- A move is ANIMATED over ~4-5 engine steps; inputs are ignored mid-animation
  (the engine only advances the animation), so an agent streams one action
  per step and the move lands when the animation settles. A blocked move
  (into a wall) settles immediately with no displacement.
- The level WINS when the player reaches the goal sprite's cell (source:
  player position == goal position offset by (+1,+1)). The goal is a specific
  sprite with no frame-distinguishable label, so this adapter has NO oracle
  for the goal cell — it must reach it by exploration.
- The level is LOST when the player touches a hazard/enemy (a death flag) OR
  a slow left-scrolling timer sprite exits the left edge (a global move
  budget). Enemies REACT to the player's moves (they step when the player
  steps), so a cell that was safe under one enemy configuration can be fatal
  under another — the state is not the player cell alone.

**Why a blind explorer fails (measured, the load-bearing wall)**: a randomised
/ greedy-toward-corner exploration dies ~7 times per 1000 actions on the
level-1 hazards and NEVER reaches the goal (feasibility probe, 6 seeds, all
0/7). So G50T level 1 is NOT a coverage problem the old ``explore_interact``
framing suggests — it needs deliberate, hazard-aware planning, and the
reactive enemies make even that non-Markov in the player cell.

**This adapter's approach — hazard-learning transition-graph frontier
exploration** (the one principled generic lever short of a full joint
player+enemy planner): it identifies the player by movement, records every
settled ``(cell, action) -> next_cell`` transition, marks a transition FATAL
when it precedes a death, and on each decision drives toward the nearest
UNEXPLORED safe edge via ``kernels.transition_shortest_path`` /
``kernels.reachable_frontier``. Death memory compounds across lives (the graph
and fatal set survive the restart), so successive attempts avoid known traps.
The goal is discovered when the engine reports WIN on the cell that reaches it.

**Measured coverage / BANKED wall**: on the only local env (``g50t-5849a774``)
this clears **0/7**. Two measured obstacles, both real research increments:

  1. **Player identification is ambiguous from frames.** The player is a small
     coloured piece sharing its colour with larger STATIC structures, while a
     scroll-timer sprite auto-advances left EVERY action independent of the
     command. Movement-based identity (used by ``dc22``/``m0r0``) is confounded
     here: the smallest-per-colour heuristic + "responds to >=2 distinct
     directions" (to reject the one-way scroller) does not reliably lock the
     player within budget on level 1's tight, wall-blocked start. REOPEN with
     per-object tracking (``kernels.track_objects`` across settled frames) that
     correlates each object's displacement with the issued action's axis.
  2. **The reactive-enemy non-Markov property** defeats a player-cell-only
     graph — a learned-safe edge turns fatal when the enemy phase differs, so
     hazard memory alone cannot converge. REOPEN with a JOINT state (player
     cell + each enemy cell) so the transition graph is Markov, plus modelling
     ACTION5-undo as a graph edge to back out of traps cheaply.

The mechanic characterisation above (undo, animation, reactive hazards, hidden
goal, scroll timer) is the banked deliverable that unblocks both — the prior
wiki recorded the mechanic as "unknown". No hardcoded coordinates/palettes/
sequences were added; the adapter runs to budget as a clean 0/7 best-effort.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the frame; the player is
    the region that displaces under a move (identity-by-movement, as
    ``dc22``/``m0r0`` do).
  - :func:`admorphiq.kernels.transition_shortest_path` /
    :func:`admorphiq.kernels.reachable_frontier` drive frontier exploration
    over the observed player-cell transition graph.
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
from admorphiq.kernels import find_regions, reachable_frontier, transition_shortest_path

GAME_ID = "g50t"

Cell = tuple[int, int]
Region = dict[str, Any]

_GIVEUP_DEFAULT = 4000
# Render pitch: one logical cell is this many pixels (measured, jarvstobjt=6).
# Used only to quantise a centroid into a stable cell key — not a coordinate.
_CELL_PX = 6
# A frame differing from the previous by more than this many cells is still
# ANIMATING a move; at or below it the move has settled (a settled/blocked
# frame changes only by the ~1-2px scroller tick). Measured: mid-animation
# diffs were 48-105 cells, settled frames 0-2.
_ANIMATING_DIFF = 10
_MOVES = (1, 2, 3, 4)


def _quantize(centroid: tuple[float, float]) -> Cell:
    return (round(centroid[0] / _CELL_PX), round(centroid[1] / _CELL_PX))


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


def _diff_count(a: tuple[tuple[int, ...], ...], b: tuple[tuple[int, ...], ...]) -> int:
    if not a or not b or len(a) != len(b):
        return _ANIMATING_DIFF + 1
    return sum(
        1 for ra, rb in zip(a, b) for va, vb in zip(ra, rb) if va != vb
    )


class Adapter(GameAdapter):
    """Hazard-learning frontier explorer composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # Death is frequent and expected here; restarting keeps the learned
        # transition graph + fatal set and retries (mirrors every other
        # script25 adapter's restart_on_game_over convention).
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._player_color: int | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None
        # The last SETTLED frame (not the immediately-previous animating one)
        # — player identity is a between-settled-frames displacement.
        self._last_settled: tuple[tuple[int, ...], ...] | None = None
        self._player_cell: Cell | None = None
        # Cycles moves while the player is not yet identified, so the probe
        # induces motion in more than one direction.
        self._probe_i = 0

        self._pending_action: int | None = None
        self._pending_from: Cell | None = None

        # Observed player-cell transitions and bookkeeping. All survive a
        # restart (the layout is fixed; only the attempt restarts), so deaths
        # compound into avoidance.
        self._transitions: set[tuple[Cell, int, Cell]] = set()
        self._tried: set[tuple[Cell, int]] = set()
        self._fatal: set[tuple[Cell, int]] = set()
        self._plan: list[int] = []
        # Per-colour set of distinct displacement directions seen across
        # settled frames. The player responds to VARIED commands (>=2
        # directions); the always-leftward scroll-timer only ever shows one,
        # so this rejects it as a false player.
        self._dir_evidence: dict[int, set[Cell]] = {}

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._on_death()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._prev_grid = None
            self._pending_action = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        simple_ids, _a6 = available_action_ids(latest_frame)
        move_ids = [a for a in simple_ids if a in _MOVES]

        # Still animating the previous move: hold (re-issue it; the engine
        # ignores it) and don't plan until the frame settles.
        if self._prev_grid is not None and _diff_count(self._prev_grid, grid) > _ANIMATING_DIFF:
            self._prev_grid = grid
            hold = self._pending_action if self._pending_action in move_ids else self._hold(move_ids)
            return simple_action(hold)

        # Settled frame: bank the result of the last move, then decide.
        self._observe_settled(grid)
        action = self._decide(grid, move_ids, 5 in simple_ids)
        self._prev_grid = grid
        return action

    # ── level / death bookkeeping ───────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        """A cleared (or first) level: the maze, hazards and goal are all new,
        so every learned spatial fact is dropped."""
        self._levels_seen = levels
        self._player_color = None
        self._player_cell = None
        self._prev_grid = None
        self._last_settled = None
        self._probe_i = 0
        self._pending_action = None
        self._pending_from = None
        self._transitions = set()
        self._tried = set()
        self._fatal = set()
        self._plan = []
        self._dir_evidence = {}

    def _on_death(self) -> None:
        """The last move killed the player. Mark it FATAL (it precedes a
        death) and drop the in-flight plan, but KEEP the transition graph and
        fatal set — the whole point is that each life avoids the last life's
        traps."""
        if self._pending_from is not None and self._pending_action is not None:
            self._fatal.add((self._pending_from, self._pending_action))
        self._plan = []
        self._prev_grid = None
        self._last_settled = None
        self._pending_action = None
        self._pending_from = None
        self._player_cell = None

    # ── perception ──────────────────────────────────────────────────────

    def _observe_settled(self, grid: tuple[tuple[int, ...], ...]) -> None:
        """After a move settles, locate the player and, if a move was pending,
        record the ``(from, action) -> to`` transition (or, if the player
        didn't move, mark that action tried-and-blocked from ``from``)."""
        new_cell = self._locate_player(grid)
        action = self._pending_action
        origin = self._pending_from
        self._pending_action = None
        self._pending_from = None
        if action is not None and origin is not None:
            self._tried.add((origin, action))
            if new_cell is not None and new_cell != origin:
                self._transitions.add((origin, action, new_cell))
        if new_cell is not None:
            self._player_cell = new_cell
        self._last_settled = grid

    def _locate_player(self, grid: tuple[tuple[int, ...], ...]) -> Cell | None:
        bg = most_common_color(grid)
        regions = find_regions(grid, background=bg)
        if not regions:
            return None
        if self._player_color is None:
            self._identify_player(grid, regions)
        candidates = [r for r in regions if r["color"] == self._player_color]
        if not candidates:
            return None
        smallest = min(candidates, key=lambda r: r["size"])
        return _quantize(smallest["centroid"])

    def _identify_player(self, grid: tuple[tuple[int, ...], ...], regions: list[Region]) -> None:
        """Identify the player by movement between the two most recent SETTLED
        frames: the small region whose largest same-colour component shifted by
        about one cell. No pre-motion guess (that mis-picked a wall shard) —
        until a displacement is seen the player stays unknown and the caller
        keeps probing moves to induce one."""
        prev = self._last_settled
        if prev is None:
            return
        bg_prev = most_common_color(prev)
        prev_cells = self._smallest_by_color(find_regions(prev, background=bg_prev))
        cur_cells = self._smallest_by_color(regions)
        for color, (cell, size) in cur_cells.items():
            if size > 40 or color not in prev_cells:
                continue
            before = prev_cells[color][0]
            if cell == before or self._cell_distance(cell, before) > 3:
                continue
            direction = (_sign(cell[0] - before[0]), _sign(cell[1] - before[1]))
            self._dir_evidence.setdefault(color, set()).add(direction)
        # Lock the smallest colour that has moved in >=2 distinct directions
        # (command-responsive), never the single-direction scroll timer.
        responsive = [c for c, dirs in self._dir_evidence.items() if len(dirs) >= 2]
        if responsive:
            self._player_color = min(responsive, key=lambda c: cur_cells.get(c, ((0, 0), 999))[1])

    def _smallest_by_color(self, regions: list[Region]) -> dict[int, tuple[Cell, int]]:
        """The SMALLEST region per colour (the player is a small piece next to
        larger static same-colour structures, so the smallest component is the
        mobile one)."""
        out: dict[int, tuple[Cell, int]] = {}
        for r in regions:
            color = r["color"]
            if color not in out or r["size"] < out[color][1]:
                out[color] = (_quantize(r["centroid"]), r["size"])
        return out

    def _cell_distance(self, a: Cell, b: Cell) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    # ── planning ────────────────────────────────────────────────────────

    def _decide(self, grid: tuple[tuple[int, ...], ...], move_ids: list[int], can_undo: bool) -> GameAction:
        if not move_ids:
            return self._hold(move_ids)
        cur = self._player_cell
        if cur is None:
            # Player not yet identified — cycle probe moves to induce a
            # displacement the identifier can catch (one direction may be
            # wall-blocked, so rotate through them).
            self._probe_i += 1
            probe = move_ids[self._probe_i % len(move_ids)]
            return self._issue(probe, cur, move_ids)

        # Drain a queued navigation plan while it stays safe.
        if self._plan:
            action = self._plan.pop(0)
            if (cur, action) not in self._fatal and action in move_ids:
                return self._issue(action, cur, move_ids)
            self._plan = []

        # Prefer an untried, non-fatal move straight from the current cell.
        direct = [a for a in move_ids if (cur, a) not in self._tried and (cur, a) not in self._fatal]
        if direct:
            return self._issue(direct[0], cur, move_ids)

        # Otherwise navigate to the nearest cell that still has an unexplored
        # safe edge, via the observed transition graph.
        target = self._frontier_target(cur)
        if target is not None:
            state, label = target
            if state == cur:
                return self._issue(label, cur, move_ids)
            path = transition_shortest_path(self._transitions_for_planning(), cur, state)
            if path:
                self._plan = list(path) + [label]
                first = self._plan.pop(0)
                if (cur, first) not in self._fatal and first in move_ids:
                    return self._issue(first, cur, move_ids)

        # Fully explored / boxed in under current knowledge. UNDO to back out
        # of a dead pocket if we can, else retry any non-fatal move.
        if can_undo:
            return self._issue_undo()
        fallback = [a for a in move_ids if (cur, a) not in self._fatal]
        return self._issue(fallback[0] if fallback else move_ids[0], cur, move_ids)

    def _frontier_target(self, cur: Cell) -> tuple[Cell, int] | None:
        tried_pairs = self._tried | self._fatal
        frontier = reachable_frontier(self._transitions_for_planning(), cur, tried_pairs)
        for state, label in frontier:
            if isinstance(label, int) and (state, label) not in self._fatal:
                return (state, label)
        return None

    def _transitions_for_planning(self) -> list[tuple[Cell, int, Cell]]:
        # Exclude fatal edges so a planned path never routes THROUGH a known
        # death (the edge that killed us is dropped from the graph the planner
        # sees).
        return [t for t in self._transitions if (t[0], t[1]) not in self._fatal]

    def _issue(self, action: int, cur: Cell | None, move_ids: list[int]) -> GameAction:
        if action not in move_ids:
            action = self._hold(move_ids)
        self._pending_action = action
        self._pending_from = cur
        return simple_action(action)

    def _issue_undo(self) -> GameAction:
        # Undo does not advance our own from-cell bookkeeping (it is not a
        # graph move); it just rewinds the engine so the next settled frame
        # re-locates the player.
        self._pending_action = None
        self._pending_from = None
        return simple_action(5)

    def _hold(self, move_ids: list[int]) -> int:
        return move_ids[0] if move_ids else 1
