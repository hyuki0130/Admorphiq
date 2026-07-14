# FT09 Level 3 click-count formula — self-contained brief for a fresh analyst

## 1. Background: the confirmed decode rule (already solved, already shipped)

FT09 is a click-toggle puzzle game (ARC-AGI-3). Its board is made of 8-cell
"rings" — a 3x3 layout of button-sized regions, minus the ring's own center
cell, which instead holds a small "glyph" (a compass-position pattern
drawn in exactly two non-marker "ink" colours, always measured as colour 0
and colour 2, plus a third "marker" colour at the glyph's own center
pixel).

**Confirmed, shipped decode rule** (validated exactly on levels 0-2, now in
production at `src/admorphiq/adapters25/ft09.py`):

- Read the glyph as a 3x3 compass grid: NW / N / NE / W / **C**(enter) / E /
  SW / S / SE.
- `C` (the glyph's own center pixel) is the ring's **marker colour**.
- Every OTHER compass position is painted either ink-colour **0** or
  ink-colour **2**.
- A compass position painted ink **0** must reach the glyph's own **marker**
  colour (the same colour as `C`).
- A compass position painted ink **2** must reach the ring's **OTHER**
  observed button colour (read from the ring's own button cells — this
  varies per board, e.g. {8,9} on one board, {9,12} on another).
- A ring cell needs a click **iff its CURRENT colour differs from its
  glyph-predicted target**. A ring that already matches its own glyph needs
  zero clicks.
- Clicking a cell advances it exactly one step; on simple 2-colour boards
  (levels 0-2) this is a single click reaching the target directly.

This alone solved levels 0, 1, and 2 exactly (byte-for-byte predicted vs
gold click sets on level 0; live smoke test clears 3/6 levels at
human-competitive-or-better efficiency — 4 vs 43 actions on level 1, 9 vs
12 on level 2, 15 vs 23 on level 3 in the game's own 1-indexed level
numbering, i.e. levels 0/1/2 in this brief's 0-indexed numbering).

## 2. What's DIFFERENT about level 3 (0-indexed) — the open problem

Level 3's board is **two-phase**: at level-start it shows a "decoy" board
(23 buttons, colours only 8/12, arranged rows{4,12,20,28,36,44,52} x
cols{12,20,28,36,44}) where EVERY discoverable ring already matches its own
glyph (zero mismatches by the decode rule above — nothing to click). The
level's FIRST click (gold click at row=14,col=20 in board coordinates,
i.e. the frame's `(row, col)` addressing used throughout this brief) causes
a **wholesale replacement**: every one of the 23 decoy buttons vanishes to
background, and a COMPLETELY DIFFERENT, previously-invisible 18-button grid
appears, using colour 9 (uniform) with the just-clicked cell already
flipped to colour 8. This "revealed" grid is the level's REAL puzzle. (This
same decoy->reveal pattern is also confirmed on level 1 — smaller scale,
2 revealed rings instead of level 3's setup below — and the shipped adapter
already handles PHASE detection generically: it re-discovers the ring/glyph
structure from the live frame on every action, so a wholesale board change
needs no special-casing.)

**This brief is about what happens ON THE REVEALED GRID** — specifically,
why some cells need 2 clicks, some need 1, and some need 0, in a way that
is NOT simply "click iff mismatched" (that simple rule predicts a "0 vs
nonzero" outcome, not "how many clicks", and level 3's own click-count
PATTERN doesn't reduce to any formula found so far — see Section 6).

## 3. The revealed grid's exact structure

Frame index `frames[106]` in `data/traces/ft09.npz` (the gold trace) is the
revealed grid immediately after the trigger click. 18 buttons on a 5x5
grid-with-7-gaps layout: rows `{14, 22, 30, 38, 46}` x cols
`{12, 20, 28, 36, 44}` (25 possible positions, 18 are buttons, 7 are gaps).

All 18 buttons start at colour **9**, except the ONE cell the trigger click
already touched (row14,col20 — the same cell the trigger click hit),
which shows colour **8**.

**Gap positions** (7 total): `(22,20)`, `(22,36)`, `(38,28)`, `(38,12)`,
`(38,44)`, `(46,12)`, `(46,44)`.

**Only 3 of the 7 gaps hold a glyph** (verified by direct pixel/region
inspection): `(22,20)`, `(22,36)`, `(38,28)`. The other 4 —
`(38,12)`, `(38,44)`, `(46,12)`, `(46,44)` — are confirmed **plain
background** (pixel value 4, the board's own background colour, no region
detected there at all). This was checked directly, not assumed — do not
assume a hidden glyph exists at any of these 4 positions unless new
evidence surfaces.

## 4. The 3 glyphs — full compass patterns

Each glyph is a 6x6 pixel block, read as a 3x3 grid of 2x2-pixel cells
(NW/N/NE/W/C/E/SW/S/SE). Values below are the raw colour at each compass
cell.

**Glyph @ (22, 20)** — center/marker colour = **12**
```
NW=2  N=0  NE=2
W=2   C=12 E=2
SW=2  S=0  SE=2
```

**Glyph @ (22, 36)** — center/marker colour = **9**
```
NW=2  N=0  NE=2
W=2   C=9  E=2
SW=2  S=2  SE=0
```

**Glyph @ (38, 28)** — center/marker colour = **12**
```
NW=0  N=2  NE=2
W=2   C=12 E=2
SW=0  S=0  SE=0
```

Each glyph's 8 compass positions map to real board cells via the STANDARD
ring geometry, pitch 8 in both directions (offset from the glyph's own
gap position): NW=(-8,-8), N=(-8,0), NE=(-8,+8), W=(0,-8), E=(0,+8),
SW=(+8,-8), S=(+8,0), SE=(+8,+8), all relative to the glyph's own `(row,
col)` gap position.

## 5. Ground-truth click counts (from the real gold trace, not inferred)

The level-3 gold sequence (rows 105-120 in the npz, 16 total actions,
starting with the trigger click at row105/106 both hitting the SAME cell)
produced these DISTINCT clicked cells and how many times each was clicked
(0 = never clicked; read directly from the click coordinate log, not
guessed):

| Cell (row,col) | Click count | Covering glyph(s) & that glyph's ink value there |
|---|---|---|
| (14,20) | **2** | (22,20).N = ink **0** |
| (14,28) | 1 | (22,20).NE = ink 2; ALSO (22,36).NW = ink 2 (shared) |
| (14,36) | 0 | (22,36).N = ink **0** |
| (14,44) | **1** | (22,36).NE = ink 2 (single-glyph coverage — no other glyph reaches this cell) |
| (14,12) | 0 | (22,20).NW = ink 2 (single-glyph coverage) |
| (22,12) | 0 | (22,20).W = ink 2 (single-glyph coverage) |
| (22,28) | 1 | (22,20).E = ink 2; ALSO (22,36).W = ink 2 (shared) |
| (22,44) | **1** | (22,36).E = ink 2 (single-glyph coverage) |
| (30,12) | 0 | (22,20).SW = ink 2 (single-glyph coverage) |
| (30,20) | **2** | (22,20).S = ink 0; ALSO (38,28).NW = ink 0 (shared) |
| (30,28) | 1 | (22,20).SE = ink 2; ALSO (38,28).N = ink 2 (shared) |
| (30,36) | 1 | (22,36).S = ink 2; ALSO (38,28).NE = ink 2 (shared) |
| (30,44) | 0 | (22,36).SE = ink **0** |
| (38,20) | 0 | (38,28).W = ink 2 (single-glyph coverage) |
| (38,36) | 0 | (38,28).E = ink 2 (single-glyph coverage) |
| (46,20) | **2** | (38,28).SW = ink **0** |
| (46,28) | **2** | (38,28).S = ink **0** |
| (46,36) | **2** | (38,28).SE = ink **0** |

Every button in the revealed grid appears exactly once in this table (18
rows = 18 buttons). No button was left unaccounted for.

## 6. What IS confirmed vs what is NOT (the actual open question)

**Confirmed, clean, no counterexamples found**: every ink-**0** compass
position, within a SINGLE glyph, shares the exact same click count as
every other ink-0 position of THAT SAME glyph:
- Glyph(22,20)'s ink-0 cells: N=2 clicks, S=2 clicks. Consistent.
- Glyph(22,36)'s ink-0 cells: N=0 clicks, SE=0 clicks. Consistent.
- Glyph(38,28)'s ink-0 cells: NW=2, SW=2, S=2, SE=2 clicks. Consistent.

**Two DISCONFIRMED hypotheses** (both individually falsified by direct
counterexample — do not re-propose these without addressing the
counterexample):

1. *"click count equals the glyph's raw colour value at that position"* —
   FALSE. Ink-2 cells get 0 OR 1 clicks (not a fixed value tied to "2"),
   and ink-0 cells get 0 OR 2 clicks depending on WHICH glyph (not a fixed
   value tied to "0").

2. *"click count equals the number of distinct glyphs whose 8-neighbourhood
   covers that cell"* — FALSE, directly falsified by (14,44) and (22,44):
   both are covered by EXACTLY ONE glyph (glyph(22,36) only — confirmed, no
   other glyph's neighbourhood reaches either cell, and no hidden glyph
   exists nearby — see Section 3's confirmed-background gaps), yet both got
   **1** click, not 0. Compare to (14,12), (22,12), (30,12), (38,20),
   (38,36) — ALSO single-glyph-coverage ink-2 cells — which got **0**
   clicks. Single coverage does NOT reliably predict 0.

**The actual unresolved question**: what distinguishes (14,44)/(22,44)
(single coverage, ink 2, click 1) from (14,12)/(22,12)/(30,12)/(38,20)/
(38,36) (single coverage, ink 2, click 0)? Both groups are genuinely
single-glyph-coverage cells (verified, no missing glyph explains the
difference — checked directly against the live frame, see Section 3). Some
other property distinguishes them. Candidate directions NOT yet tried:
- Position relative to the OVERALL grid's own bounding shape (e.g. corner
  vs edge vs "notch" of the irregular 18-button footprint — the grid is
  NOT a clean rectangle, it has genuine gaps/notches at specific spots).
- Distance (in grid steps) from the glyph's own center, or from the
  trigger-click cell (14,20).
- Whether the cell is on the CONVEX HULL / outer boundary of the button
  footprint vs an interior notch.
- Some property of the SPECIFIC glyph (glyph(22,36) is the one producing
  the anomaly; the other two glyphs' single-coverage ink-2 cells are ALL
  click-0, no exceptions there) — is glyph(22,36) itself special somehow
  (it's the only glyph whose center marker colour is 9, matching the
  BOARD's own base/unclicked colour, while the other two glyphs' markers
  are 12)?

That last point is worth flagging explicitly: glyph(22,36)'s marker colour
(9) equals the board's OWN base colour (every unclicked button starts at
9). The other two glyphs' marker colour is 12, which is NOT the base
colour. This asymmetry has not been explored as an explanation for why
glyph(22,36)'s single-coverage ink-2 cells behave differently.

## 7. Data source, if independent verification is needed

`data/traces/ft09.npz` — gold trace, schema at `data/traces/SCHEMA.md`.
Level 3 (0-indexed) gold block is rows 105-120 (`level_index[105:121] ==
3`, `is_gold[105:121]` all True, contiguous). `frames[105]` = decoy
pristine; `frames[106]` = revealed grid immediately after the trigger
click (row105's action; row106's action is a SECOND click on the SAME
cell, `(14,20)`, i.e. the trigger click and the first "real" click happen
to be the same physical button, clicked twice in a row).
