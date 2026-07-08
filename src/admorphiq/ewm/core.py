"""Executable-world-model core: serialization, prompts, sandbox, scoring, LLM client.

Extracted from ``scripts/llm_worldmodel_bench.py`` (R52 / US-1) so the RUNTIME
agent and the dev-time bench share one implementation. Everything here is
game-agnostic: no game ids, no titles, frame observations only.

The refinement/selection loop lives in :mod:`admorphiq.ewm.synthesizer`; the
bench keeps only dev-time concerns (dataset split, summary tables, CLI).
"""

from __future__ import annotations

import json
import re
import signal
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

# Combined-logit action convention shared with collect_transitions.py.
NUM_SIMPLE_ACTIONS = 5
COORD_OFFSET = NUM_SIMPLE_ACTIONS
GRID = 64

# A model-call type: (messages, model, max_tokens) -> (text, meta-dict).
ChatFn = Callable[[list[dict[str, str]], str, int], tuple[str, dict[str, Any]]]


# ─────────────────────────────────────────────────────────────────────────────
# Action decoding
# ─────────────────────────────────────────────────────────────────────────────
def action_call_args(idx: int) -> tuple[str, tuple[int, int] | None]:
    """Decode a combined-logit index into the ``(action, xy)`` call arguments.

    ``action`` is the string the generated ``predict_next_frame`` receives
    (``"ACTION1".."ACTION5"`` simple, ``"ACTION6"`` for a click); ``xy`` is the
    ``(x, y)`` grid coordinate for a click, else ``None``.
    """
    if idx < NUM_SIMPLE_ACTIONS:
        return f"ACTION{idx + 1}", None
    coord = idx - COORD_OFFSET
    y, x = divmod(coord, GRID)
    return "ACTION6", (int(x), int(y))


def action_label(idx: int) -> str:
    """Human/prompt label: ``"ACTION3"`` or ``"ACTION6(x,y)"`` for a click."""
    action, xy = action_call_args(idx)
    return action if xy is None else f"{action}({xy[0]},{xy[1]})"


# ─────────────────────────────────────────────────────────────────────────────
# Grid + diff serialization (round-trippable)
# ─────────────────────────────────────────────────────────────────────────────
def serialize_grid(frame: Any) -> str:
    """Serialize a 2-D int grid (values 0-15) to newline-joined hex rows."""
    arr = np.asarray(frame, dtype=np.int16)
    return "\n".join("".join(format(int(v) & 0xF, "x") for v in row) for row in arr)


def parse_grid(text: str) -> np.ndarray:
    """Inverse of :func:`serialize_grid` — hex rows back to an int16 array."""
    rows = [line for line in text.strip().splitlines() if line]
    return np.asarray(
        [[int(ch, 16) for ch in row] for row in rows], dtype=np.int16
    )


def diff_cells(before: Any, after: Any) -> list[list[int]]:
    """Return ``[[row, col, old, new], ...]`` for every cell that changed."""
    a = np.asarray(before, dtype=np.int16)
    b = np.asarray(after, dtype=np.int16)
    rows, cols = np.where(a != b)
    return [[int(r), int(c), int(a[r, c]), int(b[r, c])] for r, c in zip(rows, cols)]


def apply_diff(before: Any, cells: list[list[int]]) -> np.ndarray:
    """Apply a ``[[row, col, old, new], ...]`` diff, returning the new grid."""
    out = np.array(before, dtype=np.int16, copy=True)
    for r, c, _old, new in cells:
        out[r, c] = new
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Transition selection
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Transition:
    """One observed ``(frame, action, next_frame)`` sample."""

    frame: np.ndarray
    action_idx: int
    next_frame: np.ndarray

    @property
    def action(self) -> str:
        return action_call_args(self.action_idx)[0]

    @property
    def xy(self) -> tuple[int, int] | None:
        return action_call_args(self.action_idx)[1]

    @property
    def changed(self) -> list[list[int]]:
        return diff_cells(self.frame, self.next_frame)

# ─────────────────────────────────────────────────────────────────────────────
# Prompt construction
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are a program synthesizer for a grid game. The board is a 64x64 grid; "
    "each cell is an integer 0-15 (a color index). Actions are ACTION1..ACTION7. "
    "ACTION6 is a click carrying grid coordinates (x=column, y=row). In the "
    "examples, ACTION6(x,y) denotes a click at column x, row y.\n\n"
    "Write a pure-stdlib, DETERMINISTIC Python function with the exact signature:\n"
    "    def predict_next_frame(frame, action, xy=None):\n"
    "where `frame` is a list of 64 lists of 64 ints, `action` is one of the "
    "strings 'ACTION1'..'ACTION7', and `xy` is a (x, y) tuple for ACTION6 else "
    "None. Return the predicted next frame as a list of 64 lists of 64 ints. "
    "Do not read files, network, or the clock. Output ONLY a single ```python "
    "code block, nothing else."
)


def build_observations_block(few_shot: list[Transition]) -> str:
    """Serialize few-shot transitions: initial grid once, then per-action diffs."""
    if not few_shot:
        return "No observations."
    lines = ["INITIAL_FRAME (hex, one char per cell, 64 rows):"]
    lines.append(serialize_grid(few_shot[0].frame))
    lines.append("")
    lines.append("TRANSITIONS (action -> changed cells [row,col,old,new]):")
    for t in few_shot:
        lines.append(
            json.dumps(
                {"action": action_label(t.action_idx), "changed": t.changed},
                separators=(",", ":"),
            )
        )
    return "\n".join(lines)


INSTRUCTION = (
    "From these observations, infer the game's transition rule and write "
    "`predict_next_frame`. Prefer a rule that generalizes over one that "
    "hard-codes the examples. Output ONLY the ```python code block."
)


# Game-AGNOSTIC mechanic vocabulary (human Core-Knowledge prior). Names no
# specific game and gives no answers — it only primes the hypothesis space,
# so it is safe for the 110 private eval games (R51 axis B).
MECHANICS_PRIOR = (
    "Common grid-game mechanics to consider while forming hypotheses (the "
    "game at hand may use none, one, or several):\n"
    "- A player avatar that moves one cell per directional action; walls or "
    "colored borders block movement.\n"
    "- Pushable objects: moving into an object shifts it if the cell behind "
    "is free (Sokoban-like).\n"
    "- Toggles: clicking or stepping on a cell flips its state, sometimes "
    "also flipping neighbors (lights-out-like).\n"
    "- Paint/fill: an action recolors a region; color spreads by "
    "connectivity.\n"
    "- Collect/merge: touching items removes or combines them; counters or "
    "HUD pixels elsewhere may tick when this happens.\n"
    "- Gravity or sliding: pieces fall or slide until blocked.\n"
    "- Rotation/reflection: an action transforms a whole shape or board "
    "region geometrically.\n"
    "- Teleports/portals: entering one special cell moves the player to its "
    "pair.\n"
    "- No-ops: many actions legitimately change nothing in some states — "
    "predicting 'no change' can be correct.\n"
    "Match observed diffs against these patterns before inventing ad-hoc "
    "rules, and prefer the simplest mechanic consistent with ALL "
    "observations."
)


def build_prompt(
    few_shot: list[Transition], mechanics_prior: bool = False
) -> list[dict[str, str]]:
    """Build the initial (round-0) chat messages for one game."""
    system = SYSTEM_PROMPT
    if mechanics_prior:
        system = f"{SYSTEM_PROMPT}\n\n{MECHANICS_PRIOR}"
    user = f"{build_observations_block(few_shot)}\n\n{INSTRUCTION}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_refinement_prompt(prev_code: str, mismatches: list[dict[str, Any]]) -> str:
    """Build the feedback message that asks the model to FIX its function.

    Shows up to 3 held-out cases where the current function was wrong: the
    action, the ACTUAL changed cells, and what the function PREDICTED (its
    changed cells, or the execution error).
    """
    lines = [
        "Your predict_next_frame was wrong on these held-out cases.",
        "Each case lists the action, the ACTUAL changed cells, and YOUR "
        "prediction's changed cells (or the error it raised).",
        "",
    ]
    for i, m in enumerate(mismatches[:3], 1):
        lines.append(f"Case {i}: action={m['action']}")
        lines.append(f"  actual_changed = {json.dumps(m['actual_changed'])}")
        if m.get("error"):
            lines.append(f"  your_prediction = ERROR: {m['error']}")
        else:
            lines.append(f"  your_predicted_changed = {json.dumps(m['pred_changed'])}")
        lines.append("")
    lines.append(
        "Fix the transition rule so it matches the ACTUAL changes. Output ONLY "
        "the corrected ```python code block."
    )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Code extraction + sandboxed execution
# ─────────────────────────────────────────────────────────────────────────────
_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


_OPEN_FENCE = re.compile(r"```(?:python)?\s*\n", re.IGNORECASE)


def extract_code(text: str) -> str:
    """Return the LAST fenced code block, or the raw text if none is fenced.

    A generation cut off at the token cap leaves an OPENING fence with no
    closing one (R49c ka59 round 3) — strip the fence header and keep the
    body instead of exec()ing the literal backticks.
    """
    blocks = _CODE_BLOCK.findall(text)
    if blocks:
        return blocks[-1].strip()
    m = _OPEN_FENCE.search(text)
    if m:
        return text[m.end():].strip()
    return text.strip()


_ALLOWED_IMPORTS = {"math", "copy", "itertools", "collections", "functools"}


def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
    """A restricted ``__import__`` that only permits a stdlib whitelist."""
    root = name.split(".")[0]
    if root in _ALLOWED_IMPORTS:
        return __import__(name, *args, **kwargs)
    raise ImportError(f"import of {name!r} is not allowed in the sandbox")


_SAFE_BUILTIN_NAMES = (
    "abs bool dict enumerate filter float int len list map max min range "
    "reversed round set sorted sum tuple zip any all isinstance print"
).split()


def _safe_builtins() -> dict[str, Any]:
    import builtins

    ns = {name: getattr(builtins, name) for name in _SAFE_BUILTIN_NAMES}
    ns["__import__"] = _safe_import
    ns["True"] = True
    ns["False"] = False
    ns["None"] = None
    return ns


class SandboxError(Exception):
    """Raised when generated code fails to compile, load, or execute."""


def _run_with_timeout(fn: Callable[..., Any], args: tuple[Any, ...], timeout: float) -> Any:
    """Call ``fn(*args)`` but abort with ``TimeoutError`` after ``timeout`` s.

    Uses ``SIGALRM`` on the main thread (interrupts Python-level busy loops
    between bytecodes) and a non-killing daemon-thread join elsewhere.
    """
    if (
        threading.current_thread() is threading.main_thread()
        and hasattr(signal, "SIGALRM")
    ):
        def _handler(signum: int, frame: Any) -> None:
            raise TimeoutError("prediction timed out")

        old = signal.signal(signal.SIGALRM, _handler)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        try:
            return fn(*args)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)

    result: dict[str, Any] = {}

    def _target() -> None:
        try:
            result["value"] = fn(*args)
        except BaseException as exc:  # noqa: BLE001 - surfaced to caller
            result["error"] = exc

    th = threading.Thread(target=_target, daemon=True)
    th.start()
    th.join(timeout)
    if th.is_alive():
        raise TimeoutError("prediction timed out")
    if "error" in result:
        raise result["error"]
    return result["value"]


def compile_predict(code: str, timeout: float = 2.0) -> Callable[..., Any]:
    """Compile+load a ``predict_next_frame`` callable from generated source.

    Executes the module body in a restricted namespace (whitelisted builtins,
    no unrestricted imports) under a timeout. Raises :class:`SandboxError` if the
    code will not compile, loops at import time, or defines no callable.
    """
    namespace: dict[str, Any] = {"__builtins__": _safe_builtins()}
    try:
        compiled = compile(code, "<generated>", "exec")
    except SyntaxError as exc:
        raise SandboxError(f"syntax error: {exc}") from exc

    def _load() -> None:
        exec(compiled, namespace)  # noqa: S102 - sandboxed namespace

    try:
        _run_with_timeout(_load, (), timeout)
    except Exception as exc:  # noqa: BLE001 - report as sandbox failure
        raise SandboxError(f"module execution failed: {exc}") from exc

    fn = namespace.get("predict_next_frame")
    if not callable(fn):
        raise SandboxError("no callable predict_next_frame defined")
    return fn


def _validate_grid(value: Any, shape: tuple[int, int]) -> np.ndarray:
    """Coerce a prediction to an int16 array of ``shape`` or raise."""
    arr = np.asarray(value, dtype=np.int16)
    if arr.shape != shape:
        raise SandboxError(f"expected grid shape {shape}, got {arr.shape}")
    return arr


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class ScoreResult:
    """Held-out scores for one compiled function."""

    code_validity: float
    cell_accuracy: float
    exact_frame_accuracy: float
    n: int
    mismatches: list[dict[str, Any]] = field(default_factory=list)


def score_predictions(
    fn: Callable[..., Any] | None,
    held_out: list[Transition],
    timeout: float = 2.0,
) -> ScoreResult:
    """Score a compiled function over held-out transitions.

    A case that raises, times out, or returns a wrong-shaped grid contributes 0
    to cell/exact accuracy and is recorded as a mismatch (with its error, or its
    predicted changed cells) for the refinement loop.
    """
    n = len(held_out)
    if n == 0:
        return ScoreResult(0.0, 0.0, 0.0, 0)

    ran = 0
    cell_sum = 0.0
    exact = 0
    mismatches: list[dict[str, Any]] = []

    for t in held_out:
        shape = t.next_frame.shape
        actual_changed = t.changed
        if fn is None:
            mismatches.append(
                {"action": action_label(t.action_idx),
                 "actual_changed": actual_changed, "error": "no valid function"}
            )
            continue
        try:
            pred = _run_with_timeout(fn, (t.frame.tolist(), t.action, t.xy), timeout)
            grid = _validate_grid(pred, shape)
        except Exception as exc:  # noqa: BLE001 - degrade to invalid case
            mismatches.append(
                {"action": action_label(t.action_idx),
                 "actual_changed": actual_changed, "error": str(exc)[:200]}
            )
            continue

        ran += 1
        match = grid == t.next_frame
        cell_sum += float(match.mean())
        if bool(match.all()):
            exact += 1
        else:
            mismatches.append(
                {"action": action_label(t.action_idx),
                 "actual_changed": actual_changed,
                 "pred_changed": diff_cells(t.frame, grid)}
            )

    return ScoreResult(
        code_validity=ran / n,
        cell_accuracy=cell_sum / n,
        exact_frame_accuracy=exact / n,
        n=n,
        mismatches=mismatches,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Ollama chat backend
# ─────────────────────────────────────────────────────────────────────────────
class OllamaChat:
    """Live /api/chat client (stream=False) with one retry."""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        request_timeout: int = 900,
        num_ctx: int = 16384,
    ):
        self._endpoint = f"{host.rstrip('/')}/api/chat"
        self._request_timeout = request_timeout
        self._num_ctx = num_ctx

    def __call__(
        self, messages: list[dict[str, str]], model: str, max_tokens: int
    ) -> tuple[str, dict[str, Any]]:
        # gpt-oss models cannot disable thinking — Ollama's `think` for them is
        # an effort level ("low"/"medium"/"high"); boolean False is rejected.
        think: bool | str = "low" if "gpt-oss" in model else False
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": think,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.0,
                "top_p": 1.0,
                # Ollama's default num_ctx (4096) silently truncates the few-shot
                # prompt (R49 run 2: rounds[0] prompt_eval_count == 4096 exactly).
                "num_ctx": self._num_ctx,
            },
        }
        data = json.dumps(body).encode("utf-8")
        last_err: Exception | None = None
        for _attempt in range(2):
            req = urllib.request.Request(
                self._endpoint, data=data,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self._request_timeout) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_err = exc
                time.sleep(1.0)
                continue
            text = payload.get("message", {}).get("content", "")
            meta = {
                "prompt_tokens": int(payload.get("prompt_eval_count", 0)),
                "eval_tokens": int(payload.get("eval_count", 0)),
                "latency_s": round(time.time() - t0, 3),
            }
            return text, meta
        raise RuntimeError(
            f"Ollama /api/chat failed for model={model!r}: {last_err}. "
            f"Is `ollama serve` running and the model pulled?"
        )

