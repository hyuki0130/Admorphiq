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
from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService
from admorphiq.hypothesis_select.verifier import Evidence, verify_with_evidence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_hypothesis_live as live  # noqa: E402  (sibling script, loaded by path)

Grid = tuple[tuple[int, ...], ...]

_CONFIDENCE_VALUES = ("low", "medium", "high")
_SC25_PROBE_CELLS = 4  # flip probes to gather footprint evidence for the lattice family


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


def live_observation_summary(gs: GroundingService, game: str) -> str:
    """A NEUTRAL structural summary of the LIVE grounding evidence gathered this
    run — the number of interactive cells and marker symbols, the click-footprint
    histogram, and the acquired colour cycle (glyph family) or flip/pattern facts
    (lattice family). No game id, no template identity, no oracle hint."""
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
        hist = ", ".join(
            f"{size}cell(s)->{count}click(s)" for size, count in sorted(footprints.value.items())
        )
        lines.append(f"- When a click changed the board, how many cells changed (histogram): {hist}")
    else:
        lines.append("- Click-footprint histogram: none observed")

    cycle = gs.get_ordered_cycle()
    if cycle is not UNKNOWN:
        lines.append(f"- An ordered colour cycle of length {len(cycle.value)} was acquired from clicks")

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
        lines.append("- Clicking a cell paints it a distinct selection colour before it commits")

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


# ── live run (env-driven; exercised only under the real gate) ─────────────────


def _gather_evidence(env: "live.LiveEnv", gs: GroundingService, game: str, record: dict[str, Any]) -> None:
    """Probe the board to accumulate footprint (+ cycle / flip) evidence into
    ``gs`` — the ft09 cycle discovery, or a bounded lattice flip-probe for the
    pattern family — so the observation summary and the verifier's transition
    claim have measured evidence."""
    def probe(x: int, y: int) -> Optional[Grid]:
        env.click(x, y)
        return env.frame()

    if game == "ft09":
        closed, used = live.discover_cycle(gs, probe)
        record["discovery_actions"] += used
        record["cycle_acquired"] = closed
        return
    # Lattice family: click a few distinct responsive cells once each to record
    # the single-cell footprint + the selection/cast colour.
    cells = gs.cells()
    if cells is UNKNOWN:
        return
    for _cid, (ry, rx) in cells.value[:_SC25_PROBE_CELLS]:
        before = env.frame()
        after = probe(int(round(rx)), int(round(ry)))
        record["discovery_actions"] += 1
        if before is not None and after is not None:
            gs.feed_transition(before, 6, (int(round(rx)), int(round(ry))), after)


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
    verdict_name, executable = gate_selected_instance(instance, gs, game)
    record["verifier_verdict"] = verdict_name
    if not executable:
        return record  # UNKNOWN / CONTRADICTED never executes (contract)

    # Execute the PASSing pick on a fresh board, via the SAME path as the oracle
    # gate. The reset clears the probe-modified board; the footprint evidence in
    # gs persists (it is level-invariant).
    record["executed"] = True
    env.reset()
    if not _warm_up(env, gs):
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        return record

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
        return record

    live.execute_instance(
        env, gs, game, instance, target_levels, level_budget, record, run_index, rediscover
    )
    success = (
        record["levels_cleared"] >= target_levels
        if game == "ft09"
        else record["cast_and_handover"]
    )
    record["outcome"] = "PASS" if success else "FAIL"
    return record


def model_verdict(runs: list[dict[str, Any]]) -> str:
    """Per-model success = >= 2 of the runs succeeded (the frozen contract's 2/3)."""
    if not runs:
        return "FAIL"
    return "PASS" if sum(1 for r in runs if r.get("outcome") == "PASS") >= 2 else "FAIL"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, choices=["ft09", "sc25"])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", help="output JSON path")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="assemble + print the ask from a REPLAYED trace-fed grounding (no LLM, no env)",
    )
    args = parser.parse_args()

    if args.dry_run:
        gs = _replay_grounding(args.game)
        messages, mapping, _obs = build_ask_prompt(args.game, gs)
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
    runs = [run_model_once(args.game, i, llm) for i in range(args.runs)]
    report = {"game": args.game, "runs": runs, "model_verdict": model_verdict(runs)}
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
        if bool(data["is_gold"][i]) and int(data["actions"][i]) == 6 and fed < 12:
            gs.feed_transition(
                grid(data["frames"][i]), 6,
                (int(data["coords_x"][i]), int(data["coords_y"][i])),
                grid(data["next_frames"][i]),
            )
            fed += 1
    gs.feed(grid(data["frames"][0]))
    return gs


if __name__ == "__main__":
    main()
