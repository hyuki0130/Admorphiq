"""R49: measured LLM-selection benchmark for the executable-world-model track.

Purpose
-------
For each candidate LLM, measure how well it *synthesizes* a pure-Python

    def predict_next_frame(frame, action, xy=None)

transition function from a handful of observed transitions of an UNKNOWN game,
and how much that function improves under K rounds of execution feedback. This
is the pivotal go/no-go for the executable-world-model paradigm (R48 research,
``.wiki/wiki/rounds/r48_llm-selection-ewm.md``): a WRITE/refine-code LLM is only
worth deploying if it can reach useful exact-frame accuracy AND climb under
refinement.

The bench never trusts model-generated code — every synthesized function runs in
a restricted namespace with a per-prediction timeout, so a broken or malicious
generation degrades to "invalid", never a crash.

Data
----
Reuses ``scripts/collect_transitions.py`` output (``<game>.npz`` with
``frames`` / ``actions`` / ``next_frames``). Per game we take a deterministic
15 few-shot / 10 held-out split (changed transitions preferred so the examples
and the held-out targets actually exercise the game's dynamics).

Serialization (token economy)
-----------------------------
The first few-shot frame is emitted ONCE as a compact hex grid (one char/cell,
values 0-15). Every transition is then a diff — ``{"action", "changed"}`` where
``changed`` is ``[[row, col, old, new], ...]``. Prompts stay well under ~8k
tokens.

Scores (per model x game)
-------------------------
- ``code_validity``        fraction of held-out cases that ran + returned a grid
- ``cell_accuracy``        mean per-cell match over held-out
- ``exact_frame_accuracy`` fraction of held-out frames predicted 100% (headline)
- ``refinement_gain``      exact-frame delta R0 -> R{K}
- tokens / latency         per LLM call

Run (I run this; do NOT run it from an agent — the LLM call is live)
--------------------------------------------------------------------
    uv run python scripts/llm_worldmodel_bench.py \
        --models qwen3-coder:30b,qwen3:30b-a3b,qwen3:14b \
        --games ka59,sb26,sp80 --rounds 3 --out scripts/rounds/R49
"""

from __future__ import annotations

import argparse
import json
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

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


def select_transitions(
    data: dict[str, np.ndarray],
    n_few: int = 15,
    n_hold: int = 10,
    seed: int = 0,
    max_diff_cells: int = 80,
) -> tuple[list[Transition], list[Transition]]:
    """Deterministically split transitions into (few-shot, held-out) lists.

    Changed transitions with a serialization-friendly diff (``<= max_diff_cells``
    changed cells) are preferred so few-shot examples stay compact and held-out
    targets actually test the dynamics. If too few qualify, the pool is topped up
    with remaining changed then unchanged transitions. The shuffle is seeded, so
    the same (data, seed) always yields the same split.
    """
    frames = data["frames"]
    actions = data["actions"]
    next_frames = data["next_frames"]
    n = int(actions.shape[0])

    changed_counts = np.array(
        [int((frames[i] != next_frames[i]).sum()) for i in range(n)]
    )
    changed = changed_counts > 0

    small = [i for i in range(n) if changed[i] and changed_counts[i] <= max_diff_cells]
    big = [i for i in range(n) if changed[i] and changed_counts[i] > max_diff_cells]
    unchanged = [i for i in range(n) if not changed[i]]

    rng = np.random.RandomState(seed)
    rng.shuffle(small)
    rng.shuffle(big)
    rng.shuffle(unchanged)

    need = n_few + n_hold
    ordered = small + big + unchanged
    picked = ordered[:need]

    def make(i: int) -> Transition:
        return Transition(
            frame=np.asarray(frames[i], dtype=np.int16),
            action_idx=int(actions[i]),
            next_frame=np.asarray(next_frames[i], dtype=np.int16),
        )

    few = [make(i) for i in picked[:n_few]]
    hold = [make(i) for i in picked[n_few : n_few + n_hold]]
    return few, hold


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


def build_prompt(few_shot: list[Transition]) -> list[dict[str, str]]:
    """Build the initial (round-0) chat messages for one game."""
    user = f"{build_observations_block(few_shot)}\n\n{INSTRUCTION}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
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
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
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


# ─────────────────────────────────────────────────────────────────────────────
# Per model x game refinement run
# ─────────────────────────────────────────────────────────────────────────────
def run_model_game(
    chat: ChatFn,
    model: str,
    game: str,
    few_shot: list[Transition],
    held_out: list[Transition],
    rounds: int,
    max_tokens: int = 2048,
    timeout: float = 2.0,
) -> dict[str, Any]:
    """Run round-0 synthesis + ``rounds`` refinement rounds for one model×game.

    Returns a JSON-serializable record with per-round scores, the refinement
    gain (R0 -> R{rounds} exact-frame delta), and token/latency totals.
    """
    messages = build_prompt(few_shot)
    round_records: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    code = ""
    last_mismatches: list[dict[str, Any]] = []

    for r in range(rounds + 1):
        if r > 0:
            messages = messages + [
                {"role": "assistant", "content": f"```python\n{code}\n```"},
                {"role": "user",
                 "content": build_refinement_prompt(code, last_mismatches)},
            ]
        text, meta = chat(messages, model, max_tokens)
        calls.append(meta)
        code = extract_code(text)
        try:
            fn: Callable[..., Any] | None = compile_predict(code, timeout)
            compile_error = ""
        except SandboxError as exc:
            fn = None
            compile_error = str(exc)[:200]
        score = score_predictions(fn, held_out, timeout)
        last_mismatches = score.mismatches
        round_records.append(
            {
                "round": r,
                "code_validity": round(score.code_validity, 4),
                "cell_accuracy": round(score.cell_accuracy, 4),
                "exact_frame_accuracy": round(score.exact_frame_accuracy, 4),
                "compile_error": compile_error,
                "prompt_tokens": meta.get("prompt_tokens", 0),
                "eval_tokens": meta.get("eval_tokens", 0),
                "latency_s": meta.get("latency_s", 0.0),
                "code": code,
            }
        )

    r0 = round_records[0]["exact_frame_accuracy"]
    rk = round_records[-1]["exact_frame_accuracy"]
    return {
        "model": model,
        "game": game,
        "n_few": len(few_shot),
        "n_hold": len(held_out),
        "rounds": round_records,
        "final": round_records[-1],
        "refinement_gain": round(rk - r0, 4),
        "total_prompt_tokens": sum(c.get("prompt_tokens", 0) for c in calls),
        "total_eval_tokens": sum(c.get("eval_tokens", 0) for c in calls),
        "total_latency_s": round(sum(c.get("latency_s", 0.0) for c in calls), 3),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Data loading + IO
# ─────────────────────────────────────────────────────────────────────────────
def load_game_data(game: str, data_dir: Path) -> dict[str, np.ndarray]:
    """Load a game's ``.npz``, collecting it via the CLI if missing."""
    path = data_dir / f"{game.lower()}.npz"
    if not path.exists():
        print(f"[{game}] transitions missing; collecting via collect_transitions.py …",
              flush=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "collect_transitions.py"),
             "--titles", game, "--out", str(data_dir)],
            check=True,
        )
    npz = np.load(path, allow_pickle=True)
    return {"frames": npz["frames"], "actions": npz["actions"],
            "next_frames": npz["next_frames"]}


def write_summary(round_dir: Path) -> None:
    """Regenerate SUMMARY.txt from every per-model×game json (live, partial-safe)."""
    games_dir = round_dir / "games"
    records = []
    for f in sorted(games_dir.glob("*.json")):
        try:
            records.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue

    lines = ["R49 — executable-world-model LLM selection", "=" * 60, ""]
    header = (
        f"{'model':<22}{'game':<7}{'valid':>6}{'cell':>7}"
        f"{'exR0':>7}{'exRK':>7}{'exBest':>8}{'gain':>7}{'tok':>8}{'sec':>8}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    per_model: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        per_model.setdefault(rec["model"], []).append(rec)
        r0 = rec["rounds"][0]["exact_frame_accuracy"] if rec["rounds"] else 0.0
        best = max(
            (r["exact_frame_accuracy"] for r in rec["rounds"]), default=0.0
        )
        rec["_best_exact"] = best
        fin = rec["final"]
        lines.append(
            f"{rec['model']:<22}{rec['game']:<7}"
            f"{fin['code_validity']:>6.2f}{fin['cell_accuracy']:>7.3f}"
            f"{r0:>7.2f}{fin['exact_frame_accuracy']:>7.2f}{best:>8.2f}"
            f"{rec['refinement_gain']:>+7.2f}"
            f"{rec['total_prompt_tokens'] + rec['total_eval_tokens']:>8}"
            f"{rec['total_latency_s']:>8.1f}"
        )

    lines.append("")
    lines.append("Per-model means (headline = exact-frame-accuracy @ final round):")
    for model, recs in sorted(per_model.items()):
        mean_exact = float(np.mean([r["final"]["exact_frame_accuracy"] for r in recs]))
        mean_cell = float(np.mean([r["final"]["cell_accuracy"] for r in recs]))
        mean_gain = float(np.mean([r["refinement_gain"] for r in recs]))
        mean_valid = float(np.mean([r["final"]["code_validity"] for r in recs]))
        mean_best = float(np.mean([r["_best_exact"] for r in recs]))
        lines.append(
            f"  {model:<22} exact={mean_exact:.3f} best-exact={mean_best:.3f} "
            f"cell={mean_cell:.3f} valid={mean_valid:.2f} gain={mean_gain:+.3f} "
            f"(n={len(recs)})"
        )
    lines.append("")
    (round_dir / "SUMMARY.txt").write_text("\n".join(lines))


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models", default="qwen3-coder:30b,qwen3:30b-a3b,qwen3:14b",
                   help="Comma-separated Ollama model tags.")
    p.add_argument("--games", default="ka59,sb26,sp80",
                   help="Comma-separated game titles.")
    p.add_argument("--rounds", type=int, default=3, help="Refinement rounds (K).")
    p.add_argument("--out", default="scripts/rounds/R49", help="Round output dir.")
    p.add_argument("--data-dir", default="data/transitions/train",
                   help="Directory of <game>.npz transition files.")
    p.add_argument("--host", default="http://localhost:11434", help="Ollama host.")
    p.add_argument("--few", type=int, default=15, help="Few-shot transitions/game.")
    p.add_argument("--hold", type=int, default=10, help="Held-out transitions/game.")
    p.add_argument("--seed", type=int, default=0, help="Split seed.")
    p.add_argument("--max-tokens", type=int, default=2048, help="Generation cap.")
    p.add_argument("--num-ctx", type=int, default=16384,
                   help="Ollama context window (default 4096 truncates few-shot prompts).")
    p.add_argument("--pred-timeout", type=float, default=2.0,
                   help="Per-prediction sandbox timeout (s).")
    p.add_argument("--max-diff-cells", type=int, default=80,
                   help="Max changed cells for a few-shot-eligible transition.")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    games = [g.strip() for g in args.games.split(",") if g.strip()]
    round_dir = REPO_ROOT / args.out
    (round_dir / "games").mkdir(parents=True, exist_ok=True)
    data_dir = REPO_ROOT / args.data_dir

    chat = OllamaChat(host=args.host, num_ctx=args.num_ctx)

    splits: dict[str, tuple[list[Transition], list[Transition]]] = {}
    for game in games:
        data = load_game_data(game, data_dir)
        splits[game] = select_transitions(
            data, n_few=args.few, n_hold=args.hold, seed=args.seed,
            max_diff_cells=args.max_diff_cells,
        )

    for model in models:
        for game in games:
            few, hold = splits[game]
            print(f"[{model} × {game}] running {args.rounds} refinement rounds …",
                  flush=True)
            record = run_model_game(
                chat, model, game, few, hold, rounds=args.rounds,
                max_tokens=args.max_tokens, timeout=args.pred_timeout,
            )
            safe_model = model.replace(":", "_").replace("/", "_")
            out_path = round_dir / "games" / f"{safe_model}__{game}.json"
            out_path.write_text(json.dumps(record, indent=2))
            write_summary(round_dir)  # live-append per model×game
            fin = record["final"]
            print(f"    exact={fin['exact_frame_accuracy']:.2f} "
                  f"cell={fin['cell_accuracy']:.3f} "
                  f"gain={record['refinement_gain']:+.2f}", flush=True)

    print(f"Done. See {round_dir / 'SUMMARY.txt'}", flush=True)


if __name__ == "__main__":
    main()
