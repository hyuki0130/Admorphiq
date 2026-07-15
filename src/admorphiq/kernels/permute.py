"""Cyclic-permutation learning + assignment search ("permute", R56).

Generic machinery for **rotation / ring puzzles**: a game where pressing a
control cyclically rotates a fixed loop of board cells (every token on the
loop advances one cell), and the objective is to bring a set of *moving*
tokens onto a set of fixed goal cells. The LLM (or a quarantined public-game
adapter script) supplies the semantics — which frames pair to which control,
which regions are the moving tokens, which cells are the goals — and composes:

1. :func:`learn_cyclic_successor` — from ONE before/after frame pair for a
   single control, recover that control's permutation as a
   ``{cell: successor_cell}`` map. Ring cells are the small token regions that
   changed; a token that sat at ``c`` and now shows a different colour there is
   matched to the *nearest* changed cell that carries ``c``'s original colour
   afterwards. This is exact when adjacent ring cells differ in colour; where a
   few adjacent cells share a colour the swap is invisible, so the raw map is
   partial (see :func:`complete_cycle`).
2. :func:`complete_cycle` — close a partial successor map into a full cyclic
   permutation by joining each chain tail to the nearest chain head. A ring is
   a single closed loop, so the missing same-colour links are forced once the
   visible ones fix the order.
3. :func:`apply_successor` / :func:`plan_token_assignment` — simulate rotations
   on token positions and BFS a shortest control sequence that lands every
   moving token on a goal cell, within a press budget.

Stdlib only — no numpy. Must run inside the sandboxed REPL where only the
standard library and explicitly provided modules exist.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping, Sequence

Cell = tuple[int, int]


def _dist2(a: Cell, b: Cell) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _cyclic_order(cells: Sequence[Cell]) -> list[Cell]:
    """Order loop cells into a cyclic sequence via a nearest-neighbour tour.

    The cells of one rotation ring lie on a single closed loop where each cell's
    neighbours are its nearest peers, so a greedy nearest-unvisited walk from any
    start recovers the loop order (the last cell links back to the first). A
    straight-line ring is recovered end-to-end, with its wrap link closing the
    two endpoints — handled by modular indexing at the call site.
    """
    remaining = list(cells)
    order = [remaining.pop(0)]
    while remaining:
        last = order[-1]
        nxt = min(range(len(remaining)), key=lambda i: _dist2(last, remaining[i]))
        order.append(remaining.pop(nxt))
    return order


def _augment_ring_cells(order: list[Cell], candidates: Iterable[Cell]) -> list[Cell]:
    """Insert fully-unobserved ring cells into a tour by filling its gaps.

    A ring cell whose token shares a colour with BOTH neighbours never changes
    colour under a rotation, so it is absent from the diff and from ``order`` —
    leaving one oversized hop where it belongs. Its token region still exists on
    the frame, so for each hop far longer than the median we splice in the
    nearest candidate cell sitting at that gap's midpoint.
    """
    extra = [c for c in candidates if c not in set(order)]
    if not extra or len(order) < 3:
        return order
    hops = sorted(_dist2(order[i], order[(i + 1) % len(order)]) for i in range(len(order)))
    med = hops[len(hops) // 2] or 1
    out: list[Cell] = []
    avail = list(extra)
    for i in range(len(order)):
        a = order[i]
        b = order[(i + 1) % len(order)]
        out.append(a)
        if _dist2(a, b) > 2.25 * med and avail:
            mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            cand = min(avail, key=lambda c: (c[0] - mid[0]) ** 2 + (c[1] - mid[1]) ** 2)
            if (cand[0] - mid[0]) ** 2 + (cand[1] - mid[1]) ** 2 <= 1.5 * med:
                out.append(cand)
                avail.remove(cand)
    return out


def learn_cyclic_successor(
    before_regions: Sequence[Mapping[str, object]],
    after_regions: Sequence[Mapping[str, object]],
    changed_cells: Iterable[Cell],
    candidate_cells: Iterable[Cell] | None = None,
) -> dict[Cell, Cell]:
    """Recover one rotation control's ``{cell: successor}`` map from a single
    press, using pre-segmented token regions and the set of changed frame cells.

    Purpose: turn "I pressed a button and the board rearranged" into an explicit
    per-cell permutation the planner can simulate, WITHOUT reading any game
    internals — only region colours/centroids (from ``find_regions``) and a
    frame diff.

    Expected feedback: the returned map's keys are exactly the ring cells that
    visibly moved (a token whose cell changed colour); each maps to the nearest
    cell that afterwards carries the key's original colour. A clean rotation
    yields a near-bijection with a uniform small step; a returned map that is
    empty or wildly non-bijective signals the press did not rotate a ring (wrong
    control, or an inert click) — the caller should not plan on it.

    ``before_regions`` / ``after_regions`` are ``find_regions`` outputs (each a
    mapping with ``color``, ``cells`` and ``centroid``); ``changed_cells`` is the
    frame-diff cell set. Cells are ``(row, col)`` integer region centroids. Pass
    ``candidate_cells`` (all on-board token centroids) to recover ring cells that
    are FULLY unobserved — a token sharing a colour with both neighbours never
    changes, so it is spliced back in geometrically at the tour's oversized gap
    (without it a ring learns one cell short and a multi-step plan drifts off).
    """
    changed = {(int(r), int(c)) for (r, c) in changed_cells}

    def centroid(reg: Mapping[str, object]) -> Cell:
        cen = reg["centroid"]
        return (round(cen[0]), round(cen[1]))  # type: ignore[index]

    def touched(reg: Mapping[str, object]) -> bool:
        return any((int(y), int(x)) in changed for (y, x) in reg["cells"])  # type: ignore[union-attr]

    # A rotation permutes the OCCUPANTS of a fixed loop of cells: cell positions
    # are identical before and after, only their colours cycle. Only cells that
    # actually changed are on the rotated ring — restricting to them excludes
    # STATIC same-colour decoration (e.g. a fixed goal marker sharing the moving
    # token's colour) and cells of the OTHER rings.
    ring_cells = [centroid(r) for r in before_regions if touched(r)]
    if len(ring_cells) < 2:
        return {}
    before_color = {centroid(r): int(r["color"]) for r in before_regions if touched(r)}  # type: ignore[arg-type]
    after_color = {centroid(r): int(r["color"]) for r in after_regions if touched(r)}  # type: ignore[arg-type]

    # Order the ring's cells into their cyclic loop geometrically (a
    # nearest-neighbour tour — the cells lie on one closed loop, so consecutive
    # cells are mutually nearest). A single press rotates by one cell, so the
    # successor is a ±1 shift along this order; distance alone cannot say which
    # way (p->q and q->p are both short), so VOTE the global direction by colour
    # agreement: the true direction is the one where after_color[next] matches
    # before_color[cur] for the most cells. This yields one n-cycle by
    # construction — no spurious sub-cycles from local same-colour ambiguity.
    order = _cyclic_order(ring_cells)
    if candidate_cells is not None:
        order = _augment_ring_cells(order, candidate_cells)
    n = len(order)

    def agreement(step: int) -> int:
        # Only cells with observed colours vote; spliced-in invisible cells
        # (no colour entry) still receive a successor from the tour order.
        return sum(
            1
            for i in range(n)
            if order[i] in before_color
            and order[(i + step) % n] in after_color
            and after_color[order[(i + step) % n]] == before_color[order[i]]
        )

    step = 1 if agreement(1) >= agreement(-1) else -1
    return {order[i]: order[(i + step) % n] for i in range(n)}


def complete_cycle(succ: Mapping[Cell, Cell]) -> dict[Cell, Cell]:
    """Close a partial successor map into a full cyclic permutation.

    Purpose: a single press leaves a few links unobserved wherever two adjacent
    ring cells share a colour (the swap is invisible). Since a rotation ring is
    one closed loop, the observed links form chains whose gaps are forced: join
    each tail (a cell with no outgoing link) to the nearest head (a cell that is
    never a successor), which reconnects the loop.

    Expected feedback: returns a superset of ``succ`` where every cell that
    appears (as key or value) has exactly one successor. If ``succ`` is empty,
    returns an empty map. The completion is geometric (nearest tail→head); a
    map with many tails/heads far apart indicates the press mixed several rings
    and should not be trusted as a single cycle.
    """
    out = dict(succ)
    cells = set(out) | set(out.values())
    need_out = [c for c in cells if c not in out]  # cell with no successor yet
    incoming = set(out.values())
    need_in = [c for c in cells if c not in incoming]  # nothing maps into it
    # Join each successor-less cell to the nearest cell that lacks a predecessor,
    # so the observed chains close into one cycle (each target used once).
    free_in = list(need_in)
    for c in need_out:
        if not free_in:
            break
        nearest = min(free_in, key=lambda t: _dist2(c, t))
        out[c] = nearest
        free_in.remove(nearest)
    return out


def apply_successor(succ: Mapping[Cell, Cell], positions: Iterable[Cell]) -> tuple[Cell, ...]:
    """Advance every token one step along a rotation: ``pos -> succ[pos]`` (a
    token off this ring, i.e. not a key, stays put). Returns the new positions
    in sorted order so equal configurations share one canonical key."""
    return tuple(sorted(succ.get(p, p) for p in positions))


def plan_token_assignment(
    operators: Mapping[str, Mapping[Cell, Cell]],
    tokens: Iterable[Cell],
    goals: Iterable[Cell],
    *,
    labels: Iterable[object] | None = None,
    goal_labels: Iterable[object] | None = None,
    budget: int,
    max_states: int = 200_000,
) -> list[str] | None:
    """BFS a shortest sequence of rotation controls that lands every moving
    token on a goal cell.

    Purpose: the search half of a ring-puzzle solver. ``operators`` maps a
    control name (e.g. ``"A_R"``) to its ``{cell: successor}`` permutation;
    ``tokens`` are the moving tokens' current cells; ``goals`` are the target
    cells. By default tokens are interchangeable. Pass ``labels`` /
    ``goal_labels`` (parallel to ``tokens`` / ``goals``) to make the match
    CLASS-AWARE — a token only satisfies a goal of the same label — for a board
    with several distinct token/target kinds (e.g. two colour classes).

    Expected feedback: returns the shortest control-name list (length ≤
    ``budget``) reaching the goal assignment, or ``None`` if unreachable within
    the budget / ``max_states`` cap. ``None`` means the learned operators cannot
    compose to the goal — either the maps are wrong/incomplete or the budget is
    too small; the caller should fall back, not retry blindly.
    """
    toks = [(int(r), int(c)) for (r, c) in tokens]
    gls = [(int(r), int(c)) for (r, c) in goals]
    lab = list(labels) if labels is not None else [None] * len(toks)
    glab = list(goal_labels) if goal_labels is not None else [None] * len(gls)
    if len(toks) != len(gls) or len(lab) != len(toks) or len(glab) != len(gls):
        return None
    goal_set = frozenset(zip(glab, gls))
    start = tuple(sorted(zip(lab, toks), key=lambda p: (repr(p[0]), p[1])))

    def as_set(state: tuple) -> frozenset:
        return frozenset(state)

    if as_set(start) == goal_set:
        return []
    ops = {name: dict(mp) for name, mp in operators.items()}
    seen: set[tuple] = {start}
    q: deque[tuple[tuple, list[str]]] = deque([(start, [])])
    while q:
        state, path = q.popleft()
        if len(path) >= budget:
            continue
        for name, mp in ops.items():
            nxt = tuple(
                sorted(
                    ((lb, mp.get(pos, pos)) for lb, pos in state),
                    key=lambda p: (repr(p[0]), p[1]),
                )
            )
            if nxt in seen:
                continue
            if as_set(nxt) == goal_set:
                return [*path, name]
            seen.add(nxt)
            if len(seen) > max_states:
                return None
            q.append((nxt, [*path, name]))
    return None
