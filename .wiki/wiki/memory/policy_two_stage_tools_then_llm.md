---
name: policy_two_stage_tools_then_llm
description: TOP POLICY — build generic tools to 25/25 sample clears myself, THEN the LLM patches them on hidden games; order, machines, and what is NOT the plan
metadata:
  type: project
---

⛔ **Read `OPERATING_RULES.md` rule 0 and `.wiki/wiki/top_policy.md` — the repo is the source of truth
and this memory file does not travel between machines.**

**Stage 1** — I build the generic TOOLS until they clear all 25 sample games. "Goal: 25/25 generic
clears". Tool development is MY job, not the LLM's.
**Stage 2** — the LLM patches and combines those tools on HIDDEN games through the harness. Only this
generalises; it needs stage 1 as its foundation.

**Order**: (1) understand each sample game, build tools locally per-game; (2) push to ceph-build and
verify IN PARALLEL that the samples clear; (3) then cut the harness onto a Kaggle GPU kernel and
measure the HIDDEN set.

**Distance to stage 1** (2026-08-26): 20 of 25 games at 0 or 1 level under every tool; 15 at zero.

⛔ NOT the plan: porting hand-written per-game adapters into the shipped card, and treating "the tools
cannot clear these" as a verdict. Each cost a day.
