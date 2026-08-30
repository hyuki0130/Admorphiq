---
round: R101ABLATETELOWN / R101ABLATETELABL
axis: does a run own a quantity that says "I do not understand this board" — measured before anything is built
keywords: [lost-signal, give-up, bail, no-progress, novelty, saturation, coverage, inert-rate, revisit, telemetry, level-segment, FPR0, clock, budget-threshold, private-110, latch]
verdict: MEASURED, MIXED — no candidate separates early ALONE (best AUC 0.815 at action 50) and none beats the clock at its own zero-loss point (34.9% vs 28.7%). But `coverage` ADDED to the clock takes doomed actions saved from 34.9% to 51.5% at ZERO levels lost. ⛔ The threshold is fitted in-sample and pinned by ONE winning segment, and all ten flagged segments come from the ABLATED arm — so on the shipped configuration the signal fires zero times and is worth 0.0000 today.
commit: 5cefcfad
builds_on: [[r101_owner-ablation]]
---

# R101 — can a run tell that it is lost?

> Rule 7cj ended with a hypothesis, not a result: *the harness owns no signal meaning "I do
> not understand this board"; a frontier explorer always proposes and always reaches a new
> state, so `_EMPTY_TOLERANCE` and the 80-step stall are both satisfied by a tool clearing
> nothing.* That is a claim about a SIGNAL. This round measures whether such a signal exists
> before anyone builds one.

## The data was already labelled — that is why this is a measurement

The ablation arms gave the two classes on the same harness, same budgets, same boards. Both
were re-run with `TELEM=1`, recording per action: raw-frame novelty, the harness's own
`_since_progress` and `_seen_states` size, the changed-cell count and the change centroid.

⛔ **The frame is read RAW, every layer, hashed by the recorder — deliberately not through
`frame_2d`**, which takes layer 0 and reads a stale layer at level transitions (rule 7o). A
novelty signal computed off a stale layer would fire exactly where the label changes.

```
INSTRUMENT CONTROL   telemetry must be inert, and it is:
  R101ABLATETELOWN vs R101ABLATENEG    0 of 25 differing in score, levels AND actions
  R101ABLATETELABL vs R101ABLATEDROP1  0 of 25 differing in score, levels AND actions
```

## ⛔ The classes are defined by OUTCOME, not by shape — `m0r0` is why

The obvious labelling is "the fourteen latched runs are the negatives". **It is wrong, and
the counterexample was already in the data**: `m0r0` latches — one tenure, 731 actions, never
re-decided — and CLEARS FIVE LEVELS. A signal trained on latch-shape fires on it.

So the unit is a **level segment**: a contiguous stretch of actions at one level, labelled
simply by whether that level was cleared. 50 runs → **255 segments, 205 cleared, 50 doomed**.

```
cleared-segment lengths   min 3    median  27   max 310
doomed-segment  lengths   min 9    median 500   max 500
```

And the decision is evaluated at a **prefix**: at action k, only segments still running at
action k are eligible. That is the runtime framing, and it is honest that short winners are
already gone. The operating point is **FPR = 0** — bailing on a level that would have cleared
costs the level.

## ⛔ Only two prefixes have enough winners to define a threshold at all

This is the first thing the table says and it disqualifies most of it:

```
prefix              25     50     75    100    150    200    300
eligible pos/neg 111/45  48/35  19/33  13/32   2/31   1/30   1/29
```

**At k >= 150 there are one or two eligible winners.** An FPR-0 threshold set by a single
winner is not a measurement, so `inert_rate`'s apparently strong 20/29 at k=300 is NO
VERDICT, not a result. Everything below is read at **k = 25 and k = 50 only**.

```
AUC (higher = better separation)        k=25    k=50
  coverage                             0.721   0.815
  tool_novelty_rate                    0.614   0.696
  inert_rate                           0.584   0.644
  change_uniformity                    0.553   0.643
  novelty_rate / revisit               0.573   0.632
  since_progress_max                   0.577   0.632
  novelty_decay                        0.500   0.500
  norm_clock                           0.449   0.482

CATCH @ FPR0 (doomed flagged by a threshold flagging NO winner)
  coverage                              0/45   10/35
  inert_rate                            3/45    5/35
  everything else                     0-3/45   0-3/35
```

## ⭐ Elapsed time carries ZERO information at a fixed decision point

The disqualified baseline had to be reformulated mid-round, and the reason is worth keeping.
Scoring "how long has this segment run" as a ranking candidate returns **AUC 0.500 by
construction** — every segment alive at action k has used exactly k actions. **A clock does
not discriminate between runs; it only decides when to stop.** So the baseline is not a
ranking, it is a POLICY, and that is what the candidates must beat:

```
policy                                  levels lost   actions saved   of doomed
clock: bail at  25 on the level                 109           14497       92.3%
clock: bail at  50                               47           13505       86.0%
clock: bail at 150                                2           10248       65.3%
clock: bail at 311  <- the clock's ZERO-LOSS point  0            5481       34.9%
```

311 is one past the longest cleared segment in the whole corpus (`vc33` level 0, 310 actions,
in the ablated arm). ⛔ **Alone, no candidate beats it**: the best signal, `coverage` at
action 50, saves **28.7%** at zero loss against the clock's **34.9%**.

## ⭐ But a signal ADDS to the clock — and that is the round's positive result

The clock and the signal fail on different segments, so the useful policy is the union: bail
at action 50 if the signal fires, otherwise bail at 311.

```
policy                                        levels lost   actions saved   of doomed
clock alone (bail 311)                                  0            5481       34.9%
coverage@50  OR clock                                   0            8091       51.5%   +2610
coverage@50 OR inert_rate@50 OR clock                   0            8352       53.2%   +2871
```

`coverage` = 1 − (distinct 4×4-quantised change centroids ÷ actions). High means the tool
keeps disturbing the same few places. **It takes half the actions currently burned on doomed
levels, at zero cost in levels.**

## Both controls, stated as numbers

⛔ **NEGATIVE — the slow winners are exactly what limits the signal, and they hold.** All
twenty level-segments of `re86`, `wa30` and `ls20` sit at or below the threshold, and
`re86` level 5 (139 actions) **pins it exactly** at 0.8400:

```
re86 L5 n=139 coverage 0.8400  <- sets the threshold
re86 L4 n=113          0.4800      wa30 L4 n=120  0.5200      ls20 L5 n=100  0.6200
re86 L6 n=101          0.4200      wa30 L7 n=134  0.5000      ls20 L1 n=101  0.4800
```

⭐ **POSITIVE — 10 of 35 doomed segments alive at action 50 are flagged, every one of them at
the full 500-action allowance:**

```
ft09 L0 1.0000 · su15 L7 1.0000 · m0r0 L5 0.9800 · tr87 L0 0.9600 · ar25 L0 0.9200
lp85 L5 0.9200 · bp35 L0 0.8600 · cn04 L0 0.8600 · ls20 L0 0.8600 · re86 L1 0.8600
```

⭐ **And `m0r0` — the case that broke the naive labelling — comes out right**: its four
winning segments pass unflagged and only its genuinely doomed level 5 fires.

## ⛔ Four caveats, and the third is the one that decides whether this is worth anything

1. **The threshold is fitted IN-SAMPLE**, on the same 25 games it is scored on, and it is set
   by ONE winning segment. 51.5% is an upper bound on what such a rule could do, not a
   transferable number. There is no held-out set here and the round does not pretend one.
2. **Nineteen of these 25 games sit at the cap.** A signal validated only here is validated on
   the easy case — the same caveat 7cj carries.
3. ⛔ **ALL TEN FLAGGED SEGMENTS COME FROM THE ABLATED ARM.** On the shipped configuration the
   signal fires **zero times**, so it is worth exactly **0.0000** of score today. And the
   actions it would save are spent on levels that score zero however they are spent (the 7ax /
   7bq shape), so what it frees is wall-clock — not points — **unless there is something
   better to spend the freed budget on. Rule 7ba says that on these boards there is not.**
   Its entire value is contingent on the private 110 having a second claimant worth trying,
   which these 25 cannot test.
4. `norm_clock` — segment length ÷ median cost of the levels this game already cleared — is
   the weakest candidate measured (AUC 0.449 / 0.482) **and is undefined on a run that has
   cleared nothing**, which is exactly the nine games that clear zero after ablation. The
   normaliser is unavailable precisely where the problem is worst.

## What this settles

- **The hypothesis at the end of 7cj is half true.** A run-intrinsic quantity that separates
  lost from winning does exist, but it is weak alone, it does not beat a clock on its own, and
  it only pays as a *supplement* to one.
- ⛔ **Nothing ships (rule 7o).** This measures whether the signal exists. Wiring anything into
  `loop.py` is a separate decision needing a `snapgate.sh` gate on the full 25 — and on the
  evidence above that gate would measure **exactly zero change**, which is the argument for
  leaving it alone rather than for shipping it quietly.
- ⭐ **The design consequence points away from bailing.** A signal worth 0.0000 unless there is
  a better tool to hand the board to says the lever is not a better give-up rule; it is having
  a second claimant at all. That is the same conclusion 7cj reached from the other direction.

## Related

- [[r101_owner-ablation]] — the round that produced these labels and the hypothesis under test
- Rule **7cm** in `OPERATING_RULES.md`
- Rules 7ba (no tool alone goes deeper — why freed budget has nowhere to go), 7ax / 7bq
  (actions on a level that never clears score zero however they are spent), 7o (a measurement
  of a mechanism does not license a change of behaviour)
