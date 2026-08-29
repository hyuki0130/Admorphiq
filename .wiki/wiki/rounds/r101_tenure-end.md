---
round: R101TENUREEND
axis: what SHOULD end a tool's tenure — the census of tenure-ending events across all 25, and a 175-arm sweep of the only constant that ends one by exhaustion
keywords: [tenure, retirement, empty-proposal, EMPTY_TOLERANCE, handover, census, harness, loop, stall, clock, measured-negative, closed]
verdict: AXIS CLOSED, NO CHANGE SHIPPED — the whole 25-game corpus contains NINE tenure-ending events; the empty channel costs 70 actions of 7,049 propose round-trips; 6 of 7 EMPTY retirements land on a level the game NEVER clears; and a 175-arm full-25 sweep makes the shipped `_EMPTY_TOLERANCE = 8` the measured ARGMAX with zero dynamic range on 24 of 25 games
commit: pending
supersedes: nothing — this is the same agent's second half of the census banked as rule 7bq (commit 1bbc1f42); it corrects three of 7bq's numbers upward
---

# R101 — what ends a tenure

> Rule 7bd asked why the strong tool goes empty. Rule 7ac closed routing, rule 7bh measured
> "hold the strong tool" inert, rule 7bf measured a partner byte-identical. What was left was the
> RETIREMENT RULE ITSELF — `_EMPTY_TOLERANCE = 8`, the only number in the harness that ends a
> tenure by exhaustion, chosen against two boards and swept on one game. This censuses it across
> all twenty-five and then sweeps it, and the answer is that there is almost nothing there to tune.

## The instruments

`scripts/_tenure_census.py` wraps `UnifiedAgent._fill_from_current` — the ONLY place `propose()` is
called and the ONLY place `_empty_runs` moves — so every propose round-trip is recorded without
reimplementing `loop._legal`: the counter's own delta says whether a legal step survived. Tenure
boundaries are tagged by WHICH bookkeeping moved (`_clock_banned` grew → CLOCK, `_failed` grew with
`_current` going None → EMPTY, `_failed` grew across a swap → STALL, `code` without a `_failed` →
CODE_ESC). At each boundary the retiring tool's own scalars are dumped.

`scripts/_tenure_tolsweep.py` rebinds `loop._EMPTY_TOLERANCE` per arm and runs the full 25 —
seven arms × 25 games = 175 runs, one fan.

Both mirror `score_efficiency.run_game` (rule 7x). **CONTROL: 25 of 25 games reproduce
`scripts/rounds/R101LP85GATE` per-level counts and total actions EXACTLY** — mean 0.9082 — in the
census and again in the sweep's `tol8` arm, so neither instrument moved the run (rule 7ai).

## 1. The whole corpus contains NINE tenure-ending events

```
EMPTY  7      STALL  2      CLOCK  0      CODE  0
```

**Twenty of twenty-five games are played start to finish by ONE tool and never end a tenure at
all.** Only five games ever hand a board over:

| game | events | succession (actions held) |
| --- | --- | --- |
| bp35 | 1 EMPTY | `crag` 229 → `graph` 485 |
| s5i5 | 1 EMPTY | `swivel` 228 → `linkage` 462 |
| ls20 | 1 EMPTY | `keymaze` 423 → `fogscout` 219 |
| re86 | 1 STALL | `cover_targets` 379 → `reforge` 316 |
| lf52 | 4 EMPTY + 1 STALL | `railpeg` 444 → `pegjump` 19 → `graph` 225 → `llm_goal` 7 → `deadsig` 7 → `world_model` 116 |

⛔ **The death-clock retirement (`_ledger_observe`) and the code escalation NEVER FIRE on any of the
25.** They are additive machinery priced entirely against the private 110.

## 2. ⭐ Six of the seven EMPTY retirements are on a level the game never clears

```
bp35  EMPTY a=232  playing level 6 of 5 cleared   NEVER CLEARED -> scored 0
s5i5  EMPTY a=228  playing level 7 of 6 cleared   NEVER CLEARED -> scored 0
lf52  EMPTY a=444/464/697/705, all level 6 of 5   NEVER CLEARED -> scored 0
ls20  EMPTY a=423  playing level 7 of 7 cleared   CLEARED (231 actions)
re86  STALL a=379  playing level 6 of 8 cleared   CLEARED (139 actions, a CANARY at the human count)
```

Actions spent on a level that is never cleared are scored zero however they are spent — rule 7ax's
shape, and it applies to six of seven. **The only EMPTY retirement that can move the score is
ls20's, and rule 7ax already swept exactly that lever and found 231 INVARIANT for handovers from
action 9 to 17.**

## 3. The empty channel is BIMODAL, and the constant has a seven-wide dead band

Across 7,049 propose round-trips there are **70 empty proposes — 1.0%**:

```
runs of consecutive empties that RECOVERED   len 1 x 15    len 2..7 x ZERO
runs that ended in a retirement              len 7 x 1 (llm_goal)   len 8 x 6
```

⚠️ **The one run of length 7 is NOT a recovery** — it is lf52's `llm_goal` being retired one
proposal early off the inherited counter (below). Rule 7bq counts it among the recovered; corrected,
**every recovered run in the corpus has length one and nothing between a blip and death exists.**

⭐ **There is no intermediate case anywhere in the corpus.** A tool either misses exactly once and
recovers, or it stops proposing and never restarts. So every `_EMPTY_TOLERANCE` from 2 to 8 selects
the same seven retirements — the constant is unfalsifiable over a seven-wide range **by the shape of
the data, not by luck**. What it changes over that range is only the ACTION the handover lands on.

⛔ **AND THE COUNTER IS AGENT-SCOPED, NOT TENURE-SCOPED.** Nothing in `_reset_level` or `_redecide`
clears `_empty_runs`; the only writes are the reset-on-legal-fill and the reset-on-fire. A successor
therefore inherits its predecessor's partial count. MEASURED: lf52's `llm_goal` is retired after
**seven** of its own empty proposals because `graph`'s trailing single was still on the counter.

## 4. The 175-arm sweep — the shipped value is the argmax

`scripts/_tenure_tolsweep.py`, seven arms x 25 games, `loop._EMPTY_TOLERANCE` rebound per arm plus
one SHAPE arm (`perT8` = tolerance 8 with the counter zeroed whenever `_current` changes, i.e.
tenure-scoped instead of agent-scoped). 175 runs, 0 errors.

```
arm       tol1     tol2     tol4    tol8=SHIPPED   tol16    tol32    perT8
MEAN    0.7756   0.9017   0.9049      0.9082      0.9017   0.9017   0.9082
games moved   5        1        1           -           1        1        0
```

⭐ **The shipped 8 is the argmax and every other value loses.** Outside `tol1` the ONLY game that
ever moves is ls20 — on 24 of 25 the lever's dynamic range is exactly zero.

| arm | what moved |
| --- | --- |
| `tol1` | ar25 1.0000 → **0.0278**, ft09 1.0000 → **0.0476**, re86 1.0000 → **0.0278**, lf52 0.2727 → 0.0182, ls20 0.9121 → 0.7500 |
| `tol2` | ls20 → 0.7500 (level lost) |
| `tol4` | ls20 → 0.8309 (231 → 327) |
| `tol16` | ls20 → 0.7500 (level lost) |
| `tol32` | ls20 → 0.7500 (level lost) |
| `perT8` | **nothing — all 25 identical in score AND action count** |

⛔ **`tol1` shows what the fifteen singles are worth.** At a tolerance of one they become fifteen
retirements, and three games that never end a tenure under the shipped value collapse outright. The
five capped canaries survive every arm except `tol1`, where re86's L2 42/42 and L6 139/139 do not
merely move — the game never reaches them.

⭐ **ls20's arm reproduces rule 7ax's sixteen-arm table from an independently built instrument**:
`tol4` → 327 / 0.830885, `tol8` → 231 / 0.912085, `tol2`/`tol16`/`tol32` → level lost / 0.7500. Two
instruments, same surface.

## 5. The observable EXISTS at the retirement frame — and nothing reads it

The brief asked whether anything at the retirement frame separates "genuinely run out" from
"momentarily confused". It does, and it is **the tool's own state**, dumped verbatim at the boundary:

| tool | game | its own verdict at the retirement frame | reading |
| --- | --- | --- | --- |
| `swivel` | s5i5 | `_dead=True` | **genuinely out** — the latch rule 7ao named |
| `llm_goal` | lf52 | `_goal_attempted=True` | **genuinely out** — it hypothesises once |
| `pegjump` | lf52 | `_barren=3` (its own quit threshold is 3) | **genuinely out** |
| `deadsig` | lf52 | no state at all (`threshold=6, block=8`) | an augmenter, never had a plan |
| `crag` | bp35 | `_refuted=False, _mute=0, _idle=8` vs its own `_GIVE_UP=16` | **not out** — the harness fires at half its patience |
| `railpeg` | lf52 | `_barren=0, _elsewhere=True` — and `_elsewhere` explicitly BLOCKS its own quit gate | **not out** |
| `keymaze` | ls20 | `_idle=10`, and its `_choose` returns `[]` for every idle > 2 | permanently silent by construction, with no quit flag |
| `cover_targets` | re86 | `_stuck=True, _noplan=True, _handover=True` | **asks to be replaced, in so many words** |

⛔ **THERE IS NO TOOL → HARNESS EXHAUSTION CHANNEL.** `base.Tool` has no such method, `loop.py`
reads none. `cover_targets` literally sets `self._handover = True` at the moment it stops proposing
and **nothing reads it**; the only duck-typed channel in the loop is `target_stalled`, which one
tool implements and which gates a target REDRAW, not a retirement. The harness's sole exhaustion
signal is a count of silences.

⚠️ **But the observable does not license a change (rule 7o).** The two tools it would keep on the
board are `crag` and `railpeg`, and both are already measured: rule 7bh's `hold` arm ran `crag` for
360 actions instead of 229 and left **every per-level count identical**, and `crag` recovers in
shadow only because a SUCCESSOR drives it back into a readable window. Rule 7be measured `railpeg`'s
board as never lost and never finished for a perception reason. Neither is waiting on more patience.

## 6. What this closes, and the one thing it opens

⛔ **CLOSED.** `_EMPTY_TOLERANCE` is not the lever rule 7bd was looking for. The empty channel is
1.0% of the harness's propose traffic; twenty of twenty-five games never touch it; six of its seven
firings are on levels that score zero; the seventh was already swept to invariance by rule 7ax; and
the full-25 sweep finds no value of the constant that beats the shipped one. **Do not re-open it
with another constant.**

⚠️ **What is genuinely broken and is NOT shipped**: `_empty_runs` is agent-scoped where the concept
is tenure-scoped, and one retirement in the corpus is measurably one proposal early because of it.
The one-line fix (zero the counter when `_current` changes) measures **exactly inert on all 25**
(`perT8` arm). It is a correctness fix with no measured benefit, so per rule 7o it is REPORTED, not
shipped — the coordinator decides whether a latent-correctness change to `loop.py` is worth its
exposure on the private 110.

⭐ **What the census actually points at, if anything on this axis is worth more time**: the harness
has no channel for a tool to say it is finished. `cover_targets` sets `_handover = True` and nothing
reads it; the only tool→harness signal in the loop is `target_stalled`, implemented once, and it
gates a target redraw. On the 25 that gap is worth nothing — the tools that would use it are all on
levels scoring zero. On the private 110, where a tool may go silent on a level it could otherwise
clear, it is the difference between eight wasted probes and none. That is a claim about the private
set and cannot be measured here; it is recorded so it is made knowingly rather than by default.

## Backlinks

[[r101_ls20-fog-cost]] · [[index]]
