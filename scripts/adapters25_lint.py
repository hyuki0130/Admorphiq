"""AST-based lint for script25 quarantine adapters (R56).

Enforces two rules on every module under ``src/admorphiq/adapters25/``
(excluding ``__init__.py`` and ``base.py``, which is the one file inside
the quarantine zone allowed to reach outside it — see its module
docstring):

1. **HARD (fails the lint)** — every import must resolve to the standard
   library, to ``admorphiq.kernels`` (any submodule), or to
   ``admorphiq.adapters25.base`` (absolute or the equivalent relative
   ``from .base import ...``). No other ``admorphiq`` module, no
   third-party package (no numpy, no torch, no arcengine) — otherwise "an
   adapter must not contain its own search/pixel algorithm" is
   unenforceable, since nothing would stop an adapter from importing a
   brittle legacy solver wholesale and calling it a "kernel composition".

2. **SOFT (warning only)** — a function containing a ``for``/``while`` loop
   nested more than 2 deep is flagged as a possible own-search
   implementation. This is a CRUDE heuristic (real BFS/DFS is usually 2+
   nested loops or an explicit stack/queue, but genuinely simple
   nested-loop code exists too — e.g. building a 2D array), hence a
   warning, not a failure.

Usage:
  uv run python scripts/adapters25_lint.py               # lint every adapter
  uv run python scripts/adapters25_lint.py path/to/x.py   # lint specific files
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ADAPTERS_DIR = _REPO_ROOT / "src" / "admorphiq" / "adapters25"
_EXCLUDED_FILENAMES = {"__init__.py", "base.py"}

_MAX_LOOP_NESTING = 2


def _is_stdlib(module_name: str) -> bool:
    top = module_name.split(".", 1)[0]
    return top == "__future__" or top in sys.stdlib_module_names


def _is_allowed_admorphiq(module_name: str) -> bool:
    return module_name == "admorphiq.kernels" or module_name.startswith(
        "admorphiq.kernels."
    ) or module_name == "admorphiq.adapters25.base"


@dataclass
class LintResult:
    path: Path
    import_violations: list[str] = field(default_factory=list)
    nesting_warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.import_violations


def _check_imports(tree: ast.Module) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if _is_stdlib(name) or _is_allowed_admorphiq(name):
                    continue
                violations.append(f"line {node.lineno}: import {name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Adapters live flat in this package alongside base.py, so
                # the only legitimate relative import is "from .base import
                # ...". Anything else (a deeper relative reach, or a bare
                # "from . import x") is rejected -- it cannot be verified
                # against the whitelist without resolving each alias target.
                mod = node.module or ""
                if node.level == 1 and mod == "base":
                    continue
                dots = "." * node.level
                violations.append(f"line {node.lineno}: from {dots}{mod} import ...")
                continue
            mod = node.module or ""
            if _is_stdlib(mod) or _is_allowed_admorphiq(mod):
                continue
            violations.append(f"line {node.lineno}: from {mod} import ...")
    return violations


def _max_loop_depth(fn: ast.AST) -> int:
    """Deepest for/while nesting inside ``fn``, not descending into nested defs.

    A nested function/lambda is measured on its OWN when the caller walks
    every FunctionDef in the module (see :func:`_check_nesting`), so its
    loops must not also inflate the ENCLOSING function's count.
    """

    def walk(node: ast.AST, depth: int) -> int:
        best = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            child_depth = (
                depth + 1 if isinstance(child, (ast.For, ast.While, ast.AsyncFor)) else depth
            )
            best = max(best, walk(child, child_depth))
        return best

    return walk(fn, 0)


def _check_nesting(tree: ast.Module, max_depth: int = _MAX_LOOP_NESTING) -> list[str]:
    warnings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            depth = _max_loop_depth(node)
            if depth > max_depth:
                warnings.append(
                    f"{node.name} (line {node.lineno}): loop nesting depth "
                    f"{depth} > {max_depth} -- possible own-search implementation"
                )
    return warnings


def lint_module(path: Path) -> LintResult:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    return LintResult(
        path=path,
        import_violations=_check_imports(tree),
        nesting_warnings=_check_nesting(tree),
    )


def lint_paths(paths: Iterable[Path]) -> list[LintResult]:
    return [lint_module(p) for p in paths]


def discover_adapter_paths() -> list[Path]:
    if not _ADAPTERS_DIR.exists():
        return []
    return sorted(p for p in _ADAPTERS_DIR.glob("*.py") if p.name not in _EXCLUDED_FILENAMES)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "modules",
        nargs="*",
        help="Adapter .py paths to lint (default: every module under adapters25/, "
        "excluding __init__.py and base.py).",
    )
    return p


def main() -> int:
    args = _build_parser().parse_args()
    paths = [Path(m) for m in args.modules] if args.modules else discover_adapter_paths()
    if not paths:
        print("No adapter modules found.")
        return 0

    failed = False
    for result in lint_paths(paths):
        print(f"{result.path}:")
        for v in result.import_violations:
            print(f"  FAIL import: {v}")
        for w in result.nesting_warnings:
            print(f"  WARN nesting: {w}")
        if result.ok and not result.nesting_warnings:
            print("  ok")
        if not result.ok:
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
