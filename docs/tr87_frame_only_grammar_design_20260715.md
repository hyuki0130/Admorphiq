# TR87 frame-only rewrite-grammar adapter: scoping + prototype (2026-07-15)

**Status: design + prototype done; NOT built.** This scopes whether the
R56 kernels (`derive_rewrites`/`find_derivation`, `shapes`, `regions`)
can crack the tr87 wall (0/6 for the LLM-free card) once combined with a
game-specific adapter. Verdict: **feasible, and the hardest sub-problem
(glyph tokenization) is now measured, not hypothesized** — but a real
solver is a multi-day build, not a same-session patch. See "Recommendation"
at the end.

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
  backtracking) with 3 per-level output modes (`alter_rules`,
  `tree_translation`, `double_translation`).
- `src/admorphiq/kernels/` (`rewrite.py`, `regions.py`, `shapes.py`,
  `geometry.py`) — the available building blocks.

## 1. What captured data exists

Located via repo-wide search (`find . -iname "*tr87*"`):

| File | Content | Useful for |
|---|---|---|
| `.wiki/raw/traces/tr87.jsonl` | 1 line, summary stats only (no frames) | provenance, not extraction |
| `data/traces/tr87.npz` | 1200 rows: `frames`/`next_frames` (64×64 uint8), `actions` (1-indexed `{1,2,3,4}`), `level_index` (all 0), `is_gold` (all False) | glyph/layout extraction (see below: it's 1200 **independent single-step samples from one fixed reset**, not a trajectory) |
| `data/transitions/train/tr87.npz` | 2000 rows: `frames`/`next_frames` (int16), `actions` (0-indexed `{0,1,2,3}`) | **multi-step chaining** (see below: 1927/1928 before-frames connect into another sample's after-frame — a connected transition graph, not one trace, but walkable) |
| `scripts/rounds/*/games/*tr87*.json`, `scripts/test_tr87_*.py` | prior LLM-benchmark results / earlier hand probes | historical context only |

Both `.npz` files are **level 0 only** (no captures exist for levels 1-5,
which use the `alter_rules`/`tree_translation`/`double_translation` modes).
This scoping and prototype is therefore level-0-only; the other 3 modes are
designed on paper (from the verification-only read) but not measured.

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

**The dial is confirmed to cycle through exactly 7 distinct states**,
independently re-derived from frames (not read off `kjgicbtgrt = 7` and
assumed) via a transition-graph walk: chaining `action=1` (dial-step) hops
from a fixed start state through `data/transitions/train/tr87.npz`'s
connected graph visits **7 states before the sample data runs out, all
7 pairwise distinct** (both under rotation-invariant AND translation-only
signatures — the counts are equal, confirming a slot's own on-screen
rotation stays fixed across its own 7-state cycle, matching
`wpbnovjwkv`'s rotation-preserving clone). The reverse action (`action=0`)
walks the same 7 states backward, consistent with the source's documented
ACTION1=+1/ACTION2=-1 exact-inverse relationship. Note: the exploration
data ran out before observing the literal wraparound-to-start edge, so
"exactly 7, cyclic" rests on the 7-distinct-states count plus the source's
own `% (len(states)-1)` modular step logic, not a directly observed
7th-hop-returns-to-start frame — a real solver should re-verify closure
live, cheaply (7-8 presses).

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
*fallback* engine (§4) but is not what the primary L1 parse needs.

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

**Implication**: the L1 (`alter_rules=False`) adapter needs a new,
simpler primitive — "greedy tokenize `bar1_tokens` by the rule LHS list in
order, concatenate the matched RHS's" — not a BFS search. `find_derivation`
remains useful as a **defensive fallback**: if the greedy parse fails to
cover all of bar1 (a real possibility if an adapter's rule extraction
mis-orders or mis-splits a rule), a bounded `find_derivation`-style search
over the *same* rule set could recover a valid tiling the naive greedy
parse missed, or explicitly report "genuinely unparseable — extraction
bug" rather than silently producing a wrong plan. The `tree_translation`
and `double_translation` modes (unmeasured — no captured data at those
levels) are more clearly derivation-shaped (recursive RHS re-expansion),
and are closer to what `find_derivation` was built for — but each is its
own bespoke traversal per the source, not a single generic search, so
should be scoped as its own follow-up once level 1+ frames exist.

## 5. Kernel gaps this exposes

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
   sprites themselves, not just bar2) is unmeasured.

## 6. Feasibility verdict

**Confirmed feasible in principle, and de-risked further than the
2026-07-14 banking note left it**: the glyph-tokenization sub-problem
(the part flagged "feature-scale" in the round log) is now a *measured*
16→12-token rotation-invariant alphabet with a working extraction recipe,
not an open question. The rule-pair grouping (gap-width) and the dial's
7-state cycle are both independently re-confirmed from frames. What
remains unbuilt: (a) the adapter code implementing §3's pipeline end-to-end
as `admorphiq` game-specific glue (analogous to `rotation.py`/`slider.py`),
(b) the new small kernel primitives in §5 (gap-window segmentation, local
majority colour, greedy token parse, gap-width clustering — all
individually cheap, none currently exist), (c) the dial-executor (map
current↔target token via the 7-cycle, emit ACTION1/2 counts + ACTION3/4
navigation — straightforward once tokens are known), and (d) coverage for
the 3 per-level modes beyond L1's simple case, which have zero captured
data to prototype against.

## Recommendation

This is a real, scoped round (not a same-session patch): build the 4
small kernel primitives in §5 first (each is independently testable,
cheap, reusable beyond TR87), then the TR87 adapter on top, validated
against level 0's captured frames end-to-end (extract → derive expected
bar2 → confirm it equals a KNOWN correct bar2 state, which would require
either a captured "is_gold"/solved trace — none exists yet, all `is_gold`
are `False` — or one bounded live verification run). The dial executor
(step count math + bracket navigation) is the cheapest remaining piece.
Levels 1-5 (the 3 output modes) should be scoped as a explicit follow-up
once level-specific frames are captured, not assumed to generalize from
level 0.
