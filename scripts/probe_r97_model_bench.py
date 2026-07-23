"""R97 tier-2 self-extension MODEL bench — the 4-case driver (scaffolding).

Frozen+amended contract: docs/design_r97_self_extension.md ("R97 EVALUATION
CONTRACT" + the 325f097 amendment). The pre-model oracle-certification gate
(scripts/probe_r97_oracle_gate.py) has already PASSED; this drives the OFFLINE
MODEL over the four cases and scores detection separately from authoring.

Four cases (all on ft09, per the amended evidence sourcing):
  1. HOLE (idx4 k>=3 evidence): vocabulary MINUS ordered_cycle + the extend
     escape hatch. Success = `extend` proposed AND the authored definition passes
     TRAIN fit + held-out exactness. >=2/3 runs = hole recall.
  2. NO-HOLE (idx0 2-state evidence): FULL vocabulary. Success = a correct offered
     rule SELECTED; ANY `extend` is a false positive. >=2/3 = no-hole specificity.
  3. EVIDENCE-BLIND (1 run): transition lines withheld. A successful reconstruction
     = LEAKAGE (invalidates case 1) — recorded, flagged.
  4. INSUFFICIENT-EVIDENCE (1 run): a single transition. Expected `abstain`;
     invention (select/extend) = calibration failure — recorded, does not gate.

Output union (EXCLUSIVE): select(candidate) | extend(name, source) | abstain.
A mixed response (e.g. a select carrying a source) is INVALID -> ONE format retry.
Evidence is prose-only exact colour-transition tuples ("colour X became Y after a
click on that cell") per the prompt_notation_misparse lesson; the model never sees
a game id, an instance/rule provenance label, or the ablated rule's shape.

The extend path: model source -> AST sandbox (authored.validate_authored) -> exact
verifier (TRAIN fit + held-out exactness over the harness-measured ordered palette)
-> [gold gate, optional] AuthoredCellUpdate compile + live ft09 clear ([4,8]
budgets) — the exact path the hand-authored oracle certified.

No model call happens in --dry-run (renders the 4 case prompts for review). The
run mode uses the vLLM OpenAI backend via admorphiq.harness.registry, exactly like
the R95b model bench.

Usage:
  uv run python scripts/probe_r97_model_bench.py --dry-run        # render 4 prompts
  uv run python scripts/probe_r97_model_bench.py --out r.json     # paired run (needs LLM + env)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import probe_r97_oracle_gate as gate  # noqa: E402
from probe_hypothesis_model import echoing_llm  # noqa: E402

from admorphiq.hypothesis_select.authored import (  # noqa: E402
    AuthoredError,
    AuthoredUpdate,
    validate_authored,
)
from admorphiq.hypothesis_select.exact_transition import (  # noqa: E402
    ColourTransitionEvidence,
)

_CERT_DEFAULT = REPO / "scripts" / "rounds" / "R97" / "certification.json"

# The transition-rule vocabulary the model chooses among. Descriptions are generic
# and leakage-safe: the HOLE case offers everything EXCEPT ordered_cycle and never
# describes a cyclic/k-length successor (the model must re-derive that shape from
# the prose transitions alone).
_VOCAB_DESC: dict[str, str] = {
    "binary_flip": "Clicking a cell flips it between its two colours (a two-state toggle).",
    "empirical_effect_matrix": (
        "Clicking recolours a fixed, measured SET of cells around the click "
        "(a stencil footprint), leaving the rest unchanged."
    ),
    "ordered_cycle": (
        "Clicking a cell advances it one step through a fixed ordered colour "
        "sequence, wrapping from the last colour back to the first."
    ),
}
_HOLE_VOCAB = ("binary_flip", "empirical_effect_matrix")  # full vocab MINUS ordered_cycle
_FULL_VOCAB = ("binary_flip", "empirical_effect_matrix", "ordered_cycle")
# A correct NO-HOLE pick: binary_flip IS ordered_cycle(k=2), so either expresses the
# 2-state toggle (Codex correction 2) — both count as a correct SELECT.
_NO_HOLE_CORRECT = frozenset({"binary_flip", "ordered_cycle"})

_DEFINITION_CONTRACT = (
    "If you extend, author ONE pure Python function with EXACTLY this signature:\n"
    "    def update(colour, click_index, palette):\n"
    "        ...\n"
    "        return <next colour, an int in palette>\n"
    "Rules: no imports, no I/O, no global state, at most 20 lines. Use ONLY literals, "
    "arithmetic, comparisons (including `in`), boolean and conditional expressions, "
    "if/elif/else, and list/tuple/dict LITERALS indexed with `[]` — no method calls or "
    "attribute access (e.g. no `.get()`). `colour` is the "
    "clicked cell's CURRENT colour; `click_index` is how many times this cell has "
    "already been clicked; `palette` is the ordered list of colours in play. Return "
    "the cell's next colour (an int already in `palette`). It runs in a sandbox and "
    "is checked against held-out transitions — it must predict them exactly."
)

_OUTPUT_UNION = (
    "Respond with ONLY ONE JSON object, no other text, in EXACTLY one of these three "
    "shapes (do NOT mix them):\n"
    '  {"action": "select", "candidate": "<one offered rule name>"}\n'
    '  {"action": "extend", "name": "<short new rule name>", '
    '"source": "def update(colour, click_index, palette): ..."}\n'
    '  {"action": "abstain", "reason": "insufficient_evidence"}\n'
    "Choose `select` if one offered rule matches the transitions; `extend` if NONE of "
    "the offered rules can express them and you can author a rule that does; `abstain` "
    "if the evidence is insufficient to decide."
)


# ── evidence ─────────────────────────────────────────────────────────────────


def _prose(edges: list[tuple[int, int]]) -> str:
    """Exact colour-transition tuples as prose (deduplicated, deterministic order)."""
    seen: list[tuple[int, int]] = []
    for e in edges:
        if e not in seen:
            seen.append(e)
    return "\n".join(f"- colour {b} became colour {a} after a click on that cell." for b, a in sorted(seen))


def load_evidence(cert_path: Path) -> dict[str, Any]:
    """Build the four cases' colour-transition evidence from a committed
    certification.json (the oracle gate's captured live runs) — no env needed. The
    HOLE evidence is the idx4 k>=3 cycle; the NO-HOLE evidence is the 2-state
    idx0 cycle. TRAIN edges feed the prompt; HELD-OUT edges verify an extend."""
    cert = json.loads(cert_path.read_text())
    runs = cert["runs"]
    order3 = cert.get("order3") or []
    hole_ev, _eps = gate.build_evidence(runs, gate._first_kcycle)
    nohole_ev, _eps2 = gate.build_evidence(runs, gate._first_2cycle)
    return {"hole": hole_ev, "no_hole": nohole_ev, "order": list(order3)}


def _train_edges(ev: ColourTransitionEvidence) -> list[tuple[int, int]]:
    return [(e.before, e.after) for e in ev.train] or [(e.before, e.after) for e in ev.holdout]


# ── prompt assembly (per case) ───────────────────────────────────────────────


def _vocab_block(names: tuple[str, ...]) -> str:
    return "\n".join(f"- {n}: {_VOCAB_DESC[n]}" for n in names)


def build_case_prompt(case: str, evidence: dict[str, Any]) -> list[dict[str, str]]:
    """Assemble the (system, user) messages for a case. No game id, no rule
    provenance, no hint of the ablated rule's shape; prose-only transitions."""
    if case == "hole":
        vocab, edges = _HOLE_VOCAB, _train_edges(evidence["hole"])
        transitions = _prose(edges)
    elif case == "no_hole":
        vocab, edges = _FULL_VOCAB, _train_edges(evidence["no_hole"])
        transitions = _prose(edges)
    elif case == "evidence_blind":
        vocab = _HOLE_VOCAB
        transitions = "(no transition observations are available for this board.)"
    elif case == "insufficient":
        vocab = _HOLE_VOCAB
        one = _train_edges(evidence["hole"])[:1]
        transitions = _prose(one)
    else:
        raise ValueError(f"unknown case {case!r}")

    system = (
        "You are analysing how clicks change a small interactive grid puzzle, from "
        "observed transitions. You are given a fixed menu of candidate rule TYPES and "
        "the exact colour changes clicks produced. Decide which single rule type "
        "explains the observations — or, if none of the offered types can, author a "
        "new rule under a fixed contract, or abstain if the evidence is insufficient."
    )
    user = (
        "OFFERED RULE TYPES:\n"
        f"{_vocab_block(vocab)}\n\n"
        "OBSERVED TRANSITIONS (each line: a clicked cell's colour before and after):\n"
        f"{transitions}\n\n"
        f"{_DEFINITION_CONTRACT}\n\n"
        f"{_OUTPUT_UNION}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ── output union parsing (exclusive select | extend | abstain, one retry) ─────


def parse_action(text: str, offered: tuple[str, ...]) -> tuple[Optional[dict[str, Any]], str]:
    """Parse the exclusive output union. Returns ``(parsed_or_None, error)``. A
    mixed response (fields from more than one arm) is INVALID."""
    parsed = _last_json_object(text)
    if parsed is None:
        return None, "no JSON object parsed"
    action = parsed.get("action")
    if action not in ("select", "extend", "abstain"):
        return None, f"action must be select|extend|abstain, got {action!r}"
    has_candidate = "candidate" in parsed
    has_source = "source" in parsed or "name" in parsed
    if action == "select":
        if has_source:
            return None, "mixed response: a select must not carry name/source"
        cand = parsed.get("candidate")
        if cand not in offered:
            return None, f"candidate {cand!r} is not one of {list(offered)}"
        return {"action": "select", "candidate": cand}, ""
    if action == "extend":
        if has_candidate:
            return None, "mixed response: an extend must not carry a candidate"
        name, source = parsed.get("name"), parsed.get("source")
        if not isinstance(name, str) or not isinstance(source, str) or not source.strip():
            return None, "extend requires string 'name' and non-empty 'source'"
        return {"action": "extend", "name": name[:60], "source": source}, ""
    return {"action": "abstain", "reason": str(parsed.get("reason", ""))[:200]}, ""


def _last_json_object(text: str) -> Optional[dict[str, Any]]:
    import json as _json

    depth = 0
    start = -1
    candidates: list[str] = []
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                candidates.append(text[start:i + 1])
    for blob in reversed(candidates):
        try:
            parsed = _json.loads(blob)
        except _json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "action" in parsed:
            return parsed
    return None


def ask_action(
    llm: Callable[[list[dict[str, str]]], str],
    messages: list[dict[str, str]],
    offered: tuple[str, ...],
) -> dict[str, Any]:
    """One ask + validate with ONE format-error retry (the R95 ask shape)."""
    convo = list(messages)
    try:
        text = llm(convo)
    except Exception as exc:  # noqa: BLE001 - offline-safe
        return {"action": None, "attempts": 1, "error": str(exc)}
    parsed, err = parse_action(text, offered)
    if parsed is not None:
        return {**parsed, "attempts": 1, "error": None}
    convo.append({"role": "assistant", "content": text})
    convo.append({"role": "user", "content": (
        f"Your response was invalid ({err}). Reply with ONLY one JSON object in exactly "
        "one of the three shapes (select/extend/abstain), with no extra fields."
    )})
    try:
        text2 = llm(convo)
    except Exception as exc:  # noqa: BLE001
        return {"action": None, "attempts": 2, "error": str(exc)}
    parsed2, err2 = parse_action(text2, offered)
    if parsed2 is not None:
        return {**parsed2, "attempts": 2, "error": None}
    return {"action": None, "attempts": 2, "error": err2}


# ── extend evaluation (the authoring path) ───────────────────────────────────


def evaluate_extend(source: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Score a model-authored `update`: AST validity -> TRAIN fit + held-out
    exactness over the harness-measured ordered palette (the exact verifier). The
    passing bar for hole recall = valid AND train_fit AND held_out_exact."""
    verdict = validate_authored(source)
    rec: dict[str, Any] = {"ast_valid": verdict.ok, "ast_reason": verdict.reason}
    if not verdict.ok:
        rec.update({"train_fit": False, "held_out_exact": False, "passes": False})
        return rec
    order = evidence["order"]
    hole_ev = evidence["hole"]
    try:
        update = AuthoredUpdate(source, "model_authored")
    except AuthoredError as exc:
        rec.update({"train_fit": False, "held_out_exact": False, "passes": False,
                    "sandbox_error": str(exc)})
        return rec
    tf = gate.train_fit(update, hole_ev, order)
    ho = gate.held_out_exactness(update, hole_ev, order)
    rec.update({"train_fit": bool(tf), "held_out_exact": bool(ho["ok"]),
                "held_out_n": ho["n"], "source_hash": update.source_hash})
    rec["passes"] = bool(verdict.ok and tf and ho["ok"])
    return rec


def maybe_gold_gate(rec: dict[str, Any], source: str, enabled: bool) -> None:
    """When a passing extend + --gold-gate: run the AuthoredCellUpdate live ft09
    clear ([4,8] budgets) — the same path the hand-authored oracle certified. Off
    by default (the paired bench scores TRAIN+held-out per the contract; the live
    clear was already certified by the oracle gate)."""
    if not (enabled and rec.get("passes")):
        return
    live = gate.authored_live_clear(source, "model_authored", [])
    rec["live_clear"] = {k: live.get(k) for k in ("plan_outcome", "actions_per_level", "budget_ok")}


# ── per-case run + scoring ───────────────────────────────────────────────────


def _score_run(case: str, action_rec: dict[str, Any], evidence: dict[str, Any], gold_gate: bool) -> dict[str, Any]:
    """Score one model reply for a case. `success`/`false_positive`/`leakage`/
    `abstained` are set per the case's contract."""
    rec: dict[str, Any] = dict(action_rec)
    action = action_rec.get("action")
    if case == "hole":
        if action == "extend":
            ext = evaluate_extend(action_rec["source"], evidence)
            maybe_gold_gate(ext, action_rec["source"], gold_gate)
            rec["extend_eval"] = ext
            rec["success"] = bool(ext["passes"])
        else:
            rec["success"] = False  # forced-select or abstain on a genuine hole
    elif case == "no_hole":
        rec["success"] = action == "select" and action_rec.get("candidate") in _NO_HOLE_CORRECT
        rec["false_positive"] = action == "extend"  # any extend on a no-hole board
    elif case == "evidence_blind":
        if action == "extend":
            ext = evaluate_extend(action_rec["source"], evidence)
            rec["extend_eval"] = ext
            rec["leakage"] = bool(ext["passes"])  # reconstructing without evidence = leakage
        else:
            rec["leakage"] = False
    elif case == "insufficient":
        rec["abstained"] = action == "abstain"
        rec["invented"] = action in ("select", "extend")  # calibration failure (non-gating)
    return rec


def run_case(case: str, n_runs: int, llm: Callable[[list[dict[str, str]]], str],
             evidence: dict[str, Any], gold_gate: bool) -> dict[str, Any]:
    """Run one case for ``n_runs`` model samples + compute the case verdict."""
    offered = _FULL_VOCAB if case == "no_hole" else _HOLE_VOCAB
    messages = build_case_prompt(case, evidence)
    runs = [_score_run(case, ask_action(llm, messages, offered), evidence, gold_gate) for _ in range(n_runs)]
    verdict: dict[str, Any] = {"case": case, "n_runs": n_runs, "runs": runs}
    if case == "hole":
        n = sum(1 for r in runs if r.get("success"))
        verdict.update({"hole_recall": f"{n}/{n_runs}", "pass": n * 3 >= n_runs * 2})
    elif case == "no_hole":
        n = sum(1 for r in runs if r.get("success"))
        fp = sum(1 for r in runs if r.get("false_positive"))
        verdict.update({"no_hole_specificity": f"{n}/{n_runs}", "false_positives": fp,
                        "pass": n * 3 >= n_runs * 2})
    elif case == "evidence_blind":
        verdict["leakage_detected"] = any(r.get("leakage") for r in runs)
    elif case == "insufficient":
        verdict.update({"abstained": sum(1 for r in runs if r.get("abstained")),
                        "invented": sum(1 for r in runs if r.get("invented"))})
    return verdict


# ── dry-run + main ───────────────────────────────────────────────────────────

_CASES = ("hole", "no_hole", "evidence_blind", "insufficient")
_CASE_RUNS = {"hole": 3, "no_hole": 3, "evidence_blind": 1, "insufficient": 1}


def render_dry_run(evidence: dict[str, Any]) -> str:
    """Render all four case prompts for human review (no LLM, no env)."""
    out: list[str] = []
    for case in _CASES:
        offered = _FULL_VOCAB if case == "no_hole" else _HOLE_VOCAB
        messages = build_case_prompt(case, evidence)
        out.append(f"\n{'=' * 78}\n=== CASE: {case}  (offered vocab: {list(offered)}, "
                   f"runs: {_CASE_RUNS[case]}) ===\n{'=' * 78}")
        out.append("\n--- SYSTEM ---\n" + messages[0]["content"])
        out.append("\n--- USER ---\n" + messages[1]["content"])
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="output JSON path (run mode)")
    parser.add_argument("--evidence", default=str(_CERT_DEFAULT),
                        help="certification.json to source colour-transition evidence from")
    parser.add_argument("--dry-run", action="store_true",
                        help="render the 4 case prompts (no LLM, no env)")
    parser.add_argument("--gold-gate", action="store_true",
                        help="on a passing extend, also run the live ft09 clear (needs env)")
    args = parser.parse_args()

    evidence = load_evidence(Path(args.evidence))

    if args.dry_run:
        print(render_dry_run(evidence))
        return

    import os

    from admorphiq.harness.registry import openai_compat_llm

    llm = echoing_llm(openai_compat_llm(
        num_predict=int(os.environ.get("HARNESS_PATCH_NUM_PREDICT", "4096")),
        timeout=float(os.environ.get("HARNESS_PATCH_TIMEOUT", "900")),
    ))
    verdicts = [run_case(c, _CASE_RUNS[c], llm, evidence, args.gold_gate) for c in _CASES]
    hole = next(v for v in verdicts if v["case"] == "hole")
    no_hole = next(v for v in verdicts if v["case"] == "no_hole")
    seed_pass = bool(hole.get("pass") and no_hole.get("pass"))
    report = {
        "cases": verdicts,
        "seed_pass": seed_pass,
        "hole_recall": hole.get("hole_recall"),
        "no_hole_specificity": no_hole.get("no_hole_specificity"),
    }
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
