"""Lattice maze tool — recover a corridor graph from the pixels and walk it to the marked exit.

⛔ Why a plan and not a search. Measured 2026-08-27: on this family the searching generic path
spent 1,119 actions on a level a person finishes in 19, and scored 0.0000. These boards END on
their own step counter — the counter is declared per level and one of them allows only TWENTY
actions — so the budget is not a soft ceiling to explore under, it is the length of the answer.
A walk planned on a map read from the first frame costs the shortest path and nothing else.

The board grammar this tool recovers, all of it from pixels:

  * The board is a LATTICE of same-sized square blocks on a pitch of TWO blocks. Blocks on the
    even/even class are the standing places (nodes). Blocks between two nodes are the corridors:
    drawn = you may walk through, background = a wall. The diagonal class — between four nodes —
    is never drawn on a board of this shape, and that is the discriminator the tool bids on,
    because it is a statement about the whole board that a non-lattice game cannot satisfy.
  * The EXIT is the one node painted a flat colour of its own. Nothing else on the board is a
    flat block of a colour that appears exactly once.
  * The PIECES are nodes drawn as a body colour with a SINGLE pixel of a second colour — a facing
    mark. Several may be present and only one of them answers to the controls.
  * WALLS and everything off the board are the background colour.

⛔ The piece you steer is not distinguishable by looking, so it is CHOSEN and then CHECKED. The
guess is structural: pieces the board draws alike are a crowd, and the odd one out is the one the
player is given (measured on this family: the crowd shares a facing-mark colour). Ties are broken
by distance to the exit, because the board does not put the player next to the door. The check is
free — every proposal re-reads the board, and a piece that did not move the way the control was
meant to move it loses the identity to whichever piece did.

⛔ The controls are NOT assumed. A direction is mapped to a control by trying the natural order
once and then believing the DISPLACEMENT that came back; a control whose observed effect
contradicts the assumption re-writes the map for the rest of the game. Nothing here is spent
learning it, because the first planned move is a move the plan needed anyway.

⛔ CONTACT IS FATAL, and the board does not say so. Measured 2026-08-27 by reading the engine: a
struck piece is redrawn one size larger, which reads like a life being spent — but the redraw is
retried inside the SAME action until the piece is gone, so the three sizes are three frames of one
death, not three lives. A walk that treats the other pieces as scenery loses on the first touch,
and that is exactly how the first version of this tool died four actions into its second board.

The other pieces come in three behaviours and the board draws them identically, so the behaviour is
LEARNED rather than assumed: a piece whose colour class moved on the very first action PATROLS —
it advances one node along its facing every action and turns round at a wall — and a piece whose
class did not move LIES IN WAIT, striking only the one node directly in front of it. So the plan
is made in TIME, not on the map: the patrols are simulated forward and the walk is a shortest path
through (node, tick) that is never where a patrol will be, and never on the node a waiting piece
faces. The third behaviour is below.

⛔ THE PIECES ARE REMOVABLE, and that is the level design, not a bonus. Measured 2026-08-27: on
the third board every route to the door runs through a node a waiting piece faces, so a walk that
only avoids them is provably stuck — and the reason is that STEPPING ONTO a piece destroys it, by
the same three-frame collapse that destroys the player when a piece steps onto the player. Whoever
arrives second dies. So the plan is a search over (node, WHICH PIECES ARE STILL THERE, tick): a
piece is cleared by landing on it, which must be done from a side it is not facing.

⛔ And there is no way to wait. A control the board refuses spends a tick of the counter and
advances NOTHING — the patrols move only when the piece moved — so standing still is a pure loss
and a timed dodge can only be bought by walking a longer way round. The plan therefore searches
(node, tick) over MOVES alone, which is why a route may double back: the detour is the clock.

⛔ THE PIECES CANNOT BE RE-READ EACH FRAME, they have to be REPLAYED. Measured 2026-08-27: two
patrols crossed the same node, the board drew one block, and a planner that re-derives the pieces
from the picture every tick simply lost one — then walked into it. Their motion does not depend on
the player at all, so the model is the board's OPENING piece list plus the moves made since,
replayed from tick zero on every proposal. Replay rather than a carried position, because the
behaviour of a class is learned DURING the level: the moment a class turns out to patrol, every
tick already spent has to be recomputed under the new reading, and a carried position cannot be.
The picture is then only a check — every piece it shows must be somewhere the replay put one —
and the first failure is evidence, not noise: something moved that was not expected to.

⛔ The third behaviour is a piece that FOLLOWS, and it is not worth modelling. It wakes when the
player stands two nodes in front of it and then repeats the player's own moves a couple of ticks
behind, which no forward simulation of ours reproduces — and a wrong prediction about a piece is
worse than no prediction, because the walk steps confidently into it. WHEN a class started moving
is what tells it apart: a patrol is in motion from the first tick of the board, so a class that
stood still for several ticks and then set off was WOKEN. Such a piece is handled REACTIVELY
rather than predicted — it may be anywhere beside where it stands by the next tick, so no node
adjacent to it is entered, but its OWN node still is, because the engine settles the player before
it settles the pieces, so walking INTO a follower destroys it and walking beside one gets the
player destroyed.

⛔ And a failed check must never be repaired by re-reading the picture — except for a follower,
where it must. Measured the same day, both halves: a class was found to patrol while one of its
members was hidden under another piece, the model was re-seeded from what could be SEEN, the
hidden piece was dropped from the world, and it killed the walk four actions later; then the
opposite, a follower strays from the model every single tick, so a re-seed that keeps what it
modelled left a copy of it on every node it had ever stood on until eight phantoms had the walk
cornered. A re-seed keeps what it modelled and ADDS what it cannot account for — but a class known
to follow is re-read whole.

⛔ THE DOOR CAN BE STOOD ON. Measured 2026-08-27: a patrol walked over the exit, the one flat
odd-coloured node vanished from the frame, and a parser that insists on seeing it declared the
whole board unreadable — the tool stopped dead on its fifth level with a valid plan in hand. The
lattice and the door are therefore read ONCE per level and remembered; later frames are read
against that remembered geometry, so a covered door is a piece standing on a known node rather
than a board that stopped making sense.

⛔ A damaged piece stops being a block. This family redraws a struck piece as a hollow ring
straddling its node — no pixel of it lands inside the node's own block — so a tool that locates
its piece by "which block is drawn like a piece" loses the piece exactly when it is hit. The
position is read as the CENTROID of the body colour instead, which is the node centre for the
whole and for the ring alike.

Frame-only: the pitch, the lattice, the corridors, the exit, the pieces and the meaning of every
control are derived. No identifiers, no titles, no coordinates, no colours, no sizes.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame
from admorphiq.tools.segment import edge_band

__all__ = ["LatticeMazeTool"]


def settled_grid(obs: Any) -> np.ndarray | None:
    """The board AFTER the action finished, which is the LAST layer, not the first.

    ⛔ Measured 2026-08-27, and it cost the first run of this tool every level: one action on
    this board is a slide of several pixels, and the observation carries the WHOLE slide — eight
    layers, one per pixel of travel. The shared reader takes layer 0, which is the piece one
    pixel off its node, so the lattice no longer parses and the tool reported "not my game" on
    its own game after a single move. The last layer is the only one that is on-lattice.
    """
    arr = np.asarray(getattr(obs, "frame", None))
    if arr.ndim == 3:
        arr = arr[-1]
    if arr.ndim != 2:
        return None
    return arr.astype(np.int16)

Cell = tuple[int, int]

# The four board directions, as (drow, dcol) on the node lattice.
_DIRS: tuple[Cell, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))
# The order tried first when nothing has been observed yet. Every entry is replaced by the
# displacement the control is MEASURED to produce; this is a starting guess, not a contract.
_FIRST_GUESS = (1, 2, 3, 4)
# Give the level up after this many proposals without the piece reaching a new node.
_STALL = 8
# How far ahead the patrols are simulated when planning through them.
_HORIZON = 60
# How a piece behaves: unseen to move / walks its facing / defied the model and is only dodged.
_WAITS, _PATROLS, _ERRATIC = 0, 1, 2
# Ceiling on the walk search, so a crowded board cannot stall the whole game budget.
_MAX_STATES = 120000


class _Board:
    """A parsed lattice: where the nodes are, which are joined, and what stands on them."""

    __slots__ = ("side", "y0", "x0", "py", "px", "nodes", "adj", "exit", "pieces", "bg",
                 "geom")

    def __init__(self) -> None:
        self.side = 0
        self.y0 = self.x0 = 0
        self.py = self.px = 0
        self.bg = -1
        self.nodes: dict[Cell, np.ndarray] = {}
        self.adj: dict[Cell, list[Cell]] = {}
        self.exit: Cell | None = None
        # node -> (body colour, mark colour)
        self.pieces: dict[Cell, tuple[int, int]] = {}
        self.geom: Geometry | None = None


def _modal_run(grid: np.ndarray) -> int:
    """The pitch unit: the run length of constant colour that the board is drawn in."""
    runs: Counter = Counter()
    for line in (grid, grid.T):
        for row in line:
            length = 1
            for i in range(1, len(row)):
                if row[i] == row[i - 1]:
                    length += 1
                else:
                    runs[length] += 1
                    length = 1
            runs[length] += 1
    if not runs:
        return 0
    return runs.most_common(1)[0][0]


def _largest_blob(mask: np.ndarray) -> list[Cell]:
    """Cells of the biggest 4-connected drawn region — the board, without the edge furniture."""
    h, w = mask.shape
    seen = np.zeros((h, w), dtype=bool)
    best: list[Cell] = []
    for y in range(h):
        for x in range(w):
            if seen[y, x] or not mask[y, x]:
                continue
            comp = [(y, x)]
            seen[y, x] = True
            q: deque[Cell] = deque([(y, x)])
            while q:
                cy, cx = q.popleft()
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        comp.append((ny, nx))
                        q.append((ny, nx))
            if len(comp) > len(best):
                best = comp
    return best


Geometry = tuple[int, int, int, int, int, int, int, int]


def _geometry(grid: np.ndarray) -> Geometry | None:
    """(background, block side, origin, parity, block counts) of the lattice, or None."""
    h, w = grid.shape
    if h < 8 or w < 8:
        return None
    band = edge_band(grid.shape)
    inner = grid[~band].ravel()
    if inner.size == 0:
        return None
    bg = int(Counter(inner.tolist()).most_common(1)[0][0])
    mask = (grid != bg) & (~band)
    if not mask.any():
        return None
    blob = _largest_blob(mask)
    if len(blob) < 16:
        return None
    ys = [c[0] for c in blob]
    xs = [c[1] for c in blob]
    y0, x0, y1, x1 = min(ys), min(xs), max(ys), max(xs)
    side = _modal_run(grid[y0:y1 + 1, x0:x1 + 1])
    if side < 2 or (y1 - y0 + 1) < 5 * side or (x1 - x0 + 1) < 5 * side:
        return None
    rows = (y1 - y0 + 1) // side
    cols = (x1 - x0 + 1) // side
    drawn = np.zeros((rows, cols), dtype=bool)
    for i in range(rows):
        for j in range(cols):
            blk = grid[y0 + i * side:y0 + (i + 1) * side, x0 + j * side:x0 + (j + 1) * side]
            drawn[i, j] = bool((blk != bg).all())
    best: tuple[int, int] | None = None
    best_key: tuple[int, int] | None = None
    for py in (0, 1):
        for px in (0, 1):
            key = (int(drawn[1 - py::2, 1 - px::2].sum()), -int(drawn[py::2, px::2].sum()))
            if best_key is None or key < best_key:
                best_key, best = key, (py, px)
    if best is None or best_key is None or best_key[0] != 0 or -best_key[1] < 6:
        return None
    return (bg, side, y0, x0, best[0], best[1], rows, cols)


def parse_board(grid: np.ndarray, geom: Geometry | None = None) -> _Board | None:
    """Recover the lattice, or None when the board is not drawn as one."""
    if geom is None:
        geom = _geometry(grid)
    if geom is None:
        return None
    bg, side, y0, x0, py, px, rows, cols = geom
    if y0 + rows * side > grid.shape[0] or x0 + cols * side > grid.shape[1]:
        return None

    def block(i: int, j: int) -> np.ndarray:
        return grid[y0 + i * side:y0 + (i + 1) * side, x0 + j * side:x0 + (j + 1) * side]

    drawn = np.zeros((rows, cols), dtype=bool)
    for i in range(rows):
        for j in range(cols):
            drawn[i, j] = bool((block(i, j) != bg).all())

    board = _Board()
    board.side, board.y0, board.x0, board.py, board.px, board.bg = side, y0, x0, py, px, bg
    for r, i in enumerate(range(py, rows, 2)):
        for c, j in enumerate(range(px, cols, 2)):
            if drawn[i, j]:
                board.nodes[(r, c)] = block(i, j)
    if len(board.nodes) < 6:
        return None
    for (r, c) in board.nodes:
        i, j = py + 2 * r, px + 2 * c
        for dr, dc, li, lj in ((1, 0, i + 1, j), (0, 1, i, j + 1)):
            nb = (r + dr, c + dc)
            if nb in board.nodes and li < rows and lj < cols and drawn[li, lj]:
                board.adj.setdefault((r, c), []).append(nb)
                board.adj.setdefault(nb, []).append((r, c))
    if not board.adj:
        return None

    flat: Counter = Counter()
    shape: dict[Cell, tuple[int, int] | None] = {}
    for cell, blk in board.nodes.items():
        cnt = Counter(blk.ravel().tolist())
        if len(cnt) == 1:
            colour = next(iter(cnt))
            flat[colour] += 1
            shape[cell] = None
        elif len(cnt) == 2 and min(cnt.values()) == 1:
            (mark, _), = [kv for kv in cnt.items() if kv[1] == 1]
            (body, _), = [kv for kv in cnt.items() if kv[1] != 1]
            shape[cell] = (int(body), int(mark))
    if not flat:
        return None
    floor = flat.most_common(1)[0][0]
    marked = [c for c, s in shape.items() if s is None
              and int(board.nodes[c].ravel()[0]) != floor]
    # Zero is normal once play starts — a piece standing on the door hides it — and the caller
    # supplies the door it read on the first frame. More than one is a board of another shape.
    if len(marked) > 1:
        return None
    board.exit = marked[0] if marked else None
    board.pieces = {c: s for c, s in shape.items() if s is not None}
    board.geom = geom
    return board


def facing_of(board: _Board, cell: Cell) -> Cell | None:
    """Which way a piece points, read from where its single odd pixel sits in its block.

    The mark is drawn on the edge midpoint the piece faces, so its offset from the block centre
    IS the direction — no rotation state to guess and nothing to remember.
    """
    blk = board.nodes.get(cell)
    piece = board.pieces.get(cell)
    if blk is None or piece is None:
        return None
    _, mark = piece
    hit = np.argwhere(np.asarray(blk) == mark)
    if hit.shape[0] != 1:
        return None
    mid = (board.side - 1) / 2
    dy, dx = float(hit[0][0]) - mid, float(hit[0][1]) - mid
    if abs(dy) > abs(dx):
        return (1 if dy > 0 else -1, 0)
    if abs(dx) > abs(dy):
        return (0, 1 if dx > 0 else -1)
    return None


def _step_patrol(board: _Board, pos: Cell, face: Cell) -> tuple[Cell, Cell]:
    """One tick of a patrol: advance along the facing, then turn round at a wall."""
    ahead = (pos[0] + face[0], pos[1] + face[1])
    nxt = ahead if ahead in board.adj.get(pos, ()) else pos
    beyond = (nxt[0] + face[0], nxt[1] + face[1])
    if beyond not in board.adj.get(nxt, ()):
        face = (-face[0], -face[1])
    return nxt, face


def _hops(board: _Board, src: Cell, dst: Cell) -> list[Cell] | None:
    """Shortest node path src -> dst, or None when the corridors do not join them."""
    if src == dst:
        return []
    prev: dict[Cell, Cell] = {src: src}
    q: deque[Cell] = deque([src])
    while q:
        u = q.popleft()
        for v in board.adj.get(u, ()):
            if v in prev:
                continue
            prev[v] = u
            if v == dst:
                path = [v]
                while path[-1] != src:
                    path.append(prev[path[-1]])
                return list(reversed(path))[1:]
            q.append(v)
    return None


def rank_pieces(board: _Board) -> list[Cell]:
    """Pieces in order of how likely each is the one the controls steer.

    The board draws the pieces it moves itself as a crowd, so the odd mark colour comes first;
    a board that starts the player next to the door would not be a puzzle, so distance breaks
    the tie. This is a guess and the caller checks it against what actually moves.
    """
    crowd: Counter = Counter(mark for _, mark in board.pieces.values())
    assert board.exit is not None
    out = []
    for cell, (_, mark) in board.pieces.items():
        path = _hops(board, cell, board.exit)
        out.append((crowd[mark], -(len(path) if path is not None else -1), cell))
    out.sort()
    return [c for _, _, c in out]


class LatticeMazeTool:
    """Walk the steered piece to the exit along the corridor graph."""

    name = "lattice_maze"

    def __init__(self) -> None:
        # Control id -> the node displacement it was OBSERVED to produce. Survives a level:
        # the controls are a property of the game, not of the board.
        self._effect: dict[int, Cell] = {}
        self.reset()

    def reset(self) -> None:
        # body colour -> True when that class of piece was SEEN to move, False when it was seen
        # to stay put across a move of ours. Absent = not yet observed, and then both behaviours
        # are guarded against at once.
        self._mobile: dict[int, bool] = {}
        # Classes whose motion defied the model twice — predicted no further, avoided instead.
        self._erratic: set[int] = set()
        self._geom: Geometry | None = None
        # The door, kept as a PIXEL so it survives the lattice origin shifting when a piece at
        # the rim is removed; the cell it names is recomputed against the current geometry.
        self._door_px: tuple[int, int] | None = None
        # [node, facing, body colour] as the board opened, plus the nodes we have stood on —
        # together these replay every other piece exactly.
        self._seed: list[list[Any]] | None = None
        self._hist: list[Cell] = []
        self._me: Cell = (0, 0)
        self._grid: np.ndarray | None = None
        self._body: int | None = None
        self._mark: int | None = None
        self._prev_cell: Cell | None = None
        self._prev_action: int | None = None
        self._stall = 0
        self._blocked: set[tuple[Cell, Cell]] = set()

    # -- reading the board ----------------------------------------------------

    def _read(self, grid: np.ndarray) -> _Board | None:
        """Parse the board against the geometry pinned for this level, and fill in the door.

        ⛔ The geometry is PINNED and not re-derived. It comes from the extent of what is drawn,
        and a piece standing outside the maze's own drawn area moves that extent — measured
        2026-08-27: the origin shifted under the model every few ticks, every carried node
        coordinate went stale with it, and a board that had been cleared stopped being cleared.
        The maze does not move, so its geometry is a fact about the LEVEL, read once.
        """
        board = parse_board(grid, self._geom) if self._geom else None
        if board is None:
            board = parse_board(grid)
            if board is not None:
                self._geom, self._seed, self._door_px = board.geom, None, None
                self._hist, self._mobile, self._erratic = [], {}, set()
        if board is None or board.geom is None:
            return None
        _, side, y0, x0, py, px, _, _ = board.geom
        if board.exit is not None:
            r, c = board.exit
            self._door_px = (y0 + (py + 2 * r) * side, x0 + (px + 2 * c) * side)
        elif self._door_px is not None:
            r = (self._door_px[0] - y0 - py * side) // (2 * side)
            c = (self._door_px[1] - x0 - px * side) // (2 * side)
            if (r, c) in board.nodes:
                board.exit = (r, c)
        return board

    def _locate(self, board: _Board) -> Cell | None:
        """Where the steered piece stands: by POSITION when its colour is shared, colour otherwise.

        Colour alone is an identity for a CLASS, never for one piece, and this board proves it.
        ⛔ Measured 2026-08-27 on the archived re-render of this game: a second piece is drawn in
        the steered piece's own body and mark colours, so the reader fell through to the centroid
        of every pixel of that colour — which averages the two pieces to a point BETWEEN them, and
        on this board that point is not a node at all, so the answer was NOTHING. propose() then
        re-picked the identity from the ranking on every single action, which throws away what the
        level had learned each turn. The board went from 9 levels in 188 actions to 4 in 1288.

        The two copies are the same game — an action tape recorded on one clears the other level
        for level (`scripts/twinboard_probe.py same`) — and the only difference is that the maze
        sprite is drawn at a different z-order in the two renders, so it COVERS that second piece
        on one copy and not on the other. Nothing about the frame stack is involved: the level
        hands back a single layer on both copies and the nine cells that differ are visible in it.
        So a tool cannot rely on a piece being drawn at all, and must not treat "the only thing of
        my colour" as "me".

        What a position is: the piece stood at a known node and a control of known displacement
        was spent, so it is at that node plus the displacement if the move was taken and still at
        that node if it was refused. Both readings are needed — propose() distinguishes a refusal
        from a mis-identification by whether the cell changed. Everything else wearing the colour
        is a different piece.
        """
        if self._body is None:
            return None
        same = [c for c, (body, _) in board.pieces.items() if body == self._body]
        if len(same) == 1:
            return same[0]
        if not same:
            # Nothing of that colour is drawn: the piece may be mid-strike and part-way redrawn,
            # which is what the centroid was for.
            return self._centroid_cell(board, board.side)
        if self._prev_cell is None:
            # First reading of the board, with the colour already shared. The ranking is the only
            # evidence there is, and it is what chose this colour a moment ago.
            for cell in rank_pieces(board):
                if cell in same:
                    return cell
            return same[0]
        eff = self._effect.get(self._prev_action) if self._prev_action is not None else None
        if eff is not None:
            moved = (self._prev_cell[0] + eff[0], self._prev_cell[1] + eff[1])
            if moved in same:
                return moved
            if self._prev_cell in same:
                return self._prev_cell
        return min(same, key=lambda c: abs(c[0] - self._prev_cell[0])
                   + abs(c[1] - self._prev_cell[1]))

    def _centroid_cell(self, board: _Board, side: int) -> Cell | None:
        grid = self._grid
        if grid is None or self._body is None:
            return None
        ys, xs = np.where(grid == self._body)
        if ys.size == 0:
            return None
        cy, cx = float(ys.mean()), float(xs.mean())
        r = round((cy - board.y0 - board.py * side - (side - 1) / 2) / (2 * side))
        c = round((cx - board.x0 - board.px * side - (side - 1) / 2) / (2 * side))
        cell = (int(r), int(c))
        return cell if cell in board.nodes else None

    # -- the control map ------------------------------------------------------

    def _action_for(self, delta: Cell, legal: list[int]) -> int | None:
        for aid, eff in self._effect.items():
            if eff == delta and aid in legal:
                return aid
        used = set(self._effect)
        for aid, guess in zip(_FIRST_GUESS, _DIRS, strict=False):
            if guess == delta and aid not in used and aid in legal:
                return aid
        for aid in legal:
            if aid not in used:
                return aid
        return None

    def _learn(self, board: _Board, cell: Cell) -> None:
        """Believe the displacement the last control produced, over the assumption about it."""
        if self._prev_action is None or self._prev_cell is None:
            return
        delta = (cell[0] - self._prev_cell[0], cell[1] - self._prev_cell[1])
        if delta in _DIRS:
            self._effect[self._prev_action] = delta
        elif delta == (0, 0):
            # Refused. The corridor the plan believed in is not one; drop that edge for good.
            eff = self._effect.get(self._prev_action)
            if eff is None:
                idx = _FIRST_GUESS.index(self._prev_action) if self._prev_action in _FIRST_GUESS \
                    else None
                eff = _DIRS[idx] if idx is not None else None
            if eff is not None:
                self._blocked.add((cell, (cell[0] + eff[0], cell[1] + eff[1])))

    def _adopt_mover(self, board: _Board) -> bool:
        """The piece that answered the control takes the identity from the one that did not.

        ⛔ Only a piece of a class that has NEVER been seen to move on its own may take the
        identity, and only when it is the single such candidate. Everything on this board moves
        every tick, so "something moved the way I asked" is satisfied by a patrol going about its
        route — handing it the identity would leave the walk steering a piece it does not control
        while the real one stands still.
        """
        if self._prev_action is None or self._prev_cell is None:
            return False
        eff = self._effect.get(self._prev_action)
        if eff is None:
            idx = _FIRST_GUESS.index(self._prev_action) if self._prev_action in _FIRST_GUESS \
                else None
            eff = _DIRS[idx] if idx is not None else None
        if eff is None:
            return False
        claim = []
        for cell, (body, mark) in board.pieces.items():
            back = (cell[0] - eff[0], cell[1] - eff[1])
            if body == self._body or self._mobile.get(body) is True \
                    or body in self._erratic:
                continue
            if back in board.nodes and cell != self._prev_cell:
                claim.append((body, mark))
        if len(claim) != 1:
            return False
        self._body, self._mark = claim[0]
        return True

    # -- tool contract --------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        simple_ids, action6 = availability(obs)
        if action6 or len(simple_ids) < 4:
            return 0.0
        grid = settled_grid(obs)
        if grid is None:
            return 0.0
        board = parse_board(grid)
        if board is None or board.exit is None:
            return 0.0
        order = rank_pieces(board)
        if not order:
            return 0.0
        if _hops(board, order[0], board.exit) is None:
            return 0.0
        return 0.85

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        # The board is re-read on every proposal, so nothing is learned from the flag alone.
        return None

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        simple_ids, action6 = availability(obs)
        legal = [a for a in simple_ids if a in _FIRST_GUESS]
        if len(legal) < 4:
            return []
        grid = settled_grid(obs)
        if grid is None:
            return []
        self._grid = grid
        board = self._read(grid)
        if board is None or board.exit is None:
            return []

        if self._body is None:
            order = rank_pieces(board)
            if not order:
                return []
            self._body, self._mark = board.pieces[order[0]]

        cell = self._locate(board)
        if cell is None:
            # The piece we were steering is not on the board any more; take the best on offer.
            order = rank_pieces(board)
            if not order:
                return []
            self._body, self._mark = board.pieces[order[0]]
            cell = order[0]

        if self._prev_cell is not None and cell == self._prev_cell and self._prev_action is not None:
            # Nothing moved where we were looking. Either the control was refused, or we were
            # looking at the wrong piece — the one that DID move takes over.
            if self._adopt_mover(board):
                moved = self._locate(board)
                if moved is not None:
                    cell = moved
            else:
                self._learn(board, cell)
        else:
            self._learn(board, cell)

        self._me = cell
        self._stall = self._stall + 1 if cell == self._prev_cell else 0
        if self._stall > _STALL:
            return []

        path = self._plan(board, cell)
        if not path:
            return []
        delta = (path[0][0] - cell[0], path[0][1] - cell[1])
        aid = self._action_for(delta, legal)
        if aid is None:
            return []
        self._prev_cell, self._prev_action = cell, aid
        return [(aid, None)]

    def _replay(self, board: _Board) -> list[list[Any]]:
        """Every piece's node and facing now, from the opening list and the moves since."""
        pieces = [[p[0], p[1], p[2], True] for p in (self._seed or [])]
        for arrived in self._hist[1:]:
            for piece in pieces:
                if piece[3] and piece[0] == arrived:
                    piece[3] = False
            for piece in pieces:
                if piece[3] and piece[1] is not None and piece[2] not in self._erratic \
                        and self._mobile.get(piece[2]) is True:
                    piece[0], piece[1] = _step_patrol(board, piece[0], piece[1])
        return pieces

    def _sync(self, board: _Board, me: Cell) -> list[list[Any]]:
        """Advance the record, replay the pieces, and reconcile the replay with the picture."""
        watched = {c: v for c, v in board.pieces.items() if c != me}
        if self._seed is None:
            self._seed = [[c, facing_of(board, c), body] for c, (body, _) in watched.items()]
            self._hist = [me]
        elif me != self._hist[-1]:
            self._hist.append(me)
        pieces = self._replay(board)
        here: dict[Cell, list[list[Any]]] = {}
        for piece in pieces:
            if piece[3]:
                here.setdefault(piece[0], []).append(piece)
        for cell, val in watched.items():
            at = here.get(cell)
            if at is not None and len(at) == 1 and at[0][1] is not None:
                turned = facing_of(board, cell)
                if turned is not None and turned != at[0][1]:
                    self._erratic.add(val[0])
        for _ in range(2):
            live = {p[0] for p in pieces if p[3]}
            stray = [c for c in watched if c not in live]
            if not stray:
                return pieces
            # A piece is somewhere the replay did not put one. First reading: its class moves.
            # ⛔ WHEN it started moving says WHICH kind of moving it is. A patrol is in motion
            # from the first tick of the board; a class that stood still for several ticks and
            # then set off was WOKEN, and a woken piece follows the player rather than a route
            # of its own. Measured 2026-08-27: modelled as a patrol, a woken follower was
            # predicted to carry on the way it was pointing, the walk stepped into the node it
            # actually entered, and the board was lost on the ninth action.
            for cell in stray:
                body = watched[cell][0]
                if self._mobile.get(body) is not True and len(self._hist) > 2:
                    self._erratic.add(body)
                self._mobile[body] = True
            pieces = self._replay(board)
        # Still unaccounted for: the board is not the one we opened on (a restart, or a piece
        # that was hidden when we first looked). Keep every piece already modelled — dropping a
        # hidden one is how the model loses a killer — and add what the picture shows on top.
        #
        # ⛔ EXCEPT for a class already known erratic, which is re-read wholesale. Measured
        # 2026-08-27: a follower is unpredictable, so it strays every single tick, so a re-seed
        # that keeps what it modelled leaves a copy of it on every node it has ever stood on.
        # The board filled with eight phantom followers, every route was refused, and the walk
        # was cornered by pieces that did not exist.
        kept = [p for p in pieces if p[3] and p[2] not in self._erratic]
        live = {p[0] for p in kept}
        for cell, val in watched.items():
            if cell not in live and val[0] not in self._erratic:
                self._erratic.add(val[0])
        self._seed = [[p[0], p[1], p[2]] for p in kept]
        self._seed += [[c, facing_of(board, c), v[0]] for c, v in watched.items()
                       if c not in live or v[0] in self._erratic]
        self._hist = [me]
        return self._replay(board)

    def _pieces(self, board: _Board) -> list[tuple[Cell, Cell | None, int]]:
        """(node, facing, behaviour) for every piece still on the board.

        Behaviour is _WAITS until the class is seen to move, which costs nothing: the node a
        waiting piece strikes and the node a patrol steps onto are the same one.
        """
        out = []
        for piece in self._sync(board, self._me):
            if not piece[3]:
                continue
            body = piece[2]
            kind = _ERRATIC if body in self._erratic else (
                _PATROLS if self._mobile.get(body) is True else _WAITS)
            out.append((piece[0], piece[1], kind))
        return out

    def _track(self, board: _Board, pieces: list[tuple[Cell, Cell | None, int]],
               horizon: int) -> list[list[Cell]]:
        """Where each piece stands at each tick, if nothing removes it."""
        tracks = []
        for pos, face, kind in pieces:
            if kind != _PATROLS or face is None:
                tracks.append([pos] * (horizon + 1))
                continue
            walk, p, f = [], pos, face
            for _ in range(horizon + 1):
                walk.append(p)
                p, f = _step_patrol(board, p, f)
            tracks.append(walk)
        return tracks

    def _search(self, board: _Board, start: Cell,
                pieces: list[tuple[Cell, Cell | None, int]],
                tracks: list[list[Cell]], horizon: int, keep_asleep: bool,
                visible: set[Cell]) -> list[Cell] | None:
        """Shortest walk to the door over (node, surviving pieces, tick).

        ``keep_asleep`` additionally refuses the node TWO in front of a waiting piece, which is
        what wakes a follower. ⛔ It is enforced per piece per tick and not as a set of nodes
        computed up front: measured 2026-08-27, a fixed set kept refusing the nodes in front of a
        piece the walk had already removed, so the only route that never woke anything was
        reported impossible and the walk woke a follower it did not have to.
        """
        assert board.exit is not None
        if start == board.exit:
            return []
        full = (1 << len(pieces)) - 1
        root = (start, full, 0)
        prev: dict[tuple[Cell, int, int], tuple[tuple[Cell, int, int], Cell]] = {}
        seen = {root}
        q: deque[tuple[Cell, int, int]] = deque([root])
        expanded = 0
        while q:
            cell, mask, t = q.popleft()
            expanded += 1
            if t >= horizon or expanded > _MAX_STATES:
                continue
            for nxt in board.adj.get(cell, ()):
                alive = mask
                for i in range(len(pieces)):
                    if alive >> i & 1 and tracks[i][t] == nxt and (t or nxt in visible):
                        alive &= ~(1 << i)
                dead = False
                for i, (_, face, kind) in enumerate(pieces):
                    if not alive >> i & 1:
                        continue
                    if kind == _ERRATIC:
                        # Unpredictable: only the tick we can SEE is guarded, and the guard is
                        # the whole ring around it.
                        if t == 0 and nxt in board.adj.get(tracks[i][0], ()):
                            dead = True
                            break
                        continue
                    if kind == _PATROLS:
                        # ⛔ A patrol is guarded by WHERE IT WILL BE, never by where it points.
                        # Measured 2026-08-27: the track carries positions but the facing is
                        # only the one read on THIS frame, so a facing-based guard bans, at
                        # every future tick, the node a patrol faced at tick zero. That is a
                        # phantom wall — it made a solvable board report no route at all, and
                        # the walk fell through to an unguarded path and died.
                        if tracks[i][t + 1] == nxt:
                            dead = True
                            break
                    elif face is not None:
                        here = tracks[i][t]
                        if nxt == (here[0] + face[0], here[1] + face[1]):
                            dead = True
                            break
                        if keep_asleep and nxt == (here[0] + 2 * face[0],
                                                   here[1] + 2 * face[1]):
                            dead = True
                            break
                if dead:
                    continue
                key = (nxt, alive, t + 1)
                if key in seen:
                    continue
                seen.add(key)
                prev[key] = ((cell, mask, t), nxt)
                if nxt == board.exit:
                    path = []
                    cur = key
                    while cur != root:
                        back, step = prev[cur]
                        path.append(step)
                        cur = back
                    return list(reversed(path))
                q.append(key)
        return None

    def _plan(self, board: _Board, cell: Cell) -> list[Cell]:
        assert board.exit is not None
        for a, b in self._blocked:
            if b in board.adj.get(a, ()):
                board.adj[a] = [n for n in board.adj[a] if n != b]
        pieces = self._pieces(board)
        # ⛔ Removing a piece is only ever planned against a piece the picture SHOWS. Measured
        # 2026-08-27: when a class turns out to move, everything the model believed about its
        # members is recomputed, and a member that was hidden at the time can be left standing on
        # a node it never occupied. Charging that phantom walked the player into the node the real
        # one was about to enter. A model good enough to dodge is not good enough to attack.
        visible = {c for c in board.pieces if c != cell}
        horizon = min(_HORIZON, 3 * len(board.nodes) + 6)
        tracks = self._track(board, pieces, horizon + 1)
        for keep_asleep in (True, False):
            path = self._search(board, cell, pieces, tracks, horizon, keep_asleep, visible)
            if path:
                return path
        return self._edge_out(board, cell, pieces, tracks, visible)

    def _edge_out(self, board: _Board, cell: Cell,
                  pieces: list[tuple[Cell, Cell | None, int]],
                  tracks: list[list[Cell]], visible: set[Cell]) -> list[Cell]:
        """No route survives the whole way: take the least bad step that shortens the walk.

        ⛔ Never the shortest path. Measured 2026-08-27: falling back to a route that ignores the
        pieces walked the player straight into one within four actions on a board it had been
        clearing. The order here is what the engine makes true — a step ONTO a piece removes it
        and is the best move available; a step a piece is going to strike is never taken; a step
        merely beside an unpredictable piece is taken only when nothing else is left, and taken
        rather than standing still, because a refused control spends the counter and advances
        nothing at all, so waiting a follower out is not a thing this board allows.
        """
        assert board.exit is not None
        best: tuple[int, int, Cell] | None = None
        for nxt in board.adj.get(cell, ()):
            strike = nxt in visible and any(track[0] == nxt for track in tracks)
            risk, doomed = 0, False
            for i, (_, face, kind) in enumerate(pieces):
                if strike or tracks[i][0] == nxt:
                    continue
                if kind == _ERRATIC:
                    risk = max(risk, int(nxt in board.adj.get(tracks[i][0], ())))
                elif kind == _PATROLS:
                    doomed = doomed or tracks[i][1] == nxt
                elif face is not None:
                    doomed = doomed or nxt == (tracks[i][0][0] + face[0],
                                               tracks[i][0][1] + face[1])
            if doomed:
                continue
            hop = _hops(board, nxt, board.exit)
            rank = (0 if strike else risk + 1,
                    len(hop) if hop is not None else len(board.nodes))
            if best is None or rank < best[:2]:
                best = (rank[0], rank[1], nxt)
        return [best[2]] if best else []
