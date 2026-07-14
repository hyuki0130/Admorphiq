# TR87 frame-only rewrite-grammar adapter: scoping + prototype (2026-07-15)

**Status: design + prototype done; adapter build GATE REOPENED (§8) —
scoping may resume, but is not itself done yet.** This scopes whether the
R56 kernels (`derive_rewrites`/`find_derivation`/`greedy_parse`, `shapes`,
`regions`, `parse`) can crack the tr87 wall (0/6 for the LLM-free card) once
combined with a game-specific adapter. **Verdict history**: §7 measured the
level-0-only segmentation approach as FALSIFIED on level 1 (raw
`occupied_runs` merges multi-token rule sides into one run) — the
rotation-confound and 7-state-dial-cycle measurements (§2) were never in
question. **§8 (this update) tested a pitch-multiple recovery splitter
against level 1 AND level 2 (the harder case — multi-token on BOTH LHS and
RHS) and it recovered all 24 oracle-cross-validated token counts exactly,
zero misses.** Per Codex's original review
(`docs/r56_codex_tr87_review_20260715.md`), a splitter surviving 2+
representative levels reopens the gate — see §8 for the full measurement,
and "Recommendation" for what's still needed before an adapter build
starts (the splitter is a throwaway probe function, not yet a promoted
kernel or an adapter).

> **Claims audit (2026-07-15, Codex interim review)**: two claims in the
> first version of this doc were overclaims; both are corrected below and
> the audit trail is kept at the end of §2 and in the "Sources read" bullet
> for `tr87.py`, per wiki doctrine (record the journey, not just the fixed
> state). Short version: (1) the "7-state cyclic dial" claim originally
> rested on seeing 7 distinct states with the sample data running out
> before observing an actual return-to-start — closure is now DIRECTLY
> measured (see §2); (2) `alter_rules` was mischaracterized as one of
> "three per-level output-translation modes" alongside `tree_translation`/
> `double_translation` — it is a structurally different flag (it changes
> WHICH row the player edits, not how the win-check re-expands a matched
> rule) and the three flags are independent booleans a level can combine,
> not a 3-way choice. **A third correction, found while capturing level 1
> (§7)**: `.wiki/wiki/games/TR87.md`'s claim "`ACTION1` is the forward
> step" is WRONG — `tr87.py:1006` (`pxdsteijos = -1 if self.action.id ==
> GameAction.ACTION1 else 1`) shows `ACTION1` is the BACKWARD (-1) dial
> step and `ACTION2` is forward (+1); flagged here, wiki page not yet
> corrected (out of this doc's scope, but noted so it isn't silently
> carried forward — this doc's own probe was direction-agnostic and
> unaffected, but a live executor would press the wrong button on every
> "step forward" if it trusted the wiki page as written).

## Sources read

- `.wiki/wiki/lessons/tr87_dial_match_hypothesis_falsified_20260713.md` —
  6 visual-match hypotheses for the win rule, all falsified.
- `.wiki/wiki/rounds/r53_unified-harness.md`, "TR87 win-rule CRACKED"
  section (2026-07-14) — the win rule is a **production/rewrite grammar**:
  `tr87.py`'s `cifzvbcuwqe` is a list of `(LHS, RHS)` rules built from
  visible `nxkictbbvzt`-tagged glyph sprites either side of an invisible
  `iqrduxrukrk` marker; `bsqsshqpox()` requires bar2 to be a valid
  derivation of bar1 under those rules. Banked as "frame-feasible but
  feature-scale," not built.
- `.wiki/wiki/games/TR87.md` — frame-visible structure: bar1 (static
  target, top) / bar2 (editable, bottom), 5 columns each, `ACTION1`/`2`
  step a 7-state cyclic dial on the bracketed bar2 column, `ACTION3`/`4`
  move the bracket, `avail=[1,2,3,4]` (no `ACTION6`).
- `environment_files/tr87/cd924810/tr87.py` (**verification-only read**,
  per this repo's established precedent — never touched by any shipped
  solver) — read to understand the rule/marker/glyph data model precisely
  enough to design the extraction, and to cross-check measurements below
  against a second source. Confirmed: glyph identity = sprite name
  `nxkictbbvzt{LETTER}{DIGIT 1-7}` (`LETTER` = shape family, `DIGIT` =
  1-of-7 cyclic state); **every `nxkictbbvzt`-tagged sprite gets an
  independently random `set_rotation(choice([0,90,180,270]))` at level
  load**, preserved across dial-cycling (`wpbnovjwkv` clones the new
  state's sprite `.set_rotation(old.rotation)`); win-check `bsqsshqpox()`
  is a **deterministic greedy left-to-right parse** of bar1 (first
  rule in list order whose LHS matches at the current position wins, no
  backtracking).

  **Correction (Codex review): the 3 per-level flags are independent
  booleans, not a 3-way mode choice, and `alter_rules` is not a peer of
  the other two.** Re-read of `on_set_level`/`step()` (both
  verification-only): `tree_translation` and `double_translation` genuinely
  ARE about the win-check's derivation logic — both re-expand a matched
  rule's RHS through a second lookup before comparing against bar2
  (`tree_translation`: each RHS glyph is looked up as ANOTHER rule's
  `LHS[0]` and replaced by that rule's own RHS; `double_translation`: a
  hidden `tjaqvwdgkxe`-tagged sprite indirection resolves both sides
  through a second rule). `alter_rules` is a different KIND of flag
  entirely: it decides, at level load, WHICH row gets the per-glyph random
  dial-offset (bar2, when `alter_rules` is absent/False — the case this
  session captured — or every glyph in the rule table itself, `self.
  cifzvbcuwqe`, when `alter_rules` is True), and it ALSO redirects what
  `ACTION1`-`ACTION4` edit at runtime: bar2 (the `else` branch) normally,
  but **the flattened rule-table glyph list itself**
  (`[set for rule in self.cifzvbcuwqe for set in rule]`) when
  `alter_rules` is True — bar2 is left untouched by the player in that
  mode. The win-check (`bsqsshqpox`) always compares `self.zvojhrjxxm`
  (bar1) against `self.ztgmtnnufb` (bar2) regardless of `alter_rules`, so
  when `alter_rules` is True the puzzle becomes "edit the RULE TABLE until
  the ALREADY-FIXED bar1/bar2 pair happens to satisfy the derivation" — a
  materially different task shape than "edit bar2 to derive from a fixed
  rule table," which is what the rest of this document (and everything
  measured in §2/§3/§4) assumes. The flags also are NOT mutually exclusive
  — reading every level's own `data={...}` (or its absence) directly:

  | Level (index) | `alter_rules` | `tree_translation` | `double_translation` |
  |---|---|---|---|
  | 1 (0) — **captured, this doc's data** | — | — | — |
  | 2 (1) | — | — | — |
  | 3 (2) | — | — | — |
  | 4 (3) | — | — | ✓ |
  | 5 (4) | ✓ | — | — |
  | 6 (5) | ✓ | ✓ | ✓ |

  So the only captured level (index 0 / "Level 1") is the SIMPLEST case —
  no flags at all, matching everything this document measures and designs
  around — but three of the six levels have zero flags (not one "simple
  mode" among several peers), one level is `double_translation`-only, one
  is `alter_rules`-only (the edit-the-rule-table variant), and only the
  LAST level combines all three. None of levels 4-6 have captured frames
  (see §1), so the `alter_rules`/`tree_translation`/`double_translation`
  variants remain unmeasured and undesigned beyond this table.

  **One more precision the table above doesn't show**: `bsqsshqpox()` tests
  `tree_translation` with `if` and `double_translation` with `elif`
  (`tr87.py`, inside the rule-match loop) — so on level 6 (the only level
  with BOTH flags True), `tree_translation`'s branch always wins and
  `double_translation`'s branch is DEAD CODE for every level this game
  actually ships. A future adapter targeting level 6 only needs to handle
  `tree_translation`'s re-expansion, never a combined
  `tree_translation`+`double_translation` interaction — there isn't one.
- `src/admorphiq/kernels/` (`rewrite.py`, `regions.py`, `shapes.py`,
  `geometry.py`, `parse.py`) — the available building blocks.

## 1. What captured data exists

Located via repo-wide search (`find . -iname "*tr87*"`):

| File | Content | Useful for |
|---|---|---|
| `.wiki/raw/traces/tr87.jsonl` | 1 line, summary stats only (no frames) | provenance, not extraction |
| `data/traces/tr87.npz` | 1200 rows: `frames`/`next_frames` (64×64 uint8), `actions` (1-indexed `{1,2,3,4}`), `level_index` (all 0), `is_gold` (all False) | glyph/layout extraction (see below: it's 1200 **independent single-step samples from one fixed reset**, not a trajectory) |
| `data/transitions/train/tr87.npz` | 2000 rows: `frames`/`next_frames` (int16), `actions` (0-indexed `{0,1,2,3}`) | **multi-step chaining** (see below: 1927/1928 before-frames connect into another sample's after-frame — a connected transition graph, not one trace, but walkable) |
| `scripts/rounds/*/games/*tr87*.json`, `scripts/test_tr87_*.py` | prior LLM-benchmark results / earlier hand probes | historical context only |

Both `.npz` files are **level 0 only** (no captures exist for levels 1-5;
see the "Sources read" correction above for exactly which of the 3
independent flags — `alter_rules`, `tree_translation`, `double_translation`
— each of those uncaptured levels sets). This scoping and prototype is
therefore level-0-only (the one level with none of the 3 flags set); the
flagged levels are discussed on paper (from the verification-only read)
but not measured.

## 2. Confirmed structural findings (measured, not assumed)

All measurements reproducible via `scripts/_tr87_probe.py` (throwaway,
not committed to the module tree, uses only the two `.npz` files above,
zero live env calls).

**Layout** (level 0, this game hash): bar1 interior rows 41-45 (fill
colour 10), bar2 interior rows 52-56 (fill colour 7), bracket rows
48-49/59-60 (colour 0), upper rule-table row-bands at rows 4-10/13-19/
22-28. Each bar has exactly 5 glyph columns, each 7px wide with a 2px true
gap, at columns `[(15,19),(22,26),(29,33),(36,40),(43,47)]`.

**Ink colour is constant (5) across every glyph family observed; fill
colour varies by family** — measured: one row-band mixes glyphs with
fill=10 and fill=7 side by side (a naive single global "background colour"
assumption under-splits or over-splits blocks; had to be measured, see
Kernel Gaps §1).

**The rule table has a clean, frame-visible LHS|RHS split via gap width,
with no need to detect the invisible marker at all** — measured: each
row-band segments into exactly 4 glyph windows separated by gaps of
3px, 6px, 3px. The 3px gaps sit *inside* one rule (LHS|RHS split, where
the marker's own 11px footprint mostly overlaps the LHS glyph and pokes
4px into the gap); the 6px gap is the boundary *between* two different
rules. **Gap width itself is the frame-visible structural signal for
"which glyphs belong to the same rule"** — this was not obvious from the
wiki write-up (which treated the marker as necessary for parsing) and is
the single most useful design finding here.

**The rotation confound is real and load-bearing — not just a theoretical
risk from reading the source.** Comparing bar1's 5 target glyphs against
the 12 upper-grid rule-table glyphs:

| Matching method | bar1↔upper-grid matches |
|---|---|
| Translation-only (crop + exact cell equality) | **1 / 5** |
| Rotation-invariant (min over the 8 `dihedral_transforms`) | **5 / 5** |

Naive shape hashing (e.g. `kernels.regions.multiset_signature`, which is
translation-invariant only) would recognize only 1 of bar1's 5 targets as
"a glyph that also appears in the rule table" — the other 4 are the exact
same shape rendered at a different on-screen rotation. **Rotation-invariant
matching via `kernels.shapes.dihedral_transforms` + `crop_to_content` is
not optional for this game; it is required**, and it works — 5/5 once
applied. (bar2's 5 columns against the same rule table: 1/5 translation-only
vs 4/5 rotation-invariant — the missing 1 is expected, bar2's random
initial dial offset need not land on a state the rule table happens to
reference.)

**The dial is confirmed to CLOSE a 7-state cycle — not merely to show 7
distinct states.** The first pass at this measurement (see "Claims audit"
below) chained EXACT frame bytes from one fixed start and stopped at 7
distinct states purely because the sample data ran out, never observing an
actual return to the start — that is evidence of "at least 7 states," not
of a closed 7-cycle. The corrected measurement instead builds an
ABSTRACTED graph over `(column, rotation-invariant signature, action)` —
merging any two raw samples that agree on one column's own dial-state even
if they differ elsewhere on the board (different bracket position on
another sample, etc.) — from all 949 dial-step samples in `data/
transitions/train/tr87.npz` (of 2000 total; the rest are bracket-move
samples), after verifying, PER SAMPLE, that the bracket didn't move (0 of
949 did). Walking `action=1` from a fixed start state on this graph:

- All 5 columns: **exactly 7 distinct canonical states**, and the walk
  **CLOSES — returns to the exact start state — after exactly 7 hops**,
  for every column. This is genuine closure, directly observed in the
  data (not inferred from a state count or a modular-arithmetic reading of
  the source).
- The reverse action (`action=0`) is confirmed, hop-by-hop, to be the
  EXACT inverse of every forward hop on the closed cycle: **7/7 hops
  confirmed for every column** (`edges[(col, s_{i+1}, 0)] == s_i` checked
  directly against the graph, not assumed from the source's `ACTION1=+1/
  ACTION2=-1` documentation).
- A further, unplanned finding: **all 5 columns share the exact identical
  SET of 7 canonical signatures** (not just the same count) — consistent
  with the 7 shapes being one shared "digit" pattern library reused across
  glyph LETTER-families (which differ only in fill colour, not ink
  pattern; see the ink-colour finding above), though this session did not
  chase that hypothesis further.

**Conflict-checked, not silently merged.** The fuller Codex review (`docs/
r56_codex_tr87_review_20260715.md`) additionally found that the FIRST
version of this probe's graph builder used a plain dict assignment that
silently overwrites a duplicate `(frame, action)` key on conflict — and
found 4 such conflicting pairs in that exact-byte version. The corrected
probe collects every `(column, signature, action)` observation into a SET
first and explicitly reports how many keys have more than one distinct
outcome (i.e. are genuinely nondeterministic in the sampled data) before
building the graph used for the walk above: **0 of 70 edges conflict** —
every one of the 949 dial-step samples used agrees with every other sample
sharing its `(column, signature, action)` key. This is a materially
different (and stronger) result than the old exact-byte version's 4
conflicts, most plausibly because THIS abstraction discards exactly the
kind of irrelevant elsewhere-on-the-board pixel variation (a different
sample's bracket-adjacent rendering, unrelated dial state elsewhere) that
made two "different" exact frames collide under the coarser
`(column, signature)` key while genuinely agreeing on the one dial's own
transition.

Reproducible via `scripts/_tr87_probe.py`'s "section 3" (the script now
performs this abstracted-graph closure test, with the conflict check, in
place of the original exact-byte chain).

## 3. Design: pipeline as kernel compositions

```
frame → [ADAPTER: locate bar1/bar2/upper-grid row-bands]
      → gap_windows() [NEW, not a kernel yet — see gap §1] → per-glyph windows
      → ink_mask() [NEW] → boolean mask per glyph
      → kernels.shapes.crop_to_content + dihedral_transforms → canonical token id
      → [ADAPTER: cluster upper-grid windows into (LHS, RHS) rule pairs by gap width]
      → rules: list[(LHS_tokens, RHS_tokens)]
      → bar1_tokens = [canonical token per bar1 glyph]
      → bar2_target_tokens = [ADAPTER: greedy left-to-right parse of bar1_tokens
                               against rules, per bsqsshqpox()'s exact semantics —
                               see §4, NOT kernels.rewrite's BFS search for the
                               simple mode]
      → [ADAPTER: map each bar2 column's CURRENT token → target token via the
                   7-state dial cycle (BFS/graph, or just count cyclic distance)]
      → action plan: per column, N×(ACTION1 or ACTION2) + ACTION3/4 to navigate
```

**Roles the adapter must decide** (per the R56 "declared-intent" doctrine
— kernels compute, the adapter/LLM supplies semantics):
- Which row-bands are bar1/bar2/upper-grid (a discovery-phase decision;
  the row-band *shape* — bar1/bar2 continuous single-colour fill vs.
  upper-grid's background-bounded blocks — is a detectable signature, but
  the ROLE "this is the target row" is still a semantic call).
- The ink colour and per-band fill colour (measured constant=5 for ink on
  this level; general adapter should derive it, e.g. minority colour
  within a window, not hardcode 5).
- The gap-width threshold separating "same rule" from "different rule"
  (measured 3px vs 6px here; a general adapter should cluster observed gap
  widths into two groups, e.g. via a simple two-way split of the sorted
  gap-width list, rather than a fixed pixel threshold).
- Token alphabet size / equality: use rotation-invariant canonical
  signatures as token identity (kernels.shapes), NOT raw pixel equality.

**What kernels compute** (once roles are supplied): `dihedral_transforms`
+ `crop_to_content` (canonical token id, existing, used as-is);
`kernels.regions.find_regions`/`group_by_axis` are **not the right tool
for glyph segmentation** here (see Kernel Gap §1) but remain useful for
other structural sub-problems (e.g. clustering the 12 upper-grid windows
into rule-pairs by centroid position is exactly `group_by_axis`'s job,
once windows are found); `kernels.rewrite.find_derivation` is a candidate
*fallback* engine (§4) but is not what the primary no-flags-level parse
needs.

## 4. `derive_rewrites`/`find_derivation` is NOT the primary engine for the simple mode — a genuine, useful finding

`bsqsshqpox()`'s actual algorithm (verification-only read) is **not** a
general grammar-derivation search: it's a single deterministic
left-to-right greedy parse — at each position in bar1, try each rule *in
list order*, take the *first* whose LHS matches, advance, no
backtracking, fail if nothing matches. This is strictly simpler than what
`kernels.rewrite.derive_rewrites`/`find_derivation` provide (those do a
branching BFS over *all* rule/position choices, because they're designed
for the general case where multiple derivations may exist and the
target must be searched for).

**Implication**: the adapter for the no-flags levels (1-3; this session's
captured data is level 1/index 0) needs a new, simpler primitive — "greedy
tokenize `bar1_tokens` by the rule LHS list in order, concatenate the
matched RHS's" — not a BFS search. This is now built:
`kernels.parse.greedy_parse` (landed in the follow-up round after this
doc, see `src/admorphiq/kernels/parse.py`). `find_derivation` remains
useful as a **defensive fallback**: if the greedy parse fails to cover all
of bar1 (a real possibility if an adapter's rule extraction mis-orders or
mis-splits a rule), a bounded `find_derivation`-style search over the
*same* rule set could recover a valid tiling the naive greedy parse
missed, or explicitly report "genuinely unparseable — extraction bug"
rather than silently producing a wrong plan. The `tree_translation` and
`double_translation` flags (unmeasured — no captured data at the levels
that set them; see the corrected level/flag table in "Sources read") are
more clearly derivation-shaped (recursive RHS re-expansion via a second
rule lookup), and are closer to what `find_derivation` was built for — but
each is its own bespoke traversal per the source, not a single generic
search, so should be scoped as its own follow-up once frames for those
levels exist. `alter_rules` (also unmeasured) is NOT a derivation-shape
variant at all — see the "Sources read" correction — it changes which row
the player edits, so it needs its own adapter design (edit the rule table,
not bar2), not a `greedy_parse`/`find_derivation` variant.

## 5. Kernel gaps this exposes

> **Update (2 follow-up rounds, same day): gaps #1-#4 below are now CLOSED,
> under DIFFERENT names/locations than first landed (Codex primitive
> review).** Round 1 (`commit 1aab383`) landed `gap_windows`,
> `window_majority_color`, `cluster_widths`, `greedy_parse` all in a new
> `parse.py` — exactly the four primitives scoped below, but under names
> Codex's review (`docs/r56_codex_tr87_review_20260715.md`) pushed back on.
> Round 2 (uncommitted at time of writing) applied those rulings: `gap_windows`
> → **`occupied_runs(frame, axis="row"|"col", bbox=None, background=None)`**
> (axis-neutral, no "window"/token-implying naming, takes a bbox instead of
> requiring a pre-sliced band); `window_majority_color` → **removed**,
> replaced by a fully generic **`color_mode(values, k=2)`** histogram (no
> ink/minority semantics — the caller filters/selects values before
> calling, e.g. from `occupied_runs`' own `"cells"` output); `greedy_parse`
> → **moved into `kernels/rewrite.py`** (same behaviour, now living
> alongside `derive_rewrites`/`find_derivation` with an explicit "use BFS
> search diagnostically, never as an action-driving fallback" cross-warning
> in both directions); `cluster_widths` unchanged (Codex's own ruling: "this
> is exactly what you built," keep as-is). Left the numbered list below as
> originally written for the record of what was missing at scoping time;
> gap #5 (untested across levels/flags) remains open — and §7 below
> FALSIFIES the segmentation approach these gaps were meant to enable, on a
> second level.

1. **No kernel does "segment a row-band into glyph windows by background
   gap."** `kernels.regions.find_regions` segments by *same-colour*
   connected components — wrong tool here because a TR87 glyph is a
   *two-colour* (fill+ink) block, so single-colour flood fill fragments
   one glyph into several small ink-only components (measured: naive
   `find_regions(background=fill_color)` on bar1 returned 7 fragments for
   5 real columns). The right primitive is positional/gap-based: find
   background-only column runs, take everything between them as one
   window. This is closer to `kernels.geometry`'s "band scan" style
   helpers (`closed_frames`/`connectors` already do local background-gap
   flood fill) than to `regions.find_regions`, but no shared kernel does
   exactly this "1D column-gap segmentation of a row band" operation.
   `kernels.regions.tile_bbox` is adjacent (even-partition a bbox into
   N cells) and could serve as a fallback once N and the total span are
   known, but doesn't discover N or the span itself.
2. **No kernel computes a per-window "local majority colour" or "ink vs
   fill" split.** Needed because fill colour varies by glyph family within
   the same row-band (measured: fill=10 and fill=7 side by side). A
   generic `dominant_color(window)` / `minority_mask(window)` primitive
   (Counter-based, same idiom `kernels.geometry._resolve_background`
   already uses for "most common colour") would generalize this cleanly.
3. **No kernel does greedy left-to-right token-string parsing against an
   ordered rule list** (§4) — `find_derivation`/`derive_rewrites` search
   all choices; TR87's actual win-check does not. A new, much smaller
   kernel (`greedy_parse(tokens, rules) -> list[RHS_tokens] | None`,
   O(len(tokens) × len(rules)), no search) would be the right-sized
   primitve, with `find_derivation` demoted to an optional fallback for
   ambiguous/failed parses.
4. **No kernel clusters raw pixel gap-widths into "same group" vs
   "different group" automatically** — this session hand-picked a 3px vs
   6px threshold from one level's measurement; a general version needs
   something like a 1D two-cluster split (could reuse
   `kernels.regions.group_by_axis`'s tolerance-chaining idea, or
   `kernels.regions.size_clusters`'s ratio-jump idea, applied to gap
   widths instead of region sizes/positions — `size_clusters` is
   actually a near-exact fit already, just needs to be handed a list of
   gap widths instead of region sizes).
5. **Untested**: token equality across MULTIPLE levels/instances — this
   session only had level-0 data. Whether canonical (dihedral) signatures
   remain a clean 1:1 token alphabet under `alter_rules`'s additional
   random per-glyph cyclic offset (applied at load time to the rule
   sprites themselves, not just bar2) is unmeasured. Beyond token
   equality, `alter_rules` also needs an entirely separate ADAPTER MODE no
   kernel gap here covers: when it's set, `ACTION1`-`ACTION4` edit the rule
   table itself (not bar2 — see the "Sources read" correction), so the
   adapter's action-planning step (§3's last stage) needs a second variant
   that targets rule-table glyph slots instead of bar2 columns; this is a
   design/adapter gap, not a missing kernel primitive.

## 6. Feasibility verdict (pre-§7; superseded — kept for the record)

**De-risked further than the 2026-07-14 banking note left it**: the
glyph-tokenization sub-problem (the part flagged "feature-scale" in the
round log) is now a *measured* 16→12-token rotation-invariant alphabet with
a working extraction recipe on the ONE level tested. The rule-pair grouping
(gap-width) and the dial's 7-state cycle are both independently
re-confirmed from frames — including genuine cycle CLOSURE and
reverse-inverse confirmation (see §2), not just a distinct-state count.

**This verdict was written before testing a second level and is now
KNOWN INCOMPLETE — see §7.** The segmentation approach these numbers rest
on does not survive level 1 (a level with multi-token rule sides). The
measurements above are still true (rotation confound, dial cycle) but
"feasible" for the segmentation step specifically was premature; §7 is the
current verdict.

## 7. Level 1 capture — the gate test (2026-07-15, Codex's cheapest falsification step)

Codex's review (`docs/r56_codex_tr87_review_20260715.md`) identified the
single cheapest test that could falsify this document's segmentation
approach: level 0 (the only captured level) happens to have EVERY rule's
LHS and RHS be exactly one glyph — level 1 has RHS runs of 2 and 3 glyphs.
If `occupied_runs`'s background-gap scan can't tell "one wide glyph" from
"several adjacent glyphs with no gap between them," it will silently merge
a multi-glyph run into one window. This was directly tested.

**How the level-1 frame was captured**: no capture existed for any level
but 0. A disposable, non-shipped, dev-only script
(`scripts/_tr87_capture_l1.py`, never wired into the shipped agent or any
test) runs ONE local episode via `arc_agi.Arcade` (the same offline harness
`scripts/test_tr87_*.py` already use — `environment_files/tr87/cd924810/
tr87.py` executes in-process; no Kaggle submission involved) and reads the
running game object's OWN rule table (`env._game.cifzvbcuwqe`, `.
zvojhrjxxm`, `.ztgmtnnufb` — verification-only, exactly the established
precedent, but used here to ADVANCE the game rather than build a solver) to
compute which buttons clear level 0. **15 actions** (well under level 0's
128-action budget) reliably clear it. Two bugs were found and fixed while
building this script, both worth recording:

1. **`ACTION1`/`ACTION2` direction was backwards from what the wiki
   claims** (see the top-of-document audit note) — using the wiki's
   claimed direction made the capture script clear NO columns at all;
   reading `tr87.py:1006` directly resolved it.
2. **The exact same "transient multi-layer frame" issue the SB26 lesson
   documents** (`.wiki/wiki/rounds/r53_unified-harness.md`) reproduces for
   TR87: right at the level-0→level-1 transition, `obs.frame` carries **37
   layers**, and `frame[0]` is STALE (its move-counter row still shows
   level 0's partially-used budget) while `frame[-1]` is the settled
   current frame (a fresh, full budget bar). The capture script now reads
   `frame[-1]`, confirmed by row-63's move-counter going from a partial bar
   to a full one between the two.

**Measurement: SEGMENTATION FALSIFIED, cross-validated exactly against oracle ground truth.**
Using the SAME oracle row bounds as level 0 (rows 41-45/52-56/4-28 — these
DO transfer across levels, confirmed) but freshly discovering fill colours,
extents, and windows (nothing about level 1's specific layout was assumed),
`occupied_runs` on the settled level-1 frame's upper rule-table bands
measured window widths of:

- band 0 (rows 4-10): `[7, 7, 7, 21]`
- band 1 (rows 13-19): `[7, 14, 7, 14]`
- band 2 (rows 22-28): `[7, 21, 7, 7]`

7px is one glyph (the same pitch measured on level 0). 14 and 21 are EXACT
multiples (2x, 3x) — and cross-checking against `env._game.cifzvbcuwqe`
(verification-only oracle read) for this exact level, all 6 rules' LHS/RHS
token counts are `[1→1, 1→3, 1→2, 1→2, 1→3, 1→1]`, and every single one of
the 12 measured window widths matches its corresponding rule side's token
count times 7px EXACTLY (`7,7` then `7,21` in band 0 = rule0's 1→1 then
rule1's 1→3; `7,14` then `7,14` in band 1 = rule2's 1→2 then rule3's 1→2;
`7,21` then `7,7` in band 2 = rule4's 1→3 then rule5's 1→1). Zero
discrepancies across all 12 windows. This is not a coincidental pixel-width
match — it is a direct, oracle-confirmed demonstration that
`occupied_runs`'s background-gap scan merges a multi-token rule side into
one window, exactly as Codex predicted.

A SEPARATE, second segmentation fragility was also found on this same
frame: bar2's own individual glyphs (single-token per the level's OWN
authored layout — bar1 has 4 clean single-glyph windows matching its 4
authored B-family glyphs) fragmented into small pieces (`[3,1,1,3, 5,5,5,5,
1,1,1]` instead of clean 7px runs) at 2 of its 5 slot positions — the
OPPOSITE failure mode (one glyph splitting apart) rather than multiple
glyphs merging, most likely because that specific digit's ink pattern
leaves an entire column background-only within its own 7px cell width,
which a background-only gap scan misreads as an inter-glyph gap. Both
failure modes stem from the same root cause: `occupied_runs` only sees
background vs. non-background, with no notion of "glyph" or fixed pitch.

**What DID generalize to level 1 (not falsified)**:
- Row-band positions (bar1/bar2/upper-grid rows) are level-independent —
  the SAME oracle rows worked on a structurally different level.
- Ink colour = 5 stayed constant across a THIRD glyph family (level 1 uses
  B-family, fill=7, and C-family, fill=11 — both still ink=5), strengthening
  rather than weakening that earlier finding.
- The "4 windows per row-band = 2 complete rules per band" structural
  layout held (level 1's bands still show 4 windows each, just with
  variable widths instead of level 0's uniform 7px).
- Level 1 (per the corrected flag table) genuinely has no flags set,
  confirmed directly from the running level object
  (`get_data("alter_rules"/"tree_translation"/"double_translation")` all
  `None`) — consistent with this document's table.

**A recovery path, found while investigating the falsification — since
built and tested against a second level, see §8**: every one of the 6
merged/split cases in this level had a width that was an EXACT integer
multiple of the globally-observed single-glyph pitch (7px, itself always
independently available since some window on the board is always
single-glyph). A recovery heuristic — "detect the single-glyph pitch from
any clean run on the board, then split any run whose width is a multiple
>1 of that pitch into that many equal sub-cells" — would have correctly
recovered all 6 multi-token cases measured here. At the time this
paragraph was first written, this was promising but based on ONE level's
data, untested against level 2 (multi-token LHS AND RHS) or any flagged
level; §8 closes the first half of that gap.

**Duplicate/conflicting-edge concern, already resolved (prior round, not
re-investigated here)**: Codex's review separately flagged that the FIRST
version of the dial-cycle probe's graph builder silently overwrote
conflicting `(frame, action)` edges (4 conflicting pairs found in that
version). This was already fixed in the prior correction round: the
current `scripts/_tr87_probe.py` collects every `(column, signature,
action)` observation into a set and explicitly checks for conflicts before
building the graph — 0 of 70 edges conflict in the corrected (column,
signature)-abstracted version. No new investigation was needed here; flagged
so it's clear this specific Codex finding was about the OLD exact-byte
graph, already superseded.

Reproducible via `scripts/_tr87_capture_l1.py` (produces `data/traces/
tr87_l1_reset.npz`).

## 8. Level 2 capture + the pitch-multiple splitter (2026-07-15, gate-reopening test)

**Level 2 captured — the hardest segmentation case.** `scripts/_tr87_capture_l2.py`
extends level 1's capture: it clears level 0 then level 1 (chained, same
oracle-assisted approach, generalized to a variable-length bar2 — see its
own docstring), landing on level 2 in 46 total actions. Level 2's own oracle
rule table (verification-only) has 6 rules with **multi-token LHS AND RHS**
— `[1→1, 2→2, 1→2, 2→1, 3→1, 1→1]` (LHS→RHS token counts) — confirming
Codex's source-read prediction exactly (level 1 only had multi-token RHS).
`get_data(...)` confirms level 2 also has no flags set, matching this
document's table.

**Two bugs found and fixed while building the level-2 capture, both worth
recording** (the second is a genuine, non-obvious repo-relevant finding, not
just a script typo):

1. A trivial stale-variable bug: the first draft of `clear_current_level()`
   returned only the action count, not the final `obs` — so `main()` kept
   using its OWN original RESET `obs` when saving the "level 2" frame,
   silently saving level 0's reset frame under the wrong filename. Caught
   because the saved frame was BYTE-IDENTICAL to `data/traces/tr87.npz`'s
   own frame 0 — a good general lesson: sanity-check a new capture against
   byte-equality with a KNOWN-DIFFERENT prior capture, not just against
   measured widths, which can coincidentally look plausible (this one did,
   until compared byte-for-byte).
2. A GENUINE second-order transient: even after fixing (1) and correctly
   reading `obs.frame[-1]`, the level-1→level-2 transition showed as many
   as 30 stacked layers (vs. no multi-layer transient at all when the stale
   bug made everything look deceptively "settled" at n_layers=1) — this
   reconfirms §7's transient-frame finding (same class as
   `.wiki/wiki/lessons/size_floor_and_settle_reads.md`'s "Trap 2") rather
   than contradicting it; the earlier apparent "n_layers=1, no transient
   needed" reading for level 2 was itself an artifact of bug (1), not a
   real measurement.

**Pitch-multiple splitter: SURVIVES both level 1 and level 2, exact
cross-validation, zero misses.** Implemented in `scripts/_tr87_probe.py`
(new "section 4", throwaway — not promoted to a kernel yet, per the
assignment): `detect_pitch()` takes the smallest run width anywhere on the
upper rule-table grid as the single-glyph pitch (always 7px, independently
re-derived from the board each time, never hardcoded); `recovered_token_counts()`
divides every run's width by that pitch. Tested against both captured
levels' upper-grid `occupied_runs` output, cross-validated against each
level's oracle rule-table token-count sequence (hardcoded as
`L1_ORACLE_TOKEN_COUNTS`/`L2_ORACLE_TOKEN_COUNTS` constants with capture-time
provenance — the splitter itself and its cross-validation both run
frame-only, no live env calls):

| Level | Measured upper-grid widths | Recovered counts | Oracle counts | Match |
|---|---|---|---|---|
| L1 | `[7,7,7,21, 7,14,7,14, 7,21,7,7]` | `[1,1,1,3, 1,2,1,2, 1,3,1,1]` | same | **exact, 12/12** |
| L2 | `[7,7,14,14, 7,14,14,7, 21,7,7,7]` | `[1,1,2,2, 1,2,2,1, 3,1,1,1]` | same | **exact, 12/12** |

24 of 24 token counts recovered exactly across both levels — including
level 2's multi-token LHS runs (widths 14 and 21 on the LHS side, not just
RHS), which the splitter recovers identically to RHS runs since it has no
notion of "which side" a run is on. The width arithmetic is EXACT in every
case (no run's width was ever off-by-one from a clean pitch multiple) —
confirms the "no extra pixel gap between sibling glyphs of the same rule
side" structural claim from §7 generalizes to level 2's harder case too.

**Bar2 fragmentation (§7's separate, opposite failure mode) does NOT
worsen on level 2 — it's absent.** Measured: level 1's bar2 fragmented
into 11 messy runs (`[3,1,1,3, 5,5,5,5, 1,1,1]` instead of 7 clean ones);
level 2's bar2 (also 7 glyphs) segmented into exactly 7 clean 5px runs,
zero fragmentation. This confirms the fragmentation is a property of WHICH
SPECIFIC DIGIT SHAPES happen to be on display (some digits have an
ink-free column within their own cell, most don't) rather than a
structural property tied to multi-token levels — good news, but also means
it can recur unpredictably on any level/column and isn't "fixed" by
anything measured so far.

**What this does and doesn't prove**: the splitter is now validated on 2 of
6 levels (both `alter_rules`/`tree_translation`/`double_translation`-free),
with EXACT results on 24/24 tokens across genuinely different rule-token
shapes (1↔1, 1↔2, 1↔3, 2↔1, 2↔2, 3↔1 all appear across the two levels'
12 rules). It has NOT been tested against any FLAGGED level (3 remain
fully uncaptured), and it has not yet been promoted to a kernel, wired into
an adapter, or used to drive an actual action plan — see "Recommendation."

## Recommendation

**Gate reopened for scoping, per Codex's own stated criterion ("a splitter
surviving 2+ representative levels reopens the gate") — but the adapter
build itself is still not started, and several concrete steps remain
before it should be.** In order of cheapest-first:

1. **Take the splitter back to Codex** for a primitive-promotion ruling
   (§8's own measurement is self-reported, not adversarially reviewed) —
   the same review discipline that caught the original segmentation
   overclaim should evaluate the recovery heuristic before it's trusted for
   an adapter.
2. **If approved, promote `detect_pitch`/`recovered_token_counts` from
   `scripts/_tr87_probe.py` into a kernel** (likely `kernels/parse.py`
   alongside `occupied_runs`) — with real tests, not just this probe's
   print statements.
3. **Rule-pair grouping still needs its own validation** — §2's gap-width
   (3px vs 6px) LHS|RHS-split finding was only measured on level 0's
   uniform case; confirm it still holds now that individual runs may
   themselves need splitting first (does the 3px/6px gap classification
   still work BETWEEN split sub-cells and RAW un-split runs consistently?
   not yet checked).
4. **`greedy_parse` + the dial executor remain unbuilt** — now unblocked in
   principle (tokens are recoverable), but still real work: rule extraction
   from the (now-splittable) upper grid, target derivation via
   `kernels.rewrite.greedy_parse`, and mapping each bar2 position's current
   token to its target via the 7-state cycle.
5. **Levels 3-6 (the flagged levels) remain fully unmeasured** — `alter_rules`
   in particular needs its own adapter mode (edit-the-rule-table, not
   edit-bar2) that nothing here has scoped, let alone measured.

Per Codex's sequencing note (unchanged by this update): any eventual
adapter belongs only in the quarantined `script25` package, not
`admorphiq`'s main tree, and cannot promote R56 on its own (needs `agent25`
non-inferiority + no hidden-transfer regression).
