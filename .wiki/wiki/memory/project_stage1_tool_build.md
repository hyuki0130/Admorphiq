---
name: project_stage1_tool_build
description: Stage 1 = build frame-only rule-recovery tools until the 25 sample games clear; how to build one, and the scoreboard
metadata:
  type: project
---

Stage 1 is "the generic tools clear all 25 sample games". As of 2026-08-27 the generic tools
alone score **0.0230** over the 25 against the adapter-assisted card's **0.3162**, and **16 of 25
never clear a level**. Three games have a rule-recovery tool: ft09 (stencil, 0.4762), m0r0
(mirror, 0.0476), lp85 (track, 0.0278).

**How to build one — read the DATA first, do not probe blind.** Each game is one python file in
`environment_files/` holding its rules AND its levels. `scripts/read_sample_games.py <game>` prints
the action dispatch and win/lose predicates; `scripts/dump_sample_levels.py <game>` prints every
level's sprites, tags, positions and the level `data` dict. Twenty live probes on one game produced
a worse answer than one command. Details: `.wiki/wiki/sample_games_mechanics.md`.

**The fact that reframes everything: THIRTEEN of the 25 declare a per-level ACTION BUDGET and end
the game when it is exceeded** — 20 actions on one level, 13 on another. The searching generic path
runs 4,000-8,000 actions per game, so it is disqualified before it starts. Tools must plan, not
explore. `tools/budget.py` recovers the budget from the frame on 9 of 13.

**Selectivity is harder than solving.** In a shared harness a tool that bids without a plan steals
the turn from one that would solve the board: a tool bidding 0.3 for "the shape looks vaguely
right" cost another game 0.4286 and turned a +0.0278 gain into a 20x net loss. `detect` returns 0.0
when there is no plan. Measure the FULL 25 before keeping any tool change — it takes two minutes on
ceph-build at PAR=25.

Segmentation lives in ONE place, `tools/segment.py`, with its own tests. See
[[feedback_measure_full_25]] and [[policy_two_stage_tools_then_llm]].
