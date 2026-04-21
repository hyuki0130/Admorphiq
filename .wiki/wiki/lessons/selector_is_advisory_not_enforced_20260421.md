---
type: lesson
symptom: "LLM-picked strategies diverge from selector.md rules"
severity: blocker
first_seen: 2026-04-21
---

# Selector rules are advisory, not enforced

> Discovery incident log: R6 bench (2026-04-21) proved Qwen 3 14B
> treats `selector.md`'s markdown table as narrative context, not an
> executable rule set. The operational rule that follows is documented
> in [[../architecture#Routing-Rules-Require-Python-Reinforcement]];
> this page preserves the measurement that drove it.

## What happened

- `selector.md` rule 4 updated to include `lights_out, paint_game,
  click_all_colors` in the `click_rare` fallback stack.
- 14B re-run produced `fallbacks: ['click_rare', 'seq_search']` for
  FT09 — ignoring the new rule 4 AND hallucinating `seq_search`, a
  name not in the 67-strategy whitelist.
- Same pattern on CD82: rule 3 was updated to include `paint_game`,
  14B still picked `[click_all_colors, raster]`.
- R6 gate verdict FAIL on both re-runs.

## What it taught

Markdown rules in `selector.md` are read by the LLM as prose. At
8B-14B scale with 8KB+ wiki context, the model does not reliably
execute table lookups. **Rules must be reinforced at the Python layer
(decoder enum, retrieval seed, or output post-processing)** — see the
architecture doc for the governance rule and the enforcement options.

## Follow-ups already landed

- Round 1 (2026-04-21) added decoder-level enum on `primary_strategy`
  and `fallback_stack` via `_HYPOTHESIS_JSON_SCHEMA`. After that,
  hallucinations measured on the round-1 bench dropped from 26/40 to
  0/40. See [[schema_enforcement_round1_20260421]] for the full arc.
- `selector.md` now carries an "Enforcement note" at the top warning
  readers that prompt-level rules are advisory.

## Falsification

This lesson becomes obsolete if a future bench run on a stronger model
(Gemma 4 26B+, Claude API) shows selector table compliance AND survives
the R5 gate without Python-layer enforcement — none of the 8B/14B
rounds to date meet either bar.

## Related

- [[../architecture]] — rule is hosted there, not here
- [[../selector]] — the table whose rows both layers must keep in sync
- [[schema_enforcement_round1_20260421]] — round-1 follow-up
- [[brittle_tells]]

## Sources

- `scripts/wiki_agent_results_14b_r6.json` — 14B first R6 trace
- `scripts/wiki_agent_results_14b_r6_v2.json` — post selector edit
- commit `3a6cde0` — R6 bench commit
