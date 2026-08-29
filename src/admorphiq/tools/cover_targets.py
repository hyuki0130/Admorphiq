"""Slide skeleton pieces until their arms cover a board's pinned target marks.

The family this reads: the board carries a handful of small MARKS, each a 3x3 ring of one
flat colour with a differently-coloured pip at its middle, and PIECES — thin skeletal shapes
(a cross, an X, a bar, a rectangle outline) drawn in the pip colours. The level is won when
every mark's pip stands on a piece cell of that pip's own colour. Nothing else about the
board matters, so the game reduces to: choose, for each piece, the rigid translation that
between them cover every pip, then walk the pieces there.

Three things are LEARNED rather than assumed, because assuming any of them was wrong on the
board this was built against:

* Which action moves which way, and by how far. The tool issues a move, watches the cells
  shift, and records the vector. A move that changes nothing is retried before the action is
  believed inert, because these boards swallow actions during animations.
* WHAT A PIECE IS. Pieces that share a colour and touch are one blob to any segmenter, and
  this board has three such. So objecthood comes from motion: the cells that vanish, plus
  the cells that appear shifted back by the move vector, are one object. That estimate is
  never an over-claim — it can miss cells a move left standing, and those are recovered by
  union as further moves are seen — so a covering translation found from it is real.
* Which piece the controls are driving. The driven piece wears a single odd-coloured cell at
  its middle, which is a frame fact but an unreliable one when that cell is hidden under a
  mark, so what actually moved always overrules it.
"""

from __future__ import annotations

from collections import Counter
from heapq import heappop, heappush
from itertools import product
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, base_hash, frame_2d, has_frame
from admorphiq.tools.segment import background, board_changed

__all__ = ["CoverTargetsTool"]

Cell = tuple[int, int]

# A mark is a pip ringed by its 8 neighbours: the smallest shape that can say "here".
_MARK = 3
# An action is only believed inert after it has failed to move anything this many times.
_INERT_AFTER = 3
# A remembered piece is recognised in a new view once this much of it is still on show.
_RECOGNISE = 0.5
# What a repaint is worth in moves, so a pairing that needs none is preferred.
_REPAINT = 40
# How far a piece may be walked in from the edge before its shape is taken as measured.
_NUDGES = 8


class CoverTargetsTool:
    """Cover every target pip with a piece of that pip's colour (see module docstring)."""

    name = "cover_targets"

    def __init__(self) -> None:
        self._effect: dict[int, tuple[int, int]] = {}
        self._select: int | None = None
        self._noeffect: Counter[int] = Counter()
        self.reset()

    # --- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        """Drop the per-level board; the learned control map survives, it is the game's."""
        self._spec: tuple[int, list[tuple[int, int, int]]] | None = None
        self._parts: list[dict[str, Any]] = []
        self._blobs: dict[int, set[Cell]] = {}
        self._wheel: int | None = None
        self._acted: int | None = None
        self._grid: np.ndarray | None = None
        self._odd: list[Cell] = []
        self._probes = 0
        self._edge = 0
        self._paint: dict[Cell, int] = {}
        self._legs: tuple[Any, list[tuple[int, int]], Any] = (None, [], None)
        self._pairing: dict[int, int] = {}
        self._handover = True
        self._rigid = False
        self._idle = 0
        self._stuck = False
        self._noplan = False

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """The harness's transition hook; the tool learns from its own frames in propose."""

    def state_key(self, frame: np.ndarray) -> str:
        """What counts as PROGRESS while this tool holds the board.

        Progress is measured as reaching a state not seen before, and by default that state is
        the raw frame — a fact about the BOARD, not about the tool. The two come apart exactly
        when this tool has no covering plan: it proposes nothing, the actions it declined are
        filled by probes, and those shuffle pieces into frames never seen before. Novelty never
        runs out, so the stall that would hand the board on never arrives, and a tool that has
        already bid ZERO holds the level to the end of its allowance.

        ⛔ Measured on the board this was built against, whose sixth level asks for a plus whose
        bar is NOT at its middle and a rectangle outline whose sides are not the ones it starts
        with. Neither is a translation of anything on the board, so no plan exists there and none
        ever appears — the pip count stood at 8 of 8 uncovered across 480 consecutive proposals,
        of which 463 were empty. The level was held for 200 actions, lost, held for 201 more,
        lost again, and then cleared by another tool in 63 against an allowance of 200. That is
        401 actions of the game's score spent sitting on a board this tool cannot read.

        So: while a plan is being followed the answer is the board, exactly as before — that path
        is untouched. While none exists, the answer is what this tool KNOWS: its pieces, where it
        believes they stand, and how many pips are still uncovered. A probe that teaches it
        something moves that on and the clock rightly restarts; a probe that merely stirs the
        board does not, and the stall arrives.
        """
        if not self._stuck:
            return base_hash(frame)
        known = sorted(
            (-1 if p["colour"] is None else int(p["colour"]), p["anchor"], len(p["shape"]))
            for p in self._parts
        )
        pips = self._spec[1] if self._spec is not None else []
        left = sum(1 for r, c, v in pips if not self._covered(r, c, v))
        return f"cover_targets:noplan:{known}:{left}"

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence, which is zero unless a covering translation actually exists."""
        if not has_frame(obs):
            return 0.0
        simple, _ = availability(obs)
        if len([a for a in simple if a in (1, 2, 3, 4, 5)]) < 4:
            return 0.0
        grid = frame_2d(obs)
        spec = self._marks(grid)
        if spec is None:
            return 0.0
        blobs = self._blobs_of(grid, spec)
        pips = {p[2] for p in spec[1]}
        if not pips <= set(blobs):
            return 0.0
        if any(_solid(frozenset(blobs[colour])) for colour in pips):
            return 0.0
        for colour in pips:
            want = [(r, c) for r, c, v in spec[1] if v == colour]
            if _offsets(frozenset(blobs[colour]), want):
                return 0.85
        return 0.0

    # --- perception --------------------------------------------------------

    def _marks(self, grid: np.ndarray) -> tuple[int, list[tuple[int, int, int]]] | None:
        """The goal: the ring colour, and every (row, col, pip colour) it encircles."""
        if self._spec is not None:
            return self._spec
        h, w = grid.shape
        bg = background(grid.tolist())
        found: dict[int, list[tuple[int, int, int]]] = {}
        for r in range(1, h - 1):
            for c in range(1, w - 1):
                pip = int(grid[r, c])
                if pip in bg:
                    continue
                ring = {
                    int(grid[r + dy, c + dx])
                    for dy in (-1, 0, 1)
                    for dx in (-1, 0, 1)
                    if dy or dx
                }
                if len(ring) != 1:
                    continue
                ringc = ring.pop()
                if ringc == pip or ringc in bg:
                    continue
                if not _standing_clear(grid, r, c, bg):
                    continue
                found.setdefault(ringc, []).append((r, c, pip))
        if not found:
            return None
        ringc, marks = max(found.items(), key=lambda kv: len(kv[1]))
        if len(marks) < 2:
            return None
        self._spec = (ringc, marks)
        return self._spec

    def _blobs_of(
        self, grid: np.ndarray, spec: tuple[int, list[tuple[int, int, int]]]
    ) -> dict[int, set[Cell]]:
        """Every piece-coloured cell on the board, gathered by colour.

        Cells under a mark are dropped rather than guessed at: a piece running through one is
        invisible there, and inventing the crossing added cells an X-shaped piece never had.
        The remembered shapes fill those gaps instead.
        """
        ringc, marks = spec
        hidden = {
            (r + dy, c + dx)
            for r, c, _ in marks
            for dy in (-1, 0, 1)
            for dx in (-1, 0, 1)
        }
        chrome = _chrome(grid)
        blocked = set(background(grid.tolist())) | {ringc}
        h, w = grid.shape
        out: dict[int, set[Cell]] = {}
        for r in range(h):
            for c in range(w):
                if (r, c) in chrome or (r, c) in hidden:
                    continue
                v = int(grid[r, c])
                if v not in blocked:
                    out.setdefault(v, set()).add((r, c))
        # The driven piece wears one odd cell at its middle. On a solid piece that cell is
        # part of the body and its colour flips as the controls move on, so hand it back to
        # whatever it touches — otherwise the piece's size flickers by one every turn.
        self._odd = [next(iter(c)) for v, c in out.items() if len(c) == 1]
        for spot in self._odd:
            y, x = spot
            for body in out.values():
                if len(body) < 2:
                    continue
                if any(max(abs(y - a), abs(x - b)) == 1 for a, b in body):
                    body.add(spot)
                    break
        return {v: cells for v, cells in out.items() if len(cells) > 2}

    # --- objecthood from motion --------------------------------------------

    def _learn(self, blobs: dict[int, set[Cell]], grid: np.ndarray) -> None:
        """Attribute the last action: a piece moved, the controls changed hands, or neither."""
        action, before, prev = self._acted, self._blobs, self._grid
        if action is None or prev is None:
            return
        moved = _moved(before, blobs, self._effect.get(action))
        if moved is not None and not self._shifted(moved[1], blobs):
            moved = None
        self._rigid = moved is not None
        if moved is not None:
            cells, vec = moved
            self._effect[action] = vec
            self._noeffect[action] = 0
            self._idle = 0
            self._attribute(cells, vec)
            return
        if board_changed(prev, grid):
            if action not in self._effect:
                self._select = action
            if action == self._select:
                self._handover = True
            self._wheel = None
            self._noeffect[action] = 0
            self._idle = 0
            return
        self._noeffect[action] += 1

    def _shifted(self, vec: tuple[int, int], blobs: dict[int, set[Cell]]) -> bool:
        """Is the driven piece better explained one step along than where it was?

        Not everything that changes the board is a move. A piece being repainted floods with
        its new colour over several turns while standing perfectly still, and taken as motion
        that flood grew a 53-cell cross into a 94-cell smear that could then reach nothing.
        """
        if self._wheel is None or self._wheel >= len(self._parts):
            return True
        mask = _mask(self._parts[self._wheel])
        shown: set[Cell] = set()
        for cells in blobs.values():
            shown |= cells
        here = len(mask & shown)
        if here == 0:
            # The piece is not where the model says at all, so there is nothing to compare
            # against and vetoing here would be a trap door: the anchor could never advance,
            # so the piece could never be found again. Let it through; _relocate repairs it.
            return True
        return len({(y + vec[0], x + vec[1]) for y, x in mask} & shown) > here

    def _attribute(self, cells: set[Cell], vec: tuple[int, int]) -> None:
        """File the cells that just moved against a known piece, or open a new one.

        Whoever held the controls still holds them — only the select action changes that — so
        a move is filed against the driven piece without asking whether it LOOKS like it.
        That matters: a move along one axis only exposes the arms crossing that axis, so two
        moves of one cross can share barely any cells, and asking for a resemblance split it
        into two pieces that then fought each other for the controls.
        """
        target = self._wheel
        if target is None:
            box = (
                min(c[0] for c in cells), min(c[1] for c in cells),
                max(c[0] for c in cells), max(c[1] for c in cells),
            )
            for i, part in enumerate(self._parts):
                mask = _mask(part)
                seat = (
                    min(c[0] for c in mask), min(c[1] for c in mask),
                    max(c[0] for c in mask), max(c[1] for c in mask),
                )
                if all(abs(a - b) <= _MARK for a, b in zip(box, seat)):
                    target = i
                    break
        if target is not None:
            self._handover = False
        if target is None and not self._handover and self._parts:
            # A piece the controls were never passed to cannot be the one that moved. Without
            # this, the flood of a repaint read as motion by nobody in particular and opened a
            # phantom piece, after which the tool believed marks were covered that were not.
            return
        if target is None:
            self._handover = False
            anchor = (min(c[0] for c in cells), min(c[1] for c in cells))
            self._parts.append({
                "colour": None,
                "shape": frozenset((y - anchor[0], x - anchor[1]) for y, x in cells),
                "anchor": (anchor[0] + vec[0], anchor[1] + vec[1]),
                "axes": {0 if vec[0] else 1},
                "nudges": 0,
            })
            self._wheel = len(self._parts) - 1
            self._probes = 0
            return
        part = self._parts[target]
        anchor = part["anchor"]
        sole = part["colour"] is not None and sum(
            1 for q in self._parts if q["colour"] == part["colour"]
        ) == 1
        if not sole:
            # Motion is the only evidence about a piece that shares its colour with another —
            # they are one blob to the eye. When a piece is the only one wearing its colour the
            # blob IS the piece, and taking motion as extra evidence there is actively wrong:
            # on a board where pieces change shape it unioned the before and after and grew a
            # 72-cell outline to 200 cells.
            part["shape"] = part["shape"] | {(y - anchor[0], x - anchor[1]) for y, x in cells}
        part["anchor"] = (anchor[0] + vec[0], anchor[1] + vec[1])
        part["axes"].add(0 if vec[0] else 1)
        self._wheel = target

    def _at_the_wheel(self) -> int | None:
        """Which piece the controls are on, read off the odd cell it wears at its middle.

        Only a hint: the cell is invisible when it happens to lie under a mark. What actually
        moved always wins, and when neither can say, the next move is itself the probe.
        """
        for y, x in self._odd:
            for i, part in enumerate(self._parts):
                mask = _mask(part)
                if not mask:
                    continue
                cy = (min(c[0] for c in mask) + max(c[0] for c in mask)) / 2
                cx = (min(c[1] for c in mask) + max(c[1] for c in mask)) / 2
                if abs(y - cy) <= 1 and abs(x - cx) <= 1:
                    return i
        return None

    def _relocate(self, blobs: dict[int, set[Cell]]) -> None:
        """Find again a piece the model has lost track of.

        Measured under the harness: a piece can slip its anchor — a repaint or a swallowed
        action costs the model a step it cannot attribute — and once its remembered cells
        overlap nothing on the board it wears no colour, belongs to no plan, and the tool
        pushes the same dead move for the rest of the level. Matching the remembered shape
        back onto whatever is on the board recovers it, whatever colour it now wears.
        """
        shown: set[Cell] = set()
        for cells in blobs.values():
            shown |= cells
        if not shown:
            return
        for part in self._parts:
            shape = part["shape"]
            if not shape or _mask(part) & shown:
                continue
            best, score = None, len(shape) // 2
            probes = _spread(set(shape), 8)
            for spot in shown:
                for sy, sx in probes:
                    anchor = (spot[0] - sy, spot[1] - sx)
                    hit = sum(1 for y, x in shape if (anchor[0] + y, anchor[1] + x) in shown)
                    if hit > score:
                        best, score = anchor, hit
            if best is not None:
                part["anchor"] = best
                self._legs = (None, [], None)

    def _reshape(self, blobs: dict[int, set[Cell]]) -> None:
        """Accept that a piece is not the shape it was.

        Deeper boards do not only move pieces around, they CHANGE them — a piece pushed into
        an obstacle comes back with its arms in different places, or taller and narrower than
        it went in. A remembered shape is then simply wrong, and every placement computed from
        it is wrong with it. Only a piece that is the sole wearer of its colour can be re-read
        this way, and only when what is on the board still looks like one piece of about the
        same size: mid-repaint a colour's cells are half of one piece and half of another.
        """
        fenced = set(self._paint)
        for colour, cells in blobs.items():
            mine = [p for p in self._parts if p["colour"] == colour]
            if len(mine) != 1:
                continue
            part = mine[0]
            seen = frozenset(cells - fenced)
            was = _mask(part)
            if not seen or not was or _solid(seen):
                continue
            if not len(was) <= len(seen) * 2 <= len(was) * 4:
                continue
            # Cells OUTSIDE the remembered shape are what marks a real change. Cells missing
            # from it are just occlusion — a piece under a mark or under another piece — and
            # taking those as a reshape threw away every good shape on the first level.
            if len(seen - was) * 4 <= len(was):
                part["odd"] = 0
                continue
            part["odd"] = part.get("odd", 0) + 1
            if part["odd"] < 2:
                continue
            part["odd"] = 0
            anchor = (min(c[0] for c in seen), min(c[1] for c in seen))
            part["shape"] = frozenset((y - anchor[0], x - anchor[1]) for y, x in seen)
            part["anchor"] = anchor
            self._legs = (None, [], None)
            self._pairing = {}

    def _recolour(self, blobs: dict[int, set[Cell]]) -> None:
        """Say which colour each piece is now wearing, by where its cells actually are."""
        for part in self._parts:
            mask = _mask(part)
            best, score = None, 0
            for colour, cells in blobs.items():
                hit = len(mask & cells)
                if hit > score:
                    best, score = colour, hit
            part["colour"] = best

    def _grow(self, blobs: dict[int, set[Cell]], grid: np.ndarray) -> None:
        """Take in cells of a piece that are simply on show but were never seen to move.

        The flood is fenced out of solid patches of colour, which a piece stands on to be
        repainted, AND out of every other piece's own cells, without which one piece crossing
        another was simply absorbed.

        Motion alone under-measures: a piece whose arm ran off the board, once walked back on,
        is fully visible yet still short in memory, and the two cells missing from a cross's
        arm were exactly the ones its winning placement needed. Only a piece that is the sole
        wearer of its colour, once every piece has been met, can be grown this way — where
        several share a colour the blob is several pieces and motion is the only thing that
        tells them apart.
        """
        if not self._rigid:
            # A fuller view is only evidence about a shape while the piece HAS a settled
            # shape. Mid-repaint the colours are flooding across it, and taking that as a
            # view grew one 45-cell piece into a 141-cell smear that then matched no colour
            # at all and could never be planned for again.
            return
        if self._probes <= len(self._parts):
            # Not every piece has shown itself yet, and while that is true a lone part may be
            # standing in for several: on a board of three same-coloured pieces the first one
            # found swallowed all three.
            return
        fenced = set(self._paint)
        for colour, cells in blobs.items():
            mine = [p for p in self._parts if p["colour"] == colour]
            if len(mine) != 1:
                continue
            part = mine[0]
            room = cells - fenced - _near(
                {c for other in self._parts if other is not part for c in _mask(other)}
            )
            seen = set(_mask(part)) & room
            stack = list(seen)
            while stack:
                y, x = stack.pop()
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        spot = (y + dy, x + dx)
                        if spot in room and spot not in seen:
                            seen.add(spot)
                            stack.append(spot)
            ay, ax = part["anchor"]
            if not _mask(part) <= seen:
                # The view has to CONTAIN the whole remembered piece to be a fuller view of
                # it. Anything else is a different shape, and unioning the two grew a 72-cell
                # outline through 112 and 152 to 200 on the board where pieces are reshaped.
                continue
            part["shape"] = frozenset((y - ay, x - ax) for y, x in seen)

    # --- planning ----------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """One action toward covering the pips, or nothing — and say which it was.

        A step of its own is the tool acting on a plan or on a piece it is still measuring.
        Nothing at all means it has no move to make on this board, which is the state `state_key`
        exists to report: it must be a fact the tool records about itself, not something the
        harness has to infer from an empty list it has already replaced with a probe.
        """
        self._noplan = False
        steps = self._advance(frames, obs)
        # ⛔ `not steps` is not the whole of it. A tool that parks on the select control to keep
        # the board still is still a tool with no plan, and if that were read as progress the
        # stall would never come — the parking action changes the frame, so the board-hash answer
        # would look novel every turn and the level would be held to the end of its allowance
        # exactly as before.
        self._stuck = self._noplan or not steps
        return steps

    def _advance(self, frames: list[Any], obs: Any) -> list[Step]:
        """One action toward covering the pips, learning the board as it goes."""
        if not has_frame(obs):
            return []
        grid = frame_2d(obs)
        spec = self._marks(grid)
        if spec is None:
            return []
        blobs = self._blobs_of(grid, spec)
        self._edge = grid.shape[0] - 1
        self._paint = {c: int(grid[c]) for c in _fat(grid, {spec[0]})}
        self._learn(blobs, grid)
        self._relocate(blobs)
        self._recolour(blobs)
        self._reshape(blobs)
        self._grow(blobs, grid)
        if self._wheel is None:
            self._wheel = self._at_the_wheel()
        self._blobs, self._grid, self._acted = blobs, grid, None

        pips = spec[1]
        gap = [(r, c) for r, c, v in pips if not self._covered(r, c, v)]
        if not gap:
            return []
        plan = self._assign(pips, blobs)
        if plan is None:
            # Discovery first: a colour that looks absent from the board may just belong to a
            # piece not met yet, and dipping before then drove one piece onto another.
            hunt = self._discover(blobs, pips)
            if hunt:
                return hunt
            plan = self._scheme(pips, blobs)
        if plan is None:
            self._noplan = True
            return self._park()
        # ⛔ Serve the piece already in the seat. The plan is ordered cheapest-move-first, and
        # taking it in that order made the tool cycle PAST a piece that still had work to do
        # and cycle back for it later: the select control advances one seat per press, so a
        # visiting order that ignores the ring pays for the detour. Measured on the board this
        # tool carries: four presses where two would do, on a level that cost 46 against a
        # human 42. Whoever is seated and still has a move gets it; only a seated piece with
        # nothing left hands the controls on.
        seated = next(
            (v for i, v in plan if i == self._wheel and v != (0, 0)), None
        )
        if self._wheel is not None and seated is not None:
            return self._walk(self._wheel, seated)
        for i, vec in plan:
            if vec == (0, 0):
                continue
            if self._wheel is not None and self._wheel != i:
                return self._cycle()
            return self._walk(i, vec)
        return []

    def _covered(self, r: int, c: int, colour: int) -> bool:
        """Is this pip already standing on a piece of its own colour?

        Only the remembered pieces can answer: the pip's own cell is hidden under its mark,
        so the frame shows the mark there whether a piece runs through it or not.
        """
        return any(
            part["colour"] == colour and (r, c) in _mask(part) for part in self._parts
        )

    def _assign(
        self, pips: list[tuple[int, int, int]], blobs: dict[int, set[Cell]]
    ) -> list[tuple[int, tuple[int, int]]] | None:
        """One translation per piece that together cover every pip, cheapest first."""
        step = self._stride()
        if not step or not self._parts:
            return None
        chosen: list[tuple[int, tuple[int, int]]] = []
        for colour in {v for _, _, v in pips}:
            want = [(r, c) for r, c, v in pips if v == colour]
            mine = [i for i, p in enumerate(self._parts) if p["colour"] == colour]
            if not mine:
                return None
            picks = _cover(
                [(i, _mask(self._parts[i])) for i in mine], want, step, self._unmoved(blobs, colour)
            )
            if picks is None:
                return None
            chosen.extend(picks)
        chosen.sort(key=lambda iv: abs(iv[1][0]) + abs(iv[1][1]))
        return chosen

    def _scheme(
        self, pips: list[tuple[int, int, int]], blobs: dict[int, set[Cell]]
    ) -> list[tuple[int, tuple[int, int]]] | None:
        """Decide which pieces wear which colour, then where each one goes.

        When the marks ask for a colour no piece is wearing, the board is not unsolvable — it
        is telling you where to go, since the only fixed thing on it wearing that exact colour
        is where a piece acquires it. But WHICH piece takes WHICH colour is not free, in two
        ways both measured on this board. A cross covers a row and a column and an X covers
        two diagonals, so painting them the obvious way round left both unable to reach their
        marks. And a colour may want SEVERAL pieces: six marks of one colour scattered over
        the board cannot be covered by any single skeleton, and while this searched one piece
        per colour it found no plan at all and proposed nothing for the rest of the level.
        """
        step = self._stride()
        if not step or not self._parts:
            return None
        wanted = sorted({v for _, _, v in pips})
        if set(self._pairing.values()) == set(wanted):
            # Keep a pairing once made. Re-deciding it every turn flipped which piece was to
            # take which colour between two neighbouring squares, and the piece paced between
            # them: the cheapest pairing seen from here is not the cheapest seen from there.
            held = self._lay(self._pairing, pips, blobs)
            if held is not None:
                return held
        best: tuple[int, dict[int, int], list[tuple[int, tuple[int, int]]]] | None = None
        for combo in product(range(len(wanted) + 1), repeat=len(self._parts)):
            pairing = {i: wanted[c] for i, c in enumerate(combo) if c < len(wanted)}
            if set(pairing.values()) != set(wanted):
                continue
            toll = sum(
                _REPAINT for i, c in pairing.items() if self._parts[i]["colour"] != c
            )
            if best is not None and toll >= best[0]:
                continue
            plan = self._lay(pairing, pips, blobs)
            if plan is None:
                continue
            cost = toll + sum(abs(v[0]) + abs(v[1]) for _, v in plan)
            if best is None or cost < best[0]:
                best = (cost, pairing, plan)
        if best is None:
            return None
        self._pairing = best[1]
        return best[2]

    def _lay(
        self,
        pairing: dict[int, int],
        pips: list[tuple[int, int, int]],
        blobs: dict[int, set[Cell]],
    ) -> list[tuple[int, tuple[int, int]]] | None:
        """Turn a piece-to-colour pairing into the moves that carry it out, or None."""
        plan: list[tuple[int, tuple[int, int]]] = []
        for colour in sorted(set(pairing.values())):
            mine = [i for i, c in pairing.items() if c == colour]
            want = [(r, c) for r, c, v in pips if v == colour]
            picks = _cover(
                [(i, _mask(self._parts[i])) for i in mine],
                want,
                self._stride(),
                self._unmoved(blobs, colour),
            )
            if picks is None:
                return None
            for i, off in picks:
                if self._parts[i]["colour"] == colour:
                    plan.append((i, off))
                    continue
                dip = self._toward_patch(i, colour, blobs)
                if dip is None:
                    return None
                plan.append((i, dip))
        plan.sort(key=lambda iv: abs(iv[1][0]) + abs(iv[1][1]))
        return plan

    def _toward_patch(
        self, part: int, colour: int, blobs: dict[int, set[Cell]]
    ) -> tuple[int, int] | None:
        """The shortest push that lands this piece on a fixed patch of that colour.

        The patch is picked out of the cells of that colour by connectivity, not by asking
        whether ALL of them form a block: two stray cells of the wanted colour elsewhere on
        the board made a perfectly good 4x4 patch read as no patch at all, and the tool then
        had no move to offer for the rest of the level.
        """
        step = self._stride()
        patch = _patches(self._unmoved(blobs, colour))
        if not step or not patch:
            return None
        mask = _mask(self._parts[part])
        best: tuple[int, int, tuple[int, int]] | None = None
        for sy, sx in patch:
            for my, mx in mask:
                off = (_snap(sy - my, step), _snap(sx - mx, step))
                rank = (self._stains(mask, off, colour), abs(off[0]) + abs(off[1]))
                if off == (0, 0) or (best is not None and rank >= best[:2]):
                    continue
                if not _aboard(mask, off, self._edge + 1):
                    continue
                if any((y + off[0], x + off[1]) in patch for y, x in mask):
                    best = (*rank, off)
        return None if best is None else best[2]

    def _stains(self, mask: frozenset[Cell], vec: tuple[int, int], colour: int | None) -> int:
        """How many cells of a foreign colour patch this move would put the piece onto.

        Standing on a patch is how a piece is repainted, so a route across one is not free.
        Measured: a piece taken to the colour it needed was repainted again on its very next
        move, because the way out of the patch it had just used ran across its neighbour.
        """
        return sum(
            1
            for y, x in mask
            if self._paint.get((y + vec[0], x + vec[1]), colour) != colour
        )

    def _unmoved(self, blobs: dict[int, set[Cell]], colour: int) -> frozenset[Cell]:
        """Cells of this colour that no known piece accounts for; they stay where they are."""
        known: set[Cell] = set()
        for part in self._parts:
            if part["colour"] == colour:
                known |= _mask(part)
        return frozenset(blobs.get(colour, set()) - known)

    def _discover(
        self, blobs: dict[int, set[Cell]], pips: list[tuple[int, int, int]] | None = None
    ) -> list[Step]:
        """No plan yet — finish learning the piece in hand, then take the next one.

        A piece is only fully seen once it has moved on BOTH axes: one axis exposes only the
        arms that cross it. So the piece in hand is nudged along the axis it has not moved on
        — and if no action is yet known to push that way, an untried action is spent finding
        one, rather than repeating a move that cannot teach anything new.

        ⛔ The nudge is not direction-free. Measured on the board this tool carries: the nudge
        took whichever action happened to be first in the learned control map, which sent two
        of three pieces AWAY from the marks they were about to be walked to — six moves spent
        going out and coming back on a level that cost 46 against a human 42. A piece that must
        be moved to be measured can be measured on its way, so the nudge now goes toward the
        middle of the still-uncovered marks wearing the piece's own colour.
        """
        if self._wheel is not None:
            part = self._parts[self._wheel]
            goal = self._mark_for(part, pips)
            for axis in sorted({0, 1} - part["axes"]):
                pick = self._toward(axis, _mask(part), blobs, goal)
                if pick is not None:
                    return self._emit(pick)
            inward = self._inward(part)
            if inward is not None:
                return self._emit(inward)
            if self._probes > len(self._parts):
                return []
            self._probes += 1
            return self._cycle()
        blind = self._blind()
        if blind is not None:
            return self._emit(blind)
        head = self._heading(blobs, pips) if not self._parts else None
        if head is not None:
            return self._emit(head)
        known = [a for a in self._effect if a in self._usable()]
        return self._emit(known[0]) if known else []

    def _heading(
        self, blobs: dict[int, set[Cell]], pips: list[tuple[int, int, int]] | None
    ) -> int | None:
        """Which known push carries the driven piece toward a mark, before ANY piece is known.

        ⛔ Only before any piece is measured. Offered on every wheel-less turn instead, it took
        a game from eight levels to four: with a piece already known the same choice recurs deep
        in a level, where an action that closes on a mark can be one the board REFUSES, and three
        refusals retire a control the tool still needs.

        The first move of a level is made with no measured piece at all, so the choice used to
        fall to whichever action came first in the learned control map. Measured: that was up,
        on a board where two of the three pieces had to go down, and each such move is paid for
        twice — once going out and once coming back. The driven piece is not a mystery even
        then: it wears a single odd-coloured cell at its middle, so the push that closes on the
        nearest mark of that piece's colour is the one to spend.
        """
        want = [(r, c, v) for r, c, v in pips or [] if not self._covered(r, c, v)]
        if not want or not self._effect:
            return None
        goal: tuple[float, float] | None = None
        here: tuple[float, float] | None = None
        seat = self._odd[0] if self._odd else None
        if seat is not None:
            near = [
                (min(abs(y - seat[0]) + abs(x - seat[1]) for y, x in cells), colour)
                for colour, cells in blobs.items()
                if cells
            ]
            if near:
                mine = [w for w in want if w[2] == min(near)[1]]
                if mine:
                    here = (float(seat[0]), float(seat[1]))
                    pick = min(mine, key=lambda w: abs(w[0] - seat[0]) + abs(w[1] - seat[1]))
                    goal = (float(pick[0]), float(pick[1]))
        if goal is None or here is None:
            cells = [c for group in blobs.values() for c in group]
            if not cells:
                return None
            here = (sum(c[0] for c in cells) / len(cells),
                    sum(c[1] for c in cells) / len(cells))
            goal = (sum(w[0] for w in want) / len(want),
                    sum(w[1] for w in want) / len(want))
        gap = abs(goal[0] - here[0]) + abs(goal[1] - here[1])
        best: tuple[float, int] | None = None
        for action, vec in self._effect.items():
            if action not in self._usable():
                continue
            after = abs(goal[0] - here[0] - vec[0]) + abs(goal[1] - here[1] - vec[1])
            if best is None or gap - after > best[0]:
                best = (gap - after, action)
        return None if best is None else best[1]

    def _inward(self, part: dict[str, Any]) -> int | None:
        """Bring a piece that hangs off the board far enough in to be measured.

        A piece whose arm runs past the edge is short by exactly the cells that never rendered,
        and planning off that short shape rejected the placement that actually wins — two
        missing cells on a cross's right arm was the whole difference. You cannot measure what
        is off screen, so move it on screen first.
        """
        if part["nudges"] >= _NUDGES:
            return None
        mask = _mask(part)
        edge = self._edge
        for axis, want in ((0, 1), (0, -1), (1, 1), (1, -1)):
            over = min(c[axis] for c in mask) <= 0 if want > 0 else \
                max(c[axis] for c in mask) >= edge
            if not over:
                continue
            for action, vec in self._effect.items():
                if action in self._usable() and vec[axis] * want > 0 and not vec[1 - axis]:
                    part["nudges"] += 1
                    return action
        return None

    def _blind(self) -> int | None:
        """An action never yet tried, which is the only kind that can teach a new direction."""
        for a in self._usable():
            if a not in self._effect and a != self._select:
                return a
        return None

    def _mark_for(
        self, part: dict[str, Any], pips: list[tuple[int, int, int]] | None
    ) -> Cell | None:
        """Where the still-uncovered marks of this piece's colour lie, as one heading.

        Only a heading, and deliberately a weak one: which piece takes which mark is not
        settled until a plan exists, so this asks for nothing more than the middle of the marks
        wearing the piece's own colour. ⚠️ The NEAREST such mark was tried first and is worse —
        a piece usually has to cover several, and the closest one pointed one piece backwards
        on a level the middle got right (level 3 of the board this carries: 52 actions against
        50). When no mark of that colour is left there is no heading and the nudge falls back
        to the direction it used before.
        """
        if not pips:
            return None
        if not _mask(part):
            return None
        want = [(r, c) for r, c, v in pips
                if v == part["colour"] and not self._covered(r, c, v)]
        if not want:
            return None
        return (sum(w[0] for w in want) // len(want), sum(w[1] for w in want) // len(want))

    def _toward(
        self,
        axis: int,
        mask: frozenset[Cell],
        blobs: dict[int, set[Cell]],
        goal: Cell | None = None,
    ) -> int | None:
        """A push along this axis that keeps the piece on the board, or a way to find one.

        With a heading, the push that CLOSES on it is preferred over the one that opens: both
        teach the piece's shape equally, and only one of them has to be undone afterwards.
        """
        board = next(iter(blobs.values()), None)
        limit = 0 if board is None else max(max(c) for c in board) + 1
        cy = (min(c[0] for c in mask) + max(c[0] for c in mask)) / 2 if mask else 0.0
        cx = (min(c[1] for c in mask) + max(c[1] for c in mask)) / 2 if mask else 0.0
        here = (cy, cx)
        best: tuple[float, int] | None = None
        for action, vec in self._effect.items():
            if action not in self._usable() or bool(vec[0]) != (axis == 0):
                continue
            after = [(y + vec[0], x + vec[1]) for y, x in mask]
            if not any(0 <= y < limit and 0 <= x < limit for y, x in after):
                continue
            if goal is None:
                return action
            gain = abs(goal[axis] - here[axis]) - abs(goal[axis] - (here[axis] + vec[axis]))
            if best is None or gain > best[0]:
                best = (gain, action)
        if best is not None:
            return best[1]
        return self._blind()

    # --- controls ----------------------------------------------------------

    def _stride(self) -> int:
        """How far one move carries a piece, once a move has actually been seen."""
        seen = [abs(v) for vec in self._effect.values() for v in vec if v]
        return min(seen) if seen else 0

    def _usable(self) -> list[int]:
        return [a for a in (1, 2, 3, 4, 5) if self._noeffect[a] < _INERT_AFTER]

    def _emit(self, action: int) -> list[Step]:
        self._acted = action
        return [(action, None)]

    def _park(self) -> list[Step]:
        """No plan exists on this board — stand still rather than stir it.

        The action is spent either way: a tool that returns nothing has its turn filled by a
        probe, and a probe pushes pieces around. That matters here because the board is about to
        be handed to whoever CAN read it, and the boards this family draws are not all
        recoverable — pieces are re-dyed by the pads they touch and re-shaped by the press, so a
        long random walk can leave two pieces wearing one colour, which is a board no reader can
        tell apart. The control that hands the driving seat between pieces moves nothing, so
        pressing it holds the board exactly as it stands until the stall arrives.

        Measured, and worth more than the tidiness: spending those turns on probes instead
        cost 121 actions before the board changed hands and 63 after it, for a level of 184;
        parking cost 91 and 48, for 139. Against an allowance of 200 and a human baseline of 139
        that is the difference between a level barely inside its budget and one that costs
        exactly what a person spends on it. ⛔ Why the wait itself was longer is NOT established
        — only that the stirred board took longer to hand over and longer to solve once handed.
        """
        if self._select is not None and self._select in self._usable():
            return self._emit(self._select)
        return []

    def _cycle(self) -> list[Step]:
        """Hand the controls to another piece."""
        if self._select is not None and self._select in self._usable():
            return self._emit(self._select)
        blind = [a for a in self._usable() if a not in self._effect]
        return self._emit(blind[0]) if blind else []

    def _walk(self, index: int, want: tuple[int, int]) -> list[Step]:
        """Follow a route already committed to, or work one out and start it.

        Recomputing the route every turn livelocks: from one square the cheapest way round a
        patch begins by going down, and from the square that reaches, it begins by going back
        up, so the piece paces between two squares forever. The route is therefore decided
        once and followed, and thrown away only when the piece does not end up where the plan
        said it would — which is how a move the game refused gets noticed.
        """
        part = self._parts[index]
        here = part["anchor"]
        goal = (here[0] + want[0], here[1] + want[1])
        booked, legs, due = self._legs
        if booked != (index, goal) or due != here or not legs:
            legs = self._route(part, want)
            if not legs:
                return self._drive(want, part)
        leg = legs[0]
        for action, vec in self._effect.items():
            if vec == leg and action in self._usable():
                self._legs = ((index, goal), legs[1:], (here[0] + leg[0], here[1] + leg[1]))
                return self._emit(action)
        self._legs = (None, [], None)
        return self._drive(want, part)

    def _route(self, part: dict[str, Any], target: tuple[int, int]) -> list[tuple[int, int]]:
        """The cheapest way to `target`, counting a repaint as expensive.

        Stepping toward the goal one axis at a time is not enough on a board where standing
        on a patch changes what you are: a piece that had just acquired the colour it needed
        was repainted by its own first step away, then walked back for more, forever. Pricing
        a repaint into a search over the positions the controls can reach lets it go round.
        """
        vecs = [v for a, v in self._effect.items() if a in self._usable()]
        if not vecs or target == (0, 0):
            return []
        mask = _mask(part)
        colour = part["colour"]
        limit = self._edge + 1
        dist: dict[Cell, int] = {(0, 0): 0}
        came: dict[Cell, tuple[Cell, tuple[int, int]]] = {}
        queue: list[tuple[int, Cell]] = [(0, (0, 0))]
        while queue:
            cost, pos = heappop(queue)
            if pos == target:
                break
            if cost > dist.get(pos, cost + 1):
                continue
            for vec in vecs:
                step = (pos[0] + vec[0], pos[1] + vec[1])
                if abs(step[0]) > limit or abs(step[1]) > limit:
                    continue
                if not _aboard(mask, step, limit):
                    continue
                spoil = any(
                    self._paint.get((y + step[0], x + step[1]), colour) != colour
                    for y, x in mask
                )
                paid = cost + 1 + (_REPAINT if spoil else 0)
                if paid < dist.get(step, paid + 1):
                    dist[step] = paid
                    came[step] = (pos, vec)
                    heappush(queue, (paid, step))
        if target not in came:
            return []
        legs: list[tuple[int, int]] = []
        spot = target
        while spot != (0, 0):
            spot, vec = came[spot]
            legs.append(vec)
        legs.reverse()
        return legs

    def _drive(self, want: tuple[int, int], part: dict[str, Any] | None = None) -> list[Step]:
        """The action that pushes the wanted way, or the cheapest way to find one out."""
        dy, dx = want
        mask = _mask(part) if part else frozenset()
        colour = part["colour"] if part else None
        ranked: list[tuple[int, int, int]] = []
        for rank, axis in enumerate(((dy, 0), (0, dx))):
            if axis == (0, 0):
                continue
            for action, vec in self._effect.items():
                if action in self._usable() and _aligned(vec, axis):
                    ranked.append((self._stains(mask, vec, colour), rank, action))
        if ranked:
            return self._emit(min(ranked)[2])
        blind = [a for a in self._usable() if a not in self._effect and a != self._select]
        if blind:
            return self._emit(blind[0])
        self._idle += 1
        return [] if self._idle > 2 else self._cycle()


# --- geometry ---------------------------------------------------------------


def _mask(part: dict[str, Any]) -> frozenset[Cell]:
    """Where the piece's cells are right now."""
    ay, ax = part["anchor"]
    return frozenset((ay + y, ax + x) for y, x in part["shape"])


def _moved(
    before: dict[int, set[Cell]], after: dict[int, set[Cell]], known: tuple[int, int] | None
) -> tuple[set[Cell], tuple[int, int]] | None:
    """The cells of the one piece that moved, at their old spot, and by how far.

    Vanished cells were certainly the mover; appeared cells were certainly the mover, one
    move ago. Their union is a piece — possibly only part of one, when a move slid a piece
    along its own length and most of it stayed put, which is why shapes accumulate.
    """
    gone: set[Cell] = set()
    came: set[Cell] = set()
    for colour in set(before) | set(after):
        gone |= before.get(colour, set()) - after.get(colour, set())
        came |= after.get(colour, set()) - before.get(colour, set())
    # A cell that merely changed from one piece's colour to another's is one piece passing
    # over another, not a piece arriving or leaving. Counting those as motion grew a hollow
    # rectangle from 39 cells to 83 as it slid across its neighbours.
    gone, came = gone - came, came - gone
    if not gone or not came:
        return None
    vec = _vector(gone, came, known)
    if vec is None:
        return None
    return gone | {(y - vec[0], x - vec[1]) for y, x in came}, vec


def _vector(
    gone: set[Cell], came: set[Cell], known: tuple[int, int] | None
) -> tuple[int, int] | None:
    """How far the board's content shifted, by best agreement rather than by centroid.

    An action's step is a property of the control, so once measured it is simply used. What
    changed cannot re-derive it: a bar sliding ALONG its own length leaves only its two ends
    changed, and both a 3-cell step and a 43-cell leap explain those ends equally well — the
    leap even better. A centroid is no help either; it read a cross's 3-cell move as 5,
    because the mean of what changed is dragged by whichever arm happened to move wholesale.
    """
    if known is not None and known != (0, 0):
        return known

    def fits(vec: tuple[int, int]) -> int:
        return len({(y + vec[0], x + vec[1]) for y, x in gone} & came)

    best, score = None, (0, 0)
    for g in _spread(gone):
        for c in _spread(came):
            vec = (c[0] - g[0], c[1] - g[1])
            if vec == (0, 0):
                continue
            rank = (fits(vec), -abs(vec[0]) - abs(vec[1]))
            if rank > score:
                best, score = vec, rank
    return best if score[0] else None


def _spread(cells: set[Cell], take: int = 12) -> list[Cell]:
    """A handful of cells spanning the set, enough to propose every plausible shift."""
    ordered = sorted(cells)
    if len(ordered) <= take:
        return ordered
    stride = len(ordered) / take
    return [ordered[int(i * stride)] for i in range(take)]


def _offsets(mask: frozenset[Cell], pips: list[Cell]) -> set[Cell]:
    """Every translation of `mask` that lands a piece cell on each of `pips`."""
    cand: set[Cell] | None = None
    for py, px in pips:
        here = {(py - my, px - mx) for my, mx in mask}
        cand = here if cand is None else (cand & here)
        if not cand:
            return set()
    return cand or set()


def _cover(
    parts: list[tuple[int, frozenset[Cell]]],
    pips: list[Cell],
    step: int,
    fixed: frozenset[Cell],
) -> list[tuple[int, tuple[int, int]]] | None:
    """Split the pips between the pieces of one colour, minimising total moves."""
    todo = frozenset(p for p in pips if p not in fixed)
    if not todo:
        return [(i, (0, 0)) for i, _ in parts]
    choices: list[list[tuple[frozenset[Cell], tuple[int, int]]]] = []
    for _, mask in parts:
        best: dict[frozenset[Cell], tuple[int, int]] = {}
        seen: set[tuple[int, int]] = {(0, 0)}
        for py, px in todo:
            for my, mx in mask:
                seen.add((_snap(py - my, step), _snap(px - mx, step)))
        for off in seen:
            if off[0] % step or off[1] % step:
                continue
            got = frozenset(p for p in todo if (p[0] - off[0], p[1] - off[1]) in mask)
            cost = abs(off[0]) + abs(off[1])
            if got not in best or cost < abs(best[got][0]) + abs(best[got][1]):
                best[got] = off
        choices.append(sorted(best.items(), key=lambda kv: abs(kv[1][0]) + abs(kv[1][1])))

    found: list[tuple[int, tuple[int, int]]] | None = None
    cheapest = None

    def walk(k: int, left: frozenset[Cell], spent: int, picks: list[tuple[int, int]]) -> None:
        nonlocal found, cheapest
        if cheapest is not None and spent >= cheapest:
            return
        if not left:
            found, cheapest = [(parts[j][0], picks[j]) for j in range(len(picks))], spent
            return
        if k >= len(choices):
            return
        for got, off in choices[k]:
            walk(k + 1, left - got, spent + abs(off[0]) + abs(off[1]), [*picks, off])

    walk(0, todo, 0, [])
    return found


def _aboard(mask: frozenset[Cell], vec: tuple[int, int], limit: int) -> bool:
    """Would the piece still have its middle on the board after this move?

    A piece may hang over an edge — one winning placement on this board does — but a move
    that would carry its middle off is simply refused, and a plan that ends there is a plan
    the controls cannot carry out. Without this the tool chose a repaint spot beyond the top
    edge and paced beneath it until the level's step budget ran out.
    """
    ys = [c[0] + vec[0] for c in mask]
    xs = [c[1] + vec[1] for c in mask]
    mid = ((min(ys) + max(ys)) // 2, (min(xs) + max(xs)) // 2)
    return 0 <= mid[0] < limit and 0 <= mid[1] < limit


def _standing_clear(grid: np.ndarray, r: int, c: int, bg: set[int]) -> bool:
    """Is this ringed pip alone on the board, rather than a detail inside a bigger drawing?

    A mark is placed on empty board, so the square just outside its ring is background. Without
    this, ring-and-pip patterns occurring INSIDE another game's dense glyphs read as marks, and
    the tool bid on a game it has no plan for.
    """
    h, w = grid.shape
    clear = 0
    edge = 0
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            if max(abs(dy), abs(dx)) != 2:
                continue
            y, x = r + dy, c + dx
            if not (0 <= y < h and 0 <= x < w):
                edge += 1
            elif int(grid[y, x]) in bg:
                clear += 1
    return clear + edge >= 12


def _chrome(grid: np.ndarray) -> set[Cell]:
    """Cells belonging to a counter pinned along an edge, and no others.

    A fixed margin is too blunt: it swallowed a real column of a piece hanging off the right
    of the board. A counter is recognisable instead — a full edge line with nothing of the
    board's own background in it, made of at most two colours in solid runs, which is what a
    bar that marches one cell per action looks like.
    """
    h, w = grid.shape
    bg = background(grid.tolist())
    lines = {
        (0, 0): [(0, x) for x in range(w)],
        (0, 1): [(h - 1, x) for x in range(w)],
        (1, 0): [(y, 0) for y in range(h)],
        (1, 1): [(y, w - 1) for y in range(h)],
    }
    out: set[Cell] = set()
    for cells in lines.values():
        run = [int(grid[y, x]) for y, x in cells]
        if any(v in bg for v in run) or len(set(run)) > 2:
            continue
        if sum(1 for a, b in zip(run, run[1:]) if a != b) > 1:
            continue
        out |= set(cells)
    return out


def _fat(grid: np.ndarray, skip: set[int]) -> set[Cell]:
    """Cells belonging to something filled in, rather than to a one-cell-thin skeleton.

    The pieces on these boards are skeletons — a cross, an X, a bar — so any same-coloured
    region that fills its own box in both directions is furniture, and on this board that
    means a patch of colour a piece is repainted by. Measured the wrong way first: asking for
    a cell with all eight neighbours its own colour found NOTHING here, because each patch is
    a small square set inside a frame of another colour and every one of its cells touches
    that frame. With the test finding nothing, routes were priced as though standing on a
    patch were free, and a piece walked back into one immediately after leaving it.

    The marks' own rings are skipped: eight cells in a three-by-three box pass any fullness
    test, and treating a mark as furniture made routes avoid the very cells a piece is being
    sent to stand on.
    """
    h, w = grid.shape
    bg = background(grid.tolist())
    seen = np.zeros(grid.shape, dtype=bool)
    out: set[Cell] = set()
    for y in range(h):
        for x in range(w):
            if seen[y, x] or int(grid[y, x]) in bg or int(grid[y, x]) in skip:
                continue
            colour = int(grid[y, x])
            stack = [(y, x)]
            seen[y, x] = True
            blob: list[Cell] = []
            while stack:
                cy, cx = stack.pop()
                blob.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] \
                            and int(grid[ny, nx]) == colour:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if _solid(frozenset(blob)):
                out |= set(blob)
    return out


def _near(cells: set[Cell]) -> set[Cell]:
    """The cells themselves and everything touching them."""
    return {
        (y + dy, x + dx)
        for y, x in cells
        for dy in (-1, 0, 1)
        for dx in (-1, 0, 1)
    }


def _patches(cells: frozenset[Cell]) -> frozenset[Cell]:
    """The cells of `cells` that belong to a filled-in block, by connectivity."""
    left = set(cells)
    out: set[Cell] = set()
    while left:
        stack = [left.pop()]
        blob = list(stack)
        while stack:
            y, x = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    spot = (y + dy, x + dx)
                    if spot in left:
                        left.discard(spot)
                        blob.append(spot)
                        stack.append(spot)
        if _solid(frozenset(blob)):
            out |= set(blob)
    return frozenset(out)


def _solid(cells: frozenset[Cell]) -> bool:
    """Does this fill its own bounding box in both directions — a patch, not a piece?

    The pieces on these boards are skeletons — a cross, an X, a bar — so they cover a few per
    cent of the box they span, and requiring solidity is what stops a piece being mistaken
    for a supply of its own colour and driven into. Two details are measured, not chosen: the
    box must be thick in both directions, because a bar fills its own one-cell-tall box
    perfectly; and a few cells may be missing, because a patch with another piece lying
    across it showed 15 of its 16 cells and was rejected as a patch.
    """
    if len(cells) < 4:
        return False
    ys = [c[0] for c in cells]
    xs = [c[1] for c in cells]
    h = max(ys) - min(ys) + 1
    w = max(xs) - min(xs) + 1
    if h < 2 or w < 2:
        return False
    return len(cells) * 4 >= h * w * 3


def _snap(value: int, step: int) -> int:
    """The nearest translation the controls can actually produce."""
    return int(round(value / step)) * step


def _aligned(vec: tuple[int, int], axis: tuple[int, int]) -> bool:
    """Does `vec` push along `axis` — same sign, same axis, nothing sideways?"""
    dy, dx = vec
    ay, ax = axis
    if ay:
        return dx == 0 and dy * ay > 0
    return dy == 0 and dx * ax > 0
