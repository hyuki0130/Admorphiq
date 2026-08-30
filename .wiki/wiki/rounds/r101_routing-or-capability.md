---
round: R101ABLATESOLOALL
axis: is the ablated loss a ROUTING loss or a CAPABILITY loss — 47 tools forced alone on all 25 boards
keywords: [routing, capability, solo, forced-alone, ablation, owner, exclusive-ownership, private-110, destination, handoff, 7ba, 7bb, idle-tools, sweep]
verdict: CAPABILITY, 23 of 25. Perfect single-tool routing on an orphaned board recovers 0.0034 of the 0.7150 the owner was worth — 0.5%. In 21 of 25 games the best surviving tool scores EXACTLY what the ablated harness scores, and on 10 games NOTHING in the 47-tool registry clears level 1 without the owner. Both controls pass, including 7ba reproduced on all 25.
commit: 5cefcfad
builds_on: [[r101_owner-ablation]], [[r101_lost-signal]]
---

# R101 — routing loss or capability loss?

> 7cj measured that removing a game's owner costs **0.9082 → 0.1932**. 7cm measured that a
> signal saying *"I am lost"* is worth **0.0000 unless there is somewhere better to send the
> board**. That last clause was an INFERENCE from rule 7ba — which measured "no tool alone
> beats the harness" on the FULL registry, on five games. **It had never been measured on an
> ablated board, which is the only case that matters.**

```
ROUTING loss    — some SURVIVING tool alone clears more than the ablated harness managed and
                  is simply never selected. Then detection + handoff is worth something and
                  7cm's signal has a destination.
CAPABILITY loss — no surviving tool can do better, whoever picks. Then no signal, no router
                  and no model fixes it, and the only lever is a fallback that can do
                  something genuinely new.
```

## The instrument, and why the existing sweep was not used

`scripts/ceph_sweep.sh` drives `scripts/_solo_tool.py`, which **hand-rolls its own env
loop**: it passes an accumulating frames list where `run_game` passes `[]`, honours no
`restart_on_game_over`, and reports levels but never a `game_score`. ⛔ Rule 7aj clause 1
exists because a hand-rolled loop clears FOUR bp35 boards where the scorer clears five, so
its numbers cannot be compared against an arm measured through the scorer.

So `--only` was added to `ablate_run.py` instead — the same runner every ablation arm used,
patching the registry down to one tool and going through `score_efficiency.run_game`
unchanged. **A solo number and a harness number are then the same measurement.**

⭐ **AND THE KEY SIMPLIFICATION, CHECKED IN THE SOURCE RATHER THAN ASSUMED**: forcing tool
`T` alone builds `UnifiedAgent([T], ...)`, so removing the owner from the registry is a
**no-op** when `T` is not the owner. An ablated-board solo sweep IS a plain tools × games
solo sweep with the owner column excluded — which is why one sweep answers the ablated
question *and* reproduces 7ba's control for free.

**47 tools × 25 games = 1175 runs**, budget 4000, PAR 12, ~30 minutes.

## Both controls pass

```
⛔ POSITIVE — the OWNER forced alone must clear its own game
   owners clearing >=1 level alone:  25 of 25   PASSES
   (smoke-verified first: reflect_cover alone = ar25 8/8 @ 1.0000, exactly the shipped score)

⛔ NEGATIVE — on the UNABLATED board no single tool beats the harness (rule 7ba)
   games where some solo tool beats the FULL harness:  0 of 25
   7ba REPRODUCED on all 25 — it had only ever been measured on five.
```

## The table

```
game   cls  ablHarness  bestSolo    delta  lv H lv S  best surviving tool
ar25   unc      0.0000    0.0000  +0.0000     0    0  — NOTHING CLEARS
bp35   unc      0.0000    0.0000  +0.0000     0    0  — NOTHING CLEARS
cd82   unc      0.0064    0.0000  -0.0064     1    0  — NOTHING CLEARS
cn04   unc      0.0000    0.0000  +0.0000     0    0  — NOTHING CLEARS
dc22   CLM      0.4762    0.4762  +0.0000     4    4  phase_grid
ft09   unc      0.0000    0.0000  +0.0000     0    0  — NOTHING CLEARS
g50t   CLM      0.1071    0.1071  +0.0000     2    2  maze
ka59   CLM      0.4532    0.4532  +0.0000     5    5  slotlaunch
lf52   CLM      0.0182    0.1091  +0.0909     1    3  hop            <- BEATS IT
lp85   CLM      0.3394    0.3394  +0.0000     5    5  track
ls20   unc      0.0000    0.0000  +0.0000     0    0  — NOTHING CLEARS
m0r0   unc      0.7143    0.7143  +0.0000     5    5  mirror
r11l   unc      0.0043    0.0043  +0.0000     1    1  graph
re86   CLM      0.0278    0.0278  +0.0000     1    1  reforge
s5i5   CLM      0.4167    0.4167  +0.0000     5    5  telescope
sb26   unc      0.0000    0.0000  +0.0000     0    0  — NOTHING CLEARS
sc25   CLM      0.4345    0.4345  +0.0000     4    4  pattern_cast
sk48   unc      0.0000    0.0000  +0.0000     0    0  — NOTHING CLEARS
sp80   CLM      0.7143    0.7143  +0.0000     5    5  spill
su15   CLM      0.4882    0.4882  +0.0000     7    7  socketmerge
tn36   unc      0.0069    0.0065  -0.0004     1    1  graph
tr87   unc      0.0000    0.0000  +0.0000     0    0  — NOTHING CLEARS
tu93   unc      0.0000    0.0000  +0.0000     0    0  — NOTHING CLEARS
vc33   unc      0.0000    0.0012  +0.0012     1    2  toggle         <- BEATS IT
wa30   CLM      0.6222    0.6222  +0.0000     7    7  haul

mean ablated harness 0.1932      mean BEST surviving solo 0.1966      (full harness 0.9082)
ROUTING-recoverable  2 of 25 (lf52, vc33)      CAPABILITY-bound  23 of 25
```

## ⛔ CAPABILITY, and the margin is not close

**Perfect single-tool routing on an orphaned board — an oracle that always picks the best
surviving tool — recovers 0.1966 − 0.1932 = 0.0034 of the 0.7150 the owner was worth. 0.5%.**

And the shape underneath that average is starker than the average:

- **In 21 of 25 games the best surviving tool scores EXACTLY what the ablated harness
  scores.** Not approximately — bit-identical. The harness is already finding the best
  available single tool on every board where one exists.
- **On 10 of 25 games NOTHING in the 47-tool registry clears level 1 without the owner** —
  ar25, bp35, cd82, cn04, ft09, ls20, sb26, sk48, tr87, tu93. There is no second-best.
- The two exceptions are small and one is noise: `hop` on lf52 (+0.0909, 1 → 3 levels, a
  genuine miss) and `toggle` on vc33 (+0.0012, 1 → 2 levels).
- ⚠️ And on **two** games the ablated harness BEATS every single tool — cd82 (−0.0064) and
  tn36 (−0.0004). Composition is worth a little more than the best part, as 7ba's ls20 row
  already showed.

⭐ **So ownership is not merely SINGULAR (7bb) — it is EXCLUSIVE.** For nearly half the
corpus the owner is the only tool in the registry that can clear level 1 at all.

## ⛔ The 7cj class split does NOT predict routing-recoverability — expectation refuted

The expectation going in was that the eleven "a second tool claims it" games would be
routing-recoverable and the fourteen "nobody claims it" games would not:

```
CLAIMED   (a 2nd tool took the board)   n=11   routing-recoverable  1   (lf52)
UNCLAIMED (generic path alone)          n=14   routing-recoverable  1   (vc33)
```

**1 of 11 against 1 of 14.** The classes separate the ablated SCORE beautifully (7cj: 0.3725
vs 0.0523) and separate routing-recoverability not at all. Being claimed means a second tool
can play the board — it does not mean a *better* tool was passed over.

## ⭐ The idle tools are the claimants — 7bb's own warning, now measured

Rule 7bb censused seventeen tools that never hold a board on any of the 25 and warned:
*"THIS IS NOT AN ARGUMENT FOR DELETING THEM. A tool idle here may be the only claimant
there — that is the whole design."* That was a caution. It is now a measurement:

```
distinct surviving tools that clear >=1 level on SOME orphaned board:  16
of those, on 7bb's NEVER-HOLDS-A-BOARD list:                           12
  haul hop maze mirror pattern_cast phase_grid slotlaunch socketmerge
  spill telescope toggle track
not on it:  graph linkage pegjump reforge
```

**Twelve of the seventeen idle tools do real work the moment the owner is gone** — `phase_grid`
carries dc22 to 4 levels, `haul` carries wa30 to 7, `mirror` carries m0r0 to 5. ⛔ Any future
proposal to prune the registry by observed tenure would delete exactly the tools that hold the
line on an unowned board, which is the private-110 condition.

## ⚠️ What the solo maximum is, and is not

It is a **LOWER bound** on what perfect routing could achieve, not an upper one: the harness
can COMPOSE, and rule 7ba's sharpest row is ls20, where the harness reaches level 7 and no
single tool passes 6. cd82 and tn36 above show the same effect on ablated boards. **So "no
solo tool beats the ablated harness" does not strictly prove that no ROUTE does.**

What it does prove is the thing that was being asked: **the single-tool handoff — the only
kind 7cm's signal could ever trigger — has no destination on 23 of 25 boards.**

⚠️ And the standing caveat: nineteen of these 25 games sit at the cap and every tool here was
written against them. This is the easy case.

## What this closes

- **Detection is closed** (7cm: a signal exists, worth 0.0000 without a destination).
- **Routing is closed** (7ac: routing cannot lose a tie; this round: the oracle is worth 0.5%).
- **The tool set is closed** (7ba, 7bb, and now the exclusive-ownership result).

⭐ **The chain terminates at CAPABILITY.** No signal, no router, no model and no additional
per-mechanic specialist changes what happens on a board whose mechanic nothing implements.
The only remaining lever is a fallback that can learn a board it has no tool for — which is
stage two of the top policy, and it is now the measured conclusion rather than the assumed one.

⛔ Nothing ships (rule 7o). This is a measurement of where the loss lives.

## Related

- [[r101_owner-ablation]] — the ablation that produced the boards and the classes (rule 7cj)
- [[r101_lost-signal]] — the detection half, whose "unless there is somewhere better" clause
  this round tests (rule 7cm)
- Rule **7cq** in `OPERATING_RULES.md`
- Rules 7ba (now reproduced on all 25), 7bb (its idle-roster warning now measured), 7ac, 7aj
