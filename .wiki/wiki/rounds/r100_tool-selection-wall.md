---
type: reasoning
round: R100
axis: does the harness's tool-selection collapse explain the generic path's level-1/2 wall?
keywords: [tool-selection, tool_selector, graph-collapse, alt-sweep, generic-path, depth-wall, vc33-toggle, harness, agent25, near-human-level-1]
verdict: **ANSWERED 2026-08-26 — the wall is a PLANNING limit, not a SELECTION one.** The sweep completed 100/100: exactly ONE game of twenty (vc33) has a non-graph tool that beats graph, and its gain is 0.0000 -> 0.0013. Perfect tool selection would leave 19 of 20 games exactly where they are.
date: 2026-08-26
---

# R100 — does the tool-selection collapse explain the generic path's wall?

## Why this round, and why now

R98 is exhausted on the public set (its own page carries the accounting): per-target predicates
refuted, multi-piece placement stale-and-working, and the second family member has **no candidate** —
`sp80` is the only place-then-propagate game in the 25. A family of one cannot expand publicly.

Three measurements from 2026-08-26 pick the next axis, and they connect:

**1. The proxy stopped tracking the score.** Card `0.0566 -> 0.3162` (5.6x, thirteen ports) while
hidden went `0.20 -> 0.18`. The one calibration point — card 0.2772 giving hidden 0.18 — puts today's
card near 0.205, i.e. back where v3 already was. Public-game-specific code cannot transfer to 110
private games.

**2. The generic path — what runs on every unmatched private game — is near-human and then STOPS.**
17 of 25 clear at least one level; level-1 actions against the human baseline have **median 1.3x**,
with ten of seventeen at or under 1.5x and seven scoring a perfect 1.0. But **19 of 25 wall at level 1
or 2**, and each burns its whole remaining budget there: ar25 clears two levels in 77 actions and
cannot buy a third with 8,264.

**3. The harness picks ONE TOOL.** `picks.log`, recovered from `/tmp` where it was one reboot from
gone: `vc33 cn04 sp80 sc25 bp35 dc22 m0r0 sk48 g50t` — **all nine `pick=graph`**. And on vc33 a
different tool measurably does better:

```
vc33/toggle   levels=2   per_level=[113, 143]   score=0.0013
vc33/graph    levels=1   per_level=[2335]       score=0.0000
```

20x the efficiency on the level both clear, plus a level `graph` never reaches.

⚠️ The collapse is not the model ignoring the wiki. `tool_selector.md`'s decision table gives `graph`
the row *"ANY game where actions produce discrete repeatable state changes"* and locks every other
tool behind *"only pick on this exact signature"*, *"only on verified fill mechanics"*, *"never
first"*. `toggle` is excluded with *"NONE of the 25 dev games is one"* — which vc33 refutes. **The
model is following the table; the table is wrong about at least one entry.**

## The question

Is the level-1/2 wall a PLANNING limit, or a SELECTION one? If the harness had picked the right tool,
would those games go deeper?

## What is already measured, and what is not

`scripts/rounds/ALTFULL/alt.log` holds 95 of 100 tool x game combinations at budget 3000. ⛔ It is
**not usable as it stands**: completions per tool are `graph 20/20, world_model 20/20, dealias 20/20,
paint 18/20, toggle 11/20`, and the sweep was stopped (a 60-core cap breach) exactly where `toggle`
was thinnest. A first reading of the partial said *"0 games where a non-graph tool beats graph"*,
which was a statement about jobs that never ran.

**First step: finish the sweep at safe parallelism and read it whole.** Only then does the question
have an answer rather than an anecdote.

## Gates

This round has no live-engine contract to protect. What it must not break: the deployed card
(`--agent kaggle_detect`, full 25 = **0.3162**, and the dispatch bail measured a no-op at both 1,000
and 2,000 actions) and the R98 gates if any harness change reaches shared code (`oracle_gate` 3/3,
grounding PASS, mutant frozen table PASS, `depth_walk` 3/3 at 107 actions).

## Related

- [[r98_flow-deflection]] — the exhausted round, and where the burst pool and its correction were recovered to
- [[r99_detection-dispatch]] — the dispatch axis, its doctrine conflict, and the generic-path measurements quoted here
- [[r93_tool-fork-patch]] — the LLM-patches-its-own-tool design this axis feeds


## ANSWERED: the wall is PLANNING, not SELECTION

The sweep finished — 100 of 100 combinations, every tool 20/20, at budget 3000:

```
game    graph   best non-graph
vc33      1     toggle=2        <-- the only game where anything beats graph
tn36      1     toggle=1
lf52      1     dealias=0
lp85      1     dealias=0
r11l      1     dealias=0
the other fifteen: graph 0, every alternative 0
```

**One game of twenty.** And vc33's win is worth `0.0000 -> 0.0013` on the game, about **+0.00005** of
card. Perfect tool selection — an oracle that always picked the best tool — would leave nineteen of
twenty games exactly where they are.

⛔ **So the level-1/2 wall is not the harness choosing wrongly.** `tool_selector.md`'s `graph`-as-default
guidance is right on 19 of 20 games; it is wrong about exactly one entry (`toggle`, refuted by vc33),
and fixing that entry buys five hundred-thousandths of a card.

**What this closes**: the selection hypothesis, which was the reason this round opened. The three
measurements that motivated it stand — the proxy does not track the score, the generic path is
near-human on level 1 and walls at 1-2, the harness picks `graph` everywhere — but the third is now
explained by the second rather than causing it. **`graph` is picked everywhere because it is the only
tool that clears anything on nineteen of twenty boards.**

⚠️ The one correction the sweep does license: `tool_selector.md` excludes `toggle` with *"true
lights-out — NONE of the 25 dev games is one"* and *"measured 0 elsewhere"*, and vc33 contradicts
both. That is a one-line fix to a wiki claim, not a lever.

**Where the depth actually has to come from**: the tools themselves. Fifteen of twenty games score
zero under EVERY tool at 3000 actions — no selection policy reaches them, and no budget does either
(`NOGIVEUP`, 25x the give-up, 0 of 23 games changed). That is the same conclusion the card work
reached from the other direction, and it is a capability statement about `graph` and its siblings.

## The one correction applied to `tool_selector.md`

The `toggle` row claimed *"NONE of the 25 dev games is one"* and *"measured 0 elsewhere"*. The full
sweep refutes both on vc33, so the row now carries the measurement instead of the exclusion, with the
scope kept honest — `toggle` still scores 0 on the other nineteen.

⚠️ **This is a wiki fix, not a lever.** It is worth about +0.00005 of card. It is here because the
harness reads this table as its knowledge and a false exclusion in it is a false belief the model then
acts on faithfully — which is exactly what "the model is following the table" meant. Leaving a refuted
claim in the source of truth is worse than the score it costs.