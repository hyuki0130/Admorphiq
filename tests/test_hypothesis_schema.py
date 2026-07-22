"""R95b step (ii) tests: the typed cell-state hypothesis schema.

No LLM, no environment, no trace loads — pure type/serialization contracts on
the schema, its canonical oracle instances, and the mutant fixtures.
"""

from __future__ import annotations

import json
from dataclasses import fields

import pytest

from admorphiq.hypothesis_select import schema as s


def test_objective_union_makes_cross_products_unrepresentable():
    """Purpose: the objective arms are separate types whose fields do not
    overlap, so an invalid cross-product (glyph source + XOR/preview target)
    cannot be constructed — XOR/preview semantics live ONLY on PatternReference,
    ink/coverage ONLY on GlyphRelational.

    Expected feedback: pass proves the schema enforces objective coherence by
    shape (not by runtime check), the core R95b type-safety requirement. Fail
    means a caller could build a nonsensical mixed objective."""
    glyph_fields = {f.name for f in fields(s.GlyphRelational)}
    pattern_fields = {f.name for f in fields(s.PatternReference)}
    assert "preview_interpretation" not in glyph_fields
    assert "coverage_quantifier" not in pattern_fields
    assert glyph_fields.isdisjoint({"preview_interpretation", "base_snapshot_timing"})
    assert pattern_fields.isdisjoint({"coverage_quantifier", "ink_operator_map"})
    # GlyphRelational cannot even be constructed with a preview arg.
    with pytest.raises(TypeError):
        s.GlyphRelational(  # type: ignore[call-arg]
            coverage_quantifier="all_covering",
            ink_operator_map=((0, "equal"),),
            no_cell_ink=3,
            preview_interpretation="xor_exact",
        )


def test_ownership_table_model_selected_matches_the_frozen_design_list():
    """Purpose: EVERY schema field carries an ownership tag, and the set of
    model_selected fields is EXACTLY the frozen design list — coverage
    quantifier, ink/operator mapping, preview interpretation, guards.

    Expected feedback: pass proves the model owns only the four semantic slots
    (the harness materializes everything else), the contract the verifier and
    compiler substages depend on. Fail means the model/harness boundary drifted
    and later attribution would be wrong."""
    model_selected = {k for k, v in s.OWNERSHIP.items() if v == s.Ownership.MODEL_SELECTED}
    assert model_selected == set(s.MODEL_SELECTED_SEMANTICS)
    assert model_selected == {
        "GlyphRelational.coverage_quantifier",
        "GlyphRelational.ink_operator_map",
        "PatternReference.preview_interpretation",
        "Phase.guard",
    }
    # Every ownership value is a valid tag; no field left un-annotated among owned classes.
    assert all(isinstance(v, s.Ownership) for v in s.OWNERSHIP.values())
    assert "CellStateHypothesis.objective" in s.OWNERSHIP  # containers are tagged too


def test_oracle_instances_validate_and_round_trip():
    """Purpose: both canonical oracle instances construct (pass __post_init__
    validation) and survive to_neutral_json -> from_json exactly.

    Expected feedback: pass proves the oracles are well-formed and the serialized
    form is lossless — the canned-instance channel the model selects from is
    faithful. Fail means an oracle is malformed or serialization drops a field."""
    for build in (s.ft09_oracle_instance, s.sc25_oracle_instance):
        instance = build()
        assert isinstance(instance, s.CellStateHypothesis)
        assert s.from_json(s.to_neutral_json(instance)) == instance

    ft09 = s.ft09_oracle_instance()
    assert isinstance(ft09.objective, s.GlyphRelational)
    assert isinstance(ft09.transition_model, s.OrderedCycle)
    assert ft09.transition_model.order == (9, 8, 12)  # the adapter's decoded cycle

    sc25 = s.sc25_oracle_instance()
    assert isinstance(sc25.objective, s.PatternReference)
    assert isinstance(sc25.transition_model, s.BinaryFlip)
    # The cast-handover phase carries the typed guard conjunction.
    handover = sc25.phases[1]
    assert any(isinstance(c, s.StableForReads) for c in handover.guard)
    assert any(isinstance(c, s.RolesStateEqual) for c in handover.guard)


def test_every_mutant_constructs_serializes_and_round_trips():
    """Purpose: each mutant fixture is a well-formed CellStateHypothesis that
    serializes and round-trips (it is a WRONG hypothesis, not a malformed one).

    Expected feedback: pass proves the mutants are valid schema instances the
    future verifier can evaluate. Fail means a mutant is unconstructable and the
    verifier acceptance test could not run it."""
    for case in s.MUTANTS:
        assert isinstance(case.instance, s.CellStateHypothesis)
        blob = s.to_neutral_json(case.instance)
        assert s.from_json(blob) == case.instance


def test_expected_verdict_table_covers_every_mutant_exactly_once():
    """Purpose: the mutant/expected-verdict table (the verifier's future
    acceptance data) has unique names, a verdict in {CONTRADICTED, UNKNOWN} and a
    reason for each, with the data-indistinguishable mutants marked UNKNOWN and
    the dynamics/win-discriminable ones CONTRADICTED.

    Expected feedback: pass proves the honest-UNKNOWN split from the R95a
    measurements is encoded as data, not prose — the verifier must reproduce it.
    Fail means a required-rejection was demanded where the data cannot separate,
    or a discriminable mutant was let off."""
    names = [c.name for c in s.MUTANTS]
    assert len(names) == len(set(names)) == 6
    for case in s.MUTANTS:
        assert case.expected_verdict in {s.Verdict.CONTRADICTED, s.Verdict.UNKNOWN}
        assert case.reason.strip()

    unknown = {c.name for c in s.MUTANTS if c.expected_verdict == s.Verdict.UNKNOWN}
    contradicted = {c.name for c in s.MUTANTS if c.expected_verdict == s.Verdict.CONTRADICTED}
    assert unknown == {"ft09_nearest_only_quantifier", "sc25_near_match_objective"}
    assert contradicted == {
        "ft09_stencil_transition",
        "ft09_all_ink_equal",
        "sc25_neighbour_flip_transition",
        "sc25_absolute_preview_interpretation",
    }


def test_neutral_json_carries_no_provenance_labels():
    """Purpose: the model-facing serialized form exposes structural tags + values
    only — never ownership tags, oracle/mutant labels, or game ids.

    Expected feedback: pass proves the canned instances cannot leak an answer key
    (the R95a leak-guard discipline extended to R95b prompts). Fail means the
    model could shortcut on provenance instead of reasoning about mechanics."""
    forbidden = [
        "ownership", "harness_measured", "model_selected", "compiler_derived",
        "oracle", "mutant", "ft09", "sc25", "provenance",
    ]
    instances = [s.ft09_oracle_instance(), s.sc25_oracle_instance()] + [c.instance for c in s.MUTANTS]
    for instance in instances:
        text = json.dumps(s.to_neutral_json(instance)).lower()
        leaked = [tok for tok in forbidden if tok in text]
        assert leaked == [], f"neutral json leaked {leaked}"


def test_from_json_validation_errors_name_the_offending_field():
    """Purpose: from_json rejects unknown kinds, missing keys, and out-of-set
    enum values with a ValueError that NAMES the offending field path (the
    model's later error-feedback channel).

    Expected feedback: pass proves malformed model output produces a precise,
    field-addressed error rather than a silent bad instance. Fail means the
    error-feedback retry loop would have nothing actionable to echo."""
    good = s.to_neutral_json(s.ft09_oracle_instance())

    unknown_kind = json.loads(json.dumps(good))
    unknown_kind["objective"]["kind"] = "nonsense_objective"
    with pytest.raises(ValueError, match="objective.kind"):
        s.from_json(unknown_kind)

    missing = json.loads(json.dumps(good))
    del missing["objective"]["coverage_quantifier"]
    with pytest.raises(ValueError, match="coverage_quantifier"):
        s.from_json(missing)

    bad_enum = json.loads(json.dumps(good))
    bad_enum["objective"]["coverage_quantifier"] = "sometimes_covering"
    with pytest.raises(ValueError, match="GlyphRelational.coverage_quantifier"):
        s.from_json(bad_enum)

    missing_transition = json.loads(json.dumps(good))
    del missing_transition["transition_model"]
    with pytest.raises(ValueError, match="transition_model"):
        s.from_json(missing_transition)
