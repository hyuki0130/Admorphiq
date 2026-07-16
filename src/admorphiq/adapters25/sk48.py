"""script25 quarantined adapter: SK48 (snake shape / pattern-matching puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/SK48.md`` (read for reference, not imported) and this
file's own history record SK48 as a snake SHAPE / PATTERN-MATCHING puzzle,
NOT a plain eat-food snake. Reading the game source offline
(``environment_files/sk48/*/sk48.py``; dev-time only, the adapter reads only
frames at runtime) decoded the full rule set:

- The board is split by a row-53 divider into a TOP arena (controllable
  snake(s) + a row of coloured target cells) and a BOTTOM TEMPLATE (each
  controllable snake's partner snake, whose body overlaps its own coloured
  cells — the pattern to reproduce).
- ACTION1-4 move the ACTIVE snake: pressing its facing direction GROWS a head
  segment at the anchored tail, pressing the reverse RETRACTS the front, and a
  side press PUSHES the whole body sideways (allowed only where a side-push
  gate ``irkeobngyh`` sits, via an intricate segment/target-cell push
  recursion ``bnrdrdiakd``). ACTION6 selects which snake is active; ACTION7
  UNDOES the last move (a free, budget-costless back-edge).
- WIN (the engine's ``gvtmoopqgy``): every controllable snake must be shaped
  so the ordered colours of the target cells its body overlaps match its
  template partner's colour sequence, segment for segment.
- Each level grants a fixed 196-move budget; exhausting it LOSES.

**Why the online frame-only explorer banked at 0/8 (measured R56):** the win
progress IS frame-visible but SPARSE (matched segments light a checkmark only
near completion — gold L0 stays flat 0 matches for 8 of 13 moves), so a greedy
/ frontier search over any frame-derived score has no gradient. That is why
the transition-graph explorer (kept here as the FALLBACK) clears nothing.

**The tractable path, now BUILT (this file):** a FAITHFUL OFFLINE SIMULATOR of
the grow/retract/push semantics + A* toward the EXACT internal template-match
goal (computed in-simulator, sidestepping the sparse-signal wall). The
simulator was validated in lockstep against the live engine internals (gold L0
13-move replay + ~900 random moves, zero divergence; L0-L4 solutions replayed
to real engine wins). At runtime the adapter reconstructs the simulator state
from the frame alone (:func:`_parse_state`), searches offline, and executes the
found move sequence, re-planning per level. It is GATED: if the frame parse or
search fails, it falls back to the transition-graph explorer, preserving the
0/8 floor.

**The colour-5-bordered edge snakes (:func:`_parse_heads`, R56b).** From
agent-L2 (source ``Level 3``) on, levels add a partner-LESS obstacle snake whose
head (``xtuqlbebvk``/``zkekdulqku``) renders with a background-colour border, so
only its 2x2 colour-10/11 CENTRE block shows. The engine pairs snakes by that
centre pixel (== the border colour for the visible ``ejlpqgojjt``/``udbuodqlxv``
heads), so ``_parse_heads`` detects both renderings and the body walk
reconstructs the obstacle; ``active`` is pinned to a CONTROLLABLE (partnered)
head so A* moves the right snake. The floor rect is recovered as the largest
colour-4 CONNECTED COMPONENT's bbox (:func:`_parse_arena`) because those
obstacle snakes + target cells occlude the floor's top/interior, defeating the
old per-row-run scan.

**Measured (R56 dedicated session, 2026-07-15):** frame-parsed sim+search
clears **L0 (14 moves, human 61) + L1 (31 moves, human 177) + L2 (36 moves,
human 101)** — all SUPER-HUMAN, 3/8, game_score 0.1667 (deterministic x2). The
remaining wall is ACTION6 MULTI-SNAKE selection: agent-L3+ (source ``Level 4``
on) have TWO+ controllable snakes each matching its own template, so a
single-active-snake A* cannot win; the parse succeeds but search gates to the
explorer, and modelling snake selection in the search is a separate round.

Composition from ``admorphiq.kernels`` (fallback explorer only):
  - :func:`admorphiq.kernels.find_regions` masks the edge/divider HUD bands.
  - :func:`admorphiq.kernels.canonical_key` hashes the masked board.
  - :func:`admorphiq.kernels.transition_shortest_path` routes over the
    incrementally-discovered transition graph.
"""

from __future__ import annotations

import heapq
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

GAME_ID = "sk48"

Cell = tuple[int, int]
Region = dict[str, Any]
Grid = tuple[tuple[int, ...], ...]

# ── simulator geometry constants (decoded from the game source) ────────────
_STEP = 6  # udenqlsrfq: one grid unit
_DIVIDER = 53  # fzjeqdahvs: TOP arena above, BOTTOM template below
_BUDGET_MAX = 196  # qiercdohl per level
_CELL_COLORS = (8, 9, 12, 14)  # target-cell (elmjchdqcn) remap colours
_HEAD_BORDER = (6, 15)  # visible head-box border colours (ejlpqgojjt/udbuodqlxv)
_EDGE_HEAD_CORE = (10, 11)  # colour-5-bordered head centres (xtuqlbebvk/zkekdulqku)
# rotation -> facing direction (hhvuoijeua); action id -> move (ghcqtpzzlq)
_DIRS = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}
_MOVES = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
_ROT_OF_DIR = {(1, 0): 0, (0, 1): 90, (-1, 0): 180, (0, -1): 270}

_GIVEUP_DEFAULT = 4000
_SEARCH_EXPANSIONS = 400000

_HUD_SPAN_FRACTION = 0.85
_HUD_THICKNESS_FRACTION = 0.06


# ════════════════════════════════════════════════════════════════════════
# Faithful offline simulator (grow / retract / side-push + exact win test).
# Pure Python; mirrors environment_files/sk48/*/sk48.py member-for-member with
# the multi-tick slide animation collapsed to the settled state.
# ════════════════════════════════════════════════════════════════════════


class _Seg:
    __slots__ = ("x", "y", "rot")

    def __init__(self, x: int, y: int, rot: int) -> None:
        self.x, self.y, self.rot = x, y, rot


class _CellObj:
    __slots__ = ("x", "y", "color")

    def __init__(self, x: int, y: int, color: int) -> None:
        self.x, self.y, self.color = x, y, color


class _Head:
    __slots__ = ("x", "y", "rot", "color")

    def __init__(self, x: int, y: int, rot: int, color: int) -> None:
        self.x, self.y, self.rot, self.color = x, y, rot, color


class _Rect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x: int, y: int, w: int, h: int) -> None:
        self.x, self.y, self.w, self.h = x, y, w, h

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


class _Sim:
    """Deterministic SK48 world model over sprite positions."""

    def __init__(self, state: dict[str, Any]) -> None:
        self.heads: list[_Head] = state["heads"]
        self.bodies: dict[int, list[_Seg]] = {id(h): list(b) for h, b in state["bodies"]}
        self.cells: list[_CellObj] = list(state["cells"])
        self.partner: dict[int, _Head] = dict(state["partner"])
        self.check_count: dict[int, int] = dict(state["check_count"])
        self.active: _Head = state["active"]
        self.arena: _Rect = state["arena"]
        self.obstacles: list[_Rect] = list(state["obstacles"])
        self.gates: list[_Rect] = list(state["gates"])
        self.budget: int = state["budget"]
        self._retract_extra: _Seg | None = None

    # ── search support ──────────────────────────────────────────────────
    def clone(self) -> _Sim:
        heads = [_Head(h.x, h.y, h.rot, h.color) for h in self.heads]
        hmap = {id(oh): nh for oh, nh in zip(self.heads, heads)}
        bodies = [(hmap[id(h)], [_Seg(s.x, s.y, s.rot) for s in self.bodies[id(h)]]) for h in self.heads]
        cells = [_CellObj(c.x, c.y, c.color) for c in self.cells]
        partner = {id(hmap[cid]): hmap[id(p)] for cid, p in self.partner.items()}
        check_count = {id(hmap[pid]): n for pid, n in self.check_count.items()}
        return _Sim({
            "heads": heads, "bodies": bodies, "cells": cells, "partner": partner,
            "check_count": check_count, "active": hmap[id(self.active)], "arena": self.arena,
            "obstacles": self.obstacles, "gates": self.gates, "budget": self.budget,
        })

    def key(self) -> tuple:
        parts = []
        for h in self.heads:
            body = tuple((s.x, s.y) for s in self.bodies[id(h)])
            parts.append((h.color, h.x, h.y, body))
        parts.sort()
        cells = tuple(sorted((c.x, c.y, c.color) for c in self.cells))
        return (self.active.color, self.active.x, self.active.y, tuple(parts), cells)

    # ── helpers ───────────────────────────────────────────────────────────
    def _all_segs(self) -> list[_Seg]:
        segs: list[_Seg] = []
        for b in self.bodies.values():
            segs.extend(b)
        return segs

    def _seg_at(self, x: int, y: int, horiz: bool, exclude: _Seg | None = None) -> _Seg | None:
        """qtjqovumxf (body segment) at exact (x,y) with matching orientation."""
        segs = self._all_segs()
        if self._retract_extra is not None:
            segs.append(self._retract_extra)
        for s in segs:
            if s is exclude:
                continue
            if s.x == x and s.y == y and ((s.rot in (0, 180)) == horiz):
                return s
        return None

    def _cell_at(self, x: int, y: int) -> _CellObj | None:
        for c in self.cells:
            if c.x == x and c.y == y:
                return c
        return None

    def _wall(self, spr: Any, dx_dir: int, dy_dir: int, w: int = _STEP, h: int = _STEP) -> bool:
        """qzvlbxkjgk: moving spr by dir hits an arena edge or an obstacle."""
        x, y = spr.x + dx_dir * _STEP, spr.y + dy_dir * _STEP
        a = self.arena
        if x < a.x or x + w > a.x + a.w:
            return True
        if y < a.y or y + h > a.y + a.h:
            return True
        for o in self.obstacles:
            if o.contains(x, y):
                return True
        return False

    # ── win test (gvtmoopqgy) ────────────────────────────────────────────
    def _overlaps(self, head: _Head) -> list[_CellObj]:
        out = []
        for s in self.bodies[id(head)]:
            c = self._cell_at(s.x, s.y)
            if c is not None:
                out.append(c)
        return out

    def is_win(self) -> bool:
        ov = {id(h): self._overlaps(h) for h in self.heads}
        win = True
        for cid, partner in self.partner.items():
            ctrl_ov = ov[cid]
            part_ov = ov[id(partner)]
            n = self.check_count[id(partner)]
            for i in range(n):
                if i >= len(ctrl_ov):
                    win = False
                elif part_ov[i].color != ctrl_ov[i].color:
                    win = False
        return win

    # ── push recursion (bnrdrdiakd) ──────────────────────────────────────
    def _push(self, spr: Any, dx_dir: int, dy_dir: int, pushed: set[int], from_spr: Any = None) -> bool:
        if id(spr) in pushed:
            return True
        is_seg = isinstance(spr, _Seg)
        if self._wall(spr, dx_dir, dy_dir):
            if not (is_seg and (_DIRS[spr.rot] == (-dx_dir, -dy_dir) or self._wall(spr, 0, 0))):
                return False
        dx, dy = dx_dir * _STEP, dy_dir * _STEP
        if is_seg:
            for ox, oy in ((0, 0), (dx, dy)):
                c = self._cell_at(spr.x + ox, spr.y + oy)
                if c is not None:
                    seg_dir_x, _sy = _DIRS[spr.rot]
                    if self._push(c, dx_dir, dy_dir, pushed, from_spr=spr):
                        pushed.add(id(c))
                    elif (seg_dir_x == 0) != (dx_dir == 0):
                        return False
        else:  # cell
            horiz = dx_dir != 0
            for ox, oy in ((0, 0), (dx, dy)):
                seg = self._seg_at(spr.x + ox, spr.y + oy, not horiz, exclude=from_spr)
                if seg is not None:
                    seg_dir_x, _sy = _DIRS[seg.rot]
                    if (seg_dir_x == 0) != (dx_dir == 0):
                        return False
            nxt = self._cell_at(spr.x + dx, spr.y + dy)
            if nxt is not None and not self._push(nxt, dx_dir, dy_dir, pushed):
                return False
        pushed.add(id(spr))
        return True

    # ── move (hgivzuhjvj), animation collapsed ────────────────────────────
    def step(self, action_id: int) -> None:
        if action_id not in _MOVES:
            return
        self.budget -= 1
        move_x, move_y = _MOVES[action_id]
        dx, dy = move_x * _STEP, move_y * _STEP
        head = self.active
        body = self.bodies[id(head)]
        base = _DIRS[head.rot]
        pushed: set[int] = set()
        objmap = {id(o): o for o in self._all_segs() + self.cells + self.heads}

        if (move_x, move_y) == base:  # GROW
            if self._wall(body[-1], move_x, move_y):
                return
            for s in body:
                self._push(s, move_x, move_y, pushed)
            new_seg = _Seg(head.x, head.y, head.rot)
            body.insert(0, new_seg)
            objmap[id(new_seg)] = new_seg
        elif (move_x, move_y) == (-base[0], -base[1]):  # RETRACT
            if len(body) == 1:
                return
            removed = body.pop(0)
            self._retract_extra = removed
            for s in body:
                self._push(s, move_x, move_y, pushed)
            self._retract_extra = None
        else:  # SIDE push — only where a gate sits
            gx = head.x + 2 + dx // 2
            gy = head.y + 2 + dy // 2
            if not any(g.contains(gx, gy) for g in self.gates):
                return
            for s in body:
                if not self._push(s, move_x, move_y, pushed):
                    return
            pushed.add(id(head))

        for oid in pushed:
            o = objmap.get(oid)
            if o is not None:
                o.x += dx
                o.y += dy


# ════════════════════════════════════════════════════════════════════════
# A* search toward the exact template match.
# ════════════════════════════════════════════════════════════════════════


def _template_seq(sim: _Sim, partner: _Head) -> list[int]:
    ov = sim._overlaps(partner)
    return [c.color for c in ov[: sim.check_count[id(partner)]]]


def _matched_prefix(ctrl_colors: list[int], tmpl: list[int]) -> int:
    m = 0
    for i in range(min(len(ctrl_colors), len(tmpl))):
        if ctrl_colors[i] == tmpl[i]:
            m += 1
        else:
            break
    return m


def _heuristic(sim: _Sim) -> int:
    total = 0
    for cid, partner in sim.partner.items():
        ctrl = next(h for h in sim.heads if id(h) == cid)
        tmpl = _template_seq(sim, partner)
        cov = [c.color for c in sim._overlaps(ctrl)]
        matched = _matched_prefix(cov, tmpl)
        remaining = len(tmpl) - matched
        total += 6 * remaining
        if remaining:
            need = tmpl[matched]
            body = sim.bodies[id(ctrl)]
            targets = [c for c in sim.cells if c.color == need]
            if targets and body:
                total += min(abs(s.x - c.x) + abs(s.y - c.y) for s in body for c in targets) // 6
    return total


def _search(
    sim0: _Sim,
    max_expansions: int = _SEARCH_EXPANSIONS,
    budget_cap: int = _BUDGET_MAX,
    weight: int = 2,
) -> list[int] | None:
    if sim0.is_win():
        return []
    start = sim0.clone()
    counter = 0
    pq = [(_heuristic(start), 0, counter, start, [])]
    best_g = {start.key(): 0}
    expansions = 0
    while pq and expansions < max_expansions:
        _f, g, _c, sim, path = heapq.heappop(pq)
        k = sim.key()
        if best_g.get(k, 1 << 30) < g:
            continue
        expansions += 1
        for a in (1, 2, 3, 4):
            nxt = sim.clone()
            nxt.step(a)
            if nxt.budget < 0:
                continue
            npath = path + [a]
            if nxt.is_win():
                return npath
            ng = g + 1
            if ng > budget_cap:
                continue
            nk = nxt.key()
            if best_g.get(nk, 1 << 30) <= ng:
                continue
            best_g[nk] = ng
            counter += 1
            heapq.heappush(pq, (ng + weight * _heuristic(nxt), ng, counter, nxt, npath))
    return None


# ════════════════════════════════════════════════════════════════════════
# Multi-snake A* (levels with 2+ controllable snakes, source Level 4+).
# ════════════════════════════════════════════════════════════════════════
# The deeper levels have a partner-LESS "free" snake (the initially-active one)
# plus 2+ partnered CONTROL snakes, each of which must be shaped so its
# body-overlap colour sequence matches its bottom template. Two facts decoded +
# live-verified (R59) drive this search:
#   - Selection semantics (ACTION6): the initially-active snake is the FREE one;
#     ACTION6 can switch to any partnered CONTROL and between controls, but can
#     NEVER return to the free snake (it is not in the engine's click-pair map).
#     Selection does NOT cost the move budget (only ACTION1-4 decrement it), so
#     it is a budget-free search edge (still counted as a plan step).
#   - The free snake is a TOOL: moving it PUSHES the target cells (the same push
#     recursion as the controls), which is often how a control's required cells
#     are brought under it. (Measured: L3/source-Level-4 wins in 29 free-snake
#     moves alone — the free snake positions the cells to satisfy both controls,
#     no selection needed — but the search models selection for the general case.)


def _free_head(sim: _Sim) -> _Head | None:
    """The partner-less top-arena head = the initially-active free snake."""
    frees = [h for h in sim.heads if h.y < _DIVIDER and id(h) not in sim.partner]
    return frees[0] if frees else None


def _control_heads(sim: _Sim) -> list[_Head]:
    """The partnered top controls, in stable head order — the ONLY
    ACTION6-selectable snakes (the free snake is never re-selectable)."""
    return [h for h in sim.heads if id(h) in sim.partner]


# A plan step is a move id (int) OR a ("sel", head_x, head_y) selection click.
PlanStep = int | tuple[str, int, int]


def _search_multi(
    sim0: _Sim,
    max_expansions: int = _SEARCH_EXPANSIONS,
    budget_cap: int = _BUDGET_MAX,
    weight: int = 2,
) -> list[PlanStep] | None:
    """A* over (board configuration x active-snake) toward the joint template
    match, with moves on the active snake AND budget-free selection of any
    control as edges. Returns a mixed move/selection plan, or None."""
    fh = _free_head(sim0)
    if fh is not None:
        sim0.active = fh  # start on the free snake (matches the live engine)
    if sim0.is_win():
        return []
    start = sim0.clone()
    counter = 0
    pq: list[tuple] = [(_heuristic(start), 0, counter, start, [])]
    best_g = {start.key(): 0}
    expansions = 0
    while pq and expansions < max_expansions:
        _f, g, _c, sim, path = heapq.heappop(pq)
        k = sim.key()
        if best_g.get(k, 1 << 30) < g:
            continue
        expansions += 1
        for a in (1, 2, 3, 4):
            nxt = sim.clone()
            nxt.step(a)
            if nxt.budget < 0:
                continue
            npath = path + [a]
            if nxt.is_win():
                return npath
            ng = g + 1
            if ng > budget_cap:
                continue
            nk = nxt.key()
            if best_g.get(nk, 1 << 30) <= ng:
                continue
            best_g[nk] = ng
            counter += 1
            heapq.heappush(pq, (ng + weight * _heuristic(nxt), ng, counter, nxt, npath))
        # Selection edges: switch active to each control (budget-free). Recorded
        # as a click at that control's head origin (centre offset applied at
        # execution). Re-identify the control after clone by its stable index.
        for i, hh in enumerate(_control_heads(sim)):
            if hh is sim.active:
                continue
            nxt = sim.clone()
            nxt.active = _control_heads(nxt)[i]
            ng = g + 1
            nk = nxt.key()
            if best_g.get(nk, 1 << 30) <= ng:
                continue
            best_g[nk] = ng
            counter += 1
            heapq.heappush(
                pq, (ng + weight * _heuristic(nxt), ng, counter, nxt, path + [("sel", hh.x, hh.y)])
            )
    return None


# ════════════════════════════════════════════════════════════════════════
# Frame-only state parser (64x64 colour grid -> simulator init state, or None).
# ════════════════════════════════════════════════════════════════════════


def _at(grid: Grid, r: int, c: int) -> int:
    if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
        return grid[r][c]
    return -1


def _parse_budget(grid: Grid) -> int:
    row = grid[_DIVIDER]
    n2 = sum(1 for v in row if v == 2)
    return max(1, round(n2 / len(row) * _BUDGET_MAX))


def _cell_block(grid: Grid, r: int, c: int, col: int) -> bool:
    """Whether the 4x4 at (r,c) is a target cell of colour ``col``. A clean cell
    is a solid 4x4; a cell OCCLUDED by a body segment keeps its full 12-pixel
    BORDER RING in ``col`` while only its inner 2x2 is overwritten by the body's
    transparent-interior colour (measured: the border ring survives, the body's
    dashes fall OUTSIDE the 4x4 — source Level 5's template covers its cell this
    way). Checking the border ring (not all 16) reads occluded cells too; the
    inner 2x2 is left unconstrained. False positives (a non-cell 4x4 whose ring
    happens to be a cell colour) are pinned OUT by the L0-L3 parse-fixture test."""
    for cc in range(c, c + 4):  # top + bottom edges
        if grid[r][cc] != col or grid[r + 3][cc] != col:
            return False
    for rr in range(r + 1, r + 3):  # left + right edges (corners already done)
        if grid[rr][c] != col or grid[rr][c + 3] != col:
            return False
    return True


def _parse_cells(grid: Grid) -> list[_CellObj]:
    """4x4 colour blocks -> target-cell sprite (x=col-1, y=row-1). Detects cells
    OCCLUDED by a body segment via their surviving border ring (see _cell_block)."""
    h, w = len(grid), len(grid[0])
    out: list[_CellObj] = []
    seen: set[Cell] = set()
    for r in range(1, h - 3):
        for c in range(1, w - 3):
            col = grid[r][c]
            if col not in _CELL_COLORS or (r, c) in seen:
                continue
            if not _cell_block(grid, r, c, col):
                continue
            for dr in range(4):
                for dc in range(4):
                    seen.add((r + dr, c + dc))
            out.append(_CellObj(c - 1, r - 1, col))
    return out


def _parse_heads(grid: Grid) -> list[tuple[int, int, int]]:
    """Snake head boxes -> (x, y, id_colour).

    Two renderings share the ``epdquznwmq`` tag and the same win-relevant
    identity (the engine pairs snakes by the head sprite's centre pixel, which
    equals the border colour for the visible boxes):

    - Visible control/template heads: 6x6 boxes with a solid colour-6/15 border.
    - Colour-5-bordered heads (``xtuqlbebvk``/``zkekdulqku``, the partner-less
      obstacle snakes on deeper levels): the border is background so only the
      2x2 colour-10/11 CENTRE block renders. Its top-left sits at (x+2, y+2)
      under every rotation (the block is rotation-symmetric), so the head origin
      is (block_col-2, block_row-2). Detecting these is what lets the body walk
      reconstruct the edge snake the head-border scan misses.
    """
    h, w = len(grid), len(grid[0])
    out: list[tuple[int, int, int]] = []
    for r in range(h - 5):
        for c in range(w - 5):
            b = grid[r][c]
            if b not in _HEAD_BORDER:
                continue
            top = all(grid[r][c + k] == b for k in range(6))
            bot = all(grid[r + 5][c + k] == b for k in range(6))
            side = grid[r + 1][c] == b and grid[r + 4][c] == b
            if top and bot and side:
                out.append((c, r, b))
    seen: set[Cell] = set()
    for r in range(h - 1):
        for c in range(w - 1):
            v = grid[r][c]
            if v not in _EDGE_HEAD_CORE or (r, c) in seen:
                continue
            if grid[r][c + 1] == v and grid[r + 1][c] == v and grid[r + 1][c + 1] == v:
                seen |= {(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)}
                out.append((c - 2, r - 2, v))
    return out


def _is_seg(grid: Grid, x: int, y: int, horiz: bool) -> bool:
    """Body segment at (x,y)? Its dashed 1/2 (active) or 2/3 (inactive) pattern
    edge-pixels sit on the two middle rows (horizontal) or cols (vertical); this
    survives a target cell showing through the transparent interior."""
    if horiz:
        e = (_at(grid, y + 2, x), _at(grid, y + 3, x), _at(grid, y + 2, x + 5), _at(grid, y + 3, x + 5))
    else:
        e = (_at(grid, y, x + 2), _at(grid, y, x + 3), _at(grid, y + 5, x + 2), _at(grid, y + 5, x + 3))
    return all(v in (1, 2, 3) for v in e) and e[0] != e[1]


def _flood4(grid: Grid, r0: int, c0: int, seen: set[Cell]) -> list[Cell]:
    """4-connected colour-4 component above the divider from a seed."""
    comp: list[Cell] = []
    stack = [(r0, c0)]
    seen.add((r0, c0))
    w = len(grid[0])
    while stack:
        r, c = stack.pop()
        comp.append((r, c))
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < _DIVIDER and 0 <= nc < w and (nr, nc) not in seen and grid[nr][nc] == 4:
                seen.add((nr, nc))
                stack.append((nr, nc))
    return comp


def _parse_arena(grid: Grid) -> _Rect | None:
    """Bounding box of the LARGEST colour-4 connected component above the
    divider (the floor sprite). A connected component — not a per-row run —
    because on deeper levels sprites (edge snakes, target cells) occlude the
    interior/top of the floor, breaking the run-based scan; the floor stays one
    4-connected region around those holes, and head-interior colour-4 pixels
    (which sit in the corridor, disconnected from the floor) form small separate
    components that lose to the floor on size."""
    seen: set[Cell] = set()
    best: list[Cell] = []
    for r in range(_DIVIDER):
        for c in range(len(grid[0])):
            if grid[r][c] == 4 and (r, c) not in seen:
                comp = _flood4(grid, r, c, seen)
                if len(comp) > len(best):
                    best = comp
    if len(best) < 12:
        return None
    rs = [p[0] for p in best]
    cs = [p[1] for p in best]
    return _Rect(min(cs), min(rs), max(cs) - min(cs) + 1, max(rs) - min(rs) + 1)


def _parse_walls(grid: Grid, arena: _Rect) -> list[_Rect]:
    """Interior collision walls (`mkgqjopcjn`, source Level 5+) -> obstacle
    rects. A wall renders as a solid rectangular block of the BACKGROUND colour
    sitting INSIDE the colour-4 arena floor — a hole in the floor, isolated from
    the outside background by the floor around it. A background-colour component
    is a wall when it is STRICTLY inside the arena bbox (the outside background
    leaks in at the edge and is rejected) and fills its own bounding box (solid —
    this rejects the edge-snake heads' hollow background-colour border rings).
    Returns _Rect(x=col, y=row) in the sim's grid coordinates."""
    # The BACKGROUND colour is the frame corner, NOT most_common_color — the
    # colour-4 FLOOR is the frame's most common colour, so most_common_color
    # returns 4 and would never see the background-coloured (5) wall.
    bg = grid[0][0]
    y0, y1 = arena.y, arena.y + arena.h
    x0, x1 = arena.x, arena.x + arena.w
    seen: set[Cell] = set()
    out: list[_Rect] = []
    for r in range(y0, y1):
        for c in range(x0, x1):
            if grid[r][c] != bg or (r, c) in seen:
                continue
            comp: list[Cell] = []
            stack = [(r, c)]
            seen.add((r, c))
            touches_edge = False
            while stack:
                rr, cc = stack.pop()
                comp.append((rr, cc))
                if rr == y0 or rr == y1 - 1 or cc == x0 or cc == x1 - 1:
                    touches_edge = True
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = rr + dr, cc + dc
                    if y0 <= nr < y1 and x0 <= nc < x1 and (nr, nc) not in seen and grid[nr][nc] == bg:
                        seen.add((nr, nc))
                        stack.append((nr, nc))
            if touches_edge or len(comp) < 4:
                continue
            rs = [p[0] for p in comp]
            cs = [p[1] for p in comp]
            br0, br1, bc0, bc1 = min(rs), max(rs), min(cs), max(cs)
            if len(comp) == (br1 - br0 + 1) * (bc1 - bc0 + 1):
                out.append(_Rect(bc0, br0, bc1 - bc0 + 1, br1 - br0 + 1))
    return out


def _parse_gates(grid: Grid) -> list[_Rect]:
    """Side-push gate rails: 2-wide runs (>=8 long) of adjacent colour-2/3
    columns/rows. Stacked gates merge into one rail; a body segment's dashes
    never form two adjacent full 2/3 lines of length >=8."""
    h, w = len(grid), len(grid[0])
    out: list[_Rect] = []
    for c in range(w - 1):
        r = 0
        while r < h:
            if _at(grid, r, c) in (2, 3) and _at(grid, r, c + 1) in (2, 3):
                r0 = r
                while r < h and _at(grid, r, c) in (2, 3) and _at(grid, r, c + 1) in (2, 3):
                    r += 1
                if r - r0 >= 8:
                    out.append(_Rect(c, r0, 2, r - r0))
            else:
                r += 1
    for r in range(h - 1):
        c = 0
        while c < w:
            if _at(grid, r, c) in (2, 3) and _at(grid, r + 1, c) in (2, 3):
                c0 = c
                while c < w and _at(grid, r, c) in (2, 3) and _at(grid, r + 1, c) in (2, 3):
                    c += 1
                if c - c0 >= 8:
                    out.append(_Rect(c0, r, c - c0, 2))
            else:
                c += 1
    return out


def _parse_state(grid: Grid) -> dict[str, Any] | None:
    """Reconstruct a simulator init-state from a settled 64x64 frame, or None
    when the board cannot be parsed unambiguously (the adapter then gates to
    the transition-graph explorer). Returns None e.g. on levels whose
    non-controllable snakes have colour-5-bordered near-invisible heads at the
    frame edge (a NAMED divergence — those heads carry body segments the walk
    cannot anchor, so the reconstruction would be incomplete)."""
    if not grid or len(grid) < 64 or len(grid[0]) < 64:
        return None
    raw_heads = _parse_heads(grid)
    if not raw_heads:
        return None
    arena = _parse_arena(grid)
    if arena is None:
        return None

    heads: list[_Head] = []
    bodies: list[tuple[_Head, list[_Seg]]] = []
    for (x, y, bcol) in raw_heads:
        facing = None
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if _is_seg(grid, x + _STEP * d[0], y + _STEP * d[1], d[0] != 0):
                facing = d
                break
        if facing is None:
            return None  # 1-segment / ambiguous snake: gate to fallback
        rot = _ROT_OF_DIR[facing]
        head = _Head(x, y, rot, bcol)
        segs = [_Seg(x, y, rot)]
        k = 1
        while _is_seg(grid, x + _STEP * k * facing[0], y + _STEP * k * facing[1], facing[0] != 0):
            segs.append(_Seg(x + _STEP * k * facing[0], y + _STEP * k * facing[1], rot))
            k += 1
        heads.append(head)
        bodies.append((head, segs))

    partner: dict[int, _Head] = {}
    check_count: dict[int, int] = {}
    tops = [h for h in heads if h.y < _DIVIDER]
    bots = [h for h in heads if h.y >= _DIVIDER]
    for ch in tops:
        mate = next((b for b in bots if b.color == ch.color), None)
        if mate is not None:
            partner[id(ch)] = mate
            mate_body = next(b for hh, b in bodies if hh is mate)
            check_count[id(mate)] = len(mate_body) - 1
    if not partner:
        return None

    cells = _parse_cells(grid)
    # The template's own body may fully cover its target cells; _parse_cells only
    # sees a cell as a SOLID 4x4 block, so a cell occluded by a body segment is
    # MISSED, leaving that template's goal sequence incomplete (fewer parsed
    # cells than its check_count). Bail to the explorer rather than plan toward a
    # goal we cannot fully reconstruct (a NAMED divergence — source Level 5's
    # template occludes a colour-9 cell; reconstructing occluded cell colours
    # through the body's transparent interior is the reopen). Also guards the
    # is_win index. Never fires on L0-L3 (their templates parse fully).
    cell_pos = {(c.x, c.y) for c in cells}
    for mate in partner.values():
        mate_body = next(b for hh, b in bodies if hh is mate)
        covered = sum(1 for s in mate_body if (s.x, s.y) in cell_pos)
        if covered < check_count[id(mate)]:
            return None

    # Active must be a CONTROLLABLE snake (one that has a template partner); the
    # partner-less edge snakes are top-of-arena too but are obstacles, and would
    # otherwise win the (y, x) tie-break at the frame edge and misdirect A*.
    active = min((h for h in tops if id(h) in partner), key=lambda h: (h.y, h.x))
    return {
        "heads": heads, "bodies": bodies, "cells": cells, "partner": partner,
        "check_count": check_count, "active": active, "arena": arena,
        "obstacles": _parse_walls(grid, arena), "gates": _parse_gates(grid),
        "budget": _parse_budget(grid),
    }


# ════════════════════════════════════════════════════════════════════════
# Fallback: generic transition-graph frontier exploration (the R56 explorer,
# which banks 0/8 but is the safe floor when the simulator cannot be built).
# ════════════════════════════════════════════════════════════════════════


def _is_hud_band(region: Region, height: int, width: int) -> bool:
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


class _Explorer:
    """Generic transition-graph frontier exploration over HUD-masked
    frame-canonical states (snake body captured in the key)."""

    def __init__(self) -> None:
        self._pending_action: int | None = None
        self._pending_key: Any | None = None
        self._transitions: list[tuple[Any, int, Any]] = []
        self._edges: dict[Any, dict[int, Any]] = {}
        self._tried_from: dict[Any, set[int]] = {}

    def on_level_up(self) -> None:
        self._pending_action = None
        self._pending_key = None
        self._transitions = []
        self._edges = {}
        self._tried_from = {}

    def on_restart(self) -> None:
        self._pending_action = None
        self._pending_key = None

    def choose(self, grid: Grid, act_ids: list[int]) -> int:
        cur_key = canonical_key(_mask_hud(grid), mode="exact")
        self._observe_result(cur_key)
        action = self._decide(cur_key, act_ids)
        self._pending_action = action
        self._pending_key = cur_key
        return action

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


# ════════════════════════════════════════════════════════════════════════
# Adapter: simulator-search plan first (gated), transition-graph explorer as
# the safe fallback.
# ════════════════════════════════════════════════════════════════════════


class Adapter(GameAdapter):
    """Frame-parsed faithful-simulator A* plan per level, with a
    transition-graph explorer fallback when the parse or search fails."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        self._plan: list[int] = []
        self._plan_failed = False  # this level fell back to the explorer
        self._need_settle = False  # frame is a fresh-level animation; settle first
        self._explorer = _Explorer()

    # ── harness contract ─────────────────────────────────────────────────
    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._explorer.on_restart()
            self._plan = []
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._reset_level(-1)
            return reset_action()

        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            # A fresh level; its first frame is a win-flash composite. Issue one
            # free ACTION7 (undo — a no-op with a single snapshot) to settle,
            # then plan on the settled frame.
            self._reset_level(levels)
            if levels > 0:
                self._need_settle = True
                return simple_action(7)

        self._step += 1
        grid = canonical_layer(latest_frame)
        simple_ids, _a6 = available_action_ids(latest_frame)
        act_ids = sorted(a for a in simple_ids if a in (1, 2, 3, 4, 7))
        if not act_ids:
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        if self._need_settle:
            self._need_settle = False
            self._build_plan(grid)

        if not self._plan and not self._plan_failed and self._levels_seen == 0 and self._step == 1:
            # Level 0: RESET frame is already settled; plan immediately.
            self._build_plan(grid)

        if self._plan:
            step = self._plan.pop(0)
            if isinstance(step, int):
                return simple_action(step)
            # ("sel", head_x, head_y): ACTION6-click the control's centre to
            # switch active (offset +3,+3 from the head origin lands on the solid
            # centre — verified live; the corner is transparent and selects None).
            _tag, hx, hy = step
            return click_action(hx + 3, hy + 3)

        # Fallback: transition-graph explorer for this level.
        self._plan_failed = True
        move_ids = [a for a in act_ids] or [simple_ids[0]]
        return simple_action(self._explorer.choose(grid, move_ids))

    # ── planning ──────────────────────────────────────────────────────────
    def _reset_level(self, levels: int) -> None:
        self._levels_seen = levels
        self._plan = []
        self._plan_failed = False
        self._need_settle = False
        self._explorer.on_level_up()

    def _build_plan(self, grid: Grid) -> None:
        state = _parse_state(grid)
        if state is None:
            self._plan_failed = True
            return
        try:
            # 2+ partnered controls (source Level 4+) => multi-snake search with
            # selection; otherwise the single-active-snake search, byte-identical
            # to the L0-L2 behaviour (gate on the multi-controllable signature).
            if len(state["partner"]) >= 2:
                sol = _search_multi(_Sim(state))
            else:
                sol = _search(_Sim(state))
        except Exception:
            sol = None
        if sol:
            self._plan = list(sol)
        else:
            self._plan_failed = True
