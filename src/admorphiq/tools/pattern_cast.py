"""Reproduce a pattern the board is SHOWING you, then walk the avatar to its exit.

The mechanic, recovered frame-only: a compact panel carries a complete k x k lattice of
equal square cells. Most sit at one neutral colour; a minority are painted in a second.
That minority is not decoration — it is an INSTRUCTION. Clicking each painted cell arms
it, and when the armed set equals the painted set the board RESOLVES the pattern. What a
resolution does is the board's own vocabulary and has to be learned: some change the
avatar — it shrinks, it grows, it is carried across the board — and some are ranged, a
projectile that leaves the side the avatar faces and clears a switch standing where no
step can reach.

So the tool runs an agenda, not a habit. Walk to the exit if a route exists. If none
does, look for the mark a projectile is FOR — a piece bordering the ground we stand on
that no placement can touch — and go stand where the whole leading face looks at it. If
there is no such mark and no route, the board is asking for the avatar itself to change.
Only then is a pattern entered, and only a pattern whose effect matches what is being
asked for; effects are remembered by pattern, so what one level pays to learn the rest
get for nothing.

Deeper levels stop displaying the instruction at all. Their patterns live in FURNITURE —
framed plates standing off the walkable area, one per pattern the level allows. Asking a
plate costs a turn and nothing else, so the tool asks for the pattern it needs rather
than entering whatever happens to be lit.

Two things make this a plan rather than a search. The instruction is fully visible once
asked for, so no combination is ever tried: a cast costs exactly the number of painted
cells. And the panel that shows the pattern also METERS the level — every cell entered
and every step taken is charged against a per-level allowance, and running it out ends
the game — so exploring is not merely slow here, it loses. Every guard in this file that
looks like timidity is a measured loss: the same pattern entered twice from one stance,
a mark shot at that never reacts, a turn taken twice on one square.

Selectivity comes from the instruction itself. ``detect`` scores 0 unless a complete
lattice is present AND cells are painted on it: a quiet lattice means this tool has
nothing to enter and no business taking the turn.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, frame_2d, has_frame, levels_completed
from admorphiq.tools.segment import background, components, edge_band, uniform_blocks

__all__ = ["PatternCastTool"]

# Below 3x3 is not a pattern; above 5x5 is a board, not an instruction panel.
_MIN_K = 3
_MAX_K = 5
# Cell sizes worth testing, largest first: every smaller square inside a flat cell is also
# "uniform", so the biggest lattice that closes is the real one.
_SIDES = (5, 4, 3, 2)
# A click can be swallowed by an animation. Re-enter the same cell, but not forever.
_MAX_REENTRY = 3
# A path longer than this is not a plan, it is a wander — and the allowance forbids it.
_MAX_PATH = 64
# Resolutions per level. A board that genuinely wants two patterns, plus the price of
# finding out which is which, and no more: a board we have MISREAD must not be able to
# drain the allowance and lose a level already won.
_MAX_CASTS = 8
# Plate enquiries per level. Free of the allowance, so this only bounds a spin.
_MAX_ASKS = 24
# Frames a resolution is given to show itself before it is called a miss.
_SETTLE = 4

Cell = tuple[int, int]
Box = tuple[int, int, int, int]


class PatternCastTool:
    """Enter the displayed pattern, then navigate the avatar into its exit."""

    name = "pattern_cast"

    def __init__(self) -> None:
        self._level = -1
        self._engaged = False
        # What each pattern DOES, keyed by the pattern itself. A board's vocabulary is the
        # board's, not the level's: the same arrangement resolves the same way on every
        # level, so what one level pays to learn the next levels get for nothing.
        self._effects: dict[frozenset[Cell], str] = {}
        self.reset()

    # --- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        """Drop everything learned about one level's board and lattice."""
        self._entered: dict[Cell, int] = {}
        self._awaiting: tuple[Cell, int] | None = None
        self._reentry = 0
        self._avatar_palette: frozenset[int] | None = None
        self._avatar_box: Box | None = None
        self._goal: set[Cell] | None = None
        self._floor: int | None = None
        self._stride: int | None = None
        self._prev: np.ndarray | None = None
        self._prev_step: Step | None = None
        self._blocked: set[int] = set()
        self._faced = False
        self._heading: int | None = None
        self._aim: tuple[Cell, int] | None = None
        self._rearms = 0
        self._reads = 0
        self._casts = 0
        self._seen: set[Box] = set()
        self._suspect = False
        self._target: set[Cell] | None = None
        self._need: str | None = None
        self._pending: (
            tuple[frozenset[Cell], Box | None, tuple[frozenset[int], frozenset[Cell]] | None, int]
            | None
        ) = None
        self._shelf: list[Box] = []
        self._plates: dict[Box, frozenset[Cell]] = {}
        self._asked: tuple[Box, frozenset[Cell]] | None = None
        self._lit: frozenset[Cell] = frozenset()
        self._asked_since: set[Box] = set()
        self._duds: set[Cell] = set()
        self._turned: set[Box] = set()
        self._spent: set[tuple[Any, ...]] = set()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Learning happens in ``propose``, which sees both sides of a transition."""

    # --- detection ---------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence that a pattern is on display for us to reproduce."""
        if not has_frame(obs):
            return 0.0
        simple, click_ok = availability(obs)
        if not click_ok or len(simple) < 4:
            return 0.0
        pad = _find_pad(frame_2d(obs))
        if pad is None or not _painted(pad[2]):
            return 0.0
        return 0.9

    # --- planning ----------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """One action at a time: the board is deliberately re-read every turn.

        A level-up leaves the finished board on screen for one more frame, and a cast
        rewrites the avatar mid-plan, so any queued sequence is planning against a
        position that no longer exists.
        """
        if not has_frame(obs):
            return []
        simple, click_ok = availability(obs)
        if not click_ok:
            return []
        grid = frame_2d(obs)
        level = levels_completed(obs)
        if level != self._level:
            fresh = self._level >= 0
            self._level = level
            self.reset()
            self._suspect = fresh

        pad = _find_pad(grid)
        if pad is None:
            return []
        origins, side, colours = pad
        self._engaged = self._engaged or bool(_painted(colours))
        if not self._engaged:
            # A lattice that has never shown a pattern is somebody else's furniture. Other
            # boards carry regular grids of flat squares for their own reasons, and acting
            # on one — even inertly — is taking a turn this tool has no plan for.
            return []
        panel = _panel_box(grid, origins)

        self._confirm_entry(colours)
        self._learn(grid, panel)
        self._classify(grid, panel)
        self._lit = frozenset(_painted(colours))
        if self._asked is not None and self._lit and self._lit != self._asked[1]:
            # The plate we last asked ANSWERED — the lattice is showing something it was
            # not showing before. Recorded so the plate can be preferred, or avoided,
            # without paying for its pattern a second time. A plate that changed nothing
            # is not credited with whatever happens to be lit.
            self._plates[self._asked[0]] = self._lit
            self._asked = None

        # Walk BEFORE entering anything. A resolved pattern can be directional — it acts
        # the way the avatar faces — so entering it from wherever we happen to stand spends
        # the allowance on a shot into a wall. Walking first closes the distance and, when
        # the walk runs out, leaves the avatar standing where a shot has something to hit.
        step = self._navigate(grid, panel, simple)
        # A cleared level leaves the FINISHED board on screen for one more frame, with the
        # avatar already merged into its exit. Walking such a frame is harmless — the plan
        # is simply refused — but ENTERING it is not: a click aimed at the old pattern lands
        # on the NEW lattice and arms a cell that pattern does not want, which no later click
        # undoes without paying for the pattern twice. Reading the avatar and its exit off
        # the frame is the proof that the frame describes this board; until then, no clicks.
        if step is None and not self._suspect:
            step = self._face_then_enter(origins, side, colours)
        if step is None:
            step = self._read_again(grid)
        if step is None:
            step = self._rearm(grid, panel)
        if step is None:
            return []
        self._prev = grid
        self._prev_step = step
        return [step]

    # --- phase 1: reproduce the displayed pattern --------------------------

    def _confirm_entry(self, colours: list[list[int]]) -> None:
        """A cell counts as entered only once its colour has actually moved.

        Believing the click instead of the frame is what breaks on a swallowed action:
        the pattern then stays one cell short forever and never resolves.
        """
        if self._awaiting is None:
            return
        (r, c), before = self._awaiting
        now = colours[r][c]
        if now != before:
            self._entered[(r, c)] = before
            self._awaiting = None
            self._reentry = 0
        else:
            self._reentry += 1
            if self._reentry > _MAX_REENTRY:
                self._awaiting = None
                self._reentry = 0

    def _face_then_enter(
        self, origins: list[list[Cell]], side: int, colours: list[list[int]]
    ) -> Step | None:
        """Turn to the refusing direction once, then enter the pattern.

        A refused step still turns the avatar, which costs one unit of the allowance and
        is the only way to aim a directional resolution. Done once per standstill.
        """
        facing = self._prev_step[0] if self._prev_step else None
        if not self._faced and self._heading is not None:
            # A REFUSED step turns on the spot; a legal one walks. So turning toward a mark
            # that lies beside us carries us past it, to a square from which the same mark
            # is lined up from the OTHER side — and two such squares hand the avatar back
            # and forth until the allowance is gone. Measured. One turn per square is the
            # bound: on the second visit we shoot from where we already face.
            first = self._avatar_box not in self._turned
            self._turned.add(self._avatar_box)
            self._faced = True
            if first and self._heading != facing:
                return (self._heading, None)
        return self._enter_pattern(origins, side, colours)

    def _rearm(self, grid: np.ndarray, panel: Box) -> Step | None:
        """The lattice is not showing the pattern we want — ask the shelf for another.

        Boards of this family park their instructions in FURNITURE: framed boxes that
        stand off the walkable area entirely, one per pattern the level allows. Clicking
        one puts its pattern back on the lattice, and costs nothing but the turn. Furniture
        is identified by exactly that property — a piece the avatar could never walk up to,
        because the ground inside its frame is not joined to the ground it stands on.

        Which one is asked for is not a rotation: once a pattern's effect has been paid for
        it is remembered, so a plate whose pattern does the thing we currently need is
        preferred, an unpaid-for plate comes next, and a plate we KNOW does the wrong thing
        is only touched when there is nothing else.
        """
        if self._avatar_box is None or self._floor is None or self._need is None:
            return None
        self._shelf = self._shelf or self._furniture(grid, panel)
        # Asking a plate is free of the allowance — only casting is charged — so the bound
        # here is not a price, it is a spin guard: every plate gets one ask per board
        # change, and a board that changes no more offers nothing more to ask for.
        left = [p for p in self._shelf if p not in self._asked_since]
        if not left or self._rearms >= _MAX_ASKS:
            return None
        pick = min(left, key=lambda p: (self._rank(p), self._shelf.index(p)))
        self._asked_since.add(pick)
        if self._plates.get(pick) == self._lit:
            # Its pattern is already the one on the lattice; asking again shows the same
            # thing and spends a turn to do it.
            return None
        y0, x0, y1, x1 = pick
        self._asked = (pick, self._lit)
        self._rearms += 1
        self._seen.clear()
        return (6, ((x0 + x1) // 2, (y0 + y1) // 2))

    def _stance(self, pattern: frozenset[Cell]) -> tuple[Any, ...]:
        """Everything about our position that a resolution's outcome depends on.

        Where we stand and how big we are, and — when the resolution is a directional one —
        which way we face. Leaving the facing out looks harmless and is not: a board that
        wants two switches shot from the same corner refuses the second shot, because the
        first has already spent that place.
        """
        facing = self._heading if self._need == "fire" else None
        return (pattern, self._avatar_box, facing)

    def _rank(self, plate: Box) -> int:
        """0 = offers what we need, 1 = unknown, 2 = wrong effect, 3 = already spent here."""
        pattern = self._plates.get(plate)
        if pattern is None:
            return 1
        if self._stance(pattern) in self._spent:
            return 3
        effect = self._effects.get(pattern)
        if effect is None:
            return 1
        return 0 if effect == self._need else 2

    def _furniture(self, grid: np.ndarray, panel: Box) -> list[Box]:
        """The plates on the shelf, largest first, one entry per plate.

        A framed plate is several pieces to a component reader — the frame, and each blob
        of the pattern painted inside it — so entries wholly inside an entry already taken
        are dropped. Without that the tool asks the same plate for a pattern three times
        over, once per blob, and reads the refusals as three different plates.
        """
        assert self._avatar_box is not None and self._floor is not None
        board = _board_only(grid, panel)
        ground = _ground(board, self._avatar_box, self._floor)
        off = [
            o for o in self._objects(grid, board)
            if not (_halo(o["cells"]) & ground)
            and o["cells"].isdisjoint(self._goal or set())
            # Big enough to DRAW the pattern it offers. Boards leave single stray cells
            # standing off the walkable area for their own reasons, and a plate list that
            # admits them spends one turn each asking a speck for an instruction.
            and o["box"][2] - o["box"][0] >= _MIN_K
            and o["box"][3] - o["box"][1] >= _MIN_K
        ]
        off.sort(key=lambda o: (-o["size"], o["box"]))
        plates: list[Box] = []
        for o in off:
            box = o["box"]
            if any(_inside(box, kept) for kept in plates):
                continue
            plates.append(box)
        return plates

    def _read_again(self, grid: np.ndarray) -> Step | None:
        """Nothing is readable — spend one inert click to get a fresh frame.

        A cleared level leaves the FINISHED board on screen for one more frame, with the
        avatar already merged into its exit and nothing left to pair. Clicking bare wall is
        the least committal way to ask again: it touches no piece and no cell of the
        lattice. Once per level, so a genuinely dead board cannot loop.
        """
        if self._reads >= 2:
            return None
        wall = background(grid)
        for y, x in ((0, 0), (grid.shape[0] - 1, 0)):
            if int(grid[y][x]) in wall:
                self._reads += 1
                return (6, (x, y))
        return None

    def _enter_pattern(
        self, origins: list[list[Cell]], side: int, colours: list[list[int]]
    ) -> Step | None:
        """Click one painted cell, or nothing when the pattern is fully entered.

        "Entered" is held against the colour the cell HAD, so a cell toggled back off by a
        stray click returns to the pending list on its own, while the wholesale recolour a
        resolution paints over the lattice does not read as fresh work.
        """
        painted = frozenset(_painted(colours))
        pending = [
            cell for cell in sorted(painted)
            if cell not in self._entered
            or self._entered[cell] == colours[cell[0]][cell[1]]
        ]
        if not pending:
            # Everything we entered has taken: the pattern has resolved. Some boards clear
            # the lattice at that point and some leave it lit, so completion is read from
            # our own entries, never from the lattice going quiet.
            if self._entered:
                self._entered.clear()
                self._seen.clear()
                self._casts += 1
            return None
        # Only ever entered against a REASON — a mark lined up in front of us, or a board
        # that has refused every route and wants the avatar itself changed. A pattern
        # entered because it happened to be lit is how a level already won gets spent.
        if self._need is None or self._casts >= _MAX_CASTS or self._pending is not None:
            return None
        # A pattern already paid for once, whose effect is not the effect we need, is worth
        # a turn asking the shelf for a different one — never four charges of the allowance
        # to watch it do the wrong thing twice.
        if self._effects.get(painted, self._need) != self._need:
            return None
        # The board is deterministic: the same pattern, entered from the same place at the
        # same size, does the same thing. Measured on a board with three plates — a size
        # pattern entered twice shrank the avatar and grew it straight back, and would have
        # gone on alternating until the allowance ran out.
        if self._stance(painted) in self._spent:
            return None
        if self._awaiting is not None and self._reentry > _MAX_REENTRY:
            return None
        if len(pending) == 1:
            # The last cell of the pattern: whatever the board does next is this pattern's
            # doing, and this is the only moment at which the before-picture is still true.
            mark = None
            if self._target and self._prev is not None:
                mark = (
                    frozenset(int(self._prev[y][x]) for y, x in self._target),
                    frozenset(self._target),
                )
            self._pending = (painted, self._avatar_box, mark, _SETTLE)
            self._spent.add(self._stance(painted))
            self._asked_since.clear()
        r, c = self._awaiting[0] if self._awaiting is not None else pending[0]
        self._awaiting = ((r, c), colours[r][c])
        y, x = origins[r][c]
        return (6, (x + side // 2, y + side // 2))

    def _classify(self, grid: np.ndarray, panel: Box) -> None:
        """Name what the pattern we last entered actually DID.

        Two outcomes are distinguishable from the frame alone. The mark we were aiming at
        is gone: the pattern is a ranged one. The avatar is a different shape, or standing
        somewhere no step of ours could have put it: the pattern changes the avatar, which
        is what "no route exists" asks for. Neither, once the board has settled: a ranged
        resolution that missed — which is the same news for our purposes, since what it is
        NOT is the pattern that changes geometry.

        Settling is the whole difficulty. A resolution is announced on the frame that
        completes the pattern and APPLIED several frames later, so a verdict read off the
        next frame alone calls every pattern inert — measured: all three of one board's
        patterns came back "missed", and the tool then refused to enter any of them.
        """
        if self._pending is None:
            return
        pattern, before, mark, ttl = self._pending
        if mark and not (mark[0] & {int(grid[y][x]) for y, x in mark[1]}):
            self._pending = None
            self._effects[pattern] = "fire"
            return
        after = self._avatar(_board_only(grid, panel))
        if after is not None and before is not None:
            resized = (
                after[2] - after[0] != before[2] - before[0]
                or after[3] - after[1] != before[3] - before[1]
            )
            jumped = max(abs(after[0] - before[0]), abs(after[1] - before[1])) > 2 * (
                self._stride or 1
            )
            if resized or jumped:
                self._pending = None
                self._effects[pattern] = "geom"
                self._avatar_box = after
                return
        if ttl <= 0:
            self._pending = None
            self._effects[pattern] = "fire"
            if mark:
                # We stood where the whole face looked at this piece, resolved a pattern,
                # and the piece did not react. It is scenery, not the switch — and left in
                # the running it is shot again from the next stance, and the next.
                self._duds |= mark[1]
                self._target = None
            return
        self._pending = (pattern, before, mark, ttl - 1)

    # --- what the last transition taught -----------------------------------

    def _learn(self, grid: np.ndarray, panel: Box) -> None:
        """Read the effect of our own last action off the two frames."""
        prev, last = self._prev, self._prev_step
        if prev is None or last is None or last[0] == 6 or self._avatar_box is None:
            return
        box = self._track(grid, panel)
        if box is None:
            return
        if box == self._avatar_box:
            self._blocked.add(last[0])
            return
        self._blocked.clear()
        self._faced = False
        # Cells the avatar left behind are, by definition, walkable ground — but not
        # necessarily THE ground. Boards paint markers on the floor, and an avatar that
        # steps off one hands back the marker's colour as the new floor: measured, a board
        # whose ground is colour 2 came back as colour 15 every second step, and the
        # reachability map flipped with it, bouncing the avatar between two cells until the
        # allowance ran out. So a fresh reading has to be at least as WIDESPREAD as the one
        # it replaces to take its place.
        vacated = _box_cells(self._avatar_box) - _box_cells(box)
        floors = Counter(int(grid[y][x]) for y, x in vacated)
        if floors:
            candidate = floors.most_common(1)[0][0]
            spread = Counter(v for row in _board_only(grid, panel) for v in row)
            if self._floor is None or spread[candidate] >= spread[self._floor]:
                self._floor = candidate
        # Only a STEP calibrates the step. A resolved pattern can carry the avatar right
        # across the board, and taking that jump for the stride makes every later plan
        # propose leaps the avatar cannot perform.
        span = max(box[2] - box[0], box[3] - box[1]) + 1
        shift = max(abs(box[0] - self._avatar_box[0]), abs(box[1] - self._avatar_box[1]))
        if 0 < shift <= span:
            self._stride = shift

    def _track(self, grid: np.ndarray, panel: Box) -> Box | None:
        """Re-find the avatar after our own move."""
        return self._avatar(_board_only(grid, panel))

    def _avatar(self, board: list[list[int]]) -> Box | None:
        """The avatar, once the exit is known: its own colours, minus the exit's cells.

        Read as CELLS, never as a component. Walking up to the exit makes the two touch,
        and touching pieces are one component — so an avatar found by matching whole
        components vanishes on the step before arrival, which is the only step that
        matters. Anything else that drifts against it merges the same way.
        """
        if self._avatar_palette is None or self._goal is None:
            return None
        mine = {
            (y, x)
            for y, row in enumerate(board)
            for x, colour in enumerate(row)
            if colour in self._avatar_palette
        } - self._goal
        if not mine:
            return None
        oy, ox = (self._avatar_box or (0, 0, 0, 0))[:2]
        return _cells_box(min(
            _split(mine), key=lambda g: min(abs(y - oy) + abs(x - ox) for y, x in g)
        ))

    # --- phase 2: walk the avatar into the exit ----------------------------

    def _navigate(self, grid: np.ndarray, panel: Box, simple: list[int]) -> Step | None:
        """Shortest lattice path to the exit, or a nudge toward it when none exists."""
        moves = [a for a in (1, 2, 3, 4) if a in simple]
        if len(moves) < 4:
            return None
        if self._floor is None:
            self._floor = _floor_colour(grid, panel)
        if self._floor is None:
            return None
        board = _board_only(grid, panel)
        avatar_box = self._avatar(board)
        if avatar_box is None or len(self._blocked) >= 4:
            # Either the piece we were following is gone, or it has refused every
            # direction — both say the pair was read off a frame that did not describe
            # this board, so read it again rather than pushing a dead avatar around.
            self._goal = None
            self._avatar_palette = None
            self._blocked.clear()
            pair = self._pair(self._objects(grid, board))
            if pair is None:
                return None
            avatar, goal = pair
            self._avatar_palette = avatar["palette"]
            self._goal = goal["cells"]
            avatar_box = avatar["box"]
        self._avatar_box = avatar_box
        self._suspect = False
        goal_box = _cells_box(self._goal)

        stride = self._stride or (avatar_box[2] - avatar_box[0] + 1)
        reach = _reachable(grid, avatar_box, self._goal, self._floor, stride)
        route = min(
            (p for place, p in reach.items() if _footprint(place, avatar_box) & self._goal),
            key=len, default=None,
        )
        if route:
            self._heading = None
            self._aim = None
            self._need = None
            return (route[0], None)

        objs = self._objects(grid, board)
        ground = _ground(board, avatar_box, self._floor)
        self._aim = self._retarget(grid, objs, ground, avatar_box, reach)
        if self._aim is not None:
            place, heading = self._aim
            self._heading = heading
            self._need = "fire"
            if place != (avatar_box[0], avatar_box[1]):
                return (reach[place][0], None)
            return None
        # No route and nothing to shoot at: the board is asking for the avatar itself to
        # change — a different size, or a different place entirely.
        self._need = "geom"
        return self._nudge(avatar_box, goal_box, moves, reach)

    def _retarget(
        self,
        grid: np.ndarray,
        objs: list[dict[str, Any]],
        ground: set[Cell],
        avatar_box: Box,
        reach: dict[Cell, list[int]],
    ) -> tuple[Cell, int] | None:
        """Choose the piece a ranged resolution is for, and where to stand to hit it.

        The mark is a piece that borders the ground we stand on yet no placement can ever
        touch — a switch in an alcove behind a gap too narrow to enter. That is what a
        ranged resolution is FOR; anything the avatar can simply walk up against needs no
        projectile.

        Target and stance are chosen TOGETHER, because a mark with no line of sight is not
        a plan: a board that offers two of them, one standing squarely between the avatar
        and the other, otherwise fixes on the near one and shoots it forever.

        Held across resolutions once chosen. Shrinking to line up the shot can make the
        alcove walkable, and a mark dropped the moment it becomes reachable is a mark the
        tool re-derives as absent — which is how one board spent its allowance shrinking,
        growing and shrinking again with nothing to aim at.
        """
        wall = set(background(grid))
        if self._target is not None:
            if any(o["cells"] & self._target for o in objs):
                return self._sight(grid, avatar_box, self._target, wall, reach)
            self._target = None
        covered: set[Cell] = set()
        for place in reach:
            covered |= _footprint(place, avatar_box)
        own = _box_cells(avatar_box)
        marks = [
            o["cells"] for o in objs
            if not (o["cells"] & (self._goal or set()))
            and not (o["cells"] & own)
            and not (o["cells"] & self._duds)
            and _halo(o["cells"]) & ground
            and not (_halo(o["cells"]) & covered)
        ]
        for mark in sorted(marks, key=len, reverse=True):
            sight = self._sight(grid, avatar_box, mark, wall, reach)
            if sight is not None:
                self._target = mark
                return sight
        if marks:
            self._target = max(marks, key=len)
        return None

    def _sight(
        self,
        grid: np.ndarray,
        avatar_box: Box,
        mark: set[Cell],
        wall: set[int],
        reach: dict[Cell, list[int]],
    ) -> tuple[Cell, int] | None:
        """Face-wide line of sight first, one line of sight only as a second thought.

        Which cell of the avatar a resolution fires from is the board's convention, not
        ours, so the only stance that is certainly a hit is one where EVERY cell of the
        leading face looks at the mark. When no such stance exists at the size we are, the
        answer is not a hopeful shot from a corner — it is to change size and look again.
        """
        seen = _aim(grid, avatar_box, mark, wall, reach, True)
        if seen is None and self._casts:
            seen = _aim(grid, avatar_box, mark, wall, reach, False)
        return seen

    def _nudge(
        self, avatar: Box, goal: Box, moves: list[int], reach: dict[Cell, list[int]]
    ) -> Step | None:
        """No route yet — close the gap on the wider axis, and face that way.

        Directions the search has already shown to be walls are not tried: a refused step
        costs a unit of the allowance to learn what the map on hand already says. Facing
        is not incidental either — a pattern the board resolves as a projectile travels
        the way the avatar faces — but that turn is bought once, deliberately, and only
        when the avatar is not already facing the right way.
        """
        dy = (goal[0] + goal[2]) - (avatar[0] + avatar[2])
        dx = (goal[1] + goal[3]) - (avatar[1] + avatar[3])
        wants = []
        if dy:
            wants.append((abs(dy), 2 if dy > 0 else 1))
        if dx:
            wants.append((abs(dx), 4 if dx > 0 else 3))
        wants.sort(reverse=True)
        self._heading = next((a for _, a in wants if a in moves), None)
        stride = self._stride or (avatar[2] - avatar[0] + 1)
        offsets = {1: (-stride, 0), 2: (stride, 0), 3: (0, -stride), 4: (0, stride)}
        wants = [
            (d, a) for d, a in wants
            if (avatar[0] + offsets[a][0], avatar[1] + offsets[a][1]) in reach
        ]
        if len(self._seen) > 1 and avatar in self._seen:
            # Already stood here since the last thing that changed the board, so nudging
            # on can only retrace. Two walls at right angles otherwise bounce the avatar
            # between them until the allowance runs out and the level is LOST — measured.
            return None
        self._seen.add(avatar)
        for _, action in wants:
            if action in moves and action not in self._blocked:
                return (action, None)
        return None

    # --- board reading -----------------------------------------------------

    def _objects(self, grid: np.ndarray, board: list[list[int]]) -> list[dict[str, Any]]:
        """Board pieces: neither wall, nor floor, nor the panel, nor the edge chrome.

        The wall is read off the WHOLE frame — on the blanked board the commonest value is
        the blanking itself, which would leave the maze standing as one enormous "piece".
        """
        skip = set(background(grid)) | {-1}
        if self._floor is not None:
            skip.add(self._floor)
        out: list[dict[str, Any]] = []
        for cells in components(board, skip):
            out.append({
                "cells": set(cells),
                "box": _cells_box(set(cells)),
                "size": len(cells),
                "palette": frozenset(board[y][x] for y, x in cells),
            })
        return out

    def _pair(self, objs: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """The avatar and its exit: two pieces from the SAME palette, one clearly larger.

        A door is painted in the key's colours. The size gap is what separates a real pair
        from a symmetric ornament, whose halves are the same size as each other.
        """
        by_palette: dict[frozenset[int], list[dict[str, Any]]] = {}
        for o in objs:
            by_palette.setdefault(o["palette"], []).append(o)
        best: tuple[int, dict[str, Any], dict[str, Any]] | None = None
        for group in by_palette.values():
            # Exactly two: one avatar, one exit. A palette with three or more members is
            # ornament — a scatter of identical markers reads as a pair otherwise, and a
            # tool that latches onto one steers a marker around for the rest of the level.
            if len(group) != 2:
                continue
            group.sort(key=lambda o: o["size"])
            small, large = group[0], group[-1]
            if large["size"] * 2 < small["size"] * 3:
                continue
            score = small["size"] + large["size"]
            if best is None or score > best[0]:
                best = (score, small, large)
        if best is None:
            return None
        _, small, large = best
        if self._avatar_palette is not None and small["palette"] != self._avatar_palette:
            return None
        return small, large


# --- lattice perception -----------------------------------------------------


def _find_pad(grid: np.ndarray) -> tuple[list[list[Cell]], int, list[list[int]]] | None:
    """The largest complete k x k lattice of equal flat squares, with its colours."""
    wall = background(grid)
    listed = grid.tolist()
    for side in _SIDES:
        blocks = uniform_blocks(listed, side, ignore=wall)
        if len(blocks) < _MIN_K * _MIN_K:
            continue
        lattice = _complete_lattice(sorted(blocks), side)
        if lattice is not None:
            return lattice, side, [[blocks[o] for o in row] for row in lattice]
    return None


def _complete_lattice(origins: list[Cell], side: int) -> list[list[Cell]] | None:
    """Pick k rows and k columns sharing one pitch, with every crossing filled."""
    present = set(origins)
    rows = sorted({y for y, _ in origins})
    cols = sorted({x for _, x in origins})
    pitches = {b - a for a, b in zip(rows, rows[1:])} | {b - a for a, b in zip(cols, cols[1:])}
    for k in range(_MAX_K, _MIN_K - 1, -1):
        for pitch in sorted(p for p in pitches if p >= side):
            for y0 in rows:
                ys = [y0 + i * pitch for i in range(k)]
                if not all(y in rows for y in ys):
                    continue
                for x0 in cols:
                    xs = [x0 + j * pitch for j in range(k)]
                    if not all(x in cols for x in xs):
                        continue
                    if all((y, x) in present for y in ys for x in xs):
                        return [[(y, x) for x in xs] for y in ys]
    return None


def _painted(colours: list[list[int]]) -> list[Cell]:
    """Cells carrying the instruction: a strict minority against one neutral majority."""
    counts = Counter(c for row in colours for c in row)
    if len(counts) < 2:
        return []
    neutral, hits = counts.most_common(1)[0]
    if hits * 2 <= sum(counts.values()):
        return []
    return [
        (r, c)
        for r in range(len(colours))
        for c in range(len(colours[r]))
        if colours[r][c] != neutral
    ]


# --- board geometry ---------------------------------------------------------


def _panel_box(grid: np.ndarray, origins: list[list[Cell]]) -> Box:
    """Bounding box of the component the lattice is mounted in."""
    seed = origins[0][0]
    for cells in components(grid, background(grid)):
        if seed in cells:
            ys = [y for y, _ in cells]
            xs = [x for _, x in cells]
            return (min(ys), min(xs), max(ys), max(xs))
    return (origins[0][0][0], origins[0][0][1], origins[-1][-1][0], origins[-1][-1][1])


def _board_only(grid: np.ndarray, panel: Box) -> list[list[int]]:
    """The frame with the instruction panel and the edge chrome blanked to -1."""
    chrome = edge_band(grid.shape)
    h, w = grid.shape
    return [
        [
            -1 if (chrome[y][x] or (panel[0] <= y <= panel[2] and panel[1] <= x <= panel[3]))
            else int(grid[y][x])
            for x in range(w)
        ]
        for y in range(h)
    ]


def _inside(inner: Box, outer: Box) -> bool:
    """Whether one bounding box sits wholly within another."""
    return (
        inner[0] >= outer[0] and inner[1] >= outer[1]
        and inner[2] <= outer[2] and inner[3] <= outer[3]
    )


def _cells_box(cells: set[Cell]) -> Box:
    ys = [y for y, _ in cells]
    xs = [x for _, x in cells]
    return (min(ys), min(xs), max(ys), max(xs))


def _split(cells: set[Cell]) -> list[set[Cell]]:
    """4-connected groups of a cell set."""
    todo = set(cells)
    out: list[set[Cell]] = []
    while todo:
        stack = [todo.pop()]
        group = set(stack)
        while stack:
            y, x = stack.pop()
            for n in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if n in todo:
                    todo.discard(n)
                    group.add(n)
                    stack.append(n)
        out.append(group)
    return out


def _box_cells(box: Box) -> set[Cell]:
    y0, x0, y1, x1 = box
    return {(y, x) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)}


def _floor_colour(grid: np.ndarray, panel: Box) -> int | None:
    """Walkable ground: the commonest board colour once the wall is set aside.

    The wall is the commonest colour of the WHOLE frame — a maze is mostly maze — so the
    ground is what is left over, and it is still far commoner than any piece standing on it.
    """
    wall = background(grid)
    counts: Counter[int] = Counter()
    for row in _board_only(grid, panel):
        for colour in row:
            if colour >= 0 and colour not in wall:
                counts[colour] += 1
    return counts.most_common(1)[0][0] if counts else None


def _footprint(place: Cell, avatar: Box) -> set[Cell]:
    """The cells the avatar would cover standing at ``place``."""
    y, x = place
    return _box_cells((y, x, y + avatar[2] - avatar[0], x + avatar[3] - avatar[1]))


def _halo(cells: set[Cell]) -> set[Cell]:
    """The 4-neighbours just outside a cell set."""
    out: set[Cell] = set()
    for y, x in cells:
        out |= {(y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)}
    return out - cells


def _ground(board: list[list[int]], avatar: Box, floor: int) -> set[Cell]:
    """The floor region the avatar actually stands in, flood-filled from under it.

    Ground the avatar cannot walk on is not ground for our purposes: a framed panel is
    full of the same colour, and treating that as walkable makes furniture look like part
    of the board.
    """
    h, w = len(board), len(board[0])
    seed = [c for c in _halo(_box_cells(avatar)) if 0 <= c[0] < h and 0 <= c[1] < w
            and board[c[0]][c[1]] == floor]
    seen = set(seed)
    stack = list(seed)
    while stack:
        y, x = stack.pop()
        for n in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if n in seen or not (0 <= n[0] < h and 0 <= n[1] < w):
                continue
            if board[n[0]][n[1]] == floor:
                seen.add(n)
                stack.append(n)
    return seen


def _aim(
    grid: np.ndarray,
    avatar: Box,
    target: set[Cell],
    wall: set[int],
    reach: dict[Cell, list[int]],
    whole_face: bool,
) -> tuple[Cell, int] | None:
    """Where to stand and which way to face so a directional resolution hits the mark.

    A ranged resolution leaves the avatar along ONE cell of the side it faces, and which
    cell that is — top, middle, bottom — is the board's convention, not ours. So the
    placement worth walking to is the one where the WHOLE leading face looks at the mark
    over unbroken floor: from such a placement every convention hits. ``whole_face`` off
    accepts a single line of sight instead, which is a guess and is only taken once a
    resolution has already been spent and the geometry did not improve.
    """
    if not reach or not target:
        return None
    h, w = grid.shape
    ah = avatar[2] - avatar[0] + 1
    aw = avatar[3] - avatar[1] + 1
    rays = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
    best: tuple[int, Cell, int] | None = None
    for place, path in reach.items():
        if best is not None and len(path) >= best[0]:
            continue
        y0, x0 = place
        faces = {
            1: [(y0 - 1, x0 + j) for j in range(aw)],
            2: [(y0 + ah, x0 + j) for j in range(aw)],
            3: [(y0 + i, x0 - 1) for i in range(ah)],
            4: [(y0 + i, x0 + aw) for i in range(ah)],
        }
        for action, (dy, dx) in rays.items():
            hits = 0
            for sy, sx in faces[action]:
                y, x = sy, sx
                while 0 <= y < h and 0 <= x < w:
                    if (y, x) in target:
                        hits += 1
                        break
                    if int(grid[y][x]) in wall:
                        break
                    y, x = y + dy, x + dx
            if hits == len(faces[action]) if whole_face else hits > 0:
                best = (len(path), place, action)
                break
    return (best[1], best[2]) if best else None


def _reachable(
    grid: np.ndarray, avatar: Box, goal: set[Cell], floor: int, stride: int
) -> dict[Cell, list[int]]:
    """Every placement the avatar can step to, with the shortest route to each."""
    h, w = grid.shape
    ah = avatar[2] - avatar[0] + 1
    aw = avatar[3] - avatar[1] + 1
    own = _box_cells(avatar)

    def free(y: int, x: int) -> bool:
        if y < 0 or x < 0 or y + ah > h or x + aw > w:
            return False
        for cy in range(y, y + ah):
            for cx in range(x, x + aw):
                if (cy, cx) in goal or (cy, cx) in own:
                    continue
                if int(grid[cy][cx]) != floor:
                    return False
        return True

    start = (avatar[0], avatar[1])
    out: dict[Cell, list[int]] = {start: []}
    queue: deque[Cell] = deque([start])
    deltas = ((1, (0, -stride)), (2, (0, stride)), (3, (-stride, 0)), (4, (stride, 0)))
    while queue:
        y, x = queue.popleft()
        path = out[(y, x)]
        if len(path) >= _MAX_PATH:
            continue
        for action, (dx, dy) in deltas:
            step = (y + dy, x + dx)
            if step in out or not free(*step):
                continue
            out[step] = path + [action]
            queue.append(step)
    return out
