"""R33 goal spec + goal-proximity scoring + goal-directed planning.

The R32 forward model beat the state-uniqueness wall (planning fires on unseen
frames) but hit the GOAL-ABSENCE wall: scoring rollouts by predicted CHANGE /
NOVELTY is novelty-by-another-name, so it produced no gain. The missing piece
is a signal for WHICH change means "level solved".

R33 supplies that signal as a small, general, frame-computable STRUCTURED goal:

  * ``FILL_COLOR(color)``           — make MORE cells become colour C.
  * ``CLEAR_COLOR(color)``          — remove cells of colour C.
  * ``MOVE_TO_REGION(y, x, radius)``— move the movable object toward a region.
  * ``MAXIMIZE_OBJECT_COUNT(color)``— increase the count of colour-C blobs.
  * ``MINIMIZE_OBJECT_COUNT(color)``— decrease the count of colour-C blobs.
  * ``MATCH_SUBREGION(y, x, h, w, pattern)`` — make a region resemble a target.

:func:`score_goal` measures how CLOSE a frame is to satisfying the goal
(higher = closer). Goal-directed planning then rolls out candidate actions with
the forward model and picks the first action of the rollout whose PREDICTED
terminal frame scores highest under :func:`score_goal` — NOT under novelty.

Everything here is game-agnostic: it reads only the ``(64, 64)`` int
colour-index frame, never a game id / title / sprite tag.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

GRID = 64
NUM_COLORS = 16
# Background colour indices excluded from "movable object" reasoning. Colour 0
# is the canonical empty/background cell in the arcengine frames.
BACKGROUND_COLORS = (0,)


class GoalType(str, Enum):
    """The small, general set of level-completion goal shapes the agent supports.

    R33 seeded the fill / clear / move / count / match shapes. R46 adds two
    SEMANTIC-PROGRESS measures that remain purely frame-computable but capture
    the goal structure of the sort / sokoban / merge classes:

    * ``ORDER``     — sort-class: how monotone are same-colour components when
      ordered along an axis (SB26-style ordering puzzles).
    * ``ON_TARGET`` — pair-class: how close colour-A components sit to colour-B
      components (boxes-onto-targets sokoban, items-into-slots merge).
    """

    FILL_COLOR = "FILL_COLOR"
    CLEAR_COLOR = "CLEAR_COLOR"
    MOVE_TO_REGION = "MOVE_TO_REGION"
    MAXIMIZE_OBJECT_COUNT = "MAXIMIZE_OBJECT_COUNT"
    MINIMIZE_OBJECT_COUNT = "MINIMIZE_OBJECT_COUNT"
    MATCH_SUBREGION = "MATCH_SUBREGION"
    ORDER = "ORDER"
    ON_TARGET = "ON_TARGET"


@dataclass(frozen=True)
class GoalSpec:
    """A structured, frame-computable goal.

    Only the fields relevant to ``goal_type`` are used; the rest keep their
    defaults. ``color`` is a colour index in ``[0, 15]``; ``y``/``x`` are cell
    coordinates; ``radius`` is an L-infinity radius; ``pattern`` (for
    MATCH_SUBREGION) is an ``(h, w)`` int array of target colours.

    R46 fields: ``color_b`` is the second colour of an ON_TARGET pair goal (the
    "targets" that ``color`` components must reach); ``axis`` selects the ORDER
    ordering direction (0 = order components left-to-right by column, 1 = order
    top-to-bottom by row).
    """

    goal_type: GoalType
    color: int = 0
    y: int = 0
    x: int = 0
    radius: int = 0
    h: int = 0
    w: int = 0
    color_b: int = 0
    axis: int = 0
    pattern: np.ndarray | None = field(default=None, compare=False)


def _connected_component_count(frame: np.ndarray, color: int) -> int:
    """Count 4-connected blobs of ``color`` in the frame (BFS flood fill)."""
    mask = frame == color
    seen = np.zeros_like(mask, dtype=bool)
    count = 0
    h, w = mask.shape
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or seen[sy, sx]:
                continue
            count += 1
            q: deque[tuple[int, int]] = deque([(sy, sx)])
            seen[sy, sx] = True
            while q:
                cy, cx = q.popleft()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
    return count


def _movable_centroid(frame: np.ndarray, color: int | None) -> tuple[float, float] | None:
    """Centroid (y, x) of colour ``color`` cells, or of all non-background cells.

    When ``color`` is None the centroid of every non-background cell is used —
    a general "where is the stuff" estimate for MOVE_TO_REGION when the movable
    object colour is unknown.
    """
    if color is not None:
        ys, xs = np.where(frame == color)
    else:
        mask = ~np.isin(frame, BACKGROUND_COLORS)
        ys, xs = np.where(mask)
    if len(ys) == 0:
        return None
    return float(ys.mean()), float(xs.mean())


def _component_stats(frame: np.ndarray, color: int) -> list[tuple[int, float, float]]:
    """Return ``(size, cy, cx)`` for every 4-connected blob of ``color``.

    ``size`` is the cell count; ``cy``/``cx`` the centroid. Used by the R46
    ORDER and ON_TARGET measures, which reason over per-component geometry.
    """
    mask = frame == color
    seen = np.zeros_like(mask, dtype=bool)
    out: list[tuple[int, float, float]] = []
    h, w = mask.shape
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or seen[sy, sx]:
                continue
            q: deque[tuple[int, int]] = deque([(sy, sx)])
            seen[sy, sx] = True
            cells: list[tuple[int, int]] = []
            while q:
                cy, cx = q.popleft()
                cells.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            ys = sum(c[0] for c in cells) / len(cells)
            xs = sum(c[1] for c in cells) / len(cells)
            out.append((len(cells), ys, xs))
    return out


def _order_progress(frame: np.ndarray, color: int, axis: int) -> float:
    """Sort-class progress: monotone size-ordering of colour components (R46).

    Components of ``color`` (or all non-background components when ``color`` is
    0) are ordered along ``axis`` — axis 0 sorts left-to-right by column, axis 1
    top-to-bottom by row — then the number of adjacent-in-sequence pairs whose
    SIZES are monotone is counted. The measure returns the larger of the
    ascending and descending monotone-pair counts, so it rises toward EITHER a
    fully size-sorted arrangement (the game-agnostic proxy for "sorted"). With
    fewer than two components the frame carries no ordering, so 0.0 is returned.
    """
    if color != 0:
        comps = _component_stats(frame, color)
    else:
        comps = []
        for c in range(1, NUM_COLORS):
            if c in BACKGROUND_COLORS:
                continue
            comps.extend(_component_stats(frame, c))
    if len(comps) < 2:
        return 0.0
    key = 2 if axis == 0 else 1  # axis 0 => order by cx (col); axis 1 => cy (row)
    ordered = sorted(comps, key=lambda t: t[key])
    sizes = [t[0] for t in ordered]
    asc = sum(1 for a, b in zip(sizes, sizes[1:], strict=False) if a <= b)
    desc = sum(1 for a, b in zip(sizes, sizes[1:], strict=False) if a >= b)
    return float(max(asc, desc))


def _on_target_progress(frame: np.ndarray, color_a: int, color_b: int) -> float:
    """Pair-class progress: how close colour-A blobs sit to colour-B blobs (R46).

    For each colour-A component the L2 distance from its centroid to the nearest
    colour-B component centroid is measured; the measure returns the negated sum
    of those nearest distances (higher = A's sitting ON / adjacent to B's, the
    boxes-onto-targets sokoban and items-into-slots merge signature). When
    either colour is absent the pairing is undefined and the frame is scored
    maximally far so the ranker never prefers a state that lost a target.
    """
    a_comps = _component_stats(frame, color_a)
    b_comps = _component_stats(frame, color_b)
    if not a_comps or not b_comps:
        return -float(GRID * GRID)
    total = 0.0
    for _, ay, ax in a_comps:
        nearest = min(
            ((ay - by) ** 2 + (ax - bx) ** 2) ** 0.5 for _, by, bx in b_comps
        )
        total += nearest
    return -total


def score_goal(frame: np.ndarray, goal: GoalSpec) -> float:
    """Return a goal-proximity score for ``frame`` (higher = closer to the goal).

    The score is monotonic in "closeness" for each goal type so a planner can
    maximise it. It is NOT normalised across goal types (only relative values
    within one goal matter to the planner).

    * FILL_COLOR: +count of target-colour cells (more filled = higher).
    * CLEAR_COLOR: -count of target-colour cells (fewer remaining = higher).
    * MOVE_TO_REGION: negative L2 distance of the movable centroid to the
      region centre; +0 bonus once inside ``radius`` so being inside is best.
    * MAXIMIZE / MINIMIZE_OBJECT_COUNT: +count / -count of colour-C blobs.
    * MATCH_SUBREGION: +number of matching cells in the target subregion.
    * ORDER: +monotone size-ordering pairs of colour components along ``axis``.
    * ON_TARGET: -sum of nearest ``color``-to-``color_b`` component distances.
    """
    frame = np.asarray(frame)
    gt = goal.goal_type

    if gt is GoalType.FILL_COLOR:
        return float(np.count_nonzero(frame == goal.color))

    if gt is GoalType.CLEAR_COLOR:
        return -float(np.count_nonzero(frame == goal.color))

    if gt is GoalType.MOVE_TO_REGION:
        color = goal.color if goal.color != 0 else None
        centroid = _movable_centroid(frame, color)
        if centroid is None:
            return -float(GRID * GRID)  # nothing to move => maximally far
        cy, cx = centroid
        dist = ((cy - goal.y) ** 2 + (cx - goal.x) ** 2) ** 0.5
        inside_bonus = float(goal.radius) if dist <= goal.radius else 0.0
        return -dist + inside_bonus

    if gt is GoalType.MAXIMIZE_OBJECT_COUNT:
        return float(_connected_component_count(frame, goal.color))

    if gt is GoalType.MINIMIZE_OBJECT_COUNT:
        return -float(_connected_component_count(frame, goal.color))

    if gt is GoalType.MATCH_SUBREGION:
        if goal.pattern is None:
            return 0.0
        pat = np.asarray(goal.pattern)
        y0, x0 = goal.y, goal.x
        y1, x1 = min(GRID, y0 + pat.shape[0]), min(GRID, x0 + pat.shape[1])
        sub = frame[y0:y1, x0:x1]
        pat = pat[: sub.shape[0], : sub.shape[1]]
        return float(np.count_nonzero(sub == pat))

    if gt is GoalType.ORDER:
        return _order_progress(frame, goal.color, goal.axis)

    if gt is GoalType.ON_TARGET:
        return _on_target_progress(frame, goal.color, goal.color_b)

    raise ValueError(f"Unknown goal type: {gt!r}")


@dataclass(frozen=True)
class GoalPlanResult:
    """Outcome of one goal-directed planning call.

    ``action_idx`` is the chosen first action (None => planner declined, e.g.
    the forward model was below the confidence floor or no candidates were
    supplied). ``used_forward_model`` records whether the forward model
    actually drove the pick, so the caller can bump ``fwd_planned`` vs
    ``fwd_fallback`` counters. ``best_score`` is the predicted terminal
    goal-score of the winning rollout.
    """

    action_idx: int | None
    used_forward_model: bool
    best_score: float


def goal_directed_plan(
    frame_int: np.ndarray,
    goal: GoalSpec,
    candidate_actions: list[int],
    forward_model,
    horizon: int = 2,
    confidence_floor: float = 0.55,
) -> GoalPlanResult:
    """Roll out candidate actions H steps and pick the goal-maximising first move.

    For each candidate first action, the forward model predicts the resulting
    frame; from there a short greedy rollout (up to ``horizon`` steps, always
    re-picking the locally best candidate) estimates the terminal frame, which
    is scored by :func:`score_goal`. The first action of the best-scoring
    rollout is returned.

    The forward model's per-step confidence is tracked; if the FIRST-step
    prediction confidence is below ``confidence_floor`` for every candidate, the
    planner declines (``action_idx=None``, ``used_forward_model=False``) so the
    caller falls back to its novelty policy. This keeps planning ADDITIVE — it
    only overrides exploration when the model is confident enough to trust its
    rollout.

    Args:
        frame_int: current ``(64, 64)`` int colour-index frame.
        goal: the structured goal to approach.
        candidate_actions: combined action indices to consider as the first move.
        forward_model: object exposing
            ``predict_next_frame(frame_int, action_idx) -> (next_frame_int, confidence)``.
        horizon: rollout depth (number of predicted steps, >= 1).
        confidence_floor: minimum first-step confidence to trust the model.

    Returns:
        A :class:`GoalPlanResult`.
    """
    if not candidate_actions:
        return GoalPlanResult(action_idx=None, used_forward_model=False, best_score=float("-inf"))

    horizon = max(1, horizon)
    best_action: int | None = None
    best_score = float("-inf")
    any_confident = False

    for first in candidate_actions:
        cur, conf = forward_model.predict_next_frame(frame_int, first)
        if conf >= confidence_floor:
            any_confident = True
        # Greedy continuation for the remaining horizon steps.
        for _ in range(horizon - 1):
            step_best_frame = cur
            step_best_score = score_goal(cur, goal)
            for a in candidate_actions:
                nxt, _ = forward_model.predict_next_frame(cur, a)
                s = score_goal(nxt, goal)
                if s > step_best_score:
                    step_best_score = s
                    step_best_frame = nxt
            cur = step_best_frame
        terminal_score = score_goal(cur, goal)
        if terminal_score > best_score:
            best_score = terminal_score
            best_action = first

    if not any_confident:
        return GoalPlanResult(action_idx=None, used_forward_model=False, best_score=best_score)
    return GoalPlanResult(action_idx=best_action, used_forward_model=True, best_score=best_score)
