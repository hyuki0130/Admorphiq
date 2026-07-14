# FT09 Level 4 ("level 5" in 1-indexed smoke-table numbering) — win-condition mystery, self-contained brief for a fresh analyst

## 1. Background: the confirmed decode rule (already solved, already shipped)

FT09 is a click-toggle puzzle game (ARC-AGI-3). Its board is made of 8-cell
"rings" (a 3x3 layout of button-sized regions minus the center, which holds
a small "glyph": a 3x3 compass-position pattern NW/N/NE/W/**C**enter/E/SW/S/SE
drawn in ink colours, plus a marker colour at `C`). **Confirmed win-condition
rule** (validated exactly on 3 other levels, shipped in
`src/admorphiq/adapters25/ft09.py`): for every board cell, collect a
constraint from EVERY glyph whose 8-neighbour reach includes it: ink **0**
means the cell's colour must **equal** that glyph's marker; ink **2** means
it must **differ** from the marker; any other ink value (measured: **3**)
means no constraint. ALL covering constraints must hold simultaneously.
Clicking a cell always advances it one step along a MEASURED colour cycle
(cycle contents/order vary per board, discovered empirically, never
hardcoded).

**This level (0-indexed level 4) does NOT fit that rule as-is** — see
Section 5's decisive negative evidence. This brief documents everything
found; the open question is what ADDITIONAL mechanic makes gold's exact
21-click sequence clear the level when neither of two natural derivations
from the confirmed rule does.

## 2. Level setup

Level 4 (0-indexed) is also two-phase (decoy -> reveal), same pattern as
other levels: the pristine board (`frames[203]` in the gold trace,
`data/traces/ft09.npz`) shows 3 discoverable "rings" that already satisfy
their own constraints (nothing to click). Gold's FIRST action (row 203,
click at `x=14,y=12` i.e. board position `(row=12, col=14)`) wholesale-
replaces the visible region layout — after this click (`frames[204]`
onward), a completely different 27-cell field is visible and stays stable
for the rest of the level (36->114 non-background regions, confirmed
unchanging in count from `frames[204]` through the win).

## 3. The revealed board's structure

**27 field cells**, all colour **14** except gold's own already-clicked one
(colour **15**), on a 7x7 pitch-8 lattice: rows `{4,12,20,28,36,44,52}` x
cols `{6,14,22,30,38,46,54}` (49 possible positions, 27 are real buttons).
Exact list (row, col) of the 27 real field-cell bboxes' top-left corners:

```
(4,22) (4,30) (12,14) (12,30) (20,6) (20,14) (20,22) (20,30) (20,38)
(20,46) (20,54) (28,14) (28,30) (28,46) (36,6) (36,14) (36,30) (36,38)
(36,46) (36,54) (44,14) (44,30) (44,46) (52,14) (52,22) (52,30) (52,38)
```

The remaining 22 lattice positions are gaps. **9 of those 22 gaps hold a
legible glyph** (non-background center colour); the other 13 are plain
background. Of the 9 glyphs, there are TWO DISTINCT KINDS:

### 3a. Six "target" glyphs — same format as the confirmed rule (ink 0/2/3)

```
glyph@(28, 6)  marker=15  {NW:3, N:2, NE:0, W:3, SW:3, S:2, SE:0}
glyph@(36,22)  marker=14  {NW:0, N:2, NE:0, W:2, SW:0, S:3, SE:0}
glyph@(28,54)  marker=14  {NW:2, N:0, NE:3, W:0, SW:2, S:0, SE:3}
glyph@(28,38)  marker=14  {NW:2, N:0, NE:2, W:0, E:0, SW:2, S:0, SE:2}   (all 8 present)
glyph@(44,22)  marker=14  {NW:2, N:3, NE:2, W:0, SW:2, S:0, SE:2}
glyph@(12,38)  marker=15  {NW:0, N:3, NE:3, W:2, SW:0, S:2, SE:0}
```
(`C` omitted from each dict above since it equals the stated marker; `E`
column omitted when that position has no real field-cell button — same
"ink 3 there too, or simply not a lattice position with a button" pattern
as other levels' truncated rings.)

These 6 glyphs' constraints, applied to the 22 field cells they cover,
predict a WIN-STATE target set: **exactly 9 cells should end at colour 15,
all others at 14.** Verified exactly: every one of the 22 covered cells'
ACTUAL colour at the real gold win moment (`next_frames[223]`) satisfies
its full constraint set, zero exceptions. The 9 predicted cells:

```
(4,30) (20,14) (20,30) (20,46) (36,14) (36,30) (36,46) (52,14) (52,30)
```

The 5 field cells NOT covered by any of these 6 glyphs:
`(4,22) (12,14) (20,22) (44,46) (52,38)` — all end at colour 14 (base) at
the win moment.

### 3b. Three "commit" glyphs — a DIFFERENT, previously-unrecognised ink
pattern (6 and 14, not 0/2/3)

```
glyph@(12,22)  {NW:14, N:6, NE:14, W:6, C:14, E:6, SW:14, S:6, SE:14}
glyph@(28,22)  {NW:14, N:6, NE:14, W:6, C:14, E:6, SW:14, S:6, SE:14}
glyph@(44,38)  {NW:14, N:6, NE:14, W:6, C:14, E:6, SW:14, S:6, SE:14}
```

All three have the IDENTICAL pattern: corners (NW/NE/SW/SE) = ink 14
(same as C, the "don't care" reading), edges (N/W/E/S) = ink **6** (a
THIRD ink value never seen in any other level's glyphs). These are NOT
noise/false-positives — clicking directly ON one of these glyph GAP
positions (not a field cell — the glyph's own center point) produces a
real, structured effect on its 4 edge members. See Section 4's rows
221-223 for the measured behaviour. Each commit glyph's 4 edge (N/W/E/S)
targets, by offset from its own center:

```
glyph@(12,22): N=(4,22)  W=(12,14) E=(12,30) S=(20,22)   [all 4 real field cells]
glyph@(28,22): N=(20,22) W=(28,14) E=(28,30) S=(36,22)   [S has NO real field cell there]
glyph@(44,38): N=(36,38) W=(44,30) E=(44,46) S=(52,38)   [all 4 real field cells]
```

Note `(20,22)` is shared: it is glyph@(12,22)'s S member AND glyph@(28,22)'s
N member simultaneously.

## 4. Complete per-click table, all 21 gold actions (rows 203-223)

Row 203 (reveal click, `x=14,y=12`): huge noisy transition, expected
(the decoy->reveal transition itself).

Rows 204-220 (17 actions): each is a CLEAN single-cell 36px `14->15` flip,
landing on a DIFFERENT field cell every time, no side effects. Clicked
cells in order: `(36,30) (12,30) (4,22) (20,30) (36,38) (44,46) (44,30)
(52,38) (52,30) (36,46) (20,14) (4,30) (36,14) (52,14) (28,14) (30,28)
-- wait, verify exact list below` — the exact 17, in click order (row,col):

```
row204 (36,30)  row205 (12,30)  row206 (4,22)   row207 (20,30)
row208 (36,38)  row209 (44,46)  row210 (44,30)  row211 (52,38)
row212 (52,30)  row213 (36,46)  row214 (20,14)  row215 (4,30)
row216 (36,14)  row217 (52,14)  row218 (28,14)  row219 (28,30)
row220 (20,46)
```

Rows 221-223 (3 actions): each CLICKS DIRECTLY ON A COMMIT GLYPH's OWN GAP
POSITION (not a field cell), and each causes a mix of ADVANCES (14->15)
and REVERTS (15->14) among that glyph's own 4 edge members. Exact
per-cell effect (only the 27 field cells are shown; nothing else changes):

**Row 221** — click at `(row=12, col=22)` = glyph@(12,22)'s own center:
```
(4,22):  15->14   [glyph's N]
(12,14): 15->14   [glyph's W]
(12,30): 15->14   [glyph's E]
(20,22): 14->15   [glyph's S]  <- the only one ADVANCED, not reverted
```
Before this click, N/W/E were ALL already marked (15) and S was the ONLY
one NOT marked (14). After: only S remains marked; N/W/E were reset.

**Row 222** — click at `(row=44, col=38)` = glyph@(44,38)'s own center:
```
(36,38): 15->14   [glyph's N]
(44,30): 15->14   [glyph's W]
(44,46): 15->14   [glyph's E]
(52,38): 15->14   [glyph's S]
```
ALL 4 edge members were marked (15) before this click; ALL 4 got reverted
to 14. Nothing advanced (no edge member was unmarked beforehand).

**Row 223** — click at `(row=28, col=22)` = glyph@(28,22)'s own center
(**this is the WINNING click**, `levels_completed` reaches 5 right after):
```
(20,22): 15->14   [glyph's N -- shared with glyph@(12,22)'s S]
(28,14): 15->14   [glyph's W]
(28,30): 15->14   [glyph's E]
```
(glyph@(28,22) has no real S field cell, so only 3 edges are touched.)
ALL 3 were marked (15) before this click; all 3 got reverted to 14. The
level clears on THIS action despite it being a pure "revert" (nothing
advances) — the win check evidently fires on this specific click's
processing, not on reaching some particular colour pattern that persists
afterward (or the pattern IS what's needed and this reversion IS the
correct final state — see Section 5).

## 5. Decisive negative evidence (the two replays that should have worked but didn't)

Both tested via a LIVE deterministic offline arcengine replay (not
inferred): replay gold's exact levels 0-3 click sequence to reach level 4,
then a candidate level-4 click sequence, and check `levels_completed`.

**Replay A — click EXACTLY the 9 "target"-glyph-predicted cells** (Section
3a's list, one click each, any order tried was sequential list order):
`levels_completed` stays at 4. Does NOT clear.

**Replay B — click ALL 27 field cells once each** (every lattice button,
regardless of which glyph if any covers it): `levels_completed` stays at 4.
Does NOT clear.

Both replays leave the board in a state where the 6 target glyphs'
constraints ARE satisfied (Replay A trivially; Replay B needs checking —
NOT yet verified whether Replay B's end-state also satisfies the 6 target
glyphs, flagged as a gap in this brief, easy to check) — yet neither
triggers a win. **Gold's actual sequence needs the 3 commit-glyph clicks
(rows 221-223) IN ADDITION to marking the right field cells; the commit
clicks are not merely "confirmation" or "error-correction" of accidental
wrong guesses (a hypothesis this brief ORIGINALLY favoured before the
commit-glyph structure in Section 3b was found) — they hit exact,
structured glyph positions with an identical, repeated 4-edge pattern, and
each such click's own before/after state on its 4 edges is precisely what
Section 4 shows.**

## 6. Open questions for a fresh pass

1. **What triggers the win exactly?** Row 223's click reverts 3 cells to
   14 and the level clears immediately after. Is the win check evaluated
   incrementally as a byproduct of EVERY commit-glyph click (checking
   "are all 3 commit glyphs currently satisfying some condition", e.g.
   "each has AT MOST one of its edges marked"), independent of the 6
   target glyphs entirely? Or does clicking commit glyphs serve to
   "confirm" the target-glyph state and the ACTUAL win condition is
   "all 6 target glyphs satisfied AND all 3 commit glyphs satisfy some
   invariant simultaneously"?

2. **What's the commit glyphs' own win invariant?** Candidate readings,
   untested: (a) "at most one of each commit glyph's 4 edges may be
   marked (15) at any time" (would explain row222's all-revert: 4 marked
   violates "at most one", so all get cleared to restore the invariant);
   (b) "exactly one" (would explain row221's outcome differently: 3
   marked + 1 unmarked also violates "exactly one", not obviously fixed
   by "clear the marked ones and set the unmarked one" unless the rule
   is specifically "if not exactly one, normalize to zero, UNLESS
   exactly one is already correctly unmarked in which case set it" --
   convoluted, likely wrong, needs a cleaner hypothesis); (c) something
   about PARITY of total clicks across the commit glyph's own edges. This
   is the crux of the mystery and not resolved in this brief.

3. **RESOLVED: no overlap.** Checked exhaustively -- the 3 commit glyphs'
   10 distinct edge-member cells (`(4,22) (12,14) (12,30) (20,22) (28,14)
   (28,30) (36,38) (44,30) (44,46) (52,38)`) and the 6 target glyphs' 9
   predicted cells (Section 3a) are COMPLETELY DISJOINT sets -- zero
   shared cells. So the commit mechanic operates on an entirely SEPARATE
   subset of the 27-cell field from the target mechanic; they are two
   independent sub-puzzles sharing the same visual field, not two views
   of the same cells. (Between them: 9 target cells + 10 commit-edge
   cells = 19 of the 27 field cells accounted for; 8 field cells belong
   to neither mechanic as currently understood -- also worth checking
   what those 8 are and whether they matter at all.)

4. **Order/count**: gold clicked commit glyphs 3 times total (once each,
   in the specific order 12,22 -> 44,38 -> 28,22) after ALL 17 target
   clicks were done. Is this order load-bearing, or could the 3 commit
   clicks happen at any point (even interleaved with the 17 target
   clicks)? Untested.

5. Given the confirmed rule elsewhere is "collect ALL covering glyphs'
   constraints, require simultaneous satisfaction" -- is there a UNIFIED
   reading where ink **6** means something precise in the SAME
   equality/inequality vocabulary (e.g. ink 6 might encode a
   position-COUNTING constraint across the group of 4, not a per-cell
   colour constraint) that a fresh derivation from the per-click table
   above might reveal, the same way ink 0 vs 2's "equal/not-equal marker"
   meaning was derived by inspection in the original (level 0-3) work?

## 7. Data source

`data/traces/ft09.npz`, schema at `data/traces/SCHEMA.md`. Level 4
(0-indexed) gold block is rows 203-223 (`level_index[203:224] == 4`,
`is_gold[203:224]` all True, contiguous, confirmed no gap at either
boundary). `frames[203]` = decoy pristine; `frames[204]` = revealed board
immediately after the reveal click; `next_frames[223]` = the true win
moment (post-click state right when `levels_completed` becomes 5).
May read the (obfuscated) environment source
(`environment_files/ft09/0d8bbf25/ft09.py`) for VERIFICATION only, after
deriving a candidate rule from the data above — this is how the earlier
level-3 click-count formula was both discovered AND confirmed.
