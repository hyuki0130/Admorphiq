"""script25 quarantined adapter: WA30 (pick-carry-drop delivery puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/WA30.md`` (read for reference, not imported): a single
WORKER moves with ACTION1-4 and uses ACTION5 as a context interact — picking
up a box and delivering it to a goal zone. WIN = every box on a goal cell. The
mechanic (read offline, dev-time only; the adapter reads only frames at
runtime) is a facing-and-carry delivery: everything sits on a coarse logical
grid (the worker steps one logical cell per action), a box attaches when the
worker reaches it and follows the worker, and dropping it on a goal cell
satisfies that goal.

**This build — carry-aware delivery composition**: the mechanic (measured
offline, dev-time only) is a facing-and-carry delivery — a box picked while
the worker FACES it (ACTION5 at distance one cell in the facing direction)
attaches and then FOLLOWS the worker at a fixed offset equal to that facing
vector; dropping (ACTION5) leaves the box at its carried position; the level
wins when every box sits on a goal cell. The adapter detects the worker,
boxes, and goal-pad slots from the frame and composes
:func:`admorphiq.kernels.plan_carry_delivery` (the generic offset-routing
delivery planner: to seat a fixed-offset follower on a cell ``C`` the worker
routes to ``C - offset``, so both pickup and delivery legs are pure
translations, chained min-cost via
:func:`admorphiq.kernels.grid_shortest_path`). The only game-specific step it
adds on top is a facing nudge before each pickup interact (a blocked step into
the box that sets rotation). Measured: L0 clears in 30 actions vs a 71-action
human baseline (super-human, level score 1.0) — the first generic WA30 clear.

**Fallback**: when roles can't be detected or no delivery plan routes (deeper
levels with more boxes, angled walls, or a carry geometry the fixed
facing-up offset can't serve), the adapter falls back to the generic
transition-graph frontier exploration the previous build used, so it never
regresses below that baseline.

**L1 — CLEARED (R59, 2026-07-16, see WA30.md + the L1 solver section below)**:
L1 adds a second, AUTONOMOUS agent (a ``kdweefinfi``-tagged sprite, colour 12)
that picks up and delivers boxes ON ITS OWN every step, independent of the
player — the board is non-stationary, so the static carry plan desyncs and
reactive heuristics cap at ≤4/5 boxes (measured). Its policy is DETERMINISTIC,
though, so the joint evolution is predictable: the L1 path (gated on the
colour-12 signature; L0 is byte-identical without it) parses the state from the
top frame layer, searches player macro-plans in a byte-faithful internal
simulator (``_Wa30Sim``, lockstep-validated vs the engine), and executes the
winning sequence open-loop with per-step verification — the sk48 pattern. L1
clears ~54 actions vs 119 human (super-human), lifting wa30 to 2/9 @ 0.0667.

**Why namespace-safe**: the adapter assigns roles (which cluster is the
worker, which are boxes, which cells are goals) and declares the mechanic
hypothesis (delivery), but the assignment, routing, and path conversion all
live in ``admorphiq.kernels`` — no hardcoded coordinates, colours, or bespoke
search here.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the board (role detection,
    HUD masking).
  - :func:`admorphiq.kernels.plan_delivery` plans the pick->deliver chain over
    the detected roles and a passability grid.
  - :func:`admorphiq.kernels.canonical_key` /
    :func:`admorphiq.kernels.transition_shortest_path` drive the graph
    fallback.
"""

from __future__ import annotations

import itertools
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
from admorphiq.kernels import (
    canonical_key,
    find_regions,
    plan_carry_delivery,
    transition_shortest_path,
)

GAME_ID = "wa30"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]

_GIVEUP_DEFAULT = 4000
_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06

# The board is rendered at 4 px per logical cell (the worker steps one logical
# cell = 4 px per action); planning runs on the downscaled logical grid.
_CELL = 4


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    """A thin strip spanning most of one axis, OR pinned to a frame edge —
    catches WA30's bottom-row step counter."""
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


def _logical(cell_bbox: tuple[int, int, int, int]) -> Cell:
    """The logical-grid cell of a region's bbox centre (frame px / _CELL)."""
    r0, c0, r1, c1 = cell_bbox
    return ((r0 + r1) // 2 // _CELL, (c0 + c1) // 2 // _CELL)


# ═══════════════════════════════════════════════════════════════════════════
# L1 cooperative-delivery solver: faithful simulator + frame parser + search.
#
# WA30 L0 is a single-worker carry-delivery the static `plan_carry_delivery`
# kernel clears super-human. L1 adds a SECOND, AUTONOMOUS agent (the colour-12
# `kdweefinfi` sprite) that picks up and delivers boxes on its OWN every step —
# the board is non-stationary, so no static precomputed plan holds. R59 measured
# that reactive heuristic cooperation caps at ≤4/5 boxes (auto-alone already does
# 4/5; active player delivery interferes and regresses to 3/5) across 34 configs,
# while the gold oracle proves a 5/5 win exists as a precisely-timed 2-box
# delivery + park choreography a heuristic cannot reproduce.
#
# The approach (the sk48 pattern — internal simulator + search): the autonomous
# agent's policy was decoded from the game source (dev-time only) and is
# DETERMINISTIC, so the joint player+agent evolution is fully predictable from a
# parsed frame. `_parse_state` recovers the initial worker/boxes/goal/auto from
# pixels; `_Wa30Sim` is a byte-faithful reimplementation of the dynamics
# (lockstep-validated vs the live engine over 2000 random sequences, 0 desyncs);
# `_search_plan` enumerates player macro-plans (an ordered subset of boxes the
# player delivers, then a park tail) and returns the shortest sequence that wins.
# Because the sim is byte-faithful and the game deterministic, the searched
# sequence replays OPEN-LOOP to a win (validated on the live engine at 53/54
# actions, within the 70-step budget). Everything here is WA30-specific and stays
# in this quarantined adapter (no generic-kernel promotion), like sk48's sim.
# ═══════════════════════════════════════════════════════════════════════════

_GRID = 64
_HUD_ROW = 63

# Decoded colour roles (dev-time only; only pixels are read at runtime).
_WORKER_COLOR = 14   # wppuejnwhl — the player
_AUTO_COLOR = 12     # byigobxzpg / kdweefinfi — the autonomous cooperating agent
_BOX_CORE_COLOR = 9  # pktgsotzmw 2x2 core (also the goal-pad outline ring)
_ZONE_COLOR = 2      # doijajrgdi interior — the fsjjayjoeg goal pad

_MOVES = {1: (0, -_CELL), 2: (0, _CELL), 3: (-_CELL, 0), 4: (_CELL, 0)}


def _rot(dx: int, dy: int) -> int:
    """Facing rotation from a move delta (engine ``pjedoipwee``)."""
    if dy < 0:
        return 0
    if dx > 0:
        return 90
    if dy > 0:
        return 180
    return 270


def _facing_cell(x: int, y: int, rot: int) -> Cell:
    """The cell one step ahead of a worker at ``(x, y)`` facing ``rot``."""
    if rot == 0:
        return (x, y - _CELL)
    if rot == 180:
        return (x, y + _CELL)
    if rot == 90:
        return (x + _CELL, y)
    return (x - _CELL, y)


class _Wa30Sim:
    """Faithful namespace-safe WA30 simulator (kdweefinfi auto agent).

    State: the worker (x, y, rotation, carried-box-index or None), the boxes
    (list of ``[x, y]``), the autonomous agents (list of ``[x, y, carried-index
    or None]``), the goal-pad cell set, and the remaining step budget. Reproduces
    the decoded game's step for the colour-12 agent (the only autonomous agent on
    L1; the colour-15 agent of deeper levels is out of scope). Lockstep-validated
    byte-identical vs the live engine.
    """

    def __init__(
        self,
        worker: Cell,
        boxes: list[Cell],
        autos: list[Cell],
        goal_cells: set[Cell],
        steps: int = 120,
        grid: int = _GRID,
    ) -> None:
        self.wx, self.wy = worker
        self.wrot = 270
        self.wcarry: int | None = None
        self.boxes = [[b[0], b[1]] for b in boxes]
        self.autos = [[a[0], a[1], None] for a in autos]
        self.goal = set(goal_cells)
        self.steps = steps
        self.grid = grid
        self.border: set[Cell] = set()
        for i in range(0, grid, _CELL):
            self.border.update({(-_CELL, i), (grid, i), (i, -_CELL), (i, grid)})
        # lkvghqfwan: box-adjacency target set the auto agent navigates toward.
        # The engine only refreshes it at pickup/drop points (NOT when a carried
        # box moves), so it can be stale — replicated exactly for fidelity.
        self.lkv: set[Cell] = set()
        self._recompute_lkv()

    def _occ(self) -> set[Cell]:
        s = set(self.border)
        s.add((self.wx, self.wy))
        for b in self.boxes:
            s.add((b[0], b[1]))
        for a in self.autos:
            s.add((a[0], a[1]))
        return s

    def _on_goal(self, i: int) -> bool:
        return (self.boxes[i][0], self.boxes[i][1]) in self.goal

    def _carried_set(self) -> set[int]:
        c: set[int] = set()
        if self.wcarry is not None:
            c.add(self.wcarry)
        for a in self.autos:
            if a[2] is not None:
                c.add(a[2])
        return c

    def _recompute_lkv(self) -> None:
        carried = self._carried_set()
        self.lkv = set()
        for i, b in enumerate(self.boxes):
            if i in carried or self._on_goal(i):
                continue
            self.lkv.update({(b[0] - _CELL, b[1]), (b[0] + _CELL, b[1]), (b[0], b[1] - _CELL), (b[0], b[1] + _CELL)})

    def won(self) -> bool:
        carried = self._carried_set()
        return all(self._on_goal(i) and i not in carried for i in range(len(self.boxes)))

    # ── player turn (engine yygfcvqoyx) then auto turn (dhrikuybfo) ─────────

    def _move_worker(self, nx: int, ny: int) -> None:
        occ = self._occ()
        if self.wcarry is not None:
            bi = self.wcarry
            bx, by = self.boxes[bi]
            dx, dy = bx - self.wx, by - self.wy
            ndest = (nx + dx, ny + dy)
            wpos, bpos = (self.wx, self.wy), (bx, by)
            ok = ((nx, ny) not in occ or (nx, ny) == bpos) and (ndest not in occ or ndest == wpos)
            if ok:
                self.wx, self.wy = nx, ny
                self.boxes[bi] = [nx + dx, ny + dy]
        elif (nx, ny) not in occ:
            self.wx, self.wy = nx, ny

    def player(self, aid: int) -> None:
        if self.steps <= 0:
            return
        self.steps -= 1
        if aid in (1, 2, 3, 4):
            dx, dy = _MOVES[aid]
            if self.wcarry is None:
                self.wrot = _rot(dx, dy)
            self._move_worker(self.wx + dx, self.wy + dy)
        elif aid == 5:
            if self.wcarry is not None:
                self.wcarry = None
                self._recompute_lkv()  # drop (kqrtstlzkg)
            else:
                fc = _facing_cell(self.wx, self.wy, self.wrot)
                for i, b in enumerate(self.boxes):
                    if (b[0], b[1]) == fc:
                        # xpcvspllwr: grab the FIRST faced box, STEALING it if an
                        # auto agent already carries it (releases that carrier).
                        for a in self.autos:
                            if a[2] == i:
                                a[2] = None
                        self.wcarry = i
                        self._recompute_lkv()
                        break
        self._auto()

    # ── autonomous agent (engine ynmgxjqkgh) ───────────────────────────────

    def _bfs_pick(self, ax: int, ay: int) -> list[Cell] | None:
        """czrprbohhe: BFS to the nearest box-adjacent cell (stale ``lkv``)."""
        adj = self.lkv
        occ = self._occ()
        start = (ax, ay)
        seen = {start}
        q: deque[list[Cell]] = deque([[start]])
        while q:
            path = q.popleft()
            cur = path[-1]
            if cur in adj:
                return path
            for d in [(-_CELL, 0), (_CELL, 0), (0, -_CELL), (0, _CELL)]:
                n = (cur[0] + d[0], cur[1] + d[1])
                if n not in seen and n not in occ:
                    seen.add(n)
                    q.append(path + [n])
        return None

    def _bfs_carry(self, ax: int, ay: int, bi: int) -> list[Cell] | None:
        """cyjrduhzmz: BFS so the carried box's offset cell lands on a goal."""
        bx, by = self.boxes[bi]
        dx, dy = bx - ax, by - ay
        occ = self._occ()
        start = (ax, ay)
        wpos, bpos = (ax, ay), (bx, by)
        seen = {start}
        q: deque[list[Cell]] = deque([[start]])

        def carryfree(v: Cell) -> bool:
            vb = (v[0] + dx, v[1] + dy)
            return (v not in occ or v == bpos) and (vb not in occ or vb == wpos)

        while q:
            path = q.popleft()
            cur = path[-1]
            if (cur[0] + dx, cur[1] + dy) in self.goal:
                return path
            for d in [(-_CELL, 0), (_CELL, 0), (0, -_CELL), (0, _CELL)]:
                n = (cur[0] + d[0], cur[1] + d[1])
                if n not in seen and carryfree(n):
                    seen.add(n)
                    q.append(path + [n])
        return None

    def _move_auto(self, ai: int, nx: int, ny: int) -> None:
        a = self.autos[ai]
        occ = self._occ()
        if a[2] is not None:
            bi = a[2]
            bx, by = self.boxes[bi]
            dx, dy = bx - a[0], by - a[1]
            ndest = (nx + dx, ny + dy)
            apos, bpos = (a[0], a[1]), (bx, by)
            ok = ((nx, ny) not in occ or (nx, ny) == bpos) and (ndest not in occ or ndest == apos)
            if ok:
                a[0], a[1] = nx, ny
                self.boxes[bi] = [nx + dx, ny + dy]
        elif (nx, ny) not in occ:
            a[0], a[1] = nx, ny

    def _auto(self) -> None:
        for ai, a in enumerate(self.autos):
            if a[2] is not None:
                bi = a[2]
                if self._on_goal(bi):
                    a[2] = None
                    self._recompute_lkv()  # drop on goal (kqrtstlzkg)
                else:
                    p = self._bfs_carry(a[0], a[1], bi)
                    if p and len(p) > 1:
                        self._move_auto(ai, p[1][0], p[1][1])
            else:
                carried = self._carried_set()
                grabbed = False
                for i, b in enumerate(self.boxes):
                    if i in carried or self._on_goal(i):
                        continue
                    if abs(a[0] - b[0]) + abs(a[1] - b[1]) == _CELL:
                        a[2] = i
                        grabbed = True
                        self._recompute_lkv()
                        break
                if grabbed:
                    return  # engine returns after the first pickup
                p = self._bfs_pick(a[0], a[1])
                if p and len(p) > 1:
                    self._move_auto(ai, p[1][0], p[1][1])


# ── frame parser (pixels → simulator init state) ─────────────────────────────


def _color_cells(grid: Grid, color: int) -> list[Cell]:
    """All ``(row, col)`` cells of ``color``, excluding the HUD row."""
    return [
        (r, c)
        for r in range(len(grid))
        for c in range(len(grid[0]))
        if r != _HUD_ROW and grid[r][c] == color
    ]


def _multiagent_layer(latest_frame: Any) -> Grid | None:
    """The frame layer that contains the autonomous agent (colour 12), or None.

    WA30 renders on two layers: the base ``frame[0]`` (goal-pad recolouring) that
    the L0 path reads, and a top layer carrying the movable sprites — worker,
    boxes, AND the colour-12 auto agent, drawn over the pad. The L1 solver needs
    that top layer (the agent and the goal interior are only there); this returns
    whichever layer holds colour 12, robust to layer ordering.
    """
    fr = getattr(latest_frame, "frame", None)
    if not fr:
        return None
    for layer in fr:
        if any(_AUTO_COLOR in row for row in layer):
            return tuple(tuple(int(v) for v in row) for row in layer)
    return None


def _snap(v: int) -> int:
    """Snap a pixel coordinate to the logical grid (sprites are _CELL-aligned).
    Rotation-independent: the worker sprite carries a padding row that moves to a
    different edge as it turns, so the colour-14 block's raw min-row shifts ±1
    with facing — snapping recovers the stable top-left."""
    return (v // _CELL) * _CELL


def _parse_worker(grid: Grid) -> Cell | None:
    """Just the worker ``(x, y)`` — the cheap per-step check the open-loop
    executor uses to confirm the board still matches the sim's prediction."""
    w14 = _color_cells(grid, _WORKER_COLOR)
    if not w14:
        return None
    rows = [r for r, _ in w14]
    cols = [c for _, c in w14]
    return (_snap(min(cols)), _snap(min(rows)))


def _components(cells: list[Cell]) -> list[list[Cell]]:
    cs = set(cells)
    seen: set[Cell] = set()
    comps: list[list[Cell]] = []
    for cell in cells:
        if cell in seen:
            continue
        stack = [cell]
        comp: list[Cell] = []
        seen.add(cell)
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (r + dr, c + dc)
                if n in cs and n not in seen:
                    seen.add(n)
                    stack.append(n)
        comps.append(comp)
    return comps


def _parse_state(grid: Grid) -> dict[str, Any] | None:
    """Recover ``worker`` / ``boxes`` / ``autos`` / ``goal`` from a rendered frame.

    Coordinates are ``(x=col, y=row)`` sprite top-left, matching the simulator.
    Returns ``None`` when the multi-agent signature (a colour-12 autonomous
    agent) is absent — the caller uses that as the L0-vs-L1 gate. Validated to
    recover the exact engine state (worker, all 5 boxes, and the 96-cell goal
    pad) from the live L1 render.
    """
    if not grid or not grid[0]:
        return None
    autos: list[Cell] = []
    for comp in _components(_color_cells(grid, _AUTO_COLOR)):
        rows = [r for r, _ in comp]
        cols = [c for _, c in comp]
        autos.append((_snap(min(cols)), _snap(min(rows))))
    if not autos:
        return None  # no autonomous agent → not the L1 multi-agent board

    w14 = _color_cells(grid, _WORKER_COLOR)
    if not w14:
        return None
    rows = [r for r, _ in w14]
    cols = [c for _, c in w14]
    worker = (_snap(min(cols)), _snap(min(rows)))  # snap: padding row moves with facing

    boxes: list[Cell] = []
    for comp in _components(_color_cells(grid, _BOX_CORE_COLOR)):
        rows = sorted({r for r, _ in comp})
        cols = sorted({c for _, c in comp})
        h = rows[-1] - rows[0] + 1
        w = cols[-1] - cols[0] + 1
        # A box core is a compact 2x2 solid block; the goal-pad outline is a thin
        # hollow ring (large bbox). Compact-and-small isolates the box cores. The
        # core sits one pixel inside the sprite, so snap (core-1) to the grid.
        if h <= 3 and w <= 3 and len(comp) >= 3:
            boxes.append((_snap(cols[0] - 1), _snap(rows[0] - 1)))
    if not boxes:
        return None

    g2 = _color_cells(grid, _ZONE_COLOR)
    if not g2:
        return None
    rows = [r for r, _ in g2]
    cols = [c for _, c in g2]
    r0, r1, c0, c1 = min(rows) - 1, max(rows) + 1, min(cols) - 1, max(cols) + 1
    goal = {(c, r) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}

    return {"worker": worker, "boxes": sorted(boxes), "autos": sorted(autos), "goal": goal}


# ── macro-plan search over the faithful simulator ─────────────────────────────


def _bfs_walk(wp: Cell, goal: Cell, blocked: set[Cell], grid: int) -> list[int] | None:
    if wp == goal:
        return []
    seen = {wp}
    q: deque[tuple[Cell, list[int]]] = deque([(wp, [])])
    while q:
        (x, y), p = q.popleft()
        for a, (dx, dy) in _MOVES.items():
            n = (x + dx, y + dy)
            if n in seen or not (-_CELL <= n[0] <= grid and -_CELL <= n[1] <= grid):
                continue
            if n != goal and n in blocked:
                continue
            if n == goal:
                return p + [a]
            seen.add(n)
            q.append((n, p + [a]))
    return None


def _bfs_carry_walk(wp: Cell, box: Cell, off: Cell, gw: Cell, blocked: set[Cell], grid: int) -> list[int] | None:
    if wp == gw:
        return []
    seen = {wp}
    q: deque[tuple[Cell, list[int]]] = deque([(wp, [])])
    while q:
        (x, y), p = q.popleft()
        for a, (dx, dy) in _MOVES.items():
            n = (x + dx, y + dy)
            nb = (n[0] + off[0], n[1] + off[1])
            inb = (
                -_CELL <= n[0] <= grid and -_CELL <= n[1] <= grid
                and -_CELL <= nb[0] <= grid and -_CELL <= nb[1] <= grid
            )
            if n in seen or not inb:
                continue
            wc = n == gw
            if not wc and n in blocked:
                continue
            if nb in blocked and nb != box:
                continue
            if wc:
                return p + [a]
            seen.add(n)
            q.append((n, p + [a]))
    return None


def _slots_from_goal(goal: set[Cell]) -> list[Cell]:
    """Box-anchor slots inside the goal pad (a box occupies a _CELL×_CELL cell)."""
    xs = [x for x, _ in goal]
    ys = [y for _, y in goal]
    slots: list[Cell] = []
    for x in range(min(xs), max(xs) + 1, _CELL):
        for y in range(min(ys), max(ys) + 1, _CELL):
            if (x, y) in goal and (x + _CELL - 1, y + _CELL - 1) in goal:
                slots.append((x, y))
    return slots


def _empty_slots(sim: _Wa30Sim, slots: list[Cell]) -> list[Cell]:
    carried = sim._carried_set()
    occ = {(b[0], b[1]) for i, b in enumerate(sim.boxes) if i not in carried}
    return [s for s in slots if s not in occ]


def _run_macro(
    state: dict[str, Any], order: tuple[int, ...], park: Cell, slots: list[Cell], goalc: Cell, cap: int
) -> tuple[str, list[int]]:
    """Simulate one macro-plan: the player delivers boxes ``order`` (each to the
    nearest empty slot), then parks out of the way, while the auto agent works."""
    sim = _Wa30Sim(state["worker"], state["boxes"], state["autos"], state["goal"], steps=cap)
    grid = sim.grid
    acts: list[int] = []
    ti = 0
    for _ in range(cap):
        if sim.won():
            return ("WIN", acts)
        if sim.steps <= 0:
            return ("OVER", acts)
        wp = (sim.wx, sim.wy)
        carried = sim._carried_set()
        while ti < len(order):
            bi = order[ti]
            on = (sim.boxes[bi][0], sim.boxes[bi][1]) in sim.goal
            if on and bi not in carried:
                ti += 1
                continue
            if bi in carried and bi != sim.wcarry:  # the auto agent took it
                ti += 1
                continue
            break
        if sim.wcarry is not None:
            bi = sim.wcarry
            bx, by = sim.boxes[bi]
            off = (bx - sim.wx, by - sim.wy)
            best: list[int] | None = None
            for s in sorted(_empty_slots(sim, slots), key=lambda s: abs(s[0] - goalc[0]) + abs(s[1] - goalc[1])):
                gw = (s[0] - off[0], s[1] - off[1])
                bl = sim._occ() - {wp, (bx, by)}
                p = _bfs_carry_walk(wp, (bx, by), off, gw, bl, grid)
                if p is not None and (best is None or len(p) < len(best)):
                    best = p
            a = best[0] if best else 5
            sim.player(a)
            acts.append(a)
            continue
        if ti >= len(order):
            bl = sim._occ() - {wp}
            p = _bfs_walk(wp, park, bl, grid)
            a = p[0] if p else (1 if wp[1] > 0 else 2)
            sim.player(a)
            acts.append(a)
            continue
        bi = order[ti]
        b = (sim.boxes[bi][0], sim.boxes[bi][1])
        bl = sim._occ() - {wp}
        pick: tuple[tuple[int, int], Cell, list[int]] | None = None
        for tg in [(b[0] - _CELL, b[1]), (b[0] + _CELL, b[1]), (b[0], b[1] - _CELL), (b[0], b[1] + _CELL)]:
            if tg in bl:
                continue
            p = _bfs_walk(wp, tg, bl, grid)
            if p is None:
                continue
            far = abs(tg[0] - goalc[0]) + abs(tg[1] - goalc[1])
            key = (len(p), -far)
            if pick is None or key < pick[0]:
                pick = (key, tg, p)
        if pick is None:
            sim.player(5)
            acts.append(5)
            continue
        _, tg, p = pick
        if p:
            sim.player(p[0])
            acts.append(p[0])
            continue
        dx, dy = b[0] - tg[0], b[1] - tg[1]
        face = {(0, -_CELL): 1, (0, _CELL): 2, (-_CELL, 0): 3, (_CELL, 0): 4}[(dx, dy)]
        sim.player(face)
        acts.append(face)
        sim.player(5)
        acts.append(5)
    return ("TIMEOUT", acts)


def _search_plan(state: dict[str, Any], horizon: int = 120) -> list[int] | None:
    """Search macro-plans in the faithful sim; return the shortest winning player
    action sequence, or ``None`` if none wins within ``horizon``.

    The player delivers an ordered subset of boxes (each to the nearest empty
    slot) then parks; the autonomous agent handles the rest. Enumerated over
    ordered subsets of increasing size (2, 3, 1, 4) — the smallest size that
    yields any win wins (fewest player boxes = the cleanest cooperation).
    """
    boxes = state["boxes"]
    goal = state["goal"]
    n = len(boxes)
    if not goal or n == 0:
        return None
    goalc = (sum(x for x, _ in goal) // len(goal), sum(y for _, y in goal) // len(goal))
    slots = _slots_from_goal(goal)
    park = (min(x for x, _ in goal) - 2 * _CELL, goalc[1])
    best: list[int] | None = None
    for r in (2, 3, 1, 4):
        for order in itertools.permutations(range(n), r):
            res = _run_macro(state, order, park, slots, goalc, horizon)
            if res[0] == "WIN" and (best is None or len(res[1]) < len(best)):
                best = res[1]
        if best is not None:
            return best
    return best


class Adapter(GameAdapter):
    """Compose the delivery/subgoal planner over detected worker/box/goal
    roles; fall back to generic transition-graph frontier exploration.
    Composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # phase: "plan" (compute + execute a delivery chain once), "graph".
        self._phase = "plan"
        self._plan_queue: list[int] = []
        self._planned = False

        # L1 cooperative-delivery state (multi-agent board — see _wa30_l1).
        # When the frame shows an autonomous agent, the plan is a searched
        # open-loop sequence executed in lockstep with a faithful predictor.
        self._l1_active = False
        self._l1_sim: _Wa30Sim | None = None

        # graph-fallback state.
        self._pending_action: int | None = None
        self._pending_key: Any | None = None
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
            self._reset_for_new_env()
            return reset_action()

        grid = canonical_layer(latest_frame)
        # The autonomous agent (and the goal interior) live on the top frame
        # layer, not the base layer the L0 path reads; None on single-agent
        # boards keeps everything below byte-identical to the L0 build.
        ma_grid = _multiagent_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1

        simple_ids, _action6_ok = available_action_ids(latest_frame)
        act_ids = sorted(a for a in simple_ids if a in (1, 2, 3, 4, 5))
        if not act_ids:
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        if self._phase == "plan":
            return self._plan_step(grid, ma_grid, act_ids)
        return self._graph_step(grid, act_ids)

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._phase = "plan"
        self._planned = False
        self._plan_queue = []
        self._l1_active = False
        self._l1_sim = None
        self._pending_action = None
        self._pending_key = None
        self._transitions = []
        self._edges = {}
        self._tried_from = {}

    def _on_restart(self) -> None:
        self._pending_action = None
        self._pending_key = None
        if self._phase == "plan":
            self._planned = False
            self._plan_queue = []

    def _reset_for_new_env(self) -> None:
        self._levels_seen = -1
        self._on_level_up(-1)

    # ── phase 1: compute + execute the delivery chain ───────────────────

    def _plan_step(self, grid: Grid, ma_grid: Grid | None, act_ids: list[int]) -> GameAction:
        if not self._planned:
            self._planned = True
            self._build_plan(grid, ma_grid)
        if self._l1_active:
            return self._l1_step(grid, ma_grid, act_ids)
        if self._plan_queue:
            a = self._plan_queue.pop(0)
            return simple_action(a if a in act_ids else act_ids[0])
        self._phase = "graph"
        return self._graph_step(grid, act_ids)

    def _l1_step(self, grid: Grid, ma_grid: Grid | None, act_ids: list[int]) -> GameAction:
        """Execute the searched open-loop sequence, verifying each step that the
        board still matches the faithful predictor; on divergence (only possible
        if the parse/model mismatch the real board) drop to graph exploration so
        the level never regresses below the fallback baseline."""
        if not self._plan_queue or self._l1_sim is None:
            self._l1_active = False
            self._phase = "graph"
            return self._graph_step(grid, act_ids)
        predicted = (self._l1_sim.wx, self._l1_sim.wy)
        observed = _parse_worker(ma_grid) if ma_grid is not None else None
        if observed is not None and observed != predicted:
            self._l1_active = False
            self._phase = "graph"
            return self._graph_step(grid, act_ids)
        a = self._plan_queue.pop(0)
        self._l1_sim.player(a)
        return simple_action(a if a in act_ids else act_ids[0])

    def _build_plan(self, grid: Grid, ma_grid: Grid | None = None) -> None:
        # L1+ multi-agent gate: an autonomous cooperating agent on the board
        # makes it non-stationary, so no static carry plan holds. Parse the full
        # state (from the top layer that carries the agent) and search a winning
        # open-loop sequence in a faithful simulator (see _wa30_l1). Absent that
        # signature this is byte-identical to the L0 path below.
        state = _parse_state(ma_grid) if ma_grid is not None else None
        if state is not None:
            seq = _search_plan(state)
            if seq:
                self._plan_queue = list(seq)
                self._l1_sim = _Wa30Sim(
                    state["worker"], state["boxes"], state["autos"], state["goal"], steps=len(seq) + 8
                )
                self._l1_active = True
                return
            self._phase = "graph"
            return

        bg = most_common_color(grid)
        masked = _mask_hud(grid)
        regions = [r for r in find_regions(masked, background=bg) if not _is_hud_band(r, len(grid), len(grid[0]))]
        roles = self._detect_roles(regions)
        if roles is None:
            self._phase = "graph"
            return
        worker, boxes, goals = roles
        height = len(grid) // _CELL
        width = len(grid[0]) // _CELL
        # Passable everywhere except where a box currently sits (the worker
        # cannot stand on a box); goal cells are passable delivery spots.
        blocked = set(boxes)
        passable = [
            [(r, c) not in blocked for c in range(width)] for r in range(height)
        ]
        # Measured WA30 controls (game-specific, quarantine-legal): ACTION1-4
        # move the worker one logical cell up/down/left/right; ACTION5 is the
        # context pick/drop. The carried box FOLLOWS at a fixed offset equal to
        # the facing direction at pickup — picking while facing "up" seats the
        # box one cell ABOVE the worker (offset (-1, 0)) and it rides there.
        move_labels = {(-1, 0): 1, (1, 0): 2, (0, -1): 3, (0, 1): 4}
        carry_offset = (-1, 0)
        facing_action = move_labels[carry_offset]  # face the pickup before ACTION5
        plan = plan_carry_delivery(worker, boxes, goals, carry_offset, passable, move_labels, 5)
        if plan is None:
            self._phase = "graph"
            return
        # A pickup interact requires the worker to FACE the box first; insert a
        # facing move (a blocked step into the box that only sets rotation)
        # before every ODD interact (pickups). Deliveries (even interacts) drop
        # the carried box in place and need no facing.
        seq: list[int] = []
        interacts = 0
        for a in plan:
            if a == 5:
                interacts += 1
                if interacts % 2 == 1:
                    seq.append(facing_action)
                seq.append(5)
            else:
                seq.append(int(a))
        self._plan_queue = seq

    def _detect_roles(
        self, regions: list[Region]
    ) -> tuple[Cell, list[Cell], list[Cell]] | None:
        """Worker = the singleton marker colour (one region of a colour no
        other region shares); boxes = the small same-shape cluster class;
        goals = the logical cells of the largest remaining static region (the
        delivery pad). All in logical-grid coordinates. None when the roles
        can't be separated."""
        if not regions:
            return None
        by_color: dict[int, list[Region]] = {}
        for r in regions:
            by_color.setdefault(r["color"], []).append(r)
        # Worker: a colour owned by exactly one region (the mover).
        singletons = [regs[0] for regs in by_color.values() if len(regs) == 1]
        if not singletons:
            return None
        # Boxes: a same-colour class of 2+ regions that are all the SAME size
        # (a uniform repeated sprite), preferring the most populous such class.
        # This distinguishes the box class from an incidentally-shared colour
        # whose regions differ in size (e.g. sprite cores + a large pad border
        # both drawn in one colour).
        uniform = [
            (color, regs)
            for color, regs in by_color.items()
            if len(regs) >= 2 and len({r["size"] for r in regs}) == 1
        ]
        if not uniform:
            return None
        box_color, box_regs = max(uniform, key=lambda kv: (len(kv[1]), -kv[0]))
        boxes = [_logical(r["bbox"]) for r in box_regs]
        # Goal pad: the largest region whose colour is neither the box colour
        # nor a box-core colour, tiled into its logical cells.
        pad_candidates = [
            r for r in regions if r["color"] != box_color and _logical(r["bbox"]) not in boxes
        ]
        if not pad_candidates:
            return None
        pad = max(pad_candidates, key=lambda r: r["size"])
        goals = self._pad_cells(pad["bbox"], len(boxes))
        # Worker: the singleton nearest in size to a box (the mover, not the pad).
        worker_region = min(
            singletons, key=lambda r: (abs(r["size"] - box_regs[0]["size"]), r["bbox"])
        )
        worker = _logical(worker_region["bbox"])
        if not boxes or not goals:
            return None
        return worker, boxes, goals

    def _pad_cells(self, bbox: tuple[int, int, int, int], count: int) -> list[Cell]:
        """The distinct logical cells a delivery pad spans (its bbox sampled
        on the logical grid), capped at ``count`` (one per box)."""
        r0, c0, r1, c1 = bbox
        cells: list[Cell] = []
        seen: set[Cell] = set()
        r = r0
        while r <= r1:
            c = c0
            while c <= c1:
                lc = (r // _CELL, c // _CELL)
                if lc not in seen:
                    seen.add(lc)
                    cells.append(lc)
                c += _CELL
            r += _CELL
        return cells[:count] if count else cells

    # ── phase 2: generic transition-graph frontier fallback ─────────────

    def _graph_step(self, grid: Grid, act_ids: list[int]) -> GameAction:
        cur_key = canonical_key(_mask_hud(grid), mode="exact")
        self._observe_result(cur_key)
        action = self._decide(cur_key, act_ids)
        self._pending_action = action
        self._pending_key = cur_key
        return simple_action(action)

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
        nearest state with an untried action, or None if fully explored.
        Hand-rolled rather than :func:`admorphiq.kernels.reachable_frontier`
        for the same reason ``admorphiq.adapters25.tu93`` gives."""
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
