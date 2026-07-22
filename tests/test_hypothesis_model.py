"""R95b step (vii) tests: the canned-instance MODEL stage's PURE helpers.

The env-driving path (LiveEnv / run_model_once) is exercised only under the real
Kaggle gate; here we pin the candidate provisioning, the deterministic shuffle,
the leak-clean serialized ask, the choice parser, the verifier gate mapping, and
the 2-of-3 model verdict — everything the dry-run and the audit record depend on.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from admorphiq.hypothesis_select import schema

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_hypothesis_model.py"
_SPEC = importlib.util.spec_from_file_location("probe_hypothesis_model", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["probe_hypothesis_model"] = _MOD
_SPEC.loader.exec_module(_MOD)


def test_instances_for_game_is_oracle_plus_same_game_mutants():
    """Purpose: the candidate set for a game is the oracle plus exactly the
    same-game mutants from schema.MUTANTS — no cross-game leakage, oracle first in
    the internal listing.

    Expected feedback: pass proves the model chooses among the game's own
    canonical hypotheses only. Fail means a wrong-game mutant leaked into the
    candidates (an invalid distractor) or the oracle went missing."""
    for game in ("ft09", "sc25"):
        named, oracle_name = instances_from(game)
        names = [n for n, _inst in named]
        assert oracle_name == f"{game}_oracle"
        assert names[0] == oracle_name
        assert all(n == oracle_name or n.startswith(f"{game}_") for n in names)
        # every same-game MUTANT is present; no other game's mutant is
        same_game_mutants = [m.name for m in schema.MUTANTS if m.name.startswith(f"{game}_")]
        assert set(names) == {oracle_name, *same_game_mutants}
        assert len(named) == 1 + len(same_game_mutants)  # 4 today (oracle + 3)


def test_shuffle_ids_deterministic_and_bijective():
    """Purpose: the id assignment is deterministic per game (sha256-keyed, no RNG)
    and a bijection onto I1..IN over the candidate names.

    Expected feedback: pass proves the same game always yields the same audit
    mapping and every candidate is reachable under exactly one id. Fail means the
    shuffle is unstable or drops/duplicates a candidate."""
    names = [n for n, _inst in instances_from("ft09")[0]]
    m1 = _MOD._shuffle_ids("ft09", names)
    m2 = _MOD._shuffle_ids("ft09", list(reversed(names)))
    assert m1 == m2  # deterministic, order-independent
    assert set(m1) == {f"I{i + 1}" for i in range(len(names))}
    assert sorted(m1.values()) == sorted(names)


def test_ask_prompt_has_no_provenance_leak():
    """Purpose: the assembled prompt exposes NO game id, no 'oracle'/'mutant'
    label, and no internal instance name — only neutral serialized specs +
    structural observations.

    Expected feedback: pass proves the model's pick cannot be driven by a leaked
    label instead of the mechanics. Fail means a provenance token reached the
    prompt and the selection result would be untrustworthy."""
    for game in ("ft09", "sc25"):
        gs = _MOD._replay_grounding(game)
        messages, mapping, _obs = _MOD.build_ask_prompt(game, gs)
        blob = (messages[0]["content"] + messages[1]["content"]).lower()
        for token in ("ft09", "sc25", "oracle", "mutant"):
            assert token not in blob, f"{game}: leaked {token!r}"
        for internal_name in mapping.values():
            assert internal_name.lower() not in blob, f"{game}: leaked instance name {internal_name!r}"


def test_ask_prompt_serializes_every_instance_round_trip():
    """Purpose: each candidate's serialized JSON in the prompt round-trips via
    schema.from_json back to the exact mapped instance.

    Expected feedback: pass proves the model sees a faithful, reconstructable
    specification of every candidate. Fail means serialization dropped/altered a
    field and the model would judge a corrupted hypothesis."""
    game = "ft09"
    gs = _MOD._replay_grounding(game)
    messages, mapping, _obs = _MOD.build_ask_prompt(game, gs)
    named = dict(instances_from(game)[0])
    user = messages[1]["content"]
    for cid, internal_name in mapping.items():
        expected = schema.to_neutral_json(named[internal_name])
        # the block for this id is `Ik:\n{json}`; find its object and parse it
        marker = f"{cid}:\n"
        start = user.index(marker) + len(marker)
        depth = 0
        for end in range(start, len(user)):
            depth += (user[end] == "{") - (user[end] == "}")
            if depth == 0 and user[end] == "}":
                parsed = json.loads(user[start:end + 1])
                break
        assert parsed == expected
        assert schema.from_json(parsed) == named[internal_name]  # round-trips to the instance


def test_parse_choice_accepts_valid_rejects_out_of_range():
    """Purpose: the choice parser accepts a valid guided-json answer and rejects an
    out-of-range or choice-less object.

    Expected feedback: pass proves a malformed/invalid model answer is caught (and
    would trigger the retry / NO_CHOICE record) rather than silently mapped. Fail
    means an invalid id could be executed."""
    ids = {"I1", "I2", "I3", "I4"}
    ok, err = _MOD._parse_choice('{"choice": "I2", "confidence": "high", "evidence": "footprint is 1"}', ids)
    assert err == "" and ok["choice"] == "I2" and ok["confidence"] == "high"
    bad, err = _MOD._parse_choice('{"choice": "I9"}', ids)
    assert bad is None and "not one of" in err
    none, err = _MOD._parse_choice("no json here", ids)
    assert none is None


def test_gate_blocks_footprint_contradicted_mutant_passes_oracle():
    """Purpose: the verifier gate — run on the LIVE-gathered evidence (single-cell
    footprints, no win frames) — CONTRADICTS a multi-cell-footprint mutant (never
    executes) and PASSes the oracle (executes).

    Expected feedback: pass proves the contract's 'UNKNOWN/CONTRADICTED never
    executes' gate is wired to the live evidence and the sound footprint claim.
    Fail means a footprint-contradicted hypothesis would be executed, or the
    oracle would be wrongly blocked."""
    game = "ft09"
    gs = _MOD._replay_grounding(game)  # single-cell footprints from gold clicks
    named = dict(instances_from(game)[0])

    oracle_verdict, oracle_exec = _MOD.gate_selected_instance(named[f"{game}_oracle"], gs, game)
    assert oracle_verdict == "PASS" and oracle_exec is True

    stencil_verdict, stencil_exec = _MOD.gate_selected_instance(
        named["ft09_stencil_transition"], gs, game
    )
    assert stencil_verdict == "CONTRADICTED" and stencil_exec is False


def test_model_verdict_needs_two_of_three():
    """Purpose: per-model success is >= 2 of 3 runs succeeding (the frozen 2/3).

    Expected feedback: pass proves the model gate does not over-report on a single
    lucky run. Fail means the 2/3 contract threshold is mis-wired."""
    pass_run = {"outcome": "PASS"}
    fail_run = {"outcome": "FAIL"}
    assert _MOD.model_verdict([pass_run, pass_run, fail_run]) == "PASS"
    assert _MOD.model_verdict([pass_run, fail_run, fail_run]) == "FAIL"
    assert _MOD.model_verdict([]) == "FAIL"


def test_echoing_llm_is_transparent_and_logs_ask_and_reply(capsys):
    """Purpose: the v7 observability wrapper returns the wrapped model's reply
    UNCHANGED (zero behaviour change) while logging every ask message and the raw
    reply under [live-ask]/[live-reply] prefixes.

    Expected feedback: pass proves the kernel-log instrumentation cannot perturb the
    byte-identical pick it is meant to explain. Fail means the wrapper altered the
    reply or failed to log the prompt/reply."""
    def fake(_messages):
        return '{"choice": "I3"}\nwith reasoning'

    wrapped = _MOD.echoing_llm(fake)
    reply = wrapped([{"role": "system", "content": "SYS"}, {"role": "user", "content": "line1\nline2"}])
    assert reply == '{"choice": "I3"}\nwith reasoning'  # returned UNCHANGED
    out = capsys.readouterr().out
    assert "[live-ask] SYS" in out and "[live-ask] line1" in out and "[live-ask] line2" in out
    assert '[live-reply] {"choice": "I3"}' in out and "[live-reply] with reasoning" in out


def instances_from(game):
    return _MOD.instances_for_game(game)


# ── step (viii) fill-mode tests ───────────────────────────────────────────────


def test_balanced_objects_extracts_nested_slot_json():
    """Purpose: the balanced-brace extractor recovers a nested slot object (the flat
    regex used in select mode cannot, because ink_operator_map nests).

    Expected feedback: pass proves the slot parser can read the model's answer even
    with a nested map. Fail means a valid fill answer would be dropped as unparsable."""
    text = 'prose {"coverage_quantifier": "all_covering", "ink_operator_map": {"0": "equal"}} tail'
    objs = _MOD._balanced_objects(text)
    assert objs and json.loads(objs[-1])["ink_operator_map"] == {"0": "equal"}


def test_parse_variant_validates_both_kinds():
    """Purpose: ASK 1 accepts a valid (objective_kind, transition_kind) and rejects
    an out-of-vocabulary kind.

    Expected feedback: pass proves the variant stage is enum-bound. Fail means the
    model could name a nonexistent variant that has no slot ask."""
    ok, err = _MOD.parse_variant('{"objective_kind": "glyph_relational", "transition_kind": "ordered_cycle"}')
    assert err == "" and ok["objective_kind"] == "glyph_relational"
    bad, err = _MOD.parse_variant('{"objective_kind": "spline", "transition_kind": "ordered_cycle"}')
    assert bad is None and "objective_kind" in err


def test_parse_slots_glyph_enforces_inks_quantifier_and_phase_count():
    """Purpose: ASK 2 (glyph) requires a valid coverage_quantifier, an operator for
    every observed ink, and exactly n_phases guard lists over the closed guard set.

    Expected feedback: pass proves the slot answer is fully validated before
    assembly (the retry's trigger). Fail means a malformed slot set could reach
    from_json or execution."""
    def slot(cq="all_covering", inkmap='"0": "equal", "2": "differ"', guards='[], ["layout_replaced"]'):
        return f'{{"coverage_quantifier": "{cq}", "ink_operator_map": {{{inkmap}}}, "phase_guards": [{guards}]}}'

    slots, err = _MOD.parse_slots(slot(), "glyph_relational", [0, 2], 2)
    assert err == "" and slots["ink_operator_map"] == {0: "equal", 2: "differ"}
    _bad, err = _MOD.parse_slots(slot(inkmap='"0": "equal"'), "glyph_relational", [0, 2], 2)
    assert "ink_operator_map[2]" in err  # missing an observed ink
    _bad, err = _MOD.parse_slots(slot(), "glyph_relational", [0, 2], 3)
    assert "phase_guards" in err  # wrong phase count
    _bad, err = _MOD.parse_slots(slot(guards='[], ["teleport"]'), "glyph_relational", [0, 2], 2)
    assert "phase_guards[1]" in err  # unknown guard kind


def test_assemble_from_slots_round_trips_to_a_verifier_passing_instance():
    """Purpose: the harness assembles (variant + model slots + harness values) into a
    CellStateHypothesis that the verifier PASSes on live single-cell footprints, and
    ft09's decoy-reveal guard survives assembly.

    Expected feedback: pass proves fill mode reconstructs a sound, executable
    hypothesis from the model's structural choices. Fail means the assembly path
    drops the guard (ft09 idx1 would never reveal) or produces a rejected instance."""
    gs = _MOD._replay_grounding("ft09")
    harness = _MOD.harness_measured_values(gs, "ft09")
    harness["order"] = [9, 8, 12]  # the live cycle (replay has none)
    slots = {"coverage_quantifier": "all_covering", "ink_operator_map": {0: "equal", 2: "differ"},
             "phase_guards": [[], ["layout_replaced"]]}
    inst = _MOD.assemble_instance("glyph_relational", "ordered_cycle", slots, harness, [0, 2])
    neutral = schema.to_neutral_json(inst)
    assert [g["kind"] for g in neutral["phases"][1]["guard"]] == ["layout_replaced"]
    verdict, executable = _MOD.gate_selected_instance(inst, gs, "ft09")
    assert verdict == "PASS" and executable is True


def test_fill_ask_prompts_have_no_provenance_leak():
    """Purpose: BOTH fill asks (variant + slots) expose no game id / oracle / mutant
    label; the harness-measured values shown are allowed (they are the model's
    ground truth by design).

    Expected feedback: pass proves the generation channel cannot be steered by a
    leaked label. Fail means a provenance token reached a fill prompt."""
    for game in ("ft09", "sc25"):
        gs = _MOD._replay_grounding(game)
        variant = _MOD.build_variant_ask(gs, game)
        objective_kind = _MOD._oracle_variant(game)[0]
        slots = _MOD.build_slot_ask(gs, game, objective_kind)
        blob = " ".join(mm["content"] for mm in (*variant, *slots)).lower()
        for token in ("ft09", "sc25", "oracle", "mutant"):
            assert token not in blob, f"{game}: leaked {token!r}"


def test_fill_instance_two_stage_with_one_retry():
    """Purpose: the two-stage fill drives ASK 1 then ASK 2, and a first invalid slot
    answer triggers exactly ONE retry that then succeeds — recording the variant,
    the slots, assembly_valid, and retries=1.

    Expected feedback: pass proves the error-feedback retry channel works end-to-end
    without an env/LLM. Fail means the retry is not wired or the record is wrong."""
    # sc25 (pattern_reference + binary_flip) needs no live cycle to assemble, so the
    # retry flow can be exercised from a replayed grounding.
    gs = _MOD._replay_grounding("sc25")
    guards = '[], ["stable_for_reads", "roles_state_equal"]'
    scripted = iter([
        '{"objective_kind": "pattern_reference", "transition_kind": "binary_flip", "confidence": "high"}',
        f'{{"preview_interpretation": "NOPE", "phase_guards": [{guards}]}}',  # invalid -> triggers retry
        f'{{"preview_interpretation": "xor_exact", "phase_guards": [{guards}]}}',
    ])

    def llm(_messages):
        return next(scripted)

    record = {}
    inst = _MOD.fill_instance(gs, "sc25", llm, record)
    assert inst is not None
    assert record["variant_choice"] == {"objective_kind": "pattern_reference", "transition_kind": "binary_flip"}
    assert record["assembly_valid"] is True and record["retries"] == 1
    assert record["slot_values"]["preview_interpretation"] == "xor_exact"


def test_unsupported_variant_combination_is_typed_not_a_crash():
    """Purpose: a model-assembled variant the compiler cannot plan (glyph objective
    + binary-flip transition) is detected by ``compilable`` as False, so the gate
    records UNSUPPORTED_COMBINATION instead of crashing; a supported combo is True.

    Expected feedback: pass proves the harness-crash defect (rc=1 killing the whole
    case) is closed as a typed per-run failure. Fail means an unsupported pick would
    still raise out of execute_instance."""
    gs = _MOD._replay_grounding("ft09")
    harness = _MOD.harness_measured_values(gs, "ft09")
    harness["order"] = [9, 8, 12]
    slots = {"coverage_quantifier": "all_covering", "ink_operator_map": {0: "equal", 2: "differ"},
             "phase_guards": [[], ["layout_replaced"]]}
    supported = _MOD.assemble_instance("glyph_relational", "ordered_cycle", slots, harness, [0, 2])
    unsupported = _MOD.assemble_instance("glyph_relational", "binary_flip", slots, harness, [0, 2])
    assert _MOD.compilable(supported, gs) is True
    assert _MOD.compilable(unsupported, gs) is False


def test_footprint_evidence_uses_unambiguous_prose_not_arrow_notation():
    """Purpose: the click-footprint evidence is stated as unambiguous prose
    ("<M> clicks changed exactly <N> cell(s)"), NOT the "Ncell(s)->Mclick(s)"
    notation gemma4 misparsed (swapping cell-count and click-count, reading a
    single-cell effect as multi-cell — the v7-diagnosed sc25 effect_matrix cause).

    Expected feedback: pass proves the swappable notation is gone from both games.
    Fail means it regressed and would re-break the transition read."""
    for game in ("ft09", "sc25"):
        summary = _MOD.live_observation_summary(_MOD._replay_grounding(game), game)
        assert "changed exactly 1 cell each" in summary  # the clear single-cell reading
        assert "->" not in summary and "cell(s)" not in summary  # no swappable notation


def test_observation_summary_omits_the_click_style_and_colour_count_lines():
    """Purpose: the observation summary carries NO click-style / distinct-colours
    line — MEASURED (fill v1/v3/v4) to corrupt the model's transition pick in every
    wording, and redundant with the harness transition auto-pairing.

    Expected feedback: pass proves the measured-harmful evidence line is gone from
    both games while the structural facts (cells / footprints / markers / pattern)
    remain. Fail means the line regressed back in and would re-break sc25."""
    for game in ("ft09", "sc25"):
        summary = _MOD.live_observation_summary(_MOD._replay_grounding(game), game).lower()
        assert "distinct colour" not in summary
        assert "selection colour" not in summary
        assert "no separate selection step" not in summary
        assert "interactive cells detected" in summary  # the structural facts stay
        for token in ("ft09", "sc25", "oracle"):
            assert token not in summary


def test_fill_auto_pairs_the_compilable_transition_to_the_objective():
    """Purpose: a model that picks the observable objective but an incompatible
    transition (glyph_relational + binary_flip) has the transition AUTO-PAIRED to
    the compilable one (ordered_cycle), with the model's original pick recorded —
    the ft09 fill fix, since cycle-vs-flip is not cheaply observable.

    Expected feedback: pass proves ft09 fill no longer fails on an unobservable
    transition mismatch. Fail means the auto-pairing is not applied and the run
    would hit UNSUPPORTED_COMBINATION."""
    gs = _MOD._replay_grounding("ft09")
    guards = '[], ["layout_replaced"]'
    inkmap = '"0": "equal", "2": "differ"'
    scripted = iter([
        '{"objective_kind": "glyph_relational", "transition_kind": "binary_flip", "confidence": "high"}',
        f'{{"coverage_quantifier": "all_covering", "ink_operator_map": {{{inkmap}}}, "phase_guards": [{guards}]}}',
    ])

    def llm(_messages):
        return next(scripted)

    record = {"colour_variety": None}
    # Auto-pairing happens right after the variant ask (before assembly), so the
    # recorded variant reflects the compilable transition even though this replay
    # grounding has no acquired cycle for the ordered_cycle to assemble against.
    _MOD.fill_instance(gs, "ft09", llm, record)
    assert record["variant_choice"]["transition_kind"] == "ordered_cycle"  # auto-paired
    assert record.get("model_transition") == "binary_flip"  # original model pick recorded


def test_effect_matrix_pick_is_not_auto_paired_and_reaches_the_gate():
    """Purpose: an empirical_effect_matrix transition is an OBSERVABLE multi-cell
    claim — the boundary says it must STAND as chosen (not paired away to the
    objective's compatible transition) so it flows to the verifier's footprint gate.

    Expected feedback: pass proves the auto-pairing is confined to the unobservable
    {ordered_cycle, binary_flip} pair and the discriminative footprint claim / live
    catch is preserved. Fail means effect_matrix was silently erased — weakening the
    safety layer the experiment relies on."""
    gs = _MOD._replay_grounding("ft09")
    guards = '[], ["layout_replaced"]'
    inkmap = '"0": "equal", "2": "differ"'
    scripted = iter([
        '{"objective_kind": "glyph_relational", "transition_kind": "empirical_effect_matrix", "confidence": "high"}',
        f'{{"coverage_quantifier": "all_covering", "ink_operator_map": {{{inkmap}}}, "phase_guards": [{guards}]}}',
    ])

    def llm(_messages):
        return next(scripted)

    record = {"colour_variety": None}
    _MOD.fill_instance(gs, "ft09", llm, record)
    assert record["variant_choice"]["transition_kind"] == "empirical_effect_matrix"  # STANDS
    assert "model_transition" not in record  # not a correction — the pick was honoured
