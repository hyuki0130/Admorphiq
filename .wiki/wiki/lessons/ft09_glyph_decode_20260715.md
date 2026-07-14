---
type: lesson
date: 2026-07-15
rounds: R56
status: gold-trace verified; live-env smoke not yet run
---

# FT09 is a glyph-decode puzzle, not a coupled GF(2) neighbourhood stencil (R56)

> Gold-trace reverse-engineering falsifies the R16-R18 "clicking couples
> neighbour cells" model: a click only ever changes the clicked cell. The
> real win condition is drawn on the board as a 3x3 compass glyph, and the
> R56 `src/admorphiq/adapters25/ft09.py` adapter decodes it directly
> instead of measuring a stencil.

## Symptom

`_plan_lights_out` (the R16-R18 GF(2) path, see
[[gf2_lights_out_stencil_20260423]]) clears FT09 L1 but stalls on L2+:
the diff-sorted top-10 cells measure as 91-100% stencil density, which
that lesson page reads as "coupled display feedback, not real toggle
buttons" — eleven different guessed target hypotheses (majority colour,
minority colour, per-cell flip, ...) all missed the actual win condition.
R53's own conclusion ("the one open road is richer goal evidence") named
exactly this failure mode: the agent could measure structure but had no
way to know WHAT KIND of predicate the goal actually was.

## Root Cause

The R16-R18 model assumed FT09 is a coupled linear system: click cell `j`,
some SET of cells (possibly including `j`) flips, and the empirical
stencil `A[i][j]` needs to be measured and solved over GF(2). Gold-trace
decode (byte-for-byte replay against a cleared level) falsifies this: a
click only ever changes the CLICKED cell — there is no coupling to
measure, so every one of the eleven target hypotheses was searching the
wrong problem class from the start regardless of how good the target
guess was.

The actual mechanic: the board is one or more 8-cell "rings" (a 3x3
button layout minus its own center) wrapped around a 6x6 "glyph" that
occupies the ring's center gap. The glyph is itself a 3x3 compass-position
pattern (NW/N/NE/W/center/E/SW/S/SE), painted in exactly two non-marker
ink colours (measured: always 0 and 2) plus the ring's own marker colour
at the glyph's own center cell. Ink colour 0 at a compass position means
"that ring cell must show the glyph's own center (marker) colour"; ink
colour 2 means "that ring cell must show the ring's OTHER observed button
colour" (read from the ring's own cells every time — the two-colour
alphabet varies between boards, e.g. `{8,9}` vs `{8,9,12}`). A ring cell
needs a click iff its current colour differs from its glyph-predicted
target. This generalizes across boards with multiple independent rings
(verified: a 4-ring board where 3 rings are already glyph-matched and
only the mismatched 4th needs exactly the gold trace's clicks).

A second falsified assumption: some levels' board at level-start is a
"decoy" where every discoverable ring already matches its own glyph
(nothing for the decode rule to click) until ONE click anywhere
wholesale-replaces the visible region layout with a different,
previously-invisible ring set — the level's real puzzle. The reveal click
doubles as that new board's first real toggle.

## Prevention

The new adapter (`src/admorphiq/adapters25/ft09.py`) treats "discovery
found zero mismatches" as a signal to make a probing trigger click, not a
giveup, and — critically — RE-RUNS ring discovery from the live frame on
every single `choose_action` call rather than trusting a cached board
reading. That single design choice is what makes the decoy->reveal
transition fall out for free: there is no stale candidate list to
invalidate, because nothing is ever cached across calls in the first
place. Ring/pitch/glyph geometry is discovered purely from frame
observation (modal button size, MODE — not min — of measured button-gap
distances, `tile_bbox` 3x3 split of the discovered glyph bbox), so no
fixed pixel offset is hardcoded anywhere the way the old sprite-tag
solver was.

## Recovery

A per-cell click cap (`_GLYPH_PER_CELL_CLICK_CAP = 4`) plus a small
total-contradiction budget (`_GLYPH_CONTRADICTION_CAP = 2`) fall back to
the pre-existing measured-GF(2)-stencil probe/execute/fallback machinery
unchanged, if the glyph decode turns out not to apply to some board this
adapter hasn't seen. The R16-R18 stencil path is not deleted — it is now
FT09's second-line strategy rather than its only one, exactly the "no
plan fits, propose a code fix" self-healing shape the architecture doc
calls for, except decided at dev-time by gold-trace evidence instead of a
runtime LLM proposal.

## Falsification

This reading is falsified if: (a) a real board is found where a click
changes ANY cell other than the one clicked (breaks the "clicks don't
couple" claim); (b) a glyph ink colour other than `{0, 2}` is observed
(breaks the two-ink-colour assumption — would need a third target rule);
(c) a ring is found whose 8 compass neighbours are not all button-sized
regions (breaks the fixed 8-cell ring shape assumption); or (d) a decoy
board is found where the reveal trigger is NOT simply "any click on the
decoy" (would need a more specific trigger-detection rule than "found
zero mismatches").

## Open item

Gold-trace decode was verified byte-for-byte offline (replay against
captured L0/L1 frames, see the adapter's own module docstring). The
live-env smoke run (actual `choose_action` loop against the real API,
the way [[../rounds/r56_generic-kernels]]'s m0r0 PoC adapter was
smoke-tested) has not been run yet — that is the next falsification step
before this lesson's status can move from "gold-trace verified" to
"measured".

## Related

- [[gf2_lights_out_stencil_20260423]] — the R16-R18 stencil model this
  lesson falsifies; kept as FT09's fallback strategy, not deleted.
- [[../concepts/gf2_toggle_stencil]] — the coupled-toggle concept the
  glyph-decode reading no longer applies to for FT09 specifically (the
  concept page still applies to any game that genuinely IS a coupled
  toggle system).
- [[../games/FT09]] — the game's own entity page, updated alongside this
  lesson.
- [[../rounds/r56_generic-kernels]] — the round this decode work landed
  under (kernel composition: `find_regions`, `tile_bbox`).
- [[../rounds/r57_win-condition-typology]] — the gold-trace win-moment
  mining method this decode reused (per-level-up frame diffing against
  `data/traces/*.npz`).
