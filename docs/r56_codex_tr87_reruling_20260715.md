# Codex re-ruling — tr87 splitter promotion + track priority (2026-07-15)

> Follow-up to docs/r56_codex_tr87_review_20260715.md after the L1+L2 gate results
> (splitter 24/24). Ruling: PROMOTE split_runs_by_pitch (explicit pitch, strict);
> bounded L0-L2 adapter GO only after offline integration gate; FT09 FIRST.

## Decisive ruling

### 1. Primitive promotion: **PROMOTE, but reject the proposed default**

Promote the generic computation to [parse.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/kernels/parse.py:48), but use this conceptual API:

```python
split_runs_by_pitch(runs, pitch, *, axis)
```

Do not use `pitch=None → min(run width)` in the kernel.

The boundary is:

- Kernel: mechanically split half-open spans by an explicitly supplied positive pitch.
- Caller/playbook: decide that equal-pitch tiling applies and infer pitch from a selected clean run family.
- TR87 adapter: choose upper-rule parent runs, infer `min(widths)`, assert every width has zero remainder, then call the kernel.

Requirements:

- Exact division only; a remainder must fail rather than truncate or round.
- Preserve `parent_index` so raw rule-side grouping survives splitting.
- Preserve/partition `cells`; this is why `axis` is needed.
- Tests for row/column axes, 7/14/21 widths, empty input, invalid pitch, nonmultiples, provenance, and non-mutation.

The splitter itself is generic: it knows neither glyphs nor TR87. But minimum-width pitch inference is a semantic hypothesis. L1 bar2’s `[3,1,1,3,…]` fragmentation proves why making `min()` a universal default is unsafe ([documented here](/Users/nhn/Workspace/Admorphiq/docs/tr87_frame_only_grammar_design_20260715.md:596)). Do not apply this heuristic to bar2.

### 2. TR87 sequence and kill criteria

I independently rechecked item (a): all six L1/L2 bands return four raw parent runs and gaps exactly `[3,6,3]`. Therefore (a) passes.

| Order | Work | Pass bar | Kill/pause criterion |
|---|---|---|---|
| 1 | Land strict `split_runs_by_pitch` plus tests; turn the L1/L2 probe prints into assertions | All 24 sides exact; provenance retained | Any nonzero remainder or malformed child span |
| 2 | Offline frame-only integration on L0–L2: discover bands → group raw sides → split → identify tokens → extract six ordered rules → `greedy_parse(bar1)` → predict target | Token-for-token oracle equality on all three levels; no source reads or fixed coordinates/palettes in the operational path | One unknown/colliding token, wrong rule order, parse failure, or target mismatch. No BFS action fallback |
| 3 | Bar2 lattice extraction and dial executor | Current bar2 token recovered despite L1 fragmentation; all targets exist in the measured seven-state graph; zero transition conflicts | Any target absent, ambiguous slot identity, bracket mismatch, or dependence on `occupied_runs` to segment fragmented bar2 glyphs |
| 4 | Live simple-mode qualification | Clear L0–L2 from three fresh starts, with only planned dial/navigation actions plus measured transition settling; adapter lint passes | Any run fails, needs hardcoded coordinates, or requires exploratory recovery actions |
| 5 | Capture and design flagged levels in order: L4 double, L5 alter, L6 combined | Settled reset, representative transitions for every control class, and winning-boundary capture before implementing each mode | No frame-visible mapping from editable objects to rule structure; otherwise bank the simple 3/6 slice instead of contaminating kernels |

Two implementation rulings remain unchanged:

- Group the four raw rule-side runs first. Splitting afterward creates internal 0px boundaries; flattening first would destroy the `[3,6,3]` structural signal.
- Use C4 rotation canonicalization, not full D4. The current probe still uses reflections; the integration test must prove rotation-only identity without chiral collisions.

Capture-first remains mandatory for L4–L6. A reset screenshot alone is insufficient, especially for `alter_rules`; capture at least the settled reset, one transition per action/control class, cursor movement, and the winning boundary before designing that mode.

### 3. Adapter scope and priority

**Full TR87 adapter: NO-GO today.**  
**Bounded L0–L2 adapter: GO only after the offline integration gate passes exactly.**

The splitter clears the perception falsification, but it does not yet clear:

- coordinate/palette-free discovery required by the [script25 quarantine](/Users/nhn/Workspace/Admorphiq/src/admorphiq/adapters25/__init__.py:9);
- bar2 fragmentation;
- actual frame-only rule extraction and target prediction;
- live executor qualification;
- any flagged-level semantics.

The honest value calculation favors **FT09 first**.

Both games have six levels, so total RHAE weight is 21:

- TR87’s presently supported simple slice, L1–L3, covers only `1+2+3 = 6/21 = 28.6%` of its maximum game weight. The uncaptured flagged levels hold `15/21 = 71.4%`.
- FT09 already has L1; solving L2–L6 addresses `20/21 = 95.2%` of its game weight, with complete six-level frame evidence and gold trajectories. The current adapter explicitly identifies target inference as the missing component ([ft09.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/adapters25/ft09.py:11)).

On a 25-game card, those perfect-efficiency ceilings are roughly:

- TR87 simple slice: +1.14 percentage points.
- FT09 remaining depth: +3.81 percentage points.

Those are ceilings, not forecasts, but the evidence-adjusted ordering is still clear: **prioritize FT09 target decoding; bank TR87 after the strict splitter and offline integration gate.**

One correction to the FT09 framing: the gold win transitions show a single 6×6 stencil flip, but that does not prove the deeper target vector is simply one-hot. L2 contains two distinct clue glyphs with an unresolved mapping to 13 buttons ([measured topology](/Users/nhn/Workspace/Admorphiq/.wiki/wiki/rounds/r53_unified-harness.md:3273)). Treat the next FT09 round as supervised clue-to-target decoding from gold frames, not another guessed single-cell hypothesis.
