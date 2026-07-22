"""R95b step (iv) tests: the hypothesis verifier.

The headline test is the mutant expected-verdict matrix (schema.MUTANTS) run on
the real ft09/sc25 traces — the pre-built acceptance gate from step ii. The rest
pin the episode split, the min-probe UNKNOWN inheritance, and the aggregate rules
with fast synthetic fixtures.
"""

from __future__ import annotations

from admorphiq.hypothesis_select import schema as s
from admorphiq.hypothesis_select.grounding import GroundingService
from admorphiq.hypothesis_select.verifier import (
    VTransition,
    _aggregate,
    _split_episodes,
    _verify_transition,
    build_evidence,
    load_trace,
    verify_with_evidence,
)


def _game_of(instance) -> str:
    return "ft09" if isinstance(instance.objective, s.GlyphRelational) else "sc25"


def test_mutant_expected_verdict_matrix_matches_exactly():
    """Purpose: the verifier reproduces the frozen schema.MUTANTS expected-verdict
    table EXACTLY on the real traces (CONTRADICTED for dynamics/win-discriminable
    mutants, honest UNKNOWN for the data-indistinguishable ones), and PASSes both
    oracle instances.

    Expected feedback: pass proves the verifier is sound against the pre-built
    step-ii acceptance gate — the data-indistinguishable mutants are NOT
    required-rejected, and the discriminable ones ARE caught. Fail means the
    verifier or the table disagree and (per the protocol) that must be
    investigated, not forced."""
    # Build the grounded evidence ONCE per game and reuse it across every
    # instance (the evidence is hypothesis-independent).
    evidence = {g: build_evidence(load_trace(g), g) for g in ("ft09", "sc25")}

    for build in (s.ft09_oracle_instance, s.sc25_oracle_instance):
        instance = build()
        assert verify_with_evidence(instance, evidence[_game_of(instance)]).verdict is s.Verdict.PASS

    for case in s.MUTANTS:
        got = verify_with_evidence(case.instance, evidence[_game_of(case.instance)]).verdict
        assert got is case.expected_verdict, (
            f"{case.name}: verifier said {got.value}, table expects "
            f"{case.expected_verdict.value} — {case.reason}"
        )


def test_episode_split_is_disjoint_and_holds_out_later_win_episodes():
    """Purpose: the episode split puts the earlier win-bearing episodes in train
    and the later ones in held-out, with train and held-out disjoint and
    exhaustive over episodes.

    Expected feedback: pass proves claims are LEARNED and VERIFIED on different
    episodes (the Codex correction — not an adjacent even/odd frame split). Fail
    means train/held-out leak into each other and the verdicts aren't held-out."""
    triv = ((0,),)

    def tx(index, episode, levels_after, gold=True, action=6):
        return VTransition(index, episode, 0, action, (0, 0), gold, levels_after, triv, triv)

    # Episodes 1 and 2 each score a win (levels_after increments); episode 0 is
    # pure exploration (no win).
    trace = [
        tx(0, 0, 0, gold=False),
        tx(1, 1, 0),
        tx(2, 1, 1),  # win in episode 1
        tx(3, 2, 1),
        tx(4, 2, 2),  # win in episode 2
    ]
    train, holdout = _split_episodes(trace)
    assert train.isdisjoint(holdout)
    assert train | holdout == {0, 1, 2}
    assert 2 in holdout  # the later win episode is held out
    assert 0 in train  # exploration episodes are train


def test_min_probe_unknown_inheritance():
    """Purpose: a transition claim judged on fewer than the min-probe number of
    click observations is UNKNOWN, never PASS.

    Expected feedback: pass proves the verifier inherits grounding's min-probe
    rule (insufficient evidence -> UNKNOWN). Fail means a single click could
    wrongly PASS a transition-model claim."""
    cell = tuple(tuple(5 if (r, c) == (3, 3) else 0 for c in range(12)) for r in range(12))
    other = tuple(tuple(7 if (r, c) == (3, 3) else 0 for c in range(12)) for r in range(12))
    gs = GroundingService()
    gs.feed_transition(cell, 6, (3, 3), other)  # exactly ONE click observed
    model = s.ft09_oracle_instance().transition_model
    assert _verify_transition(model, gs) is s.Verdict.UNKNOWN

    empty = GroundingService()  # no observations at all
    assert _verify_transition(model, empty) is s.Verdict.UNKNOWN


def test_aggregate_rules():
    """Purpose: the aggregate combines per-claim verdicts correctly — any
    CONTRADICTED dominates; PASS needs transition PASS + objective PASS (or
    objective UNKNOWN only when there are no win events) + a non-contradicted
    guard; everything else is UNKNOWN.

    Expected feedback: pass proves the instance-level verdict rules match the
    frozen spec, including the objective-UNKNOWN tolerance being gated on the
    absence of gold win events. Fail means an instance could be mislabelled
    PASS/UNKNOWN."""
    P, C, U = s.Verdict.PASS, s.Verdict.CONTRADICTED, s.Verdict.UNKNOWN
    assert _aggregate(P, P, P, 5) is P
    assert _aggregate(C, P, P, 5) is C  # any contradicted -> contradicted
    assert _aggregate(P, C, P, 5) is C
    assert _aggregate(P, U, P, 5) is U  # objective UNKNOWN with win events -> not PASS
    assert _aggregate(P, U, P, 0) is P  # objective UNKNOWN tolerated with NO win events
    assert _aggregate(U, P, P, 5) is U  # transition UNKNOWN -> not PASS
    assert _aggregate(P, P, U, 5) is P  # guard UNKNOWN is tolerated
