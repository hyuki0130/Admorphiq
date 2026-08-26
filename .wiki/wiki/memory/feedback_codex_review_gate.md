---
name: feedback-codex-review-gate
description: "ALL planning, design, test plans, AND analyses must be reviewed with Codex (codex exec) before acting on them — user standing order 2026-07-14"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3f835f42-61d8-4a15-811f-a74e74370d28
---

**User standing order (2026-07-14):** every substantive artifact — plans, designs, test plans,
and ANALYSES (transcript analyses, scorecard analyses, failure diagnoses, research syntheses) —
goes through a Codex review (`codex exec --sandbox read-only -C <repo>`) before we act on its
conclusions. Record verdicts in docs/ + round pages.

**Why:** independent adversarial review catches misreadings before they become build decisions
(measured example: the "hand-crafted tools harmful" misreading survived until the dossier+Codex
deep-dive corrected it to "game-SPECIFIC tools harmful").

**How to apply:** (1) write the analysis/brief to a file; (2) `codex exec --sandbox read-only
-C /Users/nhn/Workspace/Admorphiq "$(cat brief.md)" </dev/null | tee out.txt` — ⚠️ ALWAYS
`</dev/null` when backgrounded (codex hangs forever waiting on open stdin otherwise — measured
2h hang 2026-07-14); (3) save the verdict to docs/, apply deltas, note disagreements explicitly.
Reviews run in parallel with builds — they gate ACTING on conclusions, not writing them down.

**EXTENDED to MODEL/LEVER VERDICTS (user order 2026-07-22, after a measured violation):** any
"model X beats model Y" / "lever closed" call is an ANALYSIS and goes through Codex BEFORE being
declared. **The gpt-oss incident (2026-07-22 ~03:00)**: I declared "gpt-oss-120b loses, gemma4
stays patcher, lever closed" from (a) a 2-game sample (statistically void vs the 25-game bench)
and (b) a mis-configured run — gpt-oss is a REASONING model and the completion path had NO
reasoning_effort set + thinking disabled (its reasoning channel was OFF). This also violated
[[feedback_measurement_discipline]]'s tune-before-discard rule (positive signals existed: clean
execution, 2-4x faster, structured code). User caught both. Corrections shipped: reasoning-effort
env gate (d94de32), breadth bench 10 games × 2 families per model (b9374bf), verdict demoted to
interim. **Rule: before ANY comparative verdict — (1) breadth sample (≥ the diverse-family
subset, never 1-2 cases), (2) each model at its OWN best config (reasoning channels, budgets),
(3) Codex reviews the experiment design AND the verdict draft, (4) — user reinforcement
2026-07-22 03:18: "테스트하고 또 테스트해" — one test round is NEVER a superiority verdict;
walk each model's TUNING LADDER (reasoning effort levels, output budgets, prompt shape incl.
evidence-first staging, temp>0 N-samples with harness selection, card-size variants) as
bounded rounds, and declare a winner only after BOTH ladders are exhausted. A losing round is
recorded as "lost under config C", never "model is worse".**
Related: [[feedback_no_copying_winners]], [[feedback_measurement_discipline]].
