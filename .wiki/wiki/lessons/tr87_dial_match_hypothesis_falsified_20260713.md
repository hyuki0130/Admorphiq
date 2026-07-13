---
type: lesson
symptom: "TR87 mechanism decoded (5-column 7-state cyclic dial + static targets) but every natural visual-match win-rule fails"
severity: warn
first_seen: 2026-07-13
---

# TR87's dial win-rule is NOT visual pattern equality — five hypotheses falsified

> Discovery incident log: the obvious "spin each dial until its pattern
> visually equals its column's target" hypothesis for [[../games/TR87]] was
> exhaustively disproven across five variants, all computed OFFLINE against
> one captured trace (zero extra game actions) — this page exists so a future
> session does not re-spend a live-trace cycle re-deriving the same negative
> result.

## What was measured (the confirmed, NOT-falsified structure)

Live-traced, frame-only (see [[../games/TR87]] for the full write-up):
five columns, each a bar1 (top, static) / bar2 (bottom, editable) pair.
ACTION3/ACTION4 move a selection bracket between the 5 bar2 columns.
ACTION1/ACTION2 step the bracketed column through a **7-state cyclic dial**
(`ACTION1` = +1, `ACTION2` = exact inverse; verified: 7x `ACTION1` returns
byte-identical to state 0, and `ACTION2` then `ACTION1` returns to the start
state). bar1's 5 glyphs are confirmed 100% static across the entire trace —
the natural reading is "target a dial must be spun to match."

## What was tried and falsified

All five run OFFLINE against ONE capture (35 dial-state masks = 5 columns x
7 states, the 5 bar1 target masks, and the 12 static upper-grid decorative
patterns — no additional game actions spent):

1. **Direct boolean-mask equality** (dial state == target, any
   column-pairing) — zero matches, 5x5=25 same-column and 175 cross-column
   comparisons.
2. **Dihedral equality** (4 rotations x mirror = 8 transforms of the target,
   compared to all 35 dial states) — zero matches.
3. **Complement equality** (dial == NOT target, + dihedral variants of the
   complement) — zero matches.
4. **Colour-cell COUNT equality** (weaker than shape equality: just does the
   dial state's cell count match the target's?) — columns 0, 1, and 4 have
   **zero** dial states matching their target's count at all; only columns 2
   and 3 have any count-matching states. A solvable per-column puzzle should
   have at least one candidate per column under even this weak condition, so
   this is itself evidence against a simple per-column matching rule, not
   just an inconclusive negative.
5. **Upper-grid-as-answer-key** (the 12 "decorative" pieces atop the board,
   confirmed static, compared to all 35 dial states with dihedral variants)
   — matches WERE found, but they are a red herring: exactly 5 of the 12
   upper patterns each matched ONE dial state per column, uniformly across
   ALL 5 columns (e.g. one upper pattern matched dial0-state2, dial1-state1,
   dial2-state3, dial3-state5, dial4-state0). This is the signature of the
   upper grid decoratively sampling the SAME finite 7-shape "digit" palette
   the dials cycle through — a rendering-engine coincidence, not an encoded
   answer, since it fires uniformly regardless of which state is actually
   correct for that column.
6. **Side-channel scan**: every one of the 35 press-transition frame pairs
   was diffed OUTSIDE the known dial box and HUD row, looking for any
   completion/correctness indicator elsewhere on the board (a flash, a
   counter, a colour change). None found.

## What it taught

An 8B-attention-budget-worthy takeaway: when a game's "obvious" mechanic
(rotate/cycle-to-match-a-shown-target) is structurally confirmed (the cyclic
dial, the static target, the counter) but the MATCH rule itself fails under
every reasonable transform, do not keep guessing shape-comparison variants
against a move-limited game — the offline-first approach (capture once,
compute many hypotheses locally) is exactly what avoided burning real budget
here, and should be the default posture whenever the interactive mechanism
is understood but the win CONDITION is not.

## Recovery / open leads for a future session

Not yet tried, listed so they aren't re-derived from scratch:
- Positional/index encoding — does the target's identity map to a NUMBER
  (e.g. count mod 7, or a fixed index unrelated to visual shape) rather than
  a pattern?
- Does one bar1 target genuinely correspond to a DIFFERENT bar2 column than
  its own (a shuffled 1:1 assignment) rather than same-column pairing — this
  was tested via cross-column comparison in hypothesis 1/2/3 above (still
  zero), so a shuffled-pairing model is ALSO ruled out, not just same-column.
- Does correctness require ALL 5 columns simultaneously correct before ANY
  observable change happens (i.e. no partial-credit signal exists to detect
  one column at a time) — would explain why the side-channel scan (which
  only tested single-column presses) found nothing.
- Read the game's actual internal transition logic once, dev-time only (not
  for the shipped agent, purely to shortcut the hypothesis space) if a
  future session has budget for it — this page exists precisely so that
  shortcut, if taken, doesn't repeat hypotheses 1-6.

## Falsification

This page is falsified the moment ANY of hypotheses 1-6 above is found to
actually hold on a corrected re-measurement (e.g. a bbox/crop bug in the
original capture) — if so, update this page's verdict rather than deleting
it, and record what the bug was.

## Related

- [[../games/TR87]]
- [[../rounds/r53_unified-harness]]
