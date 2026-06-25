---
name: wiki-authoring
description: >-
  Author or edit Admorphiq's `.wiki/wiki/**/*.md` knowledge base so the OFFLINE
  Qwen reader (Kaggle, frozen, constrained-decode) retrieves it efficiently.
  Use whenever creating/editing any page under .wiki/wiki/, appending a round
  lesson, or adding a concept/strategy/debug/game page. This encodes the repo's
  own doctrine (.wiki/schema.md + scripts/wiki_lint.py) — NOT generic Obsidian
  syntax. The wiki is written by Claude Code at dev-time and only READ by Qwen
  at Kaggle-time; Qwen never writes it and has no skill/tool runtime.
---

# Wiki Authoring (Admorphiq dev-time)

## Audience model (read first — it drives every rule)

- **Writer = you (Claude Code), dev-time only.** Qwen does NOT write the wiki.
- **Reader = Qwen 3 8B Q4, Kaggle-time, offline, frozen.** It reads a
  ~8–16K-char slice assembled by `src/admorphiq/hypothesis/wiki_retrieval.py`
  (a custom BFS over `[[backlinks]]`, NOT Obsidian). It emits enum-bound JSON.
  It has no tool/skill harness, no internet, no vector DB.
- Consequence: pages are **retrieval fuel for a weak model**, not human notes.
  Every byte competes for an 8B attention budget that degrades past ~a few KB.

## The retriever you are writing for (`wiki_retrieval.py`)

1. **Frontmatter is stripped** before any page reaches Qwen
   (`strip_frontmatter`). So frontmatter costs zero runtime budget — but a
   reasoning fact placed there is INVISIBLE to Qwen. Put reasoning in prose.
2. **Seeds load first, in order**, then a `[[backlink]]` BFS fills the budget.
   Seeds usually saturate the budget, so deep backlink pages are often never
   read at runtime. Front-load signal; don't rely on a 3-hop link being seen.
3. **`[[link]]` resolution** (`resolve_link`): `[[concepts/x]]`,
   `[[../lessons/x]]`, `[[x]]` (unique basename) all resolve to `x.md`. A link
   that resolves to 0 or >1 files is dropped — and wastes a BFS queue slot.
4. **8B attention rule**: fewer, denser pages beat many shallow ones. Do not
   "cross-link aggressively" to maximize graph fanout for its own sake — link
   only where a reader genuinely needs the neighbor. Density > connectivity.

## Hard rules (a violation is a defect `scripts/wiki_lint.py` will flag)

1. **Frontmatter required**, `type:` first. Tooling-only — never the place for
   facts Qwen must reason over. (`schema.md` Frontmatter Policy, load-bearing.)
2. **One-sentence `>` blockquote summary immediately after the H1.** The index
   generator falls back to the bare `type` token without it → `missing_summary`
   lint finding, useless catalog line.
   - **Exception — runtime-seeded pages** (`llm_context/*`, and any page in
     `wiki_retrieval.derive_seed_pages`): use a `description:` FRONTMATTER field
     instead of a body blockquote. Frontmatter is stripped at runtime, so the
     summary feeds the index at ZERO Qwen-budget cost. A body blockquote on a
     seeded page wastes the char budget the page is trying to conserve.
3. **No dead `[[links]]`.** No `(planned)` placeholders, no `[[.../...]]`
   ellipses. Either the target page exists (link it) or it doesn't (write
   prose, no brackets). `missing_xrefs` lint finding otherwise.
4. **No orphans.** Every new page must get ≥1 inbound `[[link]]` from its
   natural parent in the SAME edit:
   - `games/<G>` ← its `game_types/<type>` Games Table (and peer games)
   - `game_types/<type>` ← `selector.md` and/or its instance `games/`
   - `concepts/<c>` ← the `game_types`/`strategies` that instantiate it
   - `lessons/<l>` ← the `strategies`/`games` the lesson is about
   - `strategies/frame_only/<s>` ← `selector.md` / `decision_tree.md`
   Landing pages (`index.md`, `log.md`, `selector.md`, `architecture.md`) are
   exempt — they're reached by directory walk, not backlinks.
5. **Per-page-type required sections** (`schema.md`):
   - games: Current Status, Observations, Mechanics Hypothesis, Solution
     Pattern, Notes/Refactor Plan, Lessons Learned, Related, Sources
   - game_types: Identifying Features, Discovery Protocol, Canonical Strategy,
     Games Table, Edge Cases, Related
   - concepts: Definition, Instantiating Games, Detection Heuristics
     (frame-only), Related Concepts, Related Games
   - lessons: Symptom, Root Cause, Prevention, Recovery, Falsification, Related
   - debug: Observable Symptom, Triage Steps, Likely Root Causes, Fix Recipes,
     When to Escalate, Related
   - reasoning: Input, Chain (numbered, decision points), Worked Examples (≥2),
     Common Pitfalls, Related
   - strategies: Applies When, Algorithm, Why It Generalizes (or fails), Games
     Cleared, Limitations, Related
6. **R23c runtime fields** on every `strategies/frame_only/*` and plan-fn /
   mechanic page (Qwen reads these to self-heal at runtime):
   `## Observable Signature`, `## Falsification Signature`,
   `## Tunable Parameters`, `## Next-Best`. Literal headers — `wiki_lint`
   `r23c_gaps` checks for them.
7. **Every page answers four questions** (`schema.md`): What is this? How did
   we arrive (provenance: `raw/*`, `src/…:line`, commit hash)? What related
   pages? What would falsify this?
8. **Never put `game_title` → strategy mappings in prose as routing rules** the
   way Python would. Titles are Kaggle-invisible. Routing knowledge goes in
   `selector.md` / `reasoning/frame_to_strategy_chain.md` keyed on observable
   frame signals, with the *why* (8B needs the reason).

## Per-round ingest ritual (schema.md §Ingest Ritual)

A round that touched `src/**` must fan out to the wiki — one finding usually
hits 10–15 pages. Minimum:
1. `log.md` — append `## [YYYY-MM-DD round RN]` (title + 2-3 lines + Pages
   touched + Provenance commit). Append-only.
2. `games/<G>.md` — provenance update for every game whose status changed.
3. `lessons/<topic>_<YYYYMMDD>.md` — new page for any falsifiable claim /
   regression diagnosis / architectural correction.
4. `concepts/<c>.md` — new page for any reusable abstraction introduced.
5. `strategies/frame_only/<fn>.md` — for any new/changed plan fn (with R23c).
6. `debug/<symptom>_playbook.md` — for any reproducible failure mode.
7. Regenerate `index.md`.

Also refile dev-time exploration (`scripts/probe_*.py` results, trace
analyses): a good answer becomes a page. Leaving it in `/tmp` or scrollback is
the anti-pattern — cache is not memory.

## Verify before claiming done (always run)

```bash
uv run python scripts/generate_wiki_index.py      # regenerate catalog
uv run python scripts/wiki_lint.py                # expect 0 findings:
#   orphans / missing_xrefs / stale_claims / r23c_gaps / missing_summary / duplicate_titles
uv run pytest tests/test_wiki_lint.py tests/test_wiki_retrieval.py -q
```

A retrieval-behavior change (seed list, budget, seed order in
`wiki_retrieval.py`) is NOT done at lint-green — it changes what Qwen sees and
MUST pass a `scripts/run_wiki_agent.py` bench + `scripts/regression_gate.py`
before the baseline moves. Lint/tests gate hygiene; the bench gates routing.

## What this skill is NOT

- Not kepano's `obsidian-skills` (callouts / `.base` / canvas). Our retriever
  parses none of those — they'd be noise in Qwen's context. Only `[[backlinks]]`
  + plain markdown + frontmatter matter here.
- Not for Qwen. Qwen reads the output; it never loads this skill.
