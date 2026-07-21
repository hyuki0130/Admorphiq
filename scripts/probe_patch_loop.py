"""R93-min falsification probe: can an LLM PATCH our executable solver core to
beat the ORIGINAL on a game where the original predictably stalls?

The card the LLM sees (``solver_core.source_card``) IS the code the tool
executes (R93). This probe closes the loop: drive the original tool for a
budget (PARENT), ask the LLM to diagnose the stall and rewrite the core
(PATCH ASK), then drive the SAME budget with the patched core through the
sandbox (PATCH RUN, matched replay), and compare.

Usage (on the Kaggle-matched VM, offline Arcade):
  uv run python scripts/probe_patch_loop.py --tool toggle --game vc33 --budget 2000
  uv run python scripts/probe_patch_loop.py --tool paint --game cd82 --budget 2000

Requires HARNESS_LLM_BASE_URL / HARNESS_LLM_MODEL (vLLM OpenAI-compat server;
see ``admorphiq.harness.registry.openai_compat_llm``).

The verdict compares PARENT (original tool via observe/propose) against PATCH
(the LLM-rewritten core, executed through the SAME sandbox — ``run_code`` —
that Kaggle-time code would run in) on the SAME action budget, lexicographically:
levels, then distinct states reached, then distinct (state, action) transitions
observed, then (lower) no-op rate as the final tie-break.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402

from admorphiq.ewm.core import _ALLOWED_IMPORTS  # noqa: E402
from admorphiq.tools.base import (  # noqa: E402
    availability,
    base_hash,
    frame_2d,
    has_frame,
    levels_completed,
    state_name,
)

__all__ = [
    "validate_patch",
    "build_patch_prompt",
    "ask_patch",
    "run_patched_step",
]

# The two tools that have an executable solver core (solver_core.source_card).
_CORE_FN = {"toggle": "toggle_core", "paint": "paint_core"}

# Reverse of code_agent.act()'s _ALLOWED_ACTIONS mapping — used to turn a
# CodeResult action name back into an internal Step (action_id, xy|None).
_REV_ACTION = {"ACTION1": 1, "ACTION2": 2, "ACTION3": 3, "ACTION4": 4,
               "ACTION5": 5, "ACTION7": 7, "RESET": 0}
# Human-readable name for a simple action id (for transition summaries only —
# purely descriptive; the cores key off ``xy``, never the name string).
_NAME = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 7: "ACTION7"}

_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.S)


def _make_tool(name: str) -> Any:
    ctors = {
        "toggle": ("admorphiq.tools.toggle", "ToggleTool"),
        "paint": ("admorphiq.tools.paint_flood", "PaintFloodTool"),
    }
    if name not in ctors:
        raise SystemExit(f"unknown tool {name!r}; have {sorted(ctors)}")
    import importlib
    mod_name, cls_name = ctors[name]
    return getattr(importlib.import_module(mod_name), cls_name)()


# ── steps 2+3: patch ask (LLM call) + validate (hermetic, no env needed) ────

def validate_patch(text: str, core_fn: str) -> tuple[str | None, str | None]:
    """Validate an LLM patch response: exactly one fenced python block, compiles
    (``ast.parse``), defines ``core_fn`` at module level, and imports nothing
    beyond the sandbox-allowed set (``ewm.core._ALLOWED_IMPORTS``).

    Returns ``(code, None)`` on success or ``(None, error_message)`` on failure.
    """
    blocks = _FENCE_RE.findall(text)
    if len(blocks) != 1:
        return None, f"expected exactly one fenced python block, found {len(blocks)}"
    code = blocks[0].strip()
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return None, f"syntax error: {exc}"
    has_fn = any(
        isinstance(n, ast.FunctionDef) and n.name == core_fn for n in ast.walk(tree)
    )
    if not has_fn:
        return None, f"patched code does not define {core_fn}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in _ALLOWED_IMPORTS:
                    return None, f"disallowed import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in _ALLOWED_IMPORTS:
                return None, f"disallowed import: {node.module}"
    return code, None


def build_patch_prompt(
    tool_name: str, core_fn: str, card: str, trace_tail_text: str,
    parent_summary_text: str,
) -> list[dict[str, str]]:
    """One-shot patch-ask prompt: the real source card + the core's recent
    decisions + a compact parent-run summary + the patch instruction."""
    instruction = (
        f"Diagnose why this solver stalls on THIS game, then output the FULL "
        f"PATCHED version of the core function ({core_fn}, same signature) as "
        "ONE ```python block. Keep the structure; change what your diagnosis "
        "requires."
    )
    user = (
        f"CORE SOURCE ({tool_name} tool):\n{card}\n\n"
        f"RECENT CORE DECISIONS (this run):\n{trace_tail_text}\n\n"
        f"PARENT RUN SUMMARY:\n{parent_summary_text}\n\n{instruction}"
    )
    return [{"role": "user", "content": user}]


def ask_patch(
    llm: Callable[[list[dict[str, str]]], str],
    tool_name: str, core_fn: str, card: str,
    trace_tail_text: str, parent_summary_text: str,
) -> dict[str, Any]:
    """Steps 2+3: one LLM call + validate, with ONE retry on validation failure.

    Returns ``{"code", "failure_stage", "raw_text", "attempts", "error"}``.
    ``failure_stage`` is one of ``"generation"``/``"parse"``/``"validate"``/None.
    """
    messages = build_patch_prompt(tool_name, core_fn, card, trace_tail_text,
                                   parent_summary_text)
    try:
        text = llm(messages)
    except Exception as exc:  # noqa: BLE001 - offline-safe, record and stop
        return {"code": None, "failure_stage": "generation", "raw_text": "",
                "attempts": 1, "error": str(exc)}
    code, err = validate_patch(text, core_fn)
    if code is not None:
        return {"code": code, "failure_stage": None, "raw_text": text,
                "attempts": 1, "error": None}

    messages.append({"role": "assistant", "content": text})
    messages.append({"role": "user", "content": (
        f"Your patch failed validation: {err}. Fix it and output ONE full "
        f"corrected ```python block defining {core_fn} with the same signature."
    )})
    try:
        text2 = llm(messages)
    except Exception as exc:  # noqa: BLE001
        return {"code": None, "failure_stage": "generation", "raw_text": text,
                "attempts": 2, "error": str(exc)}
    code2, err2 = validate_patch(text2, core_fn)
    if code2 is not None:
        return {"code": code2, "failure_stage": None, "raw_text": text2,
                "attempts": 2, "error": None}
    stage = "parse" if "fenced" in err2 else "validate"
    return {"code": None, "failure_stage": stage, "raw_text": text2,
            "attempts": 2, "error": err2}


# ── step 4 primitive: the driver call through the real sandbox ─────────────

def run_patched_step(
    patched_code: str, core_fn: str, frame: np.ndarray,
    level_transitions: list[dict[str, Any]],
) -> Any:
    """Run ``{patched_code}\\n\\n{core_fn}(current_frame, transitions, act)`` in
    the ``code_agent`` sandbox, with the accumulated per-level transitions (with
    xy) serialized in. Requires ``HARNESS_KERNEL_API=1`` (transitions/K are
    otherwise absent from the sandbox namespace). Returns the ``CodeResult``."""
    from admorphiq.tools.code_agent import run_code

    driver = patched_code + f"\n\n{core_fn}(current_frame, transitions, act)\n"
    trans = [
        (t["action"], t["xy"], t["before"], t["after"]) for t in level_transitions
    ]
    return run_code(driver, frame, [], ["MOUSE"], transitions=trans)


def _to_step(name: str, xy: tuple[int, int] | None) -> tuple[int, tuple[int, int] | None]:
    if name == "ACTION6" and xy is not None:
        return (6, (int(xy[0]), int(xy[1])))
    return (_REV_ACTION.get(name, 0), None)


# ── metrics + prompt-summary helpers ────────────────────────────────────────

def _metrics_from_transitions(
    transitions_full: list[tuple[np.ndarray, tuple[int, Any], np.ndarray]],
    levels: int, actions: int,
) -> dict[str, Any]:
    """(levels, actions, distinct_states, distinct_transitions, noop_rate) from
    a run's recorded (prev_frame, Step, next_frame) transitions."""
    seen_states: set[str] = set()
    seen_transitions: set[tuple[str, int, Any]] = set()
    noop = 0
    for prev, step, nxt in transitions_full:
        seen_states.add(base_hash(prev))
        seen_states.add(base_hash(nxt))
        aid, xy = step
        seen_transitions.add((base_hash(prev), aid, tuple(xy) if xy is not None else None))
        if not bool((prev != nxt).any()):
            noop += 1
    total = len(transitions_full)
    return {
        "levels": int(levels),
        "actions": int(actions),
        "distinct_states": len(seen_states),
        "distinct_transitions": len(seen_transitions),
        "noop_rate": (noop / total) if total else 0.0,
    }


def _summarize_transitions(
    transitions_full: list[tuple[np.ndarray, tuple[int, Any], np.ndarray]],
    last_n: int = 15,
) -> str:
    lines = []
    for prev, step, nxt in transitions_full[-last_n:]:
        aid, xy = step
        changed = int((prev != nxt).sum())
        if xy is not None:
            lines.append(f"CLICK({xy[0]},{xy[1]}) changed={changed}")
        else:
            lines.append(f"{_NAME.get(aid, f'ACTION{aid}')} changed={changed}")
    return "\n".join(lines) if lines else "(no transitions observed)"


def _patch_beats_parent(patch: dict[str, Any], parent: dict[str, Any]) -> bool:
    """Lexicographic verdict: levels, then distinct states, then distinct
    transitions, then (lower) no-op rate as the final tie-break."""
    if patch["levels"] != parent["levels"]:
        return patch["levels"] > parent["levels"]
    if patch["distinct_states"] != parent["distinct_states"]:
        return patch["distinct_states"] > parent["distinct_states"]
    if patch["distinct_transitions"] != parent["distinct_transitions"]:
        return patch["distinct_transitions"] > parent["distinct_transitions"]
    return patch["noop_rate"] < parent["noop_rate"]


# ── env driving (live Arcade only; imported lazily so the rest of this module
#    stays importable/testable without arcengine) ───────────────────────────

def _drive(
    env: Any, budget: int,
    refill: Callable[[Any, np.ndarray], list[tuple[int, Any]]],
    on_transition: Callable[[np.ndarray, tuple[int, Any], np.ndarray], None],
    on_level_up: Callable[[], None] | None = None,
    tag: str = "run",
) -> tuple[Any, int, int]:
    """Generic revive-on-GAME_OVER driver loop (modelled on
    ``probe_tool_direct.py``). ``refill`` is called only when the action queue
    is empty; ``on_transition`` once per observed (prev, step, next). Prints a
    [live] progress line every 50 actions. Returns (final_obs, steps, levels)."""
    from arcengine import GameAction as EngineGameAction

    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.types import ActionType, GameAction

    convert = AdmorphiqAdapter._convert_action
    queue: list[tuple[int, Any]] = []
    prev_frame: np.ndarray | None = None
    prev_step: tuple[int, Any] | None = None
    steps = 0
    last_levels = 0
    obs = env.observation_space

    while steps < budget:
        if state_name(obs) == "WIN":
            break
        if state_name(obs) in ("GAME_OVER", "NOT_PLAYED") or not has_frame(obs):
            obs = env.step(EngineGameAction.RESET)
            prev_frame = None
            queue.clear()
            steps += 1
            continue

        frame = frame_2d(obs).astype(np.int16)
        lv = levels_completed(obs)
        if lv > last_levels:
            last_levels = lv
            queue.clear()
            prev_frame = None
            if on_level_up is not None:
                on_level_up()

        if prev_frame is not None and prev_step is not None \
                and prev_frame.shape == frame.shape:
            changed = bool((prev_frame != frame).any())
            on_transition(prev_frame, prev_step, frame, changed)

        if not queue:
            simple_ids, action6 = availability(obs)
            try:
                proposed = refill(obs, frame)
            except Exception as exc:  # noqa: BLE001 - a broken refill never crashes the probe
                print(f"[live] {tag} refill error: {exc}", file=sys.stderr, flush=True)
                proposed = []
            legal = []
            for aid, xy in proposed:
                if xy is not None and action6 and aid == 6:
                    legal.append((aid, xy))
                elif xy is None and (aid in simple_ids or (aid == 7 and not simple_ids)):
                    legal.append((aid, xy))
            if not legal:
                legal = [(simple_ids[0], None)] if simple_ids else [(6, (32, 32))]
            queue = legal

        aid, xy = queue.pop(0)
        step = (aid, xy)
        internal = GameAction.coordinate(int(xy[0]), int(xy[1])) if xy is not None \
            else GameAction.simple(ActionType(aid))
        action = convert(internal)
        obs = env.step(action) if not action.is_complex() \
            else env.step(action, data=action.action_data.model_dump())
        if obs is None:
            break
        steps += 1
        prev_frame = frame
        prev_step = step
        if steps % 50 == 0:
            print(f"[live] {tag} step={steps}/{budget} level={last_levels}", flush=True)

    lv = levels_completed(obs) if obs is not None else last_levels
    return obs, steps, lv


def _run_parent(
    tool: Any, env: Any, budget: int,
) -> tuple[dict[str, Any], list[tuple[np.ndarray, Any, np.ndarray]], list[str]]:
    """Drive the ORIGINAL tool via observe/propose for ``budget`` actions."""
    transitions_full: list[tuple[np.ndarray, Any, np.ndarray]] = []
    core_trace_log: list[str] = []

    def on_transition(prev: np.ndarray, step: Any, frame: np.ndarray, changed: bool) -> None:
        try:
            tool.observe(prev, step, changed)
        except Exception as exc:  # noqa: BLE001
            print(f"[live] parent observe error: {exc}", file=sys.stderr, flush=True)
        transitions_full.append((prev, step, frame))

    def on_level_up() -> None:
        tool.reset()

    def refill(obs: Any, frame: np.ndarray) -> list[tuple[int, Any]]:
        steps_out = tool.propose([obs], obs)
        core_trace_log.extend(getattr(tool, "_trace", []) or [])
        return steps_out

    obs, steps, lv = _drive(env, budget, refill, on_transition, on_level_up, tag="parent")
    metrics = _metrics_from_transitions(transitions_full, lv, steps)
    return metrics, transitions_full, core_trace_log


def _run_patch(
    patched_code: str, core_fn: str, env: Any, budget: int,
) -> tuple[dict[str, Any], bool]:
    """Drive the PATCHED core (through ``run_code``) for the SAME budget,
    with the per-level transitions accumulated (reset on level-up, like the
    original tool's own evidence). Returns (metrics, execute_failed)."""
    transitions_full: list[tuple[np.ndarray, Any, np.ndarray]] = []
    level_transitions: list[dict[str, Any]] = []
    stats = {"invocations": 0, "errors": 0, "any_action": False}

    def refill(obs: Any, frame: np.ndarray) -> list[tuple[int, Any]]:
        stats["invocations"] += 1
        res = run_patched_step(patched_code, core_fn, frame, level_transitions)
        if res.error:
            stats["errors"] += 1
        actions = [_to_step(name, xy) for name, xy in res.actions]
        if actions:
            stats["any_action"] = True
        return actions

    def on_transition(prev: np.ndarray, step: Any, frame: np.ndarray, changed: bool) -> None:
        aid, xy = step
        name = _NAME.get(aid, "CLICK" if aid == 6 else f"ACTION{aid}")
        level_transitions.append({
            "action": name,
            "xy": [int(xy[0]), int(xy[1])] if xy is not None else None,
            "before": prev, "after": frame,
        })
        transitions_full.append((prev, step, frame))

    def on_level_up() -> None:
        level_transitions.clear()

    obs, steps, lv = _drive(env, budget, refill, on_transition, on_level_up, tag="patch")
    metrics = _metrics_from_transitions(transitions_full, lv, steps)
    execute_failed = (
        stats["invocations"] > 0 and stats["errors"] == stats["invocations"]
        and not stats["any_action"]
    )
    return metrics, execute_failed


def _find_game(game_query: str) -> tuple[Any, Any]:
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    want = game_query.strip().lower()
    match = next(
        (e for e in arcade.get_environments()
         if want in f"{e.game_id} {e.title or ''}".lower()),
        None,
    )
    if match is None:
        raise SystemExit(f"no game matching {game_query!r}")
    return arcade, match


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", required=True, choices=sorted(_CORE_FN))
    ap.add_argument("--game", required=True)
    ap.add_argument("--budget", type=int, default=2000)
    ap.add_argument("--out", default=None, help="optional path to also write the JSON result")
    a = ap.parse_args()

    # The patched core's driver line references `transitions`/`K`, which the
    # sandbox only exposes under this gate (byte-identical default otherwise).
    os.environ.setdefault("HARNESS_KERNEL_API", "1")

    from admorphiq.harness.registry import openai_compat_llm
    from admorphiq.tools.solver_core import format_core_trace, source_card

    core_fn = _CORE_FN[a.tool]
    card = source_card(a.tool)

    print(f"[live] game={a.game!r} tool={a.tool!r} budget={a.budget}", flush=True)
    arcade, match = _find_game(a.game)

    print("[live] PARENT RUN starting", flush=True)
    tool = _make_tool(a.tool)
    parent_env = arcade.make(match.game_id)
    parent_metrics, transitions_full, core_trace_log = _run_parent(tool, parent_env, a.budget)
    print(f"[live] PARENT RUN done: {parent_metrics}", flush=True)

    trace_tail_text = format_core_trace(core_trace_log[-30:])
    parent_summary_text = (
        f"levels={parent_metrics['levels']} actions={parent_metrics['actions']} "
        f"noop_rate={parent_metrics['noop_rate']:.2f}\n"
        f"last transitions:\n{_summarize_transitions(transitions_full)}"
    )

    print("[live] PATCH ASK: calling LLM", flush=True)
    llm = openai_compat_llm()
    t0 = time.perf_counter()
    ask = ask_patch(llm, a.tool, core_fn, card, trace_tail_text, parent_summary_text)
    llm_latency_s = time.perf_counter() - t0
    print(f"[live] PATCH ASK done in {llm_latency_s:.1f}s "
          f"(attempts={ask['attempts']} failure_stage={ask['failure_stage']})", flush=True)

    if ask["code"] is None:
        patch_out = {
            "levels": 0, "actions": 0, "distinct_states": 0, "distinct_transitions": 0,
            "noop_rate": 0.0, "failure_stage": ask["failure_stage"],
            "patched_code": ask["raw_text"],
        }
        verdict = "PATCH_INVALID"
    else:
        print("[live] PATCH RUN starting", flush=True)
        patch_env = arcade.make(match.game_id)
        patch_metrics, execute_failed = _run_patch(ask["code"], core_fn, patch_env, a.budget)
        print(f"[live] PATCH RUN done: {patch_metrics}", flush=True)
        failure_stage = "execute" if execute_failed else None
        patch_out = dict(patch_metrics)
        patch_out["failure_stage"] = failure_stage
        patch_out["patched_code"] = ask["code"]
        verdict = "PATCH_INVALID" if failure_stage else (
            "PATCH_WINS" if _patch_beats_parent(patch_metrics, parent_metrics) else "PARENT_HOLDS"
        )

    result = {
        "tool": a.tool, "game": a.game, "budget": a.budget,
        "parent": parent_metrics, "patch": patch_out,
        "verdict": verdict, "llm_latency_s": llm_latency_s,
    }
    print(f"[live] VERDICT: {verdict}", flush=True)
    text = json.dumps(result, indent=2)
    if a.out:
        Path(a.out).write_text(text)
        print(f"[live] wrote {a.out}", flush=True)
    print(text)


if __name__ == "__main__":
    main()
