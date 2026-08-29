# CAMPAIGN — ACTIVE

> The plan that survives a context compaction. Read this before choosing a direction.

## STATE (2026-08-29 19:35, all gated on the full 25)

**MEAN = 0.9069**, NINETEEN games at the 1.0 cap, cumulative regressions ZERO.
Baseline dir: `scripts/rounds/R101WA30/games` — use it as the gate's BASE.

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

## ⭐ THE ONE AXIS THAT DESCRIBES THE PRIVATE 110, not the public 25 (2026-08-29)

```
no tool that is SOLVING a board is more than 7% inert   0% 0% 1% 1% 2% 7%
`graph` is NEVER below 41%                              41% 49% 71%
```

`graph` is the fallback that inherits every board no specialist claims, so **`graph` is what a stuck
game looks like**. That is a free, frame-independent, game-agnostic STALL DETECTOR — >40% inert over
a tenure says "no specialist owns this board" without knowing the game.

⛔ The direction of the correlation is NOT established: a searcher bumping walls it has not mapped is
exactly what being stuck looks like, so the inert rate is at least as likely a symptom as a cause,
and removing lf52's waste did not open its level. **The question worth funding is SELECTIVITY — why
does the board fall through to graph — not graph's hit rate.** Measure which tools bid, and what,
AT THE HANDOVER FRAME (`bid_matrix.py` reads FIRST frames only and cannot answer it). ⚠️ On dc22
`gantry` bids and then latches dead at action 6, so measure the bid AND whether the bidder survived.

## THE GATE — one command, private snapshot, no collisions (rule 7l)
```
bash scripts/snapgate.sh <name> scripts/rounds/R101WA30 8 4000
```
⛔ Do NOT use `scripts/rounds/gate_tool.sh` — it syncs the SHARED `~/admorphiq`, so it carries every
agent's work-in-progress and the tree moves under it. Both of its documented traps are that cause.
`snapgate.sh` archives HEAD into a private dir on the box; two gates run at once and a rider cannot
ride. Tests: `bash scripts/ptest.sh --dirty tests/test_x.py`.

## CLOSED BY MEASUREMENT — do not reopen without new evidence
- **lf52's stall position is genuinely CLOSED**, measured by FORCING every legal move the tool's own
  successor function offers (`scripts/_lf52_stall.py`): 6 moves, best opens ONE cell, all four drives
  open ZERO, and no boarding move EXISTS — so the two-step board-and-drive plan is refuted at its
  root, not merely unsupported. The map is still the lever (the veto has never been asked with all 8
  pads visible) but it cannot be opened FROM THERE. Six measurements; no frontier tier for this board.
- **`_reborn` does not transfer to bp35**: its eight attempts are eight DISTINCT sequences. And the
  re-seed repair WORKS and is worth nothing — crag then emits the identical 64-action loser three
  times. ⛔ Repairing an EMPTY path can expose a REPLAY problem underneath it.
- **the level-transition handover tax**: 149 transitions over 25 games, 54 inert actions in the
  6-action window, **0.36 per transition**, seventeen games at exactly ZERO. Even the upper bound —
  every one of those actions pure waste and perfectly recoverable — is ~2 actions per game against
  per-level counts of 30-400. And the re86 claim that started the axis measures 0.00.
- **the give-up budget**: `HARNESS_NOPROGRESS` 500 -> 3500 gives all five dying games ~7x the
  actions on their wall level and clears NOTHING (bp35 740->3787a, dc22 925->3928a, lf52 823->3828a,
  s5i5 694->3709a, wa30 1091->4000a, every score identical). ⛔ In RHAE an UNCLEARED level scores
  zero however long it runs, so this was pure upside if it worked at all. The wall is not a budget.
  Corroborated independently: 54,000 blind actions on dc22 level 6 clear nothing.
- **dc22's 70% inert actions are a SYMPTOM, not a lever**: `gantry` latches dead at action 6 and the
  500 actions are graph/world_model on an 18-cell island with gated exits. Saving them buys 0.0000
  because the level scores zero either way. (Elsewhere the same waste on a level that DOES clear
  would be a real efficiency lever — the number is right, the game is wrong.)
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
