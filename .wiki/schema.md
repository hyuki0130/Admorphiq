# Admorphiq LLM-Wiki Schema

Adapts [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (April 2026) to the ARC-AGI-3 competition.

Three-layer knowledge base: **raw sources → LLM-compiled wiki → schema governance**.

## Purpose

At **Kaggle inference time** (offline, no internet, no vector DB), the Hypothesis Engine LLM (one of Qwen 3 8B 4bit / Gemma 4 26B MoE 4bit / Gemma 4 E4B 4bit — selected by Task #11 benchmark) reads relevant markdown pages from this wiki to:

1. Classify a never-seen game into a known `game_type` via `concepts/` + `reasoning/discovery_phase.md`
2. Retrieve **applicable lessons** that warn about prior failure modes
3. Chain observation → hypothesis → strategy choice using `reasoning/` templates
4. Select the best strategy via `selector.md` dispatch rules, grounded in `strategies/frame_only/`
5. Avoid `strategies/brittle/` (documented only for traceability)

**The wiki is a reasoning aid, not a status report.** If a page only describes what-is and not how-we-got-there-or-what-would-break-this, rewrite it.

## Three Layers

### 1. `raw/` — Immutable sources
LLM reads, never writes.
- `traces/<game>.jsonl` — distilled solution traces from regression runs
- `regressions/<date>.md` — post-hoc analyses (v1 vs v2 breakage, etc.)
- `commits.md` — curated narrative of significant commits (why each happened)

### 2. `wiki/` — LLM-compiled knowledge
Hand- or LLM-written markdown with backlinks (`[[concepts/merge_mechanic]]`, `[[games/TN36]]`).

| Directory | Purpose | Must contain |
|-----------|---------|--------------|
| `concepts/` | Cross-game domain entities (mechanics, structures, shared abstractions) | one concept per file; lists instantiating games; example: `merge_mechanic.md`, `version_hash.md` |
| `lessons/` | Engineering wisdom from past incidents | symptom → diagnosis → prevention; example: `v2_hash_obfuscation.md`, `silent_regression.md` |
| `debug/` | Failure-mode playbooks keyed on observable symptoms | "if you see X, do Y, then Z"; example: `attribute_error_playbook.md`, `regression_bisect_playbook.md` |
| `reasoning/` | Explicit inference chains | observe → classify → choose → verify template; example: `discovery_phase.md`, `frame_to_strategy_chain.md` |
| `games/` | Per-game entries | current status + mechanics + solution pattern + lessons learned + links to concepts/lessons |
| `game_types/` | Mechanic categories | identifying features + discovery protocol + canonical strategy + games table |
| `strategies/frame_only/` | Generalizable strategies | applies-when + algorithm + generalization argument |
| `strategies/brittle/` | Anti-patterns (refactor queue) | what it relies on + why it fails + refactor recipe |

### 3. `schema.md` — This file. Governance.

## Writing Conventions

### Every `wiki/**/*.md` page must answer

1. **What is this?** (one-sentence summary in a `>` blockquote at the top)
2. **How did we arrive at this claim?** (provenance — link to `raw/traces/*`, `raw/commits.md`, `src/…:line`, commit hashes)
3. **What related pages should a reader consult?** (`Related` section with `[[backlinks]]`)
4. **What would falsify this claim?** (especially for `lessons/` and `debug/` — the symptom that makes this advice obsolete)

### Page structure template (games/game_types/concepts)

```markdown
---
type: game | game_type | concept | lesson | debug | reasoning | strategy
<other typed frontmatter>
---

# <Title>

> One-sentence summary (used by `scripts/generate_wiki_index.py`).

## <Core sections per page type — see below>

## Lessons Learned           # games/ only
- …

## Related
- [[concepts/...]]
- [[lessons/...]]
- [[games/...]]  (peer games)

## Sources
- `raw/...`
- `src/admorphiq/...` (line range)
- commit `<hash>`
```

### Per-page-type required sections

**games/**: Current Status, Observations, Mechanics Hypothesis, Solution Pattern, Refactor Plan (if brittle) OR Notes (if frame-only), Lessons Learned, Related, Sources.

**game_types/**: Identifying Features, Discovery Protocol, Canonical Strategy, Games Table, Edge Cases, Related.

**concepts/**: Definition, Instantiating Games, Detection Heuristics (frame-only), Related Concepts, Related Games.

**lessons/**: Symptom, Root Cause, Prevention, Recovery, Falsification, Related.

**debug/**: Observable Symptom, Triage Steps, Likely Root Causes, Fix Recipes, When to Escalate, Related.

**reasoning/**: Input (frame observation type), Chain (numbered steps with decision points), Worked Examples (≥2), Common Pitfalls, Related.

**strategies/**: Applies When, Algorithm, Why It Generalizes (or fails), Games Cleared, Limitations, Related.

### Backlinks

- Use `[[relative/path]]` for internal links (Obsidian-compatible and plain-text resolvable)
- Before writing `[[X]]`, ensure X exists or add a TODO to create it
- Prefer linking to the *most specific* matching page, not a broad category

### Frontmatter

All pages carry a `type:` frontmatter. Additional keys depend on the page type:

```yaml
# game
game_id, game_type, status_v1, status_v2, current_strategy, generalizes

# lesson
symptom, severity (info|warn|blocker), first_seen (commit hash or date)

# debug
trigger_symptom, affects (list of games/strategies)

# reasoning
input_type (frame|frame+diff|attempts), output_type (classification|strategy|hypothesis)

# concept
instantiating_games (list), detection_frame_only (yes|no|partial)

# strategy
generalizes (yes|no|partial), implementation (src path)
```

## Frontmatter Policy (load-bearing)

Every `wiki/**/*.md` page carries a YAML frontmatter block at the top
(`type:`, `status_v1:`, etc.) for tooling — the wiki index generator, the
retrieval seed rules, and future schema validators read these fields.

**Frontmatter is tooling metadata. It MUST NOT reach the LLM as
reasoning context.** `wiki_retrieval.strip_frontmatter` removes the leading
`---\n...\n---\n` block before any page enters the prompt. Reason: Qwen 3
8B treats the most recently seen JSON-like shape as the template for its
own response. 2026-04-21 R7 v1 bench regressed to 0 levels across all 40
envs because `games/<TITLE>.md` frontmatter leaked into the prompt and
Qwen echoed its `game_id` / `status_v1` / `current_strategy` fields back
as its response. See
[[wiki/lessons/schema_enforcement_round1_20260421]] for the history.

When authoring a new page type or a new frontmatter key: the key only
exists for scripts and governance. Do not assume the LLM will ever see it.
Conversely, if a fact belongs in LLM reasoning, it goes in the prose
body, not the frontmatter.

## Kaggle Compatibility Contract

- All files are plain markdown, readable via `open()`.
- Directory walkable with `pathlib.Path.rglob("*.md")`.
- No vector embeddings, no external index required.
- Total size target: < 10 MB (candidate LLMs all have 128K+ context).

## Dev-time vs Inference-time

- **Dev-time** (local, Claude Code or similar): writes/updates wiki pages; Obsidian optional viewer for graph view.
- **Inference-time** (Kaggle T4): selected LLM loads wiki pages on-demand as context; no writes.

## Maintenance rules

- Dead pages: add `deprecated: YYYY-MM-DD` frontmatter, do not delete (git history is the memory).
- Index regeneration: run `scripts/generate_wiki_index.py` after any batch of page edits.
- Trace refresh: run `scripts/extract_wiki_traces.py` after every 25-game regression.
- Page rewrite: any game/strategy/concept page affected by a new commit gets updated in the same commit.
