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
from dataclasses import dataclass, field
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
                self._animations.append(anim)

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
        """One colour's single region moved rigidly, and the change set is EXACTLY
        the symmetric difference of its before/after footprints. Anything else
        having changed too means this was not a clean move."""
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
            self._delta_obs[action][delta] += 1
            self._moving_colour = colour
            self._piece = a[0]
            return True
        return False

    def _absorb_selection(
        self, before: dict[Cell, int], changed: set[Cell], after: dict[Cell, int]
    ) -> bool:
        """A region took on a new appearance IN PLACE. The region that LEFT the
        selected appearance in the same transition is the previously selected
        piece, and the appearance it dropped to is the IDLE one shared by every
        piece — one event, the whole inventory."""
        for colour in {after[c] for c in changed if c in after}:
            for r in _regions(after, colour):
                if not (r <= changed) or any(before[c] == colour for c in r):
                    continue
                if len({before[c] for c in r}) != 1:
                    continue
                if self._selected_colour is not None:
                    released = {
                        c for c in changed
                        if before[c] == self._selected_colour
                        and after.get(c) != self._selected_colour
                    }
                    dropped = {after[c] for c in released if c in after}
                    if len(dropped) == 1:
                        self._idle_colour = dropped.pop()
                self._selected_colour = colour
                self._piece = r
                self._selection_obs += 1
                return True
        return False

    # ── queries ──────────────────────────────────────────────────────────

    def detected(self) -> bool:
        """True once an action has been seen to expose a multi-layer consequence —
        the family's observable tell. Every query below is UNKNOWN until then, so
        a non-flow board never activates these paths."""
        return bool(self._commit_obs)

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
        commit. The family-specific claims below stay gated."""
        if self._piece is None or not self._delta_obs:
            return UNKNOWN
        return Grounded(tuple(sorted(self._piece)), "high")

    def pieces(self) -> Any:
        """Every movable piece on the board.

        Read off the CURRENT board rather than from a remembered region, because a
        failed attempt re-selects a piece of the engine's choosing — so which one
        wears the selected appearance is not something the harness may assume. With
        one piece this is just the tracked region; once a selection event has
        revealed the IDLE appearance, it is every region wearing either appearance.
        Two touching pieces still segment correctly, because the selected one is
        always separated by its own appearance."""
        if not self.detected() or self._piece is None or self._prev_cells is None:
            return UNKNOWN
        found: list[frozenset[Cell]] = []
        for colour in (self._selected_colour, self._idle_colour, self._moving_colour):
            if colour is None:
                continue
            for region in _regions(self._prev_cells, colour):
                if region not in found:
                    found.append(region)
        if not found:
            found = [frozenset(self._piece)]
        ordered = sorted(found, key=min)
        return Grounded(
            tuple((f"piece_{i}", tuple(sorted(r))) for i, r in enumerate(ordered)), "high"
        )

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
        pieces = set(self._piece or ())
        if self._idle_colour is not None:
            for region in _regions(cells, self._idle_colour):
                pieces |= set(region)

        signatures: set[tuple[int, frozenset[Cell]]] = set()
        for region in known:
            colours = {cells[c] for c in region if c in cells}
            if len(colours) != 1:
                continue
            signatures.add((colours.pop(), _normalised(region)))

        out: list[frozenset[Cell]] = []
        for colour, shape in signatures:
            for region in _regions(cells, colour):
                if region & pieces or any(region & k for k in known):
                    continue
                if _normalised(region) == shape:
                    out.append(region)
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
        pieces = set(self._piece or ())
        if self._idle_colour is not None:
            for region in _regions(self._prev_cells, self._idle_colour):
                pieces |= set(region)

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
        piece = self._piece or frozenset()
        size = int(round(len(self._prev_cells) ** 0.5))

        out: set[Cell] = set()
        for (r, c) in trail:
            ahead = (r + dr, c + dc)
            if not (0 <= ahead[0] < size and 0 <= ahead[1] < size):
                continue
            if ahead in trail or ahead in sinks or ahead in piece:
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
        if UNKNOWN in (pieces, sinks, emitters, barriers, direction) or self._prev_cells is None:
            return UNKNOWN
        from admorphiq.hypothesis_select.propagate_flow import Board

        size = int(round(len(self._prev_cells) ** 0.5))
        return Grounded(
            Board(
                pieces=tuple(frozenset(cells) for _, cells in pieces.value),
                sinks=tuple(frozenset(cells) for _, cells in sinks.value),
                hazard_cells=frozenset(barriers.value),
                emitter_cells=frozenset(),
                standing_flow=frozenset(emitters.value),
                size=size,
                direction=direction.value,
            ),
            "high",
        )

    def sink_candidates(self) -> Any:
        """The shortlist the model binds target roles from. A shortlist, never a
        decision — which of these IS a target is the model's choice.

        Two independent sources, because a target that was never satisfied still
        has to be nameable:

        * regions that took on a STABLE new appearance while a spill ran — the
          satisfied-target signal;
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
        if not groups:
            return UNKNOWN
        return Grounded(
            tuple((f"sink_{i}", tuple(sorted(g))) for i, g in enumerate(sorted(groups, key=min))),
            "high",
        )

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
