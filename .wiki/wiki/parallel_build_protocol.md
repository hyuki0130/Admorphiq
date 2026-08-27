---
type: reference
topic: method
date: 2026-08-27
keywords: [parallel, agents, integration, tool-build, selectivity, ceph, stage-1]
---

# Fan out, then integrate — how tool development runs

> User directive, 2026-08-27: *"백그라운드로 도구별로 개발하도록 붙여서 속도 높여! 언제까지 하나씩
> 개선할거야? 그러니깐 ceph 인스턴스 최대로 활용을 못하잖아."* Full text of the rule:
> [`OPERATING_RULES.md`](../../OPERATING_RULES.md) rule 8.

## The shape

**Fan out by GAME, integrate centrally, keep on the full-25 measurement.**

| stage | who | what |
|---|---|---|
| fan out | one background agent per game, launched together | designs and verifies ONE frame-only tool for ONE game |
| own | each agent | exactly two NEW files: `src/admorphiq/tools/<name>.py`, `scripts/<name>_probe.py` |
| forbidden | each agent | `registry.py`, `loop.py`, `segment.py`, another agent's tool, any commit |
| integrate | the parent, alone | registers one tool at a time |
| decide | the full 25 on ceph-build, `PAR=25`, ~2 minutes | keep only if NO game regressed |
| record | the parent | round page + pull artefacts back off the box |

## Why each part is there

- **Per-game agents, not per-mechanic**: a mechanic is only known after the game's source is read,
  so the game is the unit that can be assigned before the work starts.
- **Two files, owned exclusively**: this is what makes the fan-out conflict-free. Shared-file edits
  across nine concurrent agents cost more in merges than the parallelism saves.
- **Integration is central because selectivity is a property of the TOOL SET.** A tool's `detect`
  imposes a cost on the other twenty-four games that its own author cannot see — measured
  2026-08-27, a tool that solved its own game perfectly took another from 0.4762 to 0.0476 by
  bidding on a board it could not solve. So no agent decides whether its own work is kept.
- **The brief carries what has already been paid for**: read the game DATA first; thirteen games
  declare a per-level action budget and END on overrun; `detect` returns 0.0 without a plan;
  segmentation lives in `tools/segment.py`; actions are swallowed during animations; an
  edge-pinned counter is not board content. An unbriefed agent re-learns each of these at the
  same cost they were first learned at.

⛔ **Freeze the snapshot before measuring.** Agents write into the same tree, so a tarball taken
mid-fan-out can capture a file its author is still editing — and the committed code is then not the
measured code. Sync once, vary only `registry.py` on the box. See
[[lessons/moving_target_measurement_20260827]].

## What a per-game agent is told, beyond the mechanic

Four things earned on 2026-08-27 that change how an agent spends a round, and that every brief
now carries:

* **Count, do not reason.** Two tools were unblocked by a single number after rounds of
  hypotheses — one showed 90% of plan deaths came from one predicate, another that a whole tier
  had fired 0 times in 728 decisions. A third had its OWN written description of the bug refuted
  by the counter. [[concepts/guard_about_the_model]]
* **A guard whose condition can never be false is the commonest defect here** — five instances in
  one day across three layers.
* **Report per-level COSTS, not the level count.** Two extra levels bought +0.0011 on one board
  because the incumbent's clears sat at human parity; the same levels made cheaper bought
  +0.0304. And on another game all five clears were already past parity and capped, so cost work
  there was worth exactly zero — measured in one command before a round was spent on it.
* **Check the archived re-render.** A tool can gain on the card and carry nothing to a board it
  has not seen, and only that run says so. [[lessons/generic_transfer_20260827]]

## Related

- [[rounds/r101_tool-development]] — the round this protocol came out of.
- [[lessons/tool_selectivity_20260827]] — why the keep/revert decision cannot sit with the author.
- [[sample_games_mechanics]] — what every agent is told to read first.
