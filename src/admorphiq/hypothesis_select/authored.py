"""R97 build prerequisite #2: the dedicated AST-validating sandbox for ONE
authored cell-update function.

Codex correction 8 made concrete: the R49/EWM loader
(:func:`admorphiq.ewm.core.compile_predict`) is measured-INSUFFICIENT as the
trust boundary for a model-authored rule — it permits a stdlib import whitelist
and executes the whole module body in-process, so an authored function could run
arbitrary module-level statements and import permitted modules. R97 needs a
tighter gate for the single authored function

    def update(colour: int, click_index: int, palette: list[int]) -> int

The gate is two-stage:

1. **AST validation** (:func:`validate_authored`) — a purely static check: the
   source is EXACTLY one ``def update(colour, click_index, palette)`` with no
   imports, no top-level statements besides the def, no nested defs/classes, no
   ``global``/``nonlocal``, no decorators, no dangerous attribute access
   (``getattr``/``setattr``/``eval``/``exec``/dunder attributes), and an AST node
   count under a cap. A function that fails validation NEVER executes.

2. **Subprocess execution** (:func:`execute_in_subprocess`) — the validated
   source runs in a FRESH interpreter with wall-clock, CPU, address-space, and
   output caps (POSIX ``resource`` limits), a builtins-stripped namespace, and NO
   import machinery. The child validates the return is an ``int`` in ``palette``
   and that ``palette`` was not mutated.

:class:`AuthoredUpdate` wraps a validated source for repeated use: it runs one
subprocess PROBE at construction to confirm the source respects the contract,
then serves fast in-process predictions (still builtins-stripped, still
enforcing return-in-palette + non-mutation per call, still counting invocations
and pinning the source hash). Planning needs hundreds of ``update`` calls; the
subprocess is the acceptance gate, the in-process callable is the hot path — and
both refuse a non-conforming result.

Scope: validation + execution of the authored function only — no compiler, no
verifier, no LLM.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Optional

_REQUIRED_PARAMS = ("colour", "click_index", "palette")
_FUNCTION_NAME = "update"
_MAX_AST_NODES = 300
# Attribute/name tokens an authored pure arithmetic rule never needs and that are
# the usual sandbox-escape handles. Any of these => reject at validation time.
_DANGEROUS_NAMES = frozenset(
    {
        "eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr",
        "globals", "locals", "vars", "open", "input", "exit", "quit", "breakpoint",
        "memoryview", "object", "type", "super", "classmethod", "staticmethod",
    }
)
# The only attribute accesses an authored pure cell-update rule needs: the pure,
# non-mutating list lookups. Everything else — and every dunder — is rejected, so
# no ``.__class__`` / ``.__globals__`` escape handle is reachable.
_ALLOWED_ATTRS = frozenset({"index", "count"})
_DEFAULT_TIMEOUT_S = 2.0
_DEFAULT_MEM_MB = 256
_MAX_OUTPUT_BYTES = 4096


class AuthoredError(Exception):
    """Raised when an authored function fails validation, execution, or the
    return-value / non-mutation contract."""


@dataclass(frozen=True)
class AuthoredCellTransition:
    """A schema-shaped transition-model TAG carrying a model-authored cell-update
    rule (the tier-2 self-extension surface): the proposed enum ``name`` and the
    executable ``source`` for ``def update(colour, click_index, palette) -> int``.
    Lives here (not in the frozen ``schema`` union) so the R95 cell-state schema is
    untouched; the compiler dispatches on this tag. The source is inert until a
    :class:`AuthoredUpdate` validates + probes it — a tag is not a trusted rule."""

    KIND = "authored_cell_update"

    name: str
    source: str


@dataclass(frozen=True)
class ValidationResult:
    """The static AST verdict: ``ok`` plus a one-line ``reason`` (empty on ok) and
    the counted AST node total (pinned by tests / logged for provenance)."""

    ok: bool
    reason: str
    node_count: int


@dataclass(frozen=True)
class ExecutionResult:
    """One guarded execution outcome: ``ok`` with the returned ``value``, or
    ``ok=False`` with the failure ``error`` (validation, timeout, resource, bad
    return, or input mutation)."""

    ok: bool
    value: Optional[int]
    error: str


# ── stage 1: static AST validation ──────────────────────────────────────────


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def validate_authored(source: str) -> ValidationResult:
    """Statically validate the authored ``update`` source. Returns a
    :class:`ValidationResult`; ``ok=False`` names the first violation. A pure
    check — it never executes the source."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ValidationResult(False, f"syntax error: {exc}", 0)

    node_count = sum(1 for _ in ast.walk(tree))
    if node_count > _MAX_AST_NODES:
        return ValidationResult(False, f"AST too large: {node_count} > {_MAX_AST_NODES}", node_count)

    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        return ValidationResult(
            False, "module body must be exactly one function definition", node_count
        )
    fn = tree.body[0]
    if fn.name != _FUNCTION_NAME:
        return ValidationResult(False, f"function must be named {_FUNCTION_NAME!r}", node_count)
    if fn.decorator_list:
        return ValidationResult(False, "decorators are not allowed", node_count)

    args = fn.args
    if args.vararg or args.kwarg or args.kwonlyargs or args.posonlyargs or args.defaults or args.kw_defaults:
        return ValidationResult(False, "signature must be exactly (colour, click_index, palette)", node_count)
    names = tuple(a.arg for a in args.args)
    if names != _REQUIRED_PARAMS:
        return ValidationResult(
            False, f"parameters must be {_REQUIRED_PARAMS}, got {names}", node_count
        )

    for node in ast.walk(fn):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return ValidationResult(False, "imports are not allowed", node_count)
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return ValidationResult(False, "global/nonlocal are not allowed", node_count)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not fn:
            return ValidationResult(False, "nested function definitions are not allowed", node_count)
        if isinstance(node, (ast.ClassDef, ast.Lambda)):
            return ValidationResult(False, "class/lambda definitions are not allowed", node_count)
        if isinstance(node, ast.Attribute) and (
            _is_dunder(node.attr) or node.attr not in _ALLOWED_ATTRS
        ):
            return ValidationResult(False, f"attribute access is not allowed ('.{node.attr}')", node_count)
        if isinstance(node, ast.Name) and (node.id in _DANGEROUS_NAMES or _is_dunder(node.id)):
            return ValidationResult(False, f"disallowed name {node.id!r}", node_count)

    return ValidationResult(True, "", node_count)


# ── restricted execution namespace ──────────────────────────────────────────

_SAFE_BUILTIN_NAMES = "abs bool int len list max min range round sum tuple sorted enumerate zip".split()


def _safe_builtins() -> dict[str, Any]:
    """A minimal builtins namespace: pure arithmetic + sequence helpers, NO import
    machinery (no ``__import__``), no I/O, no introspection."""
    import builtins

    ns = {name: getattr(builtins, name) for name in _SAFE_BUILTIN_NAMES}
    ns["True"] = True
    ns["False"] = False
    ns["None"] = None
    return ns


def _load_callable(source: str) -> Any:
    """Exec a VALIDATED source in a builtins-stripped namespace and return the
    ``update`` callable. Caller must have validated ``source`` first."""
    namespace: dict[str, Any] = {"__builtins__": _safe_builtins()}
    exec(compile(source, "<authored>", "exec"), namespace)  # noqa: S102 - sandboxed namespace
    fn = namespace.get(_FUNCTION_NAME)
    if not callable(fn):
        raise AuthoredError("no callable update defined")
    return fn


def _check_result(value: Any, palette: list[int], palette_before: list[int]) -> int:
    """Enforce the return contract: an ``int`` (never ``bool``) in ``palette``, and
    ``palette`` unmutated by the call. Returns the validated int or raises."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuthoredError(f"update must return an int, got {type(value).__name__}")
    if value not in palette_before:
        raise AuthoredError(f"return {value} not in palette {palette_before}")
    if palette != palette_before:
        raise AuthoredError("update mutated its palette argument")
    return int(value)


# ── stage 2: subprocess execution (the trust boundary) ──────────────────────

# The child program: read {source, colour, click_index, palette} as JSON on
# stdin, exec the source with stripped builtins, call update, enforce the return
# + non-mutation contract, print {"value": int} or {"error": str}. No imports
# available to the authored code; the child itself uses only json/sys/resource.
_CHILD = r"""
import json, sys
data = json.load(sys.stdin)
src = data["source"]
colour, click_index = data["colour"], data["click_index"]
palette = list(data["palette"])
snapshot = list(palette)
_SAFE = "abs bool int len list max min range round sum tuple sorted enumerate zip".split()
import builtins as _b
_ns = {"__builtins__": {n: getattr(_b, n) for n in _SAFE}}
_ns["__builtins__"].update({"True": True, "False": False, "None": None})
try:
    exec(compile(src, "<authored>", "exec"), _ns)
    fn = _ns.get("update")
    if not callable(fn):
        raise ValueError("no callable update defined")
    out = fn(colour, click_index, palette)
    if isinstance(out, bool) or not isinstance(out, int):
        raise ValueError("update must return an int")
    if out not in snapshot:
        raise ValueError("return %r not in palette" % (out,))
    if palette != snapshot:
        raise ValueError("update mutated its palette argument")
    print(json.dumps({"value": int(out)}))
except BaseException as exc:
    print(json.dumps({"error": (type(exc).__name__ + ": " + str(exc))[:400]}))
"""

def _make_preexec(mem_mb: int, cpu_s: int):
    """A ``preexec_fn`` that caps the child's CPU time and (best-effort) address
    space via POSIX ``resource`` limits, or ``None`` where ``resource`` is
    unavailable (non-POSIX). Each limit is applied independently and a platform
    rejection is swallowed — an aborting ``preexec_fn`` would kill the spawn, so a
    limit the OS will not honour (macOS is quirky about ``RLIMIT_AS``) degrades to
    the reliable wall-clock timeout + CPU cap rather than failing the run."""
    try:
        import resource
    except ImportError:
        return None

    def _limit() -> None:  # pragma: no cover - runs only in the child process
        for res_name, value in (
            ("RLIMIT_AS", mem_mb * 1024 * 1024),
            ("RLIMIT_DATA", mem_mb * 1024 * 1024),
            ("RLIMIT_CPU", cpu_s),
        ):
            res = getattr(resource, res_name, None)
            if res is None:
                continue
            try:
                resource.setrlimit(res, (value, value))
            except (ValueError, OSError):
                continue

    return _limit


def execute_in_subprocess(
    source: str,
    colour: int,
    click_index: int,
    palette: list[int],
    *,
    timeout: float = _DEFAULT_TIMEOUT_S,
    mem_mb: int = _DEFAULT_MEM_MB,
) -> ExecutionResult:
    """Validate then run ``source`` in a fresh, resource-capped interpreter. The
    child has no import machinery for the authored code, a wall-clock ``timeout``,
    an address-space + CPU cap, and a bounded stdout. Returns an
    :class:`ExecutionResult` — never raises for an authored-code fault (a fault is
    reported as ``ok=False``)."""
    verdict = validate_authored(source)
    if not verdict.ok:
        return ExecutionResult(False, None, f"validation failed: {verdict.reason}")

    payload = json.dumps(
        {"source": source, "colour": int(colour), "click_index": int(click_index),
         "palette": [int(c) for c in palette]}
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-S", "-c", _CHILD],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=_make_preexec(mem_mb, max(1, int(timeout) + 1)),
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(False, None, "timeout")
    out = proc.stdout[:_MAX_OUTPUT_BYTES].strip()
    if not out:
        err = proc.stderr[:_MAX_OUTPUT_BYTES].strip() or f"no output (exit {proc.returncode})"
        return ExecutionResult(False, None, err)
    try:
        result = json.loads(out.splitlines()[-1])
    except json.JSONDecodeError:
        return ExecutionResult(False, None, "unparseable child output")
    if "error" in result:
        return ExecutionResult(False, None, result["error"])
    return ExecutionResult(True, int(result["value"]), "")


# ── the reusable wrapper ─────────────────────────────────────────────────────


class AuthoredUpdate:
    """A validated authored ``update`` rule ready for repeated planning use.

    Construction validates the source (AST) and runs ONE subprocess probe to
    confirm the source respects the contract on a probe input, so a source that
    only misbehaves at runtime is rejected before it is trusted. Each
    :meth:`predict` then serves a fast in-process call in the same
    builtins-stripped namespace, still enforcing return-in-palette + non-mutation
    and counting the invocation. The proposed enum ``name`` and the ``source_hash``
    are logged so causal use is auditable (Codex trap 1)."""

    def __init__(self, source: str, name: str) -> None:
        verdict = validate_authored(source)
        if not verdict.ok:
            raise AuthoredError(f"validation failed: {verdict.reason}")
        self.name = name
        self.source = source
        self.source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        self.node_count = verdict.node_count
        self.invocations = 0
        probe = execute_in_subprocess(source, colour=0, click_index=0, palette=[0, 1])
        if not probe.ok:
            raise AuthoredError(f"subprocess probe failed: {probe.error}")
        self._fn = _load_callable(source)

    def predict(self, colour: int, click_index: int, palette: list[int]) -> int:
        """The authored next colour for ``colour`` after ``click_index`` clicks,
        given ``palette``. Enforces the return contract on every call and counts
        the invocation. Raises :class:`AuthoredError` on any contract violation."""
        palette_before = list(palette)
        try:
            raw = self._fn(colour, click_index, list(palette))
        except AuthoredError:
            raise
        except BaseException as exc:  # noqa: BLE001 - surfaced as an authored fault
            raise AuthoredError(f"update raised {type(exc).__name__}: {exc}") from exc
        value = _check_result(raw, list(palette), palette_before)
        self.invocations += 1
        return value


def extensionally_equal(
    authored: AuthoredUpdate,
    rule_fn: Any,
    palette: list[int],
    click_indices: tuple[int, ...] = (0, 1, 2),
) -> tuple[bool, Optional[tuple[int, int]]]:
    """Codex correction 7: compare an authored update against a canned ``rule_fn``
    over EXHAUSTIVE finite fixtures — every palette colour x every click index.
    Returns ``(equal, first_mismatch)`` where ``first_mismatch`` is the
    ``(colour, click_index)`` that diverged, or ``None`` when fully equal.
    Extensional (behaviour-over-fixtures) equivalence, NOT source identity."""
    for click_index in click_indices:
        for colour in palette:
            got = authored.predict(colour, click_index, palette)
            want = rule_fn(colour, click_index, palette)
            if got != want:
                return False, (colour, click_index)
    return True, None


__all__ = [
    "AuthoredError",
    "AuthoredCellTransition",
    "ValidationResult",
    "ExecutionResult",
    "AuthoredUpdate",
    "validate_authored",
    "execute_in_subprocess",
    "extensionally_equal",
]
