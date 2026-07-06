"""Tests for R33 goal inference + goal-directed planning.

These pin the R33 contract that closes the goal-absence wall: a frame-computable
structured goal, a goal-proximity score that rises as a frame approaches each
goal, a planner that picks the action whose predicted rollout maximises that
score (NOT novelty), an LLM goal-inference path that parses stubbed JSON and
falls back to a heuristic on invalid input, and — critically — that the default
RL_GOAL_PLAN=0 leaves the online agent byte-identical to the pre-R33 novelty
agent. The forward model is stubbed so no CNN training or Ollama call happens.
"""

from __future__ import annotations

import numpy as np

from admorphiq.planner.goal import (
    GoalPlanResult,
    GoalSpec,
    GoalType,
    goal_directed_plan,
    score_goal,
)
from admorphiq.planner.goal_inference import (
    heuristic_goal,
    infer_goal,
    parse_goal_spec,
)

# ── score_goal monotonicity ──────────────────────────────────────────────────


def test_score_goal_fill_color_rises_with_more_target_cells() -> None:
    """Purpose: score_goal(FILL_COLOR) must increase as more cells become the
    target colour.

    Expected feedback: pass => the planner can climb "fill this colour" goals;
    fail => the proximity signal is inverted or flat and planning is directionless.
    """
    goal = GoalSpec(goal_type=GoalType.FILL_COLOR, color=3)
    empty = np.zeros((64, 64), dtype=np.int64)
    partial = empty.copy()
    partial[:10, :10] = 3
    full = np.full((64, 64), 3, dtype=np.int64)
    assert score_goal(empty, goal) < score_goal(partial, goal) < score_goal(full, goal)


def test_score_goal_clear_color_rises_as_target_removed() -> None:
    """Purpose: score_goal(CLEAR_COLOR) must increase as target-colour cells vanish.

    Expected feedback: pass => "remove this colour" goals are climbable; fail =>
    the sign is wrong and the planner would fill instead of clear.
    """
    goal = GoalSpec(goal_type=GoalType.CLEAR_COLOR, color=5)
    full = np.full((64, 64), 5, dtype=np.int64)
    partial = full.copy()
    partial[:32, :] = 0
    empty = np.zeros((64, 64), dtype=np.int64)
    assert score_goal(full, goal) < score_goal(partial, goal) < score_goal(empty, goal)


def test_score_goal_move_to_region_rises_as_object_approaches() -> None:
    """Purpose: score_goal(MOVE_TO_REGION) must increase as the movable object's
    centroid nears the target region.

    Expected feedback: pass => navigation-style goals are climbable; fail =>
    distance sign is wrong and the planner drives away from the target.
    """
    goal = GoalSpec(goal_type=GoalType.MOVE_TO_REGION, color=7, y=60, x=60, radius=3)
    far = np.zeros((64, 64), dtype=np.int64)
    far[0, 0] = 7
    near = np.zeros((64, 64), dtype=np.int64)
    near[58, 58] = 7
    assert score_goal(far, goal) < score_goal(near, goal)


def test_score_goal_object_count_goals_track_blob_count() -> None:
    """Purpose: MAXIMIZE/MINIMIZE_OBJECT_COUNT must track the connected-component
    count of the target colour with the correct sign.

    Expected feedback: pass => count-based goals steer toward more/fewer blobs;
    fail => the blob counter or its sign is broken.
    """
    one_blob = np.zeros((64, 64), dtype=np.int64)
    one_blob[0:2, 0:2] = 2
    two_blobs = one_blob.copy()
    two_blobs[10:12, 10:12] = 2
    gmax = GoalSpec(goal_type=GoalType.MAXIMIZE_OBJECT_COUNT, color=2)
    gmin = GoalSpec(goal_type=GoalType.MINIMIZE_OBJECT_COUNT, color=2)
    assert score_goal(two_blobs, gmax) > score_goal(one_blob, gmax)
    assert score_goal(two_blobs, gmin) < score_goal(one_blob, gmin)


def test_score_goal_match_subregion_rises_with_matching_cells() -> None:
    """Purpose: MATCH_SUBREGION must increase as the region matches the target pattern.

    Expected feedback: pass => pattern-matching goals are climbable; fail =>
    subregion indexing or the match count is wrong.
    """
    pattern = np.array([[1, 2], [3, 4]], dtype=np.int64)
    goal = GoalSpec(goal_type=GoalType.MATCH_SUBREGION, y=0, x=0, pattern=pattern)
    none = np.zeros((64, 64), dtype=np.int64)
    half = none.copy()
    half[0, 0] = 1
    half[0, 1] = 2
    full = none.copy()
    full[0:2, 0:2] = pattern
    assert score_goal(none, goal) < score_goal(half, goal) < score_goal(full, goal)


# ── goal-directed planning ───────────────────────────────────────────────────


class _StubForwardModel:
    """Deterministic forward model for planning tests (no CNN, no training).

    Each action index maps to a canned next frame + a fixed confidence, so the
    planner's pick is fully determined by score_goal over those frames.
    """

    def __init__(self, action_to_frame: dict[int, np.ndarray], confidence: float = 0.9) -> None:
        self._map = action_to_frame
        self._conf = confidence

    def predict_next_frame(self, frame_int, action_idx):  # noqa: ANN001
        nxt = self._map.get(action_idx, np.asarray(frame_int))
        return np.asarray(nxt), self._conf


def test_goal_directed_plan_picks_score_maximising_action() -> None:
    """Purpose: goal_directed_plan must return the first action whose predicted
    rollout maximises score_goal — the whole point of R33 (goal, not novelty).

    Expected feedback: pass => planning is goal-directed; fail => it picks by
    something other than goal proximity (the R32 novelty regression).
    """
    goal = GoalSpec(goal_type=GoalType.FILL_COLOR, color=3)
    frame = np.zeros((64, 64), dtype=np.int64)
    good = np.full((64, 64), 3, dtype=np.int64)   # action 1 fills colour 3
    meh = frame.copy()
    meh[:5, :5] = 3                                # action 2 fills a little
    fm = _StubForwardModel({1: good, 2: meh, 0: frame})
    result = goal_directed_plan(frame, goal, [0, 1, 2], fm, horizon=1)
    assert isinstance(result, GoalPlanResult)
    assert result.action_idx == 1
    assert result.used_forward_model is True


def test_goal_directed_plan_declines_when_model_unconfident() -> None:
    """Purpose: below the confidence floor, the planner must decline (None) so the
    caller falls back to novelty — planning is ADDITIVE, not a hard override.

    Expected feedback: pass => low-confidence rollouts don't hijack action
    selection; fail => the agent would trust a forward model it cannot trust.
    """
    goal = GoalSpec(goal_type=GoalType.FILL_COLOR, color=3)
    frame = np.zeros((64, 64), dtype=np.int64)
    fm = _StubForwardModel({0: frame, 1: frame}, confidence=0.10)
    result = goal_directed_plan(frame, goal, [0, 1], fm, horizon=1, confidence_floor=0.55)
    assert result.action_idx is None
    assert result.used_forward_model is False


def test_goal_directed_plan_empty_candidates_returns_none() -> None:
    """Purpose: no candidate actions => no plan (None), never a crash or index error.

    Expected feedback: pass => the empty-candidate boundary is handled; fail =>
    the planner raises when availability masking leaves nothing to try.
    """
    goal = GoalSpec(goal_type=GoalType.FILL_COLOR, color=3)
    frame = np.zeros((64, 64), dtype=np.int64)
    fm = _StubForwardModel({})
    result = goal_directed_plan(frame, goal, [], fm)
    assert result.action_idx is None


# ── goal inference: LLM stub parse + heuristic fallback ──────────────────────


def test_infer_goal_parses_stubbed_llm_json() -> None:
    """Purpose: a stubbed LLM returning valid JSON must parse into the matching GoalSpec.

    Expected feedback: pass => the discovery-time LLM hook round-trips JSON to a
    structured goal; fail => the parser or the injectable-callable wiring broke.
    """
    def stub_llm(_prompt: str) -> str:
        return '{"goal_type": "CLEAR_COLOR", "color": 4}'

    spec = infer_goal({0: 100, 4: 12}, [], llm_call=stub_llm)
    assert spec.goal_type is GoalType.CLEAR_COLOR
    assert spec.color == 4


def test_infer_goal_falls_back_to_heuristic_on_invalid_llm() -> None:
    """Purpose: invalid LLM output must trigger the deterministic heuristic, never
    return None or crash — the agent is never blocked on the LLM.

    Expected feedback: pass => malformed LLM JSON degrades gracefully to the
    probe-based heuristic; fail => a bad LLM response would stall goal inference.
    """
    def bad_llm(_prompt: str) -> str:
        return "sorry I cannot help with that"

    probes = [{"action": 6, "changed_cells": 20, "top_new_color": 5}]
    spec = infer_goal({0: 4090, 5: 6}, probes, llm_call=bad_llm)
    assert spec is not None
    # Heuristic picks the most-voted new colour from probes => FILL_COLOR(5).
    assert spec.goal_type is GoalType.FILL_COLOR
    assert spec.color == 5


def test_infer_goal_raising_llm_falls_back() -> None:
    """Purpose: an LLM callable that raises must be caught and the heuristic used.

    Expected feedback: pass => Ollama/network errors never propagate out of
    goal inference; fail => a discovery-time LLM error would kill the run.
    """
    def boom(_prompt: str) -> str:
        raise RuntimeError("ollama down")

    spec = infer_goal({0: 100, 2: 5}, [], llm_call=boom)
    assert spec.goal_type is GoalType.FILL_COLOR


def test_parse_goal_spec_rejects_unknown_type_and_out_of_range() -> None:
    """Purpose: parse_goal_spec must reject unknown goal types and out-of-range
    params by returning None (the fallback trigger).

    Expected feedback: pass => validation is strict; fail => malformed specs leak
    through and score_goal would raise or misbehave downstream.
    """
    assert parse_goal_spec('{"goal_type": "NUKE_EVERYTHING"}') is None
    assert parse_goal_spec('{"goal_type": "FILL_COLOR", "color": 99}') is None
    assert parse_goal_spec("not json at all") is None
    ok = parse_goal_spec('{"goal_type": "FILL_COLOR", "color": 7}')
    assert ok is not None and ok.color == 7


def test_heuristic_goal_uses_rarest_color_without_probes() -> None:
    """Purpose: with no informative probes, the heuristic targets the rarest
    non-background colour as a plausible completion target.

    Expected feedback: pass => the never-blocking default is sensible; fail =>
    the fallback would target background or crash on an empty probe list.
    """
    spec = heuristic_goal({0: 4000, 1: 90, 2: 6}, [])
    assert spec.goal_type is GoalType.FILL_COLOR
    assert spec.color == 2


# ── R46 semantic-progress measures ───────────────────────────────────────────


def test_score_goal_order_rises_as_components_size_sort() -> None:
    """Purpose: score_goal(ORDER) must be higher for a component sequence whose
    sizes are monotone along the axis than for a scrambled one.

    Expected feedback: pass => the sort-class goal can climb toward a size-sorted
    arrangement; fail => the ORDER measure is not directional and cannot steer
    sort puzzles like SB26.
    """
    goal = GoalSpec(goal_type=GoalType.ORDER, axis=0)
    sorted_frame = np.zeros((64, 64), dtype=np.int64)
    # three blobs left->right with increasing size (1,4,9 cells)
    sorted_frame[2, 4] = 5
    sorted_frame[2, 20:22] = 5
    sorted_frame[2:4, 20:22] = 5
    sorted_frame[2:5, 36:39] = 5
    scrambled = np.zeros((64, 64), dtype=np.int64)
    scrambled[2:5, 4:7] = 5  # big on the left
    scrambled[2, 20:22] = 5  # medium mid
    scrambled[2, 36] = 5  # small right — then medium below reverses monotonicity
    scrambled[10:13, 44:47] = 5
    assert score_goal(sorted_frame, goal) >= score_goal(scrambled, goal)


def test_score_goal_order_zero_with_fewer_than_two_components() -> None:
    """Purpose: ORDER over a frame with <2 components carries no ordering, so the
    measure is 0.0 (no spurious gradient).

    Expected feedback: pass => single-object frames do not fabricate ordering
    progress; fail => the ranker chases noise on near-empty frames.
    """
    goal = GoalSpec(goal_type=GoalType.ORDER, axis=1)
    frame = np.zeros((64, 64), dtype=np.int64)
    frame[10:12, 10:12] = 7
    assert score_goal(frame, goal) == 0.0


def test_score_goal_on_target_rises_as_a_nears_b() -> None:
    """Purpose: score_goal(ON_TARGET) must increase (toward 0) as the colour-A
    component moves closer to the colour-B target.

    Expected feedback: pass => the pair-class goal can climb boxes-onto-targets /
    items-into-slots; fail => the ON_TARGET measure is not directional and cannot
    steer sokoban (KA59) or merge (SU15).
    """
    goal = GoalSpec(goal_type=GoalType.ON_TARGET, color=3, color_b=4)
    far = np.zeros((64, 64), dtype=np.int64)
    far[30:32, 4:6] = 3
    far[30:32, 50:52] = 4
    near = np.zeros((64, 64), dtype=np.int64)
    near[30:32, 46:48] = 3  # A moved next to B
    near[30:32, 50:52] = 4
    assert score_goal(near, goal) > score_goal(far, goal)


def test_score_goal_on_target_absent_color_is_maximally_far() -> None:
    """Purpose: ON_TARGET with a missing colour is scored maximally far so the
    ranker never prefers a state that lost a target/piece.

    Expected feedback: pass => losing a target is penalised; fail => the ranker
    could walk toward states that destroy the pieces it must place.
    """
    goal = GoalSpec(goal_type=GoalType.ON_TARGET, color=3, color_b=4)
    frame = np.zeros((64, 64), dtype=np.int64)
    frame[30:32, 4:6] = 3  # only A present, no B
    assert score_goal(frame, goal) == -float(64 * 64)


# ── R46 measure tracker + cross-level goal-type carry ─────────────────────────


def test_candidate_goals_covers_progress_shapes_for_salient_colors() -> None:
    """Purpose: candidate_goals must emit fill/count/order/pair shapes over the
    frame's salient object colours (the family the tracker scores).

    Expected feedback: pass => the tracker can discover any of the supported
    progress measures; fail => a whole goal class is invisible to inference.
    """
    from admorphiq.planner.goal_inference import candidate_goals

    frame = np.zeros((64, 64), dtype=np.int64)
    frame[10:12, 10:12] = 3
    frame[10:12, 40:42] = 4
    goals = candidate_goals(frame)
    types = {g.goal_type for g in goals}
    assert GoalType.FILL_COLOR in types
    assert GoalType.ORDER in types
    assert GoalType.ON_TARGET in types


def test_measure_tracker_best_trend_finds_monotone_measure() -> None:
    """Purpose: GoalMeasureTracker.best_trend must name the measure that moves
    consistently upward across observed frames.

    Expected feedback: pass => within-level trend inference works (an unseen game
    at L1 can acquire a goal); fail => trend detection is inert and the agent
    stays goal-less on stalled games.
    """
    from admorphiq.planner.goal_inference import GoalMeasureTracker

    tracker = GoalMeasureTracker()
    # A grows in colour-5 fill count monotonically across 12 frames.
    for k in range(12):
        frame = np.zeros((64, 64), dtype=np.int64)
        frame[0, : k + 2] = 5  # more colour-5 cells each step
        frame[40:42, 40:42] = 6  # a static second object so colours stay salient
        tracker.observe(frame)
    best = tracker.best_trend()
    assert best is not None
    assert best[0].goal_type is GoalType.FILL_COLOR
    assert best[0].color == 5


def test_measure_tracker_best_jump_snapshots_biggest_riser() -> None:
    """Purpose: best_jump must return the measure with the largest clean increase
    over a level — the snapshot carried to the next level.

    Expected feedback: pass => a level clear can hand its goal TYPE forward; fail
    => cross-level transfer to deep levels is broken.
    """
    from admorphiq.planner.goal_inference import GoalMeasureTracker

    tracker = GoalMeasureTracker()
    for k in range(6):
        frame = np.zeros((64, 64), dtype=np.int64)
        frame[0, : 2 * (k + 1)] = 5  # colour-5 fill climbs steadily
        frame[40:42, 40:42] = 6
        tracker.observe(frame)
    jump = tracker.best_jump()
    assert jump is not None
    assert jump.goal_type is GoalType.FILL_COLOR


def test_instantiate_goal_type_reselects_colors_on_new_frame() -> None:
    """Purpose: instantiate_goal_type must re-derive a concrete GoalSpec of the
    carried type using the NEW frame's own object colours.

    Expected feedback: pass => a carried ON_TARGET pairs the new level's two most
    salient colours; fail => cross-level carry re-uses stale colours and scores
    nothing on the next level.
    """
    from admorphiq.planner.goal_inference import instantiate_goal_type

    frame = np.zeros((64, 64), dtype=np.int64)
    frame[10:12, 10:12] = 8  # rarer object colour
    frame[10:16, 40:46] = 9  # larger object colour
    spec = instantiate_goal_type(frame, GoalType.ON_TARGET)
    assert spec is not None
    assert spec.goal_type is GoalType.ON_TARGET
    assert {spec.color, spec.color_b} == {8, 9}
