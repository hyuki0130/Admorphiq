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

from admorphiq.hypothesis_select import schema
from admorphiq.hypothesis_select.compiler import compile_hypothesis
from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService
from admorphiq.hypothesis_select.verifier import Evidence, verify_with_evidence

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


def live_observation_summary(
    gs: GroundingService, game: str, colour_variety: Optional[tuple[int, int]] = None
) -> str:
    """A NEUTRAL structural summary of the LIVE grounding evidence gathered this
    run — the number of interactive cells and marker symbols, the click-footprint
    histogram, the DISTINCT COLOURS one cell takes under repeated clicks (the
    ordered-cycle-vs-binary-flip discriminator), and the pattern facts (lattice
    family). No game id, no template identity, no oracle hint. ``colour_variety``
    is the measured ``(distinct_colours, clicks)``; when absent it falls back to the
    acquired cycle length."""
    lines = ["OBSERVATIONS (measured from this run's own probing):"]

    cells = gs.cells()
    n_cells = len(cells.value) if cells is not UNKNOWN else 0
    lines.append(f"- Interactive cells detected: {n_cells}")

    # NOTE: a distinct-colours-per-cell count is NOT reported — MEASURED to be an
    # inverted/unreliable ordered-cycle-vs-binary-flip signal (ft09 cells observably
    # toggle between 2 colours; the third cycle colour is latent, while a lattice
    # cell's transient selection colour inflates its count to 3). ``colour_variety``
    # is measured for the audit record only. The honest observable click-style line
    # (selection-then-commit vs direct change) is emitted below.
    _ = colour_variety

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
        hist = ", ".join(
            f"{size}cell(s)->{count}click(s)" for size, count in sorted(footprints.value.items())
        )
        lines.append(f"- When a click changed the board, how many cells changed (histogram): {hist}")
    else:
        lines.append("- Click-footprint histogram: none observed")

    evidence = gs.pattern_evidence()
    if evidence is not UNKNOWN:
        # Structure only — NOT the majority-based cells_matching count, which reads
        # spuriously high on an unsolved board (the base-parity artifact) and would
        # mislead the objective choice.
        lines.append(
            f"- A separate target pattern is displayed beside the grid, over the same "
            f"{evidence.value['total']} cells; the cells take two colours"
        )
    if gs.cast_colour_seen():
        # Single-cell scope is explicit: the selection colour lands on THE CLICKED
        # cell only (measured: the select-colour transition changes exactly 1 lattice
        # cell), so this is not misread as a multi-cell neighbourhood effect.
        lines.append(
            "- Clicking a cell paints THAT ONE CELL a temporary selection colour; a later click commits it"
        )
    else:
        lines.append(
            "- Clicking a cell changed THAT ONE CELL directly to another colour, with no separate selection step"
        )

    return "\n".join(lines)


# ── selection ask (serialized instances, guided-json) ─────────────────────────


def build_ask_prompt(
    game: str, gs: GroundingService, colour_variety: Optional[tuple[int, int]] = None
) -> tuple[list[dict[str, str]], dict[str, str], str]:
    """Assemble the model selection ask from the LIVE grounding ``gs``: the
    candidate instances serialized via ``schema.to_neutral_json`` under a
    deterministic ``I1..IN`` shuffle + the structural observation summary. Returns
    ``(messages, id->internal_name mapping, observation_text)``. Contains no
    instance names, no 'oracle'/'mutant', and no game id."""
    named, _oracle = instances_for_game(game)
    by_name = dict(named)
    mapping = _shuffle_ids(game, [n for n, _inst in named])

    observation = live_observation_summary(gs, game, colour_variety)
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
    """Probe the board to accumulate footprint + colour-variety evidence into
    ``gs`` — the ft09 cycle discovery, or a repeated-click colour probe for the
    pattern family — so the observation summary and the verifier's transition
    claim have measured evidence. Sets ``record['colour_variety']`` = the distinct
    colours ONE cell takes under repeated clicks (the cycle-vs-flip discriminator)."""
    def probe(x: int, y: int) -> Optional[Grid]:
        env.click(x, y)
        return env.frame()

    if game == "ft09":
        # Acquire the colour cycle the COMPILER needs for execution (the tested path).
        closed, used = live.discover_cycle(gs, probe)
        record["discovery_actions"] += used
        record["cycle_acquired"] = closed
    # The colour-variety count for the ask is measured DIRECTLY by repeated clicks
    # (both games) — get_ordered_cycle can close a PARTIAL cycle and under-report
    # the distinct-colour count (measured: ft09 acquired length 2, not 3), which
    # would falsely signal a binary flip.
    record["colour_variety"] = measure_colour_variety(env, gs, game, record)


def measure_colour_variety(
    env: "live.LiveEnv", gs: GroundingService, game: str, record: dict[str, Any], clicks: int = 5
) -> Optional[tuple[int, int]]:
    """Repeatedly click ONE responsive cell and count the distinct colours it takes
    — the ordered-cycle (3+) vs binary-flip (2) discriminator, and footprint
    evidence. Responsiveness-adaptive: skips inert cells (each probe still records a
    footprint). Returns ``(distinct_colours, clicks)`` or ``None`` when no cell is
    responsive."""
    cells = gs.cells()
    if cells is UNKNOWN:
        return None
    for cid, (ry, rx) in cells.value:
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

    messages, mapping, _obs = build_ask_prompt(game, gs, record["colour_variety"])
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


def build_variant_ask(
    gs: GroundingService, game: str, colour_variety: Optional[tuple[int, int]] = None
) -> list[dict[str, str]]:
    """ASK 1 — the VARIANT: from the live observation summary (no serialized
    instances — this is generation), choose the objective + transition category."""
    observation = live_observation_summary(gs, game, colour_variety)
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


def build_slot_ask(
    gs: GroundingService, game: str, objective_kind: str,
    colour_variety: Optional[tuple[int, int]] = None,
) -> list[dict[str, str]]:
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
    user = f"{live_observation_summary(gs, game, colour_variety)}\n\n{body}"
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
    variety = record.get("colour_variety")
    try:
        variant, verr = parse_variant(llm(build_variant_ask(gs, game, variety)))
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
    convo = build_slot_ask(gs, game, objective_kind, variety)
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


def _representative_variety(game: str) -> Optional[tuple[int, int]]:
    """The colour variety a live run would MEASURE, derived from the oracle's
    transition model — for the dry-run only (no env to probe). ordered_cycle -> its
    length; binary_flip -> 2."""
    tm = _oracle_instance(game).transition_model
    if isinstance(tm, schema.OrderedCycle):
        n = len(tm.order) or 3
        return (n, n)
    if isinstance(tm, schema.BinaryFlip):
        return (2, 5)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, choices=["ft09", "sc25"])
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

    if args.dry_run:
        gs = _replay_grounding(args.game)
        variety = _representative_variety(args.game)  # a live run measures this; here derived for review
        if args.mode == "fill":
            variant = build_variant_ask(gs, args.game, variety)
            objective_kind, _tk = _oracle_variant(args.game)
            slots = build_slot_ask(gs, args.game, objective_kind, variety)
            print("=== FILL DRY-RUN (harness-measured values ARE shown; no game id / oracle hint) ===")
            print("\n--- ASK 1 (VARIANT) SYSTEM ---\n" + variant[0]["content"])
            print("\n--- ASK 1 (VARIANT) USER ---\n" + variant[1]["content"])
            print(f"\n(the slot ask below is rendered for objective_kind={objective_kind!r})")
            print("\n--- ASK 2 (SLOTS) SYSTEM ---\n" + slots[0]["content"])
            print("\n--- ASK 2 (SLOTS) USER ---\n" + slots[1]["content"])
            return
        messages, mapping, _obs = build_ask_prompt(args.game, gs, variety)
        print("=== ID MAPPING (neutral id -> internal instance name; NOT shown to the model) ===")
        print(json.dumps(mapping, indent=2))
        print("\n=== SYSTEM ===\n" + messages[0]["content"])
        print("\n=== USER ===\n" + messages[1]["content"])
        return

    from admorphiq.harness.registry import openai_compat_llm

    llm = openai_compat_llm(
        num_predict=int(os.environ.get("HARNESS_PATCH_NUM_PREDICT", "2048")),
        timeout=float(os.environ.get("HARNESS_PATCH_TIMEOUT", "900")),
    )
    run = run_fill_once if args.mode == "fill" else run_model_once
    runs = [run(args.game, i, llm) for i in range(args.runs)]
    report = {"game": args.game, "mode": args.mode, "runs": runs, "model_verdict": model_verdict(runs)}
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
