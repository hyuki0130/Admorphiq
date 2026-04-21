---
type: lesson
symptom: "Qwen 8B drifts from prompt-declared JSON schema under long wiki context"
severity: blocker
first_seen: 2026-04-21
---

# Schema enforcement and the R7 round-1 collapse

> The R7 round-1 first bench returned 0 levels across all 40 envs because
> Qwen 8B ignored the prompt's declared output shape and instead mimicked
> the YAML frontmatter of retrieved wiki pages. Three defensive layers
> (frontmatter strip, Ollama JSON schema, strategy-name enum) closed the
> worst of the drift, raising the floor from 0 to 19 levels — still below
> baseline 29, but with cleared env coverage now matching baseline (15/40).

## Symptom

First R7 bench with R2+R3+R7a/b/c/e + 16KB graph retrieval (2026-04-21):

- 40/40 envs returned `primary=""`, 0 levels total.
- Inspecting raw Qwen output on TU93 revealed Qwen was emitting the
  shape of `games/TU93.md`'s YAML frontmatter (`game_id`, `status_v1`,
  `current_strategy`, `generalizes`, ...) instead of our declared
  schema (`primary_strategy`, `fallback_stack`, ...).

## Root cause

R7b's graph retrieval started pulling `games/<TITLE>.md` pages into the
prompt. Those pages begin with a YAML frontmatter block emitted by
`scripts/generate_wiki_game_pages.py` for wiki tooling. Qwen 8B, with
its well-documented recency bias, treated the most recently seen
JSON-like structure (the frontmatter) as the template for its response.

## Three-layer fix

Each layer was added after measuring the failure mode of the prior
version. The versions are preserved in `scripts/wiki_agent_results_r7_v*.json`.

1. **Frontmatter strip** (`wiki_retrieval.strip_frontmatter`). Removes
   the leading `---\n...\n---\n` block from every retrieved page before
   it enters the prompt. Pages without frontmatter pass through.
   - R7 v1 → v2: total_levels 0 → 13.
   - Qwen still drifted from the schema but now emitted free-form JSON
     with creative keys (`"strategy"` instead of `"primary_strategy"`).

2. **Ollama JSON schema constraint** (`OllamaBackend.generate(..., json_schema=)`).
   Passes a JSON Schema dict to Ollama's `format` parameter; the decoder
   constrains output to match the shape. Qwen 0.20.3 supports this.
   - R7 v2 → v3: cleared 9 → 16 envs, levels 13 → 20.
   - Qwen now produced valid schema keys but still emitted names not in
     the 67-strategy whitelist — 26/40 envs had invalid `primary_strategy`
     that the R7e filter had to empty out.

3. **Enum on strategy names** — `primary_strategy` and `fallback_stack.items`
   enum bound to the live `default_strategy_registry()` whitelist.
   The decoder cannot produce a name outside the set.
   - R7 v3 → v4: essentially flat (15/40 envs, 19 levels, 0 hallucinations).
   - Qwen however began repeating the same strategy 2-4 times in
     fallback_stack. Added `uniqueItems: true` (still v4): forces 3
     distinct fallbacks.

## Remaining gap (baseline 29 vs round-1 19 levels)

Four envs account for −22 of the −10 net: FT09, CD82, SB26, AR25. On
each of these the baseline 8B picked the game-specific strategy (likely
via lucky pattern-match without constraint), while Qwen-with-schema
picks a generic click strategy and leaves the game-specific one out of
fallback_stack. `sb26_sort` is in the whitelist; Qwen did not pick it
for SB26 despite `selector.md`'s title-match rule being in the prompt.

Hypothesis: Qwen attention-drifts the title-match rule under 16KB of
context. Round 2 candidate action: **guarantee title-match as a
fallback via post-processing** — if `games/<TITLE>.md` exists and the
whitelist contains a strategy whose name contains the title, prepend
that strategy to `fallback_stack`. This is a minimal augmentation, not
an override — Qwen's primary choice is preserved.

## Prevention / Recovery

**Do**:
- When the LLM is supposed to emit structured output, enforce the shape
  at the decoder level via `format` / JSON Schema — prompt instructions
  alone are insufficient at 8B-14B scale.
- Enum-bind fields whose valid values are fully enumerable (strategy
  names, game_type labels). Saves a layer of post-filtering.
- Strip tooling frontmatter from any text fed to the LLM. Humans can
  read YAML preambles; LLMs treat them as template.

**Do not**:
- Rely on "please output JSON" instructions in the prompt. 2026-04-21
  measured 40/40 drift on Qwen 8B.
- Leave strategy-name hallucination to the whitelist filter — the
  filter fires too late (the primary slot ends up empty, burning a
  trial). Constrain at the decoder.
- Assume a prompt rule ("prefer title-matching strategy") moves
  behavior. Round-1 measured 4/40 envs ignored the title-match rule
  even with the rule in the prompt.

## Falsification

This lesson becomes obsolete if:

- A stronger model (Gemma 4 26B MoE+, Claude API, etc.) follows
  prompt-declared schema without decoder enforcement across a
  40-env bench AND without hallucinating whitelist names.
- Or, Ollama adds a stronger enforcement mode (e.g., value-level
  constraints beyond enum) that removes the need for prompt-side
  title-match handling.

## Related

- [[selector_is_advisory_not_enforced_20260421]] — precursor lesson
  on prompt-level rules being ignored; same spirit, different layer
  (output selection vs decoder shape).
- [[../architecture]] — R7 round loop contract
- [[brittle_tells]] — the page frontmatter strip avoids a specific
  brittle-tells pattern (pasting YAML frontmatter verbatim into
  reasoning context).

## Sources

- `scripts/wiki_agent_results_r7_v1.json` — first R7 bench (0 levels)
- `scripts/wiki_agent_results_r7_v2.json` — after frontmatter strip (13)
- `scripts/wiki_agent_results_r7_v3.json` — after JSON schema (20)
- `scripts/wiki_agent_results_r7_v4.json` — after enum + uniqueItems (19)
- `scripts/trace_analysis_r7_v3.json` — shows 26/40 hallucinations
- `scripts/trace_analysis_r7_v4.json` — shows 0 hallucinations, same gap
- `scripts/regression_diff.json` — gate verdict (FAIL, -18 levels)
- `.omc/rounds/round_001/meta.json` — round metadata
