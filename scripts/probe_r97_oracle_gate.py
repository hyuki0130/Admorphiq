"""R97 PRE-MODEL ORACLE-CERTIFICATION GATE (the harness proof before any model runs).

Frozen contract: docs/design_r97_self_extension.md — "R97 EVALUATION CONTRACT
(FROZEN 2026-07-23 09:26)". This script builds + runs the four harness proofs
that must pass BEFORE the model authors anything:

  1. EVIDENCE CAPTURE  — live ft09 exact colour-transition tuples, episode-split
     train/held-out, from real runs through the R95b live-driver machinery
     (LiveEnv + discover_cycle imported from scripts/probe_hypothesis_live).
  2. HOLE CERTIFICATION — with the vocabulary minus ``ordered_cycle``,
     ``certify_hole`` must show every offered candidate CONTRADICTED and the
     ablated oracle PASS on the genuine k>=3 evidence.
  3. HAND-AUTHORED ORACLE PATH — a reference ``update`` implementing the ordered
     cycle traverses AST sandbox -> exact held-out verification -> extensional
     equivalence vs the ablated oracle -> AuthoredCellUpdate compiler node -> a
     LIVE ft09 clear within the 4+8-action idx0/idx1 budgets (the R95b criterion).
  4. MUTANT DEFINITIONS — the 6 frozen mutants (identity, reverse order, constant,
     missing wrap, colour hard-coding, k=2-only) must EACH fail held-out exactness
     or compiler parity.

MEASURED HARNESS FINDING (2026-07-23, this build): ft09 is a PER-LEVEL 2-state
toggle with level-specific colour pairs (idx0 {8,9}, idx1 {9,12}, idx2 {8,12});
the genuine k>=3 ordered cycle first appears at a DEEPER level (measured: the 5th
level reached, cycle (8,12,9)). So the case-1 HOLE evidence CANNOT come from idx0
(a 2-state board where binary_flip is not contradicted — correctly a no-hole
control); it must come from the deeper 3-cycle level. This script captures the
deep evidence and documents idx0 as the honest no-hole 2-state control.

No LLM anywhere; no adapter imports; live env runs allowed for THIS gate (it is
harness certification, not model measurement).

Usage:
  ARC_ENVIRONMENTS_DIR=... uv run python scripts/probe_r97_oracle_gate.py \
      --runs 3 --out scripts/rounds/R97/certification.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import probe_hypothesis_live as live  # noqa: E402

from admorphiq.hypothesis_select import schema  # noqa: E402
from admorphiq.hypothesis_select.authored import (  # noqa: E402
    AuthoredCellTransition,
    AuthoredError,
    AuthoredUpdate,
    extensionally_equal,
    validate_authored,
)
from admorphiq.hypothesis_select.compiler import (  # noqa: E402
    Click,
    PlanStatus,
    Terminal,
    compile_hypothesis,
)
from admorphiq.hypothesis_select.exact_transition import (  # noqa: E402
    ColourEdge,
    ColourTransitionEvidence,
    certify_hole,
    evidence_from_edges,
    verify_exact,
)
from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService  # noqa: E402
from admorphiq.hypothesis_select.schema import BinaryFlip, OrderedCycle  # noqa: E402

_MIN_CONF = 2  # grounding's min-probe: an edge is confirmed after >= 2 observations
_MAX_LEVELS = 6  # deep enough to reach the 3-cycle level (measured: the 5th)
_LEVEL_STEP_BUDGET = 160

# The hand-authored ORACLE: advance one step along the ordered palette. The ORDER
# is harness-measured (grounding's acquired cycle, passed AS the palette); the
# model authors only the SUCCESSOR RULE. Generic — no colour literal, no game id.
ORACLE_SOURCE = (
    "def update(colour, click_index, palette):\n"
    "    i = palette.index(colour)\n"
    "    return palette[(i + 1) % len(palette)]\n"
)


def _oracle_fn(colour: int, click_index: int, palette: list[int]) -> int:
    """The canned ablated-oracle rule (ordered_cycle successor) — the reference the
    authored definition's extensional equivalence is checked against."""
    return palette[(palette.index(colour) + 1) % len(palette)]


# ── the 6 frozen definition mutants ─────────────────────────────────────────

MUTANT_SOURCES: dict[str, str] = {
    "identity": (
        "def update(colour, click_index, palette):\n    return colour\n"
    ),
    "reverse_order": (
        "def update(colour, click_index, palette):\n"
        "    i = palette.index(colour)\n"
        "    return palette[(i - 1) % len(palette)]\n"
    ),
    "constant": (
        "def update(colour, click_index, palette):\n    return palette[0]\n"
    ),
    "missing_wrap": (
        "def update(colour, click_index, palette):\n"
        "    i = palette.index(colour)\n"
        "    return palette[i + 1] if i + 1 < len(palette) else palette[i]\n"
    ),
    "colour_hardcode": (
        # Hard-codes the OBSERVED (8,12,9) colours, so it predicts held-out EXACTLY —
        # but on any other ordered palette it falls back to palette[0], diverging from
        # the true cyclic successor: the generalisation failure extensional equivalence
        # catches. The in-palette fallback keeps it valid (survives the return-contract
        # probe) so the failure is specifically extensional, per the design intent.
        "def update(colour, click_index, palette):\n"
        "    if colour == 8:\n        return 12\n"
        "    if colour == 12:\n        return 9\n"
        "    if colour == 9:\n        return 8\n"
        "    return palette[0]\n"
    ),
    "k2_only": (
        # A binary swap of the first two palette entries — correct on a 2-state
        # board, wrong on a 3-cycle (12 -> 8 instead of 12 -> 9).
        "def update(colour, click_index, palette):\n"
        "    return palette[1] if colour == palette[0] else palette[0]\n"
    ),
}


# ── (1) evidence capture ─────────────────────────────────────────────────────


def _confirmed_edges(gs: GroundingService) -> list[tuple[int, int]]:
    """The current epoch's min-probe-confirmed colour edges, from the grounding's
    own cycle-observation tally (the observed transitions the exact verifier
    judges) — reset per level by the grounding, so snapshot per level."""
    return sorted(edge for edge, n in gs._cycle_obs.items() if n >= _MIN_CONF)


def capture_deep_run(run_index: int, log: list[str]) -> dict[str, Any]:
    """One fresh-reset deep live ft09 run: clear levels with the oracle plan,
    snapshotting each level's acquired cycle + confirmed colour edges. Returns the
    per-level records + the idx0/idx1 solve action counts."""
    env = live.LiveEnv("ft09")
    env.reset()
    gs = GroundingService()
    for _ in range(live._WARMUP_BUDGET):
        frame = env.frame()
        if frame is None or env.state() in ("GAME_OVER", "NOT_PLAYED"):
            env.reset()
            continue
        gs.feed(frame)
        if gs.cells() is not UNKNOWN:
            break

    def probe(x: int, y: int) -> Optional[tuple]:
        env.click(x, y)
        return env.frame()

    def rediscover() -> bool:
        if gs.get_ordered_cycle() is not UNKNOWN:
            return True
        closed, _used = live.discover_cycle(gs, probe)
        return closed

    inst = schema.ft09_oracle_instance()
    levels: list[dict[str, Any]] = []
    solve_actions: list[int] = []
    level_ordinal = 0
    for _ in range(_MAX_LEVELS):
        if gs.cells() is UNKNOWN or not rediscover():
            log.append(f"run{run_index} level{level_ordinal}: cycle did not close — stop")
            break
        cyc = gs.get_ordered_cycle()
        order = list(cyc.value) if cyc is not UNKNOWN else []
        edges = _confirmed_edges(gs)
        levels.append({"level": level_ordinal, "order": order, "edges": edges})
        log.append(f"run{run_index} level{level_ordinal}: order={tuple(order)} edges={edges}")
        # step the oracle plan to clear this level (bounded)
        plan = compile_hypothesis(inst, gs)
        start = env.levels()
        steps = 0
        while steps < _LEVEL_STEP_BUDGET:
            frame = env.frame()
            if frame is None:
                env.reset()
                break
            if env.levels() > start:
                break
            result = plan.step(frame)
            if isinstance(result, Click):
                env.click(result.x, result.y)
                steps += 1
            elif isinstance(result, Terminal):
                if result.status in (PlanStatus.GROUNDING_INCOMPLETE, PlanStatus.UNSATISFIABLE) and rediscover():
                    plan = compile_hypothesis(inst, gs)
                    continue
                break
        if env.levels() > start:
            solve_actions.append(steps)
            level_ordinal = env.levels()
        else:
            log.append(f"run{run_index} level{level_ordinal}: stuck after {steps} steps — stop")
            break
    return {"run": run_index, "levels": levels, "solve_actions": solve_actions}


def _first_kcycle(run: dict[str, Any], k: int = 3) -> Optional[dict[str, Any]]:
    """The first per-level record in a run whose acquired cycle has >= k colours."""
    for lvl in run["levels"]:
        if len(lvl["order"]) >= k:
            return lvl
    return None


def _first_2cycle(run: dict[str, Any]) -> Optional[dict[str, Any]]:
    for lvl in run["levels"]:
        if len(lvl["order"]) == 2:
            return lvl
    return None


def build_evidence(
    runs: list[dict[str, Any]], selector, holdout_frac: float = 0.5
) -> tuple[ColourTransitionEvidence, list[int]]:
    """Assemble episode-split evidence: each run contributing a matching level is
    one episode; the later ``holdout_frac`` of contributing episodes are held out
    (verdicts computed on held-out; train carries the synthesis-feedback edges)."""
    edges: list[ColourEdge] = []
    episodes: list[int] = []
    for run in runs:
        lvl = selector(run)
        if lvl is None:
            continue
        ep = run["run"]
        episodes.append(ep)
        for b, a in lvl["edges"]:
            edges.append(ColourEdge(ep, b, a))
    n_hold = max(1, int(round(len(episodes) * holdout_frac))) if episodes else 0
    holdout_eps = set(sorted(episodes)[len(episodes) - n_hold:]) if episodes else set()
    return evidence_from_edges(edges, holdout_eps), sorted(set(episodes))


# ── (3) hand-authored oracle path ────────────────────────────────────────────


def held_out_exactness(
    update: AuthoredUpdate, evidence: ColourTransitionEvidence, ordered_palette: list[int]
) -> dict[str, Any]:
    """Every held-out colour edge must be predicted EXACTLY by the authored update,
    over the harness-measured ordered palette. Returns per-edge results + a bool."""
    results = []
    ok = True
    for e in evidence.holdout:
        try:
            pred = update.predict(e.before, 0, ordered_palette)
        except AuthoredError as exc:
            results.append({"edge": [e.before, e.after], "pred": None, "error": str(exc)})
            ok = False
            continue
        exact = pred == e.after
        ok = ok and exact
        results.append({"edge": [e.before, e.after], "pred": pred, "exact": exact})
    return {"ok": bool(ok and evidence.holdout), "n": len(evidence.holdout), "results": results}


def train_fit(update: AuthoredUpdate, evidence: ColourTransitionEvidence, ordered_palette: list[int]) -> bool:
    """The authored rule must fit every TRAIN edge exactly (the synthesis target)."""
    for e in evidence.train:
        try:
            if update.predict(e.before, 0, ordered_palette) != e.after:
                return False
        except AuthoredError:
            return False
    return bool(evidence.train)


def authored_live_clear(source: str, name: str, log: list[str]) -> dict[str, Any]:
    """Compile the authored instance through the AuthoredCellUpdate node and clear
    ft09 idx0+idx1 LIVE, recompiling a FRESH plan per level (the per-board doctrine —
    a single plan carried across a level boundary keeps a stale pending confirmation
    from the previous board and spuriously DIVERGES; the oracle capture recompiles
    per level too). Success = idx0 <= 4 and idx1 <= 8 actions (the R95b 4+8
    criterion)."""
    base = schema.ft09_oracle_instance()
    instance = schema.CellStateHypothesis(
        objective=base.objective,
        transition_model=AuthoredCellTransition(name=name, source=source),
        phases=base.phases,  # carry the reveal/decoy phase (shared objective logic)
    )
    env = live.LiveEnv("ft09")
    env.reset()
    gs = GroundingService()
    for _ in range(live._WARMUP_BUDGET):
        frame = env.frame()
        if frame is None or env.state() in ("GAME_OVER", "NOT_PLAYED"):
            env.reset()
            continue
        gs.feed(frame)
        if gs.cells() is not UNKNOWN:
            break

    def probe(x: int, y: int) -> Optional[tuple]:
        env.click(x, y)
        return env.frame()

    def rediscover() -> bool:
        if gs.get_ordered_cycle() is not UNKNOWN:
            return True
        closed, _used = live.discover_cycle(gs, probe)
        return closed

    record: dict[str, Any] = {
        "run": 0, "levels_cleared": 0, "actions_per_level": [], "discovery_actions": 0,
        "plan_outcome": "BUDGET", "rebind_events": 0, "cycle_acquired": False,
        "cast_and_handover": False, "source_hash": AuthoredUpdate(source, name).source_hash,
    }
    if gs.cells() is UNKNOWN or not rediscover():
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        return record
    record["cycle_acquired"] = True
    # Use the SHARED continuous execution path (the oracle's path): ft09 idx0->idx1 is
    # a decoy/reveal FLOW (trigger reveals the real puzzle, re-discovery closes the new
    # board's cycle, re-solve) handled continuously by one plan + the rediscover loop.
    # The reveal-trigger now lives in AuthoredCellUpdatePlan, so the authored instance
    # traverses the identical flow.
    record = live.execute_instance(
        env, gs, "ft09", instance, live._FT09_TARGET_LEVELS, live._FT09_LEVEL_BUDGET,
        record, 0, rediscover,
    )
    apl = record.get("actions_per_level", [])
    record["idx0_ok"] = len(apl) >= 1 and apl[0] <= 4
    record["idx1_ok"] = len(apl) >= 2 and apl[1] <= 8
    record["budget_ok"] = bool(record["idx0_ok"] and record["idx1_ok"])
    log.append(f"authored live clear: outcome={record.get('plan_outcome')} actions_per_level={apl} "
               f"idx0<=4={record['idx0_ok']} idx1<=8={record['idx1_ok']}")
    return record


# ── (4) mutants ──────────────────────────────────────────────────────────────


def evaluate_mutant(
    name: str, source: str, evidence: ColourTransitionEvidence, ordered_palette: list[int]
) -> dict[str, Any]:
    """A mutant must FAIL held-out exactness OR extensional equivalence vs the
    ablated oracle (the parity surrogate). Records which check caught it."""
    verdict = validate_authored(source)
    rec: dict[str, Any] = {"mutant": name, "valid": verdict.ok, "reason": verdict.reason}
    if not verdict.ok:
        rec["caught_by"] = "ast_validation"
        rec["fails"] = True
        return rec
    try:
        update = AuthoredUpdate(source, name)
    except AuthoredError as exc:
        # The construction probe (a neutral [0,1] palette) already rejects the rule —
        # e.g. a colour-hard-coded rule returns an out-of-palette colour. That IS a
        # valid catch (the return-in-palette contract), not a harness crash.
        rec["caught_by"] = "return_contract_probe"
        rec["reason"] = str(exc)
        rec["fails"] = True
        return rec
    ho = held_out_exactness(update, evidence, ordered_palette)
    rec["held_out_exact"] = ho["ok"]
    # extensional equivalence vs the oracle over the measured order AND a neutral
    # ordered palette (the generalisation check that catches colour hard-coding).
    neutral = [0, 1, 2]
    try:
        eq_measured, _ = extensionally_equal(update, _oracle_fn, ordered_palette)
    except AuthoredError:
        eq_measured = False
    try:
        eq_neutral, _ = extensionally_equal(update, _oracle_fn, neutral)
    except AuthoredError:
        eq_neutral = False
    rec["ext_equiv_measured"] = eq_measured
    rec["ext_equiv_neutral"] = eq_neutral
    if not ho["ok"]:
        rec["caught_by"] = "held_out_exactness"
    elif not (eq_measured and eq_neutral):
        rec["caught_by"] = "extensional_equivalence"
    else:
        rec["caught_by"] = None
    rec["fails"] = not ho["ok"] or not (eq_measured and eq_neutral)
    return rec


# ── orchestration ────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    log: list[str] = []

    def note(msg: str) -> None:
        log.append(msg)
        print(msg, flush=True)

    # (1) EVIDENCE CAPTURE
    note(f"[gate] capturing {args.runs} deep ft09 runs...")
    runs = [capture_deep_run(i, log) for i in range(args.runs)]
    for r in runs:
        note(f"[gate] run{r['run']}: levels={[(lv['level'], tuple(lv['order'])) for lv in r['levels']]} "
             f"solve_actions={r['solve_actions']}")

    hole_evidence, hole_eps = build_evidence(runs, _first_kcycle)
    nohole_evidence, nohole_eps = build_evidence(runs, _first_2cycle)
    # the measured 3-cycle order (from the first run that reached it)
    order3: list[int] = []
    for r in runs:
        lvl = _first_kcycle(r)
        if lvl is not None:
            order3 = lvl["order"]
            break
    note(f"[gate] k>=3 evidence episodes={hole_eps} order={tuple(order3)} "
         f"holdout_edges={sorted({(e.before, e.after) for e in hole_evidence.holdout})}")
    note(f"[gate] 2-cycle (no-hole control) episodes={nohole_eps} "
         f"holdout_edges={sorted({(e.before, e.after) for e in nohole_evidence.holdout})}")

    result: dict[str, Any] = {"finding": "ft09 is a per-level 2-state toggle; the genuine k>=3 cycle "
                              "appears only at a deeper level — case-1 hole evidence uses that level",
                              "runs": runs, "order3": order3}

    # (2) HOLE CERTIFICATION on the genuine k>=3 evidence
    offered = [BinaryFlip()]  # the vocabulary minus ordered_cycle
    oracle = OrderedCycle(tuple(order3)) if len(order3) >= 3 else None
    if oracle is not None:
        cert = certify_hole(hole_evidence, offered, oracle)
        result["hole_certification"] = {
            "certified": cert.certified,
            "oracle_verdict": cert.oracle_verdict.value,
            "offered_verdicts": [[lbl, v.value] for lbl, v in cert.offered_verdicts],
            "reason": cert.reason,
        }
        note(f"[gate] HOLE CERTIFICATION: certified={cert.certified} oracle={cert.oracle_verdict.value} "
             f"offered={[(lbl, v.value) for lbl, v in cert.offered_verdicts]}")
    else:
        result["hole_certification"] = {"certified": False, "reason": "no k>=3 cycle reached live"}
        note("[gate] HOLE CERTIFICATION: FAILED to reach a k>=3 level live")

    # no-hole control documentation (idx-style 2-state evidence)
    if nohole_evidence.holdout:
        bf = verify_exact(BinaryFlip(), nohole_evidence).value
        oc2 = None
        two = sorted({c for e in nohole_evidence.holdout for c in (e.before, e.after)})
        if len(two) == 2:
            oc2 = verify_exact(OrderedCycle(tuple(two)), nohole_evidence).value
        result["no_hole_control"] = {"binary_flip": bf, "ordered_cycle_k2": oc2}
        note(f"[gate] NO-HOLE CONTROL (2-state): binary_flip={bf} ordered_cycle(k2)={oc2} "
             "(binary_flip PASS => correctly NOT a hole)")

    # (3) HAND-AUTHORED ORACLE PATH
    note("[gate] hand-authored oracle path...")
    sandbox = validate_authored(ORACLE_SOURCE)
    authored_rec: dict[str, Any] = {"ast_valid": sandbox.ok, "ast_reason": sandbox.reason,
                                    "node_count": sandbox.node_count}
    if sandbox.ok and oracle is not None:
        update = AuthoredUpdate(ORACLE_SOURCE, "cyclic_successor")
        ho = held_out_exactness(update, hole_evidence, order3)
        tf = train_fit(update, hole_evidence, order3)
        eq, mm = extensionally_equal(update, _oracle_fn, order3)
        authored_rec.update({
            "train_fit": tf, "held_out_exact": ho["ok"], "held_out_n": ho["n"],
            "extensional_equiv_oracle": eq, "source_hash": update.source_hash,
        })
        note(f"[gate] authored oracle: train_fit={tf} held_out_exact={ho['ok']} "
             f"ext_equiv_oracle={eq}")
    live_clear = authored_live_clear(ORACLE_SOURCE, "cyclic_successor", log)
    authored_rec["live_clear"] = live_clear
    result["authored_oracle"] = authored_rec
    note(f"[gate] authored oracle LIVE: outcome={live_clear.get('plan_outcome')} "
         f"actions_per_level={live_clear.get('actions_per_level')} budget_ok={live_clear.get('budget_ok')}")

    # (4) MUTANTS
    note("[gate] evaluating 6 definition mutants...")
    mutants = [evaluate_mutant(n, s, hole_evidence, order3) for n, s in MUTANT_SOURCES.items()]
    result["mutants"] = mutants
    for m in mutants:
        note(f"[gate] mutant {m['mutant']}: fails={m['fails']} caught_by={m.get('caught_by')}")
    all_mutants_fail = all(m["fails"] for m in mutants)

    # overall gate verdict
    hole_ok = bool(result.get("hole_certification", {}).get("certified"))
    authored_ok = bool(authored_rec.get("held_out_exact") and authored_rec.get("extensional_equiv_oracle")
                       and live_clear.get("budget_ok"))
    gate_pass = hole_ok and authored_ok and all_mutants_fail
    result["gate"] = {
        "hole_certified": hole_ok,
        "authored_oracle_ok": authored_ok,
        "all_mutants_fail": all_mutants_fail,
        "GATE": "PASS" if gate_pass else "FAIL",
    }
    result["log"] = log
    note(f"[gate] === GATE {'PASS' if gate_pass else 'FAIL'} === "
         f"hole={hole_ok} authored={authored_ok} mutants={all_mutants_fail}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    note(f"[gate] wrote {out_path}")


if __name__ == "__main__":
    main()
