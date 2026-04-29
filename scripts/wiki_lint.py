"""Periodic wiki health check (Karpathy LLM-Wiki §6.3).

Walks `.wiki/wiki/**/*.md` and surfaces:

  1. Orphan pages — markdown pages with zero inbound `[[backlinks]]`
     from any other wiki page.
  2. Missing cross-refs — `[[link]]` targets that don't resolve to an
     actual file in the wiki.
  3. Stale claims — game pages whose `status_v1` / `status_v2`
     contradict the latest `scripts/regression_baseline.json`.
  4. Plan-fn pages missing R23c runtime-consumable fields
     (Observable Signature / Falsification Signature / Tunable
     Parameters / Next-Best).

Output:

  - human-readable markdown report on stdout
  - machine-readable JSON at `scripts/wiki_lint_report.json`

Exit codes:

  0  no findings
  1  findings exist (any of orphan / missing / stale / R23c gap)
  2  CLI / IO error

Intended cadence: every 3-5 rounds, not every commit. Schema is in
`.wiki/schema.md` § "Maintenance rules" + new R23c sections.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = REPO_ROOT / ".wiki" / "wiki"
DEFAULT_REPORT = REPO_ROOT / "scripts" / "wiki_lint_report.json"
REGRESSION_BASELINE = REPO_ROOT / "scripts" / "regression_baseline.json"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
LINK_RE = re.compile(r"\[\[([^\]]+?)\]\]")

R23C_SECTIONS = [
    "## Observable Signature",
    "## Falsification Signature",
    "## Tunable Parameters",
    "## Next-Best",
]


@dataclass
class LintFinding:
    kind: str
    page: str
    detail: str


@dataclass
class LintReport:
    orphans: list[str] = field(default_factory=list)
    missing_xrefs: list[LintFinding] = field(default_factory=list)
    stale_claims: list[LintFinding] = field(default_factory=list)
    r23c_gaps: list[LintFinding] = field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(
            self.orphans or self.missing_xrefs or self.stale_claims or self.r23c_gaps
        )

    def to_dict(self) -> dict:
        return {
            "orphans": list(self.orphans),
            "missing_xrefs": [
                {"page": f.page, "detail": f.detail} for f in self.missing_xrefs
            ],
            "stale_claims": [
                {"page": f.page, "detail": f.detail} for f in self.stale_claims
            ],
            "r23c_gaps": [
                {"page": f.page, "detail": f.detail} for f in self.r23c_gaps
            ],
        }


def parse_frontmatter(text: str) -> dict[str, str]:
    fm: dict[str, str] = {}
    m = FRONTMATTER_RE.match(text)
    if not m:
        return fm
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


METALINGUISTIC = frozenset({"backlinks", "link", "page"})


def resolve_link(target: str, source: Path) -> Path | None | str:
    """Resolve `[[target]]` against the source page's directory and
    fall back to wiki root. Strips ``.md`` suffix and trailing slashes.

    Returns:
      - `Path` when the link resolves to an existing file.
      - `None` when the link is real but unresolved.
      - The string ``"skip"`` when the link is a known false positive
        (template placeholder, metalinguistic term, etc.) and should
        not be surfaced as a missing-xref finding.
    """
    cleaned = target.strip().split("|", 1)[0].split("#", 1)[0].strip()
    if not cleaned:
        return "skip"
    if "<" in cleaned or ">" in cleaned:
        return "skip"  # template placeholder e.g. [[games/<game>]]
    if cleaned.lower() in METALINGUISTIC:
        return "skip"
    if cleaned.endswith("/"):
        return "skip"  # directory-shaped link, intentional
    if not cleaned.endswith(".md"):
        cleaned += ".md"
    candidates = [
        (source.parent / cleaned).resolve(),
        (WIKI_DIR / cleaned).resolve(),
        (WIKI_DIR.parent / cleaned).resolve(),  # raw/... lives under .wiki/
    ]
    for c in candidates:
        if c.exists() and c.is_relative_to(REPO_ROOT):
            return c
    return None


def discover_pages() -> list[Path]:
    return sorted(p for p in WIKI_DIR.rglob("*.md") if p.name != "index.md")


def collect_links(page: Path) -> list[str]:
    text = page.read_text()
    return [m.group(1) for m in LINK_RE.finditer(text)]


def check_orphans(pages: list[Path]) -> list[str]:
    """A page is an orphan when no other wiki page links to it.

    `index.md`, `log.md`, `selector.md`, `architecture.md` are
    intentionally landing pages and excluded from the orphan
    check — they're discovered via the directory walk, not via
    backlinks.
    """
    landing = {"log.md", "selector.md", "architecture.md"}
    inbound: dict[Path, set[Path]] = {p: set() for p in pages}
    for src in pages:
        for raw in collect_links(src):
            if raw.startswith("../"):
                continue  # raw/ link, not a wiki page
            tgt = resolve_link(raw, src)
            if tgt is None or tgt == "skip":
                continue
            if isinstance(tgt, Path) and tgt in inbound:
                inbound[tgt].add(src)
    orphans: list[str] = []
    for p, sources in inbound.items():
        rel = p.relative_to(WIKI_DIR)
        if rel.name in landing:
            continue
        if not sources:
            orphans.append(str(rel))
    return sorted(orphans)


def check_missing_xrefs(pages: list[Path]) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for src in pages:
        for raw in collect_links(src):
            if raw.startswith("../"):
                continue
            tgt = resolve_link(raw, src)
            if tgt == "skip":
                continue
            if tgt is None:
                rel = src.relative_to(WIKI_DIR)
                findings.append(
                    LintFinding(
                        kind="missing_xref",
                        page=str(rel),
                        detail=f"unresolved [[{raw}]]",
                    )
                )
    return findings


def check_stale_claims(pages: list[Path]) -> list[LintFinding]:
    if not REGRESSION_BASELINE.exists():
        return []
    try:
        data = json.loads(REGRESSION_BASELINE.read_text())
    except json.JSONDecodeError:
        return []
    by_title_baseline: dict[str, int] = {}
    for game_id, info in data.get("by_game_id", {}).items():
        title = info.get("title", "").upper()
        levels = int(info.get("levels", 0))
        if title:
            by_title_baseline[title] = max(by_title_baseline.get(title, 0), levels)
    findings: list[LintFinding] = []
    for page in pages:
        if not page.is_relative_to(WIKI_DIR / "games"):
            continue
        fm = parse_frontmatter(page.read_text())
        title = page.stem.upper()
        baseline_levels = by_title_baseline.get(title)
        if baseline_levels is None:
            continue
        status_v1 = fm.get("status_v1", "")
        if "/" not in status_v1:
            continue
        try:
            claimed = int(status_v1.split("/", 1)[0].strip())
        except ValueError:
            continue
        if claimed > baseline_levels:
            rel = page.relative_to(WIKI_DIR)
            findings.append(
                LintFinding(
                    kind="stale_claim",
                    page=str(rel),
                    detail=f"frontmatter status_v1={claimed} but regression baseline shows {baseline_levels}",
                )
            )
    return findings


def check_r23c_gaps(pages: list[Path]) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for page in pages:
        if not page.is_relative_to(WIKI_DIR / "strategies" / "frame_only"):
            continue
        text = page.read_text()
        missing = [s for s in R23C_SECTIONS if s not in text]
        if missing:
            rel = page.relative_to(WIKI_DIR)
            findings.append(
                LintFinding(
                    kind="r23c_gap",
                    page=str(rel),
                    detail=f"missing sections: {', '.join(missing)}",
                )
            )
    return findings


def render_report(report: LintReport) -> str:
    lines: list[str] = ["# Wiki Lint Report", ""]
    if not report.has_findings:
        lines.append("No findings — wiki is healthy.")
        return "\n".join(lines)
    if report.orphans:
        lines.append(f"## Orphan pages ({len(report.orphans)})")
        lines.append("")
        for o in report.orphans:
            lines.append(f"- `{o}`")
        lines.append("")
    if report.missing_xrefs:
        lines.append(f"## Missing cross-refs ({len(report.missing_xrefs)})")
        lines.append("")
        for f in report.missing_xrefs:
            lines.append(f"- `{f.page}` — {f.detail}")
        lines.append("")
    if report.stale_claims:
        lines.append(f"## Stale claims ({len(report.stale_claims)})")
        lines.append("")
        for f in report.stale_claims:
            lines.append(f"- `{f.page}` — {f.detail}")
        lines.append("")
    if report.r23c_gaps:
        lines.append(f"## R23c runtime-field gaps ({len(report.r23c_gaps)})")
        lines.append("")
        for f in report.r23c_gaps:
            lines.append(f"- `{f.page}` — {f.detail}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=DEFAULT_REPORT,
        help="JSON report output path",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="suppress markdown report on stdout",
    )
    args = parser.parse_args()

    if not WIKI_DIR.exists():
        print(f"wiki dir not found: {WIKI_DIR}", file=sys.stderr)
        return 2

    pages = discover_pages()
    report = LintReport(
        orphans=check_orphans(pages),
        missing_xrefs=check_missing_xrefs(pages),
        stale_claims=check_stale_claims(pages),
        r23c_gaps=check_r23c_gaps(pages),
    )

    args.json_out.write_text(json.dumps(report.to_dict(), indent=2))
    if not args.quiet:
        print(render_report(report))

    return 1 if report.has_findings else 0


if __name__ == "__main__":
    sys.exit(main())
