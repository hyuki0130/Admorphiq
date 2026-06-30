"""Select-and-place multi-entity ARRANGEMENT capability (R47).

The object-centric world-model agent's navigation goal model is *single player,
single target, one BFS path*. A whole class of ARC-AGI-3 levels instead poses a
**multi-entity arrangement** goal: several controllable pieces must each be moved
to a target configuration, and a SELECTION action (commonly ``ACTION5``) cycles
WHICH entity the move actions currently drive. AR25 level 2 is the measured
exemplar — a horizontally-movable centre "alignment bar" and a pair of shapes
that descend together; the level clears only when the bar sits at a specific
column AND the shapes reach the goal-marker row *simultaneously*. No single
moving player → the navigation planner mislabels one shape as the player,
navigates it into the bar, and never clears.

This module models that as a GENERAL capability, observation-driven and with no
game-id / game-title / game-internal reads, so it transfers to any
arrangement / sort game (it is the same primitive an SB26 / SU15-class sort
puzzle needs):

1. :func:`learn_selection_modes` — fold the agent's own sequenced probes into a
   per-mode ``action -> {color: (dx, dy)}`` translation map plus the discovered
   selection-toggle action. Nothing baked in.
2. :class:`ArrangementSim` — a cheap abstract simulator over
   ``(mode, {color: centroid})`` that the planner expands for free (no env
   steps): toggling cycles the mode, a move translates every entity its mode-map
   moves. This lets the planner search hundreds of configs without spending the
   action budget.
3. :func:`plan_descend_and_sweep` — because the WIN predicate is HIDDEN (the env
   is the only oracle), the planner cannot know the exact target config offline.
   It returns a two-stage plan: (a) descend the *vertically-controllable* primary
   group ONCE onto a goal-marker ROW, then (b) a SWEEP of the separately-
   controllable *alignment* entity's column (single steps, biased toward the
   marker side). The agent executes this live and the harness checks the level-up
   after every action, so the level clears the instant the alignment column is
   right — a bounded systematic search whose WINNING length (~human baseline)
   keeps the squared-efficiency score high.

The win-predicate-is-hidden design is deliberate: a frame-only heuristic for the
exact target config proved brittle (AR25 needs the bar at exactly -2 cells, not
derivable from the markers alone), whereas "descend the primary to the marker
row, then sweep the alignment column, let the env confirm" is robust and general.
The descend-once-then-sweep order is also lose-state-safe: moving the alignment
entity does not change the primary row, so no risky full re-descent / restore is
needed (measured on AR25: restoring the descent UP trips a game-over).
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field

import numpy as np

from .general_agent import connected_components

# ── Tunables ─────────────────────────────────────────────────────────────────

# A coloured component must be at least this large to count as an arrangement
# ENTITY (filters single-pixel selection-outline dots / anti-aliasing).
_MIN_ENTITY_SIZE = 10
# Rows at/below this are the bottom HUD / timer band on the measured games; an
# entity centroid there is a progress bar, not a movable piece.
_HUD_ROW_CUTOFF = 60
# A centroid must shift at least this many pixels under a probe to count as a
# real translation (mirrors general_agent._MIN_TRANSLATION_PX; sub-pixel drift
# is HUD creep, not a move).
_MIN_SHIFT_PX = 2.0
# Max selection modes to enumerate by repeated toggling. Two is the measured
# AR25 count; a small cap bounds the discovery cost on any game.
_MAX_MODES = 4
# Max BFS nodes the simulator expands per candidate search — bounds planning
# cost. The sim is pure arithmetic so this is cheap, but a cap guarantees
# termination on a game whose entities never reach the target row.
_SIM_MAX_NODES = 20000
# Row tolerance (px) for "the primary group reached the goal-marker row". The
# winning configs land within a cell of the marker centroid; one cell of slack
# absorbs centroid rounding without admitting far-off configs.
_ROW_TOL = 1


# ── entity / mode perception ───────────────────────────────────────────────────


def entity_centroids(layer: np.ndarray, background: int) -> dict[int, tuple[float, float, int]]:
    """Largest non-background component per colour as ``{color: (cx, cy, size)}``.

    Restricts to components at least :data:`_MIN_ENTITY_SIZE` and above the HUD
    band, so the returned dict is the set of plausible movable ARRANGEMENT
    entities (and static goal markers) — the abstract state the simulator tracks.
    Pure / env-free.
    """
    out: dict[int, tuple[float, float, int]] = {}
    for c in connected_components(layer, background):
        if c["size"] < _MIN_ENTITY_SIZE or c["cy"] >= _HUD_ROW_CUTOFF:
            continue
        if c["color"] not in out or c["size"] > out[c["color"]][2]:
            out[c["color"]] = (c["cx"], c["cy"], c["size"])
    return out


def _movers(before: np.ndarray, after: np.ndarray, background: int) -> dict[int, tuple[int, int]]:
    """Per-colour centroid shift ``(dx, dy)`` for entities that translated.

    Compares the largest component of each colour before/after. Only shifts of
    at least :data:`_MIN_SHIFT_PX` on some axis are kept (HUD creep filtered).
    Quantised to integer pixels — the simulator steps in these units.
    """
    if before.shape != after.shape:
        return {}
    cb = entity_centroids(before, background)
    ca = entity_centroids(after, background)
    out: dict[int, tuple[int, int]] = {}
    for col in set(cb) & set(ca):
        dx = ca[col][0] - cb[col][0]
        dy = ca[col][1] - cb[col][1]
        if abs(dx) >= _MIN_SHIFT_PX or abs(dy) >= _MIN_SHIFT_PX:
            out[col] = (int(round(dx)), int(round(dy)))
    return out


@dataclass
class SelectionModel:
    """Learned multi-entity selection + per-mode movement model for a level.

    ``mode_maps[mode][action_id]`` is the ``{color: (dx, dy)}`` translation that
    move action produces while selection ``mode`` is active. ``toggle_action`` is
    the action that cycles the mode (the discovered ``ACTION5``-class selector).
    ``num_modes`` is how many distinct modes the toggle cycles through.
    """

    toggle_action: int | None = None
    num_modes: int = 1
    mode_maps: dict[int, dict[int, tuple[int, int]]] = field(default_factory=dict)

    def vertically_controllable(self) -> set[int]:
        """Colours whose ROW can be changed in some mode (the primary group).

        These are the entities a goal-ROW navigation can drive; an entity that
        only ever moves horizontally (the AR25 alignment bar) is excluded.
        """
        out: set[int] = set()
        for mp in self.mode_maps.values():
            for mv in mp.values():
                for col, (_dx, dy) in mv.items():
                    if abs(dy) >= _MIN_SHIFT_PX:
                        out.add(col)
        return out

    def horizontally_controllable(self) -> set[int]:
        """Colours whose COLUMN can be changed in some mode (alignment candidates)."""
        out: set[int] = set()
        for mp in self.mode_maps.values():
            for mv in mp.values():
                for col, (dx, _dy) in mv.items():
                    if abs(dx) >= _MIN_SHIFT_PX:
                        out.add(col)
        return out

    def any_movement(self) -> bool:
        """True when at least one mode/action moves at least one entity."""
        return any(mv for mp in self.mode_maps.values() for mv in mp.values())


# ── abstract simulator ─────────────────────────────────────────────────────────


class ArrangementSim:
    """Cheap abstract simulator of the multi-entity arrangement dynamics.

    State is ``(mode, {color: (cx, cy)})``. A move action translates every
    entity its mode-map moves; the toggle action advances the mode cyclically.
    The planner expands this for free — no env steps — so a search over hundreds
    of configs costs no action budget. It models centroids only (occlusion /
    merging are ignored), which is sufficient to plan the gross arrangement; the
    real env confirms the WIN.
    """

    def __init__(self, model: SelectionModel) -> None:
        self.model = model

    def step(
        self, mode: int, cents: dict[int, tuple[float, float]], action: int
    ) -> tuple[int, dict[int, tuple[float, float]]]:
        """Apply ``action`` to ``(mode, cents)``; return the next ``(mode, cents)``."""
        if action == self.model.toggle_action and self.model.num_modes > 1:
            return (mode + 1) % self.model.num_modes, dict(cents)
        mv = self.model.mode_maps.get(mode, {}).get(action, {})
        if not mv:
            return mode, dict(cents)
        nc = dict(cents)
        for col, (dx, dy) in mv.items():
            if col in nc:
                nc[col] = (nc[col][0] + dx, nc[col][1] + dy)
        return mode, nc


# ── candidate planning (hidden-win-predicate systematic search) ─────────────────


def goal_marker_rows(
    layer: np.ndarray, background: int, exclude_colors: set[int]
) -> list[float]:
    """Rows of the static goal-marker clusters, rarest colour first.

    A goal marker is a non-background coloured cluster that is NOT one of the
    movable entities (``exclude_colors``). Each qualifying cluster contributes
    its centroid row; rows are ordered so the rarest marker colour's rows come
    first (rare markers are the likeliest targets, matching the navigation
    planner's rarest-colour goal heuristic). Pure / env-free.
    """
    comps = [
        c
        for c in connected_components(layer, background)
        if c["color"] not in exclude_colors
        and c["color"] != background
        and c["size"] >= _MIN_ENTITY_SIZE
        and c["cy"] < _HUD_ROW_CUTOFF
    ]
    if not comps:
        return []
    area: Counter[int] = Counter()
    for c in comps:
        area[c["color"]] += c["size"]
    comps.sort(key=lambda c: (area[c["color"]], -c["size"]))
    rows: list[float] = []
    seen: set[int] = set()
    for c in comps:
        r = round(c["cy"])
        if r not in seen:
            seen.add(r)
            rows.append(c["cy"])
    return rows


def _sign(v: float) -> int:
    """Sign of ``v`` as -1 / 0 / +1."""
    return (v > 0) - (v < 0)


def _goal_marker_col(
    layer: np.ndarray, background: int, exclude_colors: set[int]
) -> float | None:
    """Column of the rarest goal-marker cluster, or None.

    Mirrors :func:`goal_marker_rows`'s rarest-first selection but returns the
    single most-likely marker's centroid column, used to bias the alignment
    sweep toward the side the pieces line up to. Pure / env-free.
    """
    comps = [
        c
        for c in connected_components(layer, background)
        if c["color"] not in exclude_colors
        and c["color"] != background
        and c["size"] >= _MIN_ENTITY_SIZE
        and c["cy"] < _HUD_ROW_CUTOFF
    ]
    if not comps:
        return None
    area: Counter[int] = Counter()
    for c in comps:
        area[c["color"]] += c["size"]
    comps.sort(key=lambda c: (area[c["color"]], -c["size"]))
    return comps[0]["cx"]


def _bfs_primary_to_row(
    sim: ArrangementSim,
    start_mode: int,
    start_cents: dict[int, tuple[float, float]],
    primary: set[int],
    target_row: float,
    fixed: dict[int, tuple[float, float]] | None = None,
) -> list[int] | None:
    """Shortest action plan to bring every primary entity onto ``target_row``.

    ``fixed`` pins entities that must NOT move from a given centroid (the
    alignment entity held at a swept column) — any expansion that would shift a
    fixed entity off its pinned position is pruned, so the search composes "place
    the alignment entity, then navigate the primary group" without re-disturbing
    the alignment. Returns the action-id list, or None if unreachable within the
    node budget.
    """
    model = sim.model
    actions = sorted({a for mp in model.mode_maps.values() for a in mp})
    if model.toggle_action is not None:
        actions.append(model.toggle_action)
    fixed = fixed or {}
    fixed_round = {col: (round(pos[0]), round(pos[1])) for col, pos in fixed.items()}

    def reached(cents: dict[int, tuple[float, float]]) -> bool:
        rel = [c for c in primary if c in cents]
        return bool(rel) and all(abs(cents[c][1] - target_row) <= _ROW_TOL for c in rel)

    def key(mode: int, cents: dict[int, tuple[float, float]]) -> tuple:
        return (mode, tuple(sorted((c, round(v[0]), round(v[1])) for c, v in cents.items())))

    if reached(start_cents):
        return []
    visited = {key(start_mode, start_cents)}
    queue: deque[tuple[int, dict[int, tuple[float, float]], list[int]]] = deque(
        [(start_mode, start_cents, [])]
    )
    nodes = 0
    while queue and nodes < _SIM_MAX_NODES:
        mode, cents, path = queue.popleft()
        nodes += 1
        for a in actions:
            nmode, ncents = sim.step(mode, cents, a)
            if any(
                col in ncents and (round(ncents[col][0]), round(ncents[col][1])) != fr
                for col, fr in fixed_round.items()
            ):
                continue
            if reached(ncents):
                return path + [a]
            k = key(nmode, ncents)
            if k not in visited:
                visited.add(k)
                queue.append((nmode, ncents, path + [a]))
    return None


def plan_descend_and_sweep(
    layer: np.ndarray,
    background: int,
    model: SelectionModel,
    max_offset: int = 8,
) -> tuple[list[int] | None, list[list[int]]]:
    """Plan the two-stage arrangement: descend the primary group, then sweep.

    The WIN predicate is hidden (the env is the only oracle), but the measured
    structure is: the primary group must reach a goal-marker ROW *and* the
    alignment entity must sit at a specific COLUMN. The robust, lose-state-safe
    way to satisfy both without a risky full re-descent per offset is:

    1. **Descend ONCE** — bring the vertically-controllable primary group onto
       the rarest goal-marker's row (BFS in the free simulator from mode 0).
    2. **Sweep the alignment entity** — single alignment-entity steps (each a
       short list: toggle into the alignment mode + one alignment move), ordered
       outward and biased TOWARD the goal-marker column first. Because moving the
       alignment entity does NOT change the primary's row, the level clears the
       instant the alignment column is right — and the agent checks the live
       level-up after each sweep step, so no offset is over-committed.

    Returns ``(descend_plan, sweep_steps)``. ``descend_plan`` is None when there
    is no vertically-controllable primary or no goal marker (not an arrangement);
    ``sweep_steps`` is the ordered list of single-step alignment plans (empty
    when there is no separate alignment entity, i.e. the descend alone may win).
    All planning is in the free simulator — zero env steps.
    """
    sim = ArrangementSim(model)
    start = {col: (v[0], v[1]) for col, v in entity_centroids(layer, background).items()}
    primary = model.vertically_controllable()
    if not primary:
        return None, []
    horiz = model.horizontally_controllable()
    rows = goal_marker_rows(layer, background, exclude_colors=primary | horiz)
    if not rows:
        return None, []
    target_row = rows[0]  # rarest marker — the likeliest goal

    descend = _bfs_primary_to_row(sim, 0, start, primary, target_row)
    if descend is None:
        return None, []

    alignment = sorted(horiz - primary)  # alignment entities move only sideways
    align_color = alignment[0] if alignment else None
    if align_color is None:
        return descend, []

    # After the descend plan runs, the hardware selection sits in the mode
    # reached by the descend's toggles (each toggle in ``descend`` advances the
    # cyclic mode). The sweep's toggle-entry must be computed RELATIVE to that
    # post-descend mode, not mode 0, or it enters the wrong mode and the bar
    # never moves (every alignment step would no-op or move the primary instead).
    post_mode = (
        sum(1 for a in descend if a == model.toggle_action) % max(1, model.num_modes)
    )
    # Single-step alignment options (toggle into the alignment mode + one move),
    # one per sideways direction.
    step_options = _alignment_step_options(model, align_color, post_mode)
    if not step_options:
        return descend, []
    # Order so the step that shifts the alignment entity TOWARD the goal-marker
    # column comes first (the winning column is usually on the marker's side; a
    # wrong-side sweep wastes budget / risks a lose-state).
    marker_col = _goal_marker_col(layer, background, exclude_colors=primary | horiz)
    if marker_col is not None and align_color in start:
        toward = _sign(marker_col - start[align_color][0])
        step_options.sort(key=lambda o: 0 if _step_dir(model, o, align_color) == toward else 1)

    # Two continuous sweep plans, toward-marker side first. Each enters the
    # alignment mode ONCE then steps the alignment entity one cell at a time up
    # to ``max_offset`` cells; the agent checks the live level-up after EVERY
    # action, so it stops the instant the winning column is hit. The toward plan
    # is tried first; if it does not clear, the away plan sweeps the other side
    # (its first move first cancels the toward displacement, so it covers the
    # full opposite range).
    sweep: list[list[int]] = []
    for entry, move, _mode in step_options:
        sweep.append(entry + [move] * max_offset)
    return descend, sweep


def _alignment_step_options(
    model: SelectionModel, align_color: int, current_mode: int = 0
) -> list[tuple[list[int], int, int]]:
    """For each (mode, action) that moves ``align_color`` sideways: entry + move.

    Returns ``(entry, move, mode)`` where ``entry`` is the toggles needed to go
    from ``current_mode`` (the selection mode the agent is in NOW) to the mode
    that drives the alignment entity, and ``move`` is the alignment move within
    it. Both sideways directions are returned so the sweep reaches the alignment
    column on either side of the start.
    """
    n_modes = max(1, model.num_modes)
    options: list[tuple[list[int], int, int]] = []
    for mode, mp in model.mode_maps.items():
        for a, mv in mp.items():
            if align_color in mv and abs(mv[align_color][0]) >= _MIN_SHIFT_PX:
                steps = (mode - current_mode) % n_modes
                if steps != 0 and model.toggle_action is None:
                    continue
                entry = [model.toggle_action] * steps if steps else []
                options.append((entry, a, mode))
    return options


def _step_dir(
    model: SelectionModel, option: tuple[list[int], int, int], align_color: int
) -> int:
    """Sign of the alignment entity's column shift under one step of ``option``."""
    _entry, move, mode = option
    dx = model.mode_maps.get(mode, {}).get(move, {}).get(align_color, (0, 0))[0]
    return _sign(dx)


# ── online learning of the selection model (folds the agent's own probes) ──────


def learn_selection_modes(
    probe_log: list[dict], background: int, toggle_action: int
) -> SelectionModel:
    """Build a :class:`SelectionModel` from a sequenced probe log.

    ``probe_log`` is an ordered list of ``{"action", "before", "after"}`` the
    agent issued while sweeping the selection space: the toggle action between
    modes and each move action within a mode. The mode index advances every time
    the toggle action appears (cyclically, capped at :data:`_MAX_MODES`). Move
    probes are folded into the current mode's map. Pure / env-free so the agent's
    arrangement-probe schedule is unit-testable.
    """
    model = SelectionModel(toggle_action=toggle_action)
    mode = 0
    for entry in probe_log:
        a = entry["action"]
        if a == toggle_action:
            mode = (mode + 1) % _MAX_MODES
            continue
        mv = _movers(entry["before"], entry["after"], background)
        if mv:
            model.mode_maps.setdefault(mode, {})[a] = mv
    # The toggle cycles through exactly the modes that drive movement. Counting
    # modes by toggle COUNT over-counts (a wrap-around toggle revisits mode 0,
    # and modes with no movement map are dead) — derive ``num_modes`` from the
    # populated maps instead, so the simulator's mode cycle matches reality.
    populated = sorted(model.mode_maps)
    model.num_modes = (max(populated) + 1) if populated else 1
    return model
