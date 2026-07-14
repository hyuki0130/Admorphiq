"""Packaging lint for the R58 EXPLANATION-layer runtime artifacts.

Mirrors ``scripts/adapters25_lint.py``'s quarantine-enforcement shape, but
for ``src/admorphiq/explanation/`` (schemas, playbooks, worked examples,
and the protocol module) instead of ``adapters25/``. Per
``docs/r58_codex_explanation_layer_20260715.md`` §1 ("Add a packaging lint
that rejects runtime artifacts containing public game IDs/titles, adapter
imports, absolute coordinates, fixed palettes, or provenance text"), every
file under the runtime package must be safe to ship to Kaggle: nothing in
it should let the offline model infer which of the 25 PUBLIC preview games
produced a playbook or worked example, since that identity never
transfers to the 110 PRIVATE hidden games it actually has to solve.

Five text-based checks, run over every file (schemas/playbooks/examples are
JSON/YAML/JSONL, not Python, so this is regex-based rather than AST-based
like the adapters25 lint):

1. **game_id_or_title** — any of the 25 known public game ids (whole-word,
   case-insensitive: ``ar25``, ``bp35``, ... ``wa30``) appearing anywhere.
2. **adapter_import** — the substring ``adapters25`` (the quarantined
   public-game-derived solver package; runtime artifacts must never
   reference it, even in a comment).
3. **absolute_coordinate** — a bare ``(row, col)``-shaped pixel coordinate
   pair. Runtime artifacts reference spatial state only via harness-owned
   observation HANDLES (``cell:12``, ``mask:4``, ...), never literal
   coordinates — a literal pair is a strong signal that a real board
   position leaked in from adapter work.
4. **fixed_palette** — a bracketed list of four or more small integers
   (``[3, 7, 9, 12]``-shaped), the signature of a hardcoded colour palette.
5. **provenance_text** — narrative phrases that only make sense as
   commentary on how a specific game's mechanic was discovered (e.g.
   "verified from source", "sprite tag") rather than a game-agnostic
   protocol description.

All five are HEURISTICS, not a proof of safety — see each check's
docstring for known limitations. They are conservative enough that this
package's own shipped artifacts must pass with zero violations; a seeded
violation (e.g. injecting a game id into a copy of a real file) must be
caught, which is what ``tests/test_explanation_protocol.py`` pins.

Usage:
  uv run python scripts/explanation_lint.py               # lint every runtime file
  uv run python scripts/explanation_lint.py path/to/x.yaml # lint specific files
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXPLANATION_DIR = _REPO_ROOT / "src" / "admorphiq" / "explanation"

# The 25 ARC-AGI-3 public preview game ids (see environment_files/, .wiki/wiki/games/).
_GAME_IDS = [
    "ar25", "bp35", "cd82", "cn04", "dc22", "ft09", "g50t", "ka59", "lf52",
    "lp85", "ls20", "m0r0", "r11l", "re86", "s5i5", "sb26", "sc25", "sk48",
    "sp80", "su15", "tn36", "tr87", "tu93", "vc33", "wa30",
]
_GAME_ID_RE = re.compile(r"\b(" + "|".join(_GAME_IDS) + r")\b", re.IGNORECASE)
_ADAPTER_IMPORT_RE = re.compile(r"adapters25")
_ABS_COORD_RE = re.compile(r"\(\s*\d{1,3}\s*,\s*\d{1,3}\s*\)")
_FIXED_PALETTE_RE = re.compile(r"\[\s*\d{1,2}\s*(?:,\s*\d{1,2}\s*){3,}\]")
_PROVENANCE_PHRASES = [
    "verified from source",
    "sprite tag",
    "sprite_tag",
    "internal variable",
    "internal state",
    "source-labeled",
    "source read",
    "hardcoded",
]


@dataclass
class LintResult:
    path: Path
    violations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def _check_game_ids(text: str) -> list[str]:
    """Whole-word, case-insensitive match against the 25 public game ids.

    LIMITATION: purely lexical — a game id embedded inside an unrelated
    longer identifier that still hits a word boundary (rare, given these
    ids are 4-char alphanumeric codes) would false-positive; conversely, a
    game TITLE prose form (not in ``_GAME_IDS``) would be missed. Good
    enough for a quarantine gate whose corpus is small and hand-written.
    """
    hits = sorted({m.group(0).lower() for m in _GAME_ID_RE.finditer(text)})
    return [f"game_id_or_title: {hit!r}" for hit in hits]


def _check_adapter_import(text: str) -> list[str]:
    if _ADAPTER_IMPORT_RE.search(text):
        return ["adapter_import: references 'adapters25' (quarantined package)"]
    return []


def _check_absolute_coordinate(text: str) -> list[str]:
    """Flags a bare ``(N, N)`` pair anywhere in the file.

    LIMITATION: this is intentionally broad — the runtime artifacts in
    this package never need a literal coordinate pair (spatial state is
    always a handle), so any match is suspicious. A future playbook that
    legitimately needs small paired integers for something non-spatial
    would need an explicit exemption, not a pattern refinement here.
    """
    hits = _ABS_COORD_RE.findall(text)
    return [f"absolute_coordinate: {h!r}" for h in dict.fromkeys(hits)]


def _check_fixed_palette(text: str) -> list[str]:
    hits = _FIXED_PALETTE_RE.findall(text)
    return [f"fixed_palette: {h!r}" for h in dict.fromkeys(hits)]


def _check_provenance_text(text: str) -> list[str]:
    lowered = text.lower()
    return [f"provenance_text: {phrase!r}" for phrase in _PROVENANCE_PHRASES if phrase in lowered]


def lint_text(text: str) -> list[str]:
    violations: list[str] = []
    violations.extend(_check_game_ids(text))
    violations.extend(_check_adapter_import(text))
    violations.extend(_check_absolute_coordinate(text))
    violations.extend(_check_fixed_palette(text))
    violations.extend(_check_provenance_text(text))
    return violations


def lint_file(path: Path) -> LintResult:
    text = path.read_text(encoding="utf-8")
    return LintResult(path=path, violations=lint_text(text))


def lint_paths(paths: list[Path]) -> list[LintResult]:
    return [lint_file(p) for p in paths]


def discover_runtime_paths() -> list[Path]:
    """Every file under the runtime package, excluding bytecode caches and any
    build-only ``provenance/`` subtree (per the artifact tree in
    ``docs/r58_codex_explanation_layer_20260715.md`` §1 — none exists yet in
    v0, but the exclusion is here so adding one later doesn't silently break
    the lint's own intent)."""
    if not _EXPLANATION_DIR.exists():
        return []
    out = []
    for p in sorted(_EXPLANATION_DIR.rglob("*")):
        if not p.is_file():
            continue
        if "__pycache__" in p.parts:
            continue
        if "provenance" in p.parts:
            continue
        out.append(p)
    return out


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "paths",
        nargs="*",
        help="Files to lint (default: every runtime file under src/admorphiq/explanation/).",
    )
    return p


def main() -> int:
    args = _build_parser().parse_args()
    paths = [Path(m) for m in args.paths] if args.paths else discover_runtime_paths()
    if not paths:
        print("No explanation-layer runtime files found.")
        return 0

    failed = False
    for result in lint_paths(paths):
        rel = result.path.relative_to(_REPO_ROOT) if result.path.is_relative_to(_REPO_ROOT) else result.path
        if result.ok:
            print(f"{rel}: ok")
            continue
        failed = True
        print(f"{rel}:")
        for v in result.violations:
            print(f"  FAIL {v}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
