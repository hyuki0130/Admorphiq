---
type: reasoning
round: R99
axis: submission card — port the quarantined adapters from game_id selection to FRAME DETECTION
keywords: [detection-dispatch, adapters25, port, false-positive-gate, probe-detection, control-scheme, card, submission, ceiling, transfer, first-frame-limit]
verdict: **CARD 0.0566 -> 0.2772 (4.9x), CONFIRMED on all 25 games in the SHIPPED configuration, zero regressions, nine adapters ported.** Every port lands EXACTLY on its ceiling (lossless), and the shipped configuration scores what the benched one does (0 differences across every game both runs finished). The gate that makes a port shippable is a MEASURED 0/24 false-positive rate across the public games; it blocked two attempts and predicted a specific production regression that the run then produced. Ports write as the mechanic's CONTROL SCHEME plus the entities it cannot do without, requiring BOTH members of a pair. Probe detection (one shared action) opens m0r0, the single largest gap. PARKED with the limit named: lp85's mechanic appears at LEVEL 2 and dispatch decides at L0.
commit: [b3c92a8, e6e4ae5, 4d26d25, 7d2b57c, 755dfad, 1d1c00e, 9fdd6bd, fecdf4f, 2b51a9b, 08050a4, 9e4cac6, c67db8e, c0b58c3, 1b94260, e0534c3, f5eb06d]
date: 2026-08-25
---

# R99 — detection dispatch: shipping the adapter depth

> Two months of adapter work (R56–R84) reached 0.3296 on the script25 scoreboard while the
> submission card sat at 0.0566, because `script25.py` selects an adapter by `game_id`
> substring and the 110 private games carry no id we know. This round moves that depth onto
> the card by recognising each mechanic FROM THE FRAME.

## The gap, measured

Both cards measured the same afternoon on ceph-build, 25 games each, in parallel:

```
card (--agent chained)     0.0566     27 levels
adapter ceiling            0.3296     87 levels
```

Three games the adapters CONQUER (ft09, m0r0, ls20 — all 1.0000) scored zero or near-zero on
the card; lp85 (8 levels) and su15 (6) did not clear a single level there.

## What made the port cheap, and what did not

⛔ The obvious reading of "quarantined by design" is that the adapters cheat and would need
rewriting. **Measured false.** Every adapter's entry point takes no game identity —
`ft09.Adapter.__init__(giveup)`, `ls20.Adapter.__init__()` — and the only `GAME_ID` references
under `adapters25/` are the registry and one comment. The AST lint already forbids importing
anything but stdlib, `admorphiq.kernels` and `adapters25.base`.

So the port is a DISPATCH change: `detect(frames)` on `GameAdapter`, and dispatch by detection.

⚠️ But frame-only is not general, and that is the whole difficulty. ft09's first detector —
"does ring discovery find a ring" — false-positived on **9 of 24** public games.

## The gate

A detector ships only at **0/24 false positives** (`scripts/detector_falsepos.py`). It is a
measurement, not a precaution:

* ft09 needed two narrowing passes (click-only → 4/24; one COMPLETE 8-cell ring → 0/24).
* sb26 sat at 2/24 and was refused. It reached the measurement box anyway (a sync tarball
  carries the working tree, not the index) and the full-25 run produced **exactly** the
  predicted regression: s5i5 0.0278 → 0.0000, while sb26 gained 0.7664.

The trade-off, stated rather than asserted away: on the public 25 that unsafe detector is
strongly net-positive. It stays out because **the public 25 are a proxy for 110 games we cannot
see**, where a misfire costs invisibly — no s5i5 line appears to warn us.

## How a detector is written

**The mechanic's CONTROL SCHEME, plus the entities it cannot do without.** Where the controls
are unique the entities are a formality; where they are shared the entities decide. What does
the work is requiring BOTH members of a pair.

```
ft09  clicks only          + one COMPLETE 8-cell ring (a 3x3 minus its centre — the definition)
ls20  movement only        + avatar, goal, carried token and goal preview all parse
sb26  clicks + confirm     + a portal-sort board  (controls: nothing to walk, so pick/place/undo)
      + undo, no movement
su15  clicks + undo        + fruits AND goal disks  (a delivery puzzle needs both)
re86  move + cycle-select  + a selection marker AND target gates
tr87  movement only        + THREE rule bands, a static source bar, an editable target bar
sk48  move/undo/click      + an arena AND snakes on BOTH sides of the divider
r11l  clicks only          + creatures with legs AND target nests
```

⛔ **Never ask the SOLVER whether it copes.** sb26's first detector asked `simdfs_plan` to parse
the board, reasoning that a mechanic whose engine can plan is present by definition. The engine
plans on s5i5 and sc25 too. A detector built on "my solver did not refuse" inherits the solver's
permissiveness — a property a solver may have and a detector may not.

The last five ports needed no narrowing pass at all once this was written down.

## Probe detection

Some mechanics are not in a still frame. m0r0 grounds its player colour from what MOVED, and a
static colour-searching stand-in resolves a "maze" on **18 of 25** games.

```
static (colour search)                18/25 candidates    0 actions
one probe: colour + maze parses        2 (ka59, m0r0)     1 action
+ the mechanic's MIRROR PAIR           1 (m0r0)           1 action
```

`detect_probed(before, after)` joins the contract. The dispatcher issues ONE shared probe and
offers the pair to every probe detector, so the cost is one action however many adapters read
it. ⚠️ Probe the axis being mirrored: a VERTICAL probe leaves m0r0 and ka59 identical
((-5,0) and (-3,0)); the horizontal one separates them ((0,-5) with (0,+5) against (0,-3)).

**The probe costs nothing**: m0r0 solves 6/6 in 199 actions fresh and 198 after a probe.

## What is parked, and the limit it names

⛔ **UNPARKED 2026-08-26 — the finding was right and the instrument was wrong. See below.**

lp85 is the largest remaining gap and resists both forms. Statically no threshold exists — its
rotation-button finder returns 3 where ft09 returns 12 and s5i5 returns 2, so lp85 sits BETWEEN
its rivals. And a click probe changes zero cells, because ⛔ **the ring mechanic appears at LEVEL
2** while dispatch decides at L0, where the board is a rare-colour click puzzle with no rotation
buttons at all.

**First-frame dispatch cannot see a mechanic that only appears at a deeper level.**

This is also why the probe worked for m0r0 and not here, which matters because the two look alike
from a distance: **m0r0's probe needs no aim.** A direction key acts on the whole board. A click
probe must choose WHERE to press, and choosing correctly requires already knowing the mechanic.

## The card, and measuring it as shipped

⚠️ `--agent detect` and the notebook are different configurations — a live LLM backend and the
runner's `GF_GIVEUP` against a dead LLM callable and the deployed default — so the benched number
could not be quoted for a submission without checking. `--agent kaggle_detect` builds the shipped
artifact exactly, and per game the two agree: **0 differences** across every game both runs
finished.

⛔ **That check MISSED one axis, and the miss is instructive.** The deployed wrapper sets
`os.environ.setdefault("GF_GIVEUP", "8000")`, which RESPECTS a value already in the environment —
and the measurement runner exports `GF_GIVEUP=100000`. So both the benched and the shipped runs
inherited 100,000, and comparing them could never have revealed it: **a comparison is only as good
as the axis it varies.** The tell was in the Kaggle server run all along — cn04 clearing L1 at
56,048 actions locally while the server gave it 9,358 and zero levels.

Re-measured with the environment variable UNSET, i.e. the true deployed 8,000 (`TRUESHIP`):

```
25 games, mean 0.2772 — IDENTICAL. One game differs at all:
cn04   giveup 100k: 0.0000 / 1 level      giveup 8k: 0.0000 / 0 levels
```

The level is lost and the SCORE is not, because RHAE squares efficiency: a level cleared in 56,048
actions rounds to zero anyway. **0.2772 stands as the shipped number** — but it stands by
measurement, not because the check that was supposed to establish it did its job.

```
card                0.0566
detection dispatch  0.2772      4.9x, zero regressions, 84% of the way to the ceiling
adapter ceiling     0.3296
```

**Final, in the SHIPPED configuration, all 25 games**: `--agent kaggle_detect` reads **0.2772**, and
`scripts/benched_vs_shipped.py` compares **25 of 25 games with 0 differences**. The dead LLM callable
costs nothing — the signature-routing path reaches the same result as a live backend, consistent
with the v1 notebook's own record that the LLM contributed +0.004%p there. This is the number that
may be quoted for a submission.

Every port lands EXACTLY on its ceiling, which is what says the move was lossless: the adapter
selected by frame evidence scores what it scored when selected by `game_id`.

⛔ One measured trap: a sync carrying only `src scripts tests notebooks kaggle` produced
`No module named 'agents'` and **0.0000 on all 25 games** — the shipped wrapper needs the official
`ARC-AGI-3-Agents/` directory. That reads exactly like a broken card and is not one.

## Build provenance

`kaggle/build_and_push.sh` and `kernel-metadata.json` land WITH the card, because the 0.20 card
could not be rebuilt from this repository — no kernel-metadata on any branch, no push command, no
mapping from dataset version to commit. The script stamps the commit inside the dataset and polls
the file listing before pushing the kernel, since `datasets version` returns before the files are
served. `--submit` is a flag, never the default.

Related: [[../lessons/adapter_port_is_a_dispatch_change_20260825]],
[[../lessons/adapter_port_progress_20260825]],
[[../lessons/submission_not_reproducible_20260825]],
[[../lessons/submission_build_defects_20260826]],
[[../lessons/deployment_path_is_not_the_measured_path_20260826]],
[[../lessons/instrument_validity_20260825]], [[r98_flow-deflection]].

## Why the campaign stops at nine (2026-08-26, measured)

The obvious next move is to keep porting: the ceiling is 0.3296 and the card is 0.2772, so 0.0524
is still on the table. ⛔ **The arithmetic says stop.**

```
game     gain/25    at risk if hijacked
lp85      0.0279          0.0001      (already PARKED — mechanic appears at L2)
sp80      0.0057          0.0000
g50t      0.0043          0.0000
tn36      0.0037          0.0006
…twelve more, each below 0.002…
cd82      0.0013          0.0379      <-- the card's single largest asset

every remaining port, summed        +0.0524
losing cd82 to one wrong detector   -0.0379
```

**One mistake costs what the entire remaining campaign gains.** With lp85 parked, the largest
available port is sp80 at **+0.0057**, while cd82 alone carries **0.0379** of the mean.

The risk is not hypothetical in either direction:

* sp80, cn04, m0r0 and cd82 all share the action signature `[1,2,3,4,5]` plus clicks, so a detector
  written for one of them starts out unable to exclude the others;
* this round already watched it happen — sb26's parser-only detector took s5i5 from 0.0278 to
  0.0000 in a full-25 run;
* and cd82's 0.9463 does not come from an adapter at all. It comes from `ring_paint` inside
  `world_model_agent`, which is on the FALLBACK path — so a detector that fires on cd82 does not
  merely mis-solve it, it takes the game away from the solver that already conquers it.

⛔ **From here the downside of a wrong detector exceeds the upside of a right one.** The campaign
stops at nine ports. Further depth should come from raising the CEILING (deeper levels in the
adapters) or from transfer work on the private set, not from squeezing the last 0.05 out of
dispatch.


## Why the submission takes hours, and the budget risk it exposes (2026-08-26)

Submitting a code competition re-runs the notebook server-side over the HIDDEN games, and our
card is slow where it fails. Measured from the 25-game server run:

```
25 games      48.4 minutes, 148,018 actions, 5,920 per game
110 games     ~651,000 actions, ~213 minutes projected
```

The submission had been pending 3h37m when this was worked out, against a 3h33m projection —
i.e. right on time, not stuck.

⚠️ **The shape of the cost is the finding.** Games we SOLVE are cheap; games we fail burn the
whole budget:

```
ft09    88 actions (solved)      cn04   9,358 actions (0 levels)
sb26   170 actions (solved)      sp80  10,165 actions (1 level)
m0r0   199 actions (solved)      vc33   9,631 actions (1 level)
```

So runtime scales with how many games the card CANNOT solve — and on 110 unseen games that
fraction is higher than on the 25 we tuned against. At 10,000 actions each the projection
approaches the **9-hour limit**.

I suggested giving up early on games the card cannot solve, on the grounds that it costs nothing
— they score zero anyway — while buying back hours. ⛔ **The data refutes that.** Where levels
were actually cleared, by cumulative actions:

```
cn04  L1 cleared at 56,048 actions        vc33  L1 3,656, L2 at 7,418
sp80  L1 cleared at  2,342 actions        tu93  L1   696
```

```
give up at   500 actions -> 6 levels lost (cn04 re86 sp80 tu93 vc33)
give up at 1,000 actions -> 4 levels lost
give up at 4,000 actions -> 2 levels lost (cn04 vc33)
```

**cn04's first level lands at 56,048 actions.** Every threshold I would have proposed kills it,
and "it is already zero there" was simply false — those levels are not zero.

⚠️ And the deeper objection stands: a level cleared late may be late because the GAME is that
hard, not because the agent is flailing. Nothing in our data separates slow progress from a
genuine wall, and no give-up rule can be honest until something does. Plausible signals exist
(frontier exhaustion, state-hash stagnation) but ⛔ none has been measured to discriminate.

### Asked properly: does an action cap cost SCORE, not levels?

Levels are the wrong unit — RHAE squares efficiency, so a level cleared slowly is worth almost
nothing. Per level actually cleared, by cumulative actions and the score it carries:

```
   370  re86 L5  1.0000        696  tu93 L1  0.0007
   377  ls20 L7  1.0000      2,342  sp80 L1  0.0003
   438  re86 L6  1.0000      3,656  vc33 L1  0.0000
   588  re86 L7  1.0000      7,418  vc33 L2  0.0000
```

```
cap at   500 actions -> loses 1.0010 of 57.4812   ⛔ kills re86 L7, a FULL-score level
cap at 1,000 actions -> loses 0.0003
cap at 4,000 actions -> loses 0.0000
```

So both halves were half right. ⛔ The thresholds I would have reached for (500 and below) do
destroy real score. But **1,000 actions costs 0.0003 while cutting per-game runtime eightfold**,
because clearing late and scoring are nearly incompatible under a squared metric: everything
cleared past ~700 actions is already worth ~0.

⚠️ Measured on the PUBLIC 25 only. A hidden game that clears at full score around 1,500 actions
would be a real loss, and nothing here rules that out — so a cap should sit well above the
observed cliff (2,000-4,000), which still saves half to three quarters of the runtime.

### The cap, MEASURED rather than proposed

```
no cap (100,000)     25 games, 48.4 minutes, mean 0.2772
cap at 2,000         25 games,  3.0 minutes, mean 0.2772
```

**Identical score to four decimals, sixteen times faster.** Projected over 110 hidden games that
is ~213 minutes against ~13 — the 9-hour limit stops being a risk at all.

This also checked the cliff analysis itself, which was NOT guaranteed: the cliff was computed
over CUMULATIVE actions across a game's levels, while an action cap binds the game's WHOLE
budget. Those are different quantities and could have disagreed. Measured, they do not.

⚠️ Still measured on the public 25 only. A hidden game clearing at full score near 2,000 actions
would be a real loss, so 4,000 remains the safer setting — and at 4,000 the projection is ~26
minutes, which is still nowhere near the limit. The choice is between two safe numbers, not
between speed and score.


## THE SCORE: 0.18 — BELOW the card it replaced (2026-08-26 11:41)

```
55774529  detection dispatch  local 0.2772  ->  hidden 0.18
54664749  v3                  local 5.83    ->  hidden 0.20
54637991  v1                  local 1.072   ->  hidden 0.14
```

⛔ **0.18 against the previous card's 0.20.** Against the criteria fixed below BEFORE the score
existed, this is the third reading — the one the 0/24 gate and the transfer scoring were built to
prevent. It is also BELOW the range this round projected (0.19–0.94).

⚠️ Three explanations fit the number and nothing here separates them:

1. **detectors misfiring on private games** — the reading as written;
2. **games left unfinished** — the submitted kernel predates the budget cut and ran with
   `MAX_ACTIONS = 100,000` for over ten hours; a run cut short scores zero on whatever it never
   reached, and that has nothing to do with detection;
3. **a different fallback** — v3's card and this one differ in the fallback too, so 0.20 and 0.18
   are not a controlled comparison of "with ports" against "without".

⛔ Do not read the first as established. The measurement that would separate them is the same card
WITHOUT the ports, submitted under the same budget — a controlled comparison this round never ran,
because the ports and the fallback changed together.

### The tempting reading, and why it does not hold

`KaggleDetectAgent` is `DetectDispatchAgent(build_chained())`, and `build_chained()` is exactly
what v3's `KaggleChainedAgent` wrapped — same budget too. So "ours = v3 plus dispatch, therefore
0.20 → 0.18 isolates dispatch" is very tempting.

⛔ **It is false.** Five commits touched the fallback path after v3 shipped on 2026-07-14, and one
of them is not cosmetic:

```
ea3bf21  feat(R93): executable solver cores (toggle/paint) + click-xy transition fix
         harness/loop.py, harness/context.py, harness/toolcall_agent.py
```

`chained_agent.py` and `world_model_agent.py` are untouched, but the chain's SECOND member — the
`UnifiedAgent` harness — runs different code than it did in July. So:

```
v3    (Jul 14)  fallback = July harness   + July probe
ours  (Aug 25)  fallback = CHANGED harness + same probe  + detection dispatch
```

**Two things moved at once.** The −0.02 could be misfiring detectors, the harness change, or a
truncated run, and this comparison cannot tell them apart.

⚠️ Worth recording that the false reading was one sentence from being written down as a
controlled result. Checking `git log` on the fallback path took one command; asserting the
comparison would have cost the round its main conclusion.

### WHY the fallback changed: research and deployment share the harness

The five commits are all agent25 RESEARCH — measuring whether an offline model can pick tools and
write solver code:

```
f238417  R92   agent25 Kaggle bench — vLLM backend + matched OFF/ON kernel-bridge arms
683a210  R92   expose observed transitions + transition kernels to the code sandbox
d5466e6  R92   native tool-calling agent25 — select_strategy -> write_solver_code
ea3bf21  R93   executable solver cores (toggle/paint) + click-xy transition FIX
d94de32  R93   gpt-oss A/B re-test with the reasoning channel ON
```

⛔ **None of them was aimed at the card, and every one of them shipped in it.** The harness the
research extends is the chain's SECOND MEMBER, so `UnifiedAgent` changes ride into the deployed
fallback with no measurement of what they do there. `ea3bf21` in particular carries a *click-xy
transition fix*, which touches how actions are played.

That is the structural finding, and it is larger than this round: **the research axis and the
deployment axis share code, and nothing measures what a research change does to the card.** The
card drifted between v3 and now WITHOUT INTENT, which is exactly why 0.20 → 0.18 cannot be read.

⚠️ Not a claim that the harness changes CAUSED the drop — that is one of the three confounded
explanations and remains unseparated. The claim is that they were never measured against the card
at all, so their contribution is unknown in both direction and size.

### Measured at last: the harness changes contribute NOTHING

The rule written above was applied retroactively — swap in the pre-R92 harness (`37c3967`,
2026-07-11), run the 25, restore. It took 3.3 minutes:

```
July harness (pre-R92)   0.2772
current harness          0.2772
games differing at all:  0 of 25
```

⛔ **One of the three confounded explanations is eliminated.** The R92/R93 commits change nothing
the card can see, which the previous day's measurement already explains: the harness only ever
receives the seven games that score zero, and code changes inside a zero stay zero.

| explanation | status |
|---|---|
| ~~harness change~~ | ⛔ **excluded — contributes 0 on the public 25** |
| detectors misfiring on private games | ⚠️ **weakened — 0 misfires on 15 unfamiliar boards** |
| ~~run-to-run noise~~ | ⚠️ **weakened — the card is DETERMINISTIC** |
| run truncated by the budget | **open — the standing explanation** |

### The card is deterministic, so 0.18 is its value and not a draw

I raised "0.20 and 0.18 are each one sample, so the gap may be noise" and never measured it. Six
games, run twice each at the deployed configuration:

```
cd82 (0.946286, 6) x2    sb26 (0.846019, 8) x2    re86 (0.727294, 7) x2
su15 (0.436789, 6) x2    sk48 (0.277778, 4) x2    r11l (0.259423, 4) x2
```

Identical to six decimals. So re-submitting the same card under the same conditions returns 0.18
again; the number is the card's, not a draw from a distribution.

⚠️ Two limits: this shows OUR card is deterministic, not that v3's was, and some hidden games may
be stochastic in themselves (several public ones carry a `nondeterminism` signature). The gap
still needs a cause — it just cannot be dismissed as sampling.

### ⚠️ Fixed BEFORE the second score: the budget cut may LOWER it

The same runs show `cn04` clearing 0 levels at budget 4,000 where it cleared 1 at 100,000 (at
56,048 actions). Score is 0.0000 either way — consistent with the "no score lost" measurement —
but the LEVEL is gone.

So if the hidden 110 contain cn04-shaped games — cleared very late, worth almost nothing on our
scale — budget 4,000 drops them. ⛔ **The submission now running could therefore come in BELOW
0.18**, and if it does the reading is fixed here, in advance:

* **below 0.18** — late clears that score ~0 on the public 25 are worth MORE on the hidden set
  than they are here. That is the risk flagged when the budget was chosen (*"a hidden game
  clearing at full score near 2,000 would be a real loss, and the public 25 cannot rule it out"*),
  and it would mean the cap needs raising, not that the ports are wrong.
* **above 0.18** — truncation explained the first drop, and the budget cut is the fix.
* **≈ 0.18** — neither truncation nor the cap matters, and all four explanations are then spent;
  the cause is something not yet on the list.

### Misfiring, tested on the least familiar boards available

The 0/24 gate measured false positives on the SAME 25 boards the detectors were written on, which
cannot show behaviour on an unfamiliar one. `environment_files_archive/` holds an older version
hash for fifteen games — boards no detector was tuned against — so every detector was asked about
every one (`scripts/detector_falsepos_archive.py`):

```
archived r11l -> ['r11l']     archived re86 -> ['re86']
archived sk48 -> ['sk48']     archived su15 -> ['su15']
the other eleven             -> (none)

0 misfires across 15 unfamiliar boards
```

Each detector fires on its own mechanic's other version and on nothing else. ⚠️ The archive is
still the same 25 GAMES in different versions; the private 110 may be different games entirely,
and that stays untestable. The precise statement is: **on the least familiar boards we can reach,
misfiring does not happen.**

The instrument validated itself in passing — four detectors firing on exactly their own game is
the known-answer check that the recolour probe skipped.

⚠️ Zero on the PUBLIC 25 is not zero on the hidden 110: if the probe gives up more often there,
the harness carries games it never carries here. But nothing in this data lets the harness explain
the −0.02.

### Evidence for the truncation explanation: our card spends 61% MORE actions

Both runs at the same 100,000 budget, so the totals are comparable:

```
                chained (the v3 lineage)    detect (ours)
total                     42,943                69,250     +61%

cn04                           0    ->         56,048      +56,048
re86                          64    ->            588
ls20                          23    ->            377
```

⚠️ **cn04 is not a ported game**, so the extra is not the adapters playing longer. It is one of
the seven the harness receives, and under dispatch the run reaches it having already spent the
shared probe — enough to send the harness down a different path.

If the card spends 61% more actions on the public 25, it plausibly spends more on the hidden 110
too, and finishes FEWER games inside the same wall clock. That is the truncation explanation, and
this is the first evidence for it.

⛔ **WITHDRAWN — the comparison was invalid.** `per_level` records the actions spent on levels
that were CLEARED; a game that clears nothing contributes 0 no matter how much budget it burned:

```
SUBCAND1 (chained)  cn04  per_level = []                    <- cleared nothing, so 0 recorded
SHIPPED1 (detect)   cn04  per_level = [{56,048 actions}]    <- cleared L1, so it appears
```

So the "+56,048" is not our card spending more. It is our card **CLEARING a level the previous
one never cleared** — better, not slower. Both runs almost certainly burned their whole budget on
cn04; only one has it recorded.

⚠️ And the right number was available all along: the Kaggle server logs report TOTAL actions
directly.

```
2026-08-25  budget 100,000   148,018 actions / 25 games = 5,920 each
2026-08-26  budget   4,000    77,446 actions / 25 games = 3,098 each
```

I summed a partial local field instead of reading the total the server prints — the same shape as
this session's other misreadings, and the third time a conclusion was built on a column that does
not mean what its name suggests.

## How the submission will be read — fixed BEFORE the score arrives (2026-08-26)

Submission `55774529` is pending. The reading is fixed now, the way R98 fixed its model-stage
criteria before the runs, so the number cannot be rationalised after the fact.

The only prior datapoint on this competition's proxy-to-hidden transfer is **3.4%** (v3: local
5.83 → hidden 0.20). Our card is **0.2772** on a DIFFERENT and much stricter local scale, so
scaling that ratio is meaningless. What IS comparable is the previous card's hidden score:

| outcome | reading |
|---|---|
| **> 0.20** | the ports earn on the hidden set. The mechanic detectors fire on private games, which is what the 5/5 archive-version transfer predicted. |
| **≈ 0.20** | the ports never fire there — the private 110 hold none of these nine mechanics. ⛔ NOT a failure of the port: dispatch falls back, so the card cannot lose. It means the mechanic families are public-only. |
| **< 0.20** | ⛔ a detector fires on a private game and does WORSE than the fallback would have. That is the one outcome the 0/24 gate and the transfer scoring were built to prevent, and it would mean specificity measured on 24 public boards does not generalise. |

⚠️ **The middle outcome is the most likely and the least informative**, and it must not be read
as the ports being worthless: they cost nothing when they do not fire, and they demonstrably
work on boards nobody chose for them (m0r0 clears 6/6 of a version hash it never saw). It would
say the mechanic families are narrow, not that mechanic detection is wrong.

Whatever lands, ⛔ the local numbers do not move: card 0.2772, ceiling 0.3296, nine ports at
0/24, five transfer-verified. Those were measured and are not up for revision by a hidden score.

### The scales ARE comparable, so the range can be stated

The r53 page settles it: v3's proxy was on the same percentage scale — *"cd82 = 6/6 @ 97.4858"*
against our local 0.9463, *"su15 10.35"* against our 0.0935. So:

```
v3    local  5.83%  ->  hidden 0.20     transfer 3.4%
ours  local 27.72%  ->  4.75x v3's local card
```

At the same transfer that would be **~0.94 hidden**, nearly five times the current 0.20. ⛔ But
there is no ground for assuming the transfer rate carries, and it can move either way:

* **higher** — v3's 5.83% was almost entirely ONE game (cd82 at 97.49). Ours is spread across
  nine, and five of those were MEASURED to work on version hashes they were never written
  against. That is a better transfer profile, not merely a bigger number.
* **lower** — if the private 110 hold none of those nine mechanics, no detector fires and the
  card falls back to 0.0566 (5.66%), which at 3.4% is ~0.19: indistinguishable from today.

Those two ends are exactly the ">0.20" and "≈0.20" readings fixed above, now with numbers on
them. ⚠️ The estimate assumes a transfer rate measured ONCE, on a different card, so it is a
range to expect rather than a prediction.


## Instruments

Every finding above was produced by a script in the repository, because a finding whose
instrument cannot be found has to be RE-DERIVED to be re-checked — the lesson R98 paid for.

| script | what it answers |
|---|---|
| `scripts/detector_falsepos.py` | does this detector fire on its own game and NOTHING else? (the 0/24 ship gate) |
| `scripts/detector_transfer.py` | does it fire on a version hash it was never written against? |
| `scripts/detector_transfer_score.py` | and does the adapter SOLVE that version, or fire and fail? |
| `scripts/detect_compare.py` | card vs dispatch vs ceiling, per game, refusing to read an unfinished run as zeros |
| `scripts/benched_vs_shipped.py` | does `--agent kaggle_detect` score what `--agent detect` scores? |
| `scripts/gap_table.py` | the card-vs-ceiling gap that ordered the whole port backlog |
| `scripts/summary_agrees.py` | does a round's SUMMARY.txt agree with its own games/*.json? |
| `scripts/round_lookup.py` | every round-log mention of a game in DATE order, so the LATEST is unmistakable |
| `kaggle/build_and_push.sh` | the submission build — kernel source, metadata, dataset, commit stamp |
| `scripts/rounds/R98/selfcheck.sh` | the nine cheap guards, in one command |

Measurement artefacts, so the numbers reproduce without ssh access to the measurement box:
`scripts/rounds/SUBCAND1/games` (the card), `scripts/rounds/CEILING1/*/SUMMARY.txt` (the
adapter ceiling), `scripts/rounds/DETECT9/games` and `scripts/rounds/SHIPPED1/games` (dispatch,
benched and as shipped), plus `KAGGLE_SERVER_RUN.txt` from the server-side run.


## Transfer evidence, without submitting (2026-08-26)

A detector measured at 0/24 false positives fires on exactly one public board, which leaves the
question a submission actually turns on: **does it fire on a board it was never written against?**

`environment_files_archive/` holds an OLDER VERSION HASH for fifteen games — the same mechanic with
different internals, which this project already recorded as a proxy for the private set's
obfuscation (the 2026-04-21 rotation took every sprite-tag-reading brittle solver to zero).
Swapping the archived version in and asking each detector:

```
m0r0  archived dadda488   fires: True
r11l  archived aa269680   fires: True
re86  archived 4e57566e   fires: True
sk48  archived 41055498   fires: True
su15  archived 4c352900   fires: True

5/5
```

⚠️ **Verified by the LOADER LINE, not by the reported game_id.** The arcade reports the CURRENT id
(`m0r0-492f87ba`) even while serving the archived tree, so the id proves nothing; what proves it is

```
Successfully loaded game class M0r0 from environment_files/m0r0/dadda488/m0r0.py
```

which is why this project made a loader-line audit mandatory. The first reading of this probe was
about to be reported as 5/5 on the strength of the id alone.

### And they SOLVE those versions, not merely detect them

Firing is necessary but not the point — a detector that fires and then FAILS is worse than one that
never fires, because it takes the game away from the fallback that would otherwise have played it.
Scoring BOTH agents on each archived version (`scripts/detector_transfer_score.py`):

```
game   fallback              dispatch
m0r0   0.0000 (0 levels)     1.0000 (6 levels)
r11l   0.0000 (1 level)      0.2551 (3 levels)
re86   0.0833 (2 levels)     0.2273 (4 levels)
sk48   0.0000 (0 levels)     0.2778 (4 levels)
su15   0.0935 (3 levels)     0.4368 (6 levels)

mean   0.0374            ->  0.4394        11.7x on boards nobody tuned on
```

⛔ Not one HARMFUL case: the failure mode the probe exists to catch — fire, then fail — did not
occur on any of the five. m0r0 clears all six levels of a board it has never seen.

**What it establishes:** the detectors read the MECHANIC, not this board. That is the strongest
evidence obtainable without spending a submission that the ports can earn on the hidden set — and
it is exactly the test the old brittle solvers failed.

**What it does not establish:** that the private 110 contain these mechanics at all. If none does,
the card falls back everywhere and scores what the chained card scores. The ports cannot lose
anything there; they simply may not gain.

Probe: `scripts/detector_transfer.py`.


## The card ran on Kaggle, and the transfer showed up there too (2026-08-26)

Kernel v3 COMPLETED server-side over all 25 games and wrote `submission.json`. **18 of 25 clear at
least one level**, and every port carries its depth:

```
ft09    88 actions  WIN  6 levels        m0r0   199 actions  WIN  6 levels
sb26   170 actions  WIN  8 levels        cd82   109 actions  WIN  6 levels
ls20   377 actions  WIN  7 levels        re86  4009 actions       7 levels
su15  4120 actions       6 levels        tr87   503 actions       3 levels
sk48  4023 actions       4 levels        r11l  4064 actions       4 levels
```

⛔ **A claim I made here was WRONG and is corrected.** I read Kaggle's hashes as differing from ours
— `ls20-9607627b`, `tr87-cd924810`, `su15-1944f8ab` — and called that unprompted transfer. Checking
hash by hash against the local tree, **they are the same hashes**; I was comparing against the
ARCHIVE column of an earlier table. Only ONE port genuinely ran on a different board:

```
port  local      kaggle     archive    transfer evidence
sk48  41055498 ≠ d8078629   41055498   archive-scored AND a different Kaggle hash
m0r0  492f87ba = 492f87ba   dadda488   archive-scored
re86  8af5384d = 8af5384d   4e57566e   archive-scored
su15  1944f8ab = 1944f8ab   4c352900   archive-scored
r11l  495a7899 = 495a7899   aa269680   archive-scored
ft09  0d8bbf25 = 0d8bbf25   -          ⚠️ none — no other version exists to test on
ls20  9607627b = 9607627b   -          ⚠️ none
sb26  7fbdac44 = 7fbdac44   -          ⚠️ none
tr87  cd924810 = cd924810   -          ⚠️ none
```

**Five of the nine ports are transfer-verified.** The other four are not failures — there is no
second version of those games to test against, so the question is unanswerable locally rather than
answered badly. sk48 is the one port that ran on a board nobody chose for the test, and it worked.

### The four with no variant, probed by RECOLOURING — two fail

Version hashes differ in surface detail, so permuting the palette (a bijection over the used
colours: structure preserved exactly, only labels moved) is the closest stand-in available for
the four ports with no archived version:

```
ft09   own board True,  recoloured [False, False, False]   ⛔ keys on a colour VALUE
ls20   own board True,  recoloured [False, False, False]   ⛔
sb26   own board True,  recoloured [True, True, True]      OK
tr87   own board True,  recoloured [True, True, True]      OK
```

⛔ **ft09's and ls20's detectors read colour values, not structure.** That undercuts the ground I
gave those two ports: I recorded them as "the mechanic's control scheme plus the entities it
cannot do without", and ft09's *complete 8-cell ring* and ls20's *the level parses* turn out to
be tied to particular colour indices.

⚠️ Stated carefully, because a stand-in is not the real question:

* recolouring changes ONLY the palette; a genuine variant also changes layout and internals, so
  passing is **necessary, not sufficient** — sb26 and tr87 are not thereby proven to transfer;
* failing does not prove the reverse either — a private game of the same family might use the
  same colour conventions, in which case ft09's detector fires anyway.

⛔ **The probe then INVALIDATED itself.** Run against the five ports whose transfer is already
MEASURED — they fire on archived version hashes and go on to solve them:

```
m0r0   own board False   (⚠️ it has no static detector at all; probe-ported. My script did not
                          check that, so this row is my instrument's defect, not a result)
re86   recoloured FAIL   — yet fires on archived 4e57566e and clears FOUR levels there
su15   recoloured FAIL   — yet clears SIX levels on archived 4c352900
sk48   recoloured FAIL   — yet works on the archive AND on a Kaggle hash we do not have
r11l   recoloured PASS
```

**Three detectors that fail recolouring demonstrably transfer to real variants.** So recolouring
is far harsher than an actual version change: the real hashes appear to KEEP their colour
conventions, and failing this probe says nothing about transfer.

So the footing conclusion is WITHDRAWN. "ft09 and ls20 rest on palette, therefore their footing
is weaker" does not follow, because three games that rest on palette by the same test transfer
fine.

What this leaves: **recolouring is not a stand-in for a version change**, measured by checking it
against cases whose answer was already known — the check I should have run before reading its
verdict on ft09 and ls20 at all.

⛔ The script is DELETED rather than kept as a documented-invalid tool, applying the rule from the
same page the earlier one came from: *delete a probe when its question is answered, because
keeping it hides the signal from the ones that still change with the code.* Its question — is
recolouring a transfer proxy? — is answered, and the answer is no. The numbers stay here; the
script does not need to.

Three defects had to be cleared to get a run at all, all in the build script and all found by
pushing the KERNEL ONLY, without consuming a submission slot —
[[../lessons/submission_build_defects_20260826]].


## Where the next gain is, read off the Kaggle run (2026-08-26)

The server run's action counts split the card into three tiers, and RHAE squares efficiency, so the
tiers are worth wildly different amounts:

```
game    levels  actions  act/level
ft09         6       88       15     ported and EFFICIENT — the tier the metric pays for
cd82         6      109       18
sb26         8      170       21
m0r0         6      199       33
ls20         7      377       54
tr87         3      503      168
──────────────────────────────────
re86         7     4009      573     ported and SLOW — depth won, score mostly lost to the square
su15         6     4120      687
sk48         4     4023     1006
r11l         4     4064     1016
──────────────────────────────────
ar25 lp85 s5i5 wa30 tn36 lf52 vc33 sp80    4,000-10,000 act/level, effectively zero
```

⛔ **That reading was WRONG, and the per-level scores refute it.** "573 actions/level" is the run's
TOTAL actions divided by levels cleared — it counts the budget burned on levels never cleared, not
the actions spent clearing. Per level:

```
re86  L1 25/26=1.0   L3 53/86=1.0   L4 56/108=1.0   L5 97/189=1.0   L6 68/139=1.0   L7 150/424=1.0
su15  L1 L2 L4 L5 L6 all 1.0        sk48  L1-L4 all 1.0  (14/61, 31/177, 36/101, 30/103)
r11l  L1 1.0   L2 0.8403   L3 0.8920
```

Nearly every clear is **at or above the human baseline already**. The adapters are not slow; they
clear fast and then spend the remaining budget on a level they cannot clear at all.

**So the bottleneck is DEPTH, not efficiency**, and RHAE's level-index weighting says the same thing:

| game | score | why it is below its ceiling |
|---|---|---|
| sk48 | 0.2778 | 4 of 8 levels — depth |
| r11l | 0.2594 | 4 of 6; L4 costs 172 actions against a human 26 (0.0228) — depth plus one level |
| su15 | 0.4368 | 6 of 9 — depth; only L3 is below 1.0 |
| re86 | 0.7273 | 7 of 8; only L2 is below 1.0 (139 against 42) |

The efficiency headroom is **three levels in total** (re86 L2, r11l L4, su15 L3). Everything else is
already human-or-better, so squeezing actions there buys nothing.

**The next axis is depth on ports we already own** — the levels those adapters cannot clear — which
still carries no cd82-hijack risk, because it claims no new game.


## The depth axis, looked up rather than guessed (2026-08-26)

Having stopped the port campaign, the natural next axis is depth on ports we already own. Three
ticks went into picking it from ACTION COUNTS before consulting the round log, which had the answer
the whole time — and R84's scan states it in one line: *bounded frontier otherwise EXHAUSTED,
remaining lift = multi-session builds.*

Current frontier, measured (`SHIPPED1`) and then explained from the record:

```
CONQUERED (6)      ft09 1.0 · m0r0 1.0 · ls20 1.0 · cd82 0.98 · sb26 0.846 · lp85 0.6992
⛔ WALLED           sk48  L4 single-control-unsolvable, 94,921-state reachability exhausted
                   re86  L8 provably unwinnable as modelled
                   su15  idx6 — oracle VALIDATED, but four frame-only perception routes
                         measured-falsified: the merge click is 1px-unplaceable in the
                         integer 64x64 observation space (sub-pixel-perception wall)
                   g50t  L2 ghost-reachability; tr87, sc25 settled
MULTI-SESSION      dc22 wa30 ar25 vc33 bp35 sp80 · r11l L5
```

⚠️ **Two lookup mistakes worth recording**, because both cost a tick:

1. I ranked candidates by *locked level-index weight* — sk48 72%, tr87 71% — without checking WHY
   they were locked. Both are ⛔ settled with proofs, not open work.
2. I quoted su15 as reopenable on a *"lag-compensating predictor"*. That line is from **r59s10**;
   **R75** supersedes it with the sub-pixel wall. The round log carries SEVERAL entries per game at
   different dates, so finding one is not finding the current one — **search for the LATEST**.

The depth axis closes honestly here. What remains is multi-session in scale, which is a different
kind of commitment from a tick.


## What actually runs on the hidden set (2026-08-26)

When no detector fires the FALLBACK plays, and on 110 unseen games that will be most of them. So
the fallback is, in effect, the hidden card. Its solo numbers (`SUBCAND1`, 18/25 clearing, mean
0.0566), split by how it clears:

```
CHEAP first levels (agent actions vs human)
  cd82   6/55     sb26   9/18     su15  12/22     s5i5  19/20
  ls20  23/22     re86  24/26     wa30  30/71     ar25  31/32

EXPENSIVE first levels — cleared, but worth ~0 under a squared metric
  lf52   376/32   tu93   695/19   r11l   972/22   sp80  2,341/39
  vc33 3,656/7    m0r0 5,269/30   sk48 25,274/61
```

Two different problems, and they are not equally general:

* **Depth** — the fallback mostly stops at L1-L2, and RHAE weights by level index, so shallow
  clears are worth little. But getting deeper needs per-game mechanic understanding, which is
  exactly what does NOT transfer to games we have never seen.
* **Efficiency** — half the clears cost ten to five hundred times a human's actions. vc33 spends
  3,656 where a human spends 7; sk48 spends 25,274 against 61. ⚠️ **That is not mechanic ignorance
  — it is search behaviour**, and "do not spend 500x a human" is a GENERAL property in a way that
  "understand this puzzle" is not.

### Measured: the cost is REPETITION, not a big search space

I guessed vc33's 3,656 actions were a 64x64 grid sweep (4,096 cells). ⛔ Wrong:

```
vc33   3,585 clicks, 1,406 DISTINCT cells (34% of the grid), one cell clicked 186 times
sk48   1,239 clicks,   505 DISTINCT cells (12%), one cell 65 times, plus 2,800 moves
```

Neither sweeps. Both hammer the same cells dozens to hundreds of times. vc33 also logs
`[harness] target draw failed: LLM-free deployment` — goal inference is unavailable in the shipped
configuration, and repetition fills the gap.

⚠️ **This does NOT establish that the repetition is waste.** A re-click is legitimate when the
board's state changed under it — toggle and cycle mechanics are exactly that — and vc33 DID clear
on the 3,656th action, so nothing here says it could have cleared sooner. The measurement
identifies the SHAPE of the cost and no more.

### The settling measurement: EVERY click changes the frame

```
vc33   FIRST click on a cell   changed 1,406 / 1,406  (100%)
vc33   RE-click on same cell   changed 2,179 / 2,179  (100%)
```

⛔ **Not one inert click.** Re-clicking always does something, which is the signature of a toggle
or cycle mechanic — the agent is not retrying moves it has learned nothing from.

So this axis CLOSES, and it closes against the reading I gave it one tick earlier. I wrote that
efficiency was "search behaviour, not mechanic ignorance" and therefore a GENERAL property that
transfers. The measurement says the opposite: the human spends 7 actions not by clicking LESS but
by clicking RIGHTLY, and knowing which cell to click is mechanic understanding — precisely the
thing that does not transfer to unseen games.

⚠️ Measured on vc33 alone. But the direction is against the hypothesis, and a hypothesis that
needs the next game to rescue it is not one to build on.

### ⛔ That closure was PREMATURE — sk48 is the opposite regime

```
vc33   first clicks 1,406/1,406 changed (100%)   re-clicks 2,179/2,179 (100%)
sk48   first clicks    31/488   changed (  6%)   re-clicks   155/715   ( 22%)
```

**94% of sk48's clicks do nothing at all.** The two games are not variations on one behaviour;
they are different regimes:

* **vc33** — every click lands, so there is no waste to remove and the gap really is knowing
  which cell to press. My reading holds HERE.
* **sk48** — the overwhelming majority of clicks are inert, so removable waste genuinely exists,
  and "do not re-press a cell already shown to do nothing" needs **no mechanic knowledge at all**.

I closed this axis one tick earlier on vc33 alone, writing that a hypothesis needing the next game
to rescue it is not worth building on. ⛔ The sentence was right and I applied it in one direction
only: the refutation was equally single-game, and I hardened it into a conclusion anyway.

⚠️ Two games disagreeing means two games are not enough to say which regime is typical. The axis
is **reopened and unresolved**, not closed.

### Widened to eight games: the 100% regime is TYPICAL, sk48 is the outlier

```
change rate 100% — no removable waste
  tn36    44/44 ·   5/5        lf52    57/57 ·  89/89
  r11l   581/581 · 376/376     sp80    99/99 · 896/896
  vc33  1066/1066 · 1876/1876
low — waste genuinely exists
  m0r0   251/604 (42%) · 250/600 (42%)
  sk48    21/444 ( 5%) · 119/484 (25%)
no clicks at all
  tu93   cleared on movement alone
```

**Five of eight land every click.** So the axis closes after all — but on a measured
DISTRIBUTION rather than on one game, and the closure is the same one I reached prematurely and
then withdrew: for most games the gap is knowing WHICH cell to press, which is mechanic
understanding and does not transfer.

sk48 (5%) and m0r0 (42%) are real exceptions where waste exists. ⛔ But both are already PORTED,
so their adapters handle them, and a fix aimed at two games is not the general lever the axis was
being examined for.

Worth keeping visible: this axis was closed on one game, reopened by its counter-example, and
closed again by the distribution. The first closure reached the right answer for a reason that
was not yet good enough — which is not the same as being right.

### A consequence: one harness tool is INERT on five of the eight

`DeadSignatureTool` exists for exactly this metric — its docstring opens *"the squared-efficiency
(RHAE) metric punishes wasted actions harshly"* — and it works by marking an action class dead
once it has been tried six times at a state signature and **never once changed the frame**.

⛔ In the 100% regime there is nothing to mark. On tn36, lf52, r11l, sp80 and vc33 no click is
ever inert, so the tool prunes NOTHING on precisely the games whose efficiency is worst. r11l
spends 957 effective clicks on a level a human clears in 22.

The reading is not that the tool is buggy — it does what it says. It is that **frame-change
carries no information in this regime**: when everything changes the frame, "it changed" cannot
separate a useful move from a useless one.

⚠️ ⛔ That is NOT a claim that some other signal would do better. Three times today a plausible
next step was stated and then measured false. What is established is narrow and checkable: one of
the six tools cannot fire on five of eight measured games.

### The same property also prevents the harness from ever SWITCHING tools

Counting the harness's own `pick=` log across fifteen games:

```
vc33 cn04 sp80 sc25 bp35 dc22 m0r0 sk48 g50t   ->  pick=graph, ONCE each
(six others logged no pick at all — the chain's WorldModelAgent probe handled them)
```

Every game picks `graph` once and never re-decides. `world_model`, `dealias`, `paint`, `toggle`,
`llm_goal` and `deadsig` are never selected.

The mechanism is in the harness's own comment — *"finding novelty never stalls"* — combined with
the deployed stall threshold of **80** against the harness default of 12. Re-deciding requires a
STALL, and a stall requires the agent to stop finding novelty. ⛔ In the 100% regime every single
click produces a new frame, so novelty never runs out and **the stall never fires**.

So one property does both: no inert actions means `deadsig` has nothing to prune, and unending
novelty means the orchestrator never reconsiders its first pick. `graph` runs alone to the end.

⚠️ Whether that is a DEFECT is not established — `graph` may well be the right tool on those
boards, and 1,500 actions is a short window. What is measured is only that the alternatives are
never tried.

### Tested: it is the SIGNAL, not the threshold

Running the same four games at the deployed stall of 80 and at the harness default of 12:

```
              stall=80              stall=12
lf52     cleared at   376       cleared at   376
r11l     cleared at   972       cleared at   972
sp80     cleared at 2,341       cleared at 2,341
vc33     pick=graph once        pick=graph once
```

⛔ **Identical, action for action, and still zero re-decisions.** Lowering the threshold nearly
sevenfold changes nothing, because the stall never fires at ANY threshold — novelty never runs
out. The harness's own note, *"finding novelty never stalls"*, means *"never stalls at all"* in
this regime.

So stall-based re-decision is **structurally unreachable** on 100%-change games, and no parameter
reaches it. That is a stronger statement than the observation it replaces, and it was cheap to
get: one comparison against the value the harness itself defaults to.

⚠️ It still does not say the design is wrong. `graph` may be the best tool on these boards, and
nothing measured here compares it to the alternatives. What is established: the re-decision
mechanism cannot engage on these games, and the reason is the SIGNAL's nature rather than a
tunable.

### Compared: on vc33 another tool BEATS the one always picked

Forcing each tool to run alone, same 3,000-action budget (`scripts/tool_alternatives.py`):

```
vc33   toggle 2 levels   graph 1   paint 0   world_model 0   dealias 0
r11l   graph  1 level    everything else 0
sp80   nothing clears in 3,000
```

⛔ **`toggle` reaches two levels on vc33 where `graph` reaches one** — and the harness picks
`graph` every time and cannot re-decide. So the possibility I left open, that graph is simply the
right tool, is FALSE on vc33: the missing re-decision costs a level there.

⚠️ Stated precisely, because one counter-example is not a pattern:

* it appears on **one of three** games — `graph` is genuinely best on r11l, and on sp80 nothing
  clears at all;
* the window matters — vc33 normally clears L1 at 3,656 actions, so graph's single level sits
  right at the edge of a 3,000-action budget;
* ⛔ **no score was measured.** Levels are not RHAE: `toggle`'s two levels could have cost more
  actions than `graph`'s one, and this run did not record when they landed.

### In SCORE, which is the only unit that counts

Levels are not RHAE, so the comparison was redone with per-level action counts:

```
vc33/graph    1 level   L1 at 2,335 actions              score 0.0000
vc33/toggle   2 levels  L1 at 113, L2 at 143 actions     score 0.0013
```

`toggle` does not merely reach one more level — it reaches the first **twenty times faster**.

⚠️ **And 0.0013 is still essentially zero.** A human clears vc33 L1 in SEVEN actions, so even
113 scores `(7/113)² ≈ 0.004`. The harness is measurably picking the worse tool, and picking the
better one does not make this game worth anything.

So all three findings stand together, and the last one deflates the first two:

| established | |
|---|---|
| the harness picks an inferior tool on vc33 | ✓ measured |
| re-decision is structurally impossible, at any threshold | ✓ measured |
| **fixing it would raise the card** | ⛔ **no — 0.0000 to 0.0013** |

What it does establish: "the alternatives are never tried" is not harmless in general, because at
least once an untried alternative was better — twenty times better on time-to-first-level. What it
does NOT establish is that this is worth fixing for the public 25. On the hidden 110 it could
matter if toggle-shaped games are common there, and ⛔ nothing here says whether they are.

### Why none of it moves the card: the harness only ever gets the zero-score games

The chain hands over only when its `WorldModelAgent` probe gives up, and the probe gives up on
exactly the games nobody scores:

```
harness (graph) received  9 games — total score  0.0000
probe handled            16 games — total score  1.4153
```

Every point on the card comes from the probe. `cd82` 0.9463, `su15` 0.0935, `ar25` and `re86`
0.0833, `sb26` 0.0796 — all probe. The nine the harness receives (sp80, m0r0, vc33, dc22, sc25,
sk48, cn04, bp35, g50t) score **zero, all of them**.

So all three harness findings are real and all three are worth nothing on this card:

| finding | true? | card impact |
|---|---|---|
| `deadsig` inert on 5 of 8 | ✓ | 0 |
| re-decision impossible at any threshold | ✓ | 0 |
| `toggle` 20x faster than `graph` on vc33 | ✓ | 0.0000 → 0.0013 |

⚠️ The hidden 110 could differ: if the probe gives up more often there, the harness carries more
weight and these defects start to cost. ⛔ The submission is the only thing that can say, and it
has not returned.

## What the shipped card is actually made of (2026-08-26)

Splitting the 0.2772 by which layer earned it:

```
PORTS (detection)   9 games   5.8330   84%
   m0r0 1.0000 · ls20 1.0000 · ft09 1.0000 · sb26 0.8460 · re86 0.7273
   su15 0.4368 · tr87 0.2857 · sk48 0.2778 · r11l 0.2594

PROBE               9 games   1.0972   16%
   cd82 0.9463 · ar25 0.0833 · s5i5 0.0278 · wa30 0.0222 · tn36 0.0152 · lp85 0.0022

HARNESS             7 games   0.0000    0%

total 6.9302 / 25 = 0.2772
```

The day inverted the card. This morning the probe earned everything (1.4153); now the ports earn
**84%**, and the probe's own share FELL to 1.0972 because the ports took several of its games and
played them better — su15 0.0935 → 0.4368, re86 0.0833 → 0.7273.

Where the remaining room is, stated plainly:

| segment | value | headroom |
|---|---|---|
| the nine ports | 5.8330 | at their ceiling — none |
| cd82, on the probe | 0.9463 | ceiling 0.98 — nearly none |
| **the other fifteen games** | **0.1509** | ⚠️ everything that is left |

**Fifteen games together produce 0.15.** Raising the card means raising those, and today's
measurements found most of them parked, walled by proof, or multi-session in scale.

## The submitted kernel may not fit in 9 hours — and the budget change is why the next one will

At 8h30m pending, against a 3h33m projection, the arithmetic is worth doing rather than waiting.
The submitted kernel is commit `20aa652`, which predates the budget change: it runs with
**MAX_ACTIONS = 100,000**.

```
observed rate: 51 actions/sec (148,018 actions in 48.4 minutes over 25 games)

  8,000 actions/game -> 110 games    880,000 actions =  4.8 hours
 20,000 actions/game ->            2,200,000 actions = 12.0 hours   ⛔ over the limit
100,000 actions/game ->           11,000,000 actions = 59.9 hours   ⛔ over the limit
```

Eight and a half hours in means the run has already averaged past ~15,000 actions per game, and
that trajectory reaches the 9-hour ceiling.

⚠️ **Not a declaration of failure.** If the hidden games end naturally as the public 25 mostly do,
it can still finish; Kaggle holding PENDING means it is running, not that it has died.

What this does establish is that the budget change was not the optimisation it looked like. It was
written up as "identical score, sixteen times faster" — the honest reading now is that **the
submitted card may not fit the competition's own time limit, and the next one fits with room
to spare**:

```
next card (MAX_ACTIONS = 4,000) -> 110 x 4,000 = 440,000 actions = 2.4 hours
```

⛔ A measurement taken for one reason turning out to matter for a different and larger one is not
luck to be enjoyed — it means the original risk assessment (recorded as "the 9-hour limit stops
being a risk") was about the WRONG card. The card in flight never had that protection.

What makes this axis worth the measurement at all: a game the fallback ALREADY clears, at 500x a
human's cost, needs no new mechanic and claims no new game — so it carries none of the
cd82-hijack risk that stopped the port campaign.



## lp85 — the park was a single-feature verdict, and the conjunction passes (2026-08-26)

lp85 was the largest remaining gap by a wide margin: **0.6970**, against **0.6097** for the twelve
other unported games COMBINED. It was parked on a true finding — no button-count threshold
separates it (3 controls) from ft09 (12) and s5i5 (2) — which is a verdict on ONE FEATURE, not on
the mechanic. Every shippable port in this round is a conjunction, and lp85's own `_detect`
already is one:

    click-only  AND  >=1 rotation control  AND  >=1 moving token
                AND  per colour class, #movers == #destinations

The last term is exactly the pair rule the round's ports are written to. It also makes detection
and solvability the SAME question for this adapter — a board that passes is one the solver can
finish — so the two cannot drift apart. It had never been measured.

| gate | result |
| --- | --- |
| public 25 | fires on own game, **0/24** false positives |
| archived unfamiliar boards | **0 misfires / 15** |
| shipped-path score | **0.6992 — the adapter ceiling exactly** |

Tenth consecutive lossless port. The park note stays in the docstring together with the reason it
was wrong, because the finding it rested on is still true and would otherwise be re-derived.

**The transferable rule: a park recorded against one feature is not a park against the mechanic.**
Re-read every park for which instrument produced it — this one cost 0.028 of card and sat there
because a threshold, not a conjunction, was the thing that failed.

Card arithmetic 0.2772 -> ~0.3051; the full-25 re-measure (`scripts/rounds/R99CARD/run.sh`, the
runner that unsets the three env overrides so the deployed configuration is what gets measured) is
the number that counts.

## The card MEASURED with lp85 in: 0.2772 -> 0.3051 (2026-08-26)

Full 25 on the deployed agent, `scripts/rounds/R99CARD`:

```
ft09 1.0000  ls20 1.0000  m0r0 1.0000  cd82 0.9463  sb26 0.8460  re86 0.7273
lp85 0.6992  su15 0.4368  tr87 0.2857  sk48 0.2778  r11l 0.2594  ar25 0.0833
s5i5 0.0278  wa30 0.0222  tn36 0.0152  lf52 0.0001
tu93 sp80 bp35 cn04 dc22 g50t ka59 sc25 vc33 all 0.0000

CARD MEAN = 0.3051   (5.4x the 0.0566 the card scored before any port)
```

Game by game against the previous full-25, exactly **one** game moves: lp85, 0.002157 ->
0.699156. Nothing else changed by so much as a digit — a tenth port with zero collateral.

⚠️ **One flagged difference was my own printout, and one is real and tiny.** The ad-hoc
comparison printed four decimals and labelled two equal-LOOKING rows REGRESSION. At full
precision `lf52` is identical (0.000131 both) and `vc33` moved **2e-06 -> 0.0** — a real loss of
two millionths, i.e. 8e-8 of card, and it belongs to the BUDGET cut (100,000 -> 4,000), not to any
port; the determinism runs at 4,000 already returned vc33 0.0 twice. This is the fourth time in
this round that a number formatted for reading was mistaken for a finding. ⛔ Print the raw value
before a difference becomes a claim.

## sp80 — a measured discriminator, port not yet written

sp80 is the next-largest gap (0.1429). Two measurements, no port yet:

* **First-frame layer count does NOT separate it.** The flow family's tell — a multi-layer
  scripted consequence from one action (sp80 22 layers, tu93 8, re86 1) — is a consequence of
  the COMMIT action, and every public game's first frame carries 1 layer except lf52 and bp35
  (2). So the family tell is not a first-frame signal, and a probe that commits is destructive.
* **Control scheme narrows to four, and R98's scale inference splits them.** `simple == {1,2,3,4,5}`
  with click gives exactly `sp80 m0r0 cd82 cn04`, of which m0r0 is already ported by probe.
  R98's `_infer_scale` then returns **sp80 = 4, m0r0 = 1, cn04 = 1, cd82 = 1**.

That is a candidate conjunction, NOT a gate result: the 0/24 measurement across all 25 games has
not been run, and a discriminator that separates four boards is not yet shown to separate 25.

**PORTED the same day, and the discriminator was not the scale.** Scale is one feature, and this
round has just paid for treating one feature as a verdict. What ports sp80 is the family's own
rule: satisfaction runs through a NOTCH — a cell a target does not hold whose left and right
neighbours it does — and R98's grounding already treats a region WITHOUT one as an obstacle rather
than a target, so a board of this family cannot lack one.

| gate | result |
| --- | --- |
| public 25 | fires on own game, **0/24** false positives |
| archived unfamiliar boards | **0 misfires / 15** |
| shipped-path score | **0.1429 — the adapter ceiling exactly** |

⚠️ **Reading in CELLS is load-bearing, and that was measured rather than assumed.** The same notch
test relaxed to be scale-free — any interior gap in a region's row, so a multi-pixel notch still
registers on raw pixels — fires on ALL FOUR (cd82 4, sp80 2, m0r0 2, cn04 2) and separates nothing.
The loosening that looks like generalisation is what destroys the discrimination.

The scale inference this needs lived in `hypothesis_select`, which the adapter quarantine lint
forbids importing. Copying it would have put its four measured traps in two places, so
`infer_board_scale` / `cellify` / `colour_regions` moved UNCHANGED into
`admorphiq.kernels.board_scale` and `grounding_flow` imports them from there — verified as one
implementation by identity, with R98's guards and 331 flow/kernel/grounding tests still green.
**R98's modelling work reached the card here for the first time.**

⛔ Also measured, and it closes a shortcut: **lp85 was the only adapter carrying its own
solvability predicate.** All fourteen remaining unported adapters have no `_detect`, so each needs
its conjunction written by hand rather than lifted.

## Card with sp80 in: 0.3051 -> 0.3108 (2026-08-26)

Full 25 on the deployed agent, `scripts/rounds/R99CARD2`. Exactly **one** game moves:
sp80, `1.3e-05 -> 0.142857`. Zero collateral, for the second port running.

```
0.0566  ->  0.2772  ->  0.3051  ->  0.3108
 card       9 ports    +lp85      +sp80
```

⚠️ **The runner that produced both of the last two cards had a defect, and it was in the
throttle rather than the measurement.** `wait -n` is an INVALID OPTION in bash 3.2, which is what
macOS ships, so `while [ jobs >= PAR ]; do wait -n; done` never blocked and all 25 games launched
at once. The second run was killed under the load at 17 of 25. Scores are per-process and
deterministic, so no NUMBER is affected — R99CARD's per-game values match the previous full-25
everywhere but lp85 — but the machine was, and a killed run could not resume. Fixed by throttling
with `xargs -P` and skipping games that already have a result, so a kill resumes instead of
restarting. ⛔ A guard that fails OPEN reports success while protecting nothing; this one had to be
run on the platform that ships the old shell to show it.

## g50t — a discriminating feature found and REFUSED (2026-08-26)

g50t is the next-largest gap (0.1071). Its control scheme narrows to three (`simple == {1,2,3,4,5}`,
no click: g50t, wa30, re86), and re86 is already ported, so only a 3-way split is needed.

A feature that makes that split exists and was measured: read in cells, g50t is the only one of the
three with a colour whose regions come in exactly two of DIFFERENT sizes — `colour 5, sizes (1, 879)`.
**It was refused.** Colour 5 is g50t's FLOOR, so the pair is a floor and a one-cell island of floor;
it separates the three boards while standing for nothing the mechanic requires. Shipping it would
be the exact move this round has twice recorded as the mistake — a threshold that happens to
separate, presented as a signature.

What g50t's mechanic actually needs is not statically legible from one frame:

```
g50t colour 9:  6 regions, sizes [1, 3, 8, 19, 24, 64]
```

The player and the goal WEAR THE SAME COLOUR and are told apart by MOTION, not appearance — that is
the perception root-cause that resolved this game's eight-lane saga, and it is exactly what a first
frame cannot show. A probe could, but the probe in the dispatch contract is one shared horizontal
action and g50t's identifying motion is the player's, which the frame does not yet distinguish.

⛔ **PARKED, with the limit named and the difference from lp85 stated**: lp85's park was a
single-feature verdict over a mechanism that WAS expressible, and it came free. This one is the
other kind — the mechanism is a motion, and no amount of static conjunction reaches it. Recording
which kind a park is, is what makes it re-examinable later instead of permanent.

## Card ladder (2026-08-26)

```
0.0566  ->  0.2772  ->  0.3051  ->  0.3108  ->  0.3145
 card       9 ports    +lp85      +sp80      +tn36
```

Every one measured full-25 on `--agent kaggle_detect`; every one moves EXACTLY the game it
ported and nothing else; every port lands on its adapter ceiling to six decimals. Twelve ports.

tn36's port carries the round's sharpest detector rule in a new place: it is written as the
mechanic's structure (>=2 opcode columns AND a run button AND a player/goal pair), **not** as
"`_parse` returned something". A detector built on *my solver did not refuse* inherits the
solver's permissiveness, which is measured here — sb26's parser accepted s5i5 and sc25.

## wa30 — the gate blocked a port that would have cost 0.7273 (2026-08-26)

wa30 is a pick-carry-drop delivery board, and its pair rule is the win condition itself: the level
wins when EVERY box sits on a goal cell, so the pad must span at least as many logical cells as
there are boxes. (`_pad_cells` caps at the box count but returns FEWER when the pad is too small,
so demanding equality demands a pad that can actually hold them — the term is real, not a
restatement.)

Written that way it measured **1/24 — it fires on re86**. re86 is already ported, so shipping this
would have put two detectors on one board, sent dispatch to the fallback, and **lost re86's
0.7273** — nearly a fifth of the entire card, to gain 0.0445. The gate is the only reason that did
not happen, and this is the second time in the round it has predicted a specific regression rather
than merely expressing caution.

The two mechanics differ exactly where a static frame is thinnest. re86's ACTION5 CYCLES which
piece is selected — so its board must show a selection marker — while wa30's ACTION5 is a context
INTERACT on a single worker, so there is nothing to select and no marker to show. That is a real
discriminator and wa30 cannot use it: the selection colour is re86's, and the quarantine lint
allows an adapter to import only `base` and `kernels`, never a sibling adapter. Hoisting a
`_SELECTION_COLOR` into a shared kernel would make one game's palette constant into a library fact,
which is the hardcoding this package exists to prevent.

⛔ **PARKED, third kind.** lp85's park was a single-feature verdict over an expressible mechanism
and came free; g50t's mechanism is a MOTION no static conjunction reaches; wa30's is expressible
and static but **the discriminating evidence belongs to another adapter**. Naming which kind is
what keeps a park re-examinable — this one reopens the moment the probe contract carries an
ACTION5 transition, since select-versus-interact is exactly what one such press would show.

## Do the NEW ports transfer? Measured on archived version hashes (2026-08-26)

The public 25 cannot answer the only question that matters — whether a detector reads the MECHANIC
or the board it was written against. The archived version hashes can, because they are the same
game re-rendered, which is the nearest thing available to an unseen private game.

```
sp80   archived sp80-589a99af   detector fires: True
tn36   archived tn36-ef4dde99   detector fires: True
lp85   no archived version — untested, and recorded as untested

sp80   fallback 0.0000 (1 lvl)  ->  dispatch 0.1429 (2 lvl)
tn36   fallback 0.0152 (1 lvl)  ->  dispatch 0.1071 (2 lvl)
```

Both fire, and both deliver on the archived board **exactly the gain they deliver on the current
one** — the detector recognises the mechanic through a re-render, and the adapter behind it solves
what it recognised. That is the evidence the 0/24 gate cannot give: the gate proves a detector does
not fire where it should not, and this proves it fires where it should on a board it was never
written against.

⚠️ lp85 has no archived hash, so its transfer is **not measured**. That is a gap in the evidence,
not a negative result, and it is recorded as such rather than assumed from the other two.

## Every port that HAS an archived version gains on it — 7/7 (2026-08-26)

The same measurement run across all eleven static ports. Seven have an archived version hash; all
seven gain, none loses:

```
m0r0   fallback 0.0000 (0 lvl)  ->  dispatch 1.0000 (6 lvl)
su15   fallback 0.0935 (3 lvl)  ->  dispatch 0.4368 (6 lvl)
sk48   fallback 0.0000 (0 lvl)  ->  dispatch 0.2778 (4 lvl)
r11l   fallback 0.0000 (1 lvl)  ->  dispatch 0.2551 (3 lvl)
re86   fallback 0.0833 (2 lvl)  ->  dispatch 0.2273 (4 lvl)
sp80   fallback 0.0000 (1 lvl)  ->  dispatch 0.1429 (2 lvl)
tn36   fallback 0.0152 (1 lvl)  ->  dispatch 0.1071 (2 lvl)

mean over 7 archived versions: 0.0274 -> 0.3496   (12.8x)
```

Every one of these boards is a re-render the detector was never written against, so this is the
closest measurable proxy for the hidden 110 that the repository can produce.

⚠️ **Read the differences, not just the direction.** re86 scores **0.2273** here against 0.7273 on
the current hash — the detector transfers and the SOLVER partly does not, which is a real limit and
is invisible if only the arrow is reported. r11l (0.2551 vs 0.2594) and m0r0 (1.0000 vs 1.0000) come
through nearly or exactly intact.

⚠️ **Four ports have no archived version and are therefore UNMEASURED on transfer** — recorded as a
gap in the evidence, not inferred from the seven that were.

## re86's transfer loss is CAPABILITY, not budget — and it argues for the 4,000 cap

re86 is the one port whose solver clearly does not follow its detector across a re-render (0.7273
live, 0.2273 archived), so it is the one worth taking apart. Three measurements on the archived
board `re86/4e57566e`, each a (value, budget, env) triple:

```
budget  5,000, giveup 4,000    4/8 levels, 0.2273, stopped at 4,015 actions
budget 30,000, giveup 4,000    4/8 levels, 0.2273, stopped at 4,015 actions   <- give-up, not budget
budget 30,000, giveup 30,000   4/8 levels, 0.2273, spent ALL 30,000 actions   <- capability, not give-up
```

The adapter spends thirty thousand actions on the archived board and clears nothing beyond level 4.
Its live 7/8 comes from the same code in ~4,009 actions. So the loss is a genuine capability gap on
that board's level 5 — not a budget artefact and not a give-up calibrated to the live board, which
were the two cheap explanations and are now both excluded.

**That is also the first evidence for the 4,000-action cap from something other than the public 25.**
The cap was chosen on public-25 cumulative-action data with the gap stated openly — *a hidden game
clearing at full score near 2,000 would be a real loss, and the public 25 cannot rule it out*. Here
a transfer proxy says the extra 26,000 actions buy exactly zero. One board is not the hidden 110,
but it is one real observation where the earlier decision could have been wrong and was not.

⚠️ Recorded en route, twice: **`ARC_ENVIRONMENTS_DIR` is still unread** — a run with it set loaded
`environment_files/re86/8af5384d` regardless, which is the trap CLAUDE.md already names. Version
swaps must move the directory, and must restore it from a shell `trap` so a timeout cannot leave the
repository holding an archived board.

## The dispatch campaign is essentially DONE — the adapter ceiling is now the binding constraint

Card 0.3162 with thirteen ports. If EVERY remaining game were ported, and each landed exactly on
its ceiling as all thirteen have, the card would be **0.3296**. The whole remaining campaign is
therefore worth **+0.0134**, against the **+0.2596** already taken.

```
game     card   ceiling     gap   card gain
g50t   0.0000    0.1071  0.1071      0.0043   PARKED (mechanism is a motion)
wa30   0.0222    0.0667  0.0445      0.0018   PARKED (evidence belongs to re86)
vc33   0.0000    0.0357  0.0357      0.0014   see below
cd82   0.9463    0.9800  0.0337      0.0013
cn04   0.0000    0.0309  0.0309      0.0012
dc22   0.0000    0.0272  0.0272      0.0011
ka59   0.0000    0.0205  0.0205      0.0008
lf52   0.0001    0.0182  0.0181      0.0007
bp35   0.0000    0.0145  0.0145      0.0006
tu93   0.0000    0.0028  0.0028      0.0001
                                     ------
                                     0.0134   of which 0.0075 is already parked
```

**vc33 is not worth attempting, and the reason is on this page already.** Its mechanic, as its own
adapter records it, is the *rare-colour click family* — "click the rare thing". That is precisely
what lp85's L0 face was judged on: *too generic to claim without hijacking four click-only rivals*.
vc33 shares the click-only scheme with five games, FOUR of them now ported (ft09, lp85, r11l,
tn36). Risking four live ports for **+0.0014** of card is not a trade worth making, and the board's
one distinctive fact — two identical colour-9 regions, one live — is a property of that BOARD, not
of a mechanic. Writing a detector on it would be reading the board, which is the thing this whole
campaign is built to avoid.

⛔ **So further card gain has to come from raising ADAPTER CEILINGS, not from dispatch.** Twelve of
the twenty-five games have a ceiling under 0.15, and seven of those are ceilinged at a single level.
That is depth work — the multi-session builds already spec'd — and it is a different kind of effort
from the last two days'. The dispatch lever gave 5.6x and is now down to its last one-twentieth.

## The 0.3162 card is VERIFIED as shipped (2026-08-26)

Five adapters changed since the last verification (lp85, sp80, tn36, sc25, plus the kernel move
under grounding_flow), so the card was re-checked rather than assumed:

```
full suite            1752 passed, 1 skipped
guards                all ten hold
benched --agent detect          0.3162
shipped --agent kaggle_detect   0.3162     differing games: 0 of 25
```

The two are genuinely different configurations — the bench builds a live LLM backend and takes the
runner's `GF_GIVEUP`; the notebook gets a dead LLM callable, so the harness routes by frame
signature, and takes the deployed default. They now run through ONE runner with an `AGENT` variable,
because measuring them with two runners is how a "shipped" measurement once silently ran at budget
100,000.

This makes 0.3162 a submission candidate whose shipped behaviour is measured rather than inferred.
⛔ Submitting is the user's decision and one submission is already pending; nothing is pushed here.

## The next lever, with its number: R98 already clears a level sp80's adapter cannot

The dispatch campaign is down to +0.0134 total. The depth lever's first target is measured and it is
bigger than every remaining port put together:

```
sp80 adapter (on the card)   2 of 6 levels, 4,000 actions SPENT, 0.142857
     level 1   10 actions vs 39 human   score 1.0
     level 2   16 actions vs 58 human   score 1.0
     level 3   never cleared — the other 3,974 actions go here

R98 depth_walk (same game)   idx0, idx1, idx2 all CLEARED, 107 actions total
     idx2 (= level 3)        47 actions
```

The adapter is not giving up and is not budget-starved in the usual sense: it spends its entire
allowance on level 3 and clears nothing, while R98's pipeline clears that same level in 47 actions.
Both of the adapter's cleared levels are already SUPER-HUMAN, so this is a capability gap on one
level, not a weak solver.

**Worth**: level 3 at score 1.0 takes sp80 from 3/21 to 6/21 — `0.1429 -> 0.2857`, **card +0.0057**.
That is more than four times the largest remaining port and about 40% of the entire remaining
dispatch campaign.

⛔ **The blocker is structural, not algorithmic.** R98's pipeline is 3,738 lines across five
`hypothesis_select` modules (schema / grounding / propagate / verifier / compiler), and the
quarantine lint lets an adapter import only `base` and `kernels`. The `board_scale` move showed the
shape of the answer — relocate the pure part, keep one implementation — but three questions have to
be settled first and none of them is a one-tick job:

1. Which part is actually pure? `propagate_flow` is a simulator parameterised by a response table,
   which is math; `grounding_flow` reads boards, which is perception; `compiler_flow` emits plans.
2. Does the kernels' own doctrine admit it? That package says no game semantics travel with the
   math — and a flow RESPONSE TABLE is a family model, not one game's constant, so this is arguable
   in both directions and should be argued explicitly rather than assumed.
3. `kernels` already carries an older, weaker flow set (`learn_flow_operators`, `simulate_flow`,
   `plan_flow_coverage`) which sp80's adapter already imports. Two flow models in one library is the
   duplication the `board_scale` move existed to prevent.

Recorded so the next session starts from a decision instead of a survey.

## Question 3 settled by measurement: it is the OLD kernel flow model that fails

The three questions blocking the sp80 depth work were "which part is pure", "does the kernels'
doctrine admit it", and "how to avoid two flow models in one library". The third is the cheapest and
it turns out to answer the other two.

Instrumenting the adapter's own `_phase` through a live sp80 run:

```
level 0   learn 2   probe 4   plan 4                                  -> cleared at step 9
level 1   learn 3   probe 4   classify 1   execute 8                  -> cleared at step 25
level 2   learn 6   probe 8   classify 2   execute 97   graph 1061    -> never cleared
```

**The flow model was learned and a plan WAS executed** — 97 actions of it — and then the adapter
fell back to graph exploration for the remaining thousand. So the failure is NOT the scope limit the
adapter's own docstring names ("when the flow model can't be learned... falls back"). It is a plan
that ran and was wrong.

That is exactly the axis R98 spent its round on. Its propagator is recorded EXACT cell-for-cell on
idx0/idx1/idx2 — the same three levels — after the instrument fixes that took its corpus from 93
cells of error to 12. The adapter's `simulate_flow` is a less faithful model of the same mechanic.

**So the work is not "move R98's game-specific machinery into a generic library".** `kernels`
already hosts a flow model (`learn_flow_operators` / `simulate_flow` / `plan_flow_coverage`), which
the adapter already imports; R98 built a measurably better model OF THE SAME KIND. The doctrine
question dissolves — a flow simulator is already admitted — and the duplication question inverts:
the point is to end with ONE flow model, the exact one, rather than the two there would have been.

⛔ Still not a one-tick job, and the honest scope is now visible: replacing a kernel that a shipped
adapter imports means re-measuring sp80's levels 1 and 2, which currently clear SUPER-HUMAN (10
actions vs 39 human, 16 vs 58). A fidelity improvement that costs either of those loses more than
level 3 gains.

## The escalation hook, verified in the code rather than asserted (2026-08-26)

⚠️ The `codex exec` review gate could NOT be run — this account is refused for
`gpt-5.3-codex`, `gpt-5.1-codex-max` and `gpt-5-codex` alike ("not supported when using Codex with a
ChatGPT account"). The safety claim was checked by reading the code instead, which for this
particular question is stronger than an opinion anyway.

**The hook is `src/admorphiq/adapters25/sp80.py:661`**, in `_execute_step`:

```python
if self._exec_pos >= len(self._exec_plan):
    if 5 in act_ids and not self._committed:
        self._committed = True
        return simple_action(5)        # commit the planned layout
    self._phase = "graph"              # committed, and STILL on this level
    return self._graph_step(grid, act_ids)
```

"Plan fully executed, committed, and we are still here" is exactly that second branch. It is the
one place the flow path concedes after a plan RAN, as distinct from the twelve other
`_phase = "graph"` sites, which are all "could not learn / could not plan".

**The safety property holds, and the mechanism is visible.** A winning commit raises
`levels_completed`, `_on_level_up` fires, and lines 375-385 reset `_phase` to `"learn"` — so the
concede branch is never reached on a level that clears. The measured trace agrees independently:
level 1 never entered `_execute_step` at all (learn 2, probe 4, plan 4), and level 2 executed 8
actions and cleared without touching `graph`.

⛔ **The "correction" recorded here an hour ago was itself WRONG, and it is withdrawn.** It claimed
`_on_level_up` restores the flow path only `if self._phase in ("learn", "probe", "plan", "classify",
"execute")`, so a concede to graph would latch the pipeline off for every deeper level, and that
sp80 is therefore "2 of 6 with the pipeline switched off from level 3 onward".

That conditional belongs to **`_on_restart`** (sp80.py:368, the GAME_OVER handler), not to
`_on_level_up`. `_on_level_up` resets `_phase = "learn"` **unconditionally**, with no test at all.
Two methods with adjacent bodies were read as one, and the whole inference was built on the wrong
one.

What that changes:

* **The latch does not exist across levels.** Every level-up restarts the flow pipeline whatever
  phase the previous level ended in, so the value of this work stays the **+0.0057** computed on
  level 3 — it was not raised, as claimed.
* **The safety property is STRONGER, not weaker.** An unconditional reset cannot fail to restore the
  path, so the "late level-up latches the pipeline off on a level actually won" risk written here is
  also withdrawn: a late level-up costs actions and nothing more.
* **The one real latch is narrower and deliberate.** On GAME_OVER, a phase of `"graph"` is kept —
  and `_on_restart`'s own docstring says why: *"Restart the flow pipeline from scratch; keep the
  fallback graph (same board)."* The board is unchanged across a game-over, so keeping the learned
  graph is the intended behaviour, not an oversight.

⚠️ This is the fifth time this round a claim came from something read rather than measured, and the
first where the misread was of CODE rather than of a number. The rule that has been on this page
since the morning — *print the raw value before a difference becomes a claim* — applies verbatim to
source: **print the enclosing definition before attributing a line to a method.** One `awk` over
thirty lines exposed it, after the conclusion had already been written up and reported.


## What the kernel flow model does not know: HAZARDS (2026-08-26)

Comparing the two flow models by what each can even represent:

```
src/admorphiq/kernels/motion.py               "hazard"  0 mentions
src/admorphiq/hypothesis_select/propagate_flow.py       16
src/admorphiq/adapters25/sp80.py                         2
```

`simulate_flow`'s docstring states its whole physics: fluid advances one cell in `fall_dir`; when
the cell ahead is blocked it spreads to both perpendicular cells and continues; a target is
satisfied on an interior hit. There is no third outcome — nothing in that model can END an attempt.

R98's `ResponseTable` opens exactly that axis (`hazard: terminate_fatal | terminate_local |
pass_through`), and R98 **CERTIFIED hazard-fatality on this very game**: two placements fill every
sink, one advances and one fails, differing only in hazard contact.

The adapter knows hazards exist and only ever mentions them to keep from masking one as HUD —
*"the counter band shares its colour with the in-play hazard, so only the EDGE-pinned test
distinguishes the HUD band from a hazard inside the play area"* (sp80.py:112-115). So it PERCEIVES
hazards and cannot PLAN around them, because the simulator it plans with has no notion of one.

**Measured on level 3**, wrapping the planners through a live run:

```
level 1 cleared at step   9   (1 planner call)
level 2 cleared at step  25   (3 planner calls)
level 3 conceded at step 139  (7 planner calls total)
    plan_flow_coverage        -> None          (no single-piece covering placement)
    plan_flow_coverage_multi  -> [(1,1),(1,1),(1,3)]   executed, committed, no advance
    plan_flow_coverage_multi  -> [(1,1),(1,3),(1,3)]   executed, committed, no advance
```

So the multi-piece planner twice found a placement it believed covering, ran it, committed, and the
engine refused to advance. That is the shape hazard-fatality predicts.

⚠️ **Supported, NOT established.** A mis-simulated flow that simply fails to cover would look the
same from here, because `plan_flow_coverage_multi` returns a move list and not the coverage it
predicted. The measurement that would settle it is a comparison of the PREDICTED satisfied set
against the spill the engine actually ran — the commit exposes the whole trajectory as frame layers,
so it is available. Named as the next step rather than assumed.

**If it holds, the cheap fix is not to relocate 3,738 lines.** It is to give the kernel simulator
the one outcome it lacks: hazard cells that end an attempt, and a `plan_flow_coverage` that rejects
placements whose flow contacts one. That is a bounded change to a kernel the adapter already
imports, and it keeps one flow model rather than landing a second.

## The settling measurement ran, and it REFUTES the hazard hypothesis

The previous entry proposed hazard-fatality as sp80 level 3's failure, labelled it *supported, NOT
established*, and named the measurement that would settle it: the predicted satisfied set against
the spill the engine actually ran. That measurement is now done, by capturing the adapter's own
target regions and the commit's animation layers:

```
COMMIT at step 138: 27 layers, flow colour 6, 6 targets, 976 wetted cells, fall (-1, 0)
   target 0  size 80   wetted  0   interior hit: no
   target 1  size 80   wetted  0   interior hit: no
   target 2  size 80   wetted  0   interior hit: no
   target 3  size 64   wetted  0   interior hit: no
   target 4  size 80   wetted 64   interior hit: YES
   target 5  size 96   wetted  0   interior hit: no
level 3 conceded at step 139
```

**One target of six, and five with ZERO wetted cells.** Hazard-fatality predicts full coverage that
still fails; this is nothing like it. The planner believed the placement covering and the real flow
reached one target — a propagation-fidelity failure, not a missing terminal condition. ⛔ The hazard
reading is withdrawn for this level. (It remains what R98 certified about the FAMILY; it is simply
not what breaks here.)

A second candidate was raised and refuted in the same pass. The learned fall direction on level 3 is
`(-1, 0)` — upward — and the adapter's own code warns that entering a deeper level while the previous
level's winning spill is still animating fits the wrong direction. But per level:

```
level 1   fall (1, 0)    16 source cells
level 2   fall (-1, 0)   16 source cells   <- CLEARS with the upward direction
level 3   fall (-1, 0)   48 source cells
```

Level 2 wins with `(-1, 0)`, so upward is not itself the error.

What the same numbers DO show is that level 3 is a different size of problem: **48 source cells
against 16, and six targets.** Three times the source, and the multi-piece planner returned exactly
three moves. Whatever the propagation error is, it appears where one spill has to serve six targets
rather than one or two.

⚠️ Root cause NOT yet named, and deliberately not guessed at. What is established: the failure is in
how the flow propagates, the board is 3x the source of the levels that work, and neither hazards nor
a stale fall direction explains it.

## An instrument that fails its own control — stopped before it became a conclusion

Chasing sp80 level 3's propagation error produced a promising lead: the adapter passes
`frozenset()` as `static_blocked` at BOTH planner call sites (sp80.py:470 and sp80.py:640), so the
simulator plans as though the board holds no static obstacles at all — only the movable pieces
block flow. `plan_flow_coverage_multi`'s own docstring says the goal fires when `simulate_flow`
over "``static_blocked`` plus all placed pieces" satisfies EVERY region.

Replaying `simulate_flow` on the committed placement:

```
static_blocked = frozenset()   (what the adapter passes)   ->  4 of 6 targets
static_blocked = the board's real obstacles (452 cells)    ->  3 of 6 targets
what the engine actually did                               ->  1 of 6 targets
```

⛔ **All three disagree, and that convicts the INSTRUMENT before it convicts the adapter.** The
planner's goal fires only at 6 of 6, so the placement it accepted must score 6 of 6 under ITS
inputs. My replay scores 4 — therefore my inputs are not the planner's, and nothing about the
planner can be concluded from this replay yet.

One reconstruction error was already found and fixed mid-measurement, which is why the numbers moved:
pieces were first rebuilt from `self._exec_pieces`, giving **336** cells, when the board holds
**80**. `_execute_step` assigns `self._exec_pieces[idx] = _cells_of_color(grid, self._movable_color)`
— every cell of the movable colour, written into ONE index — so that array is not a per-piece
position record and must not be read as one. Reading the placement off the board fixed that and the
prediction still does not reproduce the planner's verdict, so at least one more input differs
(stale targets from a different call, the source set, or the moment the placement was sampled).

**The control this measurement needs, and did not have**: wrap `plan_flow_coverage_multi` to record
its actual arguments and returned plan, then replay `simulate_flow` on exactly those. If the replay
does not score 6 of 6 on the planner's own inputs, the replay is wrong — not the planner.

⚠️ Recorded rather than pushed through, because this round has already paid five times for a claim
built on something read rather than measured. The lead itself (empty `static_blocked`) is still
worth testing; it is simply not tested yet.

## The control passed, and then the answer was clean: the two flow models disagree COMPLETELY

The control named last entry — replay `simulate_flow` on the planner's OWN recorded arguments and
its returned plan — was built and run. It passes on all three planner calls:

```
call 0  plan_len 5  pieces [48,48,80]     targets 3  -> replay 3/3   CONTROL OK
call 1  plan_len 3  pieces [64,176,96]    targets 3  -> replay 3/3   CONTROL OK
call 2  plan_len 3  pieces [64,80,96,96]  targets 3  -> replay 3/3   CONTROL OK
```

The replay reproduces the planner's verdict exactly, so the instrument is valid and its readings can
be used. With that established, the same instrument scored the REAL spill against the planner's own
targets, at the commit:

```
predicted   3 of 3 satisfied
actual      0 of 3 — ZERO wetted cells in ANY target, on both commits (560 and 976 wetted overall)
```

**That is the finding.** Not hazards, not missing obstacles, not target counting: the kernel's flow
model and the engine's flow disagree completely on this board. The simulator sends water into all
three targets; the engine puts none in any of them.

⚠️ **A correction to my own earlier reading, which the valid instrument exposed.** The "1 of 6
targets" figure reported two entries ago came from `_detect_targets`, the SINGLE-piece path's
finder, which returned six regions. `_build_multi_plan` sees the same board as three targets, and it
is right to: `_downstream_regions` returns `[(11,80),(11,80),(11,80),(8,64),(8,80),(9,96)]` and
`_piece_colors == {8, 9}` — a colour joins that set only after a click probe SAW the selected region
jump onto it. So colours 8 and 9 are confirmed movable pieces, and `_detect_targets` was counting
movable pieces as targets. The real target set is the three colour-11 regions, and the real spill
wets none of them.

**This is what R98's propagator was built for and measured against** — exact cell-for-cell on
idx0/idx1/idx2, which includes this level. The fidelity gap is now established rather than
hypothesised, and it is total on this board rather than marginal.

## ⛔ WITHDRAWN: "the models disagree completely" was measured with the wrong colour

The previous entry's headline — predicted 3 of 3, actual 0 of 3, **zero** wetted cells in any target
— is false and is withdrawn. It counted a target as wet only where its cells carried the FLOW
colour (6). Targets do not render that way. Their colour histogram across the commit's layers:

```
commit 1 (22 layers)   target 0 {11: 1552, 13: 160, 12: 48}
                       target 1 {11: 1552, 13: 160, 12: 48}
                       target 2 {11: 1232, 13: 480, 12: 48}
commit 2 (27 layers)   target 0 {11: 1200, 13: 960}
                       target 1 {11: 1280, 13: 880}
                       target 2 {11: 1600, 13: 560}
```

Colour 11 is the target's own appearance; **13** is what its cells take while the spill runs, and 12
appears too. Colour 6 never does. So "zero wetted cells" measured the absence of a colour targets
never wear, not the absence of water.

The contradiction was visible in the same run and I wrote past it: predicted water was a strict
SUBSET of actual water (overlap 203 of 203 predicted, 560 actual), and the prediction satisfies all
three targets by the control — so the actual water *had* to reach them. A reading that cannot be
true given the other readings in its own output is a reading to re-take, not to report.

**What survives, and it is little:**

* the control is still valid — replay on the planner's own inputs reproduces its 3/3 verdict;
* the engine wets everything the simulator predicts and 357 cells more (commit 1), so the kernel
  model UNDER-spreads rather than sending water elsewhere;
* the targets do receive colour 13 during the spill — **the flow reaches them**;
* and the level still does not advance.

⚠️ That last pair points back toward the reading withdrawn two entries ago (coverage happens, the
level fails anyway) — but what colour 13 versus 12 versus 11 MEANS is not established, and I am not
going to swing a third time on a guess about it.

**The control that settles it**: compare the target colour histogram on a commit that WINS (levels 1
and 2 both clear) against this one that does not. Satisfaction has a signature in that difference or
it does not, and either way the answer comes from a level whose outcome is known.

⛔ Sixth time this round a claim came from a field read for something it does not record. The rule
was already on this page in three forms. Writing it again is not the fix; running the control BEFORE
the headline is.

## The control answered: the gap is SATISFACTION, not propagation

One instrument, two commits whose outcome is known — level 2 clears, level 3 does not — and the
target cells' colour histogram across each commit's animation layers:

```
WON   level 2, 22 layers   target 0 {11:1552, 13:160, 12:48}
                           target 1 {11:1552, 13:160, 12:48}
                           target 2 {11:1232, 13:480, 12:48}

LOST  level 3, 27 layers   target 0 {11:1200, 13:960}
                           target 1 {11:1280, 13:880}
                           target 2 {11:1600, 13:560}
```

(The histograms are complete: 1552+160+48 = 1760 = 80x22, and 1200+960 = 2160 = 80x27.)

**Colour 12 appears in all three targets on the commit that WINS and in none of them on the commit
that LOSES.** Colour 13 goes the other way — the losing commit has MORE of it (44%, 41%, 26% of
cell-layers) than the winning one (9%, 9%, 27%). So 13 is water passing through a target, and **12
is the target being satisfied.**

That relocates the fidelity gap precisely. It is **not propagation** — the engine wets everything
the kernel predicts and more, and the flow plainly reaches all three targets on the failing level.
It is **satisfaction**: `simulate_flow` counts a target satisfied when fluid enters a cell whose two
perpendicular neighbours belong to the same target (an "interior hit"), and on level 3 the engine
gives that board水 through every target while marking none of them filled. The kernel's satisfaction
rule is not the engine's.

⚠️ **And one more correction to last entry's numbers.** The commit reported there as "commit 1"
({11:1552, 13:160, 12:48}, 22 layers) is the level-2 **WINNING** commit, not a level-3 failure — the
capture keyed on `_committed` while attributing the level from a counter that had not yet advanced.
The comparison above re-takes both readings from one run with the outcome recorded alongside each,
which is what made the difference legible at all.

**Next**: the same signature should be checked on level 1's winning commit, and then the kernel's
interior-hit test replaced by one that predicts colour 12 rather than mere entry. That is a change
to `simulate_flow`'s satisfaction predicate alone — the propagation it already gets right — which is
a far smaller thing than relocating R98's 3,738 lines.

## Two wins, two losses, and a staleness bug caught in between

The previous entry rested on ONE win against ONE loss. Widening it to every commit exposed an
instrument fault first: the spy kept the last planner call's targets in a variable that outlived the
level, so the SACRIFICIAL spill fired during `learn` was scored against the PREVIOUS level's target
cells. Those rows looked spectacular and meant nothing — a "level 2 lost" commit whose target 0 read
`{12: 1760}`, 100% of the very colour under investigation, on cells belonging to level 1.

Guarding the capture so a commit is scored only when a planner call has run on THAT level leaves
four valid commits:

```
WON   level 1, 2 targets   {11:1360, 13:160, 12:80}   {11:1200, 13:320, 12:64, 6:16}
WON   level 2, 3 targets   {11:1552, 13:160, 12:48}  x2   {11:1232, 13:480, 12:48}
lost  level 3, step 127    {11:1200, 13:720}  {11:1280, 13:640}  {11:1600, 0:320}
lost  level 3, step 138    {11:1200, 13:960}  {11:1280, 13:880}  {11:1600, 13:560}
```

**Colour 12 appears in every target of both wins and in no target of either loss** — five target
instances on the winning side, six on the losing side. The reading survives the widening, which the
single pair could not have established.

So: `13` is water passing through a target, `12` is the target satisfied, and on level 3 the engine
runs water through all three targets without filling any. The kernel's `simulate_flow` counts an
"interior hit" as satisfaction; the engine does not.

⚠️ The staleness fault is worth keeping in mind beyond this measurement: **a spy variable that
outlives the thing it describes reports the previous subject with full confidence.** It produced the
most striking number in the whole run (`{12: 1760}`) and that number was pure contamination.

## Colour 12 is an END-STATE marking, and execution does not drift

Two more measurements close out the alternatives.

**When and where colour 12 appears.** On both winning commits it occupies exactly ONE layer — the
LAST one (layer 19 of 20; layer 21 of 22) — covering 48-80 of a target's 80 cells:

```
WON level 1  target 0  layer 19: 80 cells of 12    target 1  layer 19: 64 cells
WON level 2  targets   layer 21: 48 cells each
```

So 12 is not a per-tick event but the **end-of-animation marking of a satisfied target**. That makes
it a ground-truth readout rather than a mechanism — and a useful one: the final layer of any commit
says exactly which targets ended up satisfied, which is information the adapter currently throws
away (it concedes to graph and learns nothing from the failure).

**Execution does not drift.** Comparing the placement the planner planned against the board at the
commit:

```
WON  level 2, step 25    planned 176 cells   actual 176   overlap 176   exact
lost level 3, step 138   planned 336 cells   actual 336   overlap 336   exact
     pieces on targets: planned 0, actual 0, on both
```

⚠️ The first run of this comparison reported "actual 80" against "planned 336" and looked like
massive drift. It counted only `_movable_color` (9) while the pieces are colours 8 AND 9 — a
multi-colour plan measured against a single-colour board. Counting every colour in `_piece_colors`
gives exact agreement. (The step-127 row reads 0 because `_piece_colors` was still empty at that
moment; it is not usable.)

**Where that leaves the fault, with six alternatives eliminated by measurement:**

| candidate | verdict |
| --- | --- |
| hazard contact ends the attempt | ⛔ refuted — coverage was not full when tested |
| missing static obstacles | ⛔ same prediction with and without them |
| target miscounting | ⛔ the multi path's 3 targets are evidence-based |
| stale/wrong fall direction | ⛔ level 2 WINS with the same `(-1, 0)` |
| propagation sends water elsewhere | ⛔ engine wets a SUPERSET of the prediction |
| execution drifts from the plan | ⛔ exact, 336 of 336 |

What remains is the satisfaction model itself: the engine runs water through all three targets
(colour 13 in every one) and marks none of them filled (no colour 12), while `simulate_flow` scores
all three satisfied on its interior-hit rule.

## The distinction is RETENTION, not transit — measured on the final layer

Reading only the LAST layer of each commit, per target:

```
WON  level 1   {12: 80}              {12: 64, 6: 16}
WON  level 2   {12: 48, 11: 32}   x3
lost level 3   {11: 80}           x3   (step 127)
lost level 3   {11: 80}           x3   (step 138)
```

**Every target of a winning commit ends holding colour 12; every target of a losing commit ends
100% its own base colour 11.** After a losing spill the targets look exactly as they did before it
— the water drains away and leaves nothing. After a winning one, part of each target stays filled.

Note the proportion: on level 2's win only **48 of 80** cells are 12 and the other 32 remain 11, in
all three targets alike. So 12 marks the retained portion of a target, not the whole region — the
32 unchanged cells read as the rim or wall around a basin.

Put beside the earlier histograms this settles what the two models disagree about. Water passes
THROUGH level 3's targets in quantity — colour 13 for 720, 960 and 560 cell-layers, MORE than either
winning commit — and none of it stays. `simulate_flow` marks a target satisfied the moment fluid
enters an interior cell, so transit and retention are the same event to it. To the engine they are
different events, and only the second one counts.

⚠️ **Measured**: 12 on the final layer of every winning target, base colour on every losing one, and
transit occurring in both. **Inferred, not yet measured**: that retention depends on the basin being
closed against the flow direction, so that rising water (`fall = (-1, 0)`) is held rather than
passing over. The test is to compare the target shapes' openings relative to the fall direction
between the levels that win and the level that does not — a shape measurement on boards whose
outcome is already known, which is the same control that produced everything above.

## Closure refuted, and the hazard reading comes BACK — on evidence this time

Two measurements, one refuting an inference of mine and one reinstating a hypothesis I withdrew.

**The closure inference is refuted.** Level 3's targets are walled against the flow exactly as the
winning levels' are:

```
WON  level 1   leading edge 12 cells -> 12 walled / 0 open   (fall (1, 0))
WON  level 2   leading edge 12 cells -> 12 walled / 0 open   (fall (-1, 0))  x3
lost level 3   leading edge 12 cells -> 12 walled / 0 open   (fall (-1, 0))  x2
```

So "the basin is open against the flow direction" is not what separates them. (The step-127 row
reads `fall (0, 0)` — the flow model was reset at that instant — and is unusable.)

**And full coverage DOES happen on the failing level.** Counting which cells ever take colour 13:

```
WON  level 1   80/80 cells ever 13   finally 12: 80, 64
WON  level 2   80/80 cells ever 13   finally 12: 48, 48, 48
lost level 3   80/80 cells ever 13   finally 12: 0, 0, 0
```

Every cell of every target is wetted on the losing commit, and none is retained.

⛔ **That reopens the hazard hypothesis I withdrew two entries ago, and the withdrawal has to be
withdrawn.** I retracted it on the reading "coverage was only 1 of 6" — which was itself the
measurement that counted a colour targets never wear. With a valid instrument the picture is:
**every target fully covered, nothing retained, level fails.** That is precisely the pattern R98
CERTIFIED on this family: *two placements fill every sink, one advances and one fails, differing
only in hazard contact.*

⚠️ Consistent with, not proven. What would prove it: whether the spill contacts a hazard on this
board — R98's grounding already distinguishes hazard cells from walls, and its note that "reaching a
hazard can end the attempt, while reaching a frame just ends the droplet" is the distinction at
issue.

**The lesson underneath is about retraction, not about flow.** A hypothesis retracted on a broken
measurement is not disproved — it is untested, and it has to go back on the list rather than stay
crossed off. Twice now this round a conclusion has been carried forward from a reading that was
later shown wrong, and only the second one was caught by re-deriving it.

## Hazard contact tested directly: none on this board, and the instrument was validated first

The adapter records how a hazard is told apart: *"the counter band shares its colour with the
in-play hazard, so only the EDGE-pinned test distinguishes the HUD band from a hazard inside the
play area"* (sp80.py:112-115). So a hazard is a region wearing a HUD band's colour while sitting
inside the play area. Applying that to all four commits:

```
band colours [0, 1, 14]   hazard cells inside play 0   spill 624 cells    CONTACT 0   (WON  L1)
band colours [0, 1, 14]   hazard cells inside play 0   spill 800 cells    CONTACT 0   (WON  L2)
band colours [1, 14]      hazard cells inside play 0   spill 1024 cells   CONTACT 0   (lost L3)
band colours [0, 1, 14]   hazard cells inside play 0   spill 1216 cells   CONTACT 0   (lost L3)
```

**The instrument was checked before the result was read** — the failure mode being that an in-play
hazard shaped like a strip would itself be classified as a band and vanish from the comparison.
Listing every region of those colours with its bbox:

```
c14 (0,0,0,44)   c0 (0,45,0,63)   c1 (60,0,63,63)
c1  (0,0,3,63)   c0 (63,0,63,20)  c14 (63,21,63,63)
```

Every one is genuinely at an edge — row 0, rows 0-3, rows 60-63, row 63. So the count of zero means
there are no such regions, not that the test hid them.

⛔ **Hazard contact is therefore not what fails level 3 either** — at least not a hazard of the kind
the adapter itself knows how to name. Seven candidates are now eliminated by measurement, and what
is established is this:

| established | |
| --- | --- |
| every cell of all three targets is wetted on the failing commit | 80/80 x3 |
| nothing is retained | final layer 100% base colour |
| targets are walled against the flow exactly as on winning levels | 12 walled / 0 open |
| the plan is executed exactly as planned | 336 of 336 |
| no in-play hazard exists on these boards | 0 cells, instrument validated |

**Next test, named rather than guessed**: the failing commits wet far MORE of the board than the
winning ones (1024 and 1216 cells against 624 and 800). If retention requires a target to be the
TERMINUS of the flow rather than a way-station, that surplus is the signature — water continuing
past the targets instead of stopping in them. Measurable as whether the spill extends beyond the
targets in the fall direction on level 3 and not on levels 1-2, on boards whose outcome is known.

## Terminus refuted too — eight eliminations, and what structurally remains

```
WON  level 1  fall (1, 0)    spill  624 cells   beyond the targets: 0
WON  level 2  fall (-1, 0)   spill  800 cells   beyond the targets: 0
lost level 3  fall (-1, 0)   spill 1216 cells   beyond the targets: 0
```

Water never runs past a target in the fall direction, on wins or losses. The surplus wetting on the
failing commit is spread elsewhere on the board, not downstream of the targets, so "the target must
be the terminus" does not separate them either.

**Eight candidates eliminated by measurement**: hazard contact (twice, the second time with the
instrument validated), missing static obstacles, target miscounting, stale fall direction,
misdirected propagation, execution drift, basin closure, flow terminus.

What still differs structurally between the levels that win and the one that does not is the SOURCE:

```
level 1   16 source cells   WON
level 2   16 source cells   WON
level 3   48 source cells   lost      = 3x, and the multi-piece planner returned exactly 3 moves
```

Three sources rather than one. `simulate_flow` runs a single BFS over wetted cells and has no
representation of separate streams, so stream-on-stream interaction is something it cannot express
at all — and R98's schema has an axis for exactly that (`own_flow: advance_front | overwrite |
terminate`), which R98 measured INERT on its own board, a SINGLE-piece level where it could not
matter.

⚠️ Candidate, not a finding. It fits what is left, and it is also the only structural difference
still standing, which is a reason to test it and not a reason to believe it.

⚠️ **Worth stating plainly for whoever picks this up**: this is eight eliminations deep on a target
worth **+0.0057** of card. The diagnostic chain has been the valuable part — six instrument faults
caught, several of them after they had produced a confident conclusion — but the sp80 level-3 clear
itself is a small prize, and continuing is a choice rather than an obligation.

## Budget is NOT the constraint anywhere — 25 games at 30,000, measured in parallel (2026-08-26)

First run on ceph-build with the 60-core cap in place, 25 games at once, budget **30,000** against
the deployed **4,000**:

```
CARD MEAN 0.3162   —   identical to the 4,000 run, to four decimals
Not one game gains a single level.
```

And no game spends the budget. Every one stops at its own give-up:

```
~4,000 actions    re86 su15 sk48 r11l sp80 sc25      (adapter _GIVEUP_DEFAULT = 4000)
~8,300-9,600      ar25 s5i5 wa30 lf52 tu93 ka59 g50t dc22 cn04 bp35
 15,524           vc33
   88-503         ft09 m0r0 ls20 cd82 sb26 lp85 tr87 tn36   (they finish)
```

Three things follow, all of them useful:

* **The 4,000-action cap costs nothing**, now confirmed at a second scale across all 25 games rather
  than argued from cumulative-action data on one. The earlier caveat — *a hidden game clearing at
  full score near 2,000 would be a real loss and the public 25 cannot rule it out* — survives for
  the private set, but on everything we can measure the cap is free.
* **Depth is not budget-reachable.** Every unfinished game gives up on its own long before the
  ceiling, so "run it longer" is not an available lever on any of the twelve games stuck below 0.15.
* **What blocks depth is give-up logic and capability**, which is where effort has to go if the
  adapter ceilings are to move at all.

⚠️ This is what the parallel box is for: 25 games, one wall-clock, a clean negative that would have
taken hours serially and was worth having before another day was spent on budget-shaped ideas.

## Three axes in parallel, and the one question DEPTH30 could not answer

The 30,000-action run showed no game gains a level — but it could not show whether MORE actions
would help, because every game stops at its own `_GIVEUP_DEFAULT` long before the ceiling. That
distinction was only ever tested on one game (re86, which did not improve at 30,000 with its give-up
raised). Running on ceph-build with the 60-core cap, three axes now run at once:

| round | agent | budget | question |
| --- | --- | --- | --- |
| `DEPTH30` | `kaggle_detect` | 30,000 | is depth budget-reachable? — **done, no** |
| `GENERIC30` | `chained` | 30,000 | how far does the path that runs on UNMATCHED games get? |
| `NOGIVEUP` | `kaggle_detect` | 100,000 | is the give-up premature, or is capability the wall? |

`NOGIVEUP` raises every adapter's `_GIVEUP_DEFAULT` (23 of the 25 sit at 4,000; one at 500, one at
200) to 100,000. If a game clears deeper with the same code and no other change, its give-up was
premature and the fix is cheap. If none does, capability is the wall everywhere and the give-ups are
honest — which is the more likely answer given re86's single-game result, and worth having across
all 25 rather than extrapolated from one.

⚠️ **The measurement box's source tree is PATCHED while this runs**, which is exactly the kind of
state that silently poisons a later round — the env-metadata incident on this same machine cost a
whole card's worth of confusion. Two guards: the run touches `~/GIVEUP_PATCH_ACTIVE` before patching
and removes it after restoring, and the restore (`tar xzf ~/admorphiq_sync.tgz src`) is chained
INSIDE the same command as the run, so a normal exit always restores. ⛔ Before trusting any future
measurement on this box, check that marker file is absent.

## The second submission landed: 0.18 again — truncation EXCLUDED, and the reading was pre-fixed

Submission `55784359` (detection dispatch, per-game budget **4,000**) scored **0.18** — identical to
`55774529` at budget **100,000**. The reading was fixed on this page before the score arrived:

> *"≈ 0.18 — neither truncation nor the cap matters, and all four explanations are then spent; the
> cause is something not yet on the list."*

That is the branch that happened.

| explanation | status |
| --- | --- |
| ~~harness change~~ | ⛔ excluded — contributes 0 on the public 25 |
| ~~run-to-run noise~~ | ⛔ excluded — the card is deterministic to six decimals |
| ~~run truncated by the budget~~ | ⛔ **EXCLUDED — 4,000 and 100,000 give the SAME hidden score** |
| detectors firing where they should not | **the only one left** |

Budget is now closed on both scales at once: identical on the public 25 (0.3162 = 0.3162 at 4,000
and 30,000) and identical on the hidden 110 (0.18 = 0.18 at 4,000 and 100,000).

**And the public measurement makes the remaining explanation sharp rather than vague.** Detection
versus the generic path, all 25 games:

```
GENERIC (no adapters)  0.0566
DETECT  (adapters)     0.3162
detect better on 13 games, worse on NONE
```

On every public board where a detector fires, dispatching is strictly better. So the 0.02 lost
between v3 (0.20) and detection (0.18) cannot come from the games we can see. It has to come from
private games where a detector fires and the adapter behind it does WORSE than the generic fallback
would have — a mechanic that merely resembles ours, claimed and then failed, with the fallback that
would have scored something never getting to run.

⛔ **The 0/24 gate proves no false positive on the 24 boards we can see. The eval has 110 we cannot,
and the score is now the only instrument reporting on them.** That is the gap the whole port
campaign was built over, and this is the first measurement that puts a number on it: **-0.02**.

⚠️ Not certain, and the honest caveat: v3 and the detection card differ by the harness commits as
well as by dispatch, and the harness was measured at 0 only on the public 25. Two hidden points
cannot separate two changes. But truncation and noise are gone, dispatch is the larger change, and
the direction is against it.

## Give-up is not premature either — capability is the wall, measured across 21 games

`NOGIVEUP` raised every adapter's `_GIVEUP_DEFAULT` from 4,000 to **100,000** (25x) and ran at budget
100,000. Against `DEPTH30`, on the 21 games finished so far:

```
games whose score or levels CHANGED: 0
mean 0.3142 -> 0.3142
```

Not one score, not one level, anywhere. The four still running (r11l, re86, sc25, sk48) are exactly
the games that used to stop AT 4,000 and now have 100,000 to spend, so they are the slowest and the
most likely to move — but 21 of 25 already answer the question.

**Together with DEPTH30 this closes the cheap-lever axis completely:**

| lever | verdict |
| --- | --- |
| more budget (4,000 -> 30,000, public) | ⛔ identical, 0.3162 = 0.3162 |
| more budget (4,000 -> 100,000, HIDDEN) | ⛔ identical, 0.18 = 0.18 |
| later give-up (4,000 -> 100,000) | ⛔ identical, 0 of 21 games change |

Every adapter that stops short does so because it cannot go further, not because it was cut off. The
re86 single-game result — 30,000 actions spent, nothing past level 4 — was not a peculiarity of that
game; it is the shape everywhere.

⚠️ **This is what the parallel box bought.** The same conclusion from one game was an anecdote worth
a paragraph of hedging; from 21 games in one wall-clock it is a closed axis. Both runs together cost
about half an hour of ceph-build and would have been most of a day serially on the Mac — which is
also the machine that a local full-25 already choked.