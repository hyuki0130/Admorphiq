---
name: feedback-no-copying-winners
description: "NEVER copy Duck/winner harness code — reference-only for understanding; we must design a BETTER original solution (user standing order, 2026-07-14)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3f835f42-61d8-4a15-811f-a74e74370d28
---

**User standing order (2026-07-14, "이것 항상 명심해"):** The Duck harness (Tufa's M1-winning
notebook `jeroencottaar/tufa-labs-duck-harness-june-30-milestone-winner`, pulled to scratchpad)
and any other top-team code are **REFERENCE-ONLY**. Never copy their code, prompts, or structure
verbatim into our repo.

**Why:** (1) The goal is to BEAT the winners, not tie them — copying caps us at their ceiling;
(2) originality of the solution matters to the user; (3) milestone prizes require open-sourcing
our notebook — a copied harness is both embarrassing and potentially ineligible as "our" work.

**How to apply:** Read winner code to extract MEASURED FACTS and design insights (e.g., context
eviction thresholds, segmentation-first perception, world-model note pattern) → record them as
research findings in the wiki with provenance → design OUR implementation from requirements,
improving on their known weaknesses (their own future-work list: context compaction/memory,
abstract-description perception; plus our additions: falsifiable-hypothesis memory, action
governor, transcript replay). Any PR that lifts code verbatim from a winner notebook must be
rejected. Related: [[project_unified_harness_r53]] ("baselines to BEAT, never copy").
