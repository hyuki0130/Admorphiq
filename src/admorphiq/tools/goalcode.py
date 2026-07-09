"""Executable goal scorer — the LLM WRITES ``goal_score(frame) -> float``.

The most expressive goal representation on the measured frontier ladder
(GoalSpec enum → static target frame → THIS): an arbitrary Python function can
state conditions neither can ("all colour-3 blobs merged into one", "the row of
tokens sorted by size"), and a SCORER is a far easier authoring task for a
local model than a policy (the code-agent, which had to pick actions, measured
0 — a scorer only has to describe what "solved" looks like).

The LLM sees the current board summary + observed action effects and writes one
```python block defining ``goal_score(frame)`` (numpy available as ``np``,
``frame`` is a 64x64 list-of-lists of colour ints; HIGHER = closer to solved).
The block is compiled in the same restricted sandbox the code-agent uses
(whitelisted builtins under the ``__builtins__`` key, wall-clock timeout) and
validated on the live frame (must return a finite number, fast) before it is
injected via :meth:`GraphSearchTool.set_external_scorer`.

One implementation shared by the probe and (later) the deployed harness.
"""

from __future__ import annotations

import re
from typing import Any, Callable

import numpy as np

from admorphiq.ewm.core import _run_with_timeout, _safe_builtins, extract_code
from admorphiq.tools.base import color_histogram, connected_components

__all__ = ["build_scorer_prompt", "compile_scorer"]

# Per-call wall-clock budget for one goal_score(frame) evaluation. The frontier
# ranker calls it once per stored state (memoized), so it must be quick.
_EVAL_TIMEOUT_S = 1.0
_COMPILE_TIMEOUT_S = 3.0


def build_scorer_prompt(frame: np.ndarray, effects: list[dict[str, Any]]) -> str:
    """Prompt the model to WRITE the goal scorer from what it can observe."""
    hist = color_histogram(np.asarray(frame))
    colors = ", ".join(f"colour {c}: {int(n)} cells" for c, n in enumerate(hist) if n)
    comps = connected_components(np.asarray(frame))
    comps.sort(key=lambda c: -c["size"])
    objs = "; ".join(
        f"colour {o['color']} blob at ({int(o['centroid'][1])},{int(o['centroid'][0])}) size {o['size']}"
        for o in comps[:8]
    ) or "none"
    fx = "; ".join(
        f"action {p.get('action')}: {p.get('changed_cells', 0)} cells changed"
        for p in effects[-10:]
    ) or "none observed yet"
    return (
        "An ARC-AGI-3 grid puzzle (64x64, colours 0-15, 0=background). The level "
        "completes when the board reaches some TARGET condition you must infer.\n"
        f"Board colour counts: {colors}\n"
        f"Largest objects: {objs}\n"
        f"Observed action effects: {fx}\n\n"
        "Infer the most likely completion condition, then WRITE a Python function\n"
        "    def goal_score(frame):\n"
        "that returns a NUMBER that is HIGHER the closer the board is to solved "
        "(e.g. count of a target colour, negative count of leftover blobs, "
        "-distance between two objects). ``frame`` is a 64x64 list of lists of "
        "ints; numpy is available as ``np``. Keep it under 15 lines, no imports, "
        "no I/O. Output ONLY one ```python block containing the function."
    )


def compile_scorer(
    txt: str, frame: np.ndarray
) -> tuple[Callable[[np.ndarray], float] | None, str]:
    """Compile + validate a model-written scorer; ``(fn, "ok")`` or ``(None, why)``.

    Validation gates (all must pass before injection): the block compiles in the
    restricted sandbox, defines ``goal_score``, and returns a finite number on
    the LIVE frame within the eval timeout. A rejected scorer costs nothing —
    the caller keeps the frame-only goal base.
    """
    code = extract_code(txt)
    if "def goal_score" not in code:
        return None, "no goal_score function in the reply"
    # Models reflexively add `import numpy as np` despite the prompt; np is
    # already provided in the namespace, so strip ONLY numpy imports (measured:
    # every draw was rejected on this line). All other imports stay blocked by
    # the sandbox (os/sys/... must never load).
    code = "\n".join(
        ln for ln in code.splitlines()
        if not re.match(r"\s*(import numpy\b|from numpy\b)", ln)
    )
    ns: dict[str, Any] = {"__builtins__": _safe_builtins(), "np": np}
    try:
        compiled = compile(code, "<goal_score>", "exec")
        _run_with_timeout(lambda: exec(compiled, ns), (), _COMPILE_TIMEOUT_S)  # noqa: S102
    except Exception as exc:  # noqa: BLE001
        return None, f"compile/exec failed: {exc}"
    fn = ns.get("goal_score")
    if not callable(fn):
        return None, "goal_score is not callable"

    grid = np.asarray(frame).tolist()

    def scorer(f: np.ndarray) -> float:
        return float(fn(np.asarray(f).tolist()))

    try:
        probe_val = _run_with_timeout(lambda: float(fn(grid)), (), _EVAL_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001
        return None, f"eval on live frame failed: {exc}"
    if not np.isfinite(probe_val):
        return None, f"non-finite score {probe_val!r}"
    return scorer, "ok"
