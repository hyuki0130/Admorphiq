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


def test_movement_instances_are_oracle_plus_six_frozen_mutants():
    """Purpose: the m0r0 movement candidate set is the oracle plus exactly the 6 frozen
    MUTANTS_MOVEMENT, with the oracle internal name, and NO auto-pairing (all 7 stand as
    distinct candidates for the verifier to gate).

    Expected feedback: pass proves the movement SELECT provisions the same-family
    candidates only. Fail means a mutant is missing / duplicated or the oracle is absent."""
    named, oracle_name = _MOD.movement_instances()
    names = [n for n, _inst in named]
    assert oracle_name == "m0r0_oracle"
    assert oracle_name in names
    assert len(named) == 7  # oracle + 6 frozen movement mutants
    assert len(set(names)) == 7  # no duplicates


def test_movement_observation_is_hash_robust_structural_prose():
    """Purpose: the movement observation cites STRUCTURE (symmetric-row / antisymmetric-
    column / merge / independent desync), never an action number as semantics — the R96
    (iii) hash-variable-action finding applied to the evidence.

    Expected feedback: pass proves the prose is hash-robust (no 'action N'/'press N'
    numbering the live hash could rotate). Fail means a hash-specific token leaked into
    the model-facing evidence."""
    text = _MOD.movement_observation_summary(_MOD.CANNED_M0R0_FACTS).lower()
    assert "symmetric" in text and "antisymmetric" in text and "merge" in text
    assert "independently" in text
    for token in ("action 1", "action 2", "press 1", "press 2", "action6", "action1"):
        assert token not in text


def test_movement_ask_prompt_is_leak_clean_and_serializes_all_candidates():
    """Purpose: the movement SELECT ask serializes every candidate under the I1..IN
    shuffle with NO oracle/mutant/game-id leakage in the model-facing text, and the
    id->name mapping is complete.

    Expected feedback: pass proves the model-facing prompt is neutral and complete (the
    Kaggle-safety invariant). Fail means a name/label/game-id leaked or a candidate was
    dropped."""
    messages, mapping, _obs = _MOD.build_movement_ask_prompt(_MOD.CANNED_M0R0_FACTS)
    assert set(mapping) == {f"I{i + 1}" for i in range(7)}
    blob = (messages[0]["content"] + messages[1]["content"]).lower()
    for banned in ("oracle", "mutant", "m0r0"):
        assert banned not in blob


def test_movement_fill_asks_exactly_the_three_frozen_model_slots():
    """Purpose: the movement FILL asks request EXACTLY the frozen MOVEMENT_MODEL_SELECTED_
    SEMANTICS — the actor ROLE-BINDING (role_a), the completion RELATION, and the phase
    GUARDS — and NEVER a harness-measured field (collision_policy, terminal_cells,
    per_action_deltas, occupancy). Both asks are leak-clean (no game id / oracle / mutant).

    Expected feedback: pass proves FILL asks the full-and-only frozen model-selected surface
    (actors IS a model slot, not harness). Fail means a harness-measured slot leaked into a
    model ask, or a frozen model slot (the role-binding) was wrongly dropped."""
    variant = _MOD.build_movement_variant_ask(_MOD.CANNED_M0R0_FACTS)
    slots = _MOD.build_movement_slot_ask(_MOD.CANNED_M0R0_FACTS, "same_cell")
    blob = " ".join(m["content"] for m in variant + slots).lower()
    for banned in ("collision_policy", "terminal_cells", "per_action_deltas", "occupancy",
                   "oracle", "mutant", "m0r0"):
        assert banned not in blob
    v_user = variant[1]["content"].lower()
    assert "relation" in v_user and "role_a" in v_user  # both objective model slots asked
    assert "phase_guards" in slots[1]["content"].lower()  # the guard model slot asked


def test_parse_movement_variant_and_slots_validate_closed_vocabularies():
    """Purpose: the FILL parsers accept the model's model_selected values only from their
    closed vocabularies — relation in {same_cell, adjacent, overlap}, phase_guards a list
    of exactly n_phases guard-name lists from the known guard set — and reject the rest.

    Expected feedback: pass proves a hallucinated relation / guard name / wrong phase count
    is caught before assembly. Fail means an out-of-vocabulary value would reach the schema."""
    good_v, err_v = _MOD.parse_movement_variant(
        '{"relation": "same_cell", "role_a": "A", "confidence": "high"}')
    assert err_v == "" and good_v["relation"] == "same_cell" and good_v["role_a"] == "A"
    bad_v, err_bad = _MOD.parse_movement_variant('{"relation": "teleport", "role_a": "A"}')
    assert bad_v is None and "teleport" in err_bad
    # the role-binding is also a closed vocabulary — a bad role_a is rejected
    bad_role, err_role = _MOD.parse_movement_variant('{"relation": "same_cell", "role_a": "Q"}')
    assert bad_role is None and "role_a" in err_role
    good_s, err_s = _MOD.parse_movement_slots('{"phase_guards": [["level_advanced"]]}', 1)
    assert err_s == "" and good_s["phase_guards"] == [["level_advanced"]]
    bad_s, _ = _MOD.parse_movement_slots('{"phase_guards": [["not_a_guard"]]}', 1)
    assert bad_s is None
    wrong_count, _ = _MOD.parse_movement_slots('{"phase_guards": [[], []]}', 1)
    assert wrong_count is None


def test_fill_movement_instance_assembles_a_compilable_hypothesis():
    """Purpose: fill_movement_instance builds a MovementHypothesis from the model's
    (relation + phase guards) plus the HARNESS-measured transition, and the result both
    round-trips through the schema and DISPATCHES to a movement plan (compilable) —
    proving the fill output is executable, not just well-typed.

    Expected feedback: pass proves the assembled fill instance is compilable end to end.
    Fail means the fill assembly produced a non-compilable objective/transition pairing."""
    from admorphiq.hypothesis_select import schema_movement
    from admorphiq.hypothesis_select.compiler_movement import (
        CoupledGridStepPlan,
        compile_movement_hypothesis,
    )
    from admorphiq.hypothesis_select.grounding import GroundingService

    inst = _MOD.fill_movement_instance("same_cell", "A", [["level_advanced"]])
    assert isinstance(inst, schema_movement.MovementHypothesis)
    assert inst.objective.relation == "same_cell"
    assert inst.objective.actors == ("actor_a", "actor_b")  # role_a='A' keeps grounding order
    assert inst.phases[0].guard[0].KIND == "level_advanced"
    plan = compile_movement_hypothesis(inst, GroundingService())
    assert isinstance(plan, CoupledGridStepPlan)  # dispatched, did not raise
    # role_a='B' SWAPS the role-binding (a frozen model slot, not harness-fixed)
    assert _MOD.fill_movement_instance("same_cell", "B", [["level_advanced"]]).objective.actors == (
        "actor_b", "actor_a")
    # a WRONG relation still assembles (it flows to the verifier / execution to be caught)
    assert _MOD.fill_movement_instance("adjacent", "A", [["level_advanced"]]).objective.relation == "adjacent"


def test_movement_fill_verifies_pass_on_merge_evidence_and_contradicts_without():
    """Purpose: a correctly-filled m0r0 instance (same_cell + role_a + level_advanced guard)
    must verify PASS against evidence that OBSERVED the merge, and still CONTRADICT when no
    merge was observed. Pins the R96 (vii) kernel-2 harness defect: the evidence-gathering
    solve merged the actors but ``merge_observed`` was False (plan stepping feeds via
    ``feed()``, which skips the merge detector), so a CORRECT same_cell fill was CONTRADICTED.

    Expected feedback: pass proves the fill->verify path accepts a correct fill once the merge
    is observed (both role-bindings, symmetric-equivalent) AND still rejects an unmerged
    same_cell claim — the fix supplies the missing observation without weakening the verifier.
    Fail = the merge-evidence gap regressed (correct fill CONTRADICTED) or the same_cell
    terminal check was over-loosened (unmerged PASS)."""
    from dataclasses import replace

    from admorphiq.hypothesis_select.verifier_movement import (
        MovementEvidence,
        verify_with_evidence,
    )

    mirror = {
        ("actor_a", 1): (-1, 0), ("actor_b", 1): (-1, 0), ("actor_a", 2): (1, 0),
        ("actor_b", 2): (1, 0), ("actor_a", 3): (0, -1), ("actor_b", 3): (0, 1),
        ("actor_a", 4): (0, 1), ("actor_b", 4): (0, -1),
    }
    ev = MovementEvidence(
        deltas=mirror, collision_obs=0, merge_observed=True, partner_moves=True,
        hazard_cells=frozenset(),
    )
    inst = _MOD.fill_movement_instance("same_cell", "A", [["level_advanced"]])
    v = verify_with_evidence(inst, ev)
    assert v.verdict.name == "PASS" and v.objective.name == "PASS" and v.transition.name == "PASS"
    # role_a='B' is symmetric-equivalent under same_cell — also PASSes
    inst_b = _MOD.fill_movement_instance("same_cell", "B", [["level_advanced"]])
    assert verify_with_evidence(inst_b, ev).verdict.name == "PASS"
    # NO merge observed -> the same_cell terminal is CONTRADICTED (evidence required, not loosened)
    assert verify_with_evidence(inst, replace(ev, merge_observed=False)).objective.name == "CONTRADICTED"


def test_movement_merge_seen_detects_named_event_or_coalesced_actors():
    """Purpose: _movement_merge_seen reports a merge from EITHER the grounding's named merge
    event OR the actor parse collapsing to a single coalesced cell — the coalesced-cell signal
    is what the oracle-solve evidence-gathering relies on (its feed()-based stepping never fires
    the named event). Pins the observation the kernel-2 fix added.

    Expected feedback: pass proves both merge signals are recognised and two distinct actor
    cells are NOT read as a merge. Fail = the fix mis-detects (false merge on two actors, or
    misses a genuine coalescence)."""
    from admorphiq.hypothesis_select.grounding import UNKNOWN, Grounded

    class _StubGs:
        def __init__(self, merge, n_cells):
            self._merge, self._n = merge, n_cells

        def movement_merge_event(self):
            return Grounded(("actor_a", "actor_b"), "high") if self._merge else UNKNOWN

        def movement_actors(self):
            cells = [("actor_a", (2, 6)), ("actor_b", (5, 5))][: self._n]
            return Grounded(cells, "high")

    assert _MOD._movement_merge_seen(_StubGs(merge=True, n_cells=2)) is True   # named event
    assert _MOD._movement_merge_seen(_StubGs(merge=False, n_cells=1)) is True  # coalesced to one cell
    assert _MOD._movement_merge_seen(_StubGs(merge=False, n_cells=2)) is False  # two distinct actors


def test_movement_verdict_counts_the_hazard_as_wall_equivalence_pick():
    """Purpose: the SELECT scoring credits BOTH oracle-equivalence-class members — the
    exact oracle AND the execution-equivalent hazard_as_wall (correction A) — toward the
    >=2/3 gate, with the equivalence noted in the audit; a non-equivalent mutant does not
    count, and the pick is never dropped/auto-paired.

    Expected feedback: pass proves a hazard_as_wall pick counts (idx0 execution-equivalence)
    while a real mutant does not. Fail means the equivalence-class gate mis-scored a pick."""
    assert _MOD._MOVEMENT_ORACLE_EQUIV == {"m0r0_oracle", "m0r0_hazard_as_wall"}
    ok_o, note_o = _MOD.movement_select_credit("m0r0_oracle")
    ok_h, note_h = _MOD.movement_select_credit("m0r0_hazard_as_wall")
    ok_m, _ = _MOD.movement_select_credit("m0r0_all_or_nothing_blocking")
    assert ok_o and ok_h and not ok_m
    assert "equivalence noted" in note_h and note_o == "exact-oracle"
    runs = [
        {"mapped_instance": "m0r0_oracle"},
        {"mapped_instance": "m0r0_hazard_as_wall"},
        {"mapped_instance": "m0r0_adjacent_relation"},
    ]
    assert _MOD.movement_model_verdict(runs) == "PASS"  # 2 of 3 are equivalence-class
    assert _MOD.movement_model_verdict(runs[2:]) == "FAIL"  # only the non-equivalent mutant


def test_movement_select_credit_rejects_non_equivalent_and_missing_picks():
    """Purpose: movement_select_credit counts ONLY the equivalence class (oracle,
    hazard_as_wall); a genuine distractor mutant and a None (no-choice) never count —
    the companion of the equivalence-class verdict test above.

    Expected feedback: pass proves non-equivalent and missing picks are honest misses. Fail
    means the gate would over-credit a distractor or a failed ask."""
    for miss in ("m0r0_adjacent_relation", "m0r0_single_actor_motion", None):
        assert _MOD.movement_select_credit(miss)[0] is False
