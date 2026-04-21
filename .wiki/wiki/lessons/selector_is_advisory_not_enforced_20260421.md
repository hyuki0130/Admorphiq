---
type: lesson
symptom: "LLM-picked strategies diverge from selector.md rules"
severity: blocker
first_seen: 2026-04-21
---

# Selector rules are advisory, not enforced (Phase 8 R6 finding)

> The `.wiki/wiki/selector.md` dispatch table is treated as a suggestion by
> Qwen 3 8B and 14B, not a constraint. Running R6 proved both models will
> invent fallback stacks and even hallucinate strategy names not in the
> whitelist. The rules need a Python enforcement layer — wiki edits alone
> don't change LLM behavior reliably.

## Symptom

During R6 bench on 2026-04-21:

- `selector.md` rule 4 was updated to include `lights_out, paint_game,
  click_all_colors` in the `click_rare` fallback stack.
- Qwen 3 14B re-run produced `fallbacks: ['click_rare', 'seq_search']` for
  FT09 — completely ignoring the rule 4 edit AND hallucinating
  `seq_search` which is not in the 67-strategy whitelist.
- Qwen 3 8B (baseline) "accidentally" produced `[paint_game, lights_out]`
  for FT09 via whatever holistic reasoning it does, clearing 6 levels.
  8B's behavior is not reproducible-on-demand — it's lucky hallucination.

The same divergence hit CD82: rule 3 was updated to include `paint_game`,
but 14B still picked `[click_all_colors, raster]`.

## Root cause

LLMs at 8B–14B scale treat markdown tables as narrative context, not as
executable rules. Given the full wiki prompt (~8KB), the model forms a
holistic "what kind of game is this" impression and picks strategies by
feel, not by table-row lookup. Evidence:

- 14B repeatedly ignored selector.md rule updates across two runs.
- 14B hallucinated `seq_search` despite the prompt listing all 67
  whitelisted names verbatim.
- 8B's fallback picks for FT09/CD82 are not consistent with any
  selector.md row — they're pattern-match to game title.

The wiki-as-knowledge-base pattern assumes the LLM respects explicit
rules. On these models, that assumption fails for fallback selection.

## Numbers

R6 bench (2026-04-21, same 40-env trace, same R2+R3 features):

  8B + R2+R3              : 15/40 raw cleared, 36 levels, gate PASS
  14B + R2+R3 v1          : 21/40 raw cleared, 34 levels, gate FAIL
                            (FT09 6→0, CD82 6→0)
  14B + selector.md v2    : 18/40 raw cleared, 31 levels, gate FAIL
                            (FT09 6→0, LS20 1→0, CD82 6→0 — worse)

The selector edit moved 14B sideways — improvements in some envs,
regressions in others, net slight loss of 3 levels. Selector edits
are not a reliable knob for 14B.

## Prevention / Recovery

**Do NOT**: edit selector.md expecting to change LLM fallback picks.
Those edits are documentation-only on current models.

**Do**: enforce selector rules in Python. A post-classify pass in
WikiAgent should:

1. Read the DiscoveryReport probe signature.
2. Match it against a rule table (could still live in selector.md, but
   parsed into Python tuples at boot).
3. **Overwrite** `primary_strategy` and `fallback_stack` with the rule's
   stack when the signature matches exactly.
4. Fall through to the LLM's pick only when no rule matches (the
   `unknown` bucket).

This keeps selector.md as the source of truth (still human-readable,
still wiki-cross-linkable) while making it actually executable.

A Python selector enforcement layer is the next dev-cycle task, filed
as R3+ in the Phase 8 restart plan.

## Falsification

This lesson becomes obsolete if:

- A stronger model (Gemma 4 26B MoE, Claude API, etc.) demonstrably
  follows selector.md tables under the same prompt and survives R5 gate
  without Python enforcement, OR
- The prompt is re-engineered (e.g., fewer pages, rule table at the
  end as the last thing the model reads) and the current models start
  respecting edits.

## Related

- [[../architecture.md]] — R6 bench sequence and falsification criteria
- [[api_hash_rotation_20260421]] — another "brittle to specific IDs"
  lesson; same spirit (depend on observable signals, not names)
- [[brittle_tells]] — catalog of other mis-generalizable dependencies
- [[../selector.md]] — the advisory-not-enforced rules themselves

## Sources

- `scripts/wiki_agent_results_8b_r6.json` — 8B R6 trace
- `scripts/wiki_agent_results_14b_r6.json` — 14B v1 trace
- `scripts/wiki_agent_results_14b_r6_v2.json` — 14B post-edit trace
- `scripts/trace_analysis_8b_r6.json` / `_14b_r6.json` / `_14b_r6_v2.json`
- `scripts/regression_diff.json` — strict gate verdict for 14B runs
- 14B FT09 execution trace: hallucinated `seq_search` (not in whitelist)
