# CAMPAIGN — ACTIVE

> The plan that survives a context compaction. Read this before choosing a direction.

## STATE (2026-08-29 19:35, all gated on the full 25)

**MEAN = 0.9082**, NINETEEN games at the 1.0 cap, cumulative regressions ZERO.
Baseline dir: `scripts/rounds/R101LP85GATE/games` — use it as the gate's BASE.

⭐ **AND THE GAINS REACH THE SUBMISSION PATH**, measured 2026-08-30 after fifteen source changes:
`--agent unified` 0.9069 and `--agent kaggle_unified` (through the official wrapper the notebook
would ship) 0.9069, 25 games compared, none differing. Run that check after any day of harness work —
the wrapper MIRRORS `_make_agent("unified")` and a mirror drifts; five research commits once shipped
in the deployed fallback unmeasured and the card moved 0.20 -> 0.18 with no attributable cause.
⚠️ Not a leaderboard prediction: the hidden score of the generic path is UNMEASURED.

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

1. **LIVE (four agents)**: lf52's third capture · ⛔ ls20's handover is CLOSED (my
   briefing was wrong twice: only TWO of the ten actions are keymaze's and both MOVE; 231 is
   INVARIANT for every handover from action 9 to 17) · **cross-level mechanic carry**,
   the only axis today that describes the private 110 · and the gate-guard wiring.
   ⛔ lp85 DONE (0.9767). bp35, s5i5, dc22 and ls20's ORDERING axis are all CLOSED WITH PROOFS.
2. Integrate each result as it lands and GATE it. Keep ceph busy between integrations.
3. Any surviving change: update the STATE block above with the new gated mean.

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

