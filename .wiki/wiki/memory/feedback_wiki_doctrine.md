---
name: Wiki Writing Doctrine (Karpathy LLM-Wiki Adapted for ARC-AGI-3)
description: The .wiki/ directory must support LLM reasoning, not just document current state; write history + concepts + lessons + reasoning chains, heavily cross-linked
type: feedback
originSessionId: 96a72d05-e421-4801-9b30-810c293777f0
---
## Purpose of `.wiki/`

The wiki is NOT a state dump. It is a **knowledge graph that enables an offline LLM (Qwen 3 / Gemma 4 at Kaggle inference time) to reason about a never-before-seen game**, by retrieving:

1. **Domain concepts** the game might instantiate (`concepts/`)
2. **Engineering lessons** learned from past failures and fixes (`lessons/`)
3. **Debug playbooks** for specific symptom types (`debug/`)
4. **Explicit reasoning chains** showing observation → hypothesis → action (`reasoning/`)
5. **Per-game entries** that link to the above, not just record stats (`games/`)
6. **Per-game-type entries** that summarize the class of mechanics (`game_types/`)
7. **Strategy entries** distinguishing generalizable vs brittle (`strategies/`)

Plus **immutable sources** (`raw/`) for provenance: traces, regression snapshots, curated commit history.

## Why this matters

Round 1 regression on 2026-04-20 revealed that v2 version hashes break 12 of our brittle solvers. The private test set will expose the same generalization problem. An LLM that only sees "current state" pages will replay the same hardcoded mistakes. An LLM that sees **why each brittle solver was built, why it broke, and what the generic pattern should have been** can extrapolate to new games.

## Writing conventions (in addition to `.wiki/schema.md`)

### Every `wiki/**/*.md` page must answer:
1. **What is this?** (one-sentence summary in a `>` blockquote at the top)
2. **How did we arrive at this claim?** (provenance — link to raw/traces, raw/commits.md, source code line ranges)
3. **What related pages should a reader consult?** (explicit `Related` section with ``[[...]]`` backlinks)
4. **What would falsify this claim?** (when writing lessons/debug — the symptom that means "this advice no longer applies")

### History over state
When in doubt, describe the *journey*:
- "Initially we thought X, observed Y, so we changed to Z"
- "This solver passed v1 on date N, failed v2 on date N+10, proposed refactor X"
- "LF52 was cleared at commit A, broke silently, still unresolved"

### Cross-link aggressively
Every new claim should cite ≥1 concept page, ≥1 lesson page, and ≥1 peer game page when applicable.

### Link targets must exist
Before writing ``[[X]]``, make sure X exists or add a TODO to create it.

### Rollup in index.md
Regenerate `.wiki/wiki/index.md` via `scripts/generate_wiki_index.py` after each batch.

## Page type cheat sheet

| Directory | Purpose | Example |
|-----------|---------|---------|
| `concepts/` | Cross-game domain entities (mechanics, structures) | `merge_mechanic.md`, `pushable_block.md`, `version_hash.md` |
| `lessons/` | Engineering wisdom from past incidents | `v2_hash_obfuscation.md`, `silent_regression.md`, `brittle_tells.md` |
| `debug/` | Playbooks keyed on observable symptoms | `attribute_error_playbook.md`, `regression_bisect_playbook.md` |
| `reasoning/` | Explicit chains: observe → classify → choose → verify | `discovery_phase.md`, `frame_to_strategy_chain.md` |
| `games/` | Per-game entries (25) | `TN36.md`, `SU15.md` |
| `game_types/` | Mechanic categories | `merge_puzzle.md`, `sokoban.md` |
| `strategies/frame_only/` | Generalizable strategies | `bfs_state_space.md`, `click_rare.md` |
| `strategies/brittle/` | Anti-pattern strategies (refactor queue) | `internal_method_call.md` |
| `raw/` | Immutable sources | `traces/*.jsonl`, `commits.md`, `regressions/*.md` |

## How to apply

- When adding a new game page: immediately consider which `concepts/` apply and link them; if a new concept emerges, create the concept page.
- When debugging a new failure: write a `debug/` playbook **during** the debugging, not after — that's when the symptoms are freshest.
- When a commit introduces a regression or an architectural pivot: update `raw/commits.md` with a narrative entry explaining why.
- When the LLM at Kaggle time fails to choose a strategy correctly: treat it as a `reasoning/` chain that was missing — add it.
- The wiki grows; it is never "done". Each new insight is a new page or a section in an existing page. Dead pages get a `deprecated: YYYY-MM-DD` frontmatter tag, not deletion.
