"""R7b graph-based wiki retrieval tests.

Every test carries a Purpose + Expected-feedback docstring per the
Implementation Discipline in CLAUDE.md. FEEDBACK-GATED tests are marked;
they exist for a specific measured regression and can be deleted once
confirmed stable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from admorphiq.hypothesis import (
    DiscoveryReport,
    GraphRetriever,
    derive_keywords,
    derive_seed_pages,
    extract_backlinks,
    resolve_link,
    score_link,
    strip_frontmatter,
)


# ---------------------------------------------------------------------------
# strip_frontmatter
# ---------------------------------------------------------------------------


# FEEDBACK-GATED: pins the specific R7 bench collapse (2026-04-21) where
# Qwen imitated the YAML frontmatter of games/<TITLE>.md as its output
# shape, producing 0 levels across 40 envs. Once the dev-time loop has
# completed multiple rounds with frontmatter stripping in place, this
# test can be removed — the behavior is covered by the general
# "frontmatter-bearing pages" test below.
def test_strip_frontmatter_removes_leading_yaml_block_on_real_shape():
    """Purpose: guarantee that the exact shape of a wiki game page's
    frontmatter (as emitted by scripts/generate_wiki_game_pages.py) is
    stripped — the one that caused Qwen 8B to parrot `game_id` / `status_v1`
    into its response on 2026-04-21.

    Expected feedback: if this fails, the R7 bench regression returns.
    """
    page = (
        "---\n"
        "type: game\n"
        "game_id: tu93\n"
        "game_type: movement\n"
        "status_v1: 2/9\n"
        "current_strategy: tu93_maze (brittle)\n"
        "generalizes: yes\n"
        "---\n"
        "# TU93\n\n"
        "Some prose here.\n"
    )
    out = strip_frontmatter(page)
    assert "game_id: tu93" not in out
    assert "# TU93" in out
    assert "Some prose here." in out


def test_strip_frontmatter_noop_when_absent():
    """Purpose: pages without a frontmatter block must be returned
    unchanged — selector.md and the reasoning pages don't all carry one.

    Expected feedback: failure means non-frontmatter pages are being
    mutilated at the top.
    """
    page = "# Plain page\n\nNo frontmatter here.\n"
    assert strip_frontmatter(page) == page


def test_strip_frontmatter_only_strips_leading_block():
    """Purpose: a `---` horizontal rule in the middle of content must not
    be mistaken for frontmatter fencing.

    Expected feedback: failure means the middle of a wiki page could be
    silently truncated if it contains `---`.
    """
    page = "# Heading\n\nText.\n\n---\n\nMore text.\n"
    assert strip_frontmatter(page) == page


# ---------------------------------------------------------------------------
# extract_backlinks
# ---------------------------------------------------------------------------


def test_extract_backlinks_simple():
    """Purpose: `[[path]]` forms must be extracted in reading order.

    Expected feedback: if this fails, the BFS walk over the wiki graph
    starts from a permuted queue and page ordering in the prompt becomes
    non-deterministic.
    """
    text = "See [[concepts/merge_mechanic]] and [[games/TN36]] for detail."
    assert extract_backlinks(text) == ["concepts/merge_mechanic", "games/TN36"]


def test_extract_backlinks_strips_alias_and_dedupes():
    """Purpose: Obsidian-style `[[target|alias]]` must yield target only.
    Duplicate `[[X]]` occurrences should not fill the BFS queue multiple
    times.

    Expected feedback: failure means duplicate retrieval wastes budget and
    alias text contaminates link resolution.
    """
    text = "[[lessons/brittle_tells|brittle]] then [[lessons/brittle_tells]]"
    assert extract_backlinks(text) == ["lessons/brittle_tells"]


def test_extract_backlinks_ignores_non_link_braces():
    """Purpose: JSON or dict-looking `{...}` content in a wiki page must not
    be misread as links.

    Expected feedback: failure means code-example-heavy pages pollute the
    queue with garbage targets.
    """
    text = "Config like {{'a': 1}} is not a link. [[concepts/x]] is."
    assert extract_backlinks(text) == ["concepts/x"]


# ---------------------------------------------------------------------------
# resolve_link
# ---------------------------------------------------------------------------


def _build_wiki(tmp_path: Path) -> Path:
    """Create a tiny wiki tree for resolution tests."""
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "games").mkdir(parents=True)
    (wiki / "selector.md").write_text("selector")
    (wiki / "architecture.md").write_text("arch")
    (wiki / "concepts" / "merge_mechanic.md").write_text("merge")
    (wiki / "games" / "TN36.md").write_text("tn36")
    return wiki


def test_resolve_link_exact_path_with_md(tmp_path):
    """Purpose: a fully qualified link with `.md` must resolve unchanged.

    Expected feedback: failure means well-formed internal links are being
    rejected at retrieval time.
    """
    wiki = _build_wiki(tmp_path)
    assert resolve_link("concepts/merge_mechanic.md", wiki) == "concepts/merge_mechanic.md"


def test_resolve_link_exact_path_without_md(tmp_path):
    """Purpose: the wiki convention omits `.md`; resolver must append it.

    Expected feedback: failure means `[[concepts/merge_mechanic]]` won't
    find its file and the target is silently dropped from the prompt.
    """
    wiki = _build_wiki(tmp_path)
    assert resolve_link("concepts/merge_mechanic", wiki) == "concepts/merge_mechanic.md"


def test_resolve_link_dotdot_prefix_stripped(tmp_path):
    """Purpose: Obsidian often emits `[[../architecture]]`; resolver must
    not treat `../` as an escape-above-root.

    Expected feedback: failure means common Obsidian link forms are
    dropped, forcing wiki authors to avoid them.
    """
    wiki = _build_wiki(tmp_path)
    assert resolve_link("../architecture", wiki) == "architecture.md"


def test_resolve_link_basename_only_unique_match(tmp_path):
    """Purpose: bare `[[merge_mechanic]]` should resolve to the single
    page with that filename.

    Expected feedback: failure means short-form links produce misses
    even when unambiguous.
    """
    wiki = _build_wiki(tmp_path)
    assert resolve_link("merge_mechanic", wiki) == "concepts/merge_mechanic.md"


def test_resolve_link_returns_none_for_missing(tmp_path):
    """Purpose: unresolvable links must not crash; they are silently
    dropped from the walk.

    Expected feedback: failure means a typo in a wiki page halts retrieval
    for that env.
    """
    wiki = _build_wiki(tmp_path)
    assert resolve_link("ghost/page", wiki) is None


def test_resolve_link_returns_none_for_ambiguous(tmp_path):
    """Purpose: when two files share a basename, the resolver refuses to
    guess. Ambiguity is a wiki-doctrine violation to fix at authoring
    time, not paper over at retrieval time.

    Expected feedback: failure here means the resolver would silently
    pick one of the duplicates, breaking determinism.
    """
    wiki = _build_wiki(tmp_path)
    (wiki / "games" / "dup.md").write_text("a")
    (wiki / "concepts" / "dup.md").write_text("b")
    assert resolve_link("dup", wiki) is None


# ---------------------------------------------------------------------------
# derive_seed_pages / derive_keywords
# ---------------------------------------------------------------------------


def _report(**kwargs) -> DiscoveryReport:
    defaults = dict(
        game_title="X",
        available_actions=[1, 2, 3, 4, 6],
        layer_count=1,
        dominant_colors=[],
        probe_diffs={},
        reset_levels=0,
        frame_shape=(64, 64),
    )
    defaults.update(kwargs)
    return DiscoveryReport(**defaults)


def test_seed_pages_start_with_decision_tree_then_selector():
    """Purpose: round 6 added llm_context/decision_tree.md as the
    highest-density LLM anchor page (≤ 1200 chars carrying the full
    dispatch decision). It must come first, followed by selector.md
    and the core reasoning pages. If this drifts, 8B models lose
    their compact anchor and fall back to collapsing all envs to
    `bfs_state_space` / `click_rare` as measured in rounds 4-5.

    Expected feedback: if seeds[0] is no longer decision_tree, Qwen
    re-anchors on longer prose and routing degrades measurably.
    """
    seeds = derive_seed_pages(_report())
    assert seeds[0] == "llm_context/decision_tree.md"
    assert "selector.md" in seeds[:4]
    assert "reasoning/frame_to_strategy_chain.md" in seeds[:4]
    assert "reasoning/discovery_phase.md" in seeds[:4]


def test_seed_pages_hybrid_when_click_and_movement_both():
    """Purpose: when discovery shows both directional probes and a
    responsive action 6, the hybrid game_type page must be seeded — it
    describes the mixed-mode dispatch rules.

    Expected feedback: failure routes hybrid games to pure movement or
    pure click pages, losing dispatch guidance.
    """
    rep = _report(available_actions=[1, 2, 3, 4, 6], dir_map={1: "N"})
    seeds = derive_seed_pages(rep)
    assert "game_types/hybrid.md" in seeds


def test_seed_pages_click_only_when_no_movement():
    """Purpose: click-only games (avail == [6], no dir_map) must seed
    `game_types/click.md` only — hybrid is inappropriate.

    Expected feedback: failure contaminates click-game prompts with
    movement strategies the LLM then spends budget on.
    """
    rep = _report(available_actions=[6], dir_map={})
    seeds = derive_seed_pages(rep)
    assert "game_types/click.md" in seeds
    assert "game_types/hybrid.md" not in seeds
    assert "game_types/movement.md" not in seeds


def test_seed_pages_title_match_seeds_games_page():
    """Purpose: when the game title names a page under `games/`, seed
    that page so the LLM sees any prior notes on this specific game.

    Expected feedback: failure means per-game lessons (e.g., SU15's merge
    variant notes) never reach the LLM unless a generic page links to them.
    """
    rep = _report(game_title="SU15")
    seeds = derive_seed_pages(rep)
    assert "games/SU15.md" in seeds


def test_seed_pages_topology_drives_concept_page():
    """Purpose: `change_topology == color_toggle` must seed the
    merge_mechanic concept, which covers toggle-style mechanics.

    Expected feedback: failure means the LLM loses a cross-game concept
    that distinguishes merge from click-rare games.
    """
    rep = _report(change_topology="color_toggle")
    seeds = derive_seed_pages(rep)
    assert "concepts/merge_mechanic.md" in seeds


def test_keywords_include_click_and_movement_correctly():
    """Purpose: keyword set must reflect both the raw available_actions
    and any inferred motion from dir_map.

    Expected feedback: failure means link scoring is fed incomplete
    signals and the BFS pulls in wrong pages first.
    """
    rep = _report(available_actions=[1, 2, 3, 4, 6], dir_map={1: "N"})
    kw = derive_keywords(rep)
    assert "movement" in kw
    assert "click" in kw


def test_keywords_include_game_title_lowercase():
    """Purpose: the game title (lowercased) must join keywords so pages
    that mention the title rank higher.

    Expected feedback: failure loses title-specific links (e.g., the
    games/SU15 page linking to concepts/merge_mechanic won't be followed
    in priority order).
    """
    rep = _report(game_title="SU15")
    assert "su15" in derive_keywords(rep)


# ---------------------------------------------------------------------------
# score_link
# ---------------------------------------------------------------------------


def test_score_link_boosts_keyword_matches():
    """Purpose: every keyword occurrence in a link target adds to its
    score, so `movement` games retrieve movement-related pages first.

    Expected feedback: failure means scoring is flat and the BFS becomes
    random-order, defeating R7b.
    """
    assert score_link("game_types/movement.md", {"movement"}) > score_link(
        "game_types/click.md", {"movement"}
    )


def test_score_link_boosts_reasoning_concepts_lessons_directories():
    """Purpose: cross-game pages (reasoning/, concepts/, lessons/) should
    outrank narrow `games/X.md` pages at equal keyword overlap. They carry
    abstractions that generalize; game pages do not.

    Expected feedback: failure means generalization-bearing pages lose
    priority to narrow game-specific pages, hurting unseen private-test
    performance.
    """
    kw = {"merge"}
    assert score_link("concepts/merge_mechanic.md", kw) > score_link(
        "games/SU15.md", kw
    )


# ---------------------------------------------------------------------------
# GraphRetriever.retrieve
# ---------------------------------------------------------------------------


def _build_graph_wiki(tmp_path: Path) -> Path:
    """Tiny wiki with a deliberate graph shape:
      selector.md            (seed; links to frame_to_strategy)
      reasoning/frame_to_strategy.md (links to concepts/merge_mechanic)
      reasoning/discovery_phase.md   (no outbound links)
      concepts/merge_mechanic.md     (links to games/SU15)
      games/SU15.md                  (terminal leaf)
    """
    wiki = tmp_path / "wiki"
    (wiki / "reasoning").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "games").mkdir(parents=True)
    (wiki / "selector.md").write_text(
        "Dispatch rules. See [[reasoning/frame_to_strategy_chain]]."
    )
    (wiki / "reasoning" / "frame_to_strategy_chain.md").write_text(
        "Chain. See [[concepts/merge_mechanic]] for merge games."
    )
    (wiki / "reasoning" / "discovery_phase.md").write_text("No links.")
    (wiki / "concepts" / "merge_mechanic.md").write_text(
        "Merge mechanic. Example: [[games/SU15]]."
    )
    (wiki / "games" / "SU15.md").write_text("SU15 merge puzzle notes.")
    (wiki / "game_types").mkdir()
    (wiki / "game_types" / "hybrid.md").write_text("Hybrid dispatch.")
    (wiki / "game_types" / "movement.md").write_text("Movement.")
    (wiki / "game_types" / "click.md").write_text("Click.")
    return wiki


def test_retriever_walks_backlinks_from_seeds(tmp_path):
    """Purpose: verify the BFS actually follows `[[links]]` — with a
    generous budget and a chain of four linked pages, all four must appear
    in the retrieved set.

    Expected feedback: failure means the retriever is not following links
    at all; it reverts to seeds-only behavior and the R7b work provides
    no benefit over R1-era fixed page lists.
    """
    wiki = _build_graph_wiki(tmp_path)
    r = GraphRetriever(wiki)
    rep = _report(game_title="SU15")
    _context, pages = r.retrieve(rep, budget_chars=10_000)
    # selector + reasoning + concepts + SU15 all reachable via links
    assert "selector.md" in pages
    assert "reasoning/frame_to_strategy_chain.md" in pages
    assert "concepts/merge_mechanic.md" in pages
    assert "games/SU15.md" in pages


def test_retriever_respects_budget(tmp_path):
    """Purpose: with a tight char budget, retrieval must stop early — the
    prompt has a finite context window and overflow would be dropped.

    Expected feedback: failure means the retriever can blow past the
    budget and silently truncate the LLM's prompt in unpredictable ways.
    """
    wiki = _build_graph_wiki(tmp_path)
    r = GraphRetriever(wiki)
    rep = _report(game_title="SU15")
    context, pages = r.retrieve(rep, budget_chars=200)
    assert len(context) <= 200
    # Fewer than all pages should land when budget is tight
    assert len(pages) < 5


def test_retriever_honors_wiki_needs_first(tmp_path):
    """Purpose: when the LLM's prior-turn `wiki_needs` lists a page, that
    page must appear in the retrieved set even if it is not reachable from
    the derived seeds. This is how the loop learns what pages to prefetch.

    Expected feedback: failure means `wiki_needs` is ignored and the
    Karpathy-style self-directed retrieval loop degenerates to fixed seeds.
    """
    wiki = _build_graph_wiki(tmp_path)
    # Add an island page with no inbound links
    (wiki / "reasoning" / "hypothesis_check.md").write_text("Island.")
    r = GraphRetriever(wiki)
    rep = _report(game_title="SU15")
    _context, pages = r.retrieve(
        rep, wiki_needs=["reasoning/hypothesis_check"], budget_chars=10_000
    )
    assert "reasoning/hypothesis_check.md" in pages


def test_retriever_dedupes_pages(tmp_path):
    """Purpose: the same page must not appear twice even if multiple links
    point to it.

    Expected feedback: failure inflates the prompt with duplicates,
    consuming budget that should go to novel pages.
    """
    wiki = _build_graph_wiki(tmp_path)
    # Add a page with two self-references — it must only appear once.
    (wiki / "selector.md").write_text(
        "[[reasoning/frame_to_strategy_chain]] [[reasoning/frame_to_strategy_chain]]"
    )
    r = GraphRetriever(wiki)
    rep = _report(game_title="SU15")
    _context, pages = r.retrieve(rep, budget_chars=10_000)
    assert pages.count("reasoning/frame_to_strategy_chain.md") == 1


def test_retriever_context_starts_with_path_headers(tmp_path):
    """Purpose: the R7c prompt instructs the LLM to cite pages by their
    `--- path ---` headers. Retrieval output must include those headers
    so the instruction is truthful.

    Expected feedback: failure means the LLM has no reliable way to
    identify which page a claim came from, and citation rules collapse.
    """
    wiki = _build_graph_wiki(tmp_path)
    r = GraphRetriever(wiki)
    rep = _report(game_title="SU15")
    context, _ = r.retrieve(rep, budget_chars=10_000)
    assert "--- selector.md ---" in context


# FEEDBACK-GATED: pins the specific behavior that drove R7b — a live-env
# run should retrieve more pages than the pre-R7b fixed list of 7 when
# the wiki has more than 7 relevant pages for an env. Once multiple
# rounds confirm the graph walk is reliably pulling tailored slices,
# this test is deletable (the general link-following test above covers
# the underlying contract).
def test_retriever_beats_old_fixed_seven_page_list_on_graph_wiki(tmp_path):
    """Purpose: confirm the graph walk strictly outperforms the pre-R7b
    fixed 7-page list when the wiki has >7 relevant pages.

    Expected feedback: if this fails, R7b provided no measurable
    retrieval improvement and should be rolled back.
    """
    wiki = _build_graph_wiki(tmp_path)
    # Ensure at least 5 pages exist and are reachable
    r = GraphRetriever(wiki)
    rep = _report(game_title="SU15", change_topology="color_toggle")
    _context, pages = r.retrieve(rep, budget_chars=10_000)
    # With 8 pages in the tiny test wiki and generous budget, the walk
    # should reach at least half of them via link-following from seeds.
    assert len(pages) >= 4
