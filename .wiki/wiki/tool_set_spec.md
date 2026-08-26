---
type: spec
status: ACTIVE — stage 1 of the top policy; this is the work in progress
date: 2026-08-27
keywords: [tool-set, stage-one, 25-of-25, reach, deliver, configure, induce, class-a, class-b, class-c, class-d, test-method, ceph-verification]
---

# Tool set spec — four generic tools for the 25 sample games

> The four generic tools, the order they are built in, and how each is tested.

**Where this sits**: [[top_policy]] stage 1 — I build generic tools until they clear all 25 sample
games; only then does the LLM patch them on hidden games. Round page: [[rounds/r101_tool-development]].
Full design with rationale: `docs/design_r101_tool_set.md`.

⛔ **Read this before writing tool code.** It exists so a compacted context can resume without
re-deriving the classification.

## The measurement that drove it

`scripts/tool_stall_diag.py`, bare `UnifiedAgent`, 3000 actions, all 25 in parallel on ceph-build
(`scripts/rounds/TOOLDIAG/diag.log`):

* **eleven games run 72-99% INERT actions** — ft09 opens 24 states from 1,610 transitions, lp85 99%
  inert over 1,054
* **two never draw a goal** — cn04 (1,079 states), sp80 (964)
* **twelve expand, aim, and still clear nothing** — sk48 979 states with a goal

⚠️ That diagnostic drives the BARE `UnifiedAgent`, not the deployed path (`--agent chained` puts
`WorldModelAgent` first, which is where cd82's 6/6 comes from). Its numbers compare with each other,
never with GENERIC30's.

## The four classes, from the mechanics

| class | shape | games | what a tool must have |
| --- | --- | --- | --- |
| **A** | navigate an avatar to a goal cell | 7 — dc22 tu93 ls20 m0r0 g50t bp35 s5i5 | avatar by MOTION, measured direction map, reachability refined on refusal, goal cell, closed-loop walk |
| **B** | transport objects onto destinations | 6 — wa30 re86 ka59 su15 r11l lp85 | object identity, carry model, **assignment** (which item to which target), delivery ordering |
| **C** | set a configuration, board resolves it | 5 — sp80 tn36 sc25 cd82 ar25 | two-phase detection, a SIMULATOR learned from one sacrificial commit, search over **configurations** |
| **D** | induce a rule, apply it to a target | 7 — ft09 sb26 sk48 tr87 lf52 cn04 vc33 | target read off the board, **rule induced from transitions BEFORE acting**, rule-space search, ordering |

**`graph` expands over ACTIONS — class A's shape and only A's.** Eighteen of twenty-five games are B,
C or D, which is why the only tool that clears anything covers seven.

## Build order, and the reason for it

1. **T-D `induce`** — largest class (7), owns the sharpest failure (all four worst inert games are D),
   and "induce before acting" is the step that turns guessing into direction.
2. **T-B `deliver`** — 6 games and no tool does assignment today.
3. **T-C `configure`** — 5 games; R98 already proved the shape on sp80 (*"the transition model IS the
   simulator"*), so this is generalising a working thing.
4. **T-A `reach`** — `graph` half-covers it; smallest gain.

## How each tool is tested

**Per tool, in this order — authoring is local and per-game, verification is parallel on ceph:**

1. **Unit** — the tool's own inference on a FIXED frame or capture, not a live game. A rule inducer is
   tested by whether it recovers a known rule from recorded transitions.
2. **Single game, live** — `uv run python scripts/tool_alternatives.py <game> <tool> 3000`, which runs
   that tool ALONE. This is the honest per-tool number: it removes the question of who selected it.
3. **The class, in parallel on ceph-build** — every game of the tool's class at once. ⛔ Cap by LOAD
   AVERAGE 60, not job count: start `-P 30` and read `uptime` twice, because `uv run python` is a
   wrapper plus a process (measured: `-P 55` gave load 60.97).
4. **No regression** — the deployed card `--agent kaggle_detect` full-25 must stay **0.3162** until a
   tool is deliberately promoted. `scripts/rounds/R99CARD/run.sh` measures it.

**The number that says a tool works** is levels cleared on its class's games, against the same games'
current numbers in `scripts/rounds/ALTFULL/alt.log` (every tool forced alone at 3000): today fifteen
games score zero under every tool, four reach one level, and vc33 reaches two under `toggle`.

## Current position

Design written (`docs/design_r101_tool_set.md`), classification measured, **no tool code written yet**.
Next action: T-D `induce`, starting from ft09 — the extreme case at 99% inert with 24 states opened.

## Related

- [[top_policy]] — the two stages and who does what
- [[rounds/r101_tool-development]] — this round
- [[rounds/r100_tool-selection-wall]] — the sweep proving selection is not the problem
- [[tool_selector]] — the runtime decision table (its `toggle` row was corrected 2026-08-26)

How each candidate offline model is guided to the right tool inside its own context budget is
[[model_guidance_spec]].
