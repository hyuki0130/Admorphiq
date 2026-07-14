"""Tests for scripts/adapters25_lint.py — the script25 quarantine enforcer (R56)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from adapters25_lint import (  # noqa: E402
    discover_adapter_paths,
    lint_module,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _write(tmp_path: Path, source: str) -> Path:
    p = tmp_path / "adapter.py"
    p.write_text(source, encoding="utf-8")
    return p


def test_valid_adapter_imports_pass():
    """Purpose: an adapter using only stdlib + admorphiq.kernels +
    admorphiq.adapters25.base (absolute imports) must report zero import
    violations.
    Expected feedback: failure means the whitelist check is rejecting
    legitimate imports, which would make every real adapter unwritable."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        path = _write(
            Path(td),
            """
from __future__ import annotations

import math
from typing import Any

from admorphiq.adapters25.base import GameAdapter, canonical_layer
from admorphiq.kernels import find_regions
from admorphiq.kernels.paths import grid_shortest_path


class Adapter(GameAdapter):
    pass
""",
        )
        result = lint_module(path)
        assert result.import_violations == []
        assert result.ok is True


def test_third_party_import_is_a_violation():
    """Purpose: an adapter importing numpy (or any third-party package) must
    be flagged — the quarantine's whole point is that a solution can only be
    built from the namespace-safe kernel library.
    Expected feedback: failure means a brittle numpy-powered algorithm could
    smuggle itself into an adapter undetected."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        path = _write(Path(td), "import numpy as np\n")
        result = lint_module(path)
        assert result.ok is False
        assert any("numpy" in v for v in result.import_violations)


def test_non_kernel_admorphiq_import_is_a_violation():
    """Purpose: importing a non-kernels admorphiq module (e.g. a legacy
    game-specific solver) must be flagged, even though it is technically
    "in-repo" -- only admorphiq.kernels and admorphiq.adapters25.base are
    whitelisted.
    Expected feedback: failure means an adapter could wholesale-import a
    brittle legacy solver (e.g. admorphiq.rotation) and call it a kernel
    composition, defeating the quarantine."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        path = _write(Path(td), "from admorphiq.rotation import detect_framed_patterns\n")
        result = lint_module(path)
        assert result.ok is False
        assert any("admorphiq.rotation" in v for v in result.import_violations)


def test_relative_import_of_base_is_allowed_but_other_relative_imports_fail():
    """Purpose: "from .base import X" (the natural same-package import a
    real adapter file would write) must be allowed; any other relative
    import shape must be rejected since it cannot be verified against the
    whitelist without resolving the target.
    Expected feedback: failure on the .base case would force every adapter
    to use the (equally valid but more verbose) absolute import form;
    failure on the other case means an unverifiable relative import path is
    silently accepted."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        ok_path = _write(Path(td), "from .base import GameAdapter\n")
        ok_result = lint_module(ok_path)
        assert ok_result.ok is True

    with tempfile.TemporaryDirectory() as td2:
        bad_path = _write(Path(td2), "from . import something\n")
        bad_result = lint_module(bad_path)
        assert bad_result.ok is False


def test_deeply_nested_loop_triggers_warning_not_failure():
    """Purpose: a function with 3+ nested for/while loops is a plausible
    own-search implementation and must be WARNED about, but nesting alone
    must never fail the lint (it's a crude heuristic, not a certainty --
    plenty of legitimate glue code has 3 nested loops, e.g. array
    construction).
    Expected feedback: failure to warn means an own-search implementation
    could hide inside an adapter undetected; failure by hard-failing the
    lint means the crude heuristic is over-enforced against innocent code."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        path = _write(
            Path(td),
            """
def own_bfs(grid):
    for i in range(len(grid)):
        for j in range(len(grid[0])):
            for k in range(3):
                pass
""",
        )
        result = lint_module(path)
        assert result.ok is True  # warnings never fail the lint
        assert len(result.nesting_warnings) == 1
        assert "own_bfs" in result.nesting_warnings[0]


def test_two_level_nesting_does_not_warn():
    """Purpose: exactly 2 levels of nested loops (common, innocuous glue
    code -- e.g. building a 2D array) must NOT trigger the nesting warning,
    pinning the threshold at "more than 2", not "2 or more".
    Expected feedback: failure means the threshold is off-by-one, flooding
    every real adapter (which routinely builds 2D arrays) with false
    warnings."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        path = _write(
            Path(td),
            """
def build_array(h, w):
    out = []
    for r in range(h):
        row = []
        for c in range(w):
            row.append(0)
        out.append(row)
    return out
""",
        )
        result = lint_module(path)
        assert result.nesting_warnings == []


def test_nested_function_loops_are_measured_independently():
    """Purpose: a loop inside a NESTED function definition must not inflate
    the enclosing function's own nesting count -- each function is measured
    on its own (the nested one is separately visited and reported, so
    double-counting would produce a misleading depth number for the outer
    function).
    Expected feedback: failure means the outer function's reported depth is
    wrong, making the warning message point at the wrong code."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        path = _write(
            Path(td),
            """
def outer():
    for a in range(2):
        def inner():
            for b in range(2):
                for c in range(2):
                    for d in range(2):
                        pass
        inner()
""",
        )
        result = lint_module(path)
        names = {w.split(" ")[0] for w in result.nesting_warnings}
        assert "inner" in names
        assert "outer" not in names


def test_discover_adapter_paths_excludes_init_and_base():
    """Purpose: discover_adapter_paths() must scan the real adapters25/
    package and exclude __init__.py and base.py (the two files that are not
    themselves quarantined adapters).
    Expected feedback: failure means either the real adapter directory
    isn't found (breaking `uv run python scripts/adapters25_lint.py` with
    no args) or the exclusion list is wrong, causing base.py's legitimate
    arcengine import to be mis-flagged as a violation."""
    paths = discover_adapter_paths()
    names = {p.name for p in paths}
    assert "__init__.py" not in names
    assert "base.py" not in names
    assert "m0r0.py" in names
    assert "lp85.py" in names
    assert "su15.py" in names


def test_real_m0r0_adapter_passes_the_lint():
    """Purpose: regression pin -- the actual shipped m0r0 adapter must have
    zero import violations under the real whitelist, proving the quarantine
    contract is satisfiable in practice, not just in a synthetic example.
    Expected feedback: failure means the m0r0 adapter (or the lint's
    whitelist) drifted out of sync with the quarantine rules."""
    path = _REPO_ROOT / "src" / "admorphiq" / "adapters25" / "m0r0.py"
    result = lint_module(path)
    assert result.import_violations == []


def test_real_lp85_adapter_passes_the_lint():
    """Purpose: regression pin -- the actual shipped lp85 adapter (the
    click-driven sibling of m0r0's movement adapter) must ALSO have zero
    import violations, proving the quarantine contract holds across a
    second, differently-shaped adapter, not just the first one written.
    Expected feedback: failure means the lp85 adapter (or the lint's
    whitelist) drifted out of sync with the quarantine rules."""
    path = _REPO_ROOT / "src" / "admorphiq" / "adapters25" / "lp85.py"
    result = lint_module(path)
    assert result.import_violations == []


def test_real_su15_adapter_passes_the_lint():
    """Purpose: regression pin -- the actual shipped su15 adapter (the
    vacuum-merge sibling, the first non-trivial mechanic of the three) must
    ALSO have zero import violations, proving the quarantine contract holds
    even for an adapter with its own role-assignment heuristics (HUD-band
    detection, scattered-color exclusion, same-color pairing).
    Expected feedback: failure means the su15 adapter (or the lint's
    whitelist) drifted out of sync with the quarantine rules."""
    path = _REPO_ROOT / "src" / "admorphiq" / "adapters25" / "su15.py"
    result = lint_module(path)
    assert result.import_violations == []
