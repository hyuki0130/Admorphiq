"""R98 STEP (iii): flow-family grounding — the harness-owned binding layer.

The FlowDeflectionDynamics family needs different evidence from the cell-state
and movement families: an ANIMATION. A single commit exposes the whole spill as a
stack of frame layers, so the harness must read a trajectory out of a layer stack
rather than a single before/after pair.

Everything here is earned from observation. There are NO colour constants and no
game identifiers: the flow colour is the one whose footprint grows monotonically
across an animation, the movable piece is the region that recolours on a click and
then TRANSLATES coherently under a press, the commit action is whichever action
returns more than one layer, and the emitters are the cells where flow first
appears. Anything not established returns ``UNKNOWN``.

Two measured traps from R92 are designed against:

* **Never identify a piece by connected components of its idle appearance.** A
  restore can leave two pieces touching, and 4-connectivity then merges them into
  one phantom region — which is exactly how a prior build came to plan moves for a
  blob the engine could not move. The piece is tracked by its SELECTED appearance,
  which stays separable even when pieces touch.
* **Failure to move is weak evidence.** A constraint is only recorded from a
  CONTRAST: the same action displaced the piece elsewhere and did not displace it
  here. A bare no-op is recorded as an unattributed no-op (the R96 asymmetric
  mobility rule).

Scope: grounding only — no verifier, no compiler, no LLM.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from typing import Any, Optional

Cell = tuple[int, int]
Grid = list[list[int]]

MIN_CONFIRMATIONS = 2  # the min-probe rule, shared with the other families


class _Unknown:
    """Explicit 'insufficient evidence'. A distinct sentinel so it can never be
    confused with a real value such as an empty tuple."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "UNKNOWN"


UNKNOWN = _Unknown()


@dataclass(frozen=True)
class Grounded:
    """A resolved value with the harness's confidence (``"high"`` | ``"low"``)."""

    value: Any
    confidence: str


def _as_grid(layer: Any) -> Grid:
    return [[int(v) for v in row] for row in layer]


def _infer_scale(grid: Grid) -> Optional[int]:
    """The pixel side of one board cell, read off the frame itself: the largest
    block size whose blocks are uniform. Frame-only and probe-free.

    A status bar drawn over the outermost pixel row or two is a rendering overlay
    rather than board structure, so uniformity is tested with a margin of 0, then
    1, then 2 pixels excluded from every edge. The margin is deliberately TINY: an
    earlier version exempted whole border BLOCKS and happily accepted a scale
    twice too large, because real board content near an edge was excused as
    overlay.

    A featureless frame is uniform at every scale, so a candidate must also
    resolve at least two distinct cell values; otherwise this reports nothing and
    the caller re-infers on a later, more informative frame.
    """
    n = len(grid)
    if n == 0 or len(grid[0]) != n:
        return None
    for s in range(n // 4, 0, -1):
        if n % s:
            continue
        span = n // s
        for margin in (0, 1, 2):
            if margin * 2 >= n:
                break
            uniform = True
            for by in range(span):
                for bx in range(span):
                    seen = {
                        grid[y][x]
                        for y in range(by * s, by * s + s)
                        for x in range(bx * s, bx * s + s)
                        if margin <= y < n - margin and margin <= x < n - margin
                    }
                    if len(seen) > 1:
                        uniform = False
                        break
                if not uniform:
                    break
            if uniform:
                break
        if not uniform:
            continue
        sampled = {
            grid[r * s + s // 2][c * s + s // 2] for r in range(span) for c in range(span)
        }
        if len(sampled) >= 2:
            return s
    return None


def _cellify(grid: Grid, scale: int) -> dict[Cell, int]:
    n = len(grid) // scale
    return {
        (r, c): grid[r * scale + scale // 2][c * scale + scale // 2]
        for r in range(n)
        for c in range(n)
    }


def _regions(cells: dict[Cell, int], colour: int) -> list[frozenset[Cell]]:
    """4-connected components of one appearance. Safe HERE because callers only
    segment the SELECTED appearance (unique by construction) or a colour already
    known to be a single entity."""
    todo = {c for c, v in cells.items() if v == colour}
    out: list[frozenset[Cell]] = []
    while todo:
        seed = todo.pop()
        comp = {seed}
        stack = [seed]
        while stack:
            r, c = stack.pop()
            for n in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if n in todo:
                    todo.remove(n)
                    comp.add(n)
                    stack.append(n)
        out.append(frozenset(comp))
    return sorted(out, key=min)


def _normalised(region: frozenset[Cell]) -> frozenset[Cell]:
    """A region's shape with its position removed, so two instances of the same
    shape compare equal wherever they sit."""
    r0 = min(r for r, _ in region)
    c0 = min(c for _, c in region)
    return frozenset((r - r0, c - c0) for (r, c) in region)


def _split(cells: frozenset[Cell]) -> list[frozenset[Cell]]:
    """4-connected components of an arbitrary cell set."""
    todo = set(cells)
    out: list[frozenset[Cell]] = []
    while todo:
        seed = todo.pop()
        comp = {seed}
        stack = [seed]
        while stack:
            r, c = stack.pop()
            for n in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if n in todo:
                    todo.remove(n)
                    comp.add(n)
                    stack.append(n)
        out.append(frozenset(comp))
    return sorted(out, key=min)


def _translation(before: frozenset[Cell], after: frozenset[Cell]) -> Optional[Cell]:
    """The rigid offset taking ``before`` to ``after``, or None if the shape did
    not survive as a rigid translation (a shape change is not a move)."""
    if not before or len(before) != len(after):
        return None
    dr = min(r for r, _ in after) - min(r for r, _ in before)
    dc = min(c for _, c in after) - min(c for _, c in before)
    if {(r + dr, c + dc) for (r, c) in before} != set(after):
        return None
    return (dr, dc)


@dataclass
class _Animation:
    """One commit's exposed spill: the flow colour, the per-layer frontier of new
    flow cells, and the regions that changed appearance while it ran."""

    flow_colour: int
    frontier: tuple[tuple[Cell, ...], ...]
    changed_regions: tuple[frozenset[Cell], ...] = field(default_factory=tuple)
    # Where the movable pieces stood WHEN THIS SPILL RAN. A piece is not a barrier,
    # and whether a cell held one is a fact about that moment, not about now: a
    # piece that has since been moved away leaves the cell it used to stop the flow
    # at looking like a wall for the rest of the level.
    piece_cells: frozenset[Cell] = frozenset()


class FlowGrounding:
    """Flow-family grounding over an observation stream that carries LAYERS.

    Drive it with :meth:`observe`, one call per executed action, passing the
    action id, the click coordinate (or ``None``) and the observation's layer
    stack. Query the harness_measured slots afterwards; each returns
    :class:`Grounded` or ``UNKNOWN``.
    """

    def __init__(self) -> None:
        self._scale: Optional[int] = None
        self._prev_cells: Optional[dict[Cell, int]] = None
        self._selected_colour: Optional[int] = None
        self._moving_colour: Optional[int] = None
        self._piece: Optional[frozenset[Cell]] = None
        # A board can carry SEVERAL movable pieces. One selection event reveals
        # both appearances at once — the clicked region takes the selected
        # appearance while the previously selected one drops to the IDLE one — and
        # from the idle appearance the whole inventory follows without probing
        # each candidate in turn.
        self._idle_colour: Optional[int] = None
        # Every region ever seen wearing the SELECTED appearance. Two touching
        # pieces share one idle-coloured region under 4-connectivity, and a planner
        # that can only move the merged blob cannot solve a board that needs them
        # placed independently. Selection is the disambiguator: the selected piece
        # is always segmented on its own.
        # Confirmed pieces are remembered by SHAPE, not by position. A region
        # recorded where it happened to sit goes stale the moment the piece moves,
        # and subtracting a stale region from the current board leaves fragments
        # that look like extra pieces. A shape stays true wherever the piece goes.
        self._confirmed_shapes: list[frozenset[Cell]] = []
        self._delta_obs: dict[int, Counter] = defaultdict(Counter)
        self._commit_obs: Counter = Counter()
        self._animations: list[_Animation] = []
        self._selection_obs: int = 0
        self._blocked: list[tuple[int, frozenset[Cell]]] = []
        self._unattributed_noops: int = 0

    # ── ingest ───────────────────────────────────────────────────────────

    def observe(self, action: int, xy: Optional[tuple[int, int]], layers: Any) -> None:
        """Ingest one executed action and the observation it produced.

        Action id 0 marks a SEED frame — the board as it stands before this
        grounding has acted. Its picture is recorded but nothing is attributed to
        it, because the frame it carries was produced by something else. Without
        that rule a level entered on the back of a multi-layer commit would credit
        the seed with being the commit action, and every plan afterwards would
        emit an action id that does not exist.
        """
        stack = [_as_grid(layer) for layer in layers]
        if not stack:
            return
        if self._scale is None:
            self._scale = _infer_scale(stack[0])
        if self._scale is None:
            return

        after = _cellify(stack[-1], self._scale)
        before = self._prev_cells

        seed = action == 0
        committed = len(stack) > 1 and not seed
        if committed:
            self._commit_obs[action] += 1
            anim = self._read_animation(stack)
            if anim is not None:
                self._animations.append(
                    replace(anim, piece_cells=frozenset(self._all_piece_cells()))
                )

        # An action that exposed a scripted consequence is a COMMIT, not a
        # placement action: classifying its before/after pair would read the
        # settle-and-restore as a failed move and pollute the no-op tally. The
        # tracked piece keeps its pre-commit position, which is exactly the
        # position that persists across a failed attempt.
        if before is not None and not committed and not seed:
            self._classify(before, action, xy, after)
        self._prev_cells = after

    def _read_animation(self, stack: list[Grid]) -> Optional[_Animation]:
        """Read one exposed spill out of a layer stack.

        The flow is the colour whose footprint grows INCREMENTALLY, one small step
        at a time, over the longest run of layers. Two traps this handles:

        * the run ENDS when the footprint stops being a superset of itself — a
          spill's trail only ever grows, so the first non-superset layer is a
          different board (the restore, or the next level) and must not be read;
        * a target that lights up when satisfied also "grows", but in one or two
          jumps rather than across many layers, so the number of GROWTH STEPS —
          not the final size — is what separates flow from a status change.
        """
        assert self._scale is not None
        per_layer = [_cellify(g, self._scale) for g in stack]
        colours = {v for cells in per_layer for v in cells.values()}

        best: Optional[tuple[tuple[int, int], int, list[set[Cell]]]] = None
        for colour in colours:
            sets = [{c for c, v in cells.items() if v == colour} for cells in per_layer]
            run: list[set[Cell]] = []
            for s in sets:
                if not s and not run:
                    continue
                if run and not (run[-1] <= s):
                    break
                run.append(s)
            if len(run) < 3:
                continue
            steps = sum(1 for a, b in zip(run, run[1:]) if len(b) > len(a))
            if steps < 3 or len(run[-1]) <= len(run[0]):
                continue
            key = (steps, len(run[-1]))
            if best is None or key > best[0]:
                best = (key, colour, run)
        if best is None:
            return None

        _, colour, run = best
        frontier: list[tuple[Cell, ...]] = []
        seen: set[Cell] = set()
        for s in run:
            frontier.append(tuple(sorted(s - seen)))
            seen |= s

        # Regions whose appearance changed WHILE the spill ran, excluding the flow
        # itself: the satisfied-target signal and the model's sink shortlist.
        #
        # The change must be STABLE at the end of the run. A failure animation
        # makes status bands and unmet targets OSCILLATE, and an oscillating band
        # pinned to a board edge touches the cells below the real targets — so
        # without this rule the targets and the band merge under 4-connectivity
        # into one phantom region. That is the same merge trap that once had a
        # planner moving a blob the engine could not move, in a new guise.
        end = len(run) - 1
        tail = per_layer[max(0, end - 2) : end + 1]
        first, last = per_layer[0], per_layer[end]
        changed = {
            c
            for c in first
            if first[c] != last.get(c)
            and last.get(c) != colour
            and first[c] != colour
            and len({t.get(c) for t in tail}) == 1
        }
        groups: list[frozenset[Cell]] = []
        todo = set(changed)
        while todo:
            seed = todo.pop()
            comp = {seed}
            pending = [seed]
            while pending:
                r, c = pending.pop()
                for n in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                    if n in todo:
                        todo.remove(n)
                        comp.add(n)
                        pending.append(n)
            groups.append(frozenset(comp))
        return _Animation(colour, tuple(frontier), tuple(sorted(groups, key=min)))

    def _classify(
        self,
        before: dict[Cell, int],
        action: int,
        xy: Optional[tuple[int, int]],
        after: dict[Cell, int],
    ) -> None:
        """Attribute one transition: a selection recolour, a rigid translation, or
        a no-op.

        An action that carried a COORDINATE is read as a selection first. A
        selection swap looks superficially like movement — the selected appearance
        vanishes from one region and appears on another — and letting the movement
        branch see it first records a phantom displacement for the click action,
        which then leaks into the delta table and into plans as an action id that
        does not move anything.

        Movement is checked without requiring selection to have been observed:
        coherent observed movement is the strong positive, and on a board whose
        piece starts pre-selected there is no selection event to see.
        """
        changed = {c for c in before if before[c] != after.get(c)}
        if not changed:
            if self._piece is not None and action in self._delta_obs:
                self._blocked.append((action, self._piece))
            else:
                self._unattributed_noops += 1
            return

        if xy is not None and self._absorb_selection(before, changed, after):
            return
        if self._absorb_translation(before, action, changed, after):
            return
        if xy is None:
            self._unattributed_noops += 1
            return
        if self._absorb_selection(before, changed, after):
            return
        self._unattributed_noops += 1

    def _absorb_translation(
        self,
        before: dict[Cell, int],
        action: int,
        changed: set[Cell],
        after: dict[Cell, int],
    ) -> bool:
        """One piece moved rigidly. Two ways to see it, and the second matters.

        The clean case is a colour whose single region translated. But a piece that
        comes to rest against a neighbour MERGES with it under 4-connectivity, so the
        region count changes and the clean test silently records nothing — measured
        on the fourth level, where one of the four directions was missing from the
        delta table even though pressing it plainly moves a piece. A missing action
        is not neutral: the planner then cannot reach any placement needing it.

        So the fallback reads the CHANGE SET itself: cells that stopped wearing an
        appearance and cells that started wearing it, equal in number and related by
        a single translation, is a move regardless of how the regions merged."""
        for colour in {before[c] for c in changed} | {after[c] for c in changed if c in after}:
            b = _regions(before, colour)
            a = _regions(after, colour)
            if len(b) != 1 or len(a) != 1:
                continue
            delta = _translation(b[0], a[0])
            if delta is None or delta == (0, 0):
                continue
            if changed != set(b[0]) ^ set(a[0]):
                continue
            self._record_move(action, colour, delta, a[0])
            return True

        for colour in {before[c] for c in changed} | {after[c] for c in changed if c in after}:
            vacated = frozenset(
                c for c in changed if before.get(c) == colour and after.get(c) != colour
            )
            occupied = frozenset(
                c for c in changed if after.get(c) == colour and before.get(c) != colour
            )
            if not vacated or len(vacated) != len(occupied):
                continue
            dr = min(r for r, _ in occupied) - min(r for r, _ in vacated)
            dc = min(c for _, c in occupied) - min(c for _, c in vacated)
            if (dr, dc) == (0, 0):
                continue
            if _normalised(vacated) != _normalised(occupied):
                continue
            moved = frozenset((r + dr, c + dc) for (r, c) in vacated)
            self._record_move(action, colour, (dr, dc), moved)
            return True
        return False

    def _record_move(
        self, action: int, colour: int, delta: Cell, landed: frozenset[Cell]
    ) -> None:
        self._delta_obs[action][delta] += 1
        self._moving_colour = colour
        self._piece = landed
        shape = _normalised(landed)
        if shape not in self._confirmed_shapes:
            self._confirmed_shapes.append(shape)

    def _absorb_selection(
        self, before: dict[Cell, int], changed: set[Cell], after: dict[Cell, int]
    ) -> bool:
        """A region took on a new appearance IN PLACE.

        A selection transition shows TWO regions changing at once — the clicked
        piece taking the selected appearance and the previously selected one
        dropping to the idle appearance — and both look identical to a test that
        merely asks "did a region change colour in place". Picking the wrong one
        inverts the harness's whole notion of selection, which then reads every
        later click as having done nothing.

        The engine selects exactly ONE piece at a time, so the appearance worn by a
        single region is the selected one and the appearance shared by the rest is
        idle. That is the discriminator used here."""
        candidates: list[tuple[int, frozenset[Cell]]] = []
        for colour in {after[c] for c in changed if c in after}:
            for r in _regions(after, colour):
                if not (r <= changed) or any(before[c] == colour for c in r):
                    continue
                if len({before[c] for c in r}) != 1:
                    continue
                candidates.append((colour, r))
        if not candidates:
            return False

        selected = [
            (colour, r) for colour, r in candidates if len(_regions(after, colour)) == 1
        ]
        colour, region = (selected or candidates)[0]
        others = {c for c, _ in candidates if c != colour}
        if others:
            self._idle_colour = others.pop()
        elif self._selected_colour is not None:
            released = {
                c for c in changed
                if before[c] == self._selected_colour and after.get(c) != self._selected_colour
            }
            dropped = {after[c] for c in released if c in after}
            if len(dropped) == 1:
                self._idle_colour = dropped.pop()
        self._selected_colour = colour
        self._piece = region
        self._confirmed_shapes.append(_normalised(region))
        self._selection_obs += 1
        return True

    # ── queries ──────────────────────────────────────────────────────────

    def detected(self) -> bool:
        """True once an action has been seen to expose a multi-layer consequence —
        the family's observable tell. Every query below is UNKNOWN until then, so
        a non-flow board never activates these paths."""
        return bool(self._commit_obs)

    def piece_appearances(self) -> tuple[Optional[int], Optional[int]]:
        """(selected, idle) as read off the CURRENT board.

        The engine selects exactly ONE piece at a time, so among the two piece
        appearances the one worn by a single region is the selected one. That is a
        standing invariant, not something to be inferred once from a transition and
        then trusted: a failed attempt re-selects a piece of the engine's choosing,
        and any belief carried across that moment can silently invert. Deriving it
        from the board each time removes the whole class.

        Falls back to the remembered values when the board cannot decide — a single
        piece, or both appearances forming one region."""
        stored = (self._selected_colour, self._idle_colour)
        if self._prev_cells is None or None in stored:
            return stored
        if stored[0] == stored[1]:
            return stored
        counts = {
            colour: len(_regions(self._prev_cells, colour))
            for colour in stored
            if colour is not None
        }
        singles = [c for c, n in counts.items() if n == 1]
        if len(singles) != 1:
            return stored
        selected = singles[0]
        idle = next(c for c in stored if c != selected)
        return selected, idle

    def board_view(self) -> Any:
        """The current board as a cell->appearance map, exactly as grounding sees it.

        Exposed so a diagnostic reads the SAME frame grounding does. A level
        boundary arrives as a multi-layer observation whose first layers still show
        the PREVIOUS board, and reading layer zero produces a confident description
        of the wrong level — which is how a measurement once reported a flow
        direction and an emitter set that were simply the last level's."""
        if self._prev_cells is None:
            return UNKNOWN
        return Grounded(dict(self._prev_cells), "high")

    def scale(self) -> Any:
        if self._scale is None:
            return UNKNOWN
        return Grounded(self._scale, "high")

    def commit_action(self) -> Any:
        if not self._commit_obs:
            return UNKNOWN
        action, count = self._commit_obs.most_common(1)[0]
        return Grounded(action, "high" if count >= MIN_CONFIRMATIONS else "low")

    def control_mode(self) -> Any:
        """``select_then_translate`` requires BOTH a selection recolour and a
        translation of that selected region.

        On a board with a SINGLE piece that the engine pre-selects, the two modes
        are behaviourally identical and no click produces a frame change, so the
        distinction is genuinely unobservable. The harness says so — a low-
        confidence ``direct_translate`` — rather than inventing the mechanism it
        cannot see. :meth:`control_mode_indistinguishable` reports that state
        explicitly so the contract can treat it as an equivalence class instead of
        an error."""
        if not self.detected():
            return UNKNOWN
        if self._selection_obs and self._delta_obs:
            return Grounded("select_then_translate", "high")
        if self._delta_obs:
            return Grounded("direct_translate", "low")
        return UNKNOWN

    def control_mode_indistinguishable(self) -> bool:
        """True when movement was observed but no selection event could exist —
        a single tracked piece and zero selection recolours."""
        return bool(self._delta_obs) and not self._selection_obs

    def tracked_region(self) -> Any:
        """The region confirmed to translate rigidly under a press.

        Deliberately NOT gated on family detection: "some region moves coherently
        when I press a direction" is a family-agnostic fact, and a driver needs it
        BEFORE it has seen any scripted consequence in order to aim its first
        commit. The family-specific claims below stay gated.

        Read off the CURRENT board wherever the board can answer. The remembered set
        is maintained by matching translations, and a translation that was refused —
        or a piece that came to rest against a neighbour and is now drawn as one
        region — leaves it describing a piece that is no longer there. Measured on
        idx3: six cells wore the selected appearance while this returned ONE, and the
        driver pressed on that answer. The engine selects exactly one piece at a time,
        so the region wearing the selected appearance IS the tracked piece; the
        remembered set is the fallback for when the board cannot say."""
        if self._piece is None or not self._delta_obs:
            return UNKNOWN
        if self._prev_cells is not None:
            selected, _idle = self.piece_appearances()
            if selected is not None:
                worn = _regions(self._prev_cells, selected)
                if len(worn) == 1:
                    return Grounded(tuple(sorted(worn[0])), "high")
        return Grounded(tuple(sorted(self._piece)), "high")

    def pieces(self) -> Any:
        """Every movable piece on the board, read off the CURRENT board.

        Two touching pieces share a single region under 4-connectivity while idle,
        and a planner that can only move the merged pair cannot solve a board that
        needs them placed independently. Selection is the disambiguator — the
        selected piece is always segmented on its own — and what selection teaches
        is a SHAPE, which stays true wherever that piece later moves.

        A region is therefore split by tiling it with confirmed shapes when it is
        larger than any of them. A region that matches nothing known is reported
        whole: coarser, but never invented.

        Reading the current board matters because a failed attempt re-selects a
        piece of the engine's choosing, so which one wears the selected appearance
        is not something the harness may assume."""
        if not self.detected() or self._piece is None or self._prev_cells is None:
            return UNKNOWN
        cells = self._prev_cells
        found: list[frozenset[Cell]] = []
        available = list(self._confirmed_shapes)
        selected, idle = self.piece_appearances()
        for colour in (selected, idle, self._moving_colour):
            if colour is None:
                continue
            for region in _regions(cells, colour):
                parts, available = self._tile(region, available)
                for part in parts:
                    if part not in found:
                        found.append(part)
        if not found:
            found = [frozenset(self._piece)]
        found = self._bridge(found, cells)
        # A cell wearing the MOVING appearance can sit inside a piece that is standing
        # still — measured on idx3, where one cell of a five-cell bar rendered in that
        # colour and the bar was reported as a five-cell piece PLUS a phantom one-cell
        # piece at the same place. A region already contained in another is not a
        # second piece.
        found = [r for r in found if not any(r < other for other in found)]
        ordered = sorted(found, key=min)
        return Grounded(
            tuple((f"piece_{i}", tuple(sorted(r))) for i, r in enumerate(ordered)), "high"
        )

    def _bridge(
        self, regions: list[frozenset[Cell]], cells: dict[Cell, int]
    ) -> list[frozenset[Cell]]:
        """Join pieces parted by a single foreign cell, absorbing that cell.

        A piece can carry a cell of another appearance — a source embedded in the
        bar renders in its own colour — and segmenting by appearance then splits the
        bar into two regions with the odd cell belonging to nothing. A cell in no
        entity is a FREE cell, so the flow walks straight through the middle of a bar
        the engine treats as one obstruction.

        Only a ONE-cell gap is bridged, and only when that cell is not background:
        two genuinely separate pieces are parted by empty space, which stays empty.
        """
        if not regions:
            return regions
        background = Counter(cells.values()).most_common(1)[0][0]
        merged = [set(r) for r in regions]
        changed = True
        while changed:
            changed = False
            for i in range(len(merged)):
                for j in range(i + 1, len(merged)):
                    gap = self._single_gap(merged[i], merged[j])
                    if gap is None or cells.get(gap, background) == background:
                        continue
                    merged[i] |= merged[j] | {gap}
                    merged.pop(j)
                    changed = True
                    break
                if changed:
                    break
        return [frozenset(r) for r in merged]

    @staticmethod
    def _single_gap(a: set[Cell], b: set[Cell]) -> Optional[Cell]:
        """The one cell separating two regions on a shared row, if that is all that
        separates them."""
        rows_a = {r for r, _ in a}
        if rows_a != {r for r, _ in b} or len(rows_a) != 1:
            return None
        row = next(iter(rows_a))
        cols_a = sorted(c for _, c in a)
        cols_b = sorted(c for _, c in b)
        if cols_a[-1] + 2 == cols_b[0]:
            return (row, cols_a[-1] + 1)
        if cols_b[-1] + 2 == cols_a[0]:
            return (row, cols_b[-1] + 1)
        return None

    def _tile(
        self, region: frozenset[Cell], available: list[frozenset[Cell]]
    ) -> tuple[list[frozenset[Cell]], list[frozenset[Cell]]]:
        """Split a region into confirmed shapes, consuming from a MULTISET.

        Each selection confirms one instance of a shape, and an instance may be
        spent once. Without that, a genuine six-wide piece is happily explained as
        two three-wide ones because the arithmetic works — inventing pieces the
        board does not have, which is worse than reporting a merged pair whole.

        Only an EXACT cover counts. A leftover means the shapes on hand do not
        explain this region, so it is returned whole: coarser, but never invented."""
        shape = _normalised(region)
        for i, known in enumerate(available):
            if known == shape:
                return [region], available[:i] + available[i + 1:]
        if not available:
            return [region], available

        remaining = set(region)
        pool = sorted(available, key=len, reverse=True)
        parts: list[frozenset[Cell]] = []
        used: list[int] = []
        progress = True
        while remaining and progress:
            progress = False
            for idx, candidate in enumerate(pool):
                if idx in used or len(candidate) > len(remaining):
                    continue
                anchor = min(remaining)
                dr = anchor[0] - min(r for r, _ in candidate)
                dc = anchor[1] - min(c for _, c in candidate)
                placed = frozenset((r + dr, c + dc) for (r, c) in candidate)
                if placed <= remaining:
                    parts.append(placed)
                    remaining -= placed
                    used.append(idx)
                    progress = True
                    break
        if parts and not remaining:
            left = [s for i, s in enumerate(pool) if i not in used]
            return parts, left
        return [region], available

    def idle_appearance_known(self) -> bool:
        """Whether a selection event has revealed how an unselected piece looks. Until
        it has, a multi-piece board is indistinguishable from a single-piece one."""
        return self._idle_colour is not None

    def piece_deltas(self) -> Any:
        """Per-action ``(dr, dc)``, each reported only once confirmed. Absorbs any
        board rotation without ever naming rotation."""
        if not self.detected() or not self._delta_obs:
            return UNKNOWN
        out: list[tuple[int, int, int]] = []
        low = False
        for action, counter in sorted(self._delta_obs.items()):
            (delta, count), = counter.most_common(1)
            low |= count < MIN_CONFIRMATIONS
            out.append((action, delta[0], delta[1]))
        return Grounded(tuple(out), "low" if low else "high")

    def emitters(self) -> Any:
        """Where flow first appears in an exposed animation."""
        if not self._animations:
            return UNKNOWN
        first = self._animations[0].frontier
        origin = next((f for f in first if f), None)
        if not origin:
            return UNKNOWN
        return Grounded(tuple(origin), "high")

    def flow_origin_hint(self) -> Any:
        """A PRE-COMMIT, low-confidence guess at where flow will come from: the
        topmost compact region that is neither the tracked piece nor the dominant
        background. It exists because the first sacrificial commit is more
        informative when it is aimed, and it is explicitly LOW confidence — the
        high-confidence answer is :meth:`emitters`, which only an animation can
        give. A driver may aim with the hint and must confirm with the emitter."""
        if self._prev_cells is None:
            return UNKNOWN
        cells = self._prev_cells
        background = Counter(cells.values()).most_common(1)[0][0]
        piece = self._piece or frozenset()
        candidates = [
            (r, c)
            for (r, c), v in cells.items()
            if v != background and (r, c) not in piece
        ]
        if not candidates:
            return UNKNOWN
        top = min(r for r, _ in candidates)
        row = sorted(c for r, c in candidates if r == top)
        # a wide band across the top is a status strip, not a source
        if len(row) > max(2, len(cells) ** 0.5 // 2):
            return UNKNOWN
        return Grounded(tuple((top, c) for c in row), "low")

    def initial_direction(self) -> Any:
        """The direction flow travels, read off the first two frontiers.

        Derived as the unit step that maps the first frontier onto the second, so a
        board with SEVERAL sources works exactly like one with a single source:
        three parallel streams advance by the same offset, and requiring one cell
        per frontier would report UNKNOWN on every multi-source board."""
        if not self._animations:
            return UNKNOWN
        frontier = [f for f in self._animations[0].frontier if f]
        if len(frontier) < 2:
            return UNKNOWN
        first, second = set(frontier[0]), set(frontier[1])
        best: Optional[tuple[int, Cell]] = None
        for step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            explained = sum(
                1 for (r, c) in second if (r - step[0], c - step[1]) in first
            )
            if explained and (best is None or explained > best[0]):
                best = (explained, step)
        if best is None or best[0] < len(second):
            return UNKNOWN
        return Grounded(best[1], "high")

    def trajectory(self) -> Any:
        """The per-layer frontier of the most recent animation — the verifier's
        input, and the only place a predicted trajectory can be checked against."""
        if not self._animations:
            return UNKNOWN
        return Grounded(self._animations[-1].frontier, "high")

    def _all_piece_cells(self) -> set[Cell]:
        """Every cell occupied by any movable piece — the SAME inventory
        :meth:`pieces` reports.

        Deriving it separately is how a cell ends up in two classes at once: an
        embedded source was absorbed into its bar by the inventory while a
        by-appearance recomputation still left it out, so it stayed classified as a
        barrier. The propagator checks barriers before pieces, and the flow died
        exactly where the engine splits it."""
        inventory = self.pieces()
        if inventory is not UNKNOWN:
            return {cell for _, cells in inventory.value for cell in cells}
        cells: set[Cell] = set(self._piece or ())
        if self._prev_cells is None:
            return cells
        for colour in (self._selected_colour, self._idle_colour, self._moving_colour):
            if colour is None:
                continue
            for region in _regions(self._prev_cells, colour):
                cells |= set(region)
        return cells

    def _matching_shape_regions(
        self, known: list[frozenset[Cell]]
    ) -> list[frozenset[Cell]]:
        """Regions that repeat a known target's exact shape and appearance.

        A probing spill reaches some targets and misses others, and a target the
        flow never touched still has to be planned for — otherwise "satisfy every
        target" silently means "satisfy the ones I happened to see". Targets on a
        board are near-always instances of one shape, so a region congruent (by
        translation) to a confirmed one, in the same appearance, is named as well.
        Shape identity is the evidence; no appearance constant is assumed."""
        if not known or self._prev_cells is None:
            return []
        cells = self._prev_cells
        pieces = self._all_piece_cells()

        signatures: set[tuple[int, frozenset[Cell]]] = set()
        for region in known:
            colours = {cells[c] for c in region if c in cells}
            if len(colours) != 1:
                continue
            signatures.add((colours.pop(), _normalised(region)))

        out: list[frozenset[Cell]] = []
        for colour, shape in signatures:
            for region in _regions(cells, colour):
                # Targets standing side by side merge into one region, so a region
                # is split by its MOUTHS before its shape is compared — otherwise a
                # row of identical targets matches nothing, and the ones the probe
                # never reached stay invisible.
                for part in self._by_mouth(region):
                    if part & pieces or any(part & k for k in known):
                        continue
                    if _normalised(part) == shape:
                        out.append(part)
        return sorted(out, key=min)

    def _appearance_regions(self, known: list[frozenset[Cell]]) -> list[frozenset[Cell]]:
        """Regions wearing the appearance every named target already agrees on.

        Shape congruence names a target the flow never touched only when it is an
        exact copy of a confirmed one — and a board can hold a target of a different
        size. Measured on the fourth sp80 level: three targets of five cells were
        named, a fourth of FOUR cells was not, so the plan was compiled for three
        targets on a board that needed four and could not win however precisely it
        was executed.

        What the fourth still shared was its APPEARANCE. So when every named target
        wears one and the same colour, that colour identifies targets, and the rest
        of the board is read for it. Unanimity is the guard: appearance is weaker
        evidence than shape, and a single disagreeing group means the appearance is
        not the discriminator here. The flow's own colour is never a target, and
        movable pieces are excluded as everywhere else."""
        if not known or self._prev_cells is None:
            return []
        cells = self._prev_cells
        colours = {cells[c] for region in known for c in region if c in cells}
        if len(colours) != 1:
            return []
        colour = colours.pop()
        if colour in {anim.flow_colour for anim in self._animations}:
            return []
        pieces = self._all_piece_cells()
        out: list[frozenset[Cell]] = []
        for region in _regions(cells, colour):
            for part in self._by_mouth(region):
                if part & pieces or any(part & k for k in known):
                    continue
                if not self._mouths(part):
                    # Appearance alone is not enough to call something a target: this
                    # family's satisfaction runs through a NOTCH, so a region without
                    # one cannot be satisfied however the pieces are placed. Measured
                    # on the fourth sp80 level, where a solid two-by-two block wearing
                    # the target colour was named and made the objective unreachable —
                    # the compiler then reported no layout, correctly, for a target
                    # that was never one. The stronger sources keep their say: a
                    # region the flow was OBSTRUCTED by has direct evidence behind it.
                    continue
                out.append(part)
        return sorted(out, key=min)

    def _obstruction_regions(self) -> list[frozenset[Cell]]:
        """Regions that obstructed the flow, minus the movable pieces.

        A flanking pair appearing on one row means the cell AHEAD of the flow was
        occupied by something. Those blocker cells are grouped by their appearance,
        and any group overlapping a tracked piece is dropped — what is left is a
        static obstruction, which on this family is a target."""
        if not self._animations or self._prev_cells is None:
            return []
        direction = self.initial_direction()
        if direction is UNKNOWN:
            return []
        dr, dc = direction.value
        anim = self._animations[-1]
        pieces = self._all_piece_cells()

        blockers: set[Cell] = set()
        for i in range(len(anim.frontier) - 1):
            nxt = set(anim.frontier[i + 1])
            for (r, c) in anim.frontier[i]:
                if {(r - dc, c - dr), (r + dc, c + dr)} <= nxt:
                    blockers.add((r + dr, c + dc))

        by_colour: dict[int, set[Cell]] = {}
        for cell in blockers:
            if cell in pieces or cell not in self._prev_cells:
                continue
            by_colour.setdefault(self._prev_cells[cell], set()).add(cell)

        out: list[frozenset[Cell]] = []
        for colour, seeds in by_colour.items():
            for region in _regions(self._prev_cells, colour):
                if region & seeds and not (region & pieces):
                    out.append(region)
        return sorted(out, key=min)

    def selection_candidates(self) -> Any:
        """Regions worth clicking to look for another movable piece, best first.

        Everything that is not the background, not the tracked piece, and not part
        of the flow. The ORDER matters, because probing costs actions: a further
        piece is far more likely to be shaped like the piece already being tracked
        than like anything else on the board, so candidates are ranked by shape
        FAMILY — same thickness first, then closest area — and regions that span
        the whole board are dropped as edge-pinned furniture rather than entities.
        Anchors are in CELL coordinates."""
        if self._prev_cells is None or self._scale is None or self._piece is None:
            return UNKNOWN
        cells = self._prev_cells
        size = int(round(len(cells) ** 0.5))
        background = Counter(cells.values()).most_common(1)[0][0]
        exclude = set(self._piece)
        for anim in self._animations:
            exclude |= {c for layer in anim.frontier for c in layer}

        tracked_rows = len({r for r, _ in self._piece})
        tracked_area = len(self._piece)

        scored: list[tuple[tuple[int, int], Cell]] = []
        for colour in {v for v in cells.values() if v != background}:
            for region in _regions(cells, colour):
                if region & exclude:
                    continue
                rows = sorted({r for r, _ in region})
                cols = sorted({c for _, c in region})
                if len(cols) >= size or len(rows) >= size:
                    continue  # spans the board: furniture, not an entity
                rank = (abs(len(rows) - tracked_rows), abs(len(region) - tracked_area))
                scored.append((rank, (rows[len(rows) // 2], cols[len(cols) // 2])))
        if not scored:
            return UNKNOWN
        scored.sort()
        return Grounded(tuple(anchor for _, anchor in scored), "high")

    def hidden_sources(self) -> Any:
        """Places where flow appeared with nothing feeding it.

        A source can sit UNDERNEATH a movable piece: the piece is drawn over it, so
        the frame shows no source there and the flow it produces stays invisible
        until it emerges past the piece. Measured on the fourth level, where a pair
        of cells appeared either side of a piece six ticks into the animation with
        no flow above them and no source in sight.

        Detected as an ORPHAN emergence: a new cell whose predecessor along the flow
        direction was never part of the trail. Reported with the obstruction it
        emerged around, which is where the source must be."""
        if not self._animations:
            return UNKNOWN
        direction = self.initial_direction()
        if direction is UNKNOWN:
            return UNKNOWN
        dr, dc = direction.value
        anim = self._animations[-1]
        pieces = self._all_piece_cells()

        seen: set[Cell] = set()
        orphans: list[tuple[Cell, Optional[Cell]]] = []
        for layer in anim.frontier:
            for cell in layer:
                r, c = cell
                behind = (r - dr, c - dc)
                flanks = ((r - dc, c - dr), (r + dc, c + dr))
                if behind in seen:
                    continue
                if any(f in seen for f in flanks):
                    continue
                if cell in self._first_flow(anim):
                    continue
                host = next((f for f in flanks if f in pieces), None)
                if host is None and behind in pieces:
                    host = behind
                orphans.append((cell, host))
            seen |= set(layer)
        if not orphans:
            return UNKNOWN
        return Grounded(tuple(orphans), "high")

    @staticmethod
    def _first_flow(anim: "_Animation") -> set[Cell]:
        for layer in anim.frontier:
            if layer:
                return set(layer)
        return set()

    def emergences(self) -> Any:
        """Where and WHEN flow entered the board from somewhere unmodelled.

        :meth:`hidden_sources` names the obstruction a concealed source must sit
        behind; this reports the observation itself — the cell and the tick at
        which flow appeared there — which is what a replay needs in order to
        reproduce the trajectory. Modelling the observation rather than the
        concealment keeps the prediction checkable: the frames show where and when,
        while the mechanism behind the piece is inference."""
        if not self._animations:
            return UNKNOWN
        direction = self.initial_direction()
        if direction is UNKNOWN:
            return UNKNOWN
        dr, dc = direction.value
        anim = self._animations[-1]
        first = self._first_flow(anim)

        # Ticks are counted on the PROGRESS axis — empty frontiers skipped — because
        # that is the axis the replay comparison uses. The engine renders pauses that
        # the propagator does not take, so a raw tick index would place the emergence
        # several steps late.
        seen: set[Cell] = set()
        out: list[tuple[Cell, int]] = []
        tick = -1
        for layer in anim.frontier:
            if not layer:
                continue
            tick += 1
            for cell in layer:
                r, c = cell
                behind = (r - dr, c - dc)
                flanks = ((r - dc, c - dr), (r + dc, c + dr))
                if cell in first or behind in seen or any(f in seen for f in flanks):
                    continue
                out.append((cell, tick))
            seen |= set(layer)
        if not out:
            return UNKNOWN
        if anim.piece_cells and anim.piece_cells != frozenset(self._all_piece_cells()):
            # An emergence is an OBSERVATION under one layout. A concealed source sits
            # at a fixed cell and the flow appears around whatever covers it, so once
            # the pieces have moved the same source enters somewhere else — measured on
            # idx3, where the committed spill entered at row 9 while the emergences
            # injected from the probe layout sat at row 3. Replaying them onto a
            # different layout predicts flow the engine never produces AND misses the
            # flow it does.
            return UNKNOWN
        return Grounded(tuple(out), "high")

    def barriers(self) -> Any:
        """Cells the flow reached and could NOT pass, excluding sinks and pieces.

        Evidence-bounded on purpose: this reports only barriers an observed spill
        actually ran into, never a guess at the rest of the board. A cell counts
        when the flow occupied the cell before it along the flow direction and the
        cell itself never became flow, while being neither a target nor a piece."""
        if not self._animations or self._prev_cells is None:
            return UNKNOWN
        direction = self.initial_direction()
        if direction is UNKNOWN:
            return UNKNOWN
        dr, dc = direction.value
        anim = self._animations[-1]
        trail = {c for layer in anim.frontier for c in layer}
        sinks = {c for g in anim.changed_regions for c in g}
        targets = self.sink_candidates()
        if targets is not UNKNOWN:
            sinks |= {c for _, cells in targets.value for c in cells}
        # EVERY piece, not just the tracked one. A movable piece that stops the flow
        # is not a barrier, and mistaking one for a barrier is worse than missing a
        # barrier: the propagator checks barriers first, so the flow is predicted to
        # die where the engine splits it around the piece.
        pieces = self._all_piece_cells() | set(anim.piece_cells)
        size = int(round(len(self._prev_cells) ** 0.5))

        out: set[Cell] = set()
        for (r, c) in trail:
            ahead = (r + dr, c + dc)
            if not (0 <= ahead[0] < size and 0 <= ahead[1] < size):
                continue
            if ahead in trail or ahead in sinks or ahead in pieces:
                continue
            out.add(ahead)
        if not out:
            return UNKNOWN
        return Grounded(tuple(sorted(out)), "high")

    def board(self) -> Any:
        """Assemble the measured entity geometry into the propagator's board — the
        input the verifier judges a response table against. Every field is a
        grounded measurement; nothing here is read from an appearance constant."""
        pieces = self.pieces()
        sinks = self.sink_candidates()
        emitters = self.emitters()
        barriers = self.barriers()
        direction = self.initial_direction()
        emergences = self.emergences()
        if UNKNOWN in (pieces, sinks, emitters, barriers, direction) or self._prev_cells is None:
            return UNKNOWN
        from admorphiq.hypothesis_select.propagate_flow import Board

        size = int(round(len(self._prev_cells) ** 0.5))
        return Grounded(
            Board(
                pieces=tuple(frozenset(cells) for _, cells in pieces.value),
                sinks=tuple(frozenset(cells) for _, cells in sinks.value),
                hazard_cells=frozenset(barriers.value),
                emitter_cells=(frozenset() if self.embedded_sources() is UNKNOWN
                               else frozenset(self.embedded_sources().value)),
                # An observed flow cell belongs to the layout it was seen under: once a
                # plan moves the piece that CARRIES the source, seeding the old cell
                # starts the whole spill in the wrong place. Seed from the source when
                # one is known, and fall back to the sighting when none is.
                standing_flow=(frozenset(emitters.value)
                               if self.embedded_sources() is UNKNOWN else frozenset()),
                size=size,
                direction=direction.value,
                emergences=() if emergences is UNKNOWN else emergences.value,
                absorber_cells=self.absorbers(),
                falling_sources=(() if self.falling_sources() is UNKNOWN
                                 else self.falling_sources().value),
            ),
            "high",
        )

    def embedded_sources(self) -> Any:
        """Sources carried INSIDE a piece: cells within a piece that do not wear that
        piece's appearance.

        Measured on idx3. The first stream was thought to start at a fixed board cell
        because five probe layouts left one piece where it was — (8,4) every time. Once
        a plan actually moved that piece the spill began at (11,3), and (10,3) is a
        cell of the moved piece rendered in its own colour. The source travels WITH the
        piece, and the flow starts in the cell just past it.

        This is the same cell :meth:`_bridge` absorbs so the flow cannot walk through
        the middle of a bar. Naming it here is what lets the model put the stream in
        the right place for a layout it has never seen."""
        inventory = self.pieces()
        if inventory is UNKNOWN or self._prev_cells is None:
            return UNKNOWN
        cells = self._prev_cells
        out: list[Cell] = []
        for _, piece in inventory.value:
            worn = Counter(cells[c] for c in piece if c in cells)
            if len(worn) < 2:
                continue
            majority = worn.most_common(1)[0][0]
            out.extend(c for c in piece if c in cells and cells[c] != majority)
        if not out:
            return UNKNOWN
        return Grounded(tuple(sorted(out)), "high")

    def falling_sources(self) -> Any:
        """Falling streams as (lane, tick, line): the column a source pours down, the
        step at which it starts on the PROGRESS axis the replay uses, and the ROW the
        stream was seen to start on.

        The row matters because the source is a fixed CELL, not an opening at the top of
        the board. Measured on two captured boards of the same level: with the covering
        piece one row lower the stream appears at (3,5) and (3,6) — the source cells
        themselves — and with a piece standing ON them it appears at (3,3), beside the
        piece, and never above it. A model that drops the stream from the board's edge
        puts flow a row higher than the engine ever does.

        The lane is the invariant (see :meth:`falling_columns`); the tick is needed
        because these streams are SEQUENCED — idx3's second and third start six steps
        into a spill whose first stream is still falling."""
        columns = self.falling_columns()
        if columns is UNKNOWN:
            return UNKNOWN
        direction = self.initial_direction()
        dr, dc = direction.value
        anim = self._animations[-1]
        blocking = set(anim.piece_cells) | self._all_piece_cells()
        wanted = set(columns.value)
        seen: set[Cell] = set()
        out: list[tuple[int, int]] = []
        found: set[int] = set()
        tick = -1
        for layer in anim.frontier:
            if not layer:
                continue
            tick += 1
            for (r, c) in layer:
                lane = c if dr else r
                if lane not in wanted or lane in found:
                    continue
                behind = (r - dr, c - dc)
                flanks = ((r - dc, c - dr), (r + dc, c + dr))
                if behind in seen or any(f in seen for f in flanks):
                    continue
                if (r + dr, c + dc) not in blocking:
                    continue
                out.append((lane, tick, r if dr else c))
                found.add(lane)
            seen |= set(layer)
        if not out:
            return UNKNOWN
        return Grounded(tuple(sorted(out)), "high")

    def falling_columns(self) -> Any:
        """Columns a source pours down from off the board's top.

        Measured on idx3 across four layouts: a second stream starts partway through
        the spill, and where it becomes visible tracks whatever is beneath it — piece
        at row 4 gives entries at (3,5) and (3,6), piece at row 5 gives (4,5) and
        (4,6), always the cell directly ABOVE the obstacle and always in the same two
        columns. Moving that piece out of those columns removes the stream from those
        rows entirely.

        So the invariant is the COLUMN, not the cell: what the harness had been
        recording as an emergence was the point where a falling stream came to rest on
        something. A column is reported when a cell appears in it with no flow behind
        or beside it AND the cell directly ahead is occupied — the signature of a
        stream landing. That is derivable for a layout never observed, which is what
        planning needs and what an emergence could never give."""
        if not self._animations:
            return UNKNOWN
        direction = self.initial_direction()
        if direction is UNKNOWN:
            return UNKNOWN
        dr, dc = direction.value
        anim = self._animations[-1]
        blocking = set(anim.piece_cells) | self._all_piece_cells()
        seen: set[Cell] = set()
        out: set[int] = set()
        for layer in anim.frontier:
            for (r, c) in layer:
                behind = (r - dr, c - dc)
                flanks = ((r - dc, c - dr), (r + dc, c + dr))
                landed = (r + dr, c + dc) in blocking
                if behind in seen or any(f in seen for f in flanks) or not landed:
                    continue
                out.add(c if dr else r)
            seen |= set(layer)
        if not out:
            return UNKNOWN
        return Grounded(tuple(sorted(out)), "high")

    def absorbers(self) -> frozenset[Cell]:
        """Regions that swallow the flow without the objective counting them.

        Measured on idx3: a solid block wearing the target appearance is satisfied by
        the ENGINE — it recolours when the spill reaches it — while no candidate table
        has a rule that ever satisfies a region with no notch to be flanked at. So it
        cannot be offered as a target, and it is not a hazard either: contact is not
        fatal. Left out of the board entirely, our flow ran straight through what the
        engine's flow ended at, and the forecast claimed a downstream target the engine
        never filled.

        Named exactly like the weak target source, minus the notch: a region wearing
        the appearance every named target agrees on. Boards without such a region —
        every earlier level — get an empty set and are unaffected."""
        sinks = self.sink_candidates()
        if sinks is UNKNOWN or self._prev_cells is None:
            return frozenset()
        cells = self._prev_cells
        colours = {cells[c] for _, group in sinks.value for c in group if c in cells}
        if len(colours) != 1:
            return frozenset()
        colour = colours.pop()
        named = [frozenset(group) for _, group in sinks.value]
        pieces = self._all_piece_cells()
        out: set[Cell] = set()
        for region in _regions(cells, colour):
            for part in self._by_mouth(region):
                if part & pieces or any(part & known for known in named):
                    continue
                if not self._mouths(part):
                    out |= part
        return frozenset(out)

    def sink_candidates(self) -> Any:
        """The shortlist the model binds target roles from. A shortlist, never a
        decision — which of these IS a target is the model's choice.

        Two independent sources, because a target that was never satisfied still
        has to be nameable:

        * regions that took on a STABLE new appearance while a spill ran — the
          satisfied-target signal;
        * regions that repeat a named target's shape, or — when every named target
          agrees on one appearance — simply wear it;
        * regions the flow was OBSTRUCTED by. Wherever the flow spread sideways,
          something blocked the cell ahead; excluding the known movable pieces,
          what remains is a target. This is what lets a board be grounded when the
          probing spill happens to satisfy nothing.
        """
        if not self._animations:
            return UNKNOWN
        groups: list[frozenset[Cell]] = []
        for anim in self._animations:
            for g in anim.changed_regions:
                if g not in groups:
                    groups.append(g)
        for g in self._obstruction_regions():
            if not any(g & known for known in groups):
                groups.append(g)
        for g in self._matching_shape_regions(groups):
            if not any(g & known for known in groups):
                groups.append(g)
        for g in self._appearance_regions(groups):
            if not any(g & known for known in groups):
                groups.append(g)
        if not groups:
            return UNKNOWN
        split: list[frozenset[Cell]] = []
        for group in groups:
            split.extend(self._by_mouth(group))
        return Grounded(
            tuple((f"sink_{i}", tuple(sorted(g))) for i, g in enumerate(sorted(split, key=min))),
            "high",
        )

    def _by_mouth(self, region: frozenset[Cell]) -> list[frozenset[Cell]]:
        """Split a run of adjacent targets into one target per MOUTH.

        Targets standing side by side merge into a single region under
        4-connectivity, exactly as touching pieces do — and a single merged target
        makes "satisfy every target" mean "satisfy the one blob", which a plan can
        do while the level stays unfinished.

        The family's own satisfaction rule individuates them: a target is satisfied
        when the flow occupies the notch in its edge, the cell whose two flanking
        neighbours belong to that same target. Each such notch is therefore one
        target, and the region's cells are attributed to the nearest one. A region
        with no notch, or with one, is returned unchanged."""
        if self._prev_cells is None or len(region) < 2:
            return [region]
        mouths = self._mouths(region)
        if len(mouths) < 2:
            return [region]
        buckets: dict[Cell, set[Cell]] = {m: set() for m in mouths}
        for cell in region:
            nearest = min(mouths, key=lambda m: (abs(m[1] - cell[1]), abs(m[0] - cell[0])))
            buckets[nearest].add(cell)
        return [frozenset(v) for v in buckets.values() if v]

    def _mouths(self, region: frozenset[Cell]) -> list[Cell]:
        """The region's notches: cells it does NOT contain whose two flanking
        neighbours it does. This family's satisfaction runs through one, so a region
        without any cannot be a target of this kind."""
        return [
            (r, c)
            for r in {row for row, _ in region}
            for c in range(
                min(x for y, x in region if y == r), max(x for y, x in region if y == r) + 1
            )
            if (r, c) not in region and (r, c - 1) in region and (r, c + 1) in region
        ]

    def placement_evidence(self) -> Any:
        """Blocked placements, admitted ONLY from a contrast: the same action was
        confirmed to displace the piece elsewhere and produced no displacement
        here. Bare no-ops are reported separately and never become constraints."""
        if not self.detected():
            return UNKNOWN
        established = tuple(
            (action, tuple(sorted(cells)))
            for action, cells in self._blocked
            if action in self._delta_obs
        )
        return Grounded(
            {
                "blocked_contrasts": established,
                "unattributed_noops": self._unattributed_noops,
            },
            "high" if established else "low",
        )


__all__ = [
    "UNKNOWN",
    "Grounded",
    "FlowGrounding",
    "MIN_CONFIRMATIONS",
]
