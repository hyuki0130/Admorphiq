"""R95b STEP (vii): the canned-instance MODEL stage (live gate).

The finale of the R95b substage order (``docs/design_hypothesis_dsl_r95.md``):
instead of executing the hand-authored oracle, the OFFLINE MODEL SELECTS one of
the canonical instances (the oracle + the same-game mutants from
``schema.MUTANTS``) from their NEUTRAL serialized form + the LIVE grounding
evidence gathered this run; the verifier gates the pick (UNKNOWN/CONTRADICTED
never executes, per the frozen contract); a PASSing pick is compiled and
live-executed exactly like the oracle gate (``probe_hypothesis_live``).

Per run (fresh env, the live-driver flow):
  warm-up -> discovery (gather footprint/cycle/flip evidence) -> SELECTION ASK
  -> VERIFIER GATE -> (PASS only) compile + execute.

Success per run: ft09 = idx0+idx1 cleared; sc25 = the pattern-phase
cast_and_handover. Per-model success = >= 2 of 3 runs (contract).

The model NEVER sees an instance name, the word "oracle"/"mutant", or a game id:
the candidates are serialized with ``schema.to_neutral_json`` under a
deterministic ``I1..IN`` shuffle, and the observation summary is structural. A
leak-guard test asserts the assembled prompt is clean.

Usage::

    python scripts/probe_hypothesis_model.py --game ft09 --runs 3 --out out.json
    python scripts/probe_hypothesis_model.py --game ft09 --dry-run   # prompt only, no LLM/env
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from admorphiq.hypothesis_select import schema, schema_movement
from admorphiq.hypothesis_select.compiler import compile_hypothesis
from admorphiq.hypothesis_select.compiler_movement import (
    Move as MovementMove,
)
from admorphiq.hypothesis_select.compiler_movement import (
    compile_movement_hypothesis,
)
from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService
from admorphiq.hypothesis_select.verifier import Evidence, verify_with_evidence
from admorphiq.hypothesis_select.verifier_movement import (
    MovementEvidence,
    _coupling_signature,
)
from admorphiq.hypothesis_select.verifier_movement import (
    verify_with_evidence as verify_movement_with_evidence,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_hypothesis_live as live  # noqa: E402  (sibling script, loaded by path)

Grid = tuple[tuple[int, ...], ...]

_CONFIDENCE_VALUES = ("low", "medium", "high")
_SC25_PROBE_CELLS = 4  # flip probes to gather footprint evidence for the lattice family

# fill-mode closed vocabularies (the model's structural + semantic choices)
_OBJECTIVE_KINDS = ("glyph_relational", "pattern_reference")
_TRANSITION_KINDS = ("ordered_cycle", "binary_flip", "empirical_effect_matrix")
_COVERAGE_QUANTIFIERS = ("all_covering", "nearest_only")
_PREVIEW_INTERPRETATIONS = ("xor_exact", "xor_near", "absolute_exact", "absolute_near")
_INK_OPERATORS = ("equal", "differ", "none")
_GUARD_KINDS = ("stable_for_reads", "roles_state_equal", "layout_replaced", "level_advanced")
# The compiler supports exactly one transition per objective (glyph -> ordered
# cycle, pattern -> binary flip); and the cycle-vs-flip distinction is NOT cheaply
# observable (MEASURED: ft09 cells toggle 2 colours, the cycle is latent). So the
# harness pairs the compilable transition to the model's (observable) objective —
# an uncompilable model transition is auto-corrected, recorded for audit.
_COMPATIBLE_TRANSITION = {"glyph_relational": "ordered_cycle", "pattern_reference": "binary_flip"}
# Auto-pairing is confined to THIS pair only — the two members are behaviourally
# indistinguishable from cheap probing. empirical_effect_matrix is EXCLUDED: it is
# an OBSERVABLE multi-cell claim that must stand as chosen and reach the verifier
# (the footprint gate, the proven live catch), never be paired away.
_UNOBSERVABLE_TRANSITIONS = frozenset({"ordered_cycle", "binary_flip"})
# The harness fills each guard's PARAMS (reads count, role names) — numbers/roles
# the harness measured; the model only chooses WHICH guard kinds gate each phase.
_GUARD_JSON: dict[str, dict[str, Any]] = {
    "stable_for_reads": {"kind": "stable_for_reads", "reads": 2},
    "roles_state_equal": {"kind": "roles_state_equal", "lhs": "toggle_grid", "rhs": "preview", "mask": None},
    "layout_replaced": {"kind": "layout_replaced"},
    "level_advanced": {"kind": "level_advanced"},
}


# ── canonical instances (the oracle + the same-game mutants, as DATA) ─────────


def _oracle_instance(game: str) -> schema.CellStateHypothesis:
    if game == "ft09":
        return schema.ft09_oracle_instance()
    if game == "sc25":
        return schema.sc25_oracle_instance()
    raise ValueError(f"unknown game {game!r}")


def instances_for_game(game: str) -> tuple[list[tuple[str, schema.CellStateHypothesis]], str]:
    """The candidate set for ``game``: the oracle plus every same-game mutant in
    ``schema.MUTANTS``, each paired with an INTERNAL name used ONLY to map the
    model's answer back for the audit record (never shown to the model). Returns
    ``(named_instances, oracle_internal_name)``. The mutant filter keys on the
    ``MutantCase.name`` prefix — dev-time selection, never the model-facing
    prompt.

    NOTE: ``schema.MUTANTS`` ships THREE same-game mutants per game, so the
    candidate set is 4 (oracle + 3), i.e. ids I1..I4 — not 5. Adding a fifth
    distractor requires a new canonical mutant in ``schema.MUTANTS``."""
    oracle_name = f"{game}_oracle"
    named: list[tuple[str, schema.CellStateHypothesis]] = [(oracle_name, _oracle_instance(game))]
    for mutant in schema.MUTANTS:
        if mutant.name.startswith(f"{game}_"):
            named.append((mutant.name, mutant.instance))
    return named, oracle_name


def _shuffle_ids(game: str, names: list[str]) -> dict[str, str]:
    """A DETERMINISTIC id assignment ``I1..IN`` keyed on the game via sha256 (no
    ``random``), so the same game always yields the same shuffle but the order
    carries no oracle-first bias (the R95a pattern)."""
    def key(name: str) -> int:
        return int.from_bytes(hashlib.sha256(f"{game}:{name}".encode()).digest()[:8], "big")

    order = sorted(names, key=key)
    return {f"I{i + 1}": name for i, name in enumerate(order)}


# ── live observation summary (structural; from the run's grounding) ───────────


def _count(n: int, word: str) -> str:
    """``'1 cell'`` / ``'5 cells'`` — pluralize ``word`` by count (English)."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def live_observation_summary(gs: GroundingService, game: str) -> str:
    """A NEUTRAL structural summary of the LIVE grounding evidence gathered this
    run — the number of interactive cells and marker symbols, the click-footprint
    histogram, and the pattern facts (lattice family). No game id, no template
    identity, no oracle hint.

    A click-style / distinct-colours line is DELIBERATELY NOT reported: MEASURED
    (fill v1/v3/v4) to corrupt the model's transition pick in every wording, and
    redundant — the ordered-cycle-vs-binary-flip choice is not cheaply observable
    and is handled by the harness auto-pairing the compilable transition to the
    (observable) objective, while the objective picks never needed it."""
    lines = ["OBSERVATIONS (measured from this run's own probing):"]

    cells = gs.cells()
    n_cells = len(cells.value) if cells is not UNKNOWN else 0
    lines.append(f"- Interactive cells detected: {n_cells}")

    glyphs = gs.glyphs()
    if glyphs is not UNKNOWN:
        n_incidence = 0
        for cell_id, _centroid in cells.value if cells is not UNKNOWN else []:
            cov = gs.incidence(cell_id)
            if cov is not UNKNOWN:
                n_incidence += len(cov.value)
        lines.append(
            f"- Marker symbols detected: {len(glyphs.value)}; "
            f"total cell-to-marker coverings observed: {n_incidence}"
        )

    footprints = gs.observed_footprints()
    if footprints is not UNKNOWN:
        # Unambiguous PROSE, not an "N->M" histogram notation: gemma4 misparsed the
        # notation (swapping cell-count and click-count) and misread a single-cell
        # effect as multi-cell. One clause per size, ordered by frequency.
        parts = [
            f"{_count(count, 'click')} changed exactly {_count(size, 'cell')}"
            + (" each" if count > 1 else "")
            for size, count in sorted(footprints.value.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        lines.append("- Click effect sizes: " + "; ".join(parts))
    else:
        lines.append("- Click effect sizes: none observed")

    evidence = gs.pattern_evidence()
    if evidence is not UNKNOWN:
        # Structure only — NOT the majority-based cells_matching count, which reads
        # spuriously high on an unsolved board (the base-parity artifact) and would
        # mislead the objective choice.
        lines.append(
            f"- A separate target pattern is displayed beside the grid, over the same "
            f"{evidence.value['total']} cells; the cells take two colours"
        )

    return "\n".join(lines)


# ── selection ask (serialized instances, guided-json) ─────────────────────────


def build_ask_prompt(
    game: str, gs: GroundingService
) -> tuple[list[dict[str, str]], dict[str, str], str]:
    """Assemble the model selection ask from the LIVE grounding ``gs``: the
    candidate instances serialized via ``schema.to_neutral_json`` under a
    deterministic ``I1..IN`` shuffle + the structural observation summary. Returns
    ``(messages, id->internal_name mapping, observation_text)``. Contains no
    instance names, no 'oracle'/'mutant', and no game id."""
    named, _oracle = instances_for_game(game)
    by_name = dict(named)
    mapping = _shuffle_ids(game, [n for n, _inst in named])

    observation = live_observation_summary(gs, game)
    candidate_block = "\n\n".join(
        f"{cid}:\n{json.dumps(schema.to_neutral_json(by_name[mapping[cid]]), indent=2)}"
        for cid in sorted(mapping)
    )
    ids = "|".join(f'"{cid}"' for cid in sorted(mapping))
    system = (
        "You are analysing a small interactive grid puzzle from live probing. You are "
        "given several candidate rule specifications (as structured JSON) that each claim "
        "to describe how a click changes the board and when the board is complete, plus "
        "observations from actual probing. Choose the ONE candidate whose specification "
        "best matches the observations."
    )
    user = (
        "CANDIDATE RULE SPECIFICATIONS:\n\n"
        f"{candidate_block}\n\n"
        f"{observation}\n\n"
        "Which single candidate specification best matches these observations? Weigh BOTH "
        "how each click changes the board (the transition_model) AND the completion "
        "condition (the objective). Respond with ONLY a JSON object, no other text:\n"
        f'{{"choice": {ids}, "confidence": "low"|"medium"|"high", '
        '"evidence": "<=2 sentences citing the observation that decided it"}'
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return messages, mapping, observation


def _parse_choice(text: str, valid_ids: set[str]) -> tuple[Optional[dict[str, Any]], str]:
    """Extract + validate the ask JSON (the last balanced ``{...}`` object carrying
    a ``choice``). Returns ``(parsed_or_None, error)``; choice must be in
    ``valid_ids``, confidence in the closed set, evidence a string."""
    matches = re.findall(r"\{[^{}]*\}", text, re.DOTALL)
    obj: Optional[dict[str, Any]] = None
    for candidate in reversed(matches):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "choice" in parsed:
            obj = parsed
            break
    if obj is None:
        return None, "no JSON object with a 'choice' field parsed"
    choice = obj.get("choice")
    if choice not in valid_ids:
        return None, f"choice {choice!r} is not one of {sorted(valid_ids)}"
    confidence = obj.get("confidence", "low")
    if confidence not in _CONFIDENCE_VALUES:
        confidence = "low"
    evidence = obj.get("evidence", "")
    if not isinstance(evidence, str):
        evidence = str(evidence)
    return {"choice": choice, "confidence": confidence, "evidence": evidence[:500]}, ""


def ask_once(
    llm: Callable[[list[dict[str, str]]], str],
    messages: list[dict[str, str]],
    valid_ids: set[str],
) -> dict[str, Any]:
    """One selection ask + validate, with ONE error-feedback retry (the R95a
    ask shape). Returns ``{choice, confidence, evidence, attempts, error}``;
    ``choice`` is ``None`` on a hard failure."""
    convo = list(messages)
    try:
        text = llm(convo)
    except Exception as exc:  # noqa: BLE001 - offline-safe: record and stop
        return {"choice": None, "confidence": None, "evidence": "", "attempts": 1, "error": str(exc)}
    parsed, err = _parse_choice(text, valid_ids)
    if parsed is not None:
        return {**parsed, "attempts": 1, "error": None}
    convo.append({"role": "assistant", "content": text})
    convo.append({"role": "user", "content": (
        f"Your response was not valid ({err}). Respond with ONLY the JSON object: "
        f'{{"choice": one of {sorted(valid_ids)}, "confidence": low|medium|high, '
        '"evidence": "<=2 sentences"}.'
    )})
    try:
        text2 = llm(convo)
    except Exception as exc:  # noqa: BLE001
        return {"choice": None, "confidence": None, "evidence": "", "attempts": 2, "error": str(exc)}
    parsed2, err2 = _parse_choice(text2, valid_ids)
    if parsed2 is not None:
        return {**parsed2, "attempts": 2, "error": None}
    return {"choice": None, "confidence": None, "evidence": "", "attempts": 2, "error": err2}


# ── verifier gate ─────────────────────────────────────────────────────────────


def gate_selected_instance(
    instance: schema.CellStateHypothesis, gs: GroundingService, game: str
) -> tuple[str, bool]:
    """Run the verifier on the SELECTED instance against the LIVE-gathered evidence
    (the run's grounding as the train evidence; no win frames exist pre-solve, so
    the objective is UNKNOWN-tolerated and the verdict hinges on the sound
    cross-level FOOTPRINT claim). Returns ``(verdict_name, executable)``; only a
    PASS is executable — UNKNOWN/CONTRADICTED never executes, per the contract."""
    evidence = Evidence(game=game, train_grounding=gs, win_frames=())
    verdict = verify_with_evidence(instance, evidence)
    return verdict.verdict.value, verdict.verdict is schema.Verdict.PASS


def compilable(instance: schema.CellStateHypothesis, gs: GroundingService) -> bool:
    """Whether ``instance``'s (objective, transition) variant combination has a
    compiled plan. A model-assembled hypothesis can pair an objective with a
    transition the compiler does not support (e.g. a glyph objective with a
    binary-flip transition) — that is a typed per-run failure, not a crash."""
    try:
        compile_hypothesis(instance, gs)
    except ValueError:
        return False
    return True


# ── live run (env-driven; exercised only under the real gate) ─────────────────


def _gather_evidence(env: "live.LiveEnv", gs: GroundingService, game: str, record: dict[str, Any]) -> None:
    """Probe the board to accumulate the click-FOOTPRINT evidence the verifier's
    transition claim needs — the ft09 cycle discovery (which also acquires the
    cycle the compiler needs), plus a repeated-click probe for the pattern family.
    ``record['colour_variety']`` is recorded for AUDIT only (the distinct colours
    one cell takes); it is not shown to the model — see live_observation_summary."""
    def probe(x: int, y: int) -> Optional[Grid]:
        env.click(x, y)
        return env.frame()

    if game == "ft09":
        # Acquire the colour cycle the COMPILER needs for execution (the tested path).
        closed, used = live.discover_cycle(gs, probe)
        record["discovery_actions"] += used
        record["cycle_acquired"] = closed
    record["colour_variety"] = measure_colour_variety(env, gs, game, record)


def measure_colour_variety(
    env: "live.LiveEnv", gs: GroundingService, game: str,
    record: dict[str, Any], clicks: int = 5, max_distinct_cells: int = 2,
) -> Optional[tuple[int, int]]:
    """Click ONE responsive cell repeatedly for footprint evidence (its distinct
    colours are returned for the audit record only). Two source-side safeguards:
    only ``max_distinct_cells`` DISTINCT cells are ever clicked (a pattern cast
    needs more selected cells than that, so discovery cannot complete the pattern +
    trigger the multi-cell auto-cast that would contaminate the footprint stats and
    consume the un-solved board), and inert cells are skipped. Returns
    ``(distinct_colours, clicks)`` or ``None`` when no cell is responsive."""
    cells = gs.cells()
    if cells is UNKNOWN:
        return None
    for cid, (ry, rx) in cells.value[:max_distinct_cells]:
        x, y = int(round(rx)), int(round(ry))
        c0 = gs.cell_colour(cid)
        before = env.frame()
        after = probe_and_feed(env, gs, x, y, record)
        c1 = gs.cell_colour(cid)
        if c0 is UNKNOWN or c1 is UNKNOWN or c1.value == c0.value or before is None or after is None:
            continue  # inert cell (one footprint recorded); try the next
        seen = {c0.value, c1.value}
        for _ in range(clicks - 1):
            probe_and_feed(env, gs, x, y, record)
            cc = gs.cell_colour(cid)
            if cc is not UNKNOWN:
                seen.add(cc.value)
        return (len(seen), clicks)
    return None


def probe_and_feed(
    env: "live.LiveEnv", gs: GroundingService, x: int, y: int, record: dict[str, Any]
) -> Optional[Grid]:
    """Click ``(x, y)``, feed the transition to ``gs`` (footprint evidence), and
    return the after-frame."""
    before = env.frame()
    env.click(x, y)
    after = env.frame()
    record["discovery_actions"] += 1
    if before is not None and after is not None:
        gs.feed_transition(before, 6, (x, y), after)
        gs.feed(after)  # also run the frame-state detectors (e.g. the selection-colour signal)
    return after


def _warm_up(env: "live.LiveEnv", gs: GroundingService) -> bool:
    for _ in range(live._WARMUP_BUDGET):
        frame = env.frame()
        if frame is None or env.state() in ("GAME_OVER", "NOT_PLAYED"):
            env.reset()
            continue
        gs.feed(frame)
        if gs.cells() is not UNKNOWN:
            return True
    return gs.cells() is not UNKNOWN


def run_model_once(
    game: str, run_index: int, llm: Callable[[list[dict[str, str]]], str]
) -> dict[str, Any]:
    """One fresh-reset MODEL-gate run: warm-up -> gather evidence -> ASK ->
    verifier gate -> (PASS only) compile + execute. Returns the per-run record."""
    target_levels = live._FT09_TARGET_LEVELS if game == "ft09" else live._SC25_TARGET_LEVELS
    level_budget = live._FT09_LEVEL_BUDGET if game == "ft09" else live._SC25_PHASE_BUDGET
    named, oracle_name = instances_for_game(game)
    by_name = dict(named)

    record: dict[str, Any] = {
        "run": run_index,
        "choice": None,
        "mapped_instance": None,
        "is_oracle": False,
        "confidence": None,
        "evidence": "",
        "colour_variety": None,
        "verifier_verdict": None,
        "executed": False,
        "levels_cleared": 0,
        "cast_and_handover": False,
        "actions_per_level": [],
        "discovery_actions": 0,
        "cycle_acquired": False,
        "plan_outcome": "NOT_EXECUTED",
        "rebind_events": 0,
        "outcome": "FAIL",
    }

    env = live.LiveEnv(game)
    env.reset()
    gs = GroundingService()
    if not _warm_up(env, gs):
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        return record
    _gather_evidence(env, gs, game, record)

    messages, mapping, _obs = build_ask_prompt(game, gs)
    ask = ask_once(llm, messages, set(mapping))
    mapped = mapping.get(ask["choice"]) if ask["choice"] is not None else None
    record.update(
        choice=ask["choice"],
        mapped_instance=mapped,
        is_oracle=mapped == oracle_name,
        confidence=ask["confidence"],
        evidence=ask["evidence"],
    )
    if mapped is None:
        record["verifier_verdict"] = "NO_CHOICE"
        return record

    instance = by_name[mapped]
    _gate_and_execute(env, gs, game, instance, target_levels, level_budget, record, run_index)
    return record


def _gate_and_execute(
    env: "live.LiveEnv",
    gs: GroundingService,
    game: str,
    instance: schema.CellStateHypothesis,
    target_levels: int,
    level_budget: int,
    record: dict[str, Any],
    run_index: int,
) -> None:
    """Verifier-gate ``instance`` on the live evidence, then (PASS only) execute it
    on a fresh board via the SAME path as the oracle gate. Shared by select mode
    and fill mode. Mutates ``record`` with the verdict, executed flag, and outcome."""
    verdict_name, executable = gate_selected_instance(instance, gs, game)
    record["verifier_verdict"] = verdict_name
    if not executable:
        return  # UNKNOWN / CONTRADICTED never executes (contract)
    if not compilable(instance, gs):
        # The model paired an objective with a transition the compiler cannot plan
        # (e.g. glyph_relational x binary_flip) — a typed failure, never a crash.
        record["plan_outcome"] = "UNSUPPORTED_COMBINATION"
        return  # executed stays False, outcome stays FAIL

    # The reset clears the probe-modified board; the footprint evidence in gs
    # persists (it is level-invariant).
    record["executed"] = True
    env.reset()
    if not _warm_up(env, gs):
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        return

    def probe(x: int, y: int) -> Optional[Grid]:
        env.click(x, y)
        return env.frame()

    def rediscover() -> bool:
        if game != "ft09":
            return True
        if gs.get_ordered_cycle() is not UNKNOWN:
            return True
        closed, used = live.discover_cycle(gs, probe)
        record["discovery_actions"] += used
        record["cycle_acquired"] = record["cycle_acquired"] or closed
        return closed

    if not rediscover():
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        return

    live.execute_instance(
        env, gs, game, instance, target_levels, level_budget, record, run_index, rediscover
    )
    success = (
        record["levels_cleared"] >= target_levels
        if game == "ft09"
        else record["cast_and_handover"]
    )
    record["outcome"] = "PASS" if success else "FAIL"


def model_verdict(runs: list[dict[str, Any]]) -> str:
    """Per-model success = >= 2 of the runs succeeded (the frozen contract's 2/3)."""
    if not runs:
        return "FAIL"
    return "PASS" if sum(1 for r in runs if r.get("outcome") == "PASS") >= 2 else "FAIL"


# ── fill mode: variant-first slot filling (generation, not selection) ─────────


def observed_inks(gs: GroundingService) -> list[int]:
    """The marker-ink colours seen across the grounded cells' incidence — the
    closed set the model assigns operators to (glyph family; empty for a lattice
    board)."""
    inks: set[int] = set()
    cells = gs.cells()
    if cells is not UNKNOWN:
        for cid, _centroid in cells.value:
            cov = gs.incidence(cid)
            if cov is not UNKNOWN:
                for _gid, ink, _marker, _gc in cov.value:
                    inks.add(int(ink))
    return sorted(inks)


def harness_measured_values(gs: GroundingService, game: str) -> dict[str, Any]:
    """The harness_measured field values the model must NOT author (per
    schema.OWNERSHIP): the live-acquired colour cycle order, the modal click
    footprint, the base-snapshot timing + two-read policy, and the no-cell ink
    sentinel. Everything measured, nothing invented."""
    inks = observed_inks(gs)
    cycle = gs.get_ordered_cycle()
    footprints = gs.observed_footprints()
    modal = 1
    if footprints is not UNKNOWN:
        effective = {k: v for k, v in footprints.value.items() if k >= 1}
        modal = max(effective, key=lambda k: effective[k]) if effective else 1
    return {
        "no_cell_ink": (max(inks) + 1) if inks else 0,  # a sentinel distinct from observed inks (unused by execution)
        "order": list(cycle.value) if cycle is not UNKNOWN else [],
        "asserted_footprint": modal,
        "base_snapshot_timing": "after_first_settled_action",
        "two_read_stability": True,
        "n_phases": len(_oracle_instance(game).phases),
    }


def _balanced_objects(text: str) -> list[str]:
    """Every top-level ``{...}`` balanced-brace substring in ``text`` (tolerant of
    nesting, unlike a flat regex — the slot JSON nests ink_operator_map)."""
    out: list[str] = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                out.append(text[start:i + 1])
    return out


def _last_object_with(text: str, key: str) -> Optional[dict[str, Any]]:
    for candidate in reversed(_balanced_objects(text)):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and key in parsed:
            return parsed
    return None


def build_variant_ask(gs: GroundingService, game: str) -> list[dict[str, str]]:
    """ASK 1 — the VARIANT: from the live observation summary (no serialized
    instances — this is generation), choose the objective + transition category."""
    observation = live_observation_summary(gs, game)
    system = (
        "You are analysing a small interactive grid puzzle from live probing. Identify "
        "its mechanics by choosing the category of its completion rule and its click effect."
    )
    user = (
        f"{observation}\n\n"
        "Choose the two categories that best match:\n"
        "- objective_kind: 'glyph_relational' (the board is complete when each cell satisfies "
        "relational colour requirements set by nearby marker symbols) OR 'pattern_reference' "
        "(complete when the grid matches a separately displayed target pattern).\n"
        "- transition_kind: 'ordered_cycle' (a click advances one cell one step through a "
        "repeating cycle of 3+ colours) OR 'binary_flip' (a click toggles one cell between two "
        "colours) OR 'empirical_effect_matrix' (a click changes a fixed-size neighbourhood of "
        "several cells).\n"
        "Respond with ONLY a JSON object, no other text:\n"
        '{"objective_kind": "glyph_relational"|"pattern_reference", "transition_kind": '
        '"ordered_cycle"|"binary_flip"|"empirical_effect_matrix", "confidence": "low"|"medium"|"high", '
        '"evidence": "<=2 sentences citing the observation that decided it"}'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_variant(text: str) -> tuple[Optional[dict[str, str]], str]:
    """Validate ASK 1: objective_kind + transition_kind in their closed vocabularies."""
    obj = _last_object_with(text, "objective_kind")
    if obj is None:
        return None, "no JSON object with an 'objective_kind' field parsed"
    ok, tk = obj.get("objective_kind"), obj.get("transition_kind")
    if ok not in _OBJECTIVE_KINDS:
        return None, f"objective_kind {ok!r} is not one of {list(_OBJECTIVE_KINDS)}"
    if tk not in _TRANSITION_KINDS:
        return None, f"transition_kind {tk!r} is not one of {list(_TRANSITION_KINDS)}"
    confidence = obj.get("confidence", "low")
    if confidence not in _CONFIDENCE_VALUES:
        confidence = "low"
    return {"objective_kind": ok, "transition_kind": tk, "confidence": confidence,
            "evidence": str(obj.get("evidence", ""))[:500]}, ""


def build_slot_ask(gs: GroundingService, game: str, objective_kind: str) -> list[dict[str, str]]:
    """ASK 2 — the model_selected SLOTS for the chosen objective variant only. The
    harness-measured values (cycle, structure, timing) are NOT asked for."""
    n_phases = len(_oracle_instance(game).phases)
    guards = " | ".join(_GUARD_KINDS)
    phase_note = (
        f"- phase_guards: a list of exactly {n_phases} entries (one per phase, in order); each entry is "
        f"a list of guard names that gate entering that phase, from {{{guards}}}. Use [] for a phase with "
        "no guard (the first phase is always active)."
    )
    if objective_kind == "glyph_relational":
        inks = observed_inks(gs)
        ink_fields = ", ".join(f'"{i}": "equal"|"differ"|"none"' for i in inks)
        body = (
            "You choose ONLY these fields (the harness has measured the cells, the marker structure, "
            "and the colour cycle a click advances through):\n"
            "- coverage_quantifier: 'all_covering' (a cell must satisfy EVERY marker covering it) or "
            "'nearest_only' (only its single nearest marker).\n"
            f"- ink_operator_map: for each observed marker-ink colour {inks}, how the covered cell must "
            "relate to that marker: 'equal', 'differ', or 'none' (no constraint).\n"
            f"{phase_note}\n\n"
            "Respond with ONLY a JSON object:\n"
            f'{{"coverage_quantifier": "all_covering"|"nearest_only", "ink_operator_map": {{{ink_fields}}}, '
            f'"phase_guards": [{", ".join(["[...]"] * n_phases)}], "confidence": "low"|"medium"|"high", '
            '"evidence": "<=2 sentences"}'
        )
    else:
        body = (
            "You choose ONLY these fields (the harness has measured the cells and the base-snapshot "
            "timing):\n"
            "- preview_interpretation: how the displayed target maps onto the grid: 'xor_exact' (grid = "
            "base XOR target, exact), 'xor_near' (XOR, a few mismatches allowed), 'absolute_exact' (grid "
            "cells directly equal the target colours), 'absolute_near' (absolute, a few mismatches).\n"
            f"{phase_note}\n\n"
            "Respond with ONLY a JSON object:\n"
            '{"preview_interpretation": "xor_exact"|"xor_near"|"absolute_exact"|"absolute_near", '
            f'"phase_guards": [{", ".join(["[...]"] * n_phases)}], "confidence": "low"|"medium"|"high", '
            '"evidence": "<=2 sentences"}'
        )
    system = (
        "You are specifying the rule of a small interactive grid puzzle. Fill ONLY the requested "
        "slots from their allowed values; do not restate measured values."
    )
    user = f"{live_observation_summary(gs, game)}\n\n{body}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_slots(
    text: str, objective_kind: str, inks: list[int], n_phases: int
) -> tuple[Optional[dict[str, Any]], str]:
    """Validate ASK 2 against the closed vocabularies + the observed-ink list + the
    phase count. Returns ``(slots_or_None, error)``; the error string is the
    field-naming feedback for the ONE retry."""
    anchor = "coverage_quantifier" if objective_kind == "glyph_relational" else "preview_interpretation"
    obj = _last_object_with(text, anchor)
    if obj is None:
        return None, f"no JSON object with a '{anchor}' field parsed"
    guards = obj.get("phase_guards")
    if not isinstance(guards, list) or len(guards) != n_phases:
        return None, f"phase_guards must be a list of exactly {n_phases} guard-name lists"
    for i, entry in enumerate(guards):
        if not isinstance(entry, list) or any(g not in _GUARD_KINDS for g in entry):
            return None, f"phase_guards[{i}] must be a list of names from {list(_GUARD_KINDS)}"
    if objective_kind == "glyph_relational":
        cq = obj.get("coverage_quantifier")
        if cq not in _COVERAGE_QUANTIFIERS:
            return None, f"coverage_quantifier {cq!r} is not one of {list(_COVERAGE_QUANTIFIERS)}"
        raw = obj.get("ink_operator_map")
        if not isinstance(raw, dict):
            return None, "ink_operator_map must be an object mapping each observed ink to an operator"
        ink_map: dict[int, str] = {}
        for ink in inks:
            op = raw.get(str(ink), raw.get(ink))
            if op not in _INK_OPERATORS:
                return None, f"ink_operator_map[{ink}] {op!r} is not one of {list(_INK_OPERATORS)}"
            ink_map[ink] = op
        return {"coverage_quantifier": cq, "ink_operator_map": ink_map, "phase_guards": guards}, ""
    pi = obj.get("preview_interpretation")
    if pi not in _PREVIEW_INTERPRETATIONS:
        return None, f"preview_interpretation {pi!r} is not one of {list(_PREVIEW_INTERPRETATIONS)}"
    return {"preview_interpretation": pi, "phase_guards": guards}, ""


def assemble_instance(
    objective_kind: str,
    transition_kind: str,
    slots: dict[str, Any],
    harness: dict[str, Any],
    inks: list[int],
) -> schema.CellStateHypothesis:
    """Build the full CellStateHypothesis from (model variant + model slots +
    harness_measured values) via schema.from_json — so a malformed assembly raises
    a field-naming ValueError (the retry's error-feedback channel)."""
    if objective_kind == "glyph_relational":
        objective = {
            "kind": "glyph_relational",
            "coverage_quantifier": slots["coverage_quantifier"],
            "ink_operator_map": [[ink, slots["ink_operator_map"][ink]] for ink in inks],
            "no_cell_ink": harness["no_cell_ink"],
        }
    else:
        objective = {
            "kind": "pattern_reference",
            "preview_interpretation": slots["preview_interpretation"],
            "base_snapshot_timing": harness["base_snapshot_timing"],
            "two_read_stability": harness["two_read_stability"],
        }
    if transition_kind == "ordered_cycle":
        transition = {"kind": "ordered_cycle", "order": list(harness["order"])}
    elif transition_kind == "binary_flip":
        transition = {"kind": "binary_flip"}
    else:
        transition = {"kind": "empirical_effect_matrix", "asserted_footprint": harness["asserted_footprint"]}
    phases = [
        {"guard": [_GUARD_JSON[k] for k in kinds], "objective": None}
        for kinds in slots["phase_guards"]
    ]
    return schema.from_json({"objective": objective, "transition_model": transition, "phases": phases})


def fill_instance(
    gs: GroundingService, game: str, llm: Callable[[list[dict[str, str]]], str], record: dict[str, Any]
) -> Optional[schema.CellStateHypothesis]:
    """The two-stage fill: ASK 1 (variant) then ASK 2 (that variant's slots), with
    ONE assembly-error retry on ASK 2. Mutates ``record`` with the variant choice,
    slot values, assembly validity, and retry count. Returns the assembled instance
    or ``None`` on an unrecoverable failure (which the run records as NOT executed)."""
    try:
        variant, verr = parse_variant(llm(build_variant_ask(gs, game)))
    except Exception as exc:  # noqa: BLE001 - offline-safe
        record["plan_outcome"] = f"variant_ask_error: {exc}"
        return None
    if variant is None:
        record["plan_outcome"] = f"variant_invalid: {verr}"
        return None
    objective_kind, model_transition = variant["objective_kind"], variant["transition_kind"]
    # Auto-pair ONLY within the unobservable {ordered_cycle, binary_flip} pair — the
    # compiler supports one of them per objective and they are indistinguishable
    # from cheap probing. An empirical_effect_matrix pick is an OBSERVABLE multi-cell
    # claim: it STANDS as chosen and flows to the verifier's footprint gate.
    if model_transition in _UNOBSERVABLE_TRANSITIONS:
        transition_kind = _COMPATIBLE_TRANSITION.get(objective_kind, model_transition)
    else:
        transition_kind = model_transition
    record["variant_choice"] = {"objective_kind": objective_kind, "transition_kind": transition_kind}
    if model_transition != transition_kind:
        record["model_transition"] = model_transition  # what the model picked, before auto-pairing

    inks = observed_inks(gs)
    harness = harness_measured_values(gs, game)
    convo = build_slot_ask(gs, game, objective_kind)
    error = ""
    for attempt in range(2):  # initial + ONE retry
        if attempt == 1:
            convo = convo + [
                {"role": "assistant", "content": "(previous attempt)"},
                {"role": "user", "content": (
                    f"Your previous slot answer was invalid: {error}. Respond again with ONLY the JSON "
                    "object, using only the allowed values."
                )},
            ]
        try:
            text = llm(convo)
        except Exception as exc:  # noqa: BLE001
            record["plan_outcome"] = f"slot_ask_error: {exc}"
            record["retries"] = attempt
            return None
        slots, serr = parse_slots(text, objective_kind, inks, harness["n_phases"])
        if slots is not None:
            try:
                instance = assemble_instance(objective_kind, transition_kind, slots, harness, inks)
            except ValueError as exc:
                error = str(exc)  # from_json field-naming error
            else:
                record["slot_values"] = _slot_record(slots)
                record["assembly_valid"] = True
                record["retries"] = attempt
                return instance
        else:
            error = serr
    record["retries"] = 1
    record["plan_outcome"] = f"assembly_invalid: {error}"
    return None


def _slot_record(slots: dict[str, Any]) -> dict[str, Any]:
    """A JSON-safe copy of the filled slots (int ink keys -> strings) for the audit
    record."""
    out = dict(slots)
    if "ink_operator_map" in out:
        out["ink_operator_map"] = {str(k): v for k, v in out["ink_operator_map"].items()}
    return out


def run_fill_once(
    game: str, run_index: int, llm: Callable[[list[dict[str, str]]], str]
) -> dict[str, Any]:
    """One fresh-reset FILL-gate run: warm-up -> gather evidence -> variant ask ->
    slot ask (+1 retry) -> assemble -> verifier gate -> (PASS only) execute."""
    target_levels = live._FT09_TARGET_LEVELS if game == "ft09" else live._SC25_TARGET_LEVELS
    level_budget = live._FT09_LEVEL_BUDGET if game == "ft09" else live._SC25_PHASE_BUDGET

    record: dict[str, Any] = {
        "run": run_index,
        "mode": "fill",
        "variant_choice": None,
        "slot_values": None,
        "assembly_valid": False,
        "retries": 0,
        "colour_variety": None,
        "verifier_verdict": None,
        "executed": False,
        "levels_cleared": 0,
        "cast_and_handover": False,
        "actions_per_level": [],
        "discovery_actions": 0,
        "cycle_acquired": False,
        "plan_outcome": "NOT_EXECUTED",
        "rebind_events": 0,
        "outcome": "FAIL",
    }

    env = live.LiveEnv(game)
    env.reset()
    gs = GroundingService()
    if not _warm_up(env, gs):
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        return record
    _gather_evidence(env, gs, game, record)

    instance = fill_instance(gs, game, llm, record)
    if instance is None:
        return record  # variant/slot/assembly failure -> not executed
    _gate_and_execute(env, gs, game, instance, target_levels, level_budget, record, run_index)
    return record


def _oracle_variant(game: str) -> tuple[str, str]:
    """The oracle's (objective_kind, transition_kind) — used by the fill dry-run to
    pick which slot ask to render without an LLM."""
    inst = _oracle_instance(game)
    return inst.objective.KIND, inst.transition_model.KIND


def echoing_llm(
    llm: Callable[[list[dict[str, str]]], str],
) -> Callable[[list[dict[str, str]]], str]:
    """A TRANSPARENT wrapper that echoes each assembled ask (every message) and the
    raw reply to stdout — ``[live-ask]`` / ``[live-reply]`` prefixed lines, flushed,
    before parsing — then returns the model's reply UNCHANGED. Our own kernel log
    for diagnosing the live prompt + pick (both modes, both asks, retries); never
    shown to the model, so no leak concern. Zero behaviour change."""
    def wrapped(messages: list[dict[str, str]]) -> str:
        for message in messages:
            print(f"[live-ask] --- {message['role']} ---", flush=True)
            for line in message["content"].splitlines():
                print(f"[live-ask] {line}", flush=True)
        reply = llm(messages)
        print("[live-reply] --- model reply ---", flush=True)
        for line in reply.splitlines():
            print(f"[live-reply] {line}", flush=True)
        return reply

    return wrapped


# ── movement family (m0r0): SELECT mode ──────────────────────────────────────
#
# The cell-state SELECT path above is specialised to the glyph/lattice grounding.
# The movement family reuses the SAME neutral-serialization + deterministic-shuffle
# + guided-json ask shape, but over MovementHypothesis candidates and a HASH-ROBUST
# STRUCTURAL prose observation (never action numbers as semantics — the action<->axis
# mapping is hash-variable, so the evidence describes the symmetric-row /
# antisymmetric-column STRUCTURE the grounding measured, per the R96 (iii) finding).

_MOVEMENT_GAMES = frozenset({"m0r0"})


def movement_instances() -> tuple[list[tuple[str, "schema_movement.MovementHypothesis"]], str]:
    """The movement candidate set: the m0r0 oracle plus the 6 frozen movement
    mutants (``schema_movement.MUTANTS_MOVEMENT``), each with an INTERNAL name used
    ONLY to map the model's answer back for the audit (never shown to the model).
    Returns ``(named_instances, oracle_internal_name)``. There is NO auto-pairing for
    the movement family (unlike the cell-state ordered_cycle/binary_flip pair): a wrong
    transition/relation pick must flow to the verifier and be caught."""
    oracle_name = "m0r0_oracle"
    named: list[tuple[str, "schema_movement.MovementHypothesis"]] = [
        (oracle_name, schema_movement.m0r0_oracle_instance())
    ]
    for mutant in schema_movement.MUTANTS_MOVEMENT:
        named.append((mutant.name, mutant.instance))
    return named, oracle_name


# Canned m0r0 idx0 structural facts (the decoded, oracle-verified grounding of the
# criterion level) for the offline dry-run render. At real run time these come from
# the live movement grounding via :func:`movement_facts_from_grounding`; the prose is
# identical in shape so the dry-run faithfully previews the live ask.
CANNED_M0R0_FACTS: dict[str, Any] = {
    "n_actors": 2,
    "symmetric_row_pair": True,       # two presses move both regions the same way vertically
    "antisymmetric_column_pair": True,  # two presses move them oppositely horizontally
    "merge_observed": True,           # on the converging press the two regions coincided
    "independent_desync": True,       # a blocked region while its partner still moved
    "n_walls": 89,
    "n_hazards": 0,
}


def movement_observation_summary(facts: dict[str, Any]) -> str:
    """A NEUTRAL, HASH-ROBUST structural summary of the movement grounding: the two
    mobile regions, the symmetric-row / antisymmetric-column response STRUCTURE, the
    merge event, the independent-stay desync, and the static-wall / hazard counts.
    Never cites an action number (the action<->axis numbering is hash-variable)."""
    lines = ["OBSERVATIONS (measured from this run's own probing):"]
    n = facts.get("n_actors", 2)
    lines.append(f"- {_count(n, 'small mobile region')} were tracked (call them region A and region B).")
    if facts.get("symmetric_row_pair"):
        lines.append(
            "- Under one pair of directional presses, BOTH regions moved together in the SAME "
            "vertical direction (a symmetric, row-aligned response)."
        )
    if facts.get("antisymmetric_column_pair"):
        lines.append(
            "- Under another pair of presses, the two regions moved in OPPOSITE horizontal "
            "directions — converging on one press and diverging on the other (an antisymmetric, "
            "column-aligned response)."
        )
    if facts.get("merge_observed"):
        lines.append(
            "- On the converging press the two regions met and coincided on a SINGLE cell "
            "(a merge event)."
        )
    if facts.get("independent_desync"):
        lines.append(
            "- When one region was blocked, the other still moved on the same press (the two are "
            "stepped INDEPENDENTLY, not all-or-nothing)."
        )
    # No static-wall COUNT is reported: it is non-discriminating (identical across all
    # candidates) and a bare count contradicts the candidates' serialized occupancy —
    # an ambiguity the prompt_notation lesson forbids. The hazard line IS kept: it is
    # honest observed evidence (we never curate honest evidence away to steer a pick).
    lines.append(
        f"- {_count(facts.get('n_hazards', 0), 'cell')} triggered a reset-on-entry hazard "
        "(no region entered a hazard on any observed path)."
    )
    return "\n".join(lines)


def build_movement_ask_prompt(
    facts: dict[str, Any],
) -> tuple[list[dict[str, str]], dict[str, str], str]:
    """Assemble the movement SELECT ask: the candidate instances serialized via
    ``schema_movement.to_neutral_json`` under the deterministic ``I1..IN`` shuffle +
    the structural observation. Returns ``(messages, id->internal_name, observation)``.
    Contains no instance names, no 'oracle'/'mutant', and no game id."""
    named, _oracle = movement_instances()
    by_name = dict(named)
    mapping = _shuffle_ids("m0r0", [n for n, _inst in named])

    observation = movement_observation_summary(facts)
    candidate_block = "\n\n".join(
        f"{cid}:\n{json.dumps(schema_movement.to_neutral_json(by_name[mapping[cid]]), indent=2)}"
        for cid in sorted(mapping)
    )
    ids = "|".join(f'"{cid}"' for cid in sorted(mapping))
    system = (
        "You are analysing a small grid puzzle with two movable regions, observed from live "
        "probing. You are given several candidate rule specifications (as structured JSON) that "
        "each claim how the regions move under directional presses and what spatial arrangement "
        "completes the board, plus observations from actual probing. Choose the ONE candidate "
        "whose specification best matches the observations."
    )
    user = (
        "CANDIDATE RULE SPECIFICATIONS:\n\n"
        f"{candidate_block}\n\n"
        f"{observation}\n\n"
        "Which single candidate specification best matches these observations? Weigh BOTH how the "
        "regions move under presses (the transition_model) AND the completion arrangement (the "
        "objective's relation). Respond with ONLY a JSON object, no other text:\n"
        f'{{"choice": {ids}, "confidence": "low"|"medium"|"high", '
        '"evidence": "<=2 sentences citing the observation that decided it"}'
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return messages, mapping, observation


# {oracle, hazard_as_wall} are a CRITERION-LEVEL EQUIVALENCE CLASS: on idx0 no path
# enters a hazard, so terminal_cells=hazard_soft_reset vs blocking_wall compile to the
# IDENTICAL plan (the frozen mutant table pre-declared hazard_as_wall honest-UNKNOWN).
# A model pick of EITHER counts toward the >=2/3 select gate — no auto-pairing (the pick
# still flows to the verifier), the equivalence is only a SCORING note in the audit.
_MOVEMENT_ORACLE_EQUIV = frozenset({"m0r0_oracle", "m0r0_hazard_as_wall"})

# The model_selected FILL surface for movement is the FROZEN
# schema_movement.MOVEMENT_MODEL_SELECTED_SEMANTICS only: the completion RELATION and
# the phase guards. collision_policy + terminal_cells (hazard handling) are
# HARNESS_MEASURED and are NEVER asked (field ownership — never widen a frozen schema).
_MOVEMENT_RELATIONS = ("same_cell", "adjacent", "overlap")


def movement_select_credit(mapped_name: Optional[str]) -> tuple[bool, str]:
    """Score a movement SELECT pick against the criterion-level equivalence class:
    returns ``(counts_toward_gate, audit_note)``. The oracle and its execution-equivalent
    (hazard_as_wall on idx0) both count; every other mutant does not."""
    if mapped_name == "m0r0_oracle":
        return True, "exact-oracle"
    if mapped_name in _MOVEMENT_ORACLE_EQUIV:
        return True, "exact-oracle-or-execution-equivalent, equivalence noted"
    return False, "non-equivalent-mutant"


_MOVEMENT_ROLE_A = ("A", "B")  # which harness-shortlisted region plays role_a


def build_movement_variant_ask(facts: dict[str, Any]) -> list[dict[str, str]]:
    """FILL ASK 1 (variant) — the two model_selected OBJECTIVE slots: the completion
    RELATION and the ACTOR ROLE-BINDING (which of the two shortlisted regions, named A and
    B in the observation, plays role_a). GENERATION (no candidates shown). Leak-clean,
    hash-robust prose; NO harness_measured field (deltas / occupancy / collision / hazard)
    is asked."""
    observation = movement_observation_summary(facts)
    system = (
        "You are analysing a small grid puzzle with two movable regions, observed from "
        "live probing. Identify the ARRANGEMENT of the two regions that completes the board "
        "and which region fills the first role."
    )
    user = (
        f"{observation}\n\n"
        "Choose the completion arrangement of the two regions:\n"
        "- 'same_cell': the board completes when the two regions occupy the SAME single cell "
        "(they merge onto one cell).\n"
        "- 'adjacent': completes when the two regions are in neighbouring cells (side by side), "
        "NOT on the same cell.\n"
        "- 'overlap': completes when the two regions overlap on shared cells without necessarily "
        "coinciding exactly.\n"
        "Also bind the roles: choose which region (A or B) is 'role_a' in the completion "
        "relation (the other region is 'role_b').\n"
        "Respond with ONLY a JSON object, no other text:\n"
        '{"relation": "same_cell"|"adjacent"|"overlap", "role_a": "A"|"B", '
        '"confidence": "low"|"medium"|"high", '
        '"evidence": "<=2 sentences citing the observation that decided it"}'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_movement_variant(text: str) -> tuple[Optional[dict[str, str]], str]:
    """Validate FILL ASK 1: ``relation`` in the closed relation vocabulary and ``role_a``
    the closed 2-option actor role-binding (which region is role_a)."""
    obj = _last_object_with(text, "relation")
    if obj is None:
        return None, "no JSON object with a 'relation' field parsed"
    relation = obj.get("relation")
    if relation not in _MOVEMENT_RELATIONS:
        return None, f"relation {relation!r} is not one of {list(_MOVEMENT_RELATIONS)}"
    role_a = obj.get("role_a")
    if role_a not in _MOVEMENT_ROLE_A:
        return None, f"role_a {role_a!r} is not one of {list(_MOVEMENT_ROLE_A)}"
    confidence = obj.get("confidence", "low")
    if confidence not in _CONFIDENCE_VALUES:
        confidence = "low"
    return {"relation": relation, "role_a": role_a, "confidence": confidence,
            "evidence": str(obj.get("evidence", ""))[:500]}, ""


def build_movement_slot_ask(facts: dict[str, Any], relation: str) -> list[dict[str, str]]:
    """FILL ASK 2 (slots) — the model_selected Phase.guards only. Per-actor deltas,
    occupancy, collision_policy, and hazard handling are HARNESS_MEASURED and are NOT
    asked (field ownership)."""
    n_phases = max(1, len(schema_movement.m0r0_oracle_instance().phases))
    guards = " | ".join(_GUARD_KINDS)
    system = (
        "You have identified the completion arrangement of a two-region grid puzzle. Now "
        "specify which observable conditions gate advancing through the puzzle's phase(s)."
    )
    user = (
        f"The completion arrangement is '{relation}'.\n\n"
        f"- phase_guards: a list of exactly {n_phases} entr"
        + ("y" if n_phases == 1 else "ies")
        + " (one per phase, in order); each entry is a list of guard names that must hold to "
        f"ENTER that phase, drawn from {{{guards}}}. Use [] for a phase with no guard. For a "
        "single-phase board, 'level_advanced' marks that the phase completes when the level "
        "index increases.\n"
        "Respond with ONLY a JSON object, no other text:\n"
        '{"phase_guards": [["level_advanced"]], "confidence": "low"|"medium"|"high", '
        '"evidence": "<=2 sentences"}'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_movement_slots(text: str, n_phases: int) -> tuple[Optional[dict[str, Any]], str]:
    """Validate FILL ASK 2: ``phase_guards`` is a list of ``n_phases`` guard-name lists,
    each name in the closed guard vocabulary."""
    obj = _last_object_with(text, "phase_guards")
    if obj is None:
        return None, "no JSON object with a 'phase_guards' field parsed"
    pg = obj.get("phase_guards")
    if not isinstance(pg, list) or len(pg) != n_phases:
        return None, f"phase_guards must be a list of {n_phases} entries"
    for entry in pg:
        if not isinstance(entry, list) or any(g not in _GUARD_KINDS for g in entry):
            return None, "each phase_guards entry must be a list of known guard names"
    return {"phase_guards": pg, "confidence": obj.get("confidence", "low"),
            "evidence": str(obj.get("evidence", ""))[:500]}, ""


def fill_movement_instance(
    relation: str, role_a: str, phase_guards: list[list[str]]
) -> "schema_movement.MovementHypothesis":
    """Assemble a MovementHypothesis from ALL THREE model_selected slots — the completion
    ``relation``, the actor ROLE-BINDING (``role_a`` = which shortlisted region, "A" or
    "B", plays role_a), and the phase ``guards`` — plus the HARNESS_MEASURED transition
    (per-actor deltas / occupancy / collision policy / hazard handling, from the decoded
    grounding — here the oracle instance's transition for the offline render). Compilable
    via compile_movement_hypothesis; built through ``schema_movement.from_json`` so the
    guard/transition shapes are single-sourced with the cell-state fill."""
    base_json = schema_movement.to_neutral_json(schema_movement.m0r0_oracle_instance())
    # the two shortlisted regions are named "actor_a"/"actor_b" by grounding slot order;
    # role_a="A" binds region A (actor_a) to the first role, "B" swaps the pair.
    region_a, region_b = base_json["objective"]["actors"]
    actors = [region_a, region_b] if role_a == "A" else [region_b, region_a]
    objective = {**base_json["objective"], "actors": actors, "relation": relation}
    phases = [
        {"guard": [_GUARD_JSON[k] for k in kinds], "objective": None}
        for kinds in phase_guards
    ] or base_json["phases"]
    return schema_movement.from_json(
        {"objective": objective, "transition_model": base_json["transition_model"], "phases": phases}
    )


# ── movement live run (env-driven; SELECT + FILL gates) ──────────────────────


def movement_facts_from_grounding(gs: GroundingService) -> dict[str, Any]:
    """Derive the STRUCTURAL, HASH-ROBUST facts dict (the movement_observation_summary
    input) from a live movement grounding: the coupling STRUCTURE (symmetric-row /
    antisymmetric-column, via the shared verifier signature), the merge event, the
    independent-stay desync, the wall/hazard counts. Never an action number — only the
    structure, so the summary is identical in shape to CANNED_M0R0_FACTS."""
    deltas_g = gs.movement_deltas()
    deltas = {} if deltas_g is UNKNOWN else dict(deltas_g.value)
    sig = _coupling_signature(deltas)
    actors_g = gs.movement_actors()
    n_actors = len({aid for aid, _cell in actors_g.value}) if actors_g is not UNKNOWN else 2
    collision = gs.movement_collision_evidence()
    occ = gs.movement_occupancy()
    hazards = gs.movement_hazard_cells()
    return {
        "n_actors": n_actors or 2,
        "symmetric_row_pair": bool(sig["symmetric"]),
        "antisymmetric_column_pair": bool(sig["antisym_col"]),
        "merge_observed": gs.movement_merge_event() is not UNKNOWN,
        "independent_desync": (0 if collision is UNKNOWN else int(collision.value)) > 0,
        "n_walls": 0 if occ is UNKNOWN else len(occ.value.blocked_cells),
        "n_hazards": 0 if hazards is UNKNOWN else len(hazards.value),
    }


def _movement_evidence_from_grounding(gs: GroundingService) -> MovementEvidence:
    """Build the verifier's :class:`MovementEvidence` straight from a LIVE grounding
    (the same fields ``verifier_movement.build_movement_evidence`` reads off a trace-fed
    grounding): acquired deltas, the collision-stay count, whether a merge terminal was
    observed, whether the partner moves, and the hazard cells. Not model-facing."""
    deltas_g = gs.movement_deltas()
    deltas = {} if deltas_g is UNKNOWN else dict(deltas_g.value)
    collision = gs.movement_collision_evidence()
    hazards = gs.movement_hazard_cells()
    return MovementEvidence(
        deltas=deltas,
        collision_obs=0 if collision is UNKNOWN else int(collision.value),
        merge_observed=gs.movement_merge_event() is not UNKNOWN,
        partner_moves=any(d != (0, 0) for d in deltas.values()),
        hazard_cells=frozenset() if hazards is UNKNOWN else frozenset(hazards.value),
    )


def _gather_movement_evidence(
    env: "live.LiveEnv", record: dict[str, Any], run_index: int
) -> GroundingService:
    """Live probing that grounds THIS board's dynamics for the model ask + the verifier
    gate: fresh grounding, warm-up, directional discovery (deltas / collision / hazards),
    then a minimal oracle-plan solve of the criterion board (NO online-learning loop —
    idx0 is divergence-free, measured) so a REAL merge terminal is observed and the
    same_cell objective is verifiable. The grounding is INTERNAL (never shown to the
    model). Mutates ``record`` with the discovery/merge counters; returns the grounding."""
    gs = GroundingService()

    def probe(action_id: int) -> Optional[Grid]:
        env.simple_action(action_id)
        return env.frame()

    frame: Optional[Grid] = None
    for _ in range(live._WARMUP_BUDGET):
        frame = env.frame()
        if frame is None or env.state() in ("GAME_OVER", "NOT_PLAYED"):
            env.reset()
            continue
        break
    if frame is None:
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        return gs
    closed, used, hz = live.discover_deltas(gs, frame, probe)
    record["discovery_actions"] += used
    record["hazard_resets"] += hz
    record["edges_confirmed"] = closed
    cur = env.frame()
    if cur is not None:
        gs.feed(cur)
    if gs.movement_actors() is UNKNOWN or gs.movement_deltas() is UNKNOWN:
        return gs
    # Minimal divergence-free oracle solve to OBSERVE the merge (idx0 never diverges, so
    # no online-learning loop is needed here — the full learning loop is live.execute path).
    instance = schema_movement.m0r0_oracle_instance()
    seeded = gs.movement_blocked_targets()
    walls: set[tuple[int, int]] = set() if seeded is UNKNOWN else set(seeded.value)
    plan = compile_movement_hypothesis(
        instance, gs, extra_walls=walls | live.transient_snapshot(gs)
    )
    for _ in range(live._M0R0_LEVEL_BUDGET + 10):
        frame = env.frame()
        if frame is None:
            break
        if env.state() == "WIN" or gs.movement_merge_event() is not UNKNOWN:
            break
        result = plan.step(frame)
        if isinstance(result, MovementMove):
            env.simple_action(result.action)
            record["discovery_actions"] += 1
            continue
        break  # Terminal (DONE / diverged / grounding-incomplete) — stop gathering
    record["merge_event"] = gs.movement_merge_event() is not UNKNOWN
    return gs


def _new_movement_record(run_index: int, mode: str) -> dict[str, Any]:
    return {
        "run": run_index,
        "mode": mode,
        "choice": None,
        "mapped_instance": None,
        "is_oracle": False,
        "confidence": None,
        "evidence": "",
        "variant_choice": None,
        "slot_values": None,
        "assembly_valid": False,
        "retries": 0,
        "verifier_verdict": None,
        "select_credited": False,
        "select_note": None,
        "executed": False,
        "levels_cleared": 0,
        "merge_event": False,
        "actions_per_level": [],
        "discovery_actions": 0,
        "hazard_resets": 0,
        "edges_confirmed": False,
        "plan_outcome": "NOT_EXECUTED",
        "rebind_events": 0,
        "outcome": "FAIL",
    }


def _execute_movement_instance(
    game: str, run_index: int, instance: "schema_movement.MovementHypothesis",
    record: dict[str, Any], min_levels: int,
) -> None:
    """PASS-only execution: clear the live board with the (selected/filled) instance via
    the SAME per-board re-grounding path as the oracle gate (``live.run_movement_once``).
    Records levels_cleared / plan_outcome; sets outcome PASS iff >= ``min_levels`` cleared."""
    exec_rec = live.run_movement_once(game, run_index, instance=instance)
    record["executed"] = True
    record["levels_cleared"] = exec_rec.get("levels_cleared", 0)
    record["merge_event"] = record["merge_event"] or bool(exec_rec.get("merge_event"))
    record["plan_outcome"] = exec_rec.get("plan_outcome", "NOT_EXECUTED")
    record["actions_per_level"] = exec_rec.get("actions_per_level", [])
    record["rebind_events"] = exec_rec.get("rebind_events", 0)
    if record["levels_cleared"] >= min_levels:
        record["outcome"] = "PASS"


def run_movement_model_once(
    game: str, run_index: int, llm: Callable[[list[dict[str, str]]], str]
) -> dict[str, Any]:
    """One fresh-reset movement SELECT run (mirrors ``run_model_once``): warm-up ->
    gather evidence (live) -> ASK (serialized candidates + structural observation) ->
    verifier gate -> (PASS only) live-execute. Scoring is the CRITERION-LEVEL EQUIVALENCE
    CLASS (correction A): a pick of the oracle OR its execution-equivalent hazard_as_wall
    counts toward the >=2/3 select gate — but the pick STILL flows to the verifier (the
    honest UNKNOWN of hazard_as_wall is recorded, not paired away)."""
    record = _new_movement_record(run_index, "select")
    env = live.LiveEnv(game)
    env.reset()
    gs = _gather_movement_evidence(env, record, run_index)
    if gs.movement_deltas() is UNKNOWN:
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        return record

    facts = movement_facts_from_grounding(gs)
    messages, mapping, _obs = build_movement_ask_prompt(facts)
    ask = ask_once(llm, messages, set(mapping))
    mapped = mapping.get(ask["choice"]) if ask["choice"] is not None else None
    credited, note = movement_select_credit(mapped)
    record.update(
        choice=ask["choice"], mapped_instance=mapped, is_oracle=mapped == "m0r0_oracle",
        confidence=ask["confidence"], evidence=ask["evidence"],
        select_credited=credited, select_note=note,
    )
    if mapped is None:
        record["verifier_verdict"] = "NO_CHOICE"
        return record

    by_name = dict(movement_instances()[0])
    instance = by_name[mapped]
    verdict = verify_movement_with_evidence(instance, _movement_evidence_from_grounding(gs))
    record["verifier_verdict"] = verdict.verdict.value
    # PASS-only execution (the pick's live demonstration). hazard_as_wall is honest UNKNOWN
    # -> not executed, yet still credited toward the gate by the equivalence class.
    if verdict.verdict is schema.Verdict.PASS:
        _execute_movement_instance(game, run_index, instance, record, live._M0R0_TARGET_LEVELS)
    # The SELECT gate is the PICK's equivalence-class membership (correction A), NOT the
    # execution outcome — the oracle's live clear is already proven by the R96 oracle gate.
    record["outcome"] = "PASS" if credited else "FAIL"
    return record


def run_movement_fill_once(
    game: str, run_index: int, llm: Callable[[list[dict[str, str]]], str]
) -> dict[str, Any]:
    """One fresh-reset movement FILL run (variant-first generation): warm-up -> gather
    evidence -> ASK 1 (relation) -> ASK 2 (phase guards, +1 retry) -> assemble a
    MovementHypothesis (model relation + guards + HARNESS-measured transition) -> verifier
    gate -> PASS-only compile + idx0 live clear. The model fills ONLY the frozen
    MOVEMENT_MODEL_SELECTED_SEMANTICS (relation + guards); collision_policy / deltas /
    occupancy / terminal_cells are harness-measured and never asked."""
    record = _new_movement_record(run_index, "fill")
    env = live.LiveEnv(game)
    env.reset()
    gs = _gather_movement_evidence(env, record, run_index)
    if gs.movement_deltas() is UNKNOWN:
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        return record

    facts = movement_facts_from_grounding(gs)
    n_phases = max(1, len(schema_movement.m0r0_oracle_instance().phases))
    # ASK 1 — the completion RELATION (the model_selected objective slot).
    try:
        variant, verr = parse_movement_variant(llm(build_movement_variant_ask(facts)))
    except Exception as exc:  # noqa: BLE001 - offline-safe
        record["plan_outcome"] = f"variant_ask_error: {exc}"
        return record
    if variant is None:
        record["plan_outcome"] = f"variant_invalid: {verr}"
        return record
    relation = variant["relation"]
    role_a = variant["role_a"]
    record["variant_choice"] = {"relation": relation, "role_a": role_a}
    # The actor role-binding is SYMMETRIC-EQUIVALENT under same_cell (a==b is order-blind),
    # so either binding clears idx0; the ask still EXISTS (it can matter under adjacent/
    # overlap) — the equivalence lives in scoring, recorded as an audit note.
    if relation == "same_cell":
        record["role_binding_note"] = "role-binding symmetric under same_cell, equivalence noted"

    # ASK 2 — the phase guards, with ONE assembly/parse-error retry.
    convo = build_movement_slot_ask(facts, relation)
    error = ""
    instance: Optional[schema_movement.MovementHypothesis] = None
    for attempt in range(2):
        if attempt == 1:
            convo = convo + [
                {"role": "assistant", "content": "(previous attempt)"},
                {"role": "user", "content": (
                    f"Your previous answer was invalid: {error}. Respond again with ONLY the JSON "
                    "object, using only the allowed guard names and exactly the required count."
                )},
            ]
        try:
            slots, serr = parse_movement_slots(llm(convo), n_phases)
        except Exception as exc:  # noqa: BLE001
            record["plan_outcome"] = f"slot_ask_error: {exc}"
            record["retries"] = attempt
            return record
        if slots is None:
            error = serr
            continue
        try:
            instance = fill_movement_instance(relation, role_a, slots["phase_guards"])
        except ValueError as exc:
            error = str(exc)  # from_json field-naming error -> the retry channel
            continue
        record["slot_values"] = {"phase_guards": slots["phase_guards"]}
        record["assembly_valid"] = True
        record["retries"] = attempt
        break
    if instance is None:
        record["retries"] = 1
        record["plan_outcome"] = f"assembly_invalid: {error}"
        return record

    verdict = verify_movement_with_evidence(instance, _movement_evidence_from_grounding(gs))
    record["verifier_verdict"] = verdict.verdict.value
    if verdict.verdict is not schema.Verdict.PASS:
        return record  # UNKNOWN / CONTRADICTED never executes (contract)
    # idx0 live clear (the FILL success criterion) via the same per-board re-grounding path.
    _execute_movement_instance(game, run_index, instance, record, 1)
    return record


def movement_model_verdict(runs: list[dict[str, Any]]) -> str:
    """Movement SELECT verdict (correction A): PASS iff >= 2 of the runs picked an
    oracle-EQUIVALENT candidate — the exact oracle OR the execution-equivalent
    hazard_as_wall — the criterion-level equivalence class, not the raw verifier PASS."""
    if not runs:
        return "FAIL"
    credited = sum(1 for r in runs if r.get("mapped_instance") in _MOVEMENT_ORACLE_EQUIV)
    return "PASS" if credited >= 2 else "FAIL"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, choices=["ft09", "sc25", "m0r0"])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", help="output JSON path")
    parser.add_argument(
        "--mode",
        choices=["select", "fill"],
        default="select",
        help="select = pick among serialized instances (step vii); fill = variant-first slot generation (step viii)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="assemble + print the ask(s) from a REPLAYED trace-fed grounding (no LLM, no env)",
    )
    args = parser.parse_args()

    if args.dry_run and args.game in _MOVEMENT_GAMES:
        if args.mode == "fill":
            variant = build_movement_variant_ask(CANNED_M0R0_FACTS)
            n_phases = max(1, len(schema_movement.m0r0_oracle_instance().phases))
            slots = build_movement_slot_ask(CANNED_M0R0_FACTS, "same_cell")
            print("=== FILL DRY-RUN (movement; harness-measured deltas/occupancy/collision/hazard "
                  "are NEVER asked; no game id / oracle hint) ===")
            print("\n--- ASK 1 (VARIANT = relation) SYSTEM ---\n" + variant[0]["content"])
            print("\n--- ASK 1 (VARIANT = relation) USER ---\n" + variant[1]["content"])
            print("\n(the slot ask below is rendered for relation='same_cell')")
            print("\n--- ASK 2 (SLOTS = phase guards) SYSTEM ---\n" + slots[0]["content"])
            print("\n--- ASK 2 (SLOTS = phase guards) USER ---\n" + slots[1]["content"])
            print(f"\n(model fills all three frozen model-selected slots: the actor role-binding "
                  f"(role_a) + the relation (ASK 1) and {n_phases} phase-guard list(s) (ASK 2); "
                  "per-actor deltas / occupancy / collision_policy / terminal_cells are "
                  "harness-measured and never asked)")
            return
        messages, mapping, _obs = build_movement_ask_prompt(CANNED_M0R0_FACTS)
        print("=== ID MAPPING (neutral id -> internal instance name; NOT shown to the model) ===")
        print(json.dumps(mapping, indent=2))
        print("\n=== SYSTEM ===\n" + messages[0]["content"])
        print("\n=== USER ===\n" + messages[1]["content"])
        return

    if args.dry_run:
        gs = _replay_grounding(args.game)
        if args.mode == "fill":
            variant = build_variant_ask(gs, args.game)
            objective_kind, _tk = _oracle_variant(args.game)
            slots = build_slot_ask(gs, args.game, objective_kind)
            print("=== FILL DRY-RUN (harness-measured values ARE shown; no game id / oracle hint) ===")
            print("\n--- ASK 1 (VARIANT) SYSTEM ---\n" + variant[0]["content"])
            print("\n--- ASK 1 (VARIANT) USER ---\n" + variant[1]["content"])
            print(f"\n(the slot ask below is rendered for objective_kind={objective_kind!r})")
            print("\n--- ASK 2 (SLOTS) SYSTEM ---\n" + slots[0]["content"])
            print("\n--- ASK 2 (SLOTS) USER ---\n" + slots[1]["content"])
            return
        messages, mapping, _obs = build_ask_prompt(args.game, gs)
        print("=== ID MAPPING (neutral id -> internal instance name; NOT shown to the model) ===")
        print(json.dumps(mapping, indent=2))
        print("\n=== SYSTEM ===\n" + messages[0]["content"])
        print("\n=== USER ===\n" + messages[1]["content"])
        return

    from admorphiq.harness.registry import openai_compat_llm

    llm = echoing_llm(openai_compat_llm(
        num_predict=int(os.environ.get("HARNESS_PATCH_NUM_PREDICT", "2048")),
        timeout=float(os.environ.get("HARNESS_PATCH_TIMEOUT", "900")),
    ))
    if args.game in _MOVEMENT_GAMES:
        run = run_movement_fill_once if args.mode == "fill" else run_movement_model_once
    else:
        run = run_fill_once if args.mode == "fill" else run_model_once
    runs = [run(args.game, i, llm) for i in range(args.runs)]
    # Movement SELECT scores the equivalence class (correction A); movement FILL and the
    # cell-state modes score the execution outcome (record["outcome"]).
    if args.game in _MOVEMENT_GAMES and args.mode == "select":
        verdict = movement_model_verdict(runs)
    else:
        verdict = model_verdict(runs)
    report = {"game": args.game, "mode": args.mode, "runs": runs, "model_verdict": verdict}
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


def _replay_grounding(game: str) -> GroundingService:
    """A grounding fed from the recorded trace (no env) — the dry-run's stand-in
    for a run's live grounding, so the assembled prompt can be reviewed offline.
    Feeds the game's gold ACTION6 transitions (footprints + cycle/flip evidence)
    then the first frame (cells/glyphs)."""
    import numpy as np

    trace_dir = Path(os.environ.get("R95A_TRACES_DIR", "data/traces"))
    data = np.load(trace_dir / f"{game}.npz", allow_pickle=False)

    def grid(frame: Any) -> Grid:
        arr = np.asarray(frame)
        if arr.ndim == 3:
            arr = arr[-1]
        return tuple(tuple(int(v) for v in row) for row in arr)

    gs = GroundingService()
    gs.feed(grid(data["frames"][0]))
    fed = 0
    for i in range(len(data["actions"])):
        # Level 0 only: cross-level frames are wholesale changes that rebind and
        # reset the per-board frame-state detectors (e.g. the selection-colour
        # signal), so the dry-run grounding stays on one board like a live run's.
        gold6 = bool(data["is_gold"][i]) and int(data["actions"][i]) == 6
        if gold6 and int(data["level_index"][i]) == 0 and fed < 12:
            after = grid(data["next_frames"][i])
            gs.feed_transition(
                grid(data["frames"][i]), 6,
                (int(data["coords_x"][i]), int(data["coords_y"][i])),
                after,
            )
            gs.feed(after)  # mirror the live probe: run the frame-state detectors too
            fed += 1
    return gs


if __name__ == "__main__":
    main()
