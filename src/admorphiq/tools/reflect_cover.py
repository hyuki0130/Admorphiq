"""Cover a stencil of goal cells with a shape and its MIRROR IMAGES.

The family this fires on draws a board on which a few movable shapes are reflected through
one or two full-span mirror lines, and asks that every goal cell be covered by the shape or
by one of its reflections. The board renders three things the tool needs and nothing else:

* a **mirror line** — a single colour filling one whole column and/or one whole row;
* the **reflections** — the mirror images of the real shapes, in one flat colour, painted
  only where the board was otherwise empty;
* an overlay pixel at the centre of every cell, which repaints a REAL shape cell and never a
  reflected one, and repaints a goal cell above everything else.

Those two overlay rules do all the identification without a single probe: a cell whose centre
disagrees with its body is a real shape cell, and the goal stencil is whichever overlay value
makes the reflections come out exactly right. From there the level is pure geometry, because
reflection through one vertical and one horizontal line generates a four-element group — so a
goal is covered exactly when ONE of its (at most four) orbit points lies under a real shape.
That turns "where must the shape go" into a per-goal set of allowed positions, and the level
into a small cover search over

    (mirror line positions) x (one position per shape).

The search returns the CHEAPEST configuration in actions, because these boards declare a
per-level action budget and end when it is exceeded; there is no room to explore.

What the tool refuses: ``detect`` returns 0.0 unless the lattice resolves, a full-span line
exists, the reflected cells are reproduced EXACTLY by mirroring the real cells, and the
cover search finds a reachable configuration. A board that merely looks symmetric has no
plan here and must not take the turn from a tool that has one.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np

from admorphiq.tools.base import (
    Step,
    availability,
    frame_2d,
    has_frame,
    levels_completed,
)

__all__ = ["ReflectCoverTool"]

# Conventional 4-direction mapping; corrected from observation the first time a shape is
# seen to move, so a board that wires the pad differently still plays.
_DEFAULT_DIRS: dict[int, tuple[int, int]] = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}

_MAX_GRID = 40
# Goal coverage is carried as a bitmask in one unsigned 64-bit word.
_MAX_GOALS = 64
_MOVE_BATCH = 6


def _lattice(f: np.ndarray) -> tuple[int, int, int, int, int] | None:
    """(side, oy, ox, rows, cols) of the cell lattice, or None.

    A cell is a flat square of body colour carrying at most a central overlay patch, so the
    lattice is the smallest tiling under which every block is flat outside its centre AND at
    least one centre disagrees. Requiring a disagreement is what stops a coarse multiple of
    the true pitch (whose blocks are also flat over empty board) from winning.
    """
    n = int(f.shape[0])
    for side in range(3, 11):
        lo, hi = (side - 1) // 2, side // 2
        if side >= 4:
            lo, hi = 1, side - 2
        if hi < lo:
            continue
        inner = np.zeros((side, side), dtype=bool)
        inner[lo:hi + 1, lo:hi + 1] = True
        best: tuple[float, int, int, int, int, int] | None = None
        for oy in range(side):
            for ox in range(side):
                rows, cols = (n - oy) // side, (n - ox) // side
                if rows < 6 or cols < 6:
                    continue
                blk = f[oy:oy + rows * side, ox:ox + cols * side]
                blk = blk.reshape(rows, side, cols, side).transpose(0, 2, 1, 3)
                diff = blk != blk[:, :, 0, 0][:, :, None, None]
                flat = float((~(diff & ~inner).any(axis=(2, 3))).mean())
                marks = int((diff & inner).any(axis=(2, 3)).sum())
                cand = (flat, marks, side, oy, ox, rows)
                if marks and (best is None or cand[:2] > best[:2]):
                    best = cand
        if best is not None and best[0] >= 0.995:
            _, _, side, oy, ox, rows = best
            return side, oy, ox, rows, (n - ox) // side
    return None


def _components(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    """8-connected groups of a cell set (cells are (x, y)).

    Diagonal contact counts: MEASURED, these shapes include arcs that touch only corner to
    corner, and 4-connectivity cut one piece into five.
    """
    left = set(cells)
    out: list[set[tuple[int, int]]] = []
    while left:
        seed = left.pop()
        grp = {seed}
        q = deque([seed])
        while q:
            x, y = q.popleft()
            for nb in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1),
                       (x - 1, y - 1), (x + 1, y - 1), (x - 1, y + 1), (x + 1, y + 1)):
                if nb in left:
                    left.discard(nb)
                    grp.add(nb)
                    q.append(nb)
        out.append(grp)
    return out


def _orbit(x: int, y: int, ax: int | None, ay: int | None) -> set[tuple[int, int]]:
    xs = [x] if ax is None else [x, 2 * ax - x]
    ys = [y] if ay is None else [y, 2 * ay - y]
    return {(a, b) for a in xs for b in ys}


class _Board:
    """One parse of a frame into cells, mirror lines, shapes and goals."""

    def __init__(self, body: np.ndarray, mark: np.ndarray,
                 lattice: tuple[int, int, int]) -> None:
        self.body = body
        self.mark = mark
        self.lattice = lattice
        self.rows, self.cols = body.shape
        flat = body.ravel()
        self.bg = int(np.bincount(flat[flat >= 0]).argmax()) if (flat >= 0).any() else -1
        self.vline: int | None = None
        self.hline: int | None = None
        self.line_colour: int | None = None
        self._find_lines()
        self.axis_cells = self._axis_cells()
        self.real = self._real_cells()

    def _find_lines(self) -> None:
        """The mirror lines: a colour whose cells lie in ONE column and/or ONE row.

        Containment, not run length, is the test. MEASURED: a stencil laid along the line
        overpaints a third of it, so "this run is nearly full" loses the line — while the
        cells that remain still sit in exactly one column, which nothing else on the board
        does at this size.
        """
        for colour in sorted({int(v) for v in self.body.ravel()} - {self.bg}):
            mask = self.body == colour
            colcount, rowcount = mask.sum(axis=0), mask.sum(axis=1)
            vx, hy = int(colcount.argmax()), int(rowcount.argmax())
            ys, xs = np.where(mask)
            if not all(x == vx or y == hy for x, y in zip(xs, ys)):
                continue
            v = vx if colcount[vx] * 2 >= self.rows else None
            h = hy if rowcount[hy] * 2 >= self.cols else None
            if v is None and h is None:
                continue
            if v is None and not all(y == hy for y in ys):
                continue
            if h is None and not all(x == vx for x in xs):
                continue
            if self.line_colour is not None:
                self.vline = self.hline = self.line_colour = None
                return
            self.vline, self.hline, self.line_colour = v, h, colour

    def _axis_cells(self) -> set[tuple[int, int]]:
        """Only the cells that actually SHOW a line, never the whole span.

        MEASURED: taking the full span deleted every goal that sits ON the line — a third of
        one board's stencil — and the level then read as already solved.
        """
        return set() if self.line_colour is None else self.cells_of(self.line_colour)

    def _real_cells(self) -> set[tuple[int, int]]:
        diff = self.mark != self.body
        ys, xs = np.where(diff)
        return {(int(x), int(y)) for x, y in zip(xs, ys)} - self.axis_cells

    def cells_of(self, colour: int) -> set[tuple[int, int]]:
        ys, xs = np.where(self.body == colour)
        return {(int(x), int(y)) for x, y in zip(xs, ys)}

    def line_locked(self, vertical: bool) -> bool:
        """A mirror line whose overlay repaints it in its own body colour cannot be moved.

        Read over the WHOLE line, not one cell: a goal sitting on the line repaints that one
        cell, and a single-cell probe there reads a movable line as fixed.
        """
        pos = self.vline if vertical else self.hline
        if pos is None:
            return True
        cells = ([(pos, y) for y in range(self.rows)] if vertical
                 else [(x, pos) for x in range(self.cols)])
        free = sum(1 for x, y in cells if self.mark[y, x] != self.body[y, x])
        return free * 2 < len(cells)


class ReflectCoverTool:
    """Move shapes and mirror lines so the shapes' reflections cover every goal cell."""

    name = "reflect_cover"

    def __init__(self) -> None:
        self._owned = False
        self.reset()
        self._dirs = dict(_DEFAULT_DIRS)
        self._detect_cache: tuple[str, float] | None = None

    # --- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        self._level: int | None = None
        self._model: dict[str, Any] | None = None
        self._goal: dict[Any, tuple[int, int]] | None = None
        self._frozen: set[Any] = set()
        self._active: Any = None
        self._probe: tuple[Any, tuple[int, int], dict[Any, tuple[int, int]], int] | None = None
        self._pos: dict[Any, tuple[int, int]] | None = None
        self._stuck = 0
        self._fillers = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        self._stuck = 0 if changed else self._stuck + 1

    def detect(self, frames: list[Any], obs: Any) -> float:
        # Which shape moves is chosen by clicking it; without a click there is no way to
        # address one of several entities, so there is no plan to bid for.
        if not availability(obs)[1]:
            return 0.0
        board = self._parse(obs)
        if board is None:
            return 0.0
        model = self._build(board)
        if model is None:
            return 0.0
        if self._solve(model, model["pos"], set(model["frozen"])) is None:
            return 0.0
        return 0.92

    # --- perception --------------------------------------------------------

    def _parse(self, obs: Any) -> _Board | None:
        if not has_frame(obs):
            return None
        f = np.asarray(frame_2d(obs))
        if f.ndim != 2 or f.shape[0] != f.shape[1]:
            return None
        lat = _lattice(f)
        if lat is None:
            return None
        side, oy, ox, rows, cols = lat
        if not (6 <= rows <= _MAX_GRID and 6 <= cols <= _MAX_GRID):
            return None
        c = side // 2
        body = f[oy:oy + rows * side:side, ox:ox + cols * side:side]
        mark = f[oy + c:oy + c + rows * side:side, ox + c:ox + c + cols * side:side]
        return _Board(np.asarray(body), np.asarray(mark), (side, oy, ox))

    def _build(self, board: _Board) -> dict[str, Any] | None:
        """Shapes, goals and mirror lines, or None when the frame does not fit the family.

        The overlay pixel carries the goal at top priority, so a goal keeps its overlay
        colour even when a reflection is painted over it — which is why the goal stencil is
        read off the OVERLAY and never off the body. Which overlay value means "goal" is not
        assumed: each candidate is tried and the one that makes the reflections come out
        EXACTLY right is the answer. If none does, or more than one does, there is no plan.
        """
        if board.line_colour is None or not board.real:
            return None
        diff = board.real
        picks = []
        for m in sorted({int(v) for v in board.mark.ravel()}):
            built = self._interpret(board, diff, m)
            if built is not None:
                picks.append(built)
        if len(picks) != 1:
            return None
        return picks[0]

    def _interpret(self, board: _Board, diff: set[tuple[int, int]],
                   goal_mark: int) -> dict[str, Any] | None:
        if goal_mark == board.bg:
            return None
        ys, xs = np.where(board.mark == goal_mark)
        goals = frozenset((int(x), int(y)) for x, y in zip(xs, ys))
        if not goals or len(goals) > _MAX_GOALS:
            return None
        if any(int(board.body[y, x]) == board.bg for x, y in goals):
            return None
        if not any(int(board.body[y, x]) == goal_mark for x, y in goals):
            return None
        real = diff - goals
        if not real:
            return None

        shapes: list[dict[str, Any]] = []
        for grp in _components(real):
            colours = {int(board.body[y, x]) for x, y in grp}
            if len(colours) != 1:
                return None
            x0 = min(p[0] for p in grp)
            y0 = min(p[1] for p in grp)
            rel = frozenset((p[0] - x0, p[1] - y0) for p in grp)
            shapes.append({
                "colour": colours.pop(),
                "rel": rel,
                "w": max(p[0] for p in rel) + 1,
                "h": max(p[1] for p in rel) + 1,
                "pos": (x0, y0),
            })
        if not shapes or len(shapes) > 6:
            return None

        mirrored: set[tuple[int, int]] = set()
        for x, y in real:
            mirrored |= _orbit(x, y, board.vline, board.hline)
        mirrored = {p for p in mirrored
                    if 0 <= p[0] < board.cols and 0 <= p[1] < board.rows} - real
        fg = {(int(x), int(y)) for y, x in zip(*np.where(board.body != board.bg))}
        images = fg - real - board.axis_cells - goals
        if images:
            colours = {int(board.body[y, x]) for x, y in images}
            if len(colours) != 1 or not images <= mirrored:
                return None
            if images != board.cells_of(colours.pop()) - real - board.axis_cells - goals:
                return None
        if mirrored - board.axis_cells - goals - images:
            return None

        pos: dict[Any, tuple[int, int]] = {}
        if board.vline is not None:
            pos[("v",)] = (board.vline, 0)
        if board.hline is not None:
            pos[("h",)] = (0, board.hline)
        for i, sh in enumerate(shapes):
            pos[("s", i)] = sh["pos"]
        frozen = set()
        if board.vline is not None and board.line_locked(True):
            frozen.add(("v",))
        if board.hline is not None and board.line_locked(False):
            frozen.add(("h",))
        return {
            "rows": board.rows,
            "cols": board.cols,
            "shapes": shapes,
            "goals": sorted(goals),
            "pos": pos,
            "frozen": frozen,
            "line_colour": board.line_colour,
        }

    def _track(self, board: _Board, model: dict[str, Any],
               prev: dict[Any, tuple[int, int]]) -> dict[Any, tuple[int, int]] | None:
        """Re-read every entity's position from a fresh frame (each moves at most one cell)."""
        pos: dict[Any, tuple[int, int]] = {}
        # Follow the lines by their COLOUR, not by re-detecting a full run: shapes standing on
        # a line hide its cells, and a run test then loses a line that is plainly still there.
        paint = model["line_colour"]
        seen_line = board.body == paint
        if ("v",) in prev:
            pos[("v",)] = (int(seen_line.sum(axis=0).argmax()), 0)
        if ("h",) in prev:
            pos[("h",)] = (0, int(seen_line.sum(axis=1).argmax()))
        for i, sh in enumerate(model["shapes"]):
            key = ("s", i)
            seen = board.cells_of(sh["colour"])
            if not seen:
                return None
            px, py = prev[key]
            # Score every legal placement: the most cells explained wins, nearest to where
            # the shape last was breaks ties. A radius-limited search was measured wrong —
            # a partial overlap near the old position outranked the exact match further off.
            best: tuple[tuple[int, int], tuple[int, int]] | None = None
            for cy in range(model["rows"] - sh["h"] + 1):
                for cx in range(model["cols"] - sh["w"] + 1):
                    hit = sum(1 for (rx, ry) in sh["rel"] if (cx + rx, cy + ry) in seen)
                    if not hit:
                        continue
                    score = (hit, -abs(cx - px) - abs(cy - py))
                    if best is None or score > best[0]:
                        best = (score, (cx, cy))
            if best is None:
                return None
            pos[key] = best[1]
        return pos

    # --- planning ----------------------------------------------------------

    def _solve(self, model: dict[str, Any], pos: dict[Any, tuple[int, int]],
               frozen: set[Any]) -> dict[Any, tuple[int, int]] | None:
        """Cheapest reachable configuration covering every goal, or None."""
        rows, cols = model["rows"], model["cols"]
        goals = model["goals"]
        full = (1 << len(goals)) - 1
        gx = np.array([g[0] for g in goals])
        gy = np.array([g[1] for g in goals])
        weights = (np.uint64(1) << np.arange(len(goals), dtype=np.uint64))

        has_v, has_h = ("v",) in pos, ("h",) in pos
        vx0 = pos[("v",)][0] if has_v else None
        hy0 = pos[("h",)][1] if has_h else None
        vopts = [vx0] if (not has_v or ("v",) in frozen) else list(range(cols))
        hopts = [hy0] if (not has_h or ("h",) in frozen) else list(range(rows))
        combos = sorted(
            ((abs(a - vx0) if has_v else 0) + (abs(b - hy0) if has_h else 0), a, b)
            for a in vopts for b in hopts
        )

        best_cost: float | None = None
        best: dict[Any, tuple[int, int]] | None = None
        for line_cost, ax, ay in combos:
            base = line_cost + (1 if has_v and ax != vx0 else 0) + (1 if has_h and ay != hy0 else 0)
            if best_cost is not None and base >= best_cost:
                break
            tables: list[list[tuple[int, float, tuple[int, int]]]] = []
            reach = 0
            feasible = True
            for i, sh in enumerate(model["shapes"]):
                key = ("s", i)
                px0, py0 = pos[key]
                if key in frozen:
                    table = self._masks(sh, [(px0, py0)], gx, gy, ax, ay, weights, rows, cols)
                else:
                    span = [(x, y) for y in range(rows - sh["h"] + 1)
                            for x in range(cols - sh["w"] + 1)]
                    table = self._masks(sh, span, gx, gy, ax, ay, weights, rows, cols)
                table = [(m, abs(p[0] - px0) + abs(p[1] - py0) + (0 if p == (px0, py0) else 1), p)
                         for m, p in table]
                table = self._pareto(table)
                if not table:
                    feasible = False
                    break
                for m, _, _ in table:
                    reach |= m
                tables.append(sorted(table, key=lambda t: t[1]))
            if not feasible or reach & full != full:
                continue
            found = self._cover(tables, full, base, best_cost)
            if found is not None:
                cost, choice = found
                best_cost = cost
                best = {}
                if has_v:
                    best[("v",)] = (ax, 0)
                if has_h:
                    best[("h",)] = (0, ay)
                for i, p in enumerate(choice):
                    best[("s", i)] = p
        return best

    @staticmethod
    def _masks(sh: dict[str, Any], span: list[tuple[int, int]], gx: np.ndarray, gy: np.ndarray,
               ax: int | None, ay: int | None, weights: np.ndarray,
               rows: int, cols: int) -> list[tuple[int, tuple[int, int]]]:
        w, h = sh["w"], sh["h"]
        pw, ph = cols - w + 1, rows - h + 1
        if pw <= 0 or ph <= 0:
            return []
        dxs = np.array([r[0] for r in sh["rel"]])
        dys = np.array([r[1] for r in sh["rel"]])
        cov = np.zeros((len(gx), ph, pw), dtype=bool)
        xs = [gx] if ax is None else [gx, 2 * ax - gx]
        ys = [gy] if ay is None else [gy, 2 * ay - gy]
        for qx in xs:
            for qy in ys:
                for cx, cy in zip(dxs, dys):
                    px, py = qx - cx, qy - cy
                    ok = (px >= 0) & (px < pw) & (py >= 0) & (py < ph)
                    cov[np.arange(len(gx))[ok], py[ok], px[ok]] = True
        masks = (cov.astype(np.uint64) * weights[:, None, None]).sum(axis=0)
        allow = {p for p in span}
        out: list[tuple[int, tuple[int, int]]] = []
        for py in range(ph):
            for px in range(pw):
                if (px, py) in allow:
                    out.append((int(masks[py, px]), (px, py)))
        return out

    @staticmethod
    def _pareto(table: list[tuple[int, float, tuple[int, int]]]
                ) -> list[tuple[int, float, tuple[int, int]]]:
        best: dict[int, tuple[float, tuple[int, int]]] = {}
        for m, c, p in table:
            if m not in best or c < best[m][0]:
                best[m] = (c, p)
        items = sorted(((m, c, p) for m, (c, p) in best.items()), key=lambda t: t[1])
        kept: list[tuple[int, float, tuple[int, int]]] = []
        for m, c, p in items:
            if any(m | km == km for km, _, _ in kept):
                continue
            kept.append((m, c, p))
        return kept

    @staticmethod
    def _cover(tables: list[list[tuple[int, float, tuple[int, int]]]], full: int,
               base: float, bound: float | None) -> tuple[float, list[tuple[int, int]]] | None:
        floors = [0.0] * (len(tables) + 1)
        for i in range(len(tables) - 1, -1, -1):
            floors[i] = floors[i + 1] + tables[i][0][1]
        best: tuple[float, list[tuple[int, int]]] | None = None
        limit = bound

        def walk(i: int, mask: int, cost: float, chosen: list[tuple[int, int]]) -> None:
            nonlocal best, limit
            if limit is not None and cost + floors[i] >= limit:
                return
            if i == len(tables):
                if mask == full:
                    best = (cost, list(chosen))
                    limit = cost
                return
            for m, c, p in tables[i]:
                if limit is not None and cost + c + floors[i + 1] >= limit:
                    break
                chosen.append(p)
                walk(i + 1, mask | m, cost + c, chosen)
                chosen.pop()

        walk(0, 0, base, [])
        return best

    # --- acting ------------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if self._stuck >= 4:
            # Four actions in a row moved nothing: the model no longer describes this board
            # and every further action would be spent against a declared budget for nothing.
            return []
        board = self._parse(obs)
        if board is None:
            return []
        level = levels_completed(obs)
        if level != self._level:
            known = self._level is not None
            self.reset()
            self._level = level
            if known:
                spot = self._refresh(board, obs)
                if spot is not None:
                    return [spot]
        if self._model is None:
            model = self._build(board)
            if model is not None:
                self._owned = True
            if model is None:
                spot = self._refresh(board, obs)
                if spot is not None:
                    self._fillers += 1
                    return [spot]
                return []
            self._model = model
            self._pos = dict(model["pos"])
            self._frozen = set(model["frozen"])
            self._goal = self._solve(model, self._pos, self._frozen)
            if self._goal is None:
                self._model = None
                return []
        model = self._model
        pos = self._track(board, model, self._pos or model["pos"])
        if pos is None:
            return []

        if self._probe is not None:
            key, want, before, aid = self._probe
            self._probe = None
            moved = [k for k in pos if pos[k] != before.get(k)]
            if len(moved) == 1:
                k = moved[0]
                delta = (pos[k][0] - before[k][0], pos[k][1] - before[k][1])
                if abs(delta[0]) + abs(delta[1]) == 1:
                    self._dirs[aid] = delta
            if pos.get(key) == want:
                self._active = key
            else:
                # The click did not take: this entity cannot be selected, so it cannot move.
                self._frozen.add(key)
                self._active = moved[0] if moved else None
                self._goal = self._solve(model, pos, self._frozen)
                self._pos = pos
                if self._goal is None:
                    self._model = None
                    return []
        self._pos = pos

        if self._goal is None:
            return []
        order = [k for k in (("v",), ("h",)) if k in self._goal]
        order += [k for k in self._goal if k[0] == "s"]
        target = next((k for k in order
                       if k not in self._frozen and pos[k] != self._goal[k]), None)
        if target is None:
            # Every entity stands where the plan wanted it and the level did not end, so this
            # frame is not the board it appears to be. Drop the model and re-read.
            self._model = None
            spot = self._refresh(board, obs)
            if spot is not None:
                self._fillers += 1
                return [spot]
            return []
        step = self._toward(pos[target], self._goal[target])
        if step is None:
            return []
        if self._active != target:
            click = self._click(board, model, pos, target)
            if click is None:
                self._frozen.add(target)
                self._goal = self._solve(model, pos, self._frozen)
                return []
            want = (pos[target][0] + step[0], pos[target][1] + step[1])
            aid = self._action_for(step)
            self._probe = (target, want, dict(pos), aid)
            return [click, (aid, None)]
        out: list[Step] = []
        cur = pos[target]
        for _ in range(_MOVE_BATCH):
            s = self._toward(cur, self._goal[target])
            if s is None:
                break
            out.append((self._action_for(s), None))
            cur = (cur[0] + s[0], cur[1] + s[1])
        return out

    def _refresh(self, board: _Board, obs: Any) -> Step | None:
        """One action that buys a newer frame without changing the board, or None.

        MEASURED, and the reason this tool stopped after one level when it was registered:
        the runner drops any action the game does not list as simple, and a game offering
        1-5 does NOT list undo — so the free undo asked for here was thrown away and the
        runner substituted its own probe move, which shoves whatever is selected and wrecks
        the board the very frame a level starts.

        A click on empty board is the refresh that survives: it is always legal wherever
        clicking exists, it selects nothing, and it costs no move budget. Undo is kept only
        for a game with no simple actions at all, which is the one case a runner will pass
        it through.

        Only ever on a board this tool has ALREADY modelled: a tool with no plan spending
        another game's actions is the one cost its own author cannot see.
        """
        if not self._owned or self._fillers >= 2:
            return None
        simple, click = availability(obs)
        if click:
            spot = self._empty_cell(board)
            if spot is not None:
                side, oy, ox = board.lattice
                c = side // 2
                return (6, (ox + side * spot[0] + c, oy + side * spot[1] + c))
        if not simple:
            return (7, None)
        return None

    @staticmethod
    def _empty_cell(board: _Board) -> tuple[int, int] | None:
        """The background cell furthest from anything drawn, so a click there hits nothing.

        Furthest, not merely empty: the frame this is chosen from is the board just
        finished, and a cell deep inside empty space is the one most likely to still be
        empty on the board that replaces it.
        """
        empty = board.body == board.bg
        if not empty.any() or empty.all():
            return None
        ys, xs = np.where(~empty)
        best, spot = -1, None
        for y in range(board.rows):
            for x in range(board.cols):
                if not empty[y, x]:
                    continue
                d = int(np.min(np.maximum(np.abs(ys - y), np.abs(xs - x))))
                if d > best:
                    best, spot = d, (x, y)
        return spot

    def _action_for(self, step: tuple[int, int]) -> int:
        for aid, d in self._dirs.items():
            if d == step:
                return aid
        return 1

    @staticmethod
    def _toward(cur: tuple[int, int], goal: tuple[int, int]) -> tuple[int, int] | None:
        if cur[0] != goal[0]:
            return (1 if goal[0] > cur[0] else -1, 0)
        if cur[1] != goal[1]:
            return (0, 1 if goal[1] > cur[1] else -1)
        return None

    def _click(self, board: _Board, model: dict[str, Any],
               pos: dict[Any, tuple[int, int]], key: Any) -> Step | None:
        side, oy, ox = board.lattice
        if key[0] == "v":
            cell = (pos[key][0], 0)
        elif key[0] == "h":
            cell = (0, pos[key][1])
        else:
            sh = model["shapes"][key[1]]
            px, py = pos[key]
            rel = min(sh["rel"])
            cell = (px + rel[0], py + rel[1])
        c = side // 2
        return (6, (ox + side * cell[0] + c, oy + side * cell[1] + c))
