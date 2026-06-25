"""Tests for the two karpathywiki-inspired wiki_lint checks added in the
2026-06-25 health-scan upgrade: missing index summary + duplicate titles.

These are durable contract tests — they pin the invariant that the lint's
`missing_summary` flag predicts exactly the pages `generate_wiki_index.py`
would render as a bare-type catalog line, and that `duplicate_titles`
fires only on a genuine normalized-H1 collision (not on the intended
concept/game_type/strategy facet split).
"""

from __future__ import annotations

from pathlib import Path

import scripts.wiki_lint as wl


def _write(wiki_dir: Path, rel: str, text: str) -> Path:
    p = wiki_dir / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_index_summary_source_prefers_blockquote_then_fm_then_type():
    """Purpose: lock `index_summary_source` to the index generator's exact
    fallback order (blockquote → description → purpose → type → none).

    Expected feedback: a pass proves a lint flag mirrors what the index
    will actually print; a fail means lint and the generator have drifted
    and the flag no longer predicts a junk index line.
    """
    assert wl.index_summary_source("# T\n\n> one liner\n\nbody") == "blockquote"
    assert (
        wl.index_summary_source("---\ndescription: d\ntype: concept\n---\n# T")
        == "description"
    )
    assert (
        wl.index_summary_source("---\npurpose: p\ntype: concept\n---\n# T")
        == "purpose"
    )
    assert wl.index_summary_source("---\ntype: concept\n---\n# T\nbody") == "type"
    assert wl.index_summary_source("# T\n\njust body, no fm") == ""


def test_check_missing_summary_flags_bare_type_and_none(tmp_path, monkeypatch):
    """Purpose: prove `check_missing_summary` flags rich-but-undescribed
    pages (the real gf2_toggle_stencil defect) while leaving pages with a
    blockquote or description untouched.

    Expected feedback: pass means the lint catches index-skim degradation
    at authoring time; fail means substantive pages will keep emitting
    "concept"/"lesson" catalog lines unnoticed.
    """
    monkeypatch.setattr(wl, "WIKI_DIR", tmp_path)
    good = _write(tmp_path, "concepts/good.md", "---\ntype: concept\n---\n# Good\n\n> summary\n\nbody")
    described = _write(tmp_path, "concepts/desc.md", "---\ndescription: x\ntype: concept\n---\n# D\nbody")
    bare = _write(tmp_path, "concepts/bare.md", "---\ntype: concept\n---\n# Bare\n\nrich body but no summary line")
    none = _write(tmp_path, "concepts/none.md", "# None\n\nbody only, no frontmatter at all")

    findings = wl.check_missing_summary([good, described, bare, none])
    flagged = {f.page for f in findings}
    assert flagged == {"concepts/bare.md", "concepts/none.md"}
    assert all(f.kind == "missing_summary" for f in findings)


def test_check_duplicate_titles_collision_and_facet_split(tmp_path, monkeypatch):
    """Purpose: prove `check_duplicate_titles` fires on a real normalized-H1
    collision but stays silent on the intended concept/game_type/strategy
    facet split (distinct H1s).

    Expected feedback: pass means the dedup check is safe to run in CI
    without fighting the deliberate wiki schema; fail means it would
    false-positive on facet pages and erode trust in the lint.
    """
    monkeypatch.setattr(wl, "WIKI_DIR", tmp_path)
    # Facet split — distinct H1s, must NOT collide.
    c = _write(tmp_path, "concepts/merge_mechanic.md", "# Merge Mechanic\nbody")
    g = _write(tmp_path, "game_types/merge_puzzle.md", "# Merge Puzzle\nbody")
    s = _write(tmp_path, "strategies/frame_only/merge.md", "# Merge\nbody")
    # Genuine accidental duplicate — same H1 (case/space-insensitive).
    d1 = _write(tmp_path, "concepts/foo.md", "# Frame  Hashing\nbody")
    d2 = _write(tmp_path, "lessons/bar.md", "# frame hashing\nbody")

    findings = wl.check_duplicate_titles([c, g, s, d1, d2])
    flagged = {f.page for f in findings}
    assert flagged == {"concepts/foo.md", "lessons/bar.md"}
    assert all(f.kind == "duplicate_title" for f in findings)


def test_real_wiki_has_no_duplicate_titles():
    """Purpose: regression pin — the live `.wiki/wiki` currently has zero
    H1 collisions (verified 2026-06-25). This guards against a future page
    accidentally re-using an existing title.

    Expected feedback: a fail means someone added a page whose H1 duplicates
    an existing one — merge them or rename before committing.
    """
    pages = wl.discover_pages()
    findings = wl.check_duplicate_titles(pages)
    assert findings == [], f"unexpected H1 collisions: {[f.detail for f in findings]}"
