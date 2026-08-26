---
type: policy
status: TOP — read before choosing any axis
date: 2026-08-26
keywords: [policy, two-stage, tool-development, 25-of-25, hidden-set, harness, kaggle-gpu, ceph-build, stage-order]
---

# Top policy — the two stages, and who does what

> The two stages: I build the generic tools until they clear all 25 sample games; the LLM then patches and combines them on hidden games through the harness.

Set by the user 2026-08-26, after the plan was lost twice in one day while sitting unread in this same
wiki. `OPERATING_RULES.md` rule 0 carries the operational form; this page is the wiki's copy so a
reader who starts from `index.md` finds it.


## ⛔ TOP POLICY — the two stages, and who does what (2026-08-26, user-set)

**Full text: [`OPERATING_RULES.md`](OPERATING_RULES.md) rule 0. This block is the pointer that
survives a context compaction; the rules file is the source of truth.**

**Stage 1 — build the generic TOOLS until they clear all 25 sample games.** `"Goal: 25/25 generic
clears"` (`.wiki/wiki/architecture_self_improving_agent.md:15`), `"continuation = per-tool
strengthening"` (`memory/project_unified_harness_r53.md`). **I do the tool development** — read each
sample game, diagnose where its tool stops (`scripts/tool_stall_diag.py`), and write the code.
The LLM does not build the tools; it uses them later.

**Stage 2 — the LLM patches and combines those tools on HIDDEN games, through the harness.** This is
the only part that generalises: a game never seen cannot have a tool hand-written for it. It needs
stage 1 as its foundation, because a model patching tools that clear nothing has nothing to patch
from.

**The loop, in order:** (1) understand each sample game and BUILD the tools — local, per-game, by me;
(2) push to `ceph-build` and verify IN PARALLEL that the sample games clear — that box verifies at
width, it does not author; (3) then cut the harness down onto a **Kaggle GPU kernel** and measure how
much of the HIDDEN set it completes.

**Distance to stage 1** (measured 2026-08-26, `scripts/rounds/ALTFULL`, every tool forced alone at
3000 actions): **20 of 25 games sit at 0 or 1 level; 15 score zero under every tool.**

⛔ **Not the plan**, each having cost a day: porting hand-written per-game adapters into the shipped
card (no LLM in that path, and it conflicts with the non-negotiable dual-scoreboard doctrine), and
reading "the tools cannot clear these" as a verdict instead of as stage 1's work list.


## Why it was lost, both times

Once by inheriting the previous session's axis (detection dispatch) without reading
`.wiki/wiki/rounds/index.md` first, and once by reading a measurement ("fifteen games score zero under
every tool") as a conclusion rather than as the work list stage 1 exists to burn down.

Both failures share a shape: **the plan was in the repository and the session acted from memory.**

## Related

- [[architecture_self_improving_agent]] — where "Goal: 25/25 generic clears" is stated
- [[rounds/r100_tool-selection-wall]] — the sweep that produced stage 1's work list
- [[rounds/r99_detection-dispatch]] — the axis that is NOT the plan, and its doctrine conflict
