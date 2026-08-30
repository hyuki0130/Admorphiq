---
round: R101ALLOW
axis: harness — death-clock allowance ledger
keywords: [allowance, action budget, GAME_OVER, death clock, overrun, trust gate, tool retirement, harness, r101]
verdict: BUILT + GATED (see the commit's gate line; the ledger is inert on every game that does not die)
commit: see `git log --oneline -- src/admorphiq/harness/allowance.py`
---

# R101ALLOW — learning a level's action budget by dying on it

> A level that ENDS the game on overrun teaches its own budget: the ledger learns each level's
> allowance from the actions at which it died, and refuses to trust a tool that cannot finish
> inside it. Inert on every game that does not die.

## What is measured, and why it is worth having

Many ARC-AGI-3 games END a level on action-count overrun. `obs.state` reports `GAME_OVER` directly,
so attempt boundaries are **free** — no pixel reading, no source access. The action count at that
moment IS the declared allowance plus one (the death is seen one action after the counter trips).

The pixel route was measured FIRST and mostly does not exist: of twenty-five games exactly one
(bp35, row 63, scale 1) renders its action count as a readable bar. The death clock needs no reader.

A 24-game sweep (`scripts/_deathclock_probe.py`, artefacts `scripts/rounds/R101ALLOW/`) recovered
**nine** allowances:

```
bp35 L6  64    cn04 L4 125    re86 L2 100    ka59 L3 100    s5i5 L7 200
m0r0 L6 150    tn36 L3  61    tr87 L1 129    r11l L6  60
```

⭐ A level-data grep finds twelve declared allowances; the death clock finds nine **including three
the games declare NOWHERE** (tn36, tr87, r11l). It also needs no source access — which is the whole
point, because the evaluation is 110 PRIVATE games whose level data we never see.

## The trust gate is most of the instrument

Where something OTHER than an allowance ends the level, the death lengths SCATTER:

```
TRUSTED (spread <= 1)   cn04 125..126  re86 100..101  ka59 100..101  s5i5 200..201
                        m0r0 151..152  tn36  61.. 62  r11l  60.. 61  bp35  64.. 65  tr87 129..129
REFUSED (spread >= 22)  tu93   9.. 51  su15  48..150  sb26  69..217  sp80  14..121
                        ls20 132..260  ar25 174..196  sc25  26.. 60 / 67..95
```

Nothing measured lands between a spread of 1 and a spread of 22, so **two agreeing deaths** separate
the nine cleanly. ⚠️ cd82 is the instrument's floor: nineteen "deaths" all of length 1 = the harness
idling inside `GAME_OVER` between attempts, not attempts. They inflate the death COUNT and never the
lengths, and a length-1 death would teach an allowance of zero — hence the `FLOOR = 2` guard.

## The consumer — and why THIS one

⛔ A ledger nobody reads scores exactly like no ledger (`fogscout`, committed and unregistered, was
worth +0.0942). The consumer is **retire the tool that keeps dying on a level**:

The scorer charges a level with every action spent since the previous clear, deaths included —
`score_efficiency.py`'s `action_count_this_level` is reset on a level-up and NEVER on a `GAME_OVER`.
So a level cleared after N failed attempts is priced at the whole loop, squared. And the measured
loops are not exploratory, they are VERBATIM repeats: bp35 died 19 times on one level at 64/65
actions, r11l 20 times at 60/61, tn36 21 times at 61/62, s5i5 6 times at 200/201.

The harness already knows how to abandon a tool that is getting nowhere (`_failed`), and that
machinery **never fires here**, because a dying tool is not a STALLED tool — it keeps reaching new
states right up to the moment the clock kills it. Two agreeing deaths say the attempt is
deterministic and bounded; a third repeat cannot end differently.

⚠️ The retirement is scoped to **the level that died**, not to the game. A death usually resets the
board to level 0, and the agent must REPLAY the levels it already cleared to get back — with the
tool that cleared them. Putting the ban in `_failed` would punish that tool everywhere for failing in
one place, which is a regression dressed as a fix. It also does not fire when no other live tool
exists (`_better_alternative_exists`: swapping to a weaker tool is pure downside).

## Honest headroom on the public 25

⛔ **Nearly none, and this must not be over-sold.** In the R101RE86 baseline (0.8962) **EIGHTEEN**
games score 1.0000 — ar25 cd82 cn04 ft09 g50t ka59 m0r0 r11l re86 sb26 sc25 sk48 sp80 su15 tn36 tr87
tu93 vc33 — and every level of every one of them clears at or under the human baseline. The other
seven (bp35, dc22, lf52, s5i5, wa30, lp85, ls20) die only in the ~500-action trailing window after
their LAST clear, on levels they never clear, where the score is already zero.

So on these 25 the ledger is a wall-clock instrument and at best a lottery ticket. Its score case is
the private 110, where a death loop preceding a successful clear costs that level its efficiency
squared. That distinction is stated here rather than blurred, per `OPERATING_RULES.md` rule 7o.

⚠️ **TWO CORRECTIONS TO THIS SECTION'S FIRST DRAFT, both self-inflicted and both instructive.**

1. It said "seventeen", quoted from CLAUDE.md's header — which describes the OLDER 0.8935 baseline.
   R101RE86 is 0.8962 *because* re86 reached 1.0; the round is named after it. Reading a remembered
   header instead of the artefact is the failure this repository keeps paying for.
2. It admitted lp85 and ls20 to the untouched set on the test `total_actions == sum(per_level)`.
   ⛔ **That test cannot detect a death at all**: `score_efficiency.py` adds the GAME_OVER reset to
   `action_count_total` AND `action_count_this_level`, so a death PRESERVES the equality. Both games
   have levels above the human baseline (lp85 L3 32/31, L4 33/16; ls20 L7 237/186), which is exactly
   where a folded-in death would hide.

⛔ **And the inertness claim is circumstantial, not proved.** The arithmetic route was tried and does
NOT close: a death resets the board to level 0, so retrying level k costs replay(1..k-1) first, and
`agent_actions[k] < replay(1..k-1)` would exclude a death there — but level 1 has no replay cost and
L2/L3 of most games exceed their replay. The bound rules out only ft09 L1 (4 actions), r11l L1 (4)
and vc33 L1 (3), where two deaths plus a clear cannot fit. What supports inertness is weaker: every
level of the 18 clears within the human baseline, and the R101ALLOW probe logs their non-terminal
deaths only in its SECOND pass (it runs 1500 actions and plays past the WIN, where the scored run
breaks at WIN — cn04 at 261 actions, ft09 at 79). **The gate is the proof; this argument is not.**

⭐ Corroborating measurement (coordinator, same day): `HARNESS_NOPROGRESS` A/B'd at 500 vs 3500 on all
five wall games gave **seven times the actions and not one extra level** — bp35 740->3787, dc22
925->3928, lf52 823->3828, s5i5 694->3709, wa30 1091->4000, every score identical to four decimals.
That turns this page's central premise — a verbatim repeat cannot end differently — from an inference
about death-length shape into a direct measurement. It also bounds the upside honestly: if 3,000 more
actions of the same tool buy nothing, the public-25 prize is measurably zero.

## GATE RESULT and the ENGAGEMENT RATE — the ledger is learned once and acts never (public 25)

Gated `a8ee8be6` vs `R101RE86`: **PASS, kept, new baseline 0.8986** (`scripts/rounds/R101ALLOW2/games`).
All eighteen 1.0 games byte-identical; of the seven allowed to move only lp85 did (+0.0578), and that
is the separately-committed cyclepress change. ⚠️ HEAD also carried the lf52 railpeg commit, so the
attribution is JOINT — "18 identical" does not isolate this change, though railpeg cannot touch those
eighteen either.

⛔ **WHY IT WAS IDENTITY, mechanically — and this is the answer to "should a tool that KNOWS it has 12
actions left plan differently?"** Derived from the committed artefacts, no new run required.

A death resets the board to level 0. To die AGAIN on level L the agent must first REPLAY levels
1..L. So one death CYCLE costs `replay(1..L) + allowance`. Trust needs TWO deaths; the retirement
needs a THIRD attempt to actually act. Against each game's measured trailing window:

```
game  tail  lvl  allow  replay  cycle  deaths that fit  ban can act?
bp35   507    5     64     233    297         2         NO  - trusted at action 361 of 507, and the
                                                             level it bans is 233 replay-actions
                                                             away; the give-up fires first
s5i5   502    6    200     192    392         1         NO  - never even reaches trust
dc22   500    -   none                                  -   no level gets two agreeing deaths ([1023])
lf52   500    -   none                                  -   same ([640])
```

**So on the public 25 a tool is NEVER in the position of planning with a known allowance.** Exactly
one game learns an allowance at all, and it learns it ~146 actions before `no_progress` ends the
game, with a 233-action replay between it and the level the ban applies to. The engagement rate of
this mechanism on the public set is one game, too late to act — which is a stronger statement than
the headroom section's "the deaths sit in already-zero territory", and it is the reason the gate
returned identity rather than noise.

⛔ **Therefore: do NOT build allowance-aware PLANNING against the public 25.** There is no position in
which it could execute, so any such change would be gated against a board that cannot exercise it —
and a change measured where it cannot act is measured at zero for a reason that has nothing to do
with whether it works. The one configuration where the retirement CAN act is a longer give-up
(bp35 at `HARNESS_NOPROGRESS=3500` gets ~12 cycles instead of 2). ⚠️ The coordinator measured 500 vs
3500 as score-neutral on all five wall games — but on the tree WITHOUT this ledger, so that A/B does
not answer whether the retirement helps when it gets the chance. That A/B re-run on HEAD is the only
cheap decisive experiment left on this axis, and it is worth exactly one round, not a campaign.

## Files

- `src/admorphiq/harness/allowance.py` — `AllowanceLedger` (record, trust gate, remaining clock).
- `src/admorphiq/harness/loop.py` — `_ledger_observe` (attempt boundaries, death recording,
  level-scoped retirement), `remaining_allowance()`, and a duck-typed `set_allowance(remaining)`
  offered to the active tool before it plans.
- `tests/test_harness_allowance.py` — the gate pinned against the sweep's own nine/seven series.
- `tests/test_harness_loop.py` — inertness with no deaths, retirement on two agreeing deaths, no
  retirement on scattered deaths, ban scoped to the dying level.

[[r101_silent-specialists]] · [[index]]
