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


def _tracked() -> set[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    return set(out.stdout.split())


def test_no_committed_file_imports_an_untracked_module() -> None:
    """Purpose: prove every `admorphiq.*` import in a tracked file resolves to a tracked file.

    Expected feedback: failing means a clean checkout carries a script whose import path is
    missing, and it will not be noticed until someone runs exactly that path.
    """
    tracked = _tracked()
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
