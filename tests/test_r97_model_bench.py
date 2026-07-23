"""R97 model-bench scaffolding tests (no LLM, no env).

Leak-guard on the four case prompts (no game id / provenance / ablated-rule-shape
hint), the exclusive select|extend|abstain output-union parser (mixed = invalid),
the extend authoring path (oracle passes, mutant fails), and the per-case scoring.
All hermetic: synthetic colour-transition evidence, a stub llm.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import probe_r97_model_bench as bench  # noqa: E402

from admorphiq.hypothesis_select.exact_transition import ColourEdge, evidence_from_edges  # noqa: E402

_THREE_CYCLE = [(8, 12), (12, 9), (9, 8)]
_TWO_STATE = [(8, 9), (9, 8)]


def _evidence() -> dict:
    """A synthetic evidence dict matching load_evidence's shape: a k=3 hole cycle
    (order 8->12->9) with train+held-out coverage, and a 2-state no-hole cycle."""
    hole = evidence_from_edges(
        [ColourEdge(0, b, a) for b, a in _THREE_CYCLE] + [ColourEdge(1, b, a) for b, a in _THREE_CYCLE],
        holdout_episodes={1},
    )
    no_hole = evidence_from_edges(
        [ColourEdge(0, b, a) for b, a in _TWO_STATE] + [ColourEdge(1, b, a) for b, a in _TWO_STATE],
        holdout_episodes={1},
    )
    return {"hole": hole, "no_hole": no_hole, "order": [8, 12, 9]}


_ORACLE_SRC = (
    "def update(colour, click_index, palette):\n"
    "    i = palette.index(colour)\n"
    "    return palette[(i + 1) % len(palette)]\n"
)
_IDENTITY_SRC = "def update(colour, click_index, palette):\n    return colour\n"


def _stub(reply: str):
    return lambda _messages: reply


def test_case_prompts_are_leak_safe():
    """Purpose: no case prompt leaks a game id, a rule/instance provenance label, or
    the ablated rule's SHAPE — and specifically the hole/blind/insufficient prompts
    (vocabulary minus ordered_cycle) never describe a cyclic/ordered successor,
    while the no-hole prompt MAY (ordered_cycle is offered there).

    Expected feedback: pass proves the prompts honour the R97 leakage prohibitions
    so a model pass is genuine re-derivation, not a hinted answer. Fail means a
    prompt gives away the missing rule or the provenance."""
    ev = _evidence()
    banned = ("ft09", "sc25", "m0r0", "oracle", "mutant", "idx4", "harness", "ablat")
    for case in ("hole", "no_hole", "evidence_blind", "insufficient"):
        text = " ".join(m["content"] for m in bench.build_case_prompt(case, ev)).lower()
        for token in banned:
            assert token not in text, f"{case} prompt leaked {token!r}"
    for case in ("hole", "evidence_blind", "insufficient"):
        text = " ".join(m["content"] for m in bench.build_case_prompt(case, ev)).lower()
        for token in ("ordered_cycle", "cycle", "cyclic", "advances", "wrapping"):
            assert token not in text, f"{case} prompt hints the ablated ordered-cycle shape ({token!r})"
    no_hole = " ".join(m["content"] for m in bench.build_case_prompt("no_hole", ev)).lower()
    assert "ordered_cycle" in no_hole  # it is an OFFERED option in the no-hole case


def test_output_union_parser_is_exclusive():
    """Purpose: the parser accepts each single-arm shape and REJECTS a mixed response
    (a select carrying a source, or an extend carrying a candidate), an unknown
    action, and an out-of-vocabulary candidate.

    Expected feedback: pass proves the exclusive select|extend|abstain contract is
    enforced at parse time (mixed = invalid, the Codex correction-4 rule). Fail means
    an ambiguous 'pick but flag misfit' response could be scored."""
    offered = bench._HOLE_VOCAB
    sel, err = bench.parse_action('{"action":"select","candidate":"binary_flip"}', offered)
    assert sel == {"action": "select", "candidate": "binary_flip"} and not err
    ext, err = bench.parse_action('{"action":"extend","name":"cyc","source":"def update(): pass"}', offered)
    assert ext["action"] == "extend" and ext["name"] == "cyc" and not err
    ab, err = bench.parse_action('{"action":"abstain","reason":"insufficient_evidence"}', offered)
    assert ab["action"] == "abstain" and not err
    # mixed / invalid
    assert bench.parse_action('{"action":"select","candidate":"binary_flip","source":"x"}', offered)[0] is None
    mixed_extend = '{"action":"extend","candidate":"binary_flip","name":"n","source":"s"}'
    assert bench.parse_action(mixed_extend, offered)[0] is None
    assert bench.parse_action('{"action":"select","candidate":"ordered_cycle"}', offered)[0] is None  # not offered
    assert bench.parse_action('{"action":"frobnicate"}', offered)[0] is None
    assert bench.parse_action("no json here", offered)[0] is None


def test_ask_action_retries_once_on_invalid():
    """Purpose: an invalid first reply triggers exactly one format-error retry; a
    valid retry is accepted (attempts=2).

    Expected feedback: pass proves the one-retry ask shape (R95 discipline). Fail
    means the bench either never retries or retries unboundedly."""
    replies = iter(["garbage", '{"action":"abstain","reason":"x"}'])
    llm = lambda _m: next(replies)  # noqa: E731 - test-local stub
    out = bench.ask_action(llm, [{"role": "user", "content": "q"}], bench._HOLE_VOCAB)
    assert out["action"] == "abstain" and out["attempts"] == 2


def test_evaluate_extend_oracle_passes_mutant_fails():
    """Purpose: a correct cyclic-successor `update` passes AST + TRAIN fit + held-out
    exactness; the identity mutant fails held-out.

    Expected feedback: pass proves the extend authoring path scores real re-derivation
    (the hole-recall bar). Fail means a wrong authored rule could be credited."""
    ev = _evidence()
    good = bench.evaluate_extend(_ORACLE_SRC, ev)
    assert good["ast_valid"] and good["train_fit"] and good["held_out_exact"] and good["passes"]
    bad = bench.evaluate_extend(_IDENTITY_SRC, ev)
    assert not bad["passes"] and not bad["held_out_exact"]


def test_score_run_hole_and_no_hole():
    """Purpose: hole scoring credits a passing extend and rejects a select; no-hole
    scoring credits a correct select and flags any extend as a false positive.

    Expected feedback: pass proves detection is scored separately from authoring per
    the amended contract. Fail means the case verdicts are miscounted."""
    ev = _evidence()
    hole_extend = bench._score_run("hole", {"action": "extend", "name": "c", "source": _ORACLE_SRC}, ev, False)
    assert hole_extend["success"] is True
    hole_select = bench._score_run("hole", {"action": "select", "candidate": "binary_flip"}, ev, False)
    assert hole_select["success"] is False
    nh_select = bench._score_run("no_hole", {"action": "select", "candidate": "binary_flip"}, ev, False)
    assert nh_select["success"] is True and nh_select["false_positive"] is False
    # ordered_cycle IS binary_flip at k=2, so it is ALSO a correct no-hole pick (the pin).
    nh_cycle = bench._score_run("no_hole", {"action": "select", "candidate": "ordered_cycle"}, ev, False)
    assert nh_cycle["success"] is True and nh_cycle["false_positive"] is False
    nh_extend = bench._score_run("no_hole", {"action": "extend", "name": "c", "source": _ORACLE_SRC}, ev, False)
    assert nh_extend["success"] is False and nh_extend["false_positive"] is True
    # abstain on a NO-HOLE board is a MISS (the evidence IS sufficient), not a false positive.
    nh_abstain = bench._score_run("no_hole", {"action": "abstain", "reason": "x"}, ev, False)
    assert nh_abstain["success"] is False and nh_abstain["false_positive"] is False


def test_run_case_verdict_thresholds():
    """Purpose: run_case aggregates >=2/3 correctly — a 3-run hole case where the
    stub always extends the oracle passes hole_recall; a no-hole case where the stub
    always selects binary_flip passes specificity.

    Expected feedback: pass proves the per-case >=2/3 verdict wiring. Fail means the
    SEED-PASS aggregation is wrong."""
    ev = _evidence()
    extend_reply = ('{"action":"extend","name":"cyc","source":"def update(colour, click_index, palette):\\n'
                    '    i = palette.index(colour)\\n    return palette[(i + 1) % len(palette)]\\n"}')
    hole = bench.run_case("hole", 3, _stub(extend_reply), ev, gold_gate=False)
    assert hole["pass"] is True and hole["hole_recall"] == "3/3"
    no_hole = bench.run_case("no_hole", 3, _stub('{"action":"select","candidate":"binary_flip"}'), ev, gold_gate=False)
    assert no_hole["pass"] is True and no_hole["false_positives"] == 0
