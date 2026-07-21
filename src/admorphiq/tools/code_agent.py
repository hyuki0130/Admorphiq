"""LLM REPL code-agent core — the frontier lever (Tufa/astroseger-class, original).

Measured decisively (2026-07-08, tool_selector.md): orchestrating PRE-BUILT
tools plateaus at ~the 18/25 baseline; the frontier transform games need the
LLM to WRITE bespoke solving code per game. This module is that core: the game
state is exposed to the model as Python variables in a sandbox, the model writes
Python that inspects the state and QUEUES actions, we execute it safely and
return the queued actions. Game-agnostic (no game ids); reuses the ewm.core
sandbox (import whitelist + timeout).

This is the perception/execution CORE of the code-agent; the full turn loop
(reason -> write code -> execute -> observe -> evict context) wraps it and is
built + measured separately.
"""

from __future__ import annotations

import os
import types
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from admorphiq.ewm.core import (
    _run_with_timeout,
    _safe_builtins,
    extract_code,
)


def _kernel_api_enabled() -> bool:
    """agent25 kernel bridge gate. Default OFF keeps the deployed prompt/behaviour
    byte-identical until the bridge is measured on a GPU host."""
    return os.environ.get("HARNESS_KERNEL_API", "").lower() in ("1", "true", "yes", "on")


def _kernel_namespace() -> types.SimpleNamespace:
    """The ``K`` object of curated r59 kernels for the code sandbox."""
    from admorphiq.tools.kernel_api import KERNEL_API

    return types.SimpleNamespace(**KERNEL_API)


def _system_content() -> str:
    """System prompt; appends the kernel toolbox card when the bridge is on."""
    if _kernel_api_enabled():
        from admorphiq.tools.kernel_api import KERNEL_CARDS

        return _SYSTEM + "\n\n" + KERNEL_CARDS
    return _SYSTEM


@dataclass
class CodeResult:
    """Outcome of executing one model-written code block."""

    actions: list[tuple[str, tuple[int, int] | None]] = field(default_factory=list)
    printed: str = ""
    error: str = ""
    code: str = ""  # the executed block (fed back verbatim on a refine ask)


_ALLOWED_ACTIONS = {"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5, "RESET": 0, "ACTION7": 7}
# ACTION6 = click, taken via click(x, y). UP..SPACE map to ACTION1..5 by convention here.


def run_code(
    code_text: str,
    frame: np.ndarray,
    history: list[dict[str, Any]],
    valid_actions: list[str],
    timeout: float = 5.0,
) -> CodeResult:
    """Execute a model-written code block against the game state, return actions.

    The sandbox exposes read-only ``current_frame`` (a list-of-lists grid),
    ``history`` (recent {action, changed} dicts), ``valid_actions``, numpy as
    ``np``, and an ``act(name, x=None, y=None)`` helper the code calls to QUEUE
    actions (``name`` in UP/DOWN/LEFT/RIGHT/SPACE/ACTION7 or 'MOUSE'/'CLICK' with
    x,y). No file/network/clock. Errors and prints are captured; a broken block
    yields an empty action queue (the caller falls back), never a crash.
    """
    queue: list[tuple[str, tuple[int, int] | None]] = []
    out: list[str] = []

    def act(name: str, x: int | None = None, y: int | None = None) -> None:
        n = str(name).upper()
        if n in ("MOUSE", "CLICK", "ACTION6") and x is not None and y is not None:
            if 0 <= int(x) < 64 and 0 <= int(y) < 64:
                queue.append(("ACTION6", (int(x), int(y))))
        elif n in _ALLOWED_ACTIONS:
            queue.append((f"ACTION{_ALLOWED_ACTIONS[n]}" if _ALLOWED_ACTIONS[n] else "RESET", None))

    def _print(*a: Any, **k: Any) -> None:
        out.append(" ".join(str(x) for x in a))

    # Restricted builtins go under the __builtins__ KEY (else Python injects the
    # REAL builtins and `import os` escapes the whitelist — ewm.core pattern).
    safe = _safe_builtins()
    safe["print"] = _print
    ns: dict[str, Any] = {
        "__builtins__": safe,
        "np": np,
        "current_frame": np.asarray(frame).tolist(),
        "history": list(history),
        "valid_actions": list(valid_actions),
        "act": act,
        # r59 kernel vocabulary (agent25 bridge). Inert unless the prompt tells
        # the model it exists (gated by HARNESS_KERNEL_API in the prompt builder),
        # so injecting it here leaves default behaviour byte-identical.
        "K": _kernel_namespace(),
    }
    code = extract_code(code_text)
    try:
        compiled = compile(code, "<code_agent>", "exec")
    except SyntaxError as exc:
        return CodeResult(error=f"syntax: {exc}")

    def _exec() -> None:
        exec(compiled, ns)  # noqa: S102 - sandboxed namespace, whitelisted builtins

    try:
        _run_with_timeout(_exec, (), timeout)
    except Exception as exc:  # noqa: BLE001 - degrade to empty queue, never crash
        return CodeResult(actions=queue[:8], printed="\n".join(out)[:2000],
                          error=str(exc)[:200], code=code)
    return CodeResult(actions=queue[:8], printed="\n".join(out)[:2000], code=code)


_SYSTEM = (
    "You solve an ARC-AGI-3 grid game by WRITING PYTHON. The level clears when the "
    "board reaches a specific TARGET configuration — your job is to infer that "
    "target from what you see and drive toward it. The sandbox has: current_frame "
    "(list[list[int]] 64x64 colours 0-15), history (recent {action,changed}), "
    "valid_actions, numpy as np, and act(name, x=None, y=None) to QUEUE actions — "
    "name in UP/DOWN/LEFT/RIGHT/SPACE/ACTION7, or CLICK with x,y (x=col, y=row). "
    "Reason step by step in comments: (1) what are the objects/regions and which "
    "past actions changed what (from history + the summary); (2) what is the most "
    "likely GOAL (e.g. recolor a region to match another, fill a shape, sort/order, "
    "move a piece onto a target); (3) which 1-6 actions move toward it. Then queue "
    "them. Output ONLY one ```python block that calls act(...)."
)


def build_code_prompt(
    frame: np.ndarray, history: list[dict[str, Any]], valid_actions: list[str],
    dynamics: str | None = None,
) -> list[dict[str, str]]:
    """Chat messages asking the model to infer the goal and write an action block.

    Beyond the raw grid, a compact STRUCTURED summary (colour counts, foreground
    object sizes) is included so the model can reason about the target without
    decoding 64 hex rows cell by cell — the raw grid alone gave gemma4 nothing to
    anchor goal reasoning on (measured re86 0/8).

    ``dynamics`` is the agent's OWN observed action->effect statistics (tries,
    change rate, median cells changed per action) — the graph-informed context:
    code written blind to dynamics was measured 0; what each action actually
    DOES is the evidence a solver body needs."""
    from admorphiq.ewm.core import serialize_grid
    recent = "; ".join(
        f"{h.get('action')}{'*' if h.get('changed') else ''}" for h in history[-10:]
    ) or "none"
    summary = _frame_summary(np.asarray(frame))
    user = (
        f"FRAME (hex, 64 rows):\n{serialize_grid(frame)}\n\n"
        f"SUMMARY: {summary}\n"
        + (f"OBSERVED DYNAMICS (this agent's own probes):\n{dynamics}\n" if dynamics else "")
        + f"valid_actions = {valid_actions}\nrecent = {recent}\n\n"
        "Infer the goal, then write the ```python block."
    )
    return [{"role": "system", "content": _system_content()}, {"role": "user", "content": user}]


def build_refine_prompt(
    frame: np.ndarray, prev_code: str, effect: str, valid_actions: list[str],
    dynamics: str | None = None,
) -> list[dict[str, str]]:
    """Execution-FEEDBACK revision ask (the EWM refinement pattern applied to
    solver code): show the model its previous block plus the OBSERVED effect of
    running it, and ask for a revised block. One-shot synthesis measured 0 on
    every wall game even with dynamics context — feedback is the next rung."""
    from admorphiq.ewm.core import serialize_grid
    summary = _frame_summary(np.asarray(frame))
    user = (
        "Your PREVIOUS solver block was executed. Observed effect:\n"
        f"{effect}\n\nPrevious block:\n```python\n{prev_code}\n```\n\n"
        f"CURRENT FRAME (hex, 64 rows):\n{serialize_grid(frame)}\n\n"
        f"SUMMARY: {summary}\n"
        + (f"OBSERVED DYNAMICS (this agent's own probes):\n{dynamics}\n" if dynamics else "")
        + f"valid_actions = {valid_actions}\n\n"
        "Diagnose why the previous block did not clear the level, then write a "
        "REVISED ```python block."
    )
    return [{"role": "system", "content": _system_content()}, {"role": "user", "content": user}]


def _frame_summary(frame: np.ndarray) -> str:
    """A compact structured description: colour counts + foreground object sizes."""
    from admorphiq.tools.base import color_histogram, connected_components
    hist = color_histogram(frame)
    colors = ", ".join(f"c{c}:{int(n)}" for c, n in enumerate(hist) if n)
    comps = connected_components(frame)
    comps.sort(key=lambda c: -c["size"])
    objs = "; ".join(
        f"c{o['color']}@({int(o['centroid'][1])},{int(o['centroid'][0])})sz{o['size']}"
        for o in comps[:8]
    ) or "none"
    return f"colours[{colors}] top_objects[{objs}]"
