---
round: R89
axis: probe / next-level mechanic-class + feasibility (bounded investigation)
keywords: r11l, l5, level5, whkxtx, collect-match, colour-set, puukul, dirwzt, mechanic-class, multi-session, probe
verdict: Level 5 (player idx 4) = NEW HYBRID mechanic (drag-assembly + whkxtx collect-and-colour-set-match) — MULTI-SESSION, NOT bounded; no build; floor 4/6 unchanged
commit: (this docs round)
---

# R89 — r11l L5 probe (task #115): next-level mechanic class + feasibility

> Bounded source-authoritative probe of r11l level 5: identifies a NEW hybrid
> mechanic (drag-assembly + whkxtx collect-and-colour-set-match), classifies it
> multi-session (not bounded), no build — floor 4/6 untouched.

Bounded investigation of the next uncleared r11l level after [[r87_r11l-l3-colour-blind-trial]]
(4/6 @ 0.2594). Source-authoritative, no build.

## Level indexing (verified)

`environment_files/r11l/495a7899/r11l.py` `levels = [Level1 … Level6]` — **6 levels**
(win_levels=6). r11l 4/6 = Levels 1-4 cleared:
- Level 1 (idx0): 1 creature (pumlzd) — drag-assembly.
- Level 2 (idx1): 2 creatures (orrqlj 3-leg + pumlzd) — drag-assembly (R85).
- Level 3 (idx2): 2 creatures (grhcew 4-leg + pumlzd) — drag-assembly (R85).
- Level 4 (idx3): 3 creatures, MULTI-COLOUR bodies (blxuubrengnt / orrqlj…pumlzd /
  yeogyfgrhcew) + dirwzt distractors — drag-assembly, R87 colour-blind + nested +
  trial.
- **Level 5 (idx4) = the next uncleared.**

## Verdict — Level 5 is a NEW HYBRID mechanic (NOT bounded)

Level 5's sprite list mixes the drag-assembly class with a NEW win path:
- **Drag-assembly creatures** (`blxuubrengnt`, `yeogyfgrhcew`) — R87 machinery applies.
- **`whkxtx` COLLECT-AND-COLOUR-SET-MATCH creatures** (`roefwu-whkxtx`,
  `roefwulewcui-whkxtx` + `puukul-*` collectibles). Engine truth: `zlkgwqnxrp`
  (l.1585) — a collector ABSORBS the pixels of any `owuypsqbino` piece it collides
  with; `ldzvchvkvp` (l.1601) — colour-SET equality; win-branch (l.1770-1781) — a
  body-less creature wins when its collector (having absorbed the right SUBSET of
  pieces) overlaps its target AND its accumulated colour set EQUALS the target's.
  So the goal is a subset/exact-cover selection (which pieces to absorb so the union
  matches the target colour set) + collision-order navigation — NOT a centroid drag.
- **`dirwzt` sprites are DISTRACTORS** (skipped: `"dirwzt" in name` in the win check).

WIN requires ALL non-dirwzt creatures satisfied, so the undecoded whkxtx mechanic
blocks the clear regardless of the drag-assembly half. **This is a MULTI-SESSION
decode + build, not a bounded pass.** Level 6 (idx5) has even more `puukul-*`
variety — same or harder class.

## De-risked spec for a future round (multi-session)

1. Perception: detect (a) drag-assembly creatures (R87), (b) whkxtx collectors,
   (c) `owuypsqbino` collectible pieces + their colours, (d) each collector's target
   colour set.
2. Per collector: solve the SUBSET of collectibles whose colour union == target
   colour set (exact-cover / subset-sum over colours).
3. Plan a navigation order colliding the collector with exactly those pieces then
   the target, avoiding the defgjl obstacle (reuse the strike-aware body-hazard idea).
4. Compose with the drag-assembly planner for the mixed level.

Floor 4/6 @ 0.2594 unchanged (no code touched). Related:
[[r87_r11l-l3-colour-blind-trial]] · [[../games/R11L]] Notes R89.
