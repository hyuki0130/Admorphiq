---
name: Karpathy LLM Wiki analysis
description: Full Karpathy "LLM Wiki" (2026-04-02) analysis in Korean is saved at docs/llm_wiki_karpathy_analysis_ko.md; gap table maps missing pieces to R23+ sub-rounds
type: reference
originSessionId: eba5cc76-48c0-4391-bce2-39b48288934e
---
Karpathy's "LLM Wiki" gist
(https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
is the architectural inspiration for Admorphiq's `.wiki/` layout.

The user-provided Korean analysis is archived verbatim at:

    docs/llm_wiki_karpathy_analysis_ko.md

Consult it when:

- Designing a new wiki workflow (ingest, query, lint patterns).
- Deciding whether a new automation should be built vs skipped
  (Karpathy's "stay minimal, add tools as scale demands").
- Explaining to the user why a wiki page shape was chosen (the
  doc has the vocabulary: "entity page", "concept page", "topic
  summary", "ingest fan-out", "index.md first, drill down").

Key principles lifted from the analysis:

1. Wiki is **compiled at ingest time, kept fresh**, not
   re-discovered at query time.
2. Role split — human curates sources + direction; LLM does
   summarising / cross-ref / bookkeeping / consistency.
3. Each ingest can touch 10-15 pages. Rounds that commit one code
   change and no wiki updates are violating the pattern.
4. `log.md` + `index.md` are the two special files every wiki
   needs. Admorphiq currently has `index.md` but NOT a
   chronological `log.md`.
5. Periodic lint passes catch contradictions / orphans /
   stale claims.
6. "Maintenance cost ≈ 0" only holds if the LLM actually does the
   maintenance on each round. Not doing it breaks the pattern.

The R23+ roadmap in CLAUDE.md Phase 8 absorbs the specific gaps
(log.md creation, lint-pass automation, ingest-workflow schema,
query→page refiling discipline).
