"""Phase 8 R7b — graph-based wiki retrieval (Karpathy pattern executed properly).

Before R7b: `WikiAgent` always read the same 7 pages (`_DEFAULT_PAGES`) up to an
8KB budget, ignoring the 63 other wiki pages and the `[[backlink]]` graph
edges the wiki doctrine insists on. Every env saw the same slice.

After R7b: each env gets a tailored slice. Discovery signals seed the walk
(directional movement → movement game type; action 6 + color toggle →
merge_mechanic concept; matching game title → games/<TITLE>.md). From each
seed, a BFS follows `[[link]]` edges, ordered by keyword relevance, until
the character budget is hit. The LLM's `wiki_needs` from the prior turn can
be force-included at the front of the queue so pages the LLM asked for are
always retrieved.

Pure-function design so each piece (link extraction, link resolution,
seed derivation, scoring, the BFS itself) is unit-testable without a live
filesystem and without an LLM.
"""

from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from typing import Any, Iterable

# Match [[link]] forms. The link text may contain slashes, dots, dashes,
# underscores. Obsidian also allows `[[target|alias]]`; we strip the alias.
_BACKLINK_RE = re.compile(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]")

# Match a YAML frontmatter block at the very top of a page: opening `---` on
# its own line, then any content (non-greedy), then a closing `---` line.
# Frontmatter is tooling metadata (wiki_index generator, schema governance)
# and must NOT be exposed to the LLM — Qwen 8B will imitate its key/value
# structure ("game_id", "status_v1", ...) instead of producing our response
# schema. Measured failure: 2026-04-21 R7 bench where 40/40 envs returned
# 0 levels because Qwen parroted games/<TITLE>.md's frontmatter as output.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)


def strip_frontmatter(text: str) -> str:
    """Remove a leading YAML frontmatter block from a wiki page.

    Only strips when the file begins with `---` on its own line — pages
    without frontmatter are returned unchanged.
    """
    return _FRONTMATTER_RE.sub("", text, count=1)


def extract_backlinks(text: str) -> list[str]:
    """Return distinct `[[...]]` targets in first-occurrence order.

    Preserves order so the BFS respects the prose flow of the page — earlier
    links in a page are usually more central to the topic than trailing ones.
    """
    seen: set[str] = set()
    out: list[str] = []
    for m in _BACKLINK_RE.finditer(text):
        target = m.group(1).strip()
        if not target or target in seen:
            continue
        seen.add(target)
        out.append(target)
    return out


def resolve_link(link: str, wiki_dir: Path) -> str | None:
    """Turn a `[[link]]` target into a wiki-relative path, or None on miss.

    Handles the common forms the wiki actually uses:
      "concepts/merge_mechanic"       -> "concepts/merge_mechanic.md"
      "concepts/merge_mechanic.md"    -> "concepts/merge_mechanic.md"
      "../architecture"               -> "architecture.md"
      "selector"                      -> "selector.md"
      "games/TN36"                    -> "games/TN36.md"
      "merge_mechanic" (basename only, unique match) -> "concepts/merge_mechanic.md"

    Returns None when the link cannot be resolved to exactly one file — we
    never guess between multiple candidates; ambiguity is a wiki-doctrine
    violation to fix at authoring time, not papered over at retrieval time.
    """
    wiki_dir = Path(wiki_dir)
    raw = link.strip().lstrip("/")
    if not raw:
        return None

    # Strip `../` prefix — wiki is flat enough that we resolve relative to root.
    while raw.startswith("../"):
        raw = raw[3:]

    candidates: list[str] = []
    if raw.endswith(".md"):
        candidates.append(raw)
    else:
        candidates.append(raw + ".md")
        candidates.append(raw + "/index.md")

    for cand in candidates:
        rel = Path(cand).as_posix()
        if (wiki_dir / rel).is_file():
            return rel

    # Basename fallback: single-match by filename only
    base = Path(raw).name
    if not base.endswith(".md"):
        base = base + ".md"
    matches = list(wiki_dir.rglob(base))
    if len(matches) == 1:
        return matches[0].relative_to(wiki_dir).as_posix()
    return None


def derive_seed_pages(report: Any) -> list[str]:
    """Map a DiscoveryReport to a deterministic, ordered seed-page list.

    Order matters: the first pages returned are the first the LLM sees, and
    seed pages usually saturate the char budget before the backlink walk
    runs (R23-14B retrieval audit) — so a page that lands late may be
    truncated or never read.

    B2 (round 16) tried front-loading env-specific seeds before the generic
    prose. The 2026-06-25 14B bench REGRESSED (-6 levels vs the R23 14B
    reference; `click_select_move` picks 12→0, `click_toggle_detect` 4→19),
    so the reorder was REVERTED. The original order below is the proven one:
    decision_tree, then the failure playbook + generic dispatch prose, then
    env-specific seeds appended last. See `.omc/rounds/round_016/notes.md`
    and `lessons/seed_reorder_regression_20260625.md` for the measurement.
    architecture.md: "changing the order requires re-measuring classification
    accuracy" — the bench did, and front-loading lost.
    """
    seeds: list[str] = [
        # Compact dispatch rules — first so 8B/14B sees them before
        # attention degrades on longer prose pages.
        "llm_context/decision_tree.md",
        # R24 (2026-05-06): one-page lookup of every plan-fn's
        # Falsification Signature → Next-Best. Pulled into seeds
        # because the standard backlink walk never reaches it (seeds
        # alone saturate the 16K budget; see R23-14B retrieval audit).
        # ~6K chars; sized to fit alongside selector + decision_tree.
        "debug/plan_failure_signatures.md",
        "selector.md",
        "reasoning/frame_to_strategy_chain.md",
        "reasoning/discovery_phase.md",
    ]
    avail = [a for a in (report.available_actions or []) if a not in (0, 7)]
    has_click = 6 in avail
    has_movement_actions = any(1 <= a <= 4 for a in avail)
    dir_map = report.dir_map or {}

    # Game-type seeds driven by probe signature
    if dir_map or has_movement_actions:
        if has_click:
            seeds.append("game_types/hybrid.md")
        else:
            seeds.append("game_types/movement.md")
    elif has_click:
        seeds.append("game_types/click.md")

    topology = getattr(report, "change_topology", "") or ""
    if topology == "color_toggle":
        seeds.append("concepts/merge_mechanic.md")
    elif topology == "level_transition":
        seeds.append("game_types/transform.md")
    elif topology == "sprite_move":
        seeds.append("game_types/movement.md")

    # Title-match seed: games/<TITLE>.md if present
    title = (report.game_title or "").upper()
    if title and title != "UNKNOWN":
        seeds.append(f"games/{title}.md")

    return seeds


def derive_keywords(report: Any) -> set[str]:
    """Extract lowercase keywords from the DiscoveryReport for link scoring.

    Intentionally small — 5-10 terms max — so scoring is fast and signal-
    rich rather than diluted by every feature name.
    """
    kw: set[str] = set()
    avail = [a for a in (report.available_actions or []) if a not in (0, 7)]
    if 6 in avail:
        kw.add("click")
    if any(1 <= a <= 4 for a in avail):
        kw.add("movement")
    if report.dir_map:
        kw.add("movement")
    topology = getattr(report, "change_topology", "") or ""
    if topology and topology != "unknown":
        kw.add(topology)
    title = (report.game_title or "").lower()
    if title and title != "unknown":
        kw.add(title)
    return kw


def score_link(target: str, keywords: set[str]) -> int:
    """Rank a link target by keyword overlap + directory priority.

    Higher = retrieved sooner. Reasoning/concept/lesson pages get a small
    boost because they carry cross-game abstractions that are more likely
    to help a never-seen-before env than a specific games/<TITLE> page.
    """
    target_l = target.lower()
    score = 0
    for kw in keywords:
        if kw in target_l:
            score += 2
    if target_l.startswith(("reasoning/", "concepts/", "lessons/")):
        score += 1
    return score


class GraphRetriever:
    """BFS walk over the wiki's `[[backlink]]` graph, budgeted by characters.

    Usage:
        retriever = GraphRetriever(Path(".wiki/wiki"))
        context, pages = retriever.retrieve(report)

    The `pages` list is the ordered set of wiki paths actually included in
    `context` (useful for traces and for honoring the R7c prompt's rule
    that the LLM cite only pages it read).
    """

    def __init__(self, wiki_dir: Path) -> None:
        self.wiki_dir = Path(wiki_dir)
        # R23-14B observability (2026-05-06): expose per-page char counts so
        # callers (WikiAgent.run) can emit them into the trace. Useful for
        # diagnosing retrieval-budget saturation. Repopulated each retrieve()
        # call.
        self._last_page_sizes: list[tuple[str, int]] = []

    def retrieve(
        self,
        report: Any,
        wiki_needs: Iterable[str] | None = None,
        budget_chars: int = 8000,
    ) -> tuple[str, list[str]]:
        seeds: list[str] = []
        # Requested pages from the LLM go first — they are the strongest signal
        # for what the next turn should see.
        if wiki_needs:
            seeds.extend(wiki_needs)
        seeds.extend(derive_seed_pages(report))

        keywords = derive_keywords(report)
        visited: set[str] = set()
        queue: deque[str] = deque(seeds)
        pages: list[tuple[str, str]] = []
        total = 0

        # The final context is `"\n\n".join(chunks)`, so each chunk after the
        # first also contributes 2 characters of joiner to the rendered length.
        # `total` tracks rendered length including those joiners so the budget
        # cap is honored by the concatenated string, not just the raw chunks.
        joiner_len = 2
        while queue and total < budget_chars:
            raw = queue.popleft()
            resolved = resolve_link(raw, self.wiki_dir)
            if not resolved or resolved in visited:
                continue
            visited.add(resolved)
            path = self.wiki_dir / resolved
            try:
                content = path.read_text()
            except OSError:
                continue
            content = strip_frontmatter(content)
            chunk = f"--- {resolved} ---\n{content}"
            prefix = joiner_len if pages else 0
            if total + prefix + len(chunk) > budget_chars:
                chunk = chunk[: max(0, budget_chars - total - prefix)]
                if not chunk:
                    break
            pages.append((resolved, chunk))
            total += prefix + len(chunk)
            if total >= budget_chars:
                break
            # Enqueue outbound links, ordered by score (descending)
            outbound = extract_backlinks(content)
            scored = sorted(
                ((tgt, score_link(tgt, keywords)) for tgt in outbound),
                key=lambda t: -t[1],
            )
            for target, _ in scored:
                if target not in visited:
                    queue.append(target)

        formatted = "\n\n".join(chunk for _, chunk in pages)
        self._last_page_sizes = [(p, len(chunk)) for p, chunk in pages]
        return formatted, [p for p, _ in pages]
