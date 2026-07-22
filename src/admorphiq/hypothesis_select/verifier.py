"""R95b STEP (iv): the hypothesis verifier (PASS / CONTRADICTED / UNKNOWN).

Given a :class:`~admorphiq.hypothesis_select.schema.CellStateHypothesis` and a
recorded trace, decide — over GroundingService output, NEVER raw pixels — whether
each of the hypothesis's claims is supported (PASS), refuted (CONTRADICTED), or
underdetermined by the evidence (UNKNOWN). The min-probe rule is inherited from
grounding: insufficient evidence is UNKNOWN, never PASS.

Claims verified (cell-state family):

* **transition model** — tested against the grounded click FOOTPRINT distribution
  (single-cell vs multi-cell) acquired on TRAIN episodes. Footprint is
  level-invariant (a click changes one cell on every ft09/sc25 level), unlike the
  colour cycle whose alphabet is per-board — so footprint is the sound
  cross-level discriminator; the ordered-cycle alphabet is a per-board
  harness_measured value, not verified across levels here.
* **objective** — tested against gold WIN/cast states in HELD-OUT episodes: the
  glyph-relational predicate under the hypothesis's coverage quantifier +
  ink->operator map, or the pattern-reference predicate under its preview
  interpretation. A predicate FALSE at a real win = CONTRADICTED. A predicate
  that HOLDS at wins but whose distinctive RELAXATION (nearest-only, near-match)
  is never exercised by the evidence = UNKNOWN (the R95a data-indistinguishability
  measured directly). The complete/exact reading that holds at wins = PASS.
* **guards** — a phase guard is PASS when vacuously satisfied (no clauses) and
  UNKNOWN when its clauses are not decidable from the current grounded evidence
  (step-iv scope: guards are not deeply verified; no mutant touches them).

Aggregation: any CONTRADICTED claim => the instance is CONTRADICTED; else the
instance is PASS only if the transition claim PASSes and the objective PASSes (or
is UNKNOWN-tolerated because the evidence holds no gold win events) and no guard
is CONTRADICTED; else UNKNOWN.

Episode split (Codex correction): claims are LEARNED on train episodes and
VERIFIED on held-out episodes — never an adjacent even/odd frame split.

Scope: verification only — no compiler, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np

from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService
from admorphiq.hypothesis_select.schema import (
    BinaryFlip,
    CellStateHypothesis,
    EmpiricalEffectMatrix,
    GlyphRelational,
    OrderedCycle,
    PatternReference,
    Verdict,
)

Grid = tuple[tuple[int, ...], ...]
_TRACE_DIR = Path("data/traces")
# ft09's win state is the SOLVED board (after the winning click); sc25's cast
# state is the matched grid observed BEFORE the engine consumes it on the next
# action (its after-frame is the post-cast redraw with the preview gone). Same
# split as the R95a probe's _WIN_FRAME_SIDE.
_WIN_FRAME_SIDE = {"ft09": "after", "sc25": "before"}
_NEAR_MATCH_TOLERANCE = 2  # cells: a "near" match allows up to this many mismatches


@dataclass(frozen=True)
class VTransition:
    """One recorded transition with the fields the verifier's episode split and
    win-state extraction need."""

    index: int
    episode: int
    level: int
    action: int
    xy: tuple[int, int]
    is_gold: bool
    levels_after: int
    before: Grid
    after: Grid


@dataclass(frozen=True)
class InstanceVerdict:
    """The aggregate verdict + the per-claim verdicts + the evidence counts."""

    verdict: Verdict
    transition: Verdict
    objective: Verdict
    guard: Verdict
    n_win_events: int


def _to_grid(frame: np.ndarray) -> Grid:
    arr = np.asarray(frame)
    if arr.ndim == 3:
        arr = arr[-1]
    return tuple(tuple(int(v) for v in row) for row in arr)


def load_trace(game: str) -> list[VTransition]:
    """The game's recorded trace as ``VTransition``s (from ``data/traces``)."""
    data = np.load(_TRACE_DIR / f"{game}.npz", allow_pickle=False)
    out: list[VTransition] = []
    for i in range(len(data["actions"])):
        out.append(
            VTransition(
                index=i,
                episode=int(data["episode_id"][i]),
                level=int(data["level_index"][i]),
                action=int(data["actions"][i]),
                xy=(int(data["coords_x"][i]), int(data["coords_y"][i])),
                is_gold=bool(data["is_gold"][i]),
                levels_after=int(data["levels_completed_after"][i]),
                before=_to_grid(data["frames"][i]),
                after=_to_grid(data["next_frames"][i]),
            )
        )
    return out


def _split_episodes(trace: list[VTransition]) -> tuple[set[int], set[int]]:
    """Split the WIN-bearing episodes in half: the earlier half's episodes are
    train (claims learned there), the later half held-out (claims verified
    there). Non-win (exploration) episodes are all train — they carry the
    footprint/cycle evidence but no win state to verify against."""
    win_eps: list[int] = []
    prev = trace[0].levels_after if trace else 0
    prev_ep = trace[0].episode if trace else 0
    for t in trace:
        if t.episode == prev_ep and t.levels_after > prev:
            win_eps.append(t.episode)
        prev = t.levels_after if t.episode == prev_ep else t.levels_after
        prev_ep = t.episode
    ordered = sorted(dict.fromkeys(win_eps))
    k = len(ordered) // 2
    holdout = set(ordered[k:])
    train = {t.episode for t in trace} - holdout
    return train, holdout


def _win_frames(trace: list[VTransition], game: str, episodes: set[int]) -> list[Grid]:
    """The gold win/cast frames within ``episodes``: for each level-up event, the
    game-appropriate side (see ``_WIN_FRAME_SIDE``) of the last gold ACTION6 at or
    before it within the same episode+level."""
    side = _WIN_FRAME_SIDE.get(game, "after")
    frames: list[Grid] = []
    prev = trace[0].levels_after if trace else 0
    prev_ep = trace[0].episode if trace else 0
    for pos, t in enumerate(trace):
        if t.episode == prev_ep and t.levels_after > prev and t.episode in episodes:
            frame = _last_gold_click_frame(trace, pos, t.episode, t.level, side)
            if frame is not None:
                frames.append(frame)
        prev = t.levels_after if t.episode == prev_ep else t.levels_after
        prev_ep = t.episode
    return frames


def _last_gold_click_frame(
    trace: list[VTransition], pos: int, episode: int, level: int, side: str
) -> Optional[Grid]:
    for j in range(pos, -1, -1):
        tj = trace[j]
        if tj.episode != episode or tj.level != level:
            break
        if tj.is_gold and tj.action == 6:
            return tj.after if side == "after" else tj.before
    return None


def _train_grounding(trace: list[VTransition], train: set[int]) -> GroundingService:
    """A GroundingService fed the TRAIN episodes' transitions — accumulating the
    footprint distribution and cycle edges the transition claim is judged on."""
    gs = GroundingService()
    for t in trace:
        if t.episode in train:
            gs.feed_transition(t.before, t.action, t.xy, t.after)
    return gs


# ── per-claim verifiers ──────────────────────────────────────────────────────


def _verify_transition(model: Any, gs: GroundingService) -> Verdict:
    """Transition-model verdict from the grounded footprint distribution. A
    single-cell model (ordered cycle / binary flip) PASSes iff the modal
    EFFECTIVE footprint is 1; an empirical-effect-matrix asserting a footprint N
    PASSes iff the modal footprint is N. Insufficient observations => UNKNOWN
    (min-probe)."""
    obs = gs.observed_footprints()
    if obs is UNKNOWN or obs.confidence == "low":
        return Verdict.UNKNOWN
    effective = {k: v for k, v in obs.value.items() if k >= 1}
    if not effective:
        return Verdict.UNKNOWN
    modal = max(effective, key=lambda k: effective[k])
    if isinstance(model, (OrderedCycle, BinaryFlip)):
        return Verdict.PASS if modal == 1 else Verdict.CONTRADICTED
    if isinstance(model, EmpiricalEffectMatrix):
        if model.asserted_footprint is None:
            return Verdict.UNKNOWN  # no specific footprint asserted to test
        return Verdict.PASS if modal == model.asserted_footprint else Verdict.CONTRADICTED
    return Verdict.UNKNOWN


def _verify_objective(objective: Any, win_frames: list[Grid], game: str) -> Verdict:
    if not win_frames:
        return Verdict.UNKNOWN
    if isinstance(objective, GlyphRelational):
        return _verify_glyph_objective(objective, win_frames)
    if isinstance(objective, PatternReference):
        return _verify_pattern_objective(objective, win_frames)
    return Verdict.UNKNOWN


def _verify_glyph_objective(objective: GlyphRelational, win_frames: list[Grid]) -> Verdict:
    ink_map = dict(objective.ink_operator_map)
    for frame in win_frames:
        gs = GroundingService()
        gs.feed(frame)
        if not _glyph_predicate_holds(gs, objective.coverage_quantifier, ink_map):
            return Verdict.CONTRADICTED  # the rule rejects a real win state
    # Holds at every win. The complete reading is confirmed; a relaxation
    # (nearest-only) is UNKNOWN because no divergent multi-glyph cell exercises it.
    return Verdict.PASS if objective.coverage_quantifier == "all_covering" else Verdict.UNKNOWN


def _glyph_predicate_holds(gs: GroundingService, quantifier: str, ink_map: dict[int, str]) -> bool:
    cells = gs.cells()
    if cells is UNKNOWN:
        return False
    centroids = dict(cells.value)
    for cell_id, cell_centroid in cells.value:
        colour = gs.cell_colour(cell_id)
        covering = gs.incidence(cell_id)
        if colour is UNKNOWN or covering is UNKNOWN or not covering.value:
            continue
        entries = covering.value
        if quantifier == "nearest_only":
            entries = [min(entries, key=lambda e: _dist(cell_centroid, e[3]))]
        for _gid, ink, marker, _gc in entries:
            op = ink_map.get(ink)
            if op == "equal" and colour.value != marker:
                return False
            if op == "differ" and colour.value == marker:
                return False
    return bool(centroids)


def _verify_pattern_objective(objective: PatternReference, win_frames: list[Grid]) -> Verdict:
    interp = objective.preview_interpretation
    holds_all = True
    for frame in win_frames:
        gs = GroundingService()
        gs.feed(frame)
        ev = gs.pattern_evidence()
        if ev is UNKNOWN:
            holds_all = False
            continue
        if not _pattern_predicate_holds(interp, ev.value):
            return Verdict.CONTRADICTED  # the interpretation rejects a real cast
    if not holds_all:
        return Verdict.UNKNOWN
    if interp in ("xor_exact", "absolute_exact"):
        return Verdict.PASS  # the exact reading is confirmed at every cast
    return Verdict.UNKNOWN  # a "near" relaxation is unconfirmed without a near-but-not-exact cast


def _pattern_predicate_holds(interp: str, ev: dict[str, Any]) -> bool:
    if interp == "xor_exact":
        return bool(ev["matches_xor"])
    if interp == "absolute_exact":
        return bool(ev["matches_absolute"])
    if interp == "xor_near":
        return ev["cells_matching"] >= ev["total"] - _NEAR_MATCH_TOLERANCE
    if interp == "absolute_near":
        return ev["cells_matching"] >= ev["total"] - _NEAR_MATCH_TOLERANCE
    return False


def _verify_guards(phases: tuple[Any, ...]) -> Verdict:
    """Step-iv guard verdict: PASS when every phase guard is vacuous (no clauses)
    — nothing to contradict — else UNKNOWN (deep guard verification against
    observed phase transitions is out of step-iv scope; no mutant touches
    guards)."""
    if all(len(phase.guard) == 0 for phase in phases):
        return Verdict.PASS
    return Verdict.UNKNOWN


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# ── aggregate ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Evidence:
    """The grounded evidence a game's trace yields once — reusable across many
    hypotheses (the trace-derived facts do not depend on the hypothesis): the
    train-episode grounding (footprints / cycle) and the held-out win/cast
    frames."""

    game: str
    train_grounding: GroundingService
    win_frames: tuple[Grid, ...]


def build_evidence(trace: list[VTransition], game: str) -> Evidence:
    """Build the reusable grounded evidence for ``game``: train-episode footprints
    + held-out win/cast frames. Doing this ONCE per game and verifying many
    instances against it avoids re-grounding the whole trace per hypothesis."""
    train, holdout = _split_episodes(trace)
    return Evidence(
        game=game,
        train_grounding=_train_grounding(trace, train),
        win_frames=tuple(_win_frames(trace, game, holdout)),
    )


def verify_with_evidence(instance: CellStateHypothesis, evidence: Evidence) -> InstanceVerdict:
    """Verify a hypothesis against pre-built :class:`Evidence` (per-claim verdicts
    + aggregate)."""
    transition = _verify_transition(instance.transition_model, evidence.train_grounding)
    objective = _verify_objective(instance.objective, list(evidence.win_frames), evidence.game)
    guard = _verify_guards(instance.phases)
    aggregate = _aggregate(transition, objective, guard, len(evidence.win_frames))
    return InstanceVerdict(
        verdict=aggregate,
        transition=transition,
        objective=objective,
        guard=guard,
        n_win_events=len(evidence.win_frames),
    )


def verify_instance(instance: CellStateHypothesis, trace: list[VTransition], game: str) -> InstanceVerdict:
    """The aggregate verdict for a whole hypothesis instance on ``game``'s trace,
    with per-claim verdicts. Transition claims are learned on train episodes,
    objective claims verified on held-out episodes' win states."""
    return verify_with_evidence(instance, build_evidence(trace, game))


def _aggregate(transition: Verdict, objective: Verdict, guard: Verdict, n_win: int) -> Verdict:
    if Verdict.CONTRADICTED in (transition, objective, guard):
        return Verdict.CONTRADICTED
    objective_ok = objective == Verdict.PASS or (objective == Verdict.UNKNOWN and n_win == 0)
    if transition == Verdict.PASS and objective_ok and guard in (Verdict.PASS, Verdict.UNKNOWN):
        return Verdict.PASS
    return Verdict.UNKNOWN


__all__ = [
    "VTransition",
    "InstanceVerdict",
    "Evidence",
    "load_trace",
    "build_evidence",
    "verify_with_evidence",
    "verify_instance",
]
