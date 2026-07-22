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


def instances_from(game):
    return _MOD.instances_for_game(game)
