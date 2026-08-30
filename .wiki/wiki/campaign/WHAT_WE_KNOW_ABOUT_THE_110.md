---
type: campaign
description: Everything measured on 2026-08-30 about how the 0.9082 card would behave on 110 unseen games — what transfers, what does not, and which questions the public 25 are structurally unable to answer.
---

# What we know about the 110 — and how we know it

> One day of measurement turned "the private set is a worry" into a set of numbers with named
> boundaries. This page is the synthesis: what transfers, what does not, and — the part that keeps
> being forgotten — **which questions these 25 games are structurally incapable of answering.**

⚠️ **Read the boundary before the number, every time.** Nineteen of the 25 sit at the 1.0 cap. A
class measured at ~zero on a corpus that is already nearly perfect has been measured **on the wrong
corpus**, not measured away. Three of today's results carry that caveat and it is load-bearing in
all three.

## 1. The card that ships is the card we measure

| | |
|---|---|
| `--agent unified`, full 25 | **0.9082** |
| `AGENT=kaggle_unified` (the wrapper the notebook ships) | **0.9082**, zero games differing |
| Kaggle's own machine, server-side at HEAD | **all 25 games same levels; same TOTAL ACTIONS on all 21 it wins** |

Rules **7bv**, **7bz**. `notebooks/kaggle_submission.py` registers `KaggleUnifiedAgent` (`f1067554`).
The chain local gate → shipped wrapper → Kaggle hardware is closed end to end with every link
measured rather than assumed. ⚠️ This says the 25 travel. It says nothing about the 110.

## 2. What transfers: the tools read mechanics, not pixels

| perturbation | result |
|---|---|
| archived re-render, 14 real substitutions (7by) | **24 of 25 games action-for-action identical**, ratio 0.9989 |
| colour permutation ×2, fixed-point-free (7ce) | **one action moves in the whole corpus** (cd82 L3, no score change) |
| identifier rename, all-or-nothing (7ce) | 14 games clean; 1 broken mutation; 10 not constructible |
| discarded outer band (7cf) | costs **zero**, and for a reason — see §4 |

⛔ **A re-render is the SAME GAME.** This rules out the cheapest brittleness — a tool keyed to a
literal colour or a sprite name — and nothing more. **Do not quote 0.9989 as a transfer
coefficient.**

⛔ **AND THE HEADING ABOVE IS ONLY HALF TRUE — READ §3 BEFORE QUOTING THIS TABLE.** Every
perturbation in it is one a colour bijection or a rename can express, and all of them are
**order-preserving by construction**. The one axis they cannot touch is the one that turns out to
matter: **fourteen of the 25 games depend on PAINT ORDER**, and two lose everything. A clean sweep
here is evidence about colour and naming, and about nothing else.

## 3. Paint order — FOURTEEN of 25 games depend on it

⛔ **THIS SECTION SAID "THE ONE RENDER-DEPENDENT READ IN THE CORPUS" FOR THREE HOURS AND IT WAS
WRONG.** That was true of the evidence available at the time — the archived re-render, which moves
exactly one level of one game. A better instrument landed the same day (`scripts/zordergate.sh`,
rule **7ck**) and it reaches all 25:

```
identity control     0.9082, reproducing R101SHIPPED — zero drift
positive control     s5i5 L4  39 -> 61, 0.5833 -> 0.5593  = 7cd's banked answer, to the action
14 applied · 10 INERT (cannot exhibit it) · 1 PARTIAL

movers   re86 1.0000 -> 0.9461 · s5i5 0.5833 -> 0.5593 · sc25 1.0000 -> 0.4762
         g50t -> 0.0000 · tu93 -> 0.0000
```

⚠️ The rule was CLAIMED under the title *"only three games' cameras let it move"* and its own author
records that the measurement refuted the title. Three games' cameras make the dependence **maximal**;
fourteen games carry it.

⛔ **AND BURIAL DOES NOT PREDICT THE COST — the two games that lose everything hide the least:**

```
r11l   7 of 27 sprites removed from the picture   1.0000 -> 1.0000   identical action for action
tn36   6 of 101                                   1.0000 -> 1.0000   identical
sk48   5 of 59                                    1.0000 -> 1.0000   identical
g50t   1 of 18                                    1.0000 -> 0.0000
```

So "the mutation hid an object, therefore the board is broken" is refuted by the instrument's own
column. **What matters is WHICH object, not how many.**

⭐ **Validity is one line of the engine.** `Camera.render` has exactly ONE caller inside arcengine and
its return value is the observation frame; game logic reads through `_raw_render` and clicks resolve
through `Level.get_sprite_at`. The patch touches neither, so the state trajectory stays a function of
the action sequence alone. ⛔ Do NOT patch `_raw_render` — games call that as logic. And the human
denominator is invariant **by measurement**: the two s5i5 serializations differ only in list order and
ship identical `baseline_actions`.

⚠️ **"Permute same-layer siblings only" is right for 22 games and MEANINGLESS for three.** s5i5, tu93
and wa30 override `_raw_render` with a version that never sorts, so the raw list order IS the z-order
and `layer` decides nothing — s5i5's rider and its bar are on DIFFERENT declared layers. The
conservative arm changed 0 cells on seven of s5i5's eight levels and lost its own positive control.

### The mechanism, named and proved by intervention

**A frame-only tool that identifies an object by whether it is DRAWN is reading PAINT ORDER, not
mechanics** (rule **7cd**). s5i5 L4 costs 39 actions live and 61 on the re-render because ONE cell at
(43,31) is occluded, and `telescope`'s candidate set goes from 2 to 9.

⭐ **Proved causally**: inject the rider evidence back, change nothing else, and the level returns to
39 actions and the game to 0.5833 — `[13, 30, 47, 39, 32, 31]` in both arms.

**Population** (rule **7cl**): 63 sites, **14** with that exact structure, **five** filtering on what
is painted, **three live on a run**. ⚠️ The automated arm caught 3 of the 5. ⭐ And the worst site has
NO fallback, so 7cd's shape under-counts: `lattice_maze:484` compares a colour read NOW against one
REMEMBERED — **6.9x** on tu93's re-render against telescope's 1.56x — already repaired, and invisible
to any vocabulary because no word in it names paint.

### Why the repair that works does not travel

Rule **7cn**. `lattice_maze._locate` does not remove the paint read (that is what 7cd forbids, and it
IS the 61-action behaviour) — it **demotes paint from IDENTITY to CANDIDATE GENERATION** and lets
tracked state pick among the candidates, never trusting its prediction unless the frame agrees.

⛔ **Its precondition is a prior position and a spent action, and a run says where that exists:**

```
lattice_maze:484  tu93  187 evaluations,  9 on an opening frame   178 of 187 have the state
blastclock:631    ka59   33 evaluations, 19 on an opening frame    14 of 33 do
swivel:734        s5i5    2 evaluations,  2 on an opening frame    NONE — both at action 0
telescope:1183    s5i5    5 evaluations,  5 on an opening frame    NONE — all five at action 0
```

`lattice_maze` re-reads identity EVERY action. `telescope` and `swivel` commit the rider set ONCE per
level, on the opening frame, into a model that is never revised. **There is nothing to reckon from,
so the repair cannot be ported — the axis is closed with a reason rather than a shrug.**

## 4. What does NOT transfer: the tools fit THESE games

⛔ **The single most important measurement of the day** (rule **7cj**). Remove the tool that actually
plays each game and re-score:

```
0.9082  ->  0.1932        25 of 25 games moved; the floor is NOT flat (median 0.0069, stdev 0.2558)

~0.0014   the analogue of NO TOOL FITS            14 games nobody claims
 0.1932   the analogue of NEW BUT ADJACENT        11 games another of OUR specialists partly fits
```

⛔ **Quote the pair, never the mean.** In all eleven claimed games the claimant is another specialist
we built against a PUBLIC board. **An unseen game has no near-miss waiting, by construction.**

## 5. The failure is SILENT — and that is the structural finding

Fourteen ablated games have exactly ONE `[harness] pick=` line for the whole run, and **every one has
`primary_owns` FALSE**, so `_PRIMARY_CONF` is REFUTED as the cause. A frontier explorer:

- **always proposes** → `_EMPTY_TOLERANCE` never fires
- **always reaches a new state** → the 80-step stall never fires

**It looks productive by every signal the harness watches, while clearing nothing.** Worse than a bad
threshold, because no tuning addresses it. ⛔ And not a `graph` problem: dropping `graph` too gives
0.1925 with `world_model` doing the identical thing — **the latch belongs to the fallback POSITION**.
"Demote graph" is closed.

## 6. Can a run tell it is lost? Yes — and it is worth 0.0000 today

Rule **7cm**, and it closes the lever §5 named.

- ⛔ **Classes are defined by OUTCOME, not shape.** m0r0 latches — one tenure, 731 actions — and
  CLEARS FIVE LEVELS. The unit is a level segment labelled by whether it cleared.
- ⭐ **Elapsed time carries ZERO information at a fixed decision point** — AUC 0.500 BY CONSTRUCTION,
  since every segment alive at action *k* has used exactly *k* actions. **A clock does not
  discriminate between runs; it only decides when to stop.**
- Alone, no candidate beats the clock. `coverage@50 OR clock@311` saves 51.5% of doomed actions at
  zero levels lost, against 34.9% for the zero-loss clock alone.
- ⛔ **All ten flagged segments come from the ABLATED arm. On the shipped configuration the signal
  fires ZERO times.** It frees wall-clock, not points — the actions it saves are on levels that score
  zero however they are spent.

## 7. The offline model changes nothing here — and cannot be judged here

Rule **7ch**, on a Kaggle GPU with vLLM serving gemma4:

```
arm llm       0.908187      arm fallback  0.908187      games differing: ZERO
38 served completions · target-draw failures: fallback 3, llm ZERO · 34 re-decides each arm · +104s
```

The model ran, answered, drew targets, and changed not one action. ⚠️ **It does not say an LLM is
useless.** It says these 25 cannot measure it: nineteen sit at the cap and signature routing already
picks a tool that clears. **The 110 are the case where no tool fits — exactly what §4 and §5
describe, and exactly what this run cannot see.**

## Where that leaves the work

⭐ **The missing thing is not DETECTION (§6) and not ROUTING (7ac) — it is a DESTINATION: something
to do when nothing in the registry fits.** That is a capability question, and it is the open one.

⚠️ The premise underneath it — *"there is nowhere better to send the board"* — is currently an
INFERENCE from rule 7ba, which measured *no tool alone beats the harness* on the FULL registry and has
never been run on an ablated board. **That measurement is in flight**, and it forks the campaign:
routing loss (detection gains a destination) versus capability loss (only a fallback that can learn
an unseen board is left).

## Related

[[r101_shipped-and-transfer]] · [[r101_zorder-rider]] · [[r101_visibility-identity-census]] ·
[[r101_owner-ablation]] · [[r101_lost-signal]] · [[r101_llm-on-a-gpu]] · [[r101_discarded-band]] ·
[[r101_inert-actions]] · [[ACTIVE]]
