---
name: feedback-submission-user-decides
description: NO automatic Kaggle submissions — the user decides when to submit (standing order 2026-07-14); also minimize GPU quota usage (CPU-only pushes for LLM-free kernels, batched experiments only)
metadata:
  type: feedback
---

**User standing order (2026-07-14 21:21):** Do NOT auto-submit to Kaggle on a schedule. The user
decides when a submission is worth the daily slot ("내가 판단해서 괜찮을 때 제출"). Prepare
submission candidates + a recommendation, then WAIT for the user's go.

**Why:** daily slot = 1; submissions are strategic (variance replicates vs new-card tests), and
the user wants control of that budget.

**Also:** GPU weekly quota (30h) must be spent frugally — measured waste to avoid: (a) validation
pushes of CPU-only kernels with enable_gpu=true (~2h GPU each, pure waste — push those with GPU
off); (b) unpaired speculative runs (batch OFF/ON comparisons in ONE kernel run); (c) redundant
preflights. Before any GPU run, state its purpose + expected hours; prefer designs that answer
multiple questions per run. Related: [[feedback_codex_review_gate]].

**Submission bar (user, 2026-07-14 21:26):** the next submission must EXCEED the current card
(public proxy 5.83) — the LLM version + next strategies get applied and measured first. Until
then: infinite test→feedback→develop loop toward ALL games cleared; never stop, prepare
candidates, user gives the go.

