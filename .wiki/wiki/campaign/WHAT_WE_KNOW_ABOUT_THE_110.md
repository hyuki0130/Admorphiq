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

## 3. The one render-dependent read in the corpus, proved by intervention

**A frame-only tool that identifies an object by whether it is DRAWN is reading PAINT ORDER, not
mechanics** (rule **7cd**). s5i5 L4 costs 39 actions live and 61 on the re-render because ONE cell at
(43,31) is occluded — the archived source lists the rider before the bar it rides — and `telescope`'s
candidate set goes from 2 to 9.

⭐ **Proved causally**: inject the rider evidence back, change nothing else, and the level returns to
39 actions and the game to 0.5833 — `[13, 30, 47, 39, 32, 31]` in both arms.

**Population** (rule **7cl**): not one. 63 sites, **14** with that exact structure, **five** filtering
on what is painted, **three live on a run**. ⚠️ The automated arm caught 3 of the 5. ⭐ And the worst
site has NO fallback, so 7cd's own shape under-counts the class: `lattice_maze:484` compares a colour
read NOW against one REMEMBERED — **6.9x** blow-up on tu93's re-render against telescope's 1.56x —
**already repaired** by dead reckoning, and invisible to any vocabulary because no word in it names
paint.

⛔ **No repair to the three live sites.** Removing a visibility filter takes the tool to the
unfiltered set EVERYWHERE, which IS the 61-action behaviour.

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
