"""R97 build #1 tests: the EXACT colour-transition verifier.

The core discrimination the footprint verifier cannot make (BinaryFlip vs
OrderedCycle) is tested on curated ground-truth evidence — the decoded ft09
k=3 cycle and the sc25 2-state toggle — plus the pre-model hole-certification
(binding correction 1) and the leakage boundary (train edges never consulted).
A real-trace extraction test proves the end-to-end path.
"""

from __future__ import annotations

from admorphiq.hypothesis_select.exact_transition import (
    ColourEdge,
    build_colour_evidence,
    certify_hole,
    colour_edges_from_trace,
    evidence_from_edges,
    verify_exact,
)
from admorphiq.hypothesis_select.schema import BinaryFlip, OrderedCycle, Verdict
from admorphiq.hypothesis_select.verifier import load_trace


def _evidence(edges: list[tuple[int, int]]):
    """All supplied edges as held-out (episode 1, holdout={1}) — the seed-test
    ground-truth mechanic supplied as clean tuples (oracle-first doctrine)."""
    return evidence_from_edges([ColourEdge(1, b, a) for b, a in edges], holdout_episodes={1})


# The two decoded ground-truth mechanics under test.
_FT09_THREE_CYCLE = [(9, 8), (8, 12), (12, 9)]  # k=3 ordered cycle
_SC25_TWO_TOGGLE = [(0, 14), (14, 0)]  # 2-state binary flip


def test_ordered_cycle_passes_and_binary_flip_contradicted_on_a_k3_cycle():
    """Purpose: on a genuine k=3 ordered-cycle evidence, OrderedCycle((9,8,12))
    PASSes (every source advances one step, all sources + the wrap edge covered)
    while BinaryFlip is CONTRADICTED (three colours cannot be a 2-state flip) —
    the exact discrimination the footprint verifier is blind to.

    Expected feedback: pass proves the verifier separates a cyclic successor from a
    flip on colour transitions. Fail means the two transition models are still
    conflated and the tier-2 hole test has no ground to stand on."""
    ev = _evidence(_FT09_THREE_CYCLE)
    assert verify_exact(OrderedCycle((9, 8, 12)), ev) is Verdict.PASS
    assert verify_exact(BinaryFlip(), ev) is Verdict.CONTRADICTED


def test_binary_flip_and_ordered_cycle_k2_both_pass_on_a_2state_toggle():
    """Purpose: on a 2-state toggle, BOTH BinaryFlip and OrderedCycle((0,14)) PASS —
    binary_flip IS ordered_cycle(k=2) (Codex correction 2), so the two are
    extensionally equal here.

    Expected feedback: pass proves the no-hole equivalence: the remaining
    vocabulary (ordered_cycle) already expresses a flip, which is exactly why sc25
    is the NO-HOLE control. Fail means the k=2 equivalence is not honoured and the
    control would be mis-scored as a hole."""
    ev = _evidence(_SC25_TWO_TOGGLE)
    assert verify_exact(BinaryFlip(), ev) is Verdict.PASS
    assert verify_exact(OrderedCycle((0, 14)), ev) is Verdict.PASS


def test_unknown_on_incomplete_coverage_and_no_holdout():
    """Purpose: honest UNKNOWN when a relevant source colour or the wrap edge is
    unexercised (ordered cycle missing an edge; a binary flip seen in only one
    direction), and UNKNOWN with no held-out edges at all.

    Expected feedback: pass proves the min-probe rule is inherited — insufficient
    coverage is never a PASS or a CONTRADICTED. Fail means the verifier over-claims
    from partial evidence."""
    partial_cycle = _evidence([(9, 8), (8, 12)])  # source 12 (and the wrap) uncovered
    assert verify_exact(OrderedCycle((9, 8, 12)), partial_cycle) is Verdict.UNKNOWN
    one_direction = _evidence([(0, 14)])  # only 0->14, never 14->0
    assert verify_exact(BinaryFlip(), one_direction) is Verdict.UNKNOWN
    empty = evidence_from_edges([], holdout_episodes={1})
    assert verify_exact(BinaryFlip(), empty) is Verdict.UNKNOWN
    assert verify_exact(OrderedCycle((0, 14)), empty) is Verdict.UNKNOWN


def test_off_cycle_and_wrong_successor_are_contradicted():
    """Purpose: an ordered cycle is CONTRADICTED both by a colour off the declared
    order and by a source advancing to the wrong successor.

    Expected feedback: pass proves the exact per-source-colour check rejects a
    declared cycle that the evidence refutes. Fail means an incorrect order could
    slip through."""
    off_cycle = _evidence([(9, 8), (8, 12), (12, 9), (7, 8)])  # 7 not in the order
    assert verify_exact(OrderedCycle((9, 8, 12)), off_cycle) is Verdict.CONTRADICTED
    wrong_succ = _evidence([(9, 12)])  # order says 9->8, evidence says 9->12
    assert verify_exact(OrderedCycle((9, 8, 12)), wrong_succ) is Verdict.CONTRADICTED


def test_certify_hole_true_for_genuine_hole_false_for_no_hole_control():
    """Purpose: certify_hole certifies the GENUINE hole (ablate ordered_cycle:
    offered=[binary_flip] CONTRADICTED, oracle=OrderedCycle PASS) and REFUSES the
    no-hole control (ablate binary_flip: offered=[ordered_cycle(k=2)] PASSes, so
    not a hole) — binding correction 1.

    Expected feedback: pass proves the pre-model, oracle-first hole proof works: a
    real capability gap is certified, and a false positive (the vocabulary already
    expresses it) is rejected so the correct action there is SELECT not extend.
    Fail means the escape-hatch would fire spuriously or miss a real hole."""
    genuine = certify_hole(_evidence(_FT09_THREE_CYCLE), [BinaryFlip()], OrderedCycle((9, 8, 12)))
    assert genuine.certified is True
    assert genuine.oracle_verdict is Verdict.PASS
    assert all(v is Verdict.CONTRADICTED for _, v in genuine.offered_verdicts)

    control = certify_hole(_evidence(_SC25_TWO_TOGGLE), [OrderedCycle((0, 14))], BinaryFlip())
    assert control.certified is False
    assert control.oracle_verdict is Verdict.PASS  # the oracle itself still holds
    assert "no hole" in control.reason


def test_empty_offered_is_never_a_certified_hole():
    """Purpose: with no offered candidates there is nothing shown non-expressible,
    so a hole is never certified even when the oracle PASSes.

    Expected feedback: pass proves certification requires positive evidence that
    the remaining vocabulary FAILS. Fail means an empty candidate set could
    vacuously certify a hole and licence a needless extension."""
    cert = certify_hole(_evidence(_FT09_THREE_CYCLE), [], OrderedCycle((9, 8, 12)))
    assert cert.certified is False


def test_train_edges_are_never_consulted_for_a_verdict():
    """Purpose: an edge that would CONTRADICT the oracle, placed in a TRAIN episode
    only, does not change the held-out verdict (R50b leakage doctrine — verdicts
    come from held-out edges alone).

    Expected feedback: pass proves the train/held-out boundary: synthesis-feedback
    edges cannot leak into verification. Fail means training evidence contaminates
    the verdict and the split is not honoured."""
    edges = [
        ColourEdge(0, 9, 99),  # a contradicting edge — TRAIN only
        ColourEdge(1, 9, 8),
        ColourEdge(1, 8, 12),
        ColourEdge(1, 12, 9),  # a clean k=3 cycle in HELD-OUT
    ]
    ev = evidence_from_edges(edges, holdout_episodes={1})
    assert verify_exact(OrderedCycle((9, 8, 12)), ev) is Verdict.PASS


def test_real_ft09_trace_extraction_contradicts_binary_flip():
    """Purpose: the end-to-end trace path (colour_edges_from_trace ->
    build_colour_evidence) yields real held-out colour edges spanning more than two
    colours, so BinaryFlip is correctly CONTRADICTED on the real ft09 trace.

    Expected feedback: pass proves the extraction resolves clicked-cell colour
    edges from a real recorded trace and feeds the verifier. Fail means the
    trace-extraction path is broken or the real ft09 board is not a >2-colour
    game."""
    trace = load_trace("ft09")
    assert colour_edges_from_trace(trace)  # extraction produced edges
    ev = build_colour_evidence(trace)
    assert ev.holdout  # the later win episodes carry click edges
    assert verify_exact(BinaryFlip(), ev) is Verdict.CONTRADICTED
