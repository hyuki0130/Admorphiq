"""Pure shortest-path / configuration-path kernels ("shortest_path /
configuration_path", R56).

Generic search the LLM (or a quarantined public-game adapter script) composes
by supplying a passability grid, an observed transition store, or an
arbitrary caller-defined state space — no game semantics, no player/item
interpretation, no goal inference, no autonomous frontier ownership. This is
the reusable BFS machinery behind two solver families:

- :mod:`admorphiq.tools.graph_search` — an explicit graph over frame states
  with a "nearest state with an untried action" frontier search
  (:func:`transition_shortest_path` / :func:`reachable_frontier` generalise
  its BFS-over-observed-edges core; the salience-ordered click policy,
  novelty ownership, automatic tier unlocking, and goal-ranking stay out).
- :mod:`admorphiq.delivery` — grid BFS navigation plus a measured
  action-delta map converting a waypoint path to action ids
  (:func:`grid_shortest_path` / :func:`path_to_moves` generalise its
  ``bfs_path`` / ``path_to_actions``; the item/target/player interpretation,
  pickup/carry/drop policy, and carried-item offset collision rule stay out).

Stdlib only — no numpy. These kernels must run inside the sandboxed REPL
where only the standard library and explicitly provided modules exist.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Hashable, Iterable, Sequence

Cell = tuple[int, int]
_CARDINAL: tuple[Cell, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _grid_dims(passable: Sequence[Sequence[object]]) -> tuple[int, int]:
    if not passable or not passable[0]:
        return (0, 0)
    return (len(passable), len(passable[0]))


def _in_bounds(cell: Cell, h: int, w: int) -> bool:
    r, c = cell
    return 0 <= r < h and 0 <= c < w


def _is_passable(passable: Sequence[Sequence[object]], cell: Cell) -> bool:
    r, c = cell
    return bool(passable[r][c])


def grid_shortest_path(
    passable: Sequence[Sequence[object]],
    start: Cell,
    goal: Cell,
    moves: Sequence[Cell] = _CARDINAL,
) -> list[Cell] | None:
    """Shortest ``start`` -> ``goal`` path over a 2D passability grid via BFS.

    ``passable`` is a rectangular grid of truthy/falsy values (True/1 =
    walkable). ``moves`` is the ordered set of ``(dr, dc)`` steps tried at
    each cell, tried in that order — the deterministic tie-break among
    equal-length paths. Returns the list of ``(row, col)`` cells INCLUDING
    both ``start`` and ``goal``, or ``None`` when unreachable. ``start ==
    goal`` returns ``[start]`` without checking passability of anything else.
    An out-of-bounds or impassable ``start``/``goal`` returns ``None`` (a
    ``start == goal`` shortcut is checked first, so a single impassable cell
    used as both endpoints still returns that one-cell path — the caller
    already occupies it, mirroring :func:`admorphiq.delivery.bfs_path`'s
    "start is never blocked against itself" rule).
    """
    if start == goal:
        return [start]
    h, w = _grid_dims(passable)
    if not _in_bounds(start, h, w) or not _in_bounds(goal, h, w):
        return None
    if not _is_passable(passable, start) or not _is_passable(passable, goal):
        return None
    visited = {start}
    queue: deque[tuple[Cell, list[Cell]]] = deque([(start, [start])])
    while queue:
        pos, path = queue.popleft()
        for dr, dc in moves:
            nxt = (pos[0] + dr, pos[1] + dc)
            if nxt in visited or not _in_bounds(nxt, h, w) or not _is_passable(passable, nxt):
                continue
            if nxt == goal:
                return path + [nxt]
            visited.add(nxt)
            queue.append((nxt, path + [nxt]))
    return None


def grid_distance_field(
    passable: Sequence[Sequence[object]],
    sources: Iterable[Cell],
    moves: Sequence[Cell] = _CARDINAL,
) -> dict[Cell, int]:
    """Multi-source BFS distance (in steps) from the nearest of ``sources``.

    Returns ``{cell: distance}`` for every passable cell reachable from any
    source, with distance ``0`` at the sources themselves (a source cell
    that is itself impassable, or out of bounds, is silently skipped — it
    cannot seed a walkable field). Cells unreachable from any source are
    absent from the result.
    """
    h, w = _grid_dims(passable)
    dist: dict[Cell, int] = {}
    queue: deque[Cell] = deque()
    for s in sources:
        if s in dist or not _in_bounds(s, h, w) or not _is_passable(passable, s):
            continue
        dist[s] = 0
        queue.append(s)
    while queue:
        pos = queue.popleft()
        d = dist[pos]
        for dr, dc in moves:
            nxt = (pos[0] + dr, pos[1] + dc)
            if nxt in dist or not _in_bounds(nxt, h, w) or not _is_passable(passable, nxt):
                continue
            dist[nxt] = d + 1
            queue.append(nxt)
    return dist


def transition_shortest_path(
    transitions: Iterable[tuple[Hashable, Hashable, Hashable]],
    start_key: Hashable,
    goal_key: Hashable,
) -> list[Hashable] | None:
    """Shortest sequence of edge labels from ``start_key`` to ``goal_key``.

    ``transitions`` is an iterable of observed ``(state_key, label,
    next_state_key)`` triples (as recorded by, e.g., a state-graph tool).
    The induced directed graph is built by folding transitions in iteration
    order — when a ``(state_key, label)`` pair is repeated with a different
    ``next_state_key``, the LAST-seen edge wins (matching an observed-store
    caller that overwrites a stale resolution). BFS over that graph tries a
    state's outgoing edges in the order they were first inserted, which is
    the deterministic tie-break among equal-length paths. Returns the list
    of edge labels (not states), or ``None`` when unreachable. ``start_key
    == goal_key`` returns ``[]`` (zero edges needed).
    """
    if start_key == goal_key:
        return []
    edges: dict[Hashable, dict[Hashable, Hashable]] = {}
    for state, label, nxt in transitions:
        edges.setdefault(state, {})[label] = nxt
    visited = {start_key}
    queue: deque[tuple[Hashable, list[Hashable]]] = deque([(start_key, [])])
    while queue:
        state, labels = queue.popleft()
        for label, nxt in edges.get(state, {}).items():
            if nxt in visited:
                continue
            if nxt == goal_key:
                return labels + [label]
            visited.add(nxt)
            queue.append((nxt, labels + [label]))
    return None


def reachable_frontier(
    transitions: Iterable[tuple[Hashable, Hashable, Hashable]],
    start_key: Hashable,
    tried: Iterable[tuple[Hashable, Hashable]],
) -> list[tuple[Hashable, Hashable]]:
    """``(state_key, label)`` pairs reachable from ``start_key`` not in ``tried``.

    ``transitions`` and edge construction follow :func:`transition_shortest_path`.
    The CALLER decides what counts as "tried" (a set of ``(state, label)``
    pairs) — this kernel owns no novelty tracking of its own. Results are
    ordered by BFS distance from ``start_key`` (nearest first), then by the
    order edges were first inserted at each state — the graph-search "nearest
    known state with an untried option" query, generalised: the caller
    supplies the frame/action semantics of ``tried``, the kernel only walks
    the graph. ``start_key`` itself is included in the search (a pair at
    distance 0 is reachable).
    """
    edges: dict[Hashable, dict[Hashable, Hashable]] = {}
    for state, label, nxt in transitions:
        edges.setdefault(state, {})[label] = nxt
    tried_set = set(tried)
    visited = {start_key}
    queue: deque[Hashable] = deque([start_key])
    out: list[tuple[Hashable, Hashable]] = []
    while queue:
        state = queue.popleft()
        for label, nxt in edges.get(state, {}).items():
            if (state, label) not in tried_set:
                out.append((state, label))
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return out


def configuration_path(
    initial: Hashable,
    goal_test: Callable[[Hashable], bool],
    successors: Callable[[Hashable], Iterable[tuple[Hashable, Hashable]]],
    max_states: int = 100_000,
) -> list[Hashable] | None:
    """Generic BFS over a caller-supplied state space.

    ``initial`` is a hashable state. ``goal_test(state) -> bool`` and
    ``successors(state) -> iterable of (step_label, next_state)`` must be
    DETERMINISTIC (same input always yields the same output/ordering) —
    non-determinism would make the "shortest, first-found" path meaningless
    and could make results non-reproducible across identical calls. This is
    the delivery-class configuration-space search with all state semantics
    (player/item positions, carry offsets, collision rules) fully
    externalized: the caller's ``successors`` closure encodes whatever state
    representation and legal-move rules the puzzle needs.

    Returns the list of step labels from ``initial`` to a goal state (``[]``
    when ``initial`` already satisfies ``goal_test``), or ``None`` when no
    goal is found within ``max_states`` expanded states (a bound, not a
    guarantee of unreachability — see the ``max_states`` termination note).
    """
    if goal_test(initial):
        return []
    visited = {initial}
    queue: deque[tuple[Hashable, list[Hashable]]] = deque([(initial, [])])
    expanded = 0
    while queue and expanded < max_states:
        state, labels = queue.popleft()
        expanded += 1
        for label, nxt in successors(state):
            if nxt in visited:
                continue
            path = labels + [label]
            if goal_test(nxt):
                return path
            visited.add(nxt)
            queue.append((nxt, path))
    return None


def path_to_moves(
    path: Sequence[Cell], move_labels: dict[Cell, Hashable]
) -> list[Hashable]:
    """Convert consecutive waypoint deltas in ``path`` into ``move_labels``.

    ``move_labels`` is a caller-supplied map from ``(dr, dc)`` (or ``(dx,
    dy)`` — whatever delta convention ``path`` uses) to a move label (e.g. a
    measured action id), mirroring
    :func:`admorphiq.delivery.path_to_actions`'s "never assumed, always
    measured" action map. Raises ``ValueError`` when a consecutive pair is
    not adjacent under any key in ``move_labels`` (either because the hop's
    delta was never observed during calibration, or because the two
    waypoints are not one step apart at all — both are caller errors, not
    silently-swallowed gaps). A path of length 0 or 1 returns ``[]``.
    """
    moves: list[Hashable] = []
    for (r0, c0), (r1, c1) in zip(path, path[1:]):
        delta = (r1 - r0, c1 - c0)
        if delta not in move_labels:
            raise ValueError(
                f"no move label for delta {delta} between {(r0, c0)} and {(r1, c1)}"
            )
        moves.append(move_labels[delta])
    return moves
