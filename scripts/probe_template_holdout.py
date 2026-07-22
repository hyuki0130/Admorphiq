"""R94 D5 paired-holdout runner — conquered-solution template vs the model's
adaptation of it, on a HELD-OUT game.

The pre-registration is frozen in ``.wiki/wiki/rounds/r94_adapter-template.md``
("D5 PRE-REGISTRATION"). One invocation = one arm. Per the frozen protocol, for
each arm we:

  1. TEMPLATE BASELINE — drive the arm's VERBATIM conquered card
     (``source_card(arm)``) through the ``run_code`` sandbox from RESET for
     ``--budget`` actions on the target game, capturing the core's own trace via a
     ``_tr`` list printed out of the driver (the sandbox has no other channel).
  2. ADAPTATION ASK — ONE LLM call: the card + the core's recent decisions + the
     baseline-run summary + an instruction to diagnose how THIS (different) game
     differs and emit the FULL ADAPTED core. Validated (1 error-feedback retry).
  3. ADAPTATION REPLAY — drive the ADAPTED core through the SAME sandbox path
     (``run_patched_step`` + ``_card_prelude``) from RESET for ``--budget``.
  4. SELECTION — the better of {verbatim template, adapted} by the lexicographic
     rule (levels > distinct_states > distinct_transitions, noop tie-break),
     decided ON the adaptation replay.
  5. FRESH SCORE — run the SELECTED variant ONCE MORE from RESET on a
     freshly-made env instance for the REPORTED score (select-on-replay,
     score-once-fresh).

The target game's own adapter/card/constants/wiki/traces never enter any prompt
(the holdout rule) — the ONLY per-game information the model sees is what it
observes through the sandbox contract during the baseline run.

Usage (on the Kaggle-matched VM, offline Arcade + a vLLM OpenAI server):
  uv run python scripts/probe_template_holdout.py --arm simdfs --game sk48 --budget 2000
  uv run python scripts/probe_template_holdout.py --arm toggle --game sk48 --budget 2000

Requires HARNESS_LLM_BASE_URL / HARNESS_LLM_MODEL (see
``admorphiq.harness.registry.openai_compat_llm``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402
import probe_patch_loop as ppl  # noqa: E402  shared driver + serialization + verdict

# Arm -> the core function name inside its card. simdfs/toggle both have an
# executable, sandbox-runnable solver core (source_card). Kept local (not added
# to ppl._CORE_FN) so probe_patch_loop's own --tool choices stay tool-backed.
_ARM_CORE_FN = {"simdfs": "simdfs_core", "toggle": "toggle_core"}

__all__ = [
    "template_driver",
    "build_adaptation_prompt",
    "ask_adaptation",
    "decide_selection",
    "result_json",
]


# ── template baseline: the verbatim card through the sandbox, trace captured ──

def template_driver(card: str, core_fn: str) -> str:
    """The self-contained verbatim card + a driver line that captures the core's
    trace. The card is complete (all helpers + the core), so no prelude is needed;
    we re-prepend a single ``from __future__ import annotations`` (the sandbox
    re-execs without this module's) and print the core's ``_tr`` decisions joined
    by ``||`` — the sandbox's only output channel back to the runner."""
    body = "\n".join(
        ln for ln in card.splitlines()
        if not ln.strip().startswith("from __future__ import")
    )
    return (
        "from __future__ import annotations\n\n" + body
        + f"\n\n_tr = []\n{core_fn}(current_frame, transitions, act, _tr)\n"
        + 'print("||".join(_tr))\n'
    )


def _run_template(
    card: str, core_fn: str, env: Any, budget: int, tag: str = "baseline",
) -> tuple[dict[str, Any], list[Any], list[str]]:
    """Drive the VERBATIM card (through ``run_code``) for ``budget`` actions,
    accumulating per-level transitions (reset on level-up, like the tool's own
    evidence) and the core's printed trace. Returns (metrics, transitions, trace)."""
    from admorphiq.tools.code_agent import run_code

    driver = template_driver(card, core_fn)
    transitions_full: list[Any] = []
    level_transitions: list[dict[str, Any]] = []
    trace_log: list[str] = []

    def refill(obs: Any, frame: np.ndarray) -> list[tuple[int, Any]]:
        trans = [
            (t["action"], t["xy"], t["before"], t["after"]) for t in level_transitions
        ]
        res = run_code(driver, frame, [], ["MOUSE"], transitions=trans)
        if res.error:
            print(f"[live] {tag} card execute error: {res.error}",
                  file=sys.stderr, flush=True)
        if res.printed:
            trace_log.extend(ln for ln in res.printed.split("||") if ln.strip())
        return [ppl._to_step(name, xy) for name, xy in res.actions]

    def on_transition(prev: np.ndarray, step: Any, frame: np.ndarray, changed: bool) -> None:
        aid, xy = step
        name = ppl._NAME.get(aid, "CLICK" if aid == 6 else f"ACTION{aid}")
        level_transitions.append({
            "action": name,
            "xy": [int(xy[0]), int(xy[1])] if xy is not None else None,
            "before": prev, "after": frame,
        })
        transitions_full.append((prev, step, frame))

    def on_level_up() -> None:
        level_transitions.clear()

    _obs, steps, lv = ppl._drive(env, budget, refill, on_transition, on_level_up, tag=tag)
    metrics = ppl._metrics_from_transitions(transitions_full, lv, steps)
    return metrics, transitions_full, trace_log


# ── adaptation ask (ONE LLM call + validate, one error-feedback retry) ───────

def build_adaptation_prompt(
    arm: str, core_fn: str, card: str, trace_tail_text: str, baseline_summary_text: str,
) -> list[dict[str, str]]:
    """The R94 adaptation ask: the arm's conquered card + the core's recent
    decisions + the baseline-run summary + the CROSS-FAMILY instruction. Unlike
    the R93 patch ask ("keep the structure, it stalls"), this says the template
    was built for a DIFFERENT game and priors must be RE-DERIVED from observation."""
    instruction = (
        "This solver was built for a DIFFERENT game of possibly a different "
        "family. Diagnose from the trace and observations how THIS game's "
        f"mechanics differ, then output the FULL ADAPTED version of the core "
        f"function ({core_fn}, same signature) as ONE ```python block. Re-derive "
        "any game-specific priors from YOUR observations."
    )
    user = (
        f"CORE SOURCE ({arm} template):\n{card}\n\n"
        f"RECENT CORE DECISIONS (this run):\n{trace_tail_text}\n\n"
        f"TEMPLATE BASELINE RUN SUMMARY:\n{baseline_summary_text}\n\n{instruction}"
    )
    return [{"role": "user", "content": user}]


def ask_adaptation(
    llm: Callable[[list[dict[str, str]]], str],
    arm: str, core_fn: str, card: str,
    trace_tail_text: str, baseline_summary_text: str,
) -> dict[str, Any]:
    """ONE LLM call + validate, with ONE retry on validation failure (mirrors
    ``probe_patch_loop.ask_patch`` but with the R94 adaptation prompt). Returns
    ``{"code", "failure_stage", "raw_text", "attempts", "error"}`` — reusing the
    shared ``validate_patch`` (exactly one fenced python block, compiles, defines
    ``core_fn``, no disallowed imports)."""
    messages = build_adaptation_prompt(arm, core_fn, card, trace_tail_text,
                                       baseline_summary_text)
    try:
        text = llm(messages)
    except Exception as exc:  # noqa: BLE001 - offline-safe, record and stop
        return {"code": None, "failure_stage": "generation", "raw_text": "",
                "attempts": 1, "error": str(exc)}
    code, err = ppl.validate_patch(text, core_fn)
    if code is not None:
        return {"code": code, "failure_stage": None, "raw_text": text,
                "attempts": 1, "error": None}

    messages.append({"role": "assistant", "content": text})
    messages.append({"role": "user", "content": (
        f"Your adapted core failed validation: {err}. Fix it and output ONE full "
        f"corrected ```python block defining {core_fn} with the same signature."
    )})
    try:
        text2 = llm(messages)
    except Exception as exc:  # noqa: BLE001
        return {"code": None, "failure_stage": "generation", "raw_text": text,
                "attempts": 2, "error": str(exc)}
    code2, err2 = ppl.validate_patch(text2, core_fn)
    if code2 is not None:
        return {"code": code2, "failure_stage": None, "raw_text": text2,
                "attempts": 2, "error": None}
    stage = "parse" if "fenced" in err2 else "validate"
    return {"code": None, "failure_stage": stage, "raw_text": text2,
            "attempts": 2, "error": err2}


# ── selection + result assembly (pure — hermetically testable) ───────────────

def decide_selection(
    template_metrics: dict[str, Any],
    adaptation_replay_metrics: dict[str, Any] | None,
    execute_failed: bool,
) -> str:
    """'adapted' iff the adapted replay validated, executed, and BEATS the verbatim
    template baseline lexicographically (levels > distinct_states >
    distinct_transitions, noop tie-break); 'template' otherwise. Select-on-
    adaptation-replay per the frozen protocol."""
    if adaptation_replay_metrics is None or execute_failed:
        return "template"
    return "adapted" if ppl._patch_beats_parent(
        adaptation_replay_metrics, template_metrics) else "template"


def result_json(
    arm: str, game: str, budget: int,
    template_baseline: dict[str, Any], ask: dict[str, Any],
    adaptation_replay: dict[str, Any] | None, selected: str,
    fresh_score: dict[str, Any], llm_latency_s: float,
) -> dict[str, Any]:
    """The single reported JSON object for one arm (frozen shape)."""
    return {
        "arm": arm, "game": game, "budget": budget,
        "template_baseline": template_baseline,
        "adaptation": {
            "failure_stage": ask["failure_stage"],
            "adapted_code": ask["code"] if ask["code"] is not None else ask["raw_text"],
            "llm_latency_s": round(llm_latency_s, 2),
        },
        "adaptation_replay": adaptation_replay,
        "selected": selected,
        "fresh_score": fresh_score,
    }


# ── main (env-driving; arcade/run_code imported lazily by the callees) ───────

def _baseline_summary_text(metrics: dict[str, Any], transitions_full: list[Any]) -> str:
    return (
        f"levels={metrics['levels']} actions={metrics['actions']} "
        f"noop_rate={metrics['noop_rate']:.2f}\n"
        f"last transitions:\n{ppl._summarize_transitions(transitions_full)}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(_ARM_CORE_FN))
    ap.add_argument("--game", required=True)
    ap.add_argument("--budget", type=int, default=2000)
    ap.add_argument("--out", default=None, help="optional path to also write the JSON result")
    a = ap.parse_args()

    # The driver line references ``transitions``; the sandbox only injects it under
    # this gate (byte-identical default otherwise).
    os.environ.setdefault("HARNESS_KERNEL_API", "1")

    from admorphiq.harness.registry import openai_compat_llm
    from admorphiq.tools.solver_core import format_core_trace, source_card

    core_fn = _ARM_CORE_FN[a.arm]
    card = source_card(a.arm)

    print(f"[live] HOLDOUT arm={a.arm!r} game={a.game!r} core={core_fn!r} "
          f"budget={a.budget}", flush=True)
    arcade, match = ppl._find_game(a.game)

    # 1. TEMPLATE BASELINE RUN ------------------------------------------------
    print("[live] TEMPLATE BASELINE starting", flush=True)
    base_env = arcade.make(match.game_id)
    template_metrics, template_trans, template_trace = _run_template(
        card, core_fn, base_env, a.budget, tag="baseline")
    print(f"[live] TEMPLATE BASELINE done: {template_metrics}", flush=True)

    # 2. ADAPTATION ASK -------------------------------------------------------
    print("[live] ADAPTATION ASK: calling LLM", flush=True)
    trace_tail_text = format_core_trace(template_trace[-30:])
    baseline_summary_text = _baseline_summary_text(template_metrics, template_trans)
    # timeout 900: the D5 v1 simdfs arm's adaptation FAILED at generation at
    # exactly 300.1s — the client's default 300s timeout, not model inability.
    # A 75KB family card legitimately takes longer than a 6.6KB one; the client
    # timeout must not silently decide the family-vs-generic comparison.
    llm = openai_compat_llm(
        num_predict=int(os.environ.get("HARNESS_PATCH_NUM_PREDICT", "8192")),
        timeout=float(os.environ.get("HARNESS_PATCH_TIMEOUT", "900")))
    t0 = time.perf_counter()
    ask = ask_adaptation(llm, a.arm, core_fn, card, trace_tail_text, baseline_summary_text)
    llm_latency_s = time.perf_counter() - t0
    print(f"[live] ADAPTATION ASK done in {llm_latency_s:.1f}s "
          f"(attempts={ask['attempts']} failure_stage={ask['failure_stage']})", flush=True)

    # 3. ADAPTATION REPLAY ----------------------------------------------------
    adaptation_replay: dict[str, Any] | None = None
    execute_failed = False
    if ask["code"] is None:
        print("[live] ADAPTATION INVALID -> template selected", flush=True)
    else:
        print("[live] ADAPTATION REPLAY starting", flush=True)
        replay_env = arcade.make(match.game_id)
        adaptation_replay, execute_failed = ppl._run_patch(
            ask["code"], core_fn, replay_env, a.budget,
            prelude=ppl._card_prelude(a.arm, core_fn))
        if execute_failed:
            adaptation_replay["failure_stage"] = "execute"
        print(f"[live] ADAPTATION REPLAY done: {adaptation_replay}", flush=True)

    # 4. SELECTION (on adaptation replay) -------------------------------------
    selected = decide_selection(template_metrics, adaptation_replay, execute_failed)
    print(f"[live] SELECTED: {selected}", flush=True)

    # 5. FRESH SCORE (selected variant, once, on a fresh env instance) --------
    print(f"[live] FRESH SCORE ({selected}) starting", flush=True)
    fresh_env = arcade.make(match.game_id)
    if selected == "adapted":
        fresh_score, _ = ppl._run_patch(
            ask["code"], core_fn, fresh_env, a.budget,
            prelude=ppl._card_prelude(a.arm, core_fn))
    else:
        fresh_score, _trans, _trace = _run_template(
            card, core_fn, fresh_env, a.budget, tag="fresh")
    print(f"[live] FRESH SCORE done: {fresh_score}", flush=True)

    # 6. ONE JSON -------------------------------------------------------------
    result = result_json(a.arm, a.game, a.budget, template_metrics, ask,
                         adaptation_replay, selected, fresh_score, llm_latency_s)
    text = json.dumps(result, indent=2)
    if a.out:
        Path(a.out).write_text(text)
        print(f"[live] wrote {a.out}", flush=True)
    print(text)


if __name__ == "__main__":
    main()
