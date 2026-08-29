# ACTIVE CAMPAIGN — the plan that survives a turn boundary

⛔ WHY THIS FILE. Between turns I keep nothing. A plan stated in prose is gone by the next tick, so
what I actually do is "the next question implied by the last tool output" — serial by construction,
and the measured cause of 76 commits with zero surviving source changes on 2026-08-29. A plan in a
FILE, printed into every turn by a hook, is the only kind that survives.

## GOAL
Clear the remaining sample levels. Score 0.8935, 17/25 at the cap. Only a SURVIVING source change
that raises the full-25 mean counts.

## STRUCTURE — one background agent per game, orchestration here
All eight incomplete games have a dedicated background agent (launched 2026-08-29 16:40):

| game | score | what its agent is on |
|---|---|---|
| bp35 | 0.2220 | does the crumbling platform actually BLOCK level 6? |
| lf52 | 0.2727 | can a pad MOVE without capturing? no adjacent pair exists |
| s5i5 | 0.5833 | ONE of two targets uncovered; all 60 seeds collapse the level |
| dc22 | 0.7143 | next level is its LAST (+0.0114); pocket of 3 boards, inert below row 32 |
| wa30 | 0.8000 | next level is its LAST (+0.0080); 507 effective actions, budget NOT enforced |
| ls20 | 0.8442 | efficiency only: 302 actions vs human 186, attempt 2 knows the map and costs 146 |
| lp85 | 0.9099 | efficiency only: level 4 is 33 actions vs human 16 |
| re86 | 0.9908 | efficiency only: level 2 is 46 vs 42 — four actions from perfect |

⛔ MY JOB IS ORCHESTRATION, NOT PROBING. Do not write probes for a game that has an agent. Integrate
results, gate them on the full 25, and keep the box busy.

## CLOSED BY MEASUREMENT — do not re-open without new evidence
- 47 tools solo x 5 stuck games: none goes deeper than the harness already does
- 9 tool combinations: none beats the best single tool
- patience (NOPROGRESS 6x, STALL), alignment threshold, shift range, pitch re-fit, tool revival,
  admissibility bypass, shape matching, probe-order memory, lethal-glyph probing, vocabulary carry,
  switch-reset, gauge speed-up — all built, measured, reverted
- dc22 L6: 54,000 random actions, 4,096 click-move pairs, 1,024 clicks x 3 positions — no clear;
  the cycling tile is real, reachable, and NOT the blocker
- s5i5 L7: 60 seeds, all COLLAPSE, coverage never rises above 1 of 2
- wa30 L9: budget declared 70 but NEVER ENFORCED — one unbroken 507-action attempt

## THE STANDING ORDER (rule 7h)
Never write one probe. List every hypothesis, then run them together:
    bash scripts/pfan.sh PROBE.py 60 ARG        # one probe, 60 seeds
    bash scripts/ceph_sweep.sh                  # tools x games
    ssh ... xargs -P 60                         # different probes, together

## NEXT ACTIONS — pick from here, not from the last tool output
1. Wait on the eight agents; integrate each result as it lands and GATE it on the full 25.
2. Keep ceph busy between integrations — the idle hook says when it is not.
3. Any surviving change: re-measure the full 25 and update the LOG below.

## THE GATE FOR EACH GAME — one line, ready to run the moment an agent returns
Baseline re-confirmed 2026-08-29 16:48: **R101REACH = 0.8935 over 25, no game differing.**

```
bash scripts/rounds/gate_tool.sh R101BP35 scripts/rounds/R101REACH vc33 crag
bash scripts/rounds/gate_tool.sh R101LF52 scripts/rounds/R101REACH vc33 railpeg
bash scripts/rounds/gate_tool.sh R101S5I5 scripts/rounds/R101REACH vc33 swivel
bash scripts/rounds/gate_tool.sh R101DC22 scripts/rounds/R101REACH vc33 gantry
bash scripts/rounds/gate_tool.sh R101WA30 scripts/rounds/R101REACH vc33 shepherd
bash scripts/rounds/gate_tool.sh R101LS20 scripts/rounds/R101REACH vc33 fogscout
bash scripts/rounds/gate_tool.sh R101LP85 scripts/rounds/R101REACH vc33 cyclepress
bash scripts/rounds/gate_tool.sh R101RE86 scripts/rounds/R101REACH vc33 <tool the agent names>
```

⛔ A gate that does not RAISE the mean means the change is reverted — that is the rule that kept
cumulative regressions at zero through fifteen reverted repairs today. ⚠️ Gates must not overlap with
a sweep on the same box; run them one at a time.

## LOG — what moved the score
(nothing yet today: 0.8935 unchanged, zero surviving source changes)
