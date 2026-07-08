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

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from admorphiq.ewm.core import (
    _run_with_timeout,
    _safe_builtins,
    extract_code,
)


@dataclass
class CodeResult:
    """Outcome of executing one model-written code block."""

    actions: list[tuple[str, tuple[int, int] | None]] = field(default_factory=list)
    printed: str = ""
    error: str = ""


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
        return CodeResult(actions=queue[:8], printed="\n".join(out)[:2000], error=str(exc)[:200])
    return CodeResult(actions=queue[:8], printed="\n".join(out)[:2000])


_SYSTEM = (
    "You control an ARC-AGI-3 grid game by WRITING PYTHON. The sandbox has: "
    "current_frame (list[list[int]] 64x64 colours 0-15), history (recent "
    "{action,changed}), valid_actions, numpy as np, and act(name, x=None, y=None) "
    "to QUEUE actions — name in UP/DOWN/LEFT/RIGHT/SPACE/ACTION7, or CLICK with x,y. "
    "Inspect the frame, reason about the mechanic, and queue 1-4 actions you expect "
    "to make progress. Output ONLY one ```python block that calls act(...)."
)


def build_code_prompt(
    frame: np.ndarray, history: list[dict[str, Any]], valid_actions: list[str],
) -> list[dict[str, str]]:
    """Chat messages asking the model to write an action-queuing code block."""
    from admorphiq.ewm.core import serialize_grid
    recent = "; ".join(
        f"{h.get('action')}{'*' if h.get('changed') else ''}" for h in history[-10:]
    ) or "none"
    user = (
        f"FRAME (hex, 64 rows):\n{serialize_grid(frame)}\n\n"
        f"valid_actions = {valid_actions}\nrecent = {recent}\n\n"
        "Write the ```python block."
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
