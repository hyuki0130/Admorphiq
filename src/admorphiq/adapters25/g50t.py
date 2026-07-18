"""script25 quarantined adapter: G50T (Adventures-of-Lolo momentary-plate + ghost).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

**STATUS: L0 CLEARED (first-ever g50t clear) via the ACTION5 record-replay
GHOST — the mechanic the prior banks (and the reopen brief) got wrong.**

The reopen brief (commit 81bf415) modelled L0 as "walk to a pressure plate,
the gate LATCHES open, BFS to the goal — avoid ACTION5". A clean live decode
(scratchpad probes + the game source, dev-time read only; this adapter acts
frame-only) REFUTES that: the plate is **MOMENTARY**, and the win needs a
single player at ``goal + (1, 1)`` across a single-cell barrier that is open
ONLY while a body stands on the plate. With one player that barrier is
impassable — so **ACTION5 (the record-replay ghost) is REQUIRED, not
avoidable**: you record a path onto the plate, press ACTION5 to bank that path
as a replaying GHOST clone that seats on the plate and HOLDS it open, and then
walk the (reset-to-start) player through the now-open barrier to the goal.

**Decoded mechanic (all live-verified on ``g50t-5849a774`` L0):**

- Movement is ONE CELL (6 px, ``jarvstobjt=6``) per ``env.step`` — NOT a slide
  and NOT animated across steps. ACTION1=up, 2=down, 3=left, 4=right (measured;
  the sign of each is read from the frame, never assumed). A blocked move
  leaves the player in place (the only frame change is a ~1 px HUD scroll-tick).
  There is a one-step input priming: the very first re-issue after a settle can
  be absorbed, so every hop is driven CLOSED-LOOP (re-issue until the observed
  player cell reaches the target); a blocked/absorbed step never advances the
  ghost, so this stays in lockstep.
- The PLAYER is a small (5x5) colour-9 blob that MOVES; the GOAL is a static
  colour-9 region elsewhere (both share colour 9 — identity is by MOTION, not
  colour). Floor is colour 5; walls are non-floor. A pressure PLATE and the
  barrier it controls both render as colour 8, distinguished only by
  behaviour: you can ENTER a plate cell (it opens a barrier); you cannot enter
  a wall/barrier cell.
- Circuit (source ``qxlodtievc.ayhgaxoxce``): standing on the plate sets its
  wired barrier passable; STEPPING OFF re-closes it (momentary — verified live:
  the barrier cell's colour flips 8->5 while on the plate, 5->8 when off).
- ACTION5 (``pmlawcgvcp``): rewinds the whole path to the start cell and banks
  it as a GHOST that replays the path in lockstep with the player's subsequent
  moves, then STAYS at its final recorded cell (source: a replaying ghost whose
  path is exhausted stops moving). Seat the ghost on the plate and it holds the
  barrier open for the rest of the level. A BLOCKED player move does not advance
  the ghost (``move`` returns before the replay loop).
- WIN when the player reaches ``goal + (1, 1)`` (source ``safkknjslo``);
  reaching the goal region's cell triggers it.

**Runtime pipeline (per level, all generic — no hardcoded cells):**

1. **Identify** the player by motion (probe legal moves; the colour-9 blob that
   moved is the player, the static colour-9 region is the goal). Parse the floor
   grid (colour-5 cell centres) at the player-derived 6 px cell phase.
2. If the goal cell is already reachable over the floor: BFS straight to it.
3. Otherwise **discover the plate**: the frontier colour-8 cells adjacent to
   the reachable region are candidates (tried farthest-from-goal first, which is
   the plate on L0); navigate to each and try to enter it. The one the player
   can ENTER and whose entry EXPANDS the floor (opens a barrier) is the plate;
   the newly-opened cells (minus the plate) are the BARRIER set.
4. On the plate, press **ACTION5** to bank the ghost. ``Lg`` = the genuine moves
   made before the press.
5. **Plan** the reset-to-start player's route with
   :func:`admorphiq.kernels.configuration_path` over ``(cell, moves_made)``: a
   barrier cell is passable only once ``moves_made >= Lg`` (ghost seated).
6. **Execute** closed-loop: drive to each planned cell, re-issuing the move
   until the observed player cell reaches it.

Levels beyond L0 add enemies + more circuits (source-confirmed); this adapter's
generic pipeline attempts them but is not tuned for them — a level whose plan
cannot be found degrades to a bounded explorer, so the L0 clear never hangs.
GAME_OVER restarts the attempt.

Composition from ``admorphiq.kernels``: :func:`find_regions` (player / goal /
region detection) and :func:`configuration_path` (the time-gated route BFS);
all pixel classification is plain-Python iteration over the observation grid.
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
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import configuration_path, find_regions

GAME_ID = "g50t"

Cell = tuple[int, int]
Grid = tuple[tuple[int, ...], ...]

_GIVEUP_DEFAULT = 4000
_CELL_PX = 6            # render pitch: one logical cell (measured, jarvstobjt=6)
_FLOOR_COLOR = 5
_MOVER_COLOR = 9        # both the player and the goal render in colour 9
_CIRCUIT_COLOR = 8      # plates AND barriers/walls render in colour 8
# action id -> (d_row, d_col) grid step (measured live: 1=up, 2=down, 3=left, 4=right)
_MOVE_VEC: dict[int, Cell] = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
_VEC_MOVE: dict[Cell, int] = {v: k for k, v in _MOVE_VEC.items()}
_MOVES = (1, 2, 3, 4)
_ACTION5 = 5
_STUCK_TRIES = 4        # re-issues of one hop before treating the player as blocked
_SETTLE_MAX = 40        # frames to wait for the post-ACTION5 rewind
_PLAN_BUDGET = 200_000  # joint (cell, moves) states for the route BFS


class _L1TwoGhost:
    """Frame-only two-ghost nested-circuit solver for L1+, exposed as a generator
    (:meth:`run`) so the per-call adapter can drive it: ``grid = yield action``
    returns the frame observed after that action (env lag-1, handled in the batch
    reconcile). No hardcoded cells -- plates/barriers are DISCOVERED from the
    colour-8 frontier + floor-expansion-on-seat, and barrier open/closed state is
    read live from the frame (colour 5 = open, 8 = closed), so no ghost-clock
    (Lg) arithmetic is needed. See ``.wiki/wiki/games/G50T.md`` "L1 CLEARED".
    """

    def __init__(self) -> None:
        self.off: Cell | None = None
        self.goal: Cell | None = None
        self.pcell: Cell | None = None
        self.grid: Grid | None = None
        self.blocked: set[tuple[Cell, int]] = set()
        self.barriers: set[Cell] = set()

    # ── perception ──────────────────────────────────────────────────────
    def _nine(self, grid: Grid) -> list[dict[str, Any]]:
        out = []
        for reg in find_regions(grid, background=None):
            if reg["color"] != _MOVER_COLOR:
                continue
            r0 = reg["bbox"][0]
            if 7 <= r0 <= 58 and 8 <= reg["size"] <= 40:
                out.append(reg)
        return out

    def _to_cell(self, cy: float, cx: float) -> Cell:
        return (round((cy - self.off[0]) / _CELL_PX), round((cx - self.off[1]) / _CELL_PX))  # type: ignore[index]

    def _obs_player(self, grid: Grid) -> Cell | None:
        cands = [self._to_cell(*(r["centroid"])) for r in self._nine(grid)]
        if not cands:
            return None
        cands = [c for c in cands if c != self.goal] or cands
        if self.pcell is not None:
            pc = self.pcell
            return min(cands, key=lambda c: abs(c[0] - pc[0]) + abs(c[1] - pc[1]))
        return cands[0]

    def _floor(self, grid: Grid) -> set[Cell]:
        if not grid or not grid[0]:
            return set()
        h = len(grid)
        w = len(grid[0])
        cells: set[Cell] = set()
        i = 0
        while self.off[0] + i * _CELL_PX < h - 2:  # type: ignore[index]
            j = 0
            while self.off[1] + j * _CELL_PX < w - 2:  # type: ignore[index]
                if grid[self.off[0] + i * _CELL_PX][self.off[1] + j * _CELL_PX] == _FLOOR_COLOR:  # type: ignore[index]
                    cells.add((i, j))
                j += 1
            i += 1
        return cells

    def _color(self, grid: Grid, cell: Cell) -> int:
        r = self.off[0] + cell[0] * _CELL_PX  # type: ignore[index]
        c = self.off[1] + cell[1] * _CELL_PX  # type: ignore[index]
        if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
            return grid[r][c]
        return -1

    def _open_barriers(self) -> set[Cell]:
        return {c for c in self.barriers if self._color(self.grid, c) == _FLOOR_COLOR}

    def _wall_bump(self, cell: Cell) -> int | None:
        floor = self._floor(self.grid)
        for a, (dr, dc) in _MOVE_VEC.items():
            if (cell[0] + dr, cell[1] + dc) not in floor:
                return a
        return None

    def _reach(self, passable: set[Cell], start: Cell) -> set[Cell]:
        seen = {start}
        q: deque[Cell] = deque([start])
        while q:
            cur = q.popleft()
            for a, (dr, dc) in _MOVE_VEC.items():
                if (cur, a) in self.blocked:
                    continue
                n = (cur[0] + dr, cur[1] + dc)
                if n in passable and n not in seen:
                    seen.add(n)
                    q.append(n)
        return seen

    def _plan(self, start: Cell, target: Cell, enter: Cell | None) -> list[int] | None:
        pass_set = self._floor(self.grid) | self._open_barriers()
        seen = {start}
        parent: dict[Cell, tuple[int, Cell]] = {}
        q: deque[Cell] = deque([start])
        while q:
            cur = q.popleft()
            if cur == target:
                acts: list[int] = []
                c = cur
                while c in parent:
                    a, p = parent[c]
                    acts.append(a)
                    c = p
                return acts[::-1]
            for a, (dr, dc) in _MOVE_VEC.items():
                if (cur, a) in self.blocked:
                    continue
                n = (cur[0] + dr, cur[1] + dc)
                if (n in pass_set or n == target or n == enter) and n not in seen:
                    seen.add(n)
                    parent[n] = (a, cur)
                    q.append(n)
        return None

    def _frontier8(self, region: set[Cell]) -> set[Cell]:
        out: set[Cell] = set()
        for cell in region:
            for dr, dc in _MOVE_VEC.values():
                n = (cell[0] + dr, cell[1] + dc)
                if n not in region and self._color(self.grid, n) == _CIRCUIT_COLOR:
                    out.add(n)
        return out

    # ── generator primitives (``grid = yield action``) ──────────────────
    def _step(self, a: int):
        g = yield a
        self.grid = g
        return g

    def _batch(self, plan: list[int]):
        """Open-loop plan + one flush no-op, then reconcile the lag-1 obs log.
        Returns (confirmed_cell, wall) where wall=(cell,action) if a sprite-mask
        wall was hit. Assumes the pipeline is drained at entry."""
        start = self.pcell
        planned = [start]
        for a in plan:
            dr, dc = _MOVE_VEC[a]
            planned.append((planned[-1][0] + dr, planned[-1][1] + dc))
        obs_log: list[Cell | None] = [start]
        for a in plan:
            g = yield from self._step(a)
            p = self._obs_player(g)
            obs_log.append(p)
            if p is None:
                return start, None
        wb = self._wall_bump(planned[-1]) or self._wall_bump(start) or 1  # type: ignore[arg-type]
        g = yield from self._step(wb)
        pf = self._obs_player(g)
        obs_log.append(pf if pf is not None else obs_log[-1])
        # lag-1: obs_log[k+2] is the true position after plan[k].
        for k in range(len(plan)):
            true_after = obs_log[k + 2] if k + 2 < len(obs_log) else obs_log[-1]
            if true_after == planned[k + 1]:
                continue
            self.blocked.add((planned[k], plan[k]))
            self.pcell = planned[k]
            return planned[k], (planned[k], plan[k])
        self.pcell = planned[-1]
        return planned[-1], None

    def _filler(self):
        floor = self._floor(self.grid)
        for a, (dr, dc) in _MOVE_VEC.items():
            n = (self.pcell[0] + dr, self.pcell[1] + dc)  # type: ignore[index]
            if n in floor and (self.pcell, a) not in self.blocked:
                yield from self._batch([a])
                return
        wb = self._wall_bump(self.pcell) or 1  # type: ignore[arg-type]
        yield from self._step(wb)

    def _drive(self, target: Cell, enter: Cell | None = None, cycles: int = 80, max_wait: int = 45):
        waited = 0
        for _ in range(cycles):
            if self.pcell == target:
                return True
            if not self._nine(self.grid):
                return False
            plan = self._plan(self.pcell, target, enter)  # type: ignore[arg-type]
            if not plan:
                if waited >= max_wait:
                    return False
                waited += 1
                yield from self._filler()
                continue
            _conf, wall = yield from self._batch(plan)
            if self.pcell == target:
                return True
            if wall is None and _conf != target:
                if waited >= max_wait:
                    return False
                waited += 1
                yield from self._filler()
        return self.pcell == target

    def _discover(self, seated: set[Cell], wait: int, known_plates: list[Cell]):
        floor = self._floor(self.grid)
        reach_seat = self._reach(floor | seated, self.pcell)  # type: ignore[arg-type]
        near = {(c[0] + dr, c[1] + dc) for c in self.barriers for dr, dc in _MOVE_VEC.values()} | self.barriers
        pool = self._frontier8(reach_seat) - self.barriers - set(known_plates) - near
        p = self.pcell
        ordered = sorted(pool, key=lambda c: abs(c[0] - p[0]) + abs(c[1] - p[1]))  # type: ignore[index]
        cands: list[Cell] = []
        for cand in ordered:
            for a, (dr, dc) in _MOVE_VEC.items():
                ap = (cand[0] - dr, cand[1] - dc)
                if ap in reach_seat and (ap, a) not in self.blocked:
                    cands.append(cand)
                    break
        for cand in cands:
            fb = self._floor(self.grid)
            ok = yield from self._drive(cand, enter=cand, max_wait=wait)
            added = {c for c in (self._floor(self.grid) - fb) if c != cand}
            if ok and added:
                return cand, added
        return None, None

    def _settle_rewind(self, spawn: Cell, tries: int = 12):
        for _ in range(tries):
            obs = self._obs_player(self.grid)
            if obs is not None:
                self.pcell = obs
            if self.pcell == spawn:
                return
            wb = self._wall_bump(self.pcell) or 1  # type: ignore[arg-type]
            yield from self._step(wb)

    def _identify(self):
        g = yield from self._step(_MOVES[1])  # snap probe (a displacing move)
        idc = [(r["centroid"][0], r["centroid"][1]) for r in self._nine(g)]
        for a in (2, 4, 1, 3, 2, 4, 1, 3):
            g = yield from self._step(a)
            now = [(r["centroid"][0], r["centroid"][1]) for r in self._nine(g)]
            moved = [c for c in now if all(abs(c[0] - o[0]) + abs(c[1] - o[1]) > 2 for o in idc)]
            static = [c for c in now if any(abs(c[0] - o[0]) + abs(c[1] - o[1]) <= 2 for o in idc)]
            if moved:
                self.off = (int(round(moved[0][0])) % _CELL_PX, int(round(moved[0][1])) % _CELL_PX)
                self.pcell = self._to_cell(*moved[0])
                self.goal = self._to_cell(*static[0]) if static else None
                wb = self._wall_bump(self.pcell) or 1
                g = yield from self._step(wb)  # drain the pending identify move
                op = self._obs_player(g)
                if op is not None:
                    self.pcell = op
                return
            idc = now

    def run(self):
        """Drive: identify -> seat ghost B -> seat ghost A -> walk to goal. Yields
        one action per env step; ``grid = yield action`` feeds the next frame."""
        self.grid = yield  # prime
        yield from self._identify()
        if self.off is None or self.goal is None:
            while True:
                yield _MOVES[0]
        spawn = self.pcell
        plate_b, barr_b = yield from self._discover(set(), 0, [])
        if plate_b is None:
            while True:
                yield _MOVES[0]
        self.barriers |= barr_b
        yield from self._step(_ACTION5)  # bank ghost B
        yield from self._settle_rewind(spawn)  # type: ignore[arg-type]
        plate_a, barr_a = yield from self._discover(barr_b, 60, [plate_b])
        if plate_a is None:
            while True:
                yield _MOVES[0]
        self.barriers |= barr_a
        yield from self._step(_ACTION5)  # bank ghost A
        yield from self._settle_rewind(spawn)  # type: ignore[arg-type]
        for gt in (self.goal, (self.goal[0] + 1, self.goal[1] + 1),
                   (self.goal[0] + 1, self.goal[1]), (self.goal[0], self.goal[1] + 1)):
            yield from self._drive(gt, enter=gt, cycles=60)
        while True:
            yield _MOVES[0]


class Adapter(GameAdapter):
    """Momentary-plate + record-replay-ghost solver composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        self._reset_level_state()

    def _reset_level_state(self) -> None:
        # phase: id -> discover -> press -> settle -> execute -> explore/done
        self._phase = "id"
        self._off: Cell | None = None
        self._start_cell: Cell | None = None
        self._goal_cell: Cell | None = None
        self._base_floor: set[Cell] = set()
        self._start_grid: Grid | None = None
        self._barrier: set[Cell] = set()
        self._plate_cell: Cell | None = None
        # identity-by-motion bookkeeping
        self._id_cells: list[Cell] | None = None
        self._id_try = 0
        # discovery bookkeeping
        self._candidates: list[Cell] = []
        self._disc_cand: Cell | None = None
        self._disc_enter: int | None = None
        self._floor_before: set[Cell] = set()
        # a route = ordered target cells to drive through, closed-loop
        self._route: list[Cell] = []
        self._route_stuck = 0
        # ghost / execution
        self._moves_made = 0
        self._lg = 0
        self._settle_tries = 0
        # motion tracking
        self._prev_player: Cell | None = None
        self._explore_i = 0
        # L1+ two-ghost generator solver (created on first L1 frame)
        self._l1_gen: Any = None

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._reset_level_state()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._levels_seen = levels
            self._reset_level_state()

        self._step += 1
        simple_ids, _a6 = available_action_ids(latest_frame)
        move_ids = [a for a in simple_ids if a in _MOVES]
        can_ghost = _ACTION5 in simple_ids
        if not move_ids:
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        # L1+ (nested two-ghost circuits): drive the dedicated generator solver.
        # L0 stays on the single-ghost FSM below (byte-identical).
        if levels >= 1 and can_ghost:
            act = self._l1_action(grid)
            if act in move_ids or act == _ACTION5:
                return simple_action(act)
            return simple_action(move_ids[0])

        return simple_action(self._decide(grid, move_ids, can_ghost))

    def _l1_action(self, grid: Grid) -> int:
        """Drive the persistent L1 two-ghost generator one step (per-call)."""
        if self._l1_gen is None:
            self._l1_gen = _L1TwoGhost().run()
            next(self._l1_gen)  # prime to the first ``grid = yield``
        try:
            return self._l1_gen.send(grid)
        except StopIteration:
            return _MOVES[0]

    # ── perception ──────────────────────────────────────────────────────

    def _movers(self, grid: Grid) -> list[dict[str, Any]]:
        out = []
        for reg in find_regions(grid, background=None):
            if reg["color"] != _MOVER_COLOR:
                continue
            r0 = reg["bbox"][0]
            if r0 < 7 or r0 > 58 or not (8 <= reg["size"] <= 40):
                continue
            out.append(reg)
        return out

    def _to_cell(self, centroid: tuple[float, float]) -> Cell:
        off_r, off_c = self._off  # type: ignore[misc]
        return (round((centroid[0] - off_r) / _CELL_PX), round((centroid[1] - off_c) / _CELL_PX))

    def _cell_color(self, grid: Grid, cell: Cell) -> int:
        off_r, off_c = self._off  # type: ignore[misc]
        r, c = off_r + cell[0] * _CELL_PX, off_c + cell[1] * _CELL_PX
        if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
            return grid[r][c]
        return -1

    def _floor_cells(self, grid: Grid) -> set[Cell]:
        off_r, off_c = self._off  # type: ignore[misc]
        h = len(grid)
        w = len(grid[0]) if h else 0
        cells: set[Cell] = set()
        i = 0
        while off_r + i * _CELL_PX < h:
            j = 0
            while off_c + j * _CELL_PX < w:
                if grid[off_r + i * _CELL_PX][off_c + j * _CELL_PX] == _FLOOR_COLOR:
                    cells.add((i, j))
                j += 1
            i += 1
        return cells

    def _player_cell(self, grid: Grid) -> Cell | None:
        movers = self._movers(grid)
        if not movers:
            return None
        cells = [self._to_cell(m["centroid"]) for m in movers]
        if self._goal_cell is not None:
            filtered = [c for c in cells if c != self._goal_cell]
            cells = filtered or cells
        anchor = self._prev_player or self._start_cell
        if anchor is None:
            return cells[0]
        return min(cells, key=lambda c: abs(c[0] - anchor[0]) + abs(c[1] - anchor[1]))

    def _derive_offset(self, grid: Grid) -> Cell | None:
        movers = self._movers(grid)
        if not movers:
            return None
        cy, cx = movers[0]["centroid"]
        return (int(round(cy)) % _CELL_PX, int(round(cx)) % _CELL_PX)

    # ── reachability / routing ──────────────────────────────────────────

    def _reachable(self, floor: set[Cell], start: Cell) -> tuple[set[Cell], dict[Cell, tuple[Cell, int]]]:
        seen = {start}
        parent: dict[Cell, tuple[Cell, int]] = {}
        q: deque[Cell] = deque([start])
        while q:
            cur = q.popleft()
            for a, (dr, dc) in _MOVE_VEC.items():
                n = (cur[0] + dr, cur[1] + dc)
                if n in floor and n not in seen:
                    seen.add(n)
                    parent[n] = (cur, a)
                    q.append(n)
        return seen, parent

    def _cells_to(self, parent: dict[Cell, tuple[Cell, int]], target: Cell) -> list[Cell]:
        cells: list[Cell] = []
        cur = target
        while cur in parent:
            cells.append(cur)
            cur = parent[cur][0]
        return cells[::-1]

    def _frontier_circuit(self, grid: Grid, reachable: set[Cell]) -> list[Cell]:
        cands: set[Cell] = set()
        for cell in reachable:
            for dr, dc in _MOVE_VEC.values():
                n = (cell[0] + dr, cell[1] + dc)
                if n not in reachable and self._cell_color(grid, n) == _CIRCUIT_COLOR:
                    cands.add(n)
        goal = self._goal_cell or (0, 0)
        # farthest-from-goal first: on L0 that is the plate (the barrier sits
        # between the chamber and the goal, so it is nearer the goal).
        return sorted(cands, key=lambda c: -(abs(c[0] - goal[0]) + abs(c[1] - goal[1])))

    # ── the single closed-loop hop primitive ────────────────────────────

    def _hop(self, p: Cell, target: Cell, move_ids: list[int]) -> int:
        """Action that steps one cardinal cell from ``p`` toward the adjacent
        ``target`` (re-issued by the caller until the player reaches it)."""
        dr = max(-1, min(1, target[0] - p[0]))
        dc = max(-1, min(1, target[1] - p[1]))
        for vec in ((dr, dc), (dr, 0), (0, dc)):
            if vec in _VEC_MOVE and _VEC_MOVE[vec] in move_ids:
                return _VEC_MOVE[vec]
        return move_ids[0]

    def _track(self, p: Cell) -> None:
        if self._prev_player is not None and p != self._prev_player:
            self._moves_made += 1
            self._route_stuck = 0
        elif self._prev_player is not None:
            self._route_stuck += 1
        self._prev_player = p

    # ── decision FSM ────────────────────────────────────────────────────

    def _decide(self, grid: Grid, move_ids: list[int], can_ghost: bool) -> int:
        if self._phase == "id":
            return self._identify(grid, move_ids)
        if self._phase == "discover":
            return self._discover(grid, move_ids)
        if self._phase == "press":
            self._lg = self._moves_made
            if not can_ghost:
                self._phase = "explore"
                return self._explore(move_ids)
            self._phase = "settle"
            self._settle_tries = 0
            return _ACTION5
        if self._phase == "settle":
            return self._settle(grid, move_ids)
        if self._phase == "execute":
            return self._drive(grid, move_ids)
        return self._explore(move_ids)

    def _identify(self, grid: Grid, move_ids: list[int]) -> int:
        """Probe legal moves until a colour-9 blob moves; that is the player, the
        static one is the goal. UP/LEFT are wall-blocked on L0, so cycle moves."""
        if self._off is None:
            self._off = self._derive_offset(grid)
            if self._off is None:
                return self._explore(move_ids)
        now = [self._to_cell(m["centroid"]) for m in self._movers(grid)]
        if self._id_cells is None:
            self._id_cells = now
            self._start_grid = grid
            self._base_floor = self._floor_cells(grid)
            self._id_try = 0
            return move_ids[self._id_try % len(move_ids)]
        moved = [c for c in now if c not in self._id_cells]
        if not moved:
            self._id_try += 1
            if self._id_try > 8:
                self._phase = "explore"
            return move_ids[self._id_try % len(move_ids)]
        gone = [c for c in self._id_cells if c not in now]
        static = [c for c in self._id_cells if c in now]
        self._start_cell = gone[0] if gone else self._id_cells[0]
        self._goal_cell = static[0] if static else None
        self._prev_player = moved[0]
        # The probe just made ONE genuine displacement, which the engine has
        # already banked into the ghost-record path — count it so Lg matches the
        # true recorded length (blocked probe attempts moved nothing and are not
        # counted).
        self._moves_made = 1
        assert self._start_grid is not None
        self._base_floor = self._floor_cells(self._start_grid)
        reach, parent = self._reachable(self._base_floor, self._start_cell)
        if self._goal_cell is not None and self._goal_cell in reach:
            self._route = self._cells_to(parent, self._goal_cell)
            self._phase = "execute"
            return self._drive(grid, move_ids)
        self._candidates = self._frontier_circuit(self._start_grid, reach)
        self._phase = "discover"
        return self._discover(grid, move_ids)

    def _discover(self, grid: Grid, move_ids: list[int]) -> int:
        p = self._player_cell(grid)
        if p is None:
            return self._explore(move_ids)
        self._track(p)

        # If a route to a candidate's plate cell is in flight, drive it.
        if self._route:
            while self._route and p == self._route[0]:
                self._route.pop(0)
            if self._route:
                if self._route_stuck >= _STUCK_TRIES:
                    # Could not step onto the (last) target — this candidate is a
                    # wall/barrier, not an enterable plate. Drop it.
                    self._route = []
                    self._route_stuck = 0
                    self._disc_cand = None
                else:
                    return self._hop(p, self._route[0], move_ids)

        # Route just finished. If we were probing a candidate, evaluate it.
        if self._disc_cand is not None:
            if p == self._disc_cand:
                floor_now = self._floor_cells(grid)
                opened = floor_now - self._floor_before
                if opened:
                    self._plate_cell = self._disc_cand
                    self._barrier = {c for c in opened if c != self._disc_cand}
                    self._phase = "press"
                    return self._decide(grid, move_ids, True)
                # enterable but opened nothing — not a useful plate
            self._disc_cand = None

        # Pick the next candidate and build a route: chamber path to the approach
        # cell, then one hop onto the candidate.
        while self._candidates:
            cand = self._candidates.pop(0)
            reach, parent = self._reachable(self._base_floor, p)
            approach = None
            for _a, (dr, dc) in _MOVE_VEC.items():
                nb = (cand[0] - dr, cand[1] - dc)
                if nb in reach:
                    approach = nb
                    break
            if approach is None:
                continue
            self._disc_cand = cand
            self._floor_before = self._floor_cells(grid)
            self._route = self._cells_to(parent, approach) + [cand]
            self._route_stuck = 0
            if self._route and p == self._route[0]:
                self._route.pop(0)
            if self._route:
                return self._hop(p, self._route[0], move_ids)
            return self._hop(p, cand, move_ids)

        self._phase = "explore"
        return self._explore(move_ids)

    def _settle(self, grid: Grid, move_ids: list[int]) -> int:
        """After ACTION5 the engine rewinds the player to start over several
        frames. Wait (issuing a wall-blocked nudge) until the player is back at
        the start cell, then build the gated route."""
        self._settle_tries += 1
        p = self._player_cell(grid)
        if p is not None and p == self._start_cell:
            self._prev_player = p
            self._moves_made = 0
            self._route = self._build_gated_route()
            if self._route:
                self._phase = "execute"
                return self._drive(grid, move_ids)
            self._phase = "explore"
            return self._explore(move_ids)
        if self._settle_tries > _SETTLE_MAX:
            self._phase = "explore"
        return move_ids[0]

    def _drive(self, grid: Grid, move_ids: list[int]) -> int:
        p = self._player_cell(grid)
        if p is None:
            return self._explore(move_ids)
        self._track(p)
        while self._route and p == self._route[0]:
            self._route.pop(0)
        if not self._route:
            if self._goal_cell is not None and p != self._goal_cell:
                return self._hop(p, self._goal_cell, move_ids)
            self._phase = "done"
            return move_ids[0]
        return self._hop(p, self._route[0], move_ids)

    # ── gated route plan (ghost seated on plate) ────────────────────────

    def _build_gated_route(self) -> list[Cell]:
        if self._start_cell is None or self._goal_cell is None:
            return []
        floor = self._base_floor
        barrier = self._barrier
        goal = self._goal_cell
        lg = self._lg

        def passable(cell: Cell, moves: int) -> bool:
            # ``moves`` is the move index this step WOULD become. The ghost seats
            # on the plate at the end of the player's Lg-th move, and the engine
            # validates the player's move BEFORE running the ghost's replay in
            # the same step — so a barrier cell is enterable only from the
            # (Lg+1)-th move onward (moves > lg), never on the Lg-th.
            if cell == goal:
                return True
            if cell in barrier:
                return moves > lg
            return cell in floor

        def successors(state: tuple[Cell, int]):
            cell, moves = state
            for a, (dr, dc) in _MOVE_VEC.items():
                nxt = (cell[0] + dr, cell[1] + dc)
                if passable(nxt, moves + 1):
                    yield a, (nxt, moves + 1)

        path = configuration_path(
            (self._start_cell, 0),
            lambda s: s[0] == goal,
            successors,
            max_states=_PLAN_BUDGET,
        )
        if not path:
            return []
        cells: list[Cell] = []
        cur = self._start_cell
        for a in path:
            dr, dc = _MOVE_VEC[a]
            cur = (cur[0] + dr, cur[1] + dc)
            cells.append(cur)
        return cells

    def _explore(self, move_ids: list[int]) -> int:
        self._explore_i += 1
        return move_ids[self._explore_i % len(move_ids)]
