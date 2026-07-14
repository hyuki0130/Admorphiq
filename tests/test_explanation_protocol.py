"""Tests for the R58 EXPLANATION layer (Navigation Vertical Slice v0):
``src/admorphiq/explanation/protocol.py`` (state machine) and
``scripts/explanation_lint.py`` (packaging quarantine).

These pin the four behavioral guarantees the verdict
(``docs/r58_codex_explanation_layer_20260715.md``) requires of the
enforced protocol — an invalid declaration spends zero actions (no kernel
call), a valid declaration auto-invokes the mapped kernel, an arbitrary
result "bypass" (skipping CONSUME's execute/reject contract) is rejected,
and a fired falsifier decommits the intent to a named recovery state — plus
an end-to-end happy path against the REAL kernel (not a stub) and a lint
smoke test proving the runtime package stays quarantined from public-game
identity.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from explanation_lint import (  # noqa: E402
    discover_runtime_paths,
    lint_file,
    lint_text,
)

from admorphiq.explanation.protocol import (  # noqa: E402
    CONSUME,
    FILL,
    FUNNEL_INTENT_ABANDONED,
    FUNNEL_INTENT_SELECTED,
    FUNNEL_KERNEL_INVOKED,
    FUNNEL_PREDICTION_VERIFIED,
    FUNNEL_RESULT_CONSUMED,
    FUNNEL_SLOTS_VALID,
    SELECT,
    VERIFY,
    ExplanationProtocol,
    HandleStore,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXPLANATION_DIR = _REPO_ROOT / "src" / "admorphiq" / "explanation"


# ----- fixtures ----------------------------------------------------------------
def _grid_maze() -> tuple[list[list[int]], tuple[int, int], tuple[int, int]]:
    """A tiny 3x3 all-passable grid: start (0,0), goal (0,2). A trivial
    two-step rightward path so ``moves`` has a known, checkable length."""
    passable = [[1, 1, 1] for _ in range(3)]
    return passable, (0, 0), (0, 2)


def _new_protocol() -> tuple[ExplanationProtocol, HandleStore]:
    store = HandleStore()
    protocol = ExplanationProtocol.for_navigation_v0(resolve=store)
    return protocol, store


def _seed_reachable_navigation(store: HandleStore) -> dict:
    passable, start, goal = _grid_maze()
    store.put("region:7", {"color": 3, "cells": frozenset({start})})
    store.put("cell:12", start)
    store.put("cell:31", goal)
    store.put("mask:4", passable)
    # (dr, dc) -> action id; only rightward is exercised by this fixture's path.
    store.put("action_map:2", {(0, 1): "RIGHT", (0, -1): "LEFT", (1, 0): "DOWN", (-1, 0): "UP"})
    store.put("goal:3", "arrival")
    return {
        "intent": "navigation",
        "mover": "region:7",
        "start": "cell:12",
        "goals": ["cell:31"],
        "passable_mask": "mask:4",
        "action_map": "action_map:2",
        "goal_hypothesis": "goal:3",
        "support": ["evidence:1", "evidence:2"],
        "falsifier": "mover_does_not_follow_planned_step",
    }


def _select_navigation(protocol: ExplanationProtocol) -> dict:
    return protocol.select({"intent": "navigation", "support": ["evidence:1"]})


# ----- 1. invalid declaration spends zero actions -------------------------------
def test_invalid_select_declaration_is_a_repair_no_state_change():
    """Purpose: a schema-invalid SELECT_INTENT (unknown-shaped field, intent not
    in the dynamic allowlist) must not advance past SELECT and must not touch
    any kernel — the verdict's "invalid declarations cause no environment
    action" guarantee, at the SELECT stage.

    Expected feedback: a pass proves garbage in never reaches FILL/COMPUTE; a
    fail means a malformed declaration could silently advance the state
    machine.
    """
    protocol, _ = _new_protocol()
    result = protocol.select({"intent": "teleport_home", "support": []})
    assert result["ok"] is False
    assert "repair" in result
    assert protocol.state == SELECT
    assert protocol._plan is None


def test_invalid_fill_declaration_spends_zero_actions_no_kernel_call():
    """Purpose: a schema-invalid FILL_INTENT (missing required semantic slots)
    must return a repair packet WITHOUT invoking the mapped kernel — this is
    the central "invalid declaration -> zero actions, zero kernel calls"
    guarantee from verdict §2.3, and the one most load-bearing for the
    adoption-funnel's "kernel automatically invoked" metric to be meaningful.

    Expected feedback: a pass proves the FUNNEL_KERNEL_INVOKED event never
    fires on a bad declaration; a fail means an incomplete slot set could
    still burn a real BFS call (or worse, be silently treated as valid).
    """
    protocol, store = _new_protocol()
    _select_navigation(protocol)
    assert protocol.state == FILL

    incomplete = {"intent": "navigation", "mover": "region:7"}  # missing every other required slot
    result = protocol.fill(incomplete)

    assert result["ok"] is False
    assert "repair" in result
    assert protocol.state == FILL  # did not advance to CONSUME
    assert not any(e["event"] == "kernel_invoked" for e in protocol.telemetry)
    assert not any(e["funnel"] == FUNNEL_KERNEL_INVOKED for e in protocol.telemetry)


def test_fill_called_out_of_stage_is_rejected_without_side_effects():
    """Purpose: calling fill() before select() (or consume() before a plan
    exists) must be a no-op repair, not a crash or a silent state jump — the
    state machine must reject out-of-order calls at every stage boundary.

    Expected feedback: a pass proves the harness can never accidentally skip
    a stage; a fail would let a malformed client bypass SELECT entirely.
    """
    protocol, store = _new_protocol()
    decl = _seed_reachable_navigation(store)
    result = protocol.fill(decl)  # never selected navigation first
    assert result["ok"] is False
    assert protocol.state == SELECT


# ----- 2. valid declaration auto-invokes ----------------------------------------
def test_valid_fill_declaration_auto_invokes_the_real_kernel():
    """Purpose: a schema-valid, referentially-resolvable FILL_INTENT must
    automatically call grid_shortest_path/path_to_moves (verdict §2.3 —
    "the harness validates references and automatically calls the mapped
    kernel") with NO separate model turn for COMPUTE. Uses the REAL kernel
    (not a stub) against a tiny synthetic grid so a genuine BFS result is
    checked, not just that some function was called.

    Expected feedback: a pass proves FILL->COMPUTE is a single atomic
    transition producing a real, checkable plan; a fail means either the
    kernel wasn't invoked or its result wasn't wired into a consumable plan.
    """
    protocol, store = _new_protocol()
    _select_navigation(protocol)
    decl = _seed_reachable_navigation(store)

    result = protocol.fill(decl)

    assert result["ok"] is True
    assert result["stage"] == CONSUME
    assert protocol.state == CONSUME
    assert protocol._plan is not None
    assert protocol._plan["moves"] == ["RIGHT", "RIGHT"]  # (0,0)->(0,2) on an all-passable 3x3 grid
    kernel_events = [e for e in protocol.telemetry if e["event"] == "kernel_invoked"]
    assert len(kernel_events) == 1
    assert any(e["event"] == "kernel_result" and e["path_len"] == 3 for e in protocol.telemetry)


def test_unreachable_goal_is_a_kernel_contradiction_not_a_repair():
    """Purpose: a schema-valid declaration whose goal is genuinely unreachable
    under the declared passable mask is different from a schema-invalid one —
    the kernel IS invoked (it's the kernel that discovers the contradiction),
    but there is nothing to consume, so the harness auto-returns to SELECT
    instead of offering a dead CONSUME turn.

    Expected feedback: a pass proves unreachable-goal handling is distinct
    from schema repair (kernel_invoked fires); a fail would either silently
    fabricate a plan or misreport this as a schema error.
    """
    protocol, store = _new_protocol()
    _select_navigation(protocol)
    decl = _seed_reachable_navigation(store)
    # Wall off the goal cell entirely.
    store.put("mask:4", [[1, 1, 0], [1, 1, 0], [1, 1, 0]])

    result = protocol.fill(decl)

    assert result["ok"] is True
    assert result["stage"] == SELECT
    assert result["contradiction"] == "unreachable"
    assert protocol.state == SELECT
    assert any(e["event"] == "kernel_invoked" for e in protocol.telemetry)
    assert any(e["event"] == "kernel_contradiction" for e in protocol.telemetry)


# ----- 3. result bypass rejected -------------------------------------------------
def _protocol_at_consume() -> tuple[ExplanationProtocol, HandleStore]:
    protocol, store = _new_protocol()
    _select_navigation(protocol)
    decl = _seed_reachable_navigation(store)
    protocol.fill(decl)
    assert protocol.state == CONSUME
    return protocol, store


def test_consume_rejects_unrecognized_decision_shape():
    """Purpose: CONSUME_RESULT accepts ONLY {"decision":"execute",...} or
    {"decision":"reject",...} (verdict §2.4) — any other shape (a bare
    action, an extra field, a missing plan_id) is a rejected bypass attempt
    that must not advance the state or return an action to perform.

    Expected feedback: a pass proves the "tool result was available but the
    model ignored it and did something else instead" failure mode is closed
    at the schema level; a fail means an arbitrary payload could sneak an
    action through.
    """
    protocol, _ = _protocol_at_consume()
    plan_id = protocol._plan["plan_id"]

    bypass = {"action": "RIGHT", "plan_id": plan_id}  # not a recognized decision envelope
    result = protocol.consume(bypass)

    assert result["ok"] is False
    assert protocol.state == CONSUME
    assert any(e["event"] == "bypass_rejected" for e in protocol.telemetry)


def test_consume_rejects_stale_or_foreign_plan_id():
    """Purpose: an execute/reject decision referencing a plan_id that is not
    the live plan (stale from a prior turn, or fabricated) must be rejected —
    a result cannot be bypassed by attaching an unrelated/incorrect plan_id.

    Expected feedback: a pass proves plan identity is enforced, not just
    envelope shape; a fail would let a model "consume" a plan it never
    actually received.
    """
    protocol, _ = _protocol_at_consume()
    result = protocol.consume({"decision": "execute", "plan_id": "p999", "step": 0})
    assert result["ok"] is False
    assert protocol.state == CONSUME


def test_consume_rejects_out_of_order_step():
    """Purpose: executing step 1 before step 0 (skipping ahead) is a bypass —
    CONSUME only accepts the next unexecuted step of the live plan.

    Expected feedback: a pass proves steps cannot be skipped or replayed out
    of order; a fail would let a model execute a later step whose
    preconditions (the earlier steps' predicted effects) were never verified.
    """
    protocol, _ = _protocol_at_consume()
    plan_id = protocol._plan["plan_id"]
    result = protocol.consume({"decision": "execute", "plan_id": plan_id, "step": 1})
    assert result["ok"] is False
    assert protocol.state == CONSUME


def test_consume_execute_valid_step_returns_action_and_moves_to_verify():
    """Purpose: a well-formed execute decision for the live plan's next step is
    the ONE path that returns an action, and it moves the state to VERIFY —
    proving "use the result" is a real, distinct path from "reject".

    Expected feedback: a pass proves the happy path is reachable at all; a
    fail would mean even a correct declaration can never actually act.
    """
    protocol, _ = _protocol_at_consume()
    plan_id = protocol._plan["plan_id"]
    result = protocol.consume({"decision": "execute", "plan_id": plan_id, "step": 0})
    assert result["ok"] is True
    assert result["action"] == "RIGHT"
    assert protocol.state == VERIFY
    assert any(e["event"] == "result_consumed" for e in protocol.telemetry)


def test_consume_explicit_reject_is_accepted_and_returns_to_select():
    """Purpose: the OTHER valid CONSUME_RESULT path — explicitly rejecting a
    valid kernel result with a contradiction handle — must be accepted and
    must clear the plan, distinct from an invalid bypass.

    Expected feedback: a pass proves "reject" is a first-class outcome, not
    just "execute or garbage"; a fail would force every plan to be executed
    even when the model has evidence it's wrong.
    """
    protocol, _ = _protocol_at_consume()
    plan_id = protocol._plan["plan_id"]
    result = protocol.consume(
        {"decision": "reject", "plan_id": plan_id, "contradiction": "evidence:29", "next_intent": "unknown"}
    )
    assert result["ok"] is True
    assert result["stage"] == SELECT
    assert protocol.state == SELECT
    assert protocol._plan is None


# ----- 4. falsifier fires -> decommit + next-alternative state -------------------
def test_strong_falsifier_decommits_immediately_to_select():
    """Purpose: a single strong falsifier firing in VERIFY must decommit the
    intent immediately (no strike budget) and name the recovery transition
    from the playbook (``return_to_intent_selection`` -> SELECT) — the
    "every playbook must name the next alternative state" requirement.

    Expected feedback: a pass proves a strong contradiction can never be
    argued away by continuing the same plan; a fail would let the agent keep
    executing a plan already known to be wrong.
    """
    protocol, _ = _protocol_at_consume()
    plan_id = protocol._plan["plan_id"]
    protocol.consume({"decision": "execute", "plan_id": plan_id, "step": 0})
    assert protocol.state == VERIFY

    result = protocol.verify({"a_different_region_displaces_than_the_declared_mover": True})

    assert result["ok"] is True
    assert result["decommit"] is True
    assert result["recovery"] == "return_to_intent_selection"
    assert protocol.state == SELECT
    assert protocol._plan is None
    events = [e for e in protocol.telemetry if e["event"] == "strong_falsifier_decommit"]
    assert len(events) == 1
    assert events[0]["funnel"] == FUNNEL_INTENT_ABANDONED


def test_weak_falsifier_spends_strike_budget_before_decommit():
    """Purpose: a weak falsifier does NOT decommit on the first occurrence — it
    spends one strike of the playbook's ``weak_strikes`` budget (2, per
    ``playbooks/navigation.yaml``) and returns to CONSUME for a retry; only
    exhausting the budget decommits.

    Expected feedback: a pass proves transient/noisy weak evidence doesn't
    prematurely abandon a plan; a fail means either weak falsifiers are
    ignored entirely or they decommit too eagerly (both measured failure
    modes for schema-less prose falsification in the verdict).
    """
    protocol, _ = _protocol_at_consume()
    plan_id = protocol._plan["plan_id"]

    protocol.consume({"decision": "execute", "plan_id": plan_id, "step": 0})
    first = protocol.verify({"mover_does_not_follow_planned_step": True})
    assert first["stage"] == CONSUME
    assert protocol.state == CONSUME
    assert protocol._plan is not None  # not decommitted yet — one strike spent

    protocol.consume({"decision": "execute", "plan_id": plan_id, "step": 0})
    second = protocol.verify({"mover_does_not_follow_planned_step": True})
    assert second["decommit"] is True
    assert protocol.state == SELECT
    strike_events = [e for e in protocol.telemetry if e["event"] == "weak_falsifier_strike"]
    exhausted_events = [e for e in protocol.telemetry if e["event"] == "weak_budget_exhausted_decommit"]
    assert len(strike_events) == 1
    assert len(exhausted_events) == 1


def test_verified_prediction_advances_plan_and_eventually_completes():
    """Purpose: when no falsifier fires, VERIFY advances the plan step-by-step
    and finally clears it on completion — the non-falsifying happy path all
    the way through a 2-step plan.

    Expected feedback: a pass proves the full SELECT->FILL->CONSUME->VERIFY
    loop can complete a real plan end-to-end; a fail means even a perfectly
    correct execution never reaches a terminal state.
    """
    protocol, _ = _protocol_at_consume()
    plan_id = protocol._plan["plan_id"]
    assert protocol._plan["moves"] == ["RIGHT", "RIGHT"]

    protocol.consume({"decision": "execute", "plan_id": plan_id, "step": 0})
    r1 = protocol.verify({})
    assert r1["stage"] == CONSUME
    assert r1["next_step"] == 1
    assert protocol.state == CONSUME

    protocol.consume({"decision": "execute", "plan_id": plan_id, "step": 1})
    r2 = protocol.verify({})
    assert r2["complete"] is True
    assert protocol.state == SELECT
    assert protocol._plan is None
    verified_events = [e for e in protocol.telemetry if e["funnel"] == FUNNEL_PREDICTION_VERIFIED]
    assert len(verified_events) >= 2  # one per step + plan_complete


# ----- unknown escape route + telemetry funnel tagging ---------------------------
def test_unknown_intent_is_a_valid_escape_that_stays_in_select():
    """Purpose: 'unknown' must always be selectable (verdict §2/§6 — "the
    unknown/probe escape route is mandatory so a wrong family is never
    forced indefinitely") and must not require any evidence support.

    Expected feedback: a pass proves the escape hatch exists and needs no
    fabricated evidence; a fail would force every turn into a committed
    (possibly wrong) family.
    """
    protocol, _ = _new_protocol()
    result = protocol.select({"intent": "unknown", "support": []})
    assert result["ok"] is True
    assert result["intent"] == "unknown"
    assert protocol.state == SELECT


def test_telemetry_funnel_tags_cover_the_adoption_funnel_stages():
    """Purpose: every stage transition must be tagged with the verdict §7
    adoption-funnel stage it corresponds to, so a bench can compute the
    funnel metrics directly from telemetry without re-deriving them from raw
    transcripts.

    Expected feedback: a pass proves funnel stages 2 (intent selected), 3
    (slots valid), 4 (kernel invoked), 5 (result consumed), and 6 (prediction
    verified) are all observable in one full run; a fail means the funnel
    can't actually be measured from this class's output.
    """
    protocol, store = _new_protocol()
    _select_navigation(protocol)
    decl = _seed_reachable_navigation(store)
    protocol.fill(decl)
    plan_id = protocol._plan["plan_id"]
    protocol.consume({"decision": "execute", "plan_id": plan_id, "step": 0})
    protocol.verify({})

    funnels_seen = {e["funnel"] for e in protocol.telemetry}
    assert FUNNEL_INTENT_SELECTED in funnels_seen
    assert FUNNEL_SLOTS_VALID in funnels_seen
    assert FUNNEL_KERNEL_INVOKED in funnels_seen
    assert FUNNEL_RESULT_CONSUMED in funnels_seen
    assert FUNNEL_PREDICTION_VERIFIED in funnels_seen


# ----- bundled artifacts load + budget measurement --------------------------------
def test_for_navigation_v0_loads_the_shipped_bundle():
    """Purpose: the classmethod constructor must successfully load the real
    shipped schema/playbook files (not a test double) — proves the artifact
    tree and the loader agree on paths/shape.

    Expected feedback: a pass proves the packaged files are directly usable;
    a fail means the shipped bundle itself is broken, independent of any
    protocol logic.
    """
    protocol, _ = _new_protocol()
    assert protocol.allowed_intents == frozenset({"navigation", "unknown"})
    assert protocol.playbooks["navigation"]["id"] == "navigation.v1"
    assert protocol.fill_schemas["navigation"]["properties"]["intent"]["const"] == "navigation"


def test_playbook_serialized_size_is_within_the_500_token_injection_budget():
    """Purpose: verdict §5 caps an injected playbook at ~500 tokens. This repo
    has no tokenizer dependency, so — per team-lead's instruction — token
    count is estimated as chars/4 (a standard rough English/code estimate).
    Guards against the playbook silently growing past its injection budget.

    Expected feedback: a pass means the card fits the budget under the
    chars/4 estimate; a fail means either the card grew or the estimate
    needs revisiting before the next playbook is authored the same way.
    """
    playbook_path = _EXPLANATION_DIR / "playbooks" / "navigation.yaml"
    raw_text = playbook_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw_text)
    compact = json.dumps(parsed, separators=(",", ":"))
    assert len(compact) / 4 <= 500, f"compact playbook ~{len(compact) / 4:.0f} tokens > 500 budget"


# ----- 5. lint catches a seeded game-ID violation ----------------------------------
def test_lint_passes_on_the_real_shipped_artifacts():
    """Purpose: the quarantine lint must report zero violations on the actual
    files this task ships — the packaging gate has to be green on day one,
    not just theoretically capable of catching a problem.

    Expected feedback: a pass proves the shipped bundle is clean; a fail
    means a real artifact currently leaks something the verdict forbids.
    """
    results = [lint_file(p) for p in discover_runtime_paths()]
    assert results, "expected at least one runtime file to lint"
    failing = [r for r in results if not r.ok]
    assert failing == [], f"unexpected lint violations: {[(r.path.name, r.violations) for r in failing]}"


def test_lint_catches_a_seeded_game_id_violation():
    """Purpose: pins the lint's core detection contract — injecting a public
    game id (here, 'ft09', taken from an unrelated real public game) into
    otherwise-clean playbook-shaped text must be flagged as
    ``game_id_or_title``.

    Expected feedback: a pass proves the quarantine gate actually catches
    the exact failure mode it exists for; a fail means the lint is
    decorative.
    """
    clean = (_EXPLANATION_DIR / "playbooks" / "navigation.yaml").read_text(encoding="utf-8")
    seeded = clean + "\n# lesson carried over from ft09's toggle mechanic\n"

    clean_violations = lint_text(clean)
    seeded_violations = lint_text(seeded)

    assert clean_violations == []
    assert any(v.startswith("game_id_or_title") for v in seeded_violations)
    assert "'ft09'" in next(v for v in seeded_violations if v.startswith("game_id_or_title"))


def test_lint_catches_seeded_adapter_import_and_absolute_coordinate():
    """Purpose: pins the other two concrete quarantine signatures — a
    reference to the quarantined ``adapters25`` package, and a literal pixel
    coordinate pair — on otherwise-clean text.

    Expected feedback: a pass proves both signatures fire independently; a
    fail would mean one of the two heuristics is dead code.
    """
    adapter_leak = "roles:\n  hint: see admorphiq.adapters25.base for the pattern\n"
    coord_leak = "confirm:\n  probe: click at (12, 34) to test\n"

    assert any(v.startswith("adapter_import") for v in lint_text(adapter_leak))
    assert any(v.startswith("absolute_coordinate") for v in lint_text(coord_leak))
