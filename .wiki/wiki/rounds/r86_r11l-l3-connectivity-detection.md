---
round: R86
axis: depth / colour-blind creature detection (attempted) — banked on target assignment
keywords: r11l, l3, connectivity, colour-blind, detection, target-assignment, multi-colour, shared-colour, banked, dirwzt
verdict: connectivity LEG-grouping SOLVED (de-risked); TARGET-ring assignment ambiguous under colour-sharing → multi-session wall; NO code change, floor 3/6 untouched
commit: (this docs round)
---

# R86 — r11l L3 colour-blind detection: leg-grouping solved, target assignment is the wall

> r11l L3 decode round: colour-blind LEG-grouping solved and de-risked;
> target-ring assignment stays ambiguous under colour sharing -> banked as
> a multi-session wall, no code change, floor 3/6 untouched.

Granted as the L3 build follow-on to [[r85_r11l-strike-aware-assembly]] (r11l 3/6
@ 0.2551). Goal: get `_analyze_creatures` to detect L3's 3 creatures (it returns
None — bodies are multi-colour with shared colours, [[../games/R11L]] Notes R85b)
so the proven strike-aware planner can clear L3. **Prototyped the colour-blind
detection; leg-grouping WORKS, but target-ring assignment does not converge — a
genuine multi-session wall. Banked with no code change (floor 3/6 stays safe).**

## What was prototyped (colour-blind connectivity, gated as a fallback)

On the L3 settled frame, split pieces by fill band (bodies ≥ `_BODY_FILL`, legs
`[_MIN_LEG_FILL, _BODY_FILL)`, targets < `_MIN_LEG_FILL`), then:

- **Bodies**: cluster high-fill pieces by spatial proximity (chebyshev ≤ 6),
  colour-blind → **exactly 3 body clusters** (sizes 3+2+2 pieces), each with a
  colour SET.
- **Legs**: assign each mid-fill leg piece to the nearest body cluster →
  **PERFECT grouping**, engine-verified: body{12,14,15}→2 legs, body{8,9}→2 legs,
  body{11,14}→3 legs, matching the 3 engine creatures exactly. The hard part
  (which the colour-based detector fails) is SOLVED.

## Why it BANKS — target-ring assignment is ambiguous

Each creature's target ring shares its body's colours, so the plan was to match
body→target by colour-set overlap. It does not resolve:

- 16 low-fill pieces form **9 clusters for 3 real targets** (decoy connectors /
  ring fragments). The 3 real target clusters ARE present ((12,50), (52,19),
  (51,36)) but drowned among decoys.
- **Colours are shared/split across creatures** (14 in two bodies; orrqlj's real
  target (51,36) survives clustering as only {15}), so even OPTIMAL one-to-one
  assignment maximizing total colour overlap has **4 equally-optimal solutions**
  for orrqlj's target — only one correct, and no clean tie-break (distance points
  the wrong way; the correct target (49,36) is FAR from orrqlj's body).
- L3 wins only when ALL 3 bodies are on target simultaneously, so a single
  mis-assigned target ⇒ 0 on L3 regardless. Shipping an unreliable matcher would
  add code + risk (a fallback firing on an L1/L2 transient frame could regress the
  sacred 3/6 floor) for no gain.

## Verdict + reopen

**Multi-session detection round, NOT bounded — and the colour-SET ring-matching
spec is itself STRUCTURALLY ambiguous (proven), so it cannot be the fix.** Exact
numbers: bodies `yeogy{11,14}`, `blxuub{8,9}`, `orrqlj{12,14,15}`; real targets
`T(12,50){11,14}`, `T(52,19){1,8,9}`, `T(51,36){15}`. `yeogy` and `blxuub` match
uniquely (overlap 2). But `orrqlj`'s body carries TWO colours (12 and 15) that are
each unique to it yet appear in DIFFERENT low-fill clusters — its real target
`(51,36){15}` and a decoy `(17,12){10,12}` each match by a unique orrqlj colour
(overlap 1). Global one-to-one assignment maximizing total overlap therefore has
≥4 equally-optimal solutions (all total 5), only one correct. Ring-GEOMETRY
filtering does NOT rescue it either: the 3 real rings (pix 6/12/18) are not
size/shape-separable from the decoys (pix 12-25). **No colour/geometry signal in
the frame uniquely identifies orrqlj's target.**

Leg-grouping is de-risked and reusable; target identification is the genuine wall.
Two reopen options, both a DEDICATED round (a decision, not a bounded pass):
- (a) **Speculative-target-trial** (the one viable path): place the 2 unambiguous
  creatures, then drive `orrqlj`'s body to each candidate target IN TURN until the
  engine's win fires (all 3 bodies on target). Cost ≈ 30-45 actions vs the 60
  budget — feasible but tight and budget-risky; a real runtime-strategy build.
- (b) **Richer perception** — a signal beyond colour/geometry to pin each target
  to its creature (none found in the frame so far).

Once target assignment is robust, the proven strike-aware planner clears L3
(3+2+2 ≈ 14 actions, verified in R85b) and likely L4/L5.

Related: [[r85_r11l-strike-aware-assembly]] · [[../games/R11L]] Notes R85b.
