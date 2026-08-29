---
type: round
round: R101INERT
axis: generic-tools
keywords: [inert action, dead action, wasted action, efficiency, board_changed, edge counter, livelock, cleared levels, RHAE cap, canary]
verdict: the waste is confined to levels that never clear; the whole defect class is worth +0.000056 of the mean
commit: 517f24b6
---

# R101INERT — inert actions, censused over all 25 games and restricted to levels that CLEAR

> An action that changes nothing is 9.2x more likely to be on a level that never clears. Removing
> every one of them from every cleared level is worth **+0.000056** of the mean, all of it `ls20`.

## Why the question was asked

[[r101_shipped-and-transfer]] and rule **7bw** measured `world_model` spending 117 actions on lf52's
level 6 and changing the board **zero** times — with `deadsig` and `llm_goal`, 131 of that level's
500 actions producing one board change between them. That level never clears, so it is scored zero
however it is spent and the finding costs nothing.

The question with score attached is the other half: **does the same waste happen on levels the agent
CLEARS?** There an inert action is a direct efficiency loss and RHAE squares it — and the eval is
110 unseen games, all of which get the generic path, so a tool that spends a hundred actions
learning nothing costs squared score on every one of them. That is a defect *class*, not a level.

## Method

`scripts/_inert_census.py`, one arm per game, driving `score_efficiency.run_game` rather than
re-implementing it (rule 7x). Per action it records the level, the tool that proposed it, the action
key, and **two** change tests. Per cleared level it then reports the counts and a counterfactual
score with the wasted actions removed.

### Controls

* **NEGATIVE** — every game must reproduce its `scripts/rounds/R101SHIPPED/games/<g>.json` per-level
  counts *and* game score. **25 of 25 pass.**
* **POSITIVE, both directions** — the detector must be able to say YES and NO. It does: ten games at
  0.0% inert, lf52 at 41.7%, r11l at 47.6%. A census that came back all-zero or all-one would have
  measured nothing.

### The three classes, and why two are not enough

`segment.board_changed` discards the frame's outer band **on purpose** — rule **7c**: an edge-pinned
counter otherwise makes every action, refusals included, look live. But a game that draws its
selection marker or its readout in that band has its real effect discarded by the same rule. So:

| class | test | verdict |
|---|---|---|
| `dead` | nothing changed anywhere | unambiguously inert |
| `edge-only` | the band moved, the interior did not | **ambiguous** — never counted as waste |
| `live` | the interior moved | fine |

And an inert action is not automatically waste: `deadsig` *exists* to discover that an action is
inert and discovering it costs the action. So each inert action is classified by whether its own key
was already seen inert **on the same level** — `first` (information, paid once) vs `repeat` (spent
and never used). Two keys are reported, because `strict` (action + xy) makes a click-prober never
repeat and `coarse` (action id) asks "how many more clicks did it spend after the first that did
nothing". Neither is right alone.

## The finding

```
                  actions   DEAD   dead%   dead-repeat   edge-only
cleared levels       6381     68   1.07%            38         141
never-cleared        1996    196   9.82%             —         345
```

Counterfactual, removing the wasted actions from every cleared level:

```
dead-repeat only (the defensible reading)      +0.000056 of the mean   ls20 alone
all repeat-inert (the generous reading)        +0.000474 of the mean   ls20 alone
```

Twenty-four of twenty-five games gain **exactly zero**.

### The cap is why, and it bounds the class before any census runs

Only **five** cleared levels in the whole 25 score below 1.0 — bp35 L2/L3/L5, lp85 L4, ls20 L7.
Driving all five to a perfect 1.0 is worth **+0.00796 of the mean**, and that is the ceiling on
efficiency work over cleared levels no matter what a census finds. It is one pass over
`rounds/*/games/*.json` and it should be computed first.

### The two-way instrument would have published a fiction

```
                 two-way "inert"        three-way
r11l cleared     39 of 82 = 47.6%       0 dead, 39 edge-only   -> 0% waste
lf52 cleared     34 of 323 = 10.5%      0 dead, 34 edge-only   -> 0% waste
bp35 level 6    205 of 499 = 41.1%      0 dead, 205 edge-only
cd82 cleared     44 of 131 = 33.6%     16 dead, 28 edge-only
```

Read the other way, the raw `!=` test alone reports **zero** inert actions on bp35 and r11l where
the interior test finds hundreds — rule **7c** in a second place. Neither test alone is sound.

### The livelock signature appears only where it is free

Longest run of consecutive inert actions proposed by ONE tool:

```
never-cleared:   116  lf52 L6 world_model      49  bp35 L6 graph      then 6, 4
cleared:           7  ls20 L7 keymaze           6  lf52 railpeg       then 3, 3, 2 ...
```

Only two runs of eight or more exist in all 25 games and both are on levels that never clear. The
memo-plus-give-up livelock named in rule **7bw** — *a per-frame memo plus a give-up counter livelock
whenever the tool's own action is the only thing that would invalidate the memo* — is real and
generic, and does not touch a single scored action here.

### One canary is not as tight as it looks

Of the five levels sitting at exactly the human count (rule **7bl**), four contain **zero** dead
actions: re86 L2 and L6, tu93 L7 and L8 are genuinely tight. **sc25 L2 is not — 6 actions against a
human 6, and one of them is dead** (`sigilgate`). It cannot gain score because the scorer caps at
1.0. What it means is that sc25's entire cap margin is one wasted click, and there is a free action
already inside the level to absorb a future regression.

## Verdict

The defect class is measured, bounded and worth approximately nothing on the sample set. ⛔ But the
bound comes from nineteen games sitting at the cap, which is a property of the public 25 and **not**
of the 110 unseen games. Do not read `+0.000056` as "inert actions are harmless"; read it as "the
public set cannot measure this, so it must not be used to justify the work either way."

Rule **7cb**. Artefacts `scripts/rounds/R101INERT/census.json`. Related: [[r101_shipped-and-transfer]],
[[r101_silent-specialists]].
