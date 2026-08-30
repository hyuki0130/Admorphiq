# CAMPAIGN — ACTIVE

> The plan that survives a context compaction. Read this before choosing a direction.

## STATE (2026-08-30 08:20, all gated on the full 25)

**MEAN = 0.9082**, NINETEEN games at the 1.0 cap, cumulative regressions ZERO.
Baseline dir: **`scripts/rounds/R101SHIPPED`** — use it as the gate's BASE. (It is the
SHIPPED-configuration run and scores identically to `R101LP85GATE`, game for game; prefer it so a
gate and the card it defends are measured through the same wrapper.)

⭐ **THE GAINS REACH THE SUBMISSION PATH — GATED AS SHIPPED, 2026-08-30** (rule 7bv). The gate now
takes `AGENT=`, which it did not until today, so this file's own "measure the card AS SHIPPED"
instruction named a flag the runner refused:

```
AGENT=kaggle_unified bash scripts/snapgate.sh shipped scripts/rounds/R101LF52PART 12 4000
  MEAN 0.9082 over 25   ZERO games differing from the bench member   canaries hold
```

`notebooks/kaggle_submission.py` ships `KaggleUnifiedAgent` (`f1067554`) — ⚠️ CLAUDE.md claimed for
days that it ships `KaggleDetectAgent`/`KaggleChainedAgent`; both blocks are corrected. Re-run this
after any day of harness work: the wrapper MIRRORS `_make_agent("unified")` and a mirror drifts.

⭐ **AND THE TOOLS READ MECHANICS, NOT PIXELS — 24 of 25 games IDENTICAL on a re-render** (rule 7by,
`bash scripts/xfergate.sh`, procedure now a committed script because it had been re-derived by hand
three times). All fifteen archived version hashes substituted: mean 0.9072 vs 0.9082, ratio 0.9989,
and the ONLY difference in the whole set is s5i5 L4 at 39 -> 61 actions (still clears). The ten
games with no archive are the determinism control and are identical too.
⚠️ Still weak evidence — a re-render is the SAME GAME. ⛔ Do not quote 0.9989 as a leaderboard
transfer coefficient; the hidden score of the generic path remains UNMEASURED.

Conquered on 2026-08-29, each gated: **re86 0.9908 -> 1.0000 (8/8)** and **wa30 0.8000 -> 1.0000
(9/9)** — wa30's last level was short of ATTEMPTS, not moves; six of its eight tries were
byte-identical replays.

⛔ **SIX still short — and the per-level column is from `R101SHIPPED`, the SHIPPED-configuration
gate, not from memory.** Four of the six lose NOTHING BUT DEPTH: every level they reach is at the
1.0 cap and the game simply ends. For those there is no efficiency work to do at all.

```
bp35 0.2456  reached 5   1.00 0.30 0.96 1.00 0.51   BOTH
lf52 0.2727  reached 5   1.00 1.00 1.00 1.00 1.00   DEPTH ONLY
s5i5 0.5833  reached 6   all six at 1.00            DEPTH ONLY
dc22 0.7143  reached 5   all five at 1.00           DEPTH ONLY — one level from the end
ls20 0.9121  reached 7   ...1.00 0.65               EFFICIENCY, L7 alone
lp85 0.9767  reached 8   ...0.79 at L4...           ⛔ CLOSED — identification, not slack
```

Why each is closed, largest gap first:

```
lf52    0.2727   gap 0.7273   ⭐ THE WHOLE GAP IS ONE MOVE — the third capture at action 124 is the
                             level author's own marked losing branch, and railpeg ARMS it earlier by
                             moving red to (6,6). Then a click at (6,56) RESTARTS the level with no
                             signal. Target: make the third capture the eighth candidate, not the
                             first, and stop clicking when nothing is legal (recovers 143 actions).
bp35    0.2456   gap 0.7544   ⛔ CLOSED — every attempt a near-pure traversal, human clears in ONE.
s5i5    0.5833   gap 0.4167   ⛔ CLOSED — the win opens by moving a rider that is already home, which
                             swivel's decomposition can never propose. 30 arms, all 0.5833.
dc22    0.7143   gap 0.2857   ⛔ CLOSED — the blocker is ours (phase.py:430 condemns a drawn tile for
                             ONE pixel), censused to this game alone; both repairs measured negative.
ls20    0.9121   gap 0.0879   ⛔ FULLY CLOSED — the handover too. L7's 231 = 10 handover + 58 (3 lives)
                             + 87 explore + 1 death + 75 solve; the ORACLE bound is 61. You cannot
                             wait for or ambush a mover: `Ls20.step` moves movers FIRST and UNDOES
                             them when the player's move is refused (18 of 18), so ambushing is
                             IMPOSSIBLE, not mistuned. 12 arms x 4 axes all lose or are inert.
lp85    0.9767   gap 0.0233   ⛔ CLOSED — L4 = 18 vs a human 16 and the whole of it is model
                             identification: with the converged model at the OPENING the level costs
                             EIGHT actions, and the ten probes leave the plan the same length. The two
                             saveable presses are spent at proposes 3 and 4; the evidence they are
                             unnecessary does not exist until propose 12. FIFTEEN arms refuted.
```

## ⭐ WHAT KIND OF PROBLEM EACH GAME IS — and the one reading that keeps being got wrong

⚠️ **The per-level table lives in the STATE block above, refreshed 2026-08-30 from `R101SHIPPED`.**
It used to be duplicated here with 2026-08-29 numbers, which meant this file disagreed with itself
about wa30 (conquered), ls20 and bp35. **One copy, at the top.** What survives here is the reading:

⛔ **FOUR OF THE SIX LOSE NOTHING BUT DEPTH.** Every level they reach is at the cap, several faster
than the human, and the game simply ends short. For those games there is no efficiency work to do at
all and a "make the tool faster" change cannot help — the target is the NEXT level and only the next
level. dc22 is one level from the end.

⚠️ Reading a stuck game as ONE NUMBER hides this completely, and it is one command away:
`per_level` in `scripts/rounds/*/games/*.json`.

⚠️ **bp35's two low levels are not slowness — they are a FAILURE RATE.** Its human baselines EXCEED
the game's own action allowance (87/131/163 against 64/128/192), so those baselines already contain
a retry. "87 actions vs 48 human" is TWO ATTEMPTS, not one slow one.

⭐ **AND THE EFFICIENCY HALF IS BOUNDED AT +0.00796 IN TOTAL** (rule 7cb): only FIVE cleared levels
in the whole 25 score below 1.0 — bp35 L2/L3/L5, lp85 L4, ls20 L7. Compute that bound before opening
any efficiency arm; it is one pass over `rounds/*/games/*.json`.

> ⭐ **THE ONE-PAGE SYNTHESIS OF EVERYTHING MEASURED ABOUT THE 110 IS**
> [[WHAT_WE_KNOW_ABOUT_THE_110]] — what transfers, what does not, and **which questions these 25
> games are structurally incapable of answering.** Read it before choosing a direction; this
> section is the work list, that page is the picture.

## NEXT ACTIONS — pick from here, not from the last tool output

> ⛔ **THE GOAL IS ALL 25 GAMES COMPLETE. "CLOSED WITH PROOFS" IS NOT PERMISSION TO STOP.**
> (User correction, 2026-08-30 11:41, and it was needed.) Six games are incomplete. This file said
> each of them was "closed with proofs", I read that as a verdict, and I moved the whole team onto
> the 110-transfer axis. **A proof that a hypothesis is refuted is a statement about that hypothesis
> — it is not a statement that the game is unwinnable**, and nothing in the CLOSED section ever
> claimed otherwise. The distinction had no cost while agents were still on the games and a real one
> the moment they were not.
>
> ⭐ **STANDING: one background agent per incomplete game, in parallel on ceph, at all times.**
> Six are live now — bp35 · lf52 · s5i5 · dc22 · ls20 · lp85. Each carries its own game's refuted
> list so it does not re-run a dead arm, and each is gated on the full 25 with the canaries.
> ⚠️ The transfer/110 work below is SECOND. It is real and it is measured, but it is not the goal.
>
> ⚠️ Prize per game, so effort is proportional: bp35 +0.0302 · lf52 +0.0291 · s5i5 +0.0167 ·
> dc22 +0.0114 (**one level from the end**) · ls20 +0.0035 · lp85 ⛔ CLOSED 2026-08-30
> ([[r101_lp85-level-four]] — two actions on one level, and they are spent before the evidence that
> they are unnecessary exists).


> ⭐ **THE AXIS MOVED ON 2026-08-30. IT IS NO LONGER THE DEV SCORE.**
>
> The 0.0918 that remains on the 25 is closed with proofs (below, and every word of it still
> stands). What replaced it is the question the 25 games cannot answer: **the eval is 110 games we
> have never seen, all of them rendered differently from anything here, and all of them taking the
> generic path.** Two measurements on 2026-08-30 turned that from a worry into an axis with an
> instrument — [[r101_shipped-and-transfer]], rules 7bv + 7by:
>
> - the SHIPPED wrapper scores **0.9082, zero games differing** (`AGENT=kaggle_unified bash
>   scripts/snapgate.sh`) and the notebook has shipped `KaggleUnifiedAgent` since `f1067554`, so
>   everything below reaches the card;
> - **24 of 25 games are action-for-action IDENTICAL on an archived re-render** (`bash
>   scripts/xfergate.sh`, ratio 0.9989). **s5i5 L4 is the ONLY render-dependent thing in the entire
>   corpus** — 39 -> 61 actions on the same level re-rendered.
>
> ⛔ **AND THE FIRST INSTRUMENT THAT PERTURBS THE MECHANIC RATHER THAN THE RENDERING SAYS THE
> TRANSFER PICTURE ABOVE IS MUCH TOO KIND** — [[r101_owner-ablation]], rule **7cj**. The re-render,
> the recolour and the rename all keep a board whose mechanic one of our tools implements. Remove
> each game's OWNER instead — the private-110 condition — and **0.9082 -> 0.1932**, 25 of 25 games
> moved, negative control exact. ⛔ **The floor is NOT flat, so no single number may be quoted**:
> 13 games under 0.01 against 9 at or above 0.30, split by whether any surviving tool CLAIMS the
> orphaned board (claimed n=11 mean 0.3725 · unclaimed n=14 mean 0.0523, of which 13 average
> **0.0014**). And 0.1932 is OPTIMISTIC — every claimant is one of OUR specialists near-missing a
> PUBLIC board. ⭐ **The failure is SILENT**: 14 of 25 orphaned games are seized at action 1 by a
> frontier explorer that holds all 500 actions for zero levels, with `primary_owns` FALSE — it never
> goes silent and never stalls, so it looks productive by every signal the harness watches. ⛔ Not a
> `graph` problem: dropping `graph` too gives 0.1925 because `world_model` does the identical thing.
>
> ⚠️ **AND THE OBVIOUS REPAIR — "teach the harness to notice" — IS MEASURED AND WORTH 0.0000 TODAY**
> ([[r101_lost-signal]], rule **7cm**). A run-intrinsic signal DOES exist (`coverage`, AUC 0.815 at
> action 50 over 255 outcome-labelled level segments — ⛔ labelled by outcome, not shape, because
> `m0r0` latches for 731 actions and clears FIVE levels). But it **loses to the clock alone** —
> 28.7% of doomed actions saved against the zero-loss clock's 34.9% — and only pays as a SUPPLEMENT
> (51.5%, zero levels lost). ⛔ All ten flagged segments come from the ABLATED arm, so on the shipped
> card it fires zero times; and what it saves are actions on levels scoring zero however they are
> spent, so it frees wall-clock, not points — **there is no better tool to hand the board to (7ba)**.
> ⭐ **So the lever is NOT a smarter give-up rule. It is having a second claimant at all.**
>
> ⛔⛔ **AND "THERE IS NO BETTER TOOL TO HAND IT TO" IS NOW MEASURED, NOT INFERRED — THE CHAIN
> TERMINATES AT CAPABILITY** ([[r101_routing-or-capability]], rule **7cq**). 47 tools × 25 games
> forced alone = 1175 runs through the same scorer. **An oracle that always picks the best surviving
> tool recovers 0.0034 of the 0.7150 the owner was worth — 0.5%.** In **21 of 25 games the best
> surviving tool scores EXACTLY what the ablated harness scores**, and on **10 of 25 NOTHING in the
> 47-tool registry clears level 1 without the owner** — ownership is not merely singular but
> **EXCLUSIVE**. Controls: owner-alone clears 25/25; no solo tool beats the full harness on any of
> the 25 (**7ba reproduced beyond its original five games**). ⛔ Detection is closed (7cm), routing is
> closed (7ac + this 0.5%), the tool set is closed (7ba/7bb/exclusivity). **No signal, no router, no
> model and no further per-mechanic specialist changes what happens on a board whose mechanic nothing
> implements. The only remaining lever is a fallback that can LEARN a board it has no tool for —
> stage two of the top policy, now measured rather than assumed.**
> ⭐ And 7bb's warning became a measurement: **12 of the 16 tools that clear anything on an orphaned
> board are from its never-holds-a-board roster**, so pruning the registry by observed tenure would
> delete exactly the tools that hold an unowned board.
>
> ⭐ **AND EFFICIENCY OVER CLEARED LEVELS HAS A STRUCTURAL CEILING OF +0.00796** (rule 7cb, one pass
> over `rounds/*/games/*.json`): only **FIVE** cleared levels in the whole 25 score below 1.0 —
> bp35 L2/L3/L5, lp85 L4, ls20 L7. Driving all five to a perfect 1.0 is worth eight thousandths of
> the mean, whatever any census finds. ⛔ **Compute that bound BEFORE opening an efficiency arm.**
> The inert-action census then priced the actual waste at **+0.000056**, all of it ls20, with 24 of
> 25 games gaining exactly zero — and a dead action is **9.2x** more likely on a level that never
> clears (9.82% vs 1.07%), where it is scored zero anyway.
> ⚠️ That smallness is a property of THE PUBLIC 25, where nineteen games sit at the cap. It is not
> evidence that inert actions are harmless on the 110, and must not be quoted in either direction.
>
> ⭐ **AND RENDER-DEPENDENCE NOW HAS EXACTLY ONE NAMED INSTANCE** (rule **7cd**): *a frame-only tool
> that identifies an object by whether it is DRAWN is reading PAINT ORDER, not mechanics.* s5i5 L4's
> 22 lost actions are ONE cell at (43,31) — the archived source lists the rider before the bar it
> rides, so the bar covers it, and `telescope`'s candidate set goes from 2 to 9. ⚠️ The fallback
> costs NOTHING on four of the five archived levels, so this is not "the fallback is bad"; the
> IDENTITY SIGNAL is a render fact.
>
> ⭐ **AND IT IS PROVED BY INTERVENTION, not merely correlated** ([[r101_zorder-rider]]): inject the
> rider evidence back into the archived board and change NOTHING else, and the level returns to 39
> actions and the game to 0.5833 — `[13, 30, 47, 39, 32, 31]` in BOTH arms. **The whole gap, gone,
> from one restored piece of evidence.** That is the difference between "these two co-occur" and
> "this one causes that one", and it is why the defect can be NAMED rather than suspected.
>
> ⭐ **Colour is safe** (rule **7ce**): two fixed-point-free permutations over all 25 games, 16,810
> frames, 211M cells relabelled — **one action moves in the whole set** (cd82 L3 33 -> 34, no score
> change), and there is not one numeric colour literal compared against a frame anywhere in the tool
> set. ⛔ And the archive covers **FOURTEEN** games, not fifteen: `environment_files_archive/sk48` is
> byte-identical to the live tree, a self-substitution carrying no evidence.
>
> ⭐ **The discarded outer band costs ZERO, and for a reason** (rule **7cf**): of the harness's three
> change signals only `board_changed` discards the band, exactly one tool consumes it (`deadsig`,
> the only `augmenter`), and its `_drop_dead` withheld something 918 times — **all 918 on bp35 level
> 6, which never clears**. The games whose band carries real CONTENT are exactly the ones where it is
> never called. ⛔ Widening is NOT licensed. ⚠️ What survives for the 110 is the shape: a game that
> renders feedback in the band AND is driven by `graph` would have its working actions withheld.
>
> **So the work is: find and name render-dependence, not chase the last 0.09.** ⭐ **FOUR THINGS ARE
> IN FLIGHT (2026-08-30 09:00). Continue one of them rather than open a seventh arm on a closed
> game** — and re-read the three rules above first, because three of the four exist BECAUSE of them:
>
> 1. **Z-ORDER MUTATION, all 25.** 7cd's defect was found only because s5i5 happened to have an
>    archive whose sprite list order differed. ⛔ The colour and rename arms CANNOT reproduce it — a
>    bijection preserves which sprite is drawn on top — so the campaign's only measured transfer
>    defect is the one the new instrument is blind to. Permute SAME-LAYER siblings only; validity
>    check is `scripts/_s5i5_srcdiff.py`; **positive control is s5i5's own 39 -> 61 on L4.**
> 2. ✅ **THE VISIBILITY-IDENTITY CENSUS — ANSWERED, rule 7cl. THE POPULATION IS NOT ONE.** 63 sites
>    under `tools/` + `harness/`; **14** carry 7cd's exact structure (a candidate set filtered with a
>    fallback to the UNFILTERED set); **five** filter on what is currently PAINTED — `telescope:1183`
>    (7cd's exemplar), `swivel:734` (the identical two lines), `blastclock:631`, `slotlaunch:755`,
>    `tether:413`. On a run, three are live: telescope and swivel on s5i5, blastclock on ka59 (33
>    evaluations, fallback fired 9 times). ⚠️ **The automated arm caught 3 of the 5** — two are only
>    visible by following an attribute into another module.
>
>    ⛔ **"ZERO EVALUATIONS" IS TWO DIFFERENT FINDINGS**: `slotlaunch` is registered and never wins a
>    board; `tether` wins r11l and never reaches the line. Neither is evidence the site is harmless —
>    only that this corpus cannot measure it.
>
>    ⭐ **AND THE WORST SITE HAS NO FALLBACK, SO 7cd'S OWN SHAPE UNDER-COUNTS THE CLASS.**
>    `lattice_maze:484` assigns identity by comparing a colour read NOW against one REMEMBERED — on
>    tu93 it cuts up to nine candidates down to exactly ONE on 163 of 187 evaluations, on a game
>    sitting at 1.0000. Its docstring carries the price, measured on that game's archived re-render:
>    a second piece drawn in the steered piece's colours took it from **9 levels in 188 actions to 4
>    in 1288 — a 6.9x blow-up**, against telescope's 1.56x. It is already REPAIRED (dead reckoning),
>    which is why it still scores 1.0000, and **no vocabulary could have found it** — no word in it
>    names paint. Recovered only by a STRUCTURAL arm for `== self._<remembered>`.
>
>    ⚠️ Widened to visibility/colour filters with NO fallback: **49 static sites, 39 evaluated on at
>    least one game**. The discriminator is not "does it narrow" — nearly every filter does — but
>    cutting MANY to exactly ONE (identity assigned from paint) or to ZERO (the object lost).
>    ⛔ **That is an EXPOSURE MAP, not a defect list**: cutting to zero is often the right answer.
>    ⛔ **No repair** — 7cd's reason: removing a visibility filter takes the tool to the unfiltered
>    set EVERYWHERE, which IS the 61-action behaviour.
>
> 3. ✅ **THE ABLATION TABLE — ANSWERED 2026-08-30, rule 7cj, and it names the campaign's next
>    lever.** Remove the tool that actually plays each game and score: **0.9082 -> 0.1932, 25 of 25
>    games moved.** ⛔ The hoped-for flat floor did NOT come back (median 0.0069, stdev 0.2558), so
>    **quote the PAIR, never the mean**: `~0.0014` is the analogue of *no tool fits* (14 games nobody
>    claims), `0.1932` is the analogue of *new but adjacent to something we implement* (11 games where
>    another of OUR specialists partially fits a PUBLIC board we built against — an unseen game has no
>    near-miss waiting, by construction).
>
>    ⭐ **AND THE LATCH IS REAL WHILE `_PRIMARY_CONF` IS REFUTED AS ITS CAUSE.** Fourteen ablated games
>    have exactly ONE `[harness] pick=` line for the whole run, and **every one of those tenures has
>    `primary_owns` FALSE** — the tool is eligible for retirement and is never retired, because a
>    frontier explorer **always proposes** (so `_EMPTY_TOLERANCE` never fires) and **always reaches a
>    new state** (so the 80-step stall never fires). **It looks productive by every signal the harness
>    watches, while clearing nothing.** That is worse than a bad threshold: no tuning addresses it.
>    ⛔ And it is not about `graph` — dropping owner AND `graph` gives 0.1925, with `world_model`
>    stepping into the slot and doing the identical thing. **The latch is a property of the fallback
>    POSITION, not its occupant**; "demote graph" is closed.
>
>    ⛔ **AND THAT LEVER WAS THEN MEASURED AND CAME BACK WORTH 0.0000 — rule 7cm.** A run CAN tell it
>    is lost, but only as a SUPPLEMENT to a clock and only in-sample. Three things in it change how
>    the next arm should be framed:
>    - **The classes are defined by OUTCOME, not shape.** "The fourteen latched runs are the
>      negatives" (my framing) is WRONG: m0r0 latches — one tenure, 731 actions, never re-decided —
>      and CLEARS FIVE LEVELS. The unit is a LEVEL SEGMENT labelled by whether it cleared.
>    - ⭐ **Elapsed time carries ZERO information at a fixed decision point** — AUC 0.500 BY
>      CONSTRUCTION, since every segment alive at action k has used exactly k actions. **A clock does
>      not discriminate between runs; it only decides when to stop.**
>    - **Alone, no candidate beats the clock.** `coverage@50 OR clock@311` saves 51.5% of doomed
>      actions at zero levels lost, against 34.9% for the zero-loss clock alone.
>    ⛔ **All ten flagged segments come from the ABLATED arm; on the shipped configuration the signal
>    fires ZERO times.** It frees WALL-CLOCK, not points — the actions it saves are on levels that
>    score zero however they are spent — **unless there is a better tool to hand the board to, and
>    7ba says on these boards there is not.**
>
>    ⭐ **SO THE CHAIN CLOSES SOMEWHERE ELSE THAN EXPECTED. The missing thing is not DETECTION and not
>    ROUTING — it is a DESTINATION: something to do when nothing in the registry fits.** That is a
>    capability question, and it is the open one.
>
>    ⭐ **THE LEVER, NAMED: the harness owns no signal meaning "I do not understand this board."**
>    Empty proposes, stall and the death clock are all satisfied by a tool that explores productively
>    and solves nothing. So the next thing to build is not another specialist and not routing — it is
>    a **goal-progress signal independent of "reached a new state"**, or a fallback that can recognise
>    its own failure. ⚠️ 7ch measured a live LLM inert on these 25; **this is exactly the case 7ch says
>    it cannot see**, because routing is what breaks when the right tool is absent.
>
>    ⚠️ One trap it nearly fell into, worth carrying: **ownership by ACTION SHARE is wrong on three of
>    five multi-tool games and it INVERTS** — bp35's plurality holder is `graph` (486 actions) but
>    `crag` clears L0-L4. Dropping the plurality holder on bp35/lf52/s5i5 costs EXACTLY ZERO, because
>    those actions are spent on a level the game never clears (7bq's shape). An ablation built on
>    action share would have ablated nothing on three games and reported "the harness copes".
>
> 4. ✅ **THE LLM ARM — ANSWERED 2026-08-30, rule 7ch. `arm llm` 0.908187, `arm fallback` 0.908187,
>    ZERO games differing**, on a Kaggle GPU with vLLM serving gemma4 (38 served completions, target
>    draws SUCCEEDING in the llm arm for the first time in the campaign, 34 re-decides in each arm,
>    104 extra seconds of real model work). The model ran, answered, drew targets, and changed
>    nothing. ⚠️ It does NOT say an LLM is useless — it says **these 25 cannot measure it**, because
>    nineteen sit at the cap and signature routing already picks a tool that clears. The private 110
>    are exactly the case where no tool fits, and this run cannot see that case. Same caveat shape as
>    7cb's about inert actions. _(Historical statement of the axis:_ rule 7ca).

⛔ **EVERY SHORT GAME AND EVERY TOOL-SET AXIS IS NOW CLOSED WITH PROOFS.** The remaining 0.0918 is
not reachable by tuning, routing, pairing, retiring differently, or repairing a tool — **SIX**
independent measurements say so. ⚠️ **Do not open a new arm without first reading which hypothesis
it repeats.**

⭐ **TENURE WAS THE LAST ONE, AND IT IS THE SMALLEST** (rule 7bq, all 25 games reproducing their
banked per-level counts):

```
tenure-ending events in the ENTIRE corpus:   9      (EMPTY 7 · STALL 2)
games that NEVER end a tenure:              20 of 25
total propose round-trips:               7,049      empty proposes among them: 70 = 1.0%
runs of consecutive empties that RECOVERED: 16      — FIFTEEN of them length ONE
```

⛔ There is no distribution to tune: `_EMPTY_TOLERANCE` decides **six** outcomes in the whole set.
And the run SHAPE answers "is 8 right" without an arm — a tool blips once or goes silent for good, so
**a tool empty eight times running really has run out.** That is why "retire later" (the `hold` arm,
inert) and "retire sooner" (evidence-gated, LOST ls20 a level) are both refuted.

1. **If an agent returns a change, GATE it**: `bash scripts/snapgate.sh <name> scripts/rounds/R101LP85GATE`.
2. **Before proposing anything on a stuck game**, read that game's row below AND the rules it cites.
   Nine hypotheses died on lf52 alone; seven of my own briefings were refuted by measurement.
3. **The honest remaining work is a CAPABILITY, not a constant** — see the closing note.

### ⭐ lf52 HAS MOVED — it is now a TENURE question, not perception (2026-08-30)

`cef09932` is KEPT despite moving no score (rule 7bn's exception): the run went from **DESTROYING
level 6 at action 124** and spending 376 actions on a dead board, to the level **still winnable at
action 500**. Restarts [267] → []; the fatal third capture never made; the camera unpinned from -57
to 12 distinct positions.

⛔ **AND THE TENTH HYPOTHESIS DIED WITH IT**: "widen perception and the move changes" is FALSE.
Handed the engine's TRUE six pads offline, `plan_moves` stops claiming `solved` **and returns the
IDENTICAL fatal capture** — tier 1 is cheapest-capture and that capture is the cheapest. A perception
repair alone would have been inert.

**WHERE IT SITS NOW:** `pegjump` holds **19 of level 6's 500 actions**; `graph` holds 225 and
`world_model` 117. With pegjump stopped, **`graph` made the identical fatal capture 193 actions
later.**

⛔ **AND THE TENURE READING OF THAT IS NOW CLOSED TOO** (rule 7bq). lf52 is the corpus's ONLY
multi-handover game — 5 of the 9 tenure-ending events in all 25 games happen here — and its
retirements are tools that **cannot read the board**, not tools that were interrupted: `railpeg`
retires with `_elsewhere` True and `_barren` 0, `pegjump` with a 24-cell map. Giving them longer is
the `hold` arm, measured inert on its sibling game. ⚠️ **So lf52 needs a tool that can see a board
wider than its frame — not more turns for one that cannot.**

### ⛔ WHAT NOT TO SPEND A DAY ON (each already measured, with the number)

- **bp35's `crag._rows` 10→9** — I called it a one-field perception defect. It is **downstream**:
  `_rows` is 9 at the entry to ALL 230 stitches and only a SUCCESSFUL stitch raises it, so the
  movement is produced BY the failure. The real cause is OVERLAP (8 of 8, best agreement 0.600) at a
  **one-window map** — a cold start. The repair fires and leaves every per-level count identical, and
  could never pay: levels 1-5 have **ZERO** losses and `crag` bids 0.00 on all 24 other games.
- **Handing a board back to the strong tool** — `crag` recovers only because the SUCCESSOR drives it
  into a readable window; the `hold` arm is measured INERT.
- **Forcing a pair** — 219 of 230 pairs, **ONE action count per game**. And ls20's forced pair is
  depth 6 / 922 actions against the harness's depth 7 / 645: **shallower AND slower.**
- **A margin trigger on bids** — would hand three CAPPED games to the general searcher.
- **Cross-level mechanic carry** — no tool in the 25 ever owns a level with another level after it
  that it sat out. There is no game on which to measure the hypothesis.

⛔ **THE REGISTRY IS NOW MEASURED FROM FIVE INDEPENDENT DIRECTIONS AND NONE FINDS THE GAP THERE:**
- **Forced PAIRS, 219 of 230**: each specialist plus every other tool, one at a time. Every game
  returns **ONE distinct action count** — bp35 727, lf52 824, dc22 926, s5i5 695, ls20 922. Not "no
  partner helps": **no partner ACTS.** ⛔ And ls20 is decisive the other way — its forced pair reaches
  depth 6 in 922 actions while the FULL HARNESS reaches depth 7 in 645, **shallower AND slower**. So
  composition is not what fails; **forcing a pair is.** The harness's value is choosing the successor
  at the right moment from the whole roster.
- **Why the strong tool goes EMPTY** (rule 7bh): 459 traced `propose` calls, **zero ILLEGAL**. bp35's
  `crag` quits on "window does not belong to this board" and the ONLY field that moves is
  `self._rows` **10 → 9** — the hazard its own docstring names, guarded in the band and left exposed
  in the stitch. ⛔ And the tool had not given up: its first threshold is 16 idles, the harness
  retires at **8**. ⭐ But `crag` recovers only because the SUCCESSOR drives it back into a readable
  window — **being displaced is what fixes it**, and the `hold` arm is measured INERT.

- 47 tools × 5 stuck games = 235 pairs, forced alone: **no tool beats the harness anywhere**, and
  **exactly ONE does anything at all on each board** (43–46 of 47 clear NOTHING). On ls20 the
  harness reaches level 7 while no single tool passes 6 — the composition earns a level none of its
  parts can reach.
- Tenure across all 25: **17 of 47 tools never hold a board**, and **19 of 25 games are played start
  to finish by ONE tool**. ⚠️ Not an argument to delete them — the eval is 110 PRIVATE games with
  the same set — but `loop.py` interrogates every tool at every re-decide and 19 of 47 have a
  `detect` that mutates.
- Routing: **no handover was ever lost to a tie, and none can be** (registration order puts every
  specialist ahead of `graph`); 41–43 of ~48 tools bid 0.00 at every decision point.

⚠️ **AND THE HONEST POSITION ON THE REMAINING 0.0918**: bp35, s5i5 and dc22 each need a capability
the tool set does not have — a first attempt that knows which glyph kills; a planner that can move a
piece already home; a 297k-state joint planner on a game with 8 actions of slack. lf52 needs one
better choice. Nothing here is a constant to tune.

### ⛔ CLOSED TODAY WITH PROOFS — do not re-open without NEW evidence.

- **lf52's MAP is a dead end for the score.** Three of four hypotheses refuted by an engine oracle
  (negative control reproducing the banked [8,52,60,64,139] exactly): the model does NOT discard the
  map (`known_drops` 0, final == max == 98); growth IS ranked (boarding moves exist at 22 points and
  `_rail_reach` already fires); and the camera has exactly three movers, all exhausted — a jump onto
  the cart at the home offset, eleven laden drives, and a jump the engine never offers again.
  ⭐ **And opening the last column wins NOTHING**: the win predicate is `len(fozwvlovdui*) == 2`, red
  is uncapturable, and the piece in the unseen column can simply be the survivor. **The level is
  decided at the THIRD capture (action 124), after which the engine offers zero legal jumps.**

- **bp35 = 0.2456.** Every attempt is a near-pure traversal with no slack: 7 spike discovery (proven
  irreducible — nothing in the frame says which of the ten drawn kinds kills), 34 building 140 of the
  board's 370 map cells, 44 clearing in **43 against a human 48**. `_stranded` and a pre-entry veto
  are both refuted; the flat turns TRAVERSE and revisiting is ANTI-correlated with the score (the
  0.9560 board does twice the true revisiting of the 0.3044 one). ⚠️ The human clears board 2 in ONE
  attempt, so the whole gap is that it neither dies to the spike nor gets walled in on the way.
- **s5i5 = 0.5833, not reachable by `swivel` as built.** Thirty arms across five fans, all 0.5833.
  An engine A* with nothing banned clears in 45 clicks **opening by moving a rider that is already
  home** — and `swivel`'s decomposition gives each subproblem only the controls touching its own bar,
  so that move belongs to no subproblem. All 41 runs banning it are EXHAUSTED. Three missing
  capabilities, none a constant.
- **dc22 = 0.7143.** The crane is fully decoded (4 plates measured 1:1, 69 presses, zero cross-talk,
  precondition frame-visible). ⛔ The blocker is OURS — `phase.py:430` condemns a tile if ANY pixel is
  a banned colour and every plate sprite contains colour 0. Censused across the 25: dc22 only
  (107,969 mixed rejections; every other game ZERO, and 24 of 25 record no tool turns at all). Proof
  is one cell — (55,34) condemned at turn 582, the avatar STANDS IN IT at turn 680. ⚠️ Both repairs
  are measured negative, and levels 1-5 have EIGHT actions of slack, so probing on them loses more
  than level 6 returns.

## THE GATE — one command, private snapshot, no collisions (rule 7l)

```
bash scripts/snapgate.sh <name> scripts/rounds/R101LP85GATE 8 4000
bash scripts/ptest.sh --dirty tests/test_x.py     # tests, on the BOX; TARGET it (whole suite = 24 cores)
bash scripts/pfan.sh <name> <probe.py> <n> "<arg>" 6   # any probe, snapshotted; NAME is required
```

⛔ Do NOT use `scripts/rounds/gate_tool.sh` — it syncs the SHARED `~/admorphiq`, so it carries every
agent's work-in-progress and the tree moves under it. Both of its documented traps are that cause.
`snapgate.sh` archives HEAD into a private dir on the box; two gates run at once and a rider cannot
ride.

⚠️ In a fan-out, `ptest.sh --dirty` ships EVERY PEER'S uncommitted tree, so a red suite is not
evidence about your change (rule 7ae). Grep whether the failing modules can even see your symbol
before spending a control run.

## ⭐ THE PRIVATE-110 AXIS — and the headline it used to carry is REFUTED (2026-08-30)

⛔ This block used to say "`graph` is what a stuck game looks like" and offer >40% inert as a
game-agnostic stall detector. **Measured at the harness's own re-decide point, on the CURRENT tree,
with all nine games reproducing the R101WA30 baseline TO THE ACTION — it is true of TWO of the four
stuck games, not four:**

```
lf52 L6   graph holds 366 of 500      41-49% inert     <- fits
bp35 L6   graph holds 486 of 500      41% inert        <- fits
dc22 L6   gantry holds 500, ZERO HANDOVERS ALL GAME    <- the 70.6% inert is the SPECIALIST's
s5i5 L7   linkage holds 461, graph never runs          <- same
```

`gantry` bids 0.86 against `_PRIMARY_CONF` 0.70, so it is never stall-retired, and returns a legal
plan on 924 of 925 refills. The earlier attribution predated the gated `phase.py` base. ⚠️ **A table
must reproduce its own baseline before it is believed.**

### What the selectivity measurement DID settle, permanently

```
5 retirements, ALL through the EMPTY path.  ZERO stall-swaps.  ZERO death-clock.
3 ties, ALL broken by REGISTRATION ORDER; registry.py puts every specialist ahead of graph (43/48).
41-43 of ~48 tools bid 0.00 at EVERY decision point.
```

⛔ **Routing is not the defect and cannot be** — a specialist losing a tie to `graph` is structurally
impossible. The boards have no second claimant, so the answer is a TOOL, not a tie-break. Nobody
should look for a routing defect again.

⚠️ The harness's stderr MISREPORTS the reason: it printed `feedback='action no new state x3'` at an
EMPTY retirement. `_feedback` is the last message set, not the cause.

### Two transfer facts, both measured 2026-08-30

- **The gains reach the submission path**: `--agent unified` 0.9069 and `--agent kaggle_unified`
  (the official wrapper the notebook would ship) 0.9069, 25 games, none differing. The wrapper
  MIRRORS `_make_agent("unified")` and a mirror drifts — five research commits once shipped in the
  deployed fallback unmeasured and the card moved 0.20 -> 0.18 with no attributable cause.
- **The tools do not overfit their version hash**: on `environment_files_archive/` (a DIFFERENT
  hash of 15 games — a re-render with different sprite tags and coordinates), **14 of 15 are
  identical to four decimals**, including every 1.0000; s5i5 alone moves -0.0240. Mean 0.9532 ->
  0.9516. ⚠️ Weak evidence, and it must not be oversold: a re-render is the same game with different
  tags, and the 13 hand-written adapters passed this same test 7/7 while moving the hidden score by
  nothing. It rules out the cheapest failure — a tool keyed to a sprite name or a coordinate.

