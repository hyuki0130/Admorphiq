# CAMPAIGN — ACTIVE

> The plan that survives a context compaction. Read this before choosing a direction.

## STATE (2026-08-29 19:35, all gated on the full 25)

**MEAN = 0.8962**, eighteen games at the 1.0 cap, cumulative regressions ZERO.
Baseline dir: `scripts/rounds/R101RE86/games` — use it as the gate's BASE.

Moved today, each gated: **re86 CONQUERED 0.9908 -> 1.0000 (8/8)**, ls20 0.8442 -> 0.9040,
lp85 0.9099 -> 0.9677. First movement in a day.

The seven still short, largest gap first:

```
lf52  0.2727   gap 0.7273   level 6 CLEARED LIVE by an oracle in 91 of 640 actions
bp35  0.2220   gap 0.7780   level 6 optimum 41 actions vs 87 human — CLOSED, see below
s5i5  0.5833   gap 0.4167   level 7, allowance 200, every seed COLLAPSES
dc22  0.7143   gap 0.2857   levels 1-5 all at 1.0; oracle clears 6/6 at 1.0000, 3/3
wa30  0.8000   gap 0.2000
ls20  0.9040   gap 0.0960   all 8 fallback presses are inert; it is a FUEL game
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
1. SIX agents are live: dc22-into-gantry, lf52 camera-vs-state, s5i5, wa30 level 9,
   ls20 level 7, and the death-clock allowance ledger.
2. Integrate each result as it lands and GATE it. Keep ceph busy between integrations.
3. Any surviving change: update the STATE block above with the new gated mean.

## THE GATE — one command, private snapshot, no collisions (rule 7l)
```
bash scripts/snapgate.sh <name> scripts/rounds/R101RE86 8 4000
```
⛔ Do NOT use `scripts/rounds/gate_tool.sh` — it syncs the SHARED `~/admorphiq`, so it carries every
agent's work-in-progress and the tree moves under it. Both of its documented traps are that cause.
`snapgate.sh` archives HEAD into a private dir on the box; two gates run at once and a rider cannot
ride. Tests: `bash scripts/ptest.sh --dirty tests/test_x.py`.

## CLOSED BY MEASUREMENT — do not reopen without new evidence
- **frame_2d reading the last layer**: the measurement was RIGHT (layer 0 is stale at 100% of level
  transitions in all 21 games) and the change cost **0.8962 -> 0.6525, fourteen games**. Rule 7o.
- **bp35 level 6**: reachable in 41 actions, and getting there costs 4.6x search states +
  `_MAX_EDITS` 6->8 + `_MAX_EXPAND` 40k->120k, for +0.0053. Declined. Exhaustion proofs recorded.
- **the pixel allowance reader**: of twelve games declaring an allowance, exactly ONE draws it
  readably. Refuted. The DEATH CLOCK replaces it and recovers nine, four of them undeclared.
- 47 tools solo x 5 stuck games, and 9 tool combinations: none goes deeper than the harness.
- Thirteen repairs built, measured, reverted (patience, alignment threshold, shift range, pitch
  re-fit, tool revival, map-drop-on-flip, admissibility bypass, shape matching, probe-order memory,
  lethal-glyph probing, vocabulary carry, switch-reset, gauge speed-up).

## ASSETS FOUND TODAY, unused — check these before writing anything new
- **A game may RENDER ITS OWN LEGAL-MOVE ORACLE.** lf52 draws a ring on a selectable piece and
  markers at each legal landing. ⚠️ The markers are FOUR TWO-PIXEL BLOBS, so a min-blob-size-4
  filter reads exactly like "there is no oracle". Look for one before writing a search.
- **The death clock**: `allowance = min(death_lengths) - 1`, learnable from ONE death, no source
  access. Nine games, four of them undeclared. Trust it only when two deaths agree.
- **43 of 43 fallback presses are NOPLAN** — zero ILLEGAL, zero THREW. The tool genuinely has
  nothing; the action vocabulary is not the problem.
- `scripts/_bp35_sim.py` — differential-tested bp35 simulator, 0 mismatches over 40 sequences.

## THE FAILURE MODE THAT COSTS THE MOST
⛔ **An instrument that lies toward "there is nothing here."** Three today: a min-blob-size-4 filter
hid lf52's oracle; a `!=` level test read a collapse to level 0 as a clear; and a layer-staleness
instrument took SIX versions, five of which scored its own known positive at ZERO — four of those
would have been written up as "no other game has this problem", the exact opposite of the truth.
**Run every checker on input whose verdict you already know, in BOTH directions.**
