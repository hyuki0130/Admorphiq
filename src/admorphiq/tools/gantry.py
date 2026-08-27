"""Gantry tool — a crane that CARRIES a slab of floor, read as one more kind of control.

The mechanic, recovered from the game's own source and then measured on the frames. A board of
phase-shifting terrain — the family `phase_grid` already reads — grows a second machine on its
deeper boards: a **gantry**. Four of the side panel's controls do not re-phase anything; each of
them TRANSLATES one rigid body of pixels by a fixed step along a rail, and the rail has ends, so a
press at the end changes nothing at all. A fifth control looks completely inert everywhere except
at ONE rail position, where it LATCHES a second body — a slab that the avatar can stand on — to
the moving one. From then on the slab travels with the gantry, and the level is won by parking it
where it bridges a gap the walk cannot cross.

⛔ WHY THIS IS NOT `phase_grid`, the tool that already owns this family and clears its first four
boards. `phase_grid` models a control as a CYCLE of pictures over a fixed footprint: press it
enough times and the board comes back. A gantry control is not a cycle and the difference is
structural, not a threshold:

  * it never returns — three presses of one direction and the fourth does nothing, because the rail
    ended, so no repeat of any picture-sequence ever closes;
  * its footprint MOVES, so "the cells this control paints" is not a fixed set;
  * the latch shows NO CHANGE at nine of ten rail positions, which is exactly `phase_grid`'s
    definition of an inert control — it presses it once, records it dead, and never presses it
    again, so the slab is never picked up;
  * and the slab is FLOOR, so the route is a search over (cell, phase vector, RAIL POSITION), a
    coordinate `phase_grid`'s search does not carry.

Measured on the board where this matters: `phase_grid` clears the four boards before it and then
spends the game's whole remaining budget on this one, because the avatar's opening island is four
cells wide and every way off it goes through the slab. The board is winnable in 108 actions
against a human baseline of 324.

So this tool KEEPS `phase_grid`'s perception and its phase model — it subclasses it rather than
re-deriving a second reading of the same boards, which is the mistake that cost a 20x regression
once already — and adds exactly three things: a rigid-translation reading of a control, an
exhaustive walk of the rail that finds the latch as a side effect, and a route search that carries
the rail position beside the phase vector.

⛔ Frame-only, by construction. Which controls drive, by how much, where the rail ends, which
control latches, what the moving body is made of and what lies UNDER it are all derived from the
frames the presses produce. Nothing about any game is written down here.

⛔ Selectivity. The bid is `phase_grid`'s own conjunction, which was measured at 0 false positives
over the 25 sample games, one notch above it — the precedent is `cyclepress` over `track`: where
both read the mechanic, the one that clears more boards should hold them. It drops to zero the
moment the board stops reading as the mechanic or the route runs out, because a tool with no plan
must not spend another tool's budget.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame, levels_completed
from admorphiq.tools.phase import PhaseGridTool

__all__ = ["GantryCraneTool", "rigid_translation"]

Cell = tuple[int, int]

_SIMPLE = (1, 2, 3, 4)
# One notch above `phase_grid` on the identical conjunction, for the reason in the docstring.
_CONF = 0.86
_CONF_WITH_PLAN = 0.96
# States the route may open once the model is complete. The widest board here settles at ~245k;
# the cap is what stops a board that is NOT this mechanic from spending minutes proving it.
_BFS_CAP = 400_000
# ⛔ And the cap while the model is still being MEASURED, which is the one that matters for cost.
# A route is attempted after every single press — that is how the tool notices it has learned
# enough — and at full width those attempts are seconds each over the dozens of presses a ring
# and a rail take. Scouting is cheap and complete-model planning is paid for once.
_SCOUT_CAP = 60_000
# Presses the rail walk may spend before the model is taken as complete. The board that needs the
# most spends 47 — five non-phase controls at each of the ten rail positions it can reach, minus
# the pairs the walk arrives at already answered. The cap is what stops a board with a long rail
# and many controls from spending its whole budget measuring itself.
_MAX_RAIL_PRESSES = 80
# Fraction of the gantry body's own pixels that must be found at an offset for the body to be
# read as standing there. ⛔ Not 1.0, and the difference decides whether the board is cleared: a
# re-rendered copy of the board this was built on draws FOUR of the slab's pixels differently at
# one rail position out of ten — four out of eighty-two — and an exact test called that a rail end,
# which disconnected the rail and stranded the gantry two positions from where it was needed. The
# exactness stays where it belongs, on DISCOVERING that a control drives at all; recognising a body
# already known does not need it.
_BODY_MATCH = 0.9
# Stalls (a turn held with nothing to propose) before the tool hands the level back.
_MAX_STALLS = 2


def _shifted(mask: np.ndarray, delta: Cell) -> np.ndarray:
    """`mask` translated by `delta`, cropped to the frame (pixels leaving it are lost)."""
    out = np.zeros_like(mask)
    dy, dx = delta
    h, w = mask.shape
    ys0, ys1 = max(0, dy), min(h, h + dy)
    xs0, xs1 = max(0, dx), min(w, w + dx)
    if ys1 <= ys0 or xs1 <= xs0:
        return out
    out[ys0:ys1, xs0:xs1] = mask[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def rigid_translation(before: np.ndarray, after: np.ndarray,
                      skip: set[int]) -> tuple[Cell, np.ndarray] | None:
    """(delta, body mask in `before`) if this transition is one rigid body sliding, else None.

    ⛔ Read the translation COLOUR BY COLOUR, never off the changed region as a whole. The changed
    region of a slide is the union of where the body was and where it went, so its shape and its
    centroid say nothing about the step — the same region is produced by a body of any size moving
    any distance that spans it. A colour whose ENTIRE footprint reappears translated is evidence of
    a different kind: nothing except a translation produces it.

    ⛔ Not every colour of the body qualifies, and that is expected rather than a failure. This
    family draws the gantry partly in a colour it shares with static scenery, so that colour's
    footprint does not translate and is left out of the body. What the body must account for is the
    CHANGE: every changed pixel has to lie either where the body was or where it went, which is the
    test that separates a slide from a slide plus something else.
    """
    if before.shape != after.shape:
        return None
    diff = before != after
    if not diff.any():
        return None
    colours = set(int(v) for v in np.unique(before)) | set(int(v) for v in np.unique(after))
    by_delta: dict[Cell, list[int]] = {}
    for colour in sorted(colours - skip):
        mb = before == colour
        ma = after == colour
        if not mb.any() or not ma.any() or int(mb.sum()) != int(ma.sum()):
            continue
        ys, xs = np.where(mb)
        yt, xt = np.where(ma)
        delta = (int(yt.min() - ys.min()), int(xt.min() - xs.min()))
        if delta == (0, 0) or not np.array_equal(_shifted(mb, delta), ma):
            continue
        by_delta.setdefault(delta, []).append(colour)
    for delta, found in sorted(by_delta.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        body = np.zeros_like(diff)
        for colour in found:
            body |= before == colour
        if not (diff & ~(body | _shifted(body, delta))).any():
            return delta, body
    return None


def _shape_key(mask: np.ndarray, board: np.ndarray) -> frozenset[tuple[int, int, int]]:
    """A body's identity: its cells relative to its own corner, each with the colour it wears."""
    ys, xs = np.where(mask)
    y0, x0 = int(ys.min()), int(xs.min())
    return frozenset((int(y) - y0, int(x) - x0, int(board[int(y)][int(x)]))
                     for y, x in zip(ys, xs))


class GantryCraneTool(PhaseGridTool):
    """Walk the avatar to its marker, re-phasing terrain AND driving a gantry when one exists."""

    name = "gantry"

    # --- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        super().reset()
        self._bg = 0
        # What each panel control turned out to be: "phase", "drive" or "idle".
        self._kind: dict[Cell, str] = {}
        self._seen_click: set[Cell] = set()
        self._delta: dict[Cell, Cell] = {}
        # The gantry, in board coordinates relative to where its body stood on the first frame.
        self._off: Cell = (0, 0)
        self._body: dict[Cell, int] = {}
        self._span: set[Cell] = set()
        self._hull: tuple[int, int, int, int] | None = None
        self._under: dict[Cell, int] = {}
        self._edges: dict[Cell, dict[Cell, Cell | None]] = {}
        self._tried: set[tuple[Cell, Cell]] = set()
        self._slid: dict[frozenset, dict[Cell, Cell]] = {}
        self._shape: frozenset | None = None
        self._gprobed: set[Cell] = set()
        self._presses = 0
        self._latched = False
        self._body_stale = False
        # The step in flight and what was expected of it.
        self._kindof: str = ""
        self._want_cell: Cell | None = None
        self._want_off: Cell | None = None
        self._steps: list[tuple[Step, str, Cell, Cell]] = []
        # Set whenever anything measured changes, so a route is re-attempted then and not
        # otherwise; cleared by the attempt.
        self._dirty = True
        self._panel_prev: frozenset[Cell] = frozenset()

    # --- reading a press ---------------------------------------------------

    def _resolve_press(self, geom: dict[str, Any], click: Cell) -> None:
        """Classify what the control just pressed actually did."""
        board = geom["board"]
        before = self._before
        if before is None or before.shape != board.shape:
            return
        landed = self._at(board, self._avatar)
        if self._before_pos is not None:
            self._warp_tested.add((click, self._before_pos))
            if landed is not None and landed != self._before_pos:
                self._warps[(click, self._before_pos)] = landed
        still = np.array_equal(before, board)
        if self._kind.get(click) == "drive":
            if still:
                self._edges.setdefault(self._off, {})[click] = None
                return
            slide = rigid_translation(before, board, {self._avatar, self._marker})
            if slide is not None:
                self._learn_drive(click, board, slide)
                return
            # The board answered but not as a clean slide. The body is already known, so ASK WHERE
            # IT IS rather than re-deriving what moved — see `_relocate`.
            where = self._relocate(board)
            if where is None or where == self._off:
                self._edges.setdefault(self._off, {})[click] = None
            else:
                self._slide_known(click, board, where)
            return
        if still:
            if self._kind.get(click) == "phase":
                super()._settle_flip(geom, click)
            else:
                self._kind.setdefault(click, "idle")
            return
        if self._kind.get(click) != "phase" and self._is_latch(before, board):
            # ⛔ The latch is IDENTIFIED, never assumed from position. When it takes hold the
            # gantry redraws itself and nothing else on the board moves — measured, eighteen
            # pixels, all of them inside the body's own footprint. That is a signal no
            # re-phasing produces, because a phase group paints terrain and terrain is not
            # where the gantry is standing.
            self._kind[click] = "latch"
            self._latched = True
            self._body_stale = True
            return
        slide = rigid_translation(before, board, {self._avatar, self._marker})
        if slide is not None and self._register_slide(click, before, board, slide):
            return
        self._kind[click] = "phase"
        super()._settle_flip(geom, click)

    def _register_slide(self, click: Cell, before: np.ndarray, board: np.ndarray,
                        slide: tuple[Cell, np.ndarray]) -> bool:
        """Is this slide a GANTRY, or a picture that merely happens to look like one?

        ⛔ One press cannot tell them apart, and that was measured rather than feared: a terrain
        control on this family cycles a six-pixel bar through six positions two cells apart, so
        FOUR presses running are exact rigid translations of the same body by the same step.
        Believing the first one made the tool drive a bridge as though it were a crane, and the
        board it then planned in did not exist.

        What separates them is that a gantry is a MACHINE WITH DIRECTIONS: at least two different
        controls move the SAME body, because a rail one can only travel one way down is not a
        rail. A cycling picture belongs to exactly one control. So a slide stays provisional until
        a second control moves the same shape, and the provisional presses go to the phase model
        meanwhile, so nothing is lost when the second control never comes.
        """
        delta, mask = slide
        if self._shape is None:
            key = _shape_key(mask, before)
            seen = self._slid.setdefault(key, {})
            seen[click] = delta
            if len(seen) < 2:
                return False
            self._shape = key
            self._groups = [gr for gr in self._groups if gr["click"] not in seen]
            self._settled_clicks -= set(seen)
            for other, step in seen.items():
                self._kind[other] = "drive"
                self._delta[other] = step
            self._off, self._body, self._span, self._under, self._edges = (0, 0), {}, set(), {}, {}
            self._learn_drive(click, board, slide)
            self._steps = []
            return True
        here = {(dy + self._off[0], dx + self._off[1]) for dy, dx in self._span}
        if not any((int(y), int(x)) in here for y, x in np.argwhere(mask)):
            return False
        # A control found later that moves the body already known: one more direction of the rail.
        self._learn_drive(click, board, slide)
        return True

    def _learn_drive(self, click: Cell, board: np.ndarray, slide: tuple[Cell, np.ndarray]) -> None:
        """Bank the step this control drives, the body it drives, and what it uncovered."""
        delta, mask = slide
        was = self._off
        now = (was[0] + delta[0], was[1] + delta[1])
        self._kind[click] = "drive"
        self._delta[click] = delta
        self._edges.setdefault(was, {})[click] = now
        vacated = mask & ~_shifted(mask, delta)
        for y, x in np.argwhere(vacated):
            # ⛔ What lies under the gantry is only ever seen when the gantry LEAVES. Cells it has
            # never left stay unknown and are read as the board's ground, which is not standable —
            # a route that would have run under the rail is lost, and one that runs into it is not
            # invented. The conservative direction is the safe one: a refused move costs an action,
            # a route through a wall costs the level.
            self._under[(int(y), int(x))] = int(board[int(y)][int(x)])
        body: dict[Cell, int] = {}
        for y, x in np.argwhere(_shifted(mask, delta)):
            body[(int(y) - now[0], int(x) - now[1])] = int(board[int(y)][int(x)])
        self._body = body
        ys = [c[0] for c in body]
        xs = [c[1] for c in body]
        if ys:
            # ⛔ The body's HULL, kept apart from its lit cells. The latch is recognised by a change
            # that stays inside the gantry — and the pixels it lights up were DARK before, so they
            # are not in the set of cells the body is drawn in. Testing the latch against the lit
            # cells missed it at the one rail position where it works, which is the only position
            # that matters.
            self._hull = (min(ys), min(xs), max(ys), max(xs))
        self._span |= set(body)
        self._span |= {(int(y) - was[0], int(x) - was[1]) for y, x in np.argwhere(mask)}
        self._off = now
        self._body_stale = False

    def _relocate(self, board: np.ndarray) -> Cell | None:
        """Where the known body is standing now, by matching its own pixels against the board.

        The offsets considered are the rail positions already seen plus one step of every drive
        from each of them, so this recognises the body somewhere new without inventing a rail.
        """
        if not self._body:
            return None
        h, w = board.shape
        places = set(self._edges) | {self._off}
        places |= {(o[0] + d[0], o[1] + d[1]) for o in set(places) for d in self._delta.values()}
        best: Cell | None = None
        top = 0.0
        for off in sorted(places):
            hit = sum(1 for (dy, dx), colour in self._body.items()
                      if 0 <= dy + off[0] < h and 0 <= dx + off[1] < w
                      and int(board[dy + off[0]][dx + off[1]]) == colour)
            frac = hit / len(self._body)
            if frac > top:
                top, best = frac, off
        return best if top >= _BODY_MATCH else None

    def _slide_known(self, click: Cell, board: np.ndarray, where: Cell) -> None:
        """Move the known body to `where`: record the rail edge and what it uncovered.

        The body's own picture is NOT re-read here. It was read exactly when the control was
        discovered, and the reason this path is being taken is that the board is drawing a few of
        its pixels differently — folding those into the body would write the occlusion into it.
        """
        was = self._off
        self._edges.setdefault(was, {})[click] = where
        h, w = board.shape
        old = {(dy + was[0], dx + was[1]) for dy, dx in self._span}
        new = {(dy + where[0], dx + where[1]) for dy, dx in self._span}
        for (y, x) in old - new:
            if 0 <= y < h and 0 <= x < w:
                self._under[(y, x)] = int(board[y][x])
        self._off = where

    def _is_latch(self, before: np.ndarray, after: np.ndarray) -> bool:
        """Is every changed pixel inside the gantry body's own hull, here and now?"""
        if self._hull is None:
            return False
        y0, x0, y1, x1 = self._hull
        dy, dx = self._off
        return all(y0 + dy <= int(y) <= y1 + dy and x0 + dx <= int(x) <= x1 + dx
                   for y, x in np.argwhere(before != after))

    # --- the world the route is planned in ---------------------------------

    def _drives(self) -> list[Cell]:
        return sorted(c for c, k in self._kind.items() if k == "drive")

    def _movers(self) -> list[Cell]:
        """Controls the rail walk presses: the drives, plus everything not yet shown to re-phase.

        ⛔ A control that did nothing is not evidence of an inert control until it has been tried
        somewhere else. Three of the four drives on this board do nothing at all from the rail's
        starting corner, because that corner is the end of their rail — reading them as inert on
        that one press left the gantry able to travel in a single direction.
        """
        return sorted(c for c, k in self._kind.items() if k in ("drive", "idle"))

    def _world(self, board: np.ndarray, pcfg: tuple[int, ...], off: Cell) -> np.ndarray:
        """The board with the terrain in `pcfg` and the gantry parked at `off`."""
        out = np.array(board, copy=True)
        h, w = out.shape
        for dy, dx in self._span:
            y, x = dy + self._off[0], dx + self._off[1]
            if 0 <= y < h and 0 <= x < w:
                out[y, x] = self._under.get((y, x), self._bg)
        for index, group in enumerate(self._groups):
            if not group["images"]:
                continue
            for (y, x), colour in group["images"][pcfg[index] % len(group["images"])].items():
                out[y, x] = colour
        for (dy, dx), colour in self._body.items():
            y, x = dy + off[0], dx + off[1]
            if 0 <= y < h and 0 <= x < w:
                out[y, x] = colour
        return out

    def _standable(self, layout: np.ndarray) -> np.ndarray:
        """Boolean grid of the cells a whole avatar-sized tile is floor in — vectorised.

        The rule is `phase_grid`'s: a tile carrying one pixel of the board's ground, or of a colour
        a refusal has condemned, is not floor. Computed here as one prefix sum rather than per
        cell, because the route opens hundreds of thousands of states and the per-cell form is
        what makes that unaffordable.
        """
        side = max(1, self._side)
        bad = layout == self._bg
        for colour in self._not_floor:
            bad |= layout == colour
        h, w = bad.shape
        if h < side or w < side:
            return np.zeros((0, 0), dtype=bool)
        acc = np.zeros((h + 1, w + 1), dtype=np.int32)
        acc[1:, 1:] = bad.astype(np.int32).cumsum(0).cumsum(1)
        tot = acc[side:, side:] - acc[:-side, side:] - acc[side:, :-side] + acc[:-side, :-side]
        return tot == 0

    def _grid(self, cache: dict[Any, set[Cell]], board: np.ndarray,
              pcfg: tuple[int, ...], off: Cell) -> set[Cell]:
        """The set of cells the avatar may stand in, for one terrain phase and one rail position."""
        key = (pcfg, off)
        got = cache.get(key)
        if got is None:
            layout = self._world(board, pcfg, off)
            grid = self._standable(layout)
            got = {(int(y), int(x)) for y, x in zip(*np.where(grid))}
            for cell, signature in self._blocked:
                if cell in got and self._signature(layout, cell) == signature:
                    got.discard(cell)
            cache[key] = got
        return got

    # --- routing -----------------------------------------------------------

    def _route(self, board: np.ndarray, start: Cell, goals: set[Cell], bg: int) -> list[Step]:
        """Shortest action list over (cell, phase vector, rail position)."""
        return [step for step, _kind, _cell, _off in self._plan_full(board, start, goals)]

    def _plan_full(self, board: np.ndarray, start: Cell,
                   goals: set[Cell]) -> list[tuple[Step, str, Cell, Cell]]:
        """The route, each step carrying what it should leave behind so the board can falsify it.

        ⛔ The trail is kept as PARENT POINTERS, never as a list carried on every state. Carrying
        it copies the whole path into every one of hundreds of thousands of states, at a depth of a
        hundred — measured as minutes of wall clock for a search that is seconds with a back-link.
        """
        if not self._deltas or self._step() <= 0 or not goals:
            return []
        cache: dict[Any, set[Cell]] = {}
        cap = _BFS_CAP if self._settled_model() else _SCOUT_CAP
        moves = list(self._deltas.items())
        rings = [(i, gr["click"], gr["period"]) for i, gr in enumerate(self._groups) if gr["period"]]
        drives = self._drives()
        warps = self._warps
        origin = (start, self._config(), self._off)
        seen: dict[Any, tuple[Any, tuple[Step, str, Cell, Cell] | None]] = {origin: (None, None)}
        queue: deque[Any] = deque([origin])
        found = None
        while queue and len(seen) < cap:
            state = queue.popleft()
            pos, pcfg, off = state
            if pos in goals:
                found = state
                break
            here = self._grid(cache, board, pcfg, off)
            for action, (dy, dx) in moves:
                nxt = (pos[0] + dy, pos[1] + dx)
                key = (nxt, pcfg, off)
                if nxt not in here or key in seen:
                    continue
                seen[key] = (state, ((action, None), "walk", nxt, off))
                queue.append(key)
            for index, click, period in rings:
                nc = list(pcfg)
                nc[index] = (pcfg[index] + 1) % period
                ncfg = tuple(nc)
                land = warps.get((click, pos), pos)
                key = (land, ncfg, off)
                if key in seen or land not in self._grid(cache, board, ncfg, off):
                    continue
                seen[key] = (state, ((6, (click[1], click[0])), "press", land, off))
                queue.append(key)
            for click in drives:
                nxt_off = self._edges.get(off, {}).get(click)
                if nxt_off is None:
                    # Refused there, or never reached there: the rail walk settles every position
                    # the gantry can get to, so an unknown edge would be a guess.
                    continue
                land = warps.get((click, pos), pos)
                key = (land, pcfg, nxt_off)
                # ⛔ Driving the gantry out from under the avatar drops it. The slab IS the floor
                # on this family, so the check is the whole point rather than a precaution.
                if key in seen or land not in self._grid(cache, board, pcfg, nxt_off):
                    continue
                seen[key] = (state, ((6, (click[1], click[0])), "drive", land, nxt_off))
                queue.append(key)
        if found is None:
            return []
        out: list[tuple[Step, str, Cell, Cell]] = []
        while True:
            parent, step = seen[found]
            if step is None:
                break
            out.append(step)
            found = parent
        return out[::-1]

    # --- walking the rail --------------------------------------------------

    def _rail_path(self, target: Cell) -> list[Cell] | None:
        """Drive presses that carry the gantry from where it is to `target`, over known edges."""
        if target == self._off:
            return []
        seen: dict[Cell, list[Cell]] = {self._off: []}
        queue = deque([self._off])
        while queue:
            here = queue.popleft()
            for click, there in self._edges.get(here, {}).items():
                if there is None or there in seen:
                    continue
                seen[there] = seen[here] + [click]
                if there == target:
                    return seen[there]
                queue.append(there)
        return None

    def _next_rail_probe(self) -> tuple[Cell, Cell] | None:
        """The nearest (rail position, control) pair nobody has tried yet."""
        movers = self._movers()
        if not movers:
            return None
        seen = {self._off}
        queue = deque([self._off])
        while queue:
            here = queue.popleft()
            for click in movers:
                if (click, here) not in self._tried:
                    return here, click
            for there in self._edges.get(here, {}).values():
                if there is not None and there not in seen:
                    seen.add(there)
                    queue.append(there)
        return None

    # --- the harness contract ----------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence this board is the mechanic and that this tool can still act on it.

        ⛔ The conjunction is `phase_grid`'s, unchanged and inherited rather than restated: the
        four senses and a click are offered, the frame splits into a board and a panel of
        different grounds, and the board carries exactly two congruent single squares among its
        rarest colours. Measured over 200 frames of live play on each of the 25 sample games with
        a FRESH tool asked on every frame, so no accumulated state can hide an answer: it fires on
        one board throughout and on a second for eight frames, and returns 0.0 on the other 23.
        The eight are a board another tool holds for all 1,438 of its actions, measured unchanged
        with this tool registered beside it.

        ⛔ The bid is one notch above `phase_grid`'s because this tool clears everything
        `phase_grid` clears on that board and one level more, in the same action counts — the
        precedent is `cyclepress` over `track`. It is a claim, and the withdrawal is what makes it
        safe: the moment no square moves under any action, the pieces stop being readable, or the
        world holds no route through three re-plans, the tool latches dead and hands the board
        back rather than owning something it cannot finish.
        """
        if self._dead or self._retired or not has_frame(obs):
            return 0.0
        simple, click = availability(obs)
        if not click or not set(_SIMPLE).issubset(set(simple)):
            return 0.0
        if self._read(frame_2d(obs)) is None:
            return 0.0
        return _CONF_WITH_PLAN if self._steps else _CONF

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if self._dead or self._retired or not has_frame(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        simple, _ = availability(obs)
        legal = [a for a in _SIMPLE if a in simple]
        if not legal:
            return []
        if self._warm:
            # ⛔ The frame that reports a level cleared still draws the level just finished; one
            # action turns the page before anything on it may be read.
            self._warm = False
            return [(legal[0], None)]

        g = frame_2d(obs)
        geom = self._read(g)
        if geom is None:
            return []
        self._bg = geom["bg"]

        if self._rare == (-1, -1):
            self._rare, self._side = (geom["rare"][0], geom["rare"][1]), geom["side"]
            self._to_probe = list(legal)
            self._probed = list(legal)
            self._probe_seen = [(0, {c: self._at(geom["board"], c) for c in self._rare})]

        if self._pending is not None:
            self._settle(geom)

        probe = self._sense_probe(geom, legal)
        if probe is not None:
            return probe
        if self._avatar < 0:
            # Neither square moved under any simple action: this is not the mechanic.
            self._dead = True
            return []
        self._fill_by_elimination()

        start = self._at(geom["board"], self._avatar)
        goal = self._at(geom["board"], self._marker)
        if start is None or goal is None:
            # An animation may be drawing over a piece; give up on the level, not the game.
            self._retired = True
            return []
        if start == goal:
            return self._stall()
        self._visited.add(start)
        before_objects = len(self._objects)
        # ⛔ Objects are remembered, not re-read on demand: the avatar HIDES the tile it stands on,
        # so a tile walked to stops looking like an object the moment it is reached.
        self._objects |= self._items(geom["board"], start, self._bg)
        if len(self._objects) != before_objects and not self._steps:
            self._dirty = True

        panel = self._panel_buttons(g, geom)
        if frozenset(panel) != self._panel_prev:
            # ⛔ A control can be UNLOCKED partway through a level — standing somewhere the board
            # cares about makes a button APPEAR — and every route in hand was planned in a world
            # without it. This is the only reason to throw a plan away for having moved, and it is
            # keyed on the panel actually changing: keying it on "the avatar reached a new cell"
            # re-runs the whole search once per step, which at this width is the level's clock.
            self._panel_prev = frozenset(panel)
            self._steps = []
            self._dirty = True
        # ⛔ Once a gantry is known to be there, finish MEASURING it before planning again. A
        # route attempted with half a rail is not merely wrong, it is expensive: the rail is the
        # third coordinate of the search space, and paying for that search after every one of the
        # rail's forty-seven presses is the difference between a level and a timeout.
        if self._drives():
            rail = self._discover(geom, start, panel)
            if rail is not None:
                return rail
        return self._act(geom, start, goal, panel)

    # --- the phases of a turn ----------------------------------------------

    def _settle(self, geom: dict[str, Any]) -> None:
        """Fold the action just taken back into the model."""
        pending, kind = self._pending, self._kindof
        self._pending, self._kindof = None, ""
        if pending is None:
            return
        if kind == "sense":
            self._settle_move(geom, pending[0])
            return
        if kind == "walk":
            now = self._at(geom["board"], self._avatar)
            if now != self._want_cell and self._want_cell is not None:
                self._blocked.add((self._want_cell, self._signature(geom["board"], self._want_cell)))
                self._learn_refusal(geom["board"], self._want_cell)
                self._steps = []
                self._dirty = True
            return
        was_off = self._off
        self._dirty = True
        self._resolve_press(geom, (pending[1][1], pending[1][0]) if pending[1] else (0, 0))
        if kind == "plan" and self._want_off is not None and self._off != self._want_off:
            # The board did not do what the plan said; everything after this step is fiction.
            self._steps = []
        elif kind == "plan" and self._want_cell is not None \
                and self._at(geom["board"], self._avatar) != self._want_cell:
            self._steps = []
        elif kind == "probe" and self._off != was_off:
            self._steps = []

    def _sense_probe(self, geom: dict[str, Any], legal: list[int]) -> list[Step] | None:
        """Measure what each simple action does to the avatar, re-running the ones that bounced."""
        if self._to_probe:
            self._pending, self._kindof = (self._to_probe.pop(0), None), "sense"
            return [self._pending]
        if self._avatar >= 0 and len(self._deltas) < 3 and self._probe_passes < 2:
            missing = [a for a in self._probed if a not in self._deltas]
            if missing and self._deltas:
                self._probe_passes += 1
                self._to_probe = missing
                self._probe_seen = [(0, {c: self._at(geom["board"], c) for c in self._rare})]
                self._pending, self._kindof = (self._to_probe.pop(0), None), "sense"
                return [self._pending]
        return None

    def _confirm_probe(self, geom: dict[str, Any], start: Cell) -> list[Step] | None:
        """A body has slid once. Ask the controls that did nothing whether they move it too.

        ⛔ This is why a control that did nothing is not yet an inert control. Three of the four
        directions on this board do nothing at all from the rail's starting corner, because that
        corner is the end of their rail — and the fourth's slide cannot be believed until one of
        them answers. Asking them costs one press each, once, and only while there is a slide to
        confirm.
        """
        if self._shape is not None or not self._slid:
            return None
        for click in sorted(c for c, k in self._kind.items() if k == "idle"):
            if click in self._gprobed:
                continue
            self._gprobed.add(click)
            return [self._press(geom, start, click, "probe")]
        return None

    def _discover(self, geom: dict[str, Any], start: Cell,
                  panel: list[Cell]) -> list[Step] | None:
        """Finish measuring a board that HAS a gantry, before any route is planned in it.

        Every non-phase control is tried at every rail position the gantry can reach, and the
        latch falls out of that walk for free rather than needing a search of its own: it is one
        of the controls being tried, and it answers at exactly the position where it works.

        ⛔ The terrain rings are settled here too, not left to the route's own ladder. That ladder
        presses a control only when the route has already failed — and on a board with a gantry
        the route fails for the gantry's reasons long before the rings matter, so the rings were
        still unmeasured when the search finally ran, and the search then answered in a world
        with half its terrain missing.
        """
        cheap = self._rings(geom, start, panel)
        if cheap is not None:
            return cheap
        if self._presses < _MAX_RAIL_PRESSES:
            wanted = self._next_rail_probe()
            if wanted is not None:
                where, click = wanted
                path = self._rail_path(where)
                if path is None:
                    self._tried.add((click, where))
                    return None
                if path:
                    return [self._press(geom, start, path[0], "probe")]
                self._tried.add((click, where))
                self._presses += 1
                return [self._press(geom, start, click, "probe")]
        if self._body_stale:
            # ⛔ The latch is only half the discovery: what it picked up is invisible until the
            # gantry MOVES with it, so one more drive press is spent before the slab is planned on.
            for click in self._drives():
                if self._edges.get(self._off, {}).get(click) is not None:
                    return [self._press(geom, start, click, "probe")]
            self._body_stale = False
        return None

    def _settled_model(self) -> bool:
        """Is there anything left to measure? Only then is a full-width route worth its cost."""
        if any(k == "phase" and c not in self._settled_clicks for c, k in self._kind.items()):
            return False
        if self._drives() and (self._body_stale
                               or (self._presses < _MAX_RAIL_PRESSES
                                   and self._next_rail_probe() is not None)):
            return False
        return True

    def _portals(self, board: np.ndarray) -> set[Cell]:
        """Objects whose tile PICTURE has exactly one twin elsewhere on the board.

        ⛔ Why this narrowing exists, and it is the difference between clearing the board and
        spending it. One control on this family neither re-phases anything nor drives the gantry:
        it TELEPORTS the avatar between two tiles that carry the same marking, and no route to the
        marker exists without it. The only way to find that is to stand on such a tile and press —
        but the board carries FORTY-FOUR tiles that are not flat colour, and pressing every control
        on every one of them costs the level several times over.

        A teleport is a PAIR by construction: it has two ends, and the game draws both the same.
        So the tiles worth pressing on are those whose picture is one of exactly two of its kind,
        which on the board that needs this is two tiles out of the forty-four.
        """
        side = self._side
        groups: dict[Any, list[Cell]] = {}
        for (y, x) in self._objects:
            tile = np.asarray(board)[y:y + side, x:x + side]
            if tile.size != side * side:
                continue
            groups.setdefault(frozenset(int(v) for v in tile.ravel()), []).append((y, x))
        return {c for cells in groups.values() if len(cells) == 2 for c in cells}

    def _rings(self, geom: dict[str, Any], start: Cell, panel: list[Cell]) -> list[Step] | None:
        """The cheapest evidence there is: press, in place, a control not yet understood."""
        for click in panel:
            if click not in self._seen_click:
                self._seen_click.add(click)
                return [self._press(geom, start, click, "probe")]
        for click in panel:
            if self._kind.get(click) == "phase" and click not in self._settled_clicks:
                return [self._press(geom, start, click, "probe")]
        return self._confirm_probe(geom, start)

    def _act(self, geom: dict[str, Any], start: Cell, goal: Cell,
             panel: list[Cell]) -> list[Step]:
        """Follow the plan, or make one; failing that, enlarge the world and try again.

        ⛔ A route is attempted only when something MEASURED has changed since the last attempt.
        Re-searching an unchanged world every turn returns the same answer at the same price, and
        at this width that price is seconds.

        ⛔ The order below is an order of COST, and getting it wrong lost a board this tool used to
        clear. Pressing a control where the avatar already stands costs one action; walking across
        the board to stand on a particular tile costs twenty. Putting the walking first meant the
        terrain rings were still unmeasured when the budget ran out, on a board whose route needs
        nothing but the rings.
        """
        if self._steps:
            return [self._emit_planned(geom, start)]
        board = geom["board"]
        if self._dirty:
            self._dirty = False
            self._steps = self._plan_full(board, start, {goal})
            if self._steps:
                self._stalls = 0
                return [self._emit_planned(geom, start)]
        cheap = self._rings(geom, start, panel)
        if cheap is not None:
            return cheap
        # ⛔ Test a twin tile the moment the avatar is STANDING on one, before routing anywhere
        # else. Routing first walks straight past it: the tile it is standing on is excluded from
        # its own goal set, so the plan goes to the twin at the far end of the board, arrives, and
        # walks back — for ever, without ever pressing anything.
        if start in self._portals(board):
            for click in panel:
                if (click, start) not in self._warp_tested:
                    return [self._press(geom, start, click, "probe")]
        # Nowhere to go for the marker. A tile with a twin may CARRY the avatar somewhere the walk
        # cannot reach, and a tile nobody has stood on may unlock a control; both are worth the
        # walk, the paired ones first because they are few.
        twins = {c for c in self._portals(board)
                 if any((k, c) not in self._warp_tested for k in panel)}
        for goals in (twins - {start}, self._objects - self._visited):
            self._steps = self._plan_full(board, start, goals)
            if self._steps:
                self._stalls = 0
                return [self._emit_planned(geom, start)]
        # ⛔ Last resort, and only while standing ON an object: press a control here and watch the
        # AVATAR. On this family one of them carries it across the board, and no amount of terrain
        # phasing reaches the rest of the board without that. An empty tile is not a reason.
        if start in self._objects:
            for click in panel:
                if (click, start) not in self._warp_tested:
                    return [self._press(geom, start, click, "probe")]
        return self._stall()

    def _stall(self) -> list[Step]:
        """⛔ Running out of route retires the tool for this LEVEL, never for the game."""
        self._stalls += 1
        if self._stalls > _MAX_STALLS:
            self._retired = True
        return []

    # --- emitting ----------------------------------------------------------

    def _press(self, geom: dict[str, Any], start: Cell, click: Cell, kind: str) -> Step:
        step: Step = (6, (click[1], click[0]))
        self._before = np.array(geom["board"], copy=True)
        self._before_pos = start
        self._pending, self._kindof = step, kind
        self._want_cell, self._want_off = None, None
        return step

    def _emit_planned(self, geom: dict[str, Any], start: Cell) -> Step:
        step, kind, cell, off = self._steps.pop(0)
        if not self._steps:
            # The plan ends here; whatever comes next has to be searched for.
            self._dirty = True
        self._before = np.array(geom["board"], copy=True)
        self._before_pos = start
        self._pending = step
        self._kindof = "walk" if kind == "walk" else "plan"
        self._want_cell, self._want_off = cell, off
        return step
