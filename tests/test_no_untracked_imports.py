"""A committed file must not import a module the repository does not track.

Purpose: pin the invariant that a clean checkout can run everything it ships. A lazily-imported
module — one imported inside a function — leaves the importing module loading FINE on a clean
checkout and failing only when that code path is invoked, which is the kind of breakage nobody
finds for weeks.

Expected feedback: a failure names both files. Either commit the missing module, or remove the
import from the committed one. MEASURED 2026-08-27: this caught two real instances within an
hour of each other, and the second was created by the fix for the first — a probe was committed
while the tool it imports was deliberately held back.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess

import pytest


def _tracked() -> set[str] | None:
    """Every file git tracks, or None where there is no repository to ask.

    ⛔ `scripts/ptest.sh` runs the suite from a `git archive` SNAPSHOT on ceph-build (rule 7l — a
    measurement must not write to a shared path), and a snapshot is not a repository. `git ls-files`
    exits non-zero there, `check=True` raised, and this test reported RED on every box run for a
    reason that has nothing to do with the invariant it defends. Measured 2026-08-30, and two agents
    each spent time deciding whether it was their change.

    ⚠️ SKIPPING is right here and would be wrong for most guards: this one compares committed files
    against git's own index, so without an index there is no question to answer. A guard that cannot
    see must say so rather than fail (rule 7bm) — and rather than pass (rule 7q).
    """
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return set(out.stdout.split())


def test_no_committed_file_imports_an_untracked_module() -> None:
    """Purpose: prove every `admorphiq.*` import in a tracked file resolves to a tracked file.

    Expected feedback: failing means a clean checkout carries a script whose import path is
    missing, and it will not be noticed until someone runs exactly that path.
    """
    tracked = _tracked()
    if tracked is None:
        pytest.skip("no git index here (a ptest.sh snapshot) — nothing to compare against")
    offenders: list[str] = []
    for name in sorted(tracked):
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse(pathlib.Path(name).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
            continue
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            if not module or not module.startswith("admorphiq."):
                continue
            path = "src/" + module.replace(".", "/") + ".py"
            if path not in tracked and pathlib.Path(path).exists():
                offenders.append(f"{name} imports {module} but {path} is untracked")
    assert not offenders, "committed files importing untracked modules:\n  " + "\n  ".join(
        sorted(set(offenders))
    )
