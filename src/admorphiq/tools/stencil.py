"""Stencil tool — satisfy small instruction glyphs printed onto a lattice of equal tiles.

Recovered from frames alone in round r101 and deepened on 2026-08-27. The mechanic, as it is
now measured rather than guessed:

  * the board is a lattice of equal square tiles at a constant pitch;
  * a site holds either a TILE (clickable, carries one state colour) or a STENCIL (inert);
  * a stencil's centre names a MARKER colour, and its eight outer cells each speak about the
    lattice neighbour in that direction: one ink says "that neighbour MUST be the marker",
    another says "it must NOT be", and a third is printed where there is no tile to speak of;
  * clicking a tile advances every tile in its EFFECT MASK one step around a colour cycle.

⛔ The effect mask is the part that was missing, and its absence is exactly why the tool stopped
four levels in. A tile drawn in one flat colour moves only itself. A tile whose art carries a
second colour is announcing a bigger reach: each off-colour cell of its 3x3 art marks a lattice
direction that moves WITH it. On the level that had been recorded as an impassable wall, three
tiles carry a plus of off-colour cells; the earlier model read them as decoration, clicked them
as if they were ordinary, and destroyed two neighbours per click.

⛔ The recorded wall was also mis-diagnosed. The round page said the neighbourhood model
"self-contradicts — 4 tiles demanded in two colours at once". It does not: the contradiction was
manufactured by reading "must NOT be the marker" as "must be the OTHER colour", which is the same
statement only while the cycle has exactly two colours. One level runs a cycle of three. Solved as
an inequality there is no contradiction anywhere — checked on all six boards.

⛔ Nothing here is written down: not the tile size, not the pitch, not the palette, not which ink
means which, not the effect masks. Every one of those is derived, because a constant recovered by
hand does not transfer to a private game, which is the entire point of the generic-tool track.

The derivations that are easy to get wrong, each of which DID fail a measurement first:

  * a coloured FRAME touches every tile, so plain connected components return the whole board
    as one blob — `segment.peel_containers` treats a component far larger than its siblings as a
    container;
  * two unrelated panels can sit 2 pixels apart, so the lattice step is the COMMONEST gap
    between origins, never the smallest;
  * the ink -> role code cannot be guessed from ink frequency (both inks appear exactly four
    times on the first board). It is read off the solved panels drawn beside the live board, and
    then CARRIED, because the next level ships no worked example at all;
  * a tile with a reach mask breaks one-click-at-a-time greed: retiring one stencil's demand
    breaks a neighbour's. Coupled boards are SOLVED as a linear system over the cycle, not walked.

Full failure ledger: `.wiki/wiki/rounds/r101_tool-development.md`.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, frame_2d, has_frame, levels_completed
from admorphiq.tools.segment import (
    square_regions,
)

__all__ = [
    "StencilTool",
    "Demand",
    "tiles",
    "all_tiles",
    "read_code",
    "plan",
    "pitch",
    "board_model",
]

Grid = Any
Cell = tuple[int, int]


def all_tiles(g: Grid) -> dict[Cell, dict[str, Any]]:
    """Every equal tile on screen — the worked examples live in the panels that are not live."""
    return square_regions(g)


def tiles(g: Grid) -> dict[Cell, dict[str, Any]]:
    """Only the tiles of the LIVE board, when the game frames one."""
    kept = square_regions(g)
    live = {o: t for o, t in kept.items() if t["framed"]}
    return live or kept


def pitch(origins: list[Cell], side: int = 0) -> int:
    """The lattice step is the COMMONEST gap between origins, never the smallest."""
    gaps: list[int] = []
    for axis in (0, 1):
        vals = sorted({o[axis] for o in origins})
        gaps += [b - a for a, b in zip(vals, vals[1:]) if b - a >= side]
    return Counter(gaps).most_common(1)[0][0] if gaps else 0


def _art(g: Grid, origin: Cell, side: int = 6) -> list[list[int]]:
    """The 3x3 glyph a tile carries — one sample per cell of its own 3x3 division.

    The cell size is the tile's side over three, derived rather than assumed: the pre-2026-08-27
    version hard-coded a stride of 2, which is the answer for a 6-pixel tile and for nothing else.
    """
    y0, x0 = origin
    unit = max(1, side // 3)
    return [[int(g[y0 + r * unit][x0 + c * unit]) for c in range(3)] for r in range(3)]


def _is_stencil(art: list[list[int]]) -> bool:
    """A stencil names ONE cell in the marker colour — itself. A tile repeats its own colour.

    Measured on the coupled board, which carries tiles drawn `[[14,6,14],[6,14,6],[14,6,14]]`:
    read as stencils they taught the ink code two roles no real stencil uses and the level
    planned nothing. Counting the centre colour separates the two kinds with no threshold.
    """
    marker = art[1][1]
    return sum(row.count(marker) for row in art) == 1


def _mask(art: list[list[int]]) -> set[Cell]:
    """Which lattice neighbours move WITH this tile, in (dy, dx) lattice steps.

    A tile always moves itself. Every cell of its art drawn in something other than its own
    colour marks one more direction. A flat tile therefore yields `{(0, 0)}` and behaves exactly
    as the pre-2026-08-27 model assumed — which is why four levels cleared under that model and
    the fifth, the first to print reach onto its tiles, did not.
    """
    own = art[1][1]
    out = {(0, 0)}
    for r in range(3):
        for c in range(3):
            if art[r][c] != own:
                out.add((r - 1, c - 1))
    return out


def read_code(g: Grid, board: dict[Cell, dict[str, Any]], step: int) -> dict[int, bool]:
    """Learn ink -> ROLE (demands the marker / forbids it) from the solved panels on screen.

    A panel counts as worked only when its ink -> colour map is ONE-TO-ONE: an untouched board
    maps every ink to the blank colour, which is a map that carries no code. The role is stored,
    never the colour — the first board is painted in 8 and the second in 12.
    """
    votes: Counter[tuple[int, bool]] = Counter()
    for origin, tile in board.items():
        if len(tile["colours"]) == 1:
            continue
        art = _art(g, origin, tile["size"])
        if not _is_stencil(art):
            continue
        marker = art[1][1]
        y0, x0 = origin
        seen: dict[int, set[int]] = {}
        for r in range(3):
            for c in range(3):
                if (r, c) == (1, 1):
                    continue
                nb = board.get((y0 + (r - 1) * step, x0 + (c - 1) * step))
                if nb is None or len(nb["colours"]) != 1:
                    continue
                seen.setdefault(art[r][c], set()).add(next(iter(nb["colours"])))
        if len(seen) < 2 or any(len(v) != 1 for v in seen.values()):
            continue
        if len({next(iter(v)) for v in seen.values()}) < len(seen):
            continue
        for k, v in seen.items():
            votes[(k, next(iter(v)) == marker)] += 1
    out: dict[int, bool] = {}
    for (k, role), _ in votes.most_common():
        out.setdefault(k, role)
    return out


class Demand:
    """What the stencils around one tile jointly require of it.

    ⛔ The forbidden colours are held as an EXCLUSION, never as "the other colour". Those two
    readings agree only while the cycle has exactly two colours, and this game runs one board on
    three. Read positively, that board reports four tiles demanded in two colours at once and the
    tool refuses to act — which is precisely the contradiction the round page recorded as an
    impassable wall. Read as an inequality it is an ordinary board with an ordinary answer: the
    third colour, which satisfies both stencils and is not on screen to be named until a tile
    reaches it.
    """

    __slots__ = ("must", "forbid", "broken")

    def __init__(self) -> None:
        self.must: int | None = None
        self.forbid: set[int] = set()
        self.broken = False

    def demand(self, colour: int) -> None:
        if self.must is not None and self.must != colour:
            self.broken = True
        self.must = colour

    def refuse(self, colour: int) -> None:
        self.forbid.add(colour)

    def satisfied_by(self, colour: int) -> bool:
        return colour not in self.forbid and (self.must is None or colour == self.must)

    def impossible(self) -> bool:
        return self.broken or (self.must is not None and self.must in self.forbid)

    def target(self, palette: set[int]) -> int | None:
        """The one colour that satisfies this demand, when the visible cycle leaves only one."""
        if self.must is not None:
            return self.must
        left = palette - self.forbid
        return next(iter(left)) if len(left) == 1 else None


def board_model(
    g: Grid, code: dict[int, bool]
) -> tuple[dict[Cell, int], dict[Cell, set[Cell]], dict[Cell, Demand], int, int] | None:
    """Read the live board as (tile states, effect masks, per-tile demands, pitch, tile side).

    `None` when the frame carries no lattice this tool can speak about. An impossible demand is
    left in place deliberately — the caller refuses to act on it, and silence is what keeps a
    won level.
    """
    board = tiles(g)
    if not board:
        return None
    side = next(iter(board.values()))["size"]
    step = pitch(list(board), side)
    if step <= 0:
        return None
    arts = {o: _art(g, o, side) for o in board}
    stencils = {o: a for o, a in arts.items() if len(board[o]["colours"]) > 1 and _is_stencil(a)}
    state = {o: a[1][1] for o, a in arts.items() if o not in stencils}
    masks = {o: _mask(arts[o]) for o in state}
    demands: dict[Cell, Demand] = {}
    for (y0, x0), art in stencils.items():
        marker = art[1][1]
        for r in range(3):
            for c in range(3):
                if (r, c) == (1, 1):
                    continue
                role = code.get(art[r][c])
                if role is None:
                    continue                  # the third ink marks an EMPTY site; it says nothing
                at = (y0 + (r - 1) * step, x0 + (c - 1) * step)
                if at not in state:
                    continue
                want = demands.setdefault(at, Demand())
                if role:
                    want.demand(marker)
                else:
                    want.refuse(marker)
    return state, masks, demands, step, side


def _gf2(rows: list[list[int]], width: int) -> list[int] | None:
    """Least-index particular solution of an augmented GF(2) system, or None if inconsistent.

    Free variables are pinned to 0 and the pivot order is the column order, which makes the
    answer a FUNCTION of the board rather than of the search. That matters: the plan is recomputed
    from scratch after every single click, so a solver that wandered between equally valid
    solutions would spend the level undoing itself.
    """
    work = [r[:] for r in rows]
    pivots: list[int] = []
    r = 0
    for col in range(width):
        src = next((i for i in range(r, len(work)) if work[i][col]), None)
        if src is None:
            continue
        work[r], work[src] = work[src], work[r]
        for i in range(len(work)):
            if i != r and work[i][col]:
                work[i] = [a ^ b for a, b in zip(work[i], work[r])]
        pivots.append(col)
        r += 1
    if any(row[width] and not any(row[:width]) for row in work):
        return None
    out = [0] * width
    for i, col in enumerate(pivots):
        out[col] = work[i][width]
    return out


def _coupled_clicks(
    state: dict[Cell, int],
    masks: dict[Cell, set[Cell]],
    demands: dict[Cell, Demand],
    step: int,
) -> list[Cell]:
    """Solve a board whose tiles move their neighbours, as a linear system over a 2-state cycle.

    ⛔ Only over TWO states. With a longer cycle the same board is a system over Z_k, and the two
    colours currently on screen are not proof the cycle is that short — so an under-determined
    board returns nothing rather than guessing, and the tool falls silent. Both coupled boards
    measured here run two states; the three-state board has no coupled tiles.
    """
    # The cycle a tile walks is not printed anywhere. What IS on screen is every colour a tile
    # holds plus every colour a stencil names, and their union is the cycle so far.
    palette = set(state.values()) | {d.must for d in demands.values() if d.must is not None}
    palette |= {c for d in demands.values() for c in d.forbid}
    if len(palette) != 2:
        return []
    targets: dict[Cell, int] = {}
    for site, want in demands.items():
        pick = want.target(palette)
        if pick is None:
            return []
        targets[site] = pick
    lo, hi = sorted(palette)
    bit = {lo: 0, hi: 1}
    order = sorted(state)
    at = {t: n for n, t in enumerate(order)}
    rows: list[list[int]] = []
    for site, pick in sorted(targets.items()):
        row = [0] * (len(order) + 1)
        for tile, mask in masks.items():
            for dy, dx in mask:
                if (tile[0] + dy * step, tile[1] + dx * step) == site:
                    row[at[tile]] ^= 1
        row[len(order)] = bit[pick] ^ bit[state[site]]
        rows.append(row)
    sol = _gf2(rows, len(order))
    if sol is None:
        return []
    return [order[i] for i, v in enumerate(sol) if v]


def plan(g: Grid, code: dict[int, bool] | None = None) -> tuple[list[Cell], dict[int, bool]]:
    """Every click the live stencils call for, plus the ink code in force."""
    carried = code or {}
    every = all_tiles(g)
    if every:
        side = next(iter(every.values()))["size"]
        learned = read_code(g, every, pitch(list(every), side))
        if learned:
            carried = learned
    if not carried:
        return [], carried
    model = board_model(g, carried)
    if model is None:
        return [], carried
    state, masks, demands, step, side = model
    # ⛔ Refuse to act on a model that contradicts itself. One tile demanded in two colours at
    # once means the reading is wrong for this board, and this game charges an ACTION BUDGET per
    # level that a wrong plan burns straight through. Silence keeps what is already won.
    if any(d.impossible() for d in demands.values()):
        return [], carried
    if any(len(m) > 1 for m in masks.values()):
        want = _coupled_clicks(state, masks, demands, step)
    else:
        # Independent tiles: a tile that fails its demand is advanced one step and re-read. The
        # cycle's LENGTH and ORDER stay unknown and unneeded — "not yet right" is a complete
        # instruction when a click can only affect the tile under it, and it is what carries the
        # three-colour board, whose third colour never appears until a tile is clicked onto it.
        want = sorted(t for t, d in demands.items() if not d.satisfied_by(state[t]))
    unit = max(1, side // 3)          # aim at the tile's middle cell, whatever its size
    return [(y + unit, x + unit) for y, x in want], carried


class StencilTool:
    """Harness tool wrapping the stencil mechanic."""

    name = "stencil"

    def __init__(self) -> None:
        self._code: dict[int, bool] = {}
        self._level: int | None = None
        self._seen: set[str] = set()

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        g = frame_2d(obs)
        board = tiles(g)
        if len(board) < 4:
            return 0.0
        marked = [o for o, t in board.items() if len(t["colours"]) > 1]
        if not marked:
            return 0.0
        clicks, _ = plan(g, self._code)
        # ⛔ NO consolation bid. Returning 0.4 for "there is a lattice with a marked tile here"
        # made this tool bid on ANOTHER game's board — measured by the cross-bid audit, 0.40 on a
        # game it cannot solve. That is the same defect this round rejected in two other authors'
        # tools and then found twice in my own. A tool with no plan bids ZERO.
        return 0.9 if clicks else 0.0

    def reset(self) -> None:
        """The ink code survives a level change — the game teaches it once and then stops.

        The visited-state set does not: a new board revisits nothing.
        """
        self._seen = set()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Stateless: the plan is recomputed from each frame, so nothing accumulates here."""

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        g = frame_2d(obs)
        # ⛔ Stop on a REVISITED board. A demand count that fails to fall is not the signal —
        # one click can retire one stencil's demand while breaking a neighbour's, and requiring
        # a strict decrease killed a level that legitimately plateaus. A repeated state is
        # unambiguous: the plan is cycling. Here that matters because clicking on regardless
        # burned 130 actions on one level and lost every level already won (4 -> 0).
        # Hash the TILE MAP, not the frame: this game marches an action counter one pixel per
        # action, so a whole-frame hash is unique every step and never detects anything.
        stamp = repr(sorted((o, sorted(v["colours"])) for o, v in tiles(g).items()))
        if stamp in self._seen:
            return []
        self._seen.add(stamp)
        clicks, self._code = plan(g, self._code)
        # One click at a time. The frame after a level-up still shows the board just finished,
        # so a batch computed once runs the previous level's plan against the next level's board.
        return [(6, (x, y)) for y, x in clicks[:1]]
