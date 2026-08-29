# CAMPAIGN — ACTIVE

> The plan that survives a context compaction. Read this before choosing a direction.

## STATE (2026-08-29 19:35, all gated on the full 25)

**MEAN = 0.9069**, NINETEEN games at the 1.0 cap, cumulative regressions ZERO.
Baseline dir: `scripts/rounds/R101GRAPHOWN/games` — use it as the gate's BASE.

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
lf52  0.2727   gap 0.7273   ⛔ the stall position is CLOSED — see below. Do not build a frontier tier.
bp35  0.2220   gap 0.7780   ⭐ the WINNING attempt already beats the human (43<48, 30<33); the whole
                             loss is EXPLORATORY DEATHS. Removing them = 0.3304, +0.0043, WITHOUT
                             level 6. Needs lethality read from the frame BEFORE contact.
s5i5  0.5833   gap 0.4167   level 7 solvable in 24-28 clicks; _MAX_OPEN is cut off just short   level 7, allowance 200, every seed COLLAPSES
dc22  0.7143   gap 0.2857   levels 1-5 all at 1.0; oracle clears 6/6 at 1.0000, 3/3
ls20  0.9121   gap 0.0879   all 8 fallback presses are inert; it is a FUEL game
lp85  0.9677   gap 0.0323
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
1. Agents live on: dc22 (the crane plate), bp35 (lethality from the frame), s5i5, and SELECTIVITY.
2. Integrate each result as it lands and GATE it. Keep ceph busy between integrations.
3. Any surviving change: update the STATE block above with the new gated mean.

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

