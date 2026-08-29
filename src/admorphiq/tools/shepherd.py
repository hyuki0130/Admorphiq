"""Shepherd tool — on a haulage board the FIELD does most of the work; clear its way.

The mechanic this tool owns is the deep half of the towing family, and it is a different mechanic
from "walk to the cargo and tow it in", which is what `haul` already does well. On these boards the
field is not passive:

  * some of the things standing on it WALK, and they carry cargo into the bay by themselves —
    they are doing the level FOR the carrier;
  * one or more of them carry cargo to a SECOND destination instead: a region painted in the bay's
    own fill colour with no frame around it. That one is undoing the work, and it can take a piece
    back OUT of a bay, so a board with one in it can be finished and unfinished forever;
  * the carrier can remove that kind, and only that kind: aimed at an actor rather than at a piece,
    the latch deletes it. The board says which is which — face one, and the removable kind is
    redrawn with a ring that turn.

⛔ THE CARRIER'S OWN HAULING IS A NET LOSS ONCE THE MOVERS ARE RUNNING. Measured on the board that
gates this game (thirteen pieces, two movers, two thieves, 150 actions allowed): with both thieves
removed and the carrier STANDING STILL the movers finish the board on their own in 122 actions;
with the thieves alive and the carrier standing still they manage 4 of 13. Adding a carrier that
also hauls took the count DOWN, 12 delivered to 10, under five different rules for choosing which
piece to take (cheapest plan, nearest, farthest, hardest, shortest-plan-only). The carrier is
solid: every cell it walks through is a cell a mover has to route around, and every piece it picks
up is a piece the movers are no longer allowed to touch.

So the plan is, in order: remove the thieves, then help only where a mover will not.

Three measured rules make that work, and each of them cost a wrong version first:

1. ⛔ CAMP, DO NOT CHASE. Both move in the same turn, so a carrier that walks to the cell beside
   where the quarry IS arrives beside where it WAS: measured, pursuit killed the first thief on
   action 92 of 150 and the second on 147, and the two danced from cell to cell in between.
   Standing on one cell, facing one cell and pressing the latch every turn kills it on action 6 —
   the press is judged BEFORE anything else moves, so the turn the quarry steps into the covered
   cell is the turn it is removed, the press costs the same as a step, and unlike a step it leaves
   the carrier pointing the same way.
2. ⛔ A THIEF FARTHER FROM THE CARGO THAN THE CARRIER IS, IS NOT THE PROBLEM. On the last board of
   this game the one thief starts sealed inside a comb of corridors about forty steps from anything
   it can steal; walking in after it spent 42 of the 70 actions that board allows. The test is a
   walk distance, never a straight line — measured, the straight-line distance to that thief is 7
   cells and calls it a threat, while the route to it is forty.
3. ⛔ COMMIT TO A HAUL, AND TAKE THE PIECE THE MOVERS WILL REACH LAST. Re-choosing the cheapest
   plan every action made the carrier switch targets mid-walk and cost about thirty actions per
   delivery; running one chosen plan to its end costs about ten. And the piece to choose is the one
   FARTHEST from every mover, not the nearest to the carrier: the movers work nearest-first, so the
   nearest piece is the one being taken care of, and taking it is what turned 12 delivered into 10.

Measured end to end on the gating board: 4 of 13 delivered standing still, 11 with the incumbent,
12 removing the thieves, and 13 — the level CLEARED, in 116 of 150 actions — with all three rules
together.

⛔ EVERY OTHER BOARD IS HANDED TO THE INCUMBENT WHOLE, not offered a second opinion. Driven by the
plan above, a board with nothing walking on it clears 2 levels of 9 where the incumbent clears 7:
"stand still, the field is delivering" is exactly wrong where nothing is going to deliver, and the
incumbent's hand-off and parking cases are not reproduced here. So this tool runs the incumbent
turn for turn — same instance, same bookkeeping — until it sees the board it is for, and the test
for that board is TWO kinds of thing walking on it AND a second destination drawn on it. The
second destination alone is not enough: two boards in this game have a thief and nothing else that
walks, and taking those over cost 13 and 21 extra actions apiece for nothing. With the gate in, the
first seven levels are cleared in exactly the incumbent's own action counts, to the action.

⛔ THE FINAL BOARD WAS PARKED AT 8 OF 9 AND IS NOT PARKED ANY MORE — what unparked it was not a
better plan, it was noticing that the level had started again. Nine pieces, 70 actions declared,
and on overrun the engine RESTARTS THE LEVEL rather than ending the game, so the harness gets
EIGHT attempts at it inside one run. Measured on the shipped tool:

    attempt 1     8 of 9, banked by action 63, seven actions to spare
    attempts 2-7  7 of 9, and identical to each other action for action
    attempt 8     cut short by the run's own budget

Six of the eight attempts were the same attempt. `levels_completed` is the only thing `propose`
watched and a restart does not move it, so a plan for a board that no longer existed, a flag
saying a piece was in hand, and a walker sweep straddling the reset all rode across it. `_reborn`
below is the fix, and `_start_haul` ranking pieces by the ROUTE to a helper rather than by the
straight line to one is the other half. **Measured, whole-game through the harness, both halves
needed and neither sufficient**: restart-aware alone 8 of 9, route-distance alone 8 of 9, the two
together CLEAR the board — 9 levels, the ninth in 136 actions against a human baseline of 415, and
levels one to eight cost 27/58/77/67/120/46/55/134, unchanged to the action.

⚠️ Read the two as one mechanism. What the route distance buys is a carrier that opens on the
three pieces the sealed helper can never reach; what the restart-aware reset buys is that the
SECOND attempt gets to open at all, instead of resuming the first one's endgame. Under the old
rule the carrier's own hauling was worth four to the board and only three of those were its own —
taking the far pieces leaves the one working helper a nearer one every time.

⚠️ ONE THING THAT LOOKED LIKE THE ANSWER AND IS NOT: varying the retries. Shifting the opening
choice by the attempt number so that the eight tries differ was measured alongside these two and
made the board WORSE — 8,8,6,4,4,4,4 where the pair alone clears. Diversity is not the lever here;
the retries were not failing because they were the same, they were failing because they were the
FIRST attempt's endgame replayed. Learning the allowance from the death and declining a haul too
long to finish was also measured: it fires (ten refusals in a run) and changes nothing, so it is
not in the code.

Beaten by none of: five ranking rules, eight weightings of the mover bias, four drop-cell rules,
five bay-choice rules, five hand-off caps, 300 randomised target orders, and four beam searches
over whole deliveries using EXACT engine state rather than frames — every one of those searched
INSIDE one attempt, which is why none of them found this.

⛔ The final board's NEW elements were checked against what this tool believes them to be, and the
model is right about all three. Its hazard band reads blocked-and-porous, and the engine forbids
the carrier there while letting a towed piece ride over — the same rule. Its two bay shapes read
as bays. Its thief region reads as the second destination. The only thing the reader misses is two
goal cells sealed in a pocket above the hazard, and those are exactly the two of thirteen that no
carrier can deliver into, so the reader's eleven usable bays is the right number for nine pieces.
The second helper is sealed in that same pocket: the carrier cannot reach even a cell beside it,
which is why it moves zero cells in seventy actions — and why a straight line to it was a lie.

⛔ Frame-only, and the pixel reading is NOT re-derived here. Which tile is a piece, which is the
carrier and which way it faces, which rectangle is a bay, what blocks a move and what is porous
enough for cargo to pass through are all read by the reader `haul` already pins, driven here as an
instrument. A second copy of that six-heuristic pile is the exact failure this round has already
paid for once — a loosened copy fired on another game's lattice and cost twenty times what it won —
so this tool contributes a PLAN, not a second grammar.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame, levels_completed
from admorphiq.tools.haul import _DELTA, _LATCH, _MOVES, HaulDeliveryTool, _Board
from admorphiq.tools.segment import background

__all__ = ["ShepherdRelayTool"]

Cell = tuple[int, int]

# A camp is abandoned after this many presses at one cell: the quarry has gone elsewhere and the
# board is paying a step per press. Measured — every kill on the gating board lands inside ten.
_MAX_CAMP = 12
# Total presses spent on thieves in one level. The gating board needs about forty for two of them;
# past that the board is lost anyway and the movers should have the turns.
_MAX_CHASE = 60
# How close the quarry must be before standing still beats walking, in lattice cells.
_CAMP_RANGE = 2


def _spread(board: _Board, sources: list[Cell]) -> dict[Cell, int]:
    """Steps from the nearest source to every cell a walker can stand on.

    Sources are seeded at distance 0 even when they are themselves blocked — a mover stands on the
    cell it occupies, and a walker's own cell is not an obstacle to it.
    """
    seen: dict[Cell, int] = {s: 0 for s in sources}
    queue: deque[Cell] = deque(sources)
    while queue:
        cur = queue.popleft()
        for d in _DELTA.values():
            nxt = (cur[0] + d[0], cur[1] + d[1])
            if nxt in seen or not board.inside(nxt) or nxt in board.blocked:
                continue
            seen[nxt] = seen[cur] + 1
            queue.append(nxt)
    return seen


def _reach(field: dict[Cell, int], cell: Cell) -> int | None:
    """How far it is to STAND BESIDE `cell` — the cell itself holds a piece and cannot be entered."""
    near = [field[(cell[0] - d[0], cell[1] - d[1])] for d in _DELTA.values()
            if (cell[0] - d[0], cell[1] - d[1]) in field]
    return min(near) if near else None


def _span(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class ShepherdRelayTool:
    """Remove what is undoing the work, then let the field finish the board."""

    name = "shepherd"

    def __init__(self) -> None:
        self._eyes = HaulDeliveryTool()   # driven as an instrument: the pixel reader only
        self._hands = HaulDeliveryTool()  # driven whole, on the boards this tool has nothing to add to
        self._own = False
        self._level: int | None = None
        self._plan: list[int] = []
        self._offset: Cell | None = None
        self._promise: Cell | None = None
        self._camp: Cell | None = None
        self._camped = 0
        self._chase = 0
        self._friendly: set[int] = set()     # colours that stayed flat when faced: helpers
        self._removable: set[int] = set()    # colours that grew a ring when faced: thieves
        self._walkers: set[int] = set()      # colours proven to WALK, friend or thief
        self._actors: dict[Cell, int] = {}   # where each of them stands, this frame
        self._flat: dict[int, set[Cell]] = {}
        self._fresh = True
        self._grid: np.ndarray | None = None
        self._blinks = 0
        self._pending: tuple[Cell, Cell | None, int] | None = None
        self._last: tuple[int | None, Cell | None] = (None, None)

    # -- Tool protocol -------------------------------------------------------

    def reset(self) -> None:
        """A new level redraws every piece and every bay, so no plan survives it."""
        self._eyes.reset()
        self._plan = []
        self._offset = None
        self._promise = None
        self._camp = None
        self._camped = 0
        self._chase = 0
        self._blinks = 0
        self._pending = None
        self._actors = {}
        self._flat = {}
        self._fresh = True
        self._own = False
        self._last = (None, None)
        # ⛔ Which colour walks and which of those can be removed belongs to the GAME, not to the
        # level: `_friendly` is not cleared here. Re-learning it costs one press per mover per
        # level, and on a board that declares 70 actions that is the whole margin.

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Nothing to accumulate: the board is re-read every turn and the plan is re-validated."""

    def detect(self, frames: list[Any], obs: Any) -> float:
        """0.8 on a haulage board that has a SECOND destination drawn on it, and on any other
        haulage board exactly what the incumbent bids — because on those boards this tool IS the
        incumbent, turn for turn.

        ⛔ Not on haulage boards in general. The incumbent handles those and handles them well; this
        tool's whole content is what to do about a thief and about movers that are already
        delivering, and on a board with neither it would only be a second opinion with a different
        set of mistakes. The second destination is visible in the level's FIRST frame — a region
        painted in the bay's own fill colour with no frame round it — which matters because nothing
        has walked yet on that frame, so the movers themselves cannot be seen at the moment the
        board is handed out.
        """
        if not has_frame(obs):
            return 0.0
        simple, action6 = availability(obs)
        if action6 or not {1, 2, 3, 4, _LATCH} <= set(simple):
            return 0.0
        grid = frame_2d(obs)
        # ⛔ Read TWICE. The reader learns a bay's frame-and-fill colours from the frame it is
        # looking at, and only recognises the SECOND destination — a region in that fill colour
        # with no frame — on the read after it knows them. Asked once, the level's first frame
        # always says there is no thief here. Re-reading the same frame is free by construction:
        # the reader keys "time has passed" on the frame's bytes, not on being called.
        board = self._eyes._read(grid)
        if board is not None and not board.hostile:
            board = self._eyes._read(grid)
        if board is None or not board.hostile:
            return self._hands.detect(frames, obs)
        # Every piece has to end up in a bay, so a board with fewer bays than pieces is not this
        # mechanic however much of it looks right.
        if not board.cargo or len(board.bays) < len(board.cargo):
            return 0.0
        loose = [c for c in board.cargo if c not in board.bays]
        if not loose:
            return 0.0
        # ⛔ A plan or nothing. Either a thief can be walked up to, or a piece can be taken hold
        # of; a board where neither is true is one this tool would spend the budget standing on.
        walk = self._eyes._walk(board, board.carrier)
        if any((c[0] - d[0], c[1] - d[1]) in walk for c in loose for d in _DELTA.values()):
            return 0.8
        if any((m[0] - d[0], m[1] - d[1]) in walk for m in board.movers for d in _DELTA.values()):
            return 0.8
        return 0.0

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            stepped = self._level is not None
            drove = self._own
            self._level = level
            self.reset()
            # ⛔ The frame that REPORTS a level cleared still draws the level just finished, so
            # reading it learns the OLD board's furniture into the new level. One key press buys
            # the real frame — and only one: the incumbent buys its own when it is driving.
            if stepped and drove:
                return [(_MOVES[0], None)]
        grid = frame_2d(obs)
        board = self._eyes._read(grid)
        if board is not None and not board.hostile:
            board = self._eyes._read(grid)
        if board is not None:
            self._reborn(board)
            self._sight(board, grid)
        if not self._own:
            # ⛔ A board with nothing undoing the work is the incumbent's board, and this tool
            # hands it over WHOLE rather than offering a second opinion with a different set of
            # mistakes. Measured: driven by this tool's own plan, a board with no movers on it
            # clears 2 levels of 9 where the incumbent clears 7 — the deference rule that wins the
            # deep boards ("stand still, the field is delivering") is exactly wrong where nothing
            # is going to deliver, and the incumbent's hand-off and parking cases are not
            # reproduced here.
            # ⛔ A second destination is NOT on its own enough to take a board over. Two boards in
            # this game have a thief on them and nothing else that walks, and there the whole
            # content of this tool — defer to the field, remove what is undoing the work — buys
            # nothing: the incumbent simply delivers both pieces and wins before the thief
            # matters, and taking those boards over cost 13 and 21 extra actions apiece. A field
            # that plays itself has at least TWO kinds of thing walking on it, the kind delivering
            # and the kind undoing, and that is the board this tool is for.
            if board is None or not board.hostile or len(set(self._actors.values())) < 2:
                return self._hands.propose(frames, obs)
            # Taking over mid-level: the incumbent may be holding a piece, and which piece is
            # bookkeeping, not something the frame states.
            self._own = True
            self._offset = self._hands._offset
        if board is None:
            # ⛔ An unreadable frame is not a reason to drop a plan that does not need one. The
            # reader loses the carrier the moment it stands in the OUTERMOST ring of cells: the
            # chrome mask paints over the frame's edge, and on that ring the pixels it paints are
            # the very line that says which way the carrier is facing, so the tile goes uniform
            # and the board is refused. Measured — the carrier walked into a corner on its way to
            # the piece farthest from every mover and the tool gave the rest of the level up
            # three actions later, holding a 17-step plan it could have simply run out.
            if self._plan:
                return [(self._plan.pop(0), None)]
            self._blinks += 1
            return [] if self._blinks > 3 else [(_MOVES[0], None)]
        self._blinks = 0
        self._unsee(board, grid)
        self._judge(board)
        held = self._offset
        action = self._decide(board)
        if action is None:
            return []
        if action == _LATCH:
            self._offset = None if self._offset else self._grip(board)
        elif self._expected(board, held, action):
            self._pending = (board.carrier, held, action)
        return [(action, None)]

    # -- the level starting again -------------------------------------------

    def _reborn(self, board: _Board) -> None:
        """A board whose allowance ran out RESTARTS the level, and nothing positional survives it.

        ⛔ MEASURED, and it is the whole of what this game has left. The last board declares 70
        actions and ENDS THE ATTEMPT on overrun — it does not end the game — so the harness gets
        eight tries at it inside one run. Only `levels_completed` was being watched, and a restart
        does not move it, so the tool carried a plan for a board that no longer existed, a flag
        saying it was holding a piece it had been holding then, and a walker sweep comparing one
        attempt's last frame with the next attempt's first. The result was six identical retries:
        attempt 1 banked 8 of 9 and attempts 2 to 7 banked 7 apiece, action for action the same.

        ⛔ The test is a TELEPORT together with pieces reappearing loose, and both halves are
        needed. The carrier moves at most one cell per action, so a jump is not something play
        produces; a thief takes at most one piece back out of a bay per turn, so two pieces
        reappearing outside the bays in one action is not something the field produces either.
        Neither half alone is safe: the reader loses the carrier on the frame's outermost ring,
        which reads as a jump, and a board with two thieves could return two pieces at once.

        ⚠️ What is cleared is everything that says WHERE something is. What the GAME taught —
        which colour walks, which kind the latch removes, which moves the furniture refuses — is
        as true on the retry as it was on the attempt, and re-learning it costs presses this board
        has no room for.

        ⚠️ NOT DONE HERE, and named so it is not assumed: when the incumbent is driving the board
        this clears THIS tool's bookkeeping and not the incumbent's, so `_hands` carries its own
        plan across a restart. Untested — `shepherd` acts on exactly one of the twenty-five sample
        games and owns that board outright, so the case has never arisen, and reaching into the
        incumbent on the strength of a mechanism nobody has measured is how a true finding becomes
        a regression.
        """
        loose = sum(1 for c in board.cargo if c not in board.bays)
        was_loose, was_carrier = self._last
        self._last = (loose, board.carrier)
        if was_carrier is None or board.carrier is None or was_loose is None:
            return
        if _span(board.carrier, was_carrier) <= 1 or loose - was_loose < 2:
            return
        self._plan = []
        self._offset = None
        self._promise = None
        self._camp = None
        self._camped = 0
        self._chase = 0
        self._pending = None
        self._fresh = True
        self._flat = {}
        self._actors = {}

    # -- learning from a refusal --------------------------------------------

    def _judge(self, board: _Board) -> None:
        """A move the board refused is a fact about the board, and it invalidates the plan.

        Furniture a piece is standing on is invisible from the level's first frame onward, so the
        press that bounced is the only evidence it is there. The refusal is recorded in the reader's
        own ledger, which is what its route finders consult.
        """
        if self._pending is None:
            return
        frm, off, act = self._pending
        self._pending = None
        if board.carrier != frm:
            return
        self._eyes._refused[(frm, off, act)] += 1
        self._plan = []

    def _expected(self, board: _Board, held: Cell | None, action: int) -> bool:
        d = _DELTA[action]
        nxt = (board.carrier[0] + d[0], board.carrier[1] + d[1])
        if not board.inside(nxt):
            return False
        if nxt not in board.blocked:
            return True
        return held is not None and nxt == (board.carrier[0] + held[0], board.carrier[1] + held[1])

    def _unsee(self, board: _Board, grid: np.ndarray) -> None:
        """Take back the porosity of any cell whose own tile has NOTHING to see through.

        ⛔ Porosity is what lets a piece be towed through furniture the carrier cannot follow into,
        and the reader decides it per REGION: furniture is porous when its own colour seals a pocket
        of background. A wall that happens to CLOSE OFF a pocket satisfies that as surely as a
        barrier with holes punched in it. Measured on the final board of this game — where a
        vertical wall touches a hazard band and together they seal a corner — eight of the fifty
        wall cells came back porous, and the planner believed it could hand a piece straight
        through solid wall into a sealed pocket.

        A cell can only be seen through if its OWN tile shows some floor: a solid wall tile is
        sixteen pixels of one colour with nothing behind it, while the hazard tile that IS porous
        here is drawn with the floor showing between its marks. That test keeps all six real ones
        and drops all eight false ones.

        ⚠️ Measured NEUTRAL, on the final board and on every level before it — the plans that
        routed through those cells were not ones the carrier had time to take anyway. Kept because
        it is a wrong belief about a solid object rather than a tuning choice, and the next board
        it meets may not be so forgiving.
        """
        side = board.side
        if not side or not board.porous:
            return
        oy, ox = board.origin
        floor = self._floor(grid)
        bogus = set()
        for (r, c) in board.porous:
            tile = grid[oy + r * side:oy + (r + 1) * side, ox + c * side:ox + (c + 1) * side]
            if not (tile == floor).any():
                bogus.add((r, c))
        board.porous -= bogus
        self._eyes._screens -= bogus

    def _sight(self, board: _Board, grid: np.ndarray) -> None:
        """Which colours WALK, and where every actor of one is standing — bays included.

        ⛔ A thief is at its most dangerous standing ON a bay: that is where it takes a delivered
        piece back out. The reader reports a mover only on frames whose tile happens to read flat
        AND is not a bay cell, so measured, the quarry vanished from the board on exactly the turns
        it was raiding, the threat test then said there was nothing to deal with, and the carrier
        committed to a 28-action haul while a thief emptied the bay behind it. The lattice is the
        reader's; only the sweep is new.

        ⛔ "Walks" is a STEP ACROSS THE FLOOR, and every weaker reading of it was measured wrong
        on this game. "Was covered and is now bare" makes a walker of any wall a piece was standing
        on. "Left one cell and arrived in a neighbouring one" still does, because a piece towed
        along a wall uncovers one wall cell while covering the next. Both readings returned a
        walking set of five colours on a board with two things on it that walk — and with the wall
        and the floor in that set, "the piece farthest from every mover" is a distance to the
        nearest wall, which is the rule this tool's whole plan rests on.

        What a thing that walks does, and furniture never does, is step from floor ONTO floor: the
        cell it arrives in was background a moment ago and the cell it left is background now.
        Furniture only ever appears where a piece USED to stand.
        """
        side = board.side
        oy, ox = board.origin
        floor = self._floor(grid)
        # ⛔ Paint the chrome out before asking what moved. The budget bar pinned to the frame's
        # edge advances one pixel per action, so the tiles it runs through change every turn and
        # the bar's own two colours read as things stepping across the floor.
        grid = grid.copy()
        grid[0, :] = grid[-1, :] = grid[:, 0] = grid[:, -1] = floor
        self._grid = grid
        if side <= 0:
            return
        if self._fresh:
            # ⛔ Throw the first sweep of a level away. The frame that REPORTS a level cleared
            # still draws the level just FINISHED, so the sweep after it compares one board's
            # picture with another's and every colour in both looks like it stepped. Measured:
            # that single comparison put the wall colour into the walking set on the first action
            # of the deepest board, and "the piece farthest from every mover" then means the piece
            # farthest from the nearest wall.
            self._fresh = False
            self._flat = {}
            self._actors = {}
            return
        flat: dict[int, set[Cell]] = {}
        for r in range(board.rows):
            for c in range(board.cols):
                tile = grid[oy + r * side:oy + (r + 1) * side, ox + c * side:ox + (c + 1) * side]
                shades = set(tile.ravel().tolist())
                if len(shades) == 1:
                    flat.setdefault(int(next(iter(shades))), set()).add((r, c))
        was_bg = self._flat.get(floor, set())
        now_bg = flat.get(floor, set())
        for colour, cells in flat.items():
            was = self._flat.get(colour)
            if not was or colour in self._walkers:
                continue
            onto = (cells - was) & was_bg
            off = (was - cells) & now_bg
            if any(_span(a, b) == 1 for a in onto for b in off):
                self._walkers.add(colour)
        self._flat = flat
        self._actors = {c: v for v, cells in flat.items() if v in self._walkers for c in cells}

    def _floor(self, grid: np.ndarray) -> int:
        """The colour a walker steps across — the shared grammar's answer, not a local one."""
        return next(iter(background(grid.tolist())))

    def _core(self, board: _Board, cell: Cell) -> int:
        """The colour inside a tile's ring — what the actor is, with the ring stripped off."""
        side = board.side
        oy, ox = board.origin
        y = oy + cell[0] * side + side // 2
        x = ox + cell[1] * side + side // 2
        return int(self._grid[y, x]) if self._grid is not None else -1

    def _grip(self, board: _Board) -> Cell | None:
        if board.carrier is None or board.facing is None:
            return None
        d = _DELTA[board.facing]
        ahead = (board.carrier[0] + d[0], board.carrier[1] + d[1])
        return d if ahead in board.cargo else None

    # -- deciding ------------------------------------------------------------

    def _decide(self, board: _Board) -> int | None:
        carrier = board.carrier
        if carrier is None or board.facing is None:
            return None
        # The latch is bookkeeping this tool owns; the frame confirms it by where the piece sits.
        if self._offset is not None:
            ride = (carrier[0] + self._offset[0], carrier[1] + self._offset[1])
            if ride not in board.cargo:
                self._offset = None
                self._plan = []
                self._promise = None
        if self._offset is not None:
            return self._deliver(board, carrier, self._offset)
        act = self._police(board, carrier)
        if act is not None:
            return act
        if self._plan:
            return self._plan.pop(0)
        return self._start_haul(board, carrier)

    # -- removing what is undoing the work -----------------------------------

    def _police(self, board: _Board, carrier: Cell) -> int | None:
        """Deal with a thief, or decide that this one is not worth the walk.

        ⛔ The order matters and is not a preference. On the gating board the thieves take pieces
        back out of the bays, so every action spent hauling while one is alive is an action the
        board can undo; measured, the same carrier delivers 4 of 13 with them alive and 13 with
        them gone.
        """
        if self._chase > _MAX_CHASE:
            return None
        ahead = None
        if board.facing is not None:
            d = _DELTA[board.facing]
            ahead = (carrier[0] + d[0], carrier[1] + d[1])
            # The ring is the licence to press: this board redraws a removable actor with one the
            # moment it is looked at.
            if ahead in board.marked:
                # ⛔ Read the colour out of the tile's CORE, not out of the actor sweep. Being
                # faced is exactly what puts a ring round it, so the frame that proves an actor
                # removable is the one frame on which its tile is no longer flat and the sweep
                # cannot see it at all — and the colour never got recorded, so the carrier walked
                # up to a helper on the far side of the board to ask a question it had answered.
                self._removable.add(self._core(board, ahead))
                self._chase += 1
                return _LATCH
            if ahead in self._actors:
                # Faced and still flat: this kind cannot be removed, and chasing it again would
                # cost the rest of the budget. Written off by colour, for the whole game.
                self._friendly.add(self._actors[ahead])
                self._camp = None
                self._camped = 0
        prey = [c for c, kind in self._actors.items() if kind not in self._friendly]
        # ⛔ A colour that has already answered the latch never needs asking again, and a colour
        # that has never been asked is not worth walking across the board to ask while a known
        # thief is loose. Measured: without this the carrier spent sixteen of the gating board's
        # 150 actions walking up to a helper it had already watched deliver, to face it once.
        known = [c for c in prey if self._actors[c] in self._removable]
        if known:
            prey = known
        if not prey:
            self._camp = None
            return None
        # ⛔ Judge the threat by the ROUTE, not by the picture. A thief that is seven cells away
        # across a wall and forty steps away around it is not about to take anything.
        field = _spread(board, prey)
        walk = self._eyes._walk(board, carrier)
        mine = {c: len(p) for c, p in walk.items()}
        pressing = False
        for piece in board.cargo:
            theirs = _reach(field, piece)
            if theirs is None:
                continue
            ours = _reach(mine, piece)
            if ours is None or theirs <= ours:
                pressing = True
                break
        if not pressing:
            self._camp = None
            return None
        near = min(prey, key=lambda c: _span(c, carrier))
        if _span(near, carrier) <= _CAMP_RANGE and self._camped < _MAX_CAMP:
            # ⛔ Stand still and cover a cell. Walking to where it IS arrives where it WAS.
            self._plan = []
            self._camped += 1
            self._chase += 1
            act = min(_MOVES, key=lambda a: _span((carrier[0] + _DELTA[a][0],
                                                   carrier[1] + _DELTA[a][1]), near))
            if board.facing != act:
                return act
            self._camp = (carrier[0] + _DELTA[act][0], carrier[1] + _DELTA[act][1])
            return _LATCH
        self._camped = 0
        best: tuple[int, int, Cell] | None = None
        for cell in prey:
            for act in _MOVES:
                d = _DELTA[act]
                stance = (cell[0] - d[0], cell[1] - d[1])
                if stance not in walk:
                    continue
                cost = len(walk[stance])
                if best is None or cost < best[0]:
                    best = (cost, act, stance)
        if best is None:
            return None
        self._plan = []
        _, act, stance = best
        if stance != carrier:
            return walk[stance][0]
        self._chase += 1
        return act if board.facing != act else _LATCH

    # -- hauling -------------------------------------------------------------

    def _open_bays(self, board: _Board, held: Cell | None) -> set[Cell]:
        return {b for b in board.bays if b not in board.cargo or b == held}

    def _deliver(self, board: _Board, carrier: Cell, offset: Cell) -> int | None:
        """Carry on with the delivery in hand, re-routing only when the queued plan is spent."""
        ride = (carrier[0] + offset[0], carrier[1] + offset[1])
        bays = self._open_bays(board, ride)
        if ride in bays:
            self._plan = []
            self._promise = None
            return _LATCH
        if self._plan:
            return self._plan.pop(0)
        paths = self._eyes._tow(board, carrier, offset)
        aim = [(len(p), q) for q, p in paths.items()
               if (q[0] + offset[0], q[1] + offset[1]) in bays]
        if not aim:
            # Walled off from every bay while holding a piece: put it down rather than tow it
            # around the board, and let the plan be rebuilt from where it lands.
            self._promise = None
            return _LATCH
        self._plan = list(paths[min(aim)[1]])
        return self._plan.pop(0) if self._plan else _LATCH

    def _start_haul(self, board: _Board, carrier: Cell) -> int | None:
        """Choose the piece the movers will reach LAST and commit to the whole plan for it."""
        bays = self._open_bays(board, None)
        loose = [c for c in board.cargo if c not in board.bays]
        if not loose or not bays:
            return self._hold(board, carrier)
        walk = self._eyes._walk(board, carrier)
        # ⛔ The sweep's answer ALONE. This union'd in the reader's own mover map as well, which
        # is the noisy test — "a cell that was covered and is now bare" — that the sweep exists to
        # replace, and unioning a clean set with the dirty one it replaces just restores the dirt.
        # Counted on the final board: 49 cells reported as movers, of which 2 were movers and 47
        # were the wall of a comb of corridors. "The piece farthest from every mover" then means
        # the piece farthest from the nearest wall, which is the rule this whole plan rests on.
        # ⚠️ The sweep is also the STABLE answer, which the rule needs: the reader reports a mover
        # only on frames whose tile happens to read flat and off a bay, so on the frames it reports
        # none the distance is zero for every piece and the choice collapses to the cheapest plan —
        # which is the rule measured to take the gating board from 12 delivered to 10.
        # ⛔ Attendants, not actors. A thief does not deliver anything — a piece standing next to
        # one is in danger, not in hand — so counting it here says "leave that piece alone" about
        # the one piece most likely to be stolen. Colours that answered the latch are known.
        movers = sorted(c for c, kind in self._actors.items() if kind not in self._removable)
        # ⛔ BY THE ROUTE, NOT BY THE PICTURE — the rule `_police` already states for a thief and
        # this function did not state for a mover. On the last board of this game one of the two
        # helpers is sealed above a hazard band and moves ZERO cells in seventy actions, and a
        # straight line puts it four cells from a piece it can never reach: all three pieces on
        # that side of the board then rank as already-taken-care-of and the carrier walks away
        # from the only pieces no helper will ever collect. A helper that cannot walk to a piece
        # is not delivering it. With no movers seen the field is empty and every piece is adrift,
        # which ties exactly as the straight line's zero did — so a board with nothing walking on
        # it is unchanged.
        field = _spread(board, movers)
        adrift = board.rows + board.cols
        best: tuple[int, int, list[int]] | None = None
        for piece in loose:
            # ⛔ Distance to the nearest MOVER, not to the carrier. The movers work nearest-first,
            # so the piece nearest one of them is the piece being taken care of already.
            walked = _reach(field, piece)
            alone = adrift if walked is None else walked
            for act in _MOVES:
                d = _DELTA[act]
                stance = (piece[0] - d[0], piece[1] - d[1])
                if stance == carrier:
                    approach: list[int] = []
                elif stance in walk:
                    approach = list(walk[stance])
                else:
                    continue
                tow = self._eyes._tow(board, stance, d)
                drop = sorted((len(p), q) for q, p in tow.items()
                              if (q[0] + d[0], q[1] + d[1]) in bays)
                if not drop:
                    continue
                turn = [] if (not approach and board.facing == act) else [act]
                plan = approach + turn + [_LATCH] + list(tow[drop[0][1]]) + [_LATCH]
                if best is None or (-alone, len(plan)) < (-best[0], len(best[2])):
                    best = (alone, len(plan), plan)
        if best is None:
            return self._hold(board, carrier)
        self._plan = list(best[2])
        return self._plan.pop(0)

    @staticmethod
    def _hold(board: _Board, carrier: Cell) -> int:
        """Stand still while the field works: a key press that cannot walk the carrier anywhere.

        ⛔ This is a PLAN, not a shrug. Standing still is what lets the movers finish the board:
        measured, a carrier that wanders instead costs them up to 28 of the 150 actions the gating
        board allows, and one that hauls costs them two whole pieces.
        """
        for act in _MOVES:
            d = _DELTA[act]
            nxt = (carrier[0] + d[0], carrier[1] + d[1])
            if not board.inside(nxt) or nxt in board.blocked:
                return act
        return _MOVES[0]
