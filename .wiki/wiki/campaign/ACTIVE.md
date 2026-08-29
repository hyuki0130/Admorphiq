# CAMPAIGN — ACTIVE

> The plan that survives a context compaction. Read this before choosing a direction.

## STATE (2026-08-29 19:35, all gated on the full 25)

**MEAN = 0.9082**, NINETEEN games at the 1.0 cap, cumulative regressions ZERO.
Baseline dir: `scripts/rounds/R101LP85GATE/games` — use it as the gate's BASE.

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

Moved today, each gated: **re86 CONQUERED 0.9908 -> 1.0000 (8/8)**, ls20 0.8442 -> 0.9040,
lp85 0.9099 -> 0.9677. First movement in a day.

The seven still short, largest gap first:

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
lp85    0.9767   gap 0.0233   L4 = 18 vs a human 16; the six confirmations are load-bearing.
```

## ⭐ THE DECOMPOSITION THAT SAYS WHAT KIND OF PROBLEM EACH GAME IS (2026-08-29, from the gate's own per_level)

```
game     score  reached  per-level (* = at the 1.0 cap)      what is actually lost
dc22    0.7143     5     * * * * *                           DEPTH ONLY — one level, its last
lf52    0.2727     5     * * * * *                           DEPTH ONLY
s5i5    0.5833     6     * * * * * *                         DEPTH ONLY
wa30    0.8000     8     * * * * * * * *                     DEPTH ONLY — one level, its last
ls20    0.9040     7     * * * * * * +                       EFFICIENCY, L7 = 0.62, one level
lp85    0.9677     8     * * + . * * * *                     EFFICIENCY, L4 = 0.24, L3 = 0.94
bp35    0.2220     5     * . + * .                           BOTH — L2 = 0.30, L5 = 0.30
```

⛔ **FOUR OF THE SEVEN LOSE NOTHING BUT DEPTH.** Every level they reach is at the cap, several
faster than the human, and the game simply ends short. For those games there is no efficiency work
to do at all and a "make the tool faster" change cannot help — the target is the NEXT level and
only the next level. dc22 and wa30 are one level from the end.

⚠️ Reading a stuck game as ONE NUMBER hides this completely, and it is one command away:
`per_level` in `scripts/rounds/*/games/*.json`.

⚠️ bp35's two 0.30 levels are not slowness. Its human baselines EXCEED the game's own action
allowance (87/131/163 against 64/128/192), so those baselines already contain a retry — "87 actions
vs 48 human" is TWO ATTEMPTS, not one slow one. Its efficiency loss is a FAILURE RATE.

## NEXT ACTIONS — pick from here, not from the last tool output

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

