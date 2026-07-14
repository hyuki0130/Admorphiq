"""EXPLANATION layer: harness-enforced protocol compiler (R58, Navigation Vertical
Slice v0).

Implements the verdict's two-stage decoder contract
(``docs/r58_codex_explanation_layer_20260715.md`` §2) as a pure, harness-agnostic
state machine: ``SELECT -> FILL -> (COMPUTE, automatic) -> CONSUME -> VERIFY``.

The model never needs to remember kernel names or invocation syntax. It
declares typed intent (SELECT), fills typed semantic slots that reference
harness-owned observation handles (FILL), and the harness validates the
declaration and auto-invokes the mapped kernel (COMPUTE — not a separate
model turn). The next decoder turn is constrained to either use or
explicitly reject the kernel result (CONSUME); after execution, the
harness evaluates the playbook's falsifiers against what actually happened
(VERIFY) and decommits the intent on a strong contradiction or an
exhausted weak-falsifier strike budget.

This module owns NO environment access, NO game semantics, and NO kernel
math of its own — it is glue between (a) hand-rolled JSON-Schema-shaped
validation (stdlib only; no ``jsonschema`` dependency — not present in
``pyproject.toml`` and this slice's schemas are small enough to hand-check),
(b) a machine-readable playbook card (``playbooks/navigation.yaml``), and
(c) the namespace-safe kernels in :mod:`admorphiq.kernels`. Every stage
transition emits a telemetry dict tagged with its adoption-funnel stage
(verdict §7) so a harness/bench can measure schema validity, invocation
rate, consumption compliance, and falsifier-triggered abandonment without
re-deriving them from raw transcripts.

Kept as a SEPARATE package from :mod:`admorphiq.repl_agent` on purpose —
that harness is running live experiments; this slice is designed to plug
into it later, not to replace it mid-flight.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import yaml

_PACKAGE_DIR = Path(__file__).resolve().parent

# ----- adoption-funnel stage tags (verdict §7) --------------------------------
FUNNEL_OPPORTUNITY = 1
FUNNEL_INTENT_SELECTED = 2
FUNNEL_SLOTS_VALID = 3
FUNNEL_KERNEL_INVOKED = 4
FUNNEL_RESULT_CONSUMED = 5
FUNNEL_PREDICTION_VERIFIED = 6
FUNNEL_INTENT_ABANDONED = 7

# ----- protocol states ---------------------------------------------------------
SELECT = "SELECT"
FILL = "FILL"
CONSUME = "CONSUME"
VERIFY = "VERIFY"

_CONSUME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["decision", "plan_id"],
    "additionalProperties": False,
    "properties": {
        "decision": {"type": "string", "enum": ["execute", "reject"]},
        "plan_id": {"type": "string", "minLength": 1},
        "step": {"type": "integer"},
        "contradiction": {"type": "string", "pattern": "^evidence:[A-Za-z0-9_]+$"},
        "next_intent": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
    },
}

# One-line kernel contracts for the "relevant kernel contract" element of the
# after-intent-declaration injection (verdict §5). Deliberately just a
# signature summary, not the kernel's full docstring — the model needs to
# know a call exists and roughly what it does, not how to invoke it (the
# harness invokes it automatically in COMPUTE; the model never calls it
# itself).
_KERNEL_CONTRACTS: dict[str, str] = {
    "navigation": (
        "grid_shortest_path(passable, start, goal) -> path; "
        "path_to_moves(path, action_map) -> moves"
    ),
}


def _strip_descriptions(node: Any) -> Any:
    """Recursively drop every ``"description"`` key from a JSON-Schema-shaped
    dict/list, used by :meth:`ExplanationProtocol.compact_injection` — the
    long-form field descriptions in ``intents/*.schema.json`` are authoring
    documentation for humans/Claude Code, not something the 27B needs
    re-injected every turn."""
    if isinstance(node, dict):
        return {k: _strip_descriptions(v) for k, v in node.items() if k != "description"}
    if isinstance(node, list):
        return [_strip_descriptions(v) for v in node]
    return node


# ----- minimal hand-rolled JSON-Schema validator (stdlib only) -----------------
def validate(schema: dict[str, Any], instance: Any, path: str = "$") -> list[str]:
    """Validate ``instance`` against a small subset of JSON Schema.

    Supports exactly what this slice's schema files use: ``type`` (object,
    array, string, integer), ``required``, ``additionalProperties: false``,
    ``properties``, ``items``, ``minItems``, ``pattern``, ``minLength``,
    ``enum``, ``const``. Returns a list of short human-readable error
    strings (empty == valid). No third-party ``jsonschema`` dependency —
    intentionally not added to ``pyproject.toml`` for two small runtime
    schemas per verdict guidance ("no jsonschema dep unless it's already in
    pyproject").
    """
    errors: list[str] = []
    t = schema.get("type")
    if t == "object":
        if not isinstance(instance, dict):
            return [f"{path}: expected object, got {type(instance).__name__}"]
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}.{key}: missing required field")
        props: dict[str, Any] = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{path}.{key}: unexpected field")
        for key, sub_schema in props.items():
            if key in instance:
                errors.extend(validate(sub_schema, instance[key], f"{path}.{key}"))
        return errors
    if t == "array":
        if not isinstance(instance, list):
            return [f"{path}: expected array, got {type(instance).__name__}"]
        min_items = schema.get("minItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(f"{path}: expected at least {min_items} item(s), got {len(instance)}")
        item_schema = schema.get("items")
        if item_schema is not None:
            for i, item in enumerate(instance):
                errors.extend(validate(item_schema, item, f"{path}[{i}]"))
        return errors
    if t == "string":
        if not isinstance(instance, str):
            return [f"{path}: expected string, got {type(instance).__name__}"]
        pattern = schema.get("pattern")
        if pattern and not re.match(pattern, instance):
            errors.append(f"{path}: {instance!r} does not match pattern {pattern!r}")
        min_len = schema.get("minLength")
        if min_len is not None and len(instance) < min_len:
            errors.append(f"{path}: shorter than minLength {min_len}")
        enum = schema.get("enum")
        if enum is not None and instance not in enum:
            errors.append(f"{path}: {instance!r} not in enum {enum!r}")
        return errors
    if t == "integer":
        if not isinstance(instance, int) or isinstance(instance, bool):
            errors.append(f"{path}: expected integer, got {type(instance).__name__}")
        return errors
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    return errors


# ----- handle resolution --------------------------------------------------------
class HandleStore:
    """Trivial dict-backed resolver for observation-store handles.

    A real harness resolves ``"region:7"`` / ``"cell:12"`` / ``"mask:4"`` /
    ``"action_map:2"`` against its own live observation objects (e.g. the
    ``repl_agent`` sandbox's ``ObservationStore``); this slice only needs
    *some* ``Callable[[str], Any]`` and ships this minimal reference
    implementation so the protocol class stays harness-agnostic while
    remaining directly testable.
    """

    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def put(self, handle: str, value: Any) -> str:
        self._values[handle] = value
        return handle

    def __call__(self, handle: str) -> Any:
        if handle not in self._values:
            raise KeyError(f"unresolved handle: {handle!r}")
        return self._values[handle]


# ----- navigation COMPUTE (the one kernel-mapped intent in v0) -----------------
def compute_navigation(fill_decl: dict[str, Any], resolve: Callable[[str], Any]) -> dict[str, Any]:
    """Auto-invoked kernel composition for a valid ``navigation`` FILL_INTENT.

    Resolves every handle in ``fill_decl``, tries each declared goal in
    order via :func:`admorphiq.kernels.paths.grid_shortest_path` (first
    reachable goal wins), and converts the winning path to moves via
    :func:`admorphiq.kernels.paths.path_to_moves`. Returns
    ``{"ok": True, "path": [...], "moves": [...], "goal": <resolved goal>}``
    on success, or ``{"ok": False, "reason": ...}`` when every declared
    goal is unreachable under the declared mask, or when a handle fails to
    resolve (a semantically-valid-shaped but referentially-broken
    declaration — distinct from a schema-invalid one, which never reaches
    this function at all).
    """
    from admorphiq.kernels import grid_shortest_path, path_to_moves

    try:
        start = resolve(fill_decl["start"])
        goals = [resolve(g) for g in fill_decl["goals"]]
        passable = resolve(fill_decl["passable_mask"])
        action_map = resolve(fill_decl["action_map"])
    except KeyError as exc:
        return {"ok": False, "reason": "unresolved_handle", "detail": str(exc)}

    for goal in goals:
        path = grid_shortest_path(passable, start, goal)
        if path is None:
            continue
        moves = path_to_moves(path, action_map)
        return {"ok": True, "path": path, "moves": moves, "goal": goal}
    return {"ok": False, "reason": "unreachable", "goals": goals}


# ----- the state machine --------------------------------------------------------
class ExplanationProtocol:
    """Harness-agnostic SELECT -> FILL -> COMPUTE -> CONSUME -> VERIFY state machine.

    Constructed with the schemas/playbook/compute-function bundle for
    whichever intent families are currently loaded (v0: ``navigation``
    only). Every public method takes exactly the JSON-shaped declaration
    the model would have emitted for that decoder turn and returns a
    compact result dict; every transition also appends one event to
    :attr:`telemetry`.
    """

    def __init__(
        self,
        select_schema: dict[str, Any],
        fill_schemas: dict[str, dict[str, Any]],
        playbooks: dict[str, dict[str, Any]],
        compute_fns: dict[str, Callable[[dict[str, Any], Callable[[str], Any]], dict[str, Any]]],
        resolve: Callable[[str], Any],
        kernel_contracts: dict[str, str] | None = None,
    ) -> None:
        if fill_schemas.keys() != playbooks.keys() or fill_schemas.keys() != compute_fns.keys():
            raise ValueError("fill_schemas, playbooks, and compute_fns must share the same intent keys")
        self.select_schema = select_schema
        self.fill_schemas = fill_schemas
        self.playbooks = playbooks
        self.compute_fns = compute_fns
        self.resolve = resolve
        self.kernel_contracts = kernel_contracts or {}
        self.allowed_intents: frozenset[str] = frozenset(fill_schemas.keys()) | {"unknown"}

        self.state = SELECT
        self.telemetry: list[dict[str, Any]] = []
        self._seq = 0
        self._pending_intent: str | None = None
        self._plan: dict[str, Any] | None = None
        self._next_step = 0
        self._strikes = 0
        self._plan_counter = 0

    @classmethod
    def for_navigation_v0(cls, resolve: Callable[[str], Any] | None = None) -> "ExplanationProtocol":
        """Construct the shipped v0 bundle: navigation schemas + playbook + kernel."""
        select_schema = _load_json(_PACKAGE_DIR / "intents" / "select.schema.json")
        nav_schema = _load_json(_PACKAGE_DIR / "intents" / "navigation.schema.json")
        nav_playbook = _load_yaml(_PACKAGE_DIR / "playbooks" / "navigation.yaml")
        return cls(
            select_schema=select_schema,
            fill_schemas={"navigation": nav_schema},
            playbooks={"navigation": nav_playbook},
            compute_fns={"navigation": compute_navigation},
            resolve=resolve if resolve is not None else HandleStore(),
            kernel_contracts=dict(_KERNEL_CONTRACTS),
        )

    def compact_injection(self, intent: str) -> dict[str, Any]:
        """The REAL after-intent-declaration injection payload (verdict §5's
        "One selected playbook, its slot schema, and relevant kernel
        contract" row) — distinct from measuring the playbook alone. Strips
        every ``"description"`` field from the FILL schema (authoring
        documentation, not a per-turn injection need) and adds a one-line
        kernel contract string. Team-lead ruling (R58 follow-up, 2026-07-15):
        the ≤500-token budget row is playbook-only; this combined bundle's
        target is a PROVISIONAL ≤900 tokens pending the protocol-review
        round — not yet a hard gate, just the number this method's output
        should be checked against as the playbook/schema grow.
        """
        return {
            "playbook": self.playbooks[intent],
            "schema": _strip_descriptions(self.fill_schemas[intent]),
            "kernel_contract": self.kernel_contracts.get(intent, ""),
        }

    # -- telemetry -----------------------------------------------------------
    def _emit(self, funnel: int | None, event: str, **details: Any) -> dict[str, Any]:
        self._seq += 1
        record = {"seq": self._seq, "funnel": funnel, "stage": self.state, "event": event, **details}
        self.telemetry.append(record)
        return record

    def record_opportunity(self, intent: str, evidence: Sequence[str]) -> dict[str, Any]:
        """Harness-side bookkeeping: a playbook's activation predicates fired.

        Funnel stage 1 ("pre-registered signature opportunity") happens
        BEFORE the model ever declares anything, so it is not a state
        transition — this only records that the opportunity existed, for
        adoption-rate measurement (opportunities seen vs. intents selected).
        """
        return self._emit(FUNNEL_OPPORTUNITY, "signature_opportunity", intent=intent, evidence=list(evidence))

    def _repair(self, errors: list[str], **extra: Any) -> dict[str, Any]:
        return {"ok": False, "stage": self.state, "repair": {"errors": errors}, **extra}

    # -- SELECT ---------------------------------------------------------------
    def select(self, declaration: dict[str, Any]) -> dict[str, Any]:
        """SELECT_INTENT turn. Invalid shape or an off-allowlist intent name
        never advances the state and never touches a kernel (zero actions
        spent)."""
        if self.state != SELECT:
            self._emit(None, "stage_violation", attempted="select", expected=SELECT)
            return self._repair([f"select() called while in stage {self.state}, expected {SELECT}"])

        errors = validate(self.select_schema, declaration)
        if not errors and declaration["intent"] not in self.allowed_intents:
            errors.append(
                f"$.intent: {declaration['intent']!r} not in allowed intents {sorted(self.allowed_intents)}"
            )
        if errors:
            self._emit(None, "repair", errors=errors)
            return self._repair(errors)

        intent = declaration["intent"]
        support = declaration["support"]
        if intent == "unknown":
            self._emit(FUNNEL_INTENT_SELECTED, "unknown_selected", support=support)
            return {"ok": True, "stage": SELECT, "intent": "unknown"}

        self._pending_intent = intent
        self.state = FILL
        self._emit(FUNNEL_INTENT_SELECTED, "intent_selected", intent=intent, support=support)
        return {"ok": True, "stage": FILL, "intent": intent, "schema": self.fill_schemas[intent]}

    # -- FILL + auto COMPUTE ---------------------------------------------------
    def fill(self, declaration: dict[str, Any]) -> dict[str, Any]:
        """FILL_INTENT turn. A schema-invalid declaration is a repair packet
        with NO kernel call (verdict §2.3). A valid declaration automatically
        invokes the mapped kernel — there is no separate model turn for
        COMPUTE."""
        if self.state != FILL or self._pending_intent is None:
            self._emit(None, "stage_violation", attempted="fill", expected=FILL)
            return self._repair([f"fill() called while in stage {self.state}, expected {FILL}"])

        intent = self._pending_intent
        schema = self.fill_schemas[intent]
        errors = validate(schema, declaration)
        if errors:
            self._emit(FUNNEL_SLOTS_VALID, "repair", errors=errors)
            return self._repair(errors)

        self._emit(FUNNEL_SLOTS_VALID, "slots_valid", intent=intent)

        self._emit(FUNNEL_KERNEL_INVOKED, "kernel_invoked", intent=intent)
        result = self.compute_fns[intent](declaration, self.resolve)

        if not result.get("ok"):
            self._emit(FUNNEL_KERNEL_INVOKED, "kernel_contradiction", intent=intent, reason=result.get("reason"))
            self.state = SELECT
            self._pending_intent = None
            return {"ok": True, "stage": SELECT, "contradiction": result.get("reason", "kernel_returned_no_plan"),
                    "detail": result}

        self._plan_counter += 1
        plan_id = f"p{self._plan_counter}"
        moves = result["moves"]
        self._plan = {
            "plan_id": plan_id,
            "intent": intent,
            "declaration": declaration,
            "moves": moves,
            "playbook": self.playbooks[intent],
        }
        self._next_step = 0
        compact_result = {
            "plan_id": plan_id,
            "path_len": len(result["path"]),
            "first_step": moves[0] if moves else None,
            "predicted_effect": f"{declaration['mover']} displaces toward {declaration['goals'][0]}",
        }
        self._emit(FUNNEL_KERNEL_INVOKED, "kernel_result", intent=intent, **compact_result)
        self.state = CONSUME
        return {"ok": True, "stage": CONSUME, "plan_id": plan_id, "result": compact_result}

    # -- CONSUME_RESULT ---------------------------------------------------------
    def consume(self, decision: dict[str, Any]) -> dict[str, Any]:
        """CONSUME_RESULT turn. Only ``{"decision":"execute",...}`` matching the
        live plan_id/step, or ``{"decision":"reject",...}``, are accepted — any
        other shape, a stale/foreign plan_id, or an out-of-order step is a
        rejected bypass attempt that leaves the state (and the plan) untouched."""
        if self.state != CONSUME or self._plan is None:
            self._emit(None, "stage_violation", attempted="consume", expected=CONSUME)
            return self._repair([f"consume() called while in stage {self.state}, expected {CONSUME}"])

        errors = validate(_CONSUME_SCHEMA, decision)
        if not errors and decision["plan_id"] != self._plan["plan_id"]:
            errors.append(f"$.plan_id: {decision['plan_id']!r} does not match live plan {self._plan['plan_id']!r}")
        if not errors and decision["decision"] == "execute":
            if "step" not in decision:
                errors.append("$.step: required when decision == 'execute'")
            elif decision["step"] != self._next_step:
                errors.append(f"$.step: expected {self._next_step} (next unexecuted step), got {decision['step']}")
        if errors:
            self._emit(FUNNEL_RESULT_CONSUMED, "bypass_rejected", errors=errors)
            return self._repair(errors)

        if decision["decision"] == "reject":
            next_intent = decision.get("next_intent", "unknown")
            self._emit(FUNNEL_RESULT_CONSUMED, "explicit_reject",
                       plan_id=decision["plan_id"], contradiction=decision.get("contradiction"),
                       next_intent=next_intent)
            self._plan = None
            self._pending_intent = None
            self.state = SELECT
            return {"ok": True, "stage": SELECT, "next_intent": next_intent}

        step = decision["step"]
        action = self._plan["moves"][step]
        self._emit(FUNNEL_RESULT_CONSUMED, "result_consumed", plan_id=decision["plan_id"], step=step, action=action)
        self.state = VERIFY
        return {"ok": True, "stage": VERIFY, "plan_id": decision["plan_id"], "step": step, "action": action}

    # -- VERIFY -------------------------------------------------------------
    def verify(self, observation: dict[str, bool]) -> dict[str, Any]:
        """VERIFY turn. ``observation`` maps playbook falsifier names -> whether
        that named predicate fired this step. A true strong falsifier decommits
        immediately; weak falsifiers spend a strike from the playbook's budget
        before decommitting; otherwise the prediction is verified and the plan
        advances (or completes)."""
        if self.state != VERIFY or self._plan is None:
            self._emit(None, "stage_violation", attempted="verify", expected=VERIFY)
            return self._repair([f"verify() called while in stage {self.state}, expected {VERIFY}"])

        playbook = self._plan["playbook"]
        falsification = playbook["falsification"]
        plan_id = self._plan["plan_id"]

        for name in falsification.get("strong", []):
            if observation.get(name):
                self._emit(FUNNEL_INTENT_ABANDONED, "strong_falsifier_decommit", plan_id=plan_id, falsifier=name)
                return self._decommit(falsification["on_reject"])

        for name in falsification.get("weak", []):
            if observation.get(name):
                self._strikes += 1
                budget = falsification.get("weak_strikes", 1)
                if self._strikes >= budget:
                    self._emit(FUNNEL_INTENT_ABANDONED, "weak_budget_exhausted_decommit",
                               plan_id=plan_id, falsifier=name, strikes=self._strikes, budget=budget)
                    return self._decommit(falsification["on_reject"])
                self._emit(FUNNEL_INTENT_ABANDONED, "weak_falsifier_strike",
                           plan_id=plan_id, falsifier=name, strikes=self._strikes, budget=budget)
                self.state = CONSUME
                return {"ok": True, "stage": CONSUME, "retry_step": self._next_step, "strikes": self._strikes}

        self._emit(FUNNEL_PREDICTION_VERIFIED, "prediction_verified", plan_id=plan_id, step=self._next_step)
        self._next_step += 1
        if self._next_step < len(self._plan["moves"]):
            self.state = CONSUME
            return {"ok": True, "stage": CONSUME, "next_step": self._next_step}

        self._emit(FUNNEL_PREDICTION_VERIFIED, "plan_complete", plan_id=plan_id)
        self._plan = None
        self._pending_intent = None
        self._strikes = 0
        self.state = SELECT
        return {"ok": True, "stage": SELECT, "complete": True}

    def _decommit(self, recovery_transition: str) -> dict[str, Any]:
        self._plan = None
        self._pending_intent = None
        self._next_step = 0
        self._strikes = 0
        self.state = SELECT
        return {"ok": True, "decommit": True, "stage": SELECT, "recovery": recovery_transition}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
