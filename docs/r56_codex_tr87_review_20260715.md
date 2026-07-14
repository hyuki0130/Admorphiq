# Codex review — TR87 frame-only grammar design (2026-07-15)

> Adversarial review of docs/tr87_frame_only_grammar_design_20260715.md +
> scripts/_tr87_probe.py. Verdict: GATE ON REPRESENTATIVE L1+ CAPTURES FIRST.

## Verdict: GATE ON REPRESENTATIVE L1+ CAPTURES FIRST

Do not spend multiple days building a level-0-only TR87 adapter. Level 0 validates one unusually simple 1→1-rule layout; it does not validate the perception or control architecture needed for the remaining levels.

The cheapest next step is:

> Capture one reset frame from level index 1—the second game level—and run the existing gap probe against it, with oracle row bounds only.

That level already contains 1→3 and 1→2 rules. If `gap_windows` merges adjacent glyph slots, as the source layout strongly predicts, the current token-segmentation pipeline is falsified within an hour. If direct level selection is unavailable, use a disposable, non-shipped source-assisted L0 action sequence solely to advance and capture the frame.

## Measured-claim audit

| Claim | Verdict |
|---|---|
| Dihedral 5/5 vs translation 1/5 | **Supported for the single L0 reset.** The probe computes set overlap at [scripts/_tr87_probe.py:108](/Users/nhn/Workspace/Admorphiq/scripts/_tr87_probe.py:108). Although that metric is weaker in principle than five position-wise matches, my audit found all five bar1 signatures distinct, each matching exactly one upper token. C4 rotations alone also give 5/5; reflections are unnecessary. |
| Exactly seven cyclic dial states | **Overstated.** The walk reaches seven distinct states and then lacks another sampled edge [scripts/_tr87_probe.py:145](/Users/nhn/Workspace/Admorphiq/scripts/_tr87_probe.py:145). This proves **at least seven**, not exactly seven or closure. The claimed reverse walk is not implemented. Equal translation/D4 distinct counts also do not prove fixed orientation; that fact comes from source preservation at [tr87.py:1024](/Users/nhn/Workspace/Admorphiq/environment_files/tr87/cd924810/tr87.py:1024). The graph builder also silently overwrites duplicate `(frame, action)` edges; I found four conflicting pairs. |
| 3px/6px LHS–RHS split | **Pixels supported; semantics source-assisted.** Direct inspection confirms every L0 band has windows separated by `[3,6,3]`. But the probe neither prints nor asserts those widths; it only reports 12 blocks using the source-known expectation of six 1→1 rules [scripts/_tr87_probe.py:103](/Users/nhn/Workspace/Admorphiq/scripts/_tr87_probe.py:103). Frames show two gap classes; the assertion that 3px means LHS→RHS and 6px means rule boundary depends on marker/source correspondence. |
| Greedy ordered parse | **Strongly supported by source, not by the probe.** The checker scans rules in list order, matches at the current source position, accepts the first applicable rule and never backtracks [tr87.py:1056](/Users/nhn/Workspace/Admorphiq/environment_files/tr87/cd924810/tr87.py:1056). |

The prototype is also more oracle-assisted than “frame-only extraction recipe” suggests: every band, palette, window and bracket row is hardcoded [scripts/_tr87_probe.py:34](/Users/nhn/Workspace/Admorphiq/scripts/_tr87_probe.py:34). Discovery—the portion a valid `script25` adapter must perform without hardcoded coordinates or pixel algorithms—has not been prototyped.

## Primitive review

| Proposed primitive | Ruling |
|---|---|
| Row-band gap-window segmentation | **Generic if reformulated.** Expose an axis-neutral occupied-run projection over a caller-supplied bbox/background predicate. Do not call its outputs “glyph windows.” It is genuinely absent from `regions`, but L0 evidence does not show that every occupied run equals one token. |
| Local majority colour / minority mask | **Do not add as proposed.** Dominant colour is generic; “minority equals ink” is a semantic and two-colour assumption. Existing `canonical_key(mode="shape", background=None)` already treats the local mode as background [canonical.py:103](/Users/nhn/Workspace/Admorphiq/src/admorphiq/kernels/canonical.py:103). At most expose a generic colour histogram/mode helper and let the caller choose the mask predicate. |
| Greedy ordered-rule parse | **Add to `rewrite.py`.** This is generic, small and materially different from the branching successor/BFS semantics in [rewrite.py:75](/Users/nhn/Workspace/Admorphiq/src/admorphiq/kernels/rewrite.py:75). Return the output plus an ordered match proof. Do **not** use `find_derivation` as an action-driving fallback: a nongreedy tiling can be rejected by the actual game even when it is grammatically valid. BFS is useful only diagnostically. |
| Gap-width clustering | **Defer or generalize existing logic.** A TR87-specific two-gap classifier is not generic. If cross-level evidence justifies it, extract a generic numeric `ratio_clusters(values)` and have `regions.size_clusters` delegate to it; its ratio-jump algorithm already supplies the computation [regions.py:268](/Users/nhn/Workspace/Admorphiq/src/admorphiq/kernels/regions.py:268). |

Also use C4 rotation canonicalization, not full D4, unless the caller explicitly declares reflection equivalence. `dihedral_transforms` includes mirrors [shapes.py:75](/Users/nhn/Workspace/Admorphiq/src/admorphiq/kernels/shapes.py:75); that can collapse distinct chiral tokens in another grammar even though this particular 21-glyph source alphabet has no D4 collisions.

## Underweighted risks

The largest risk is not an exotic translation mode—it is ordinary multi-token rules in uncaptured simple levels. Source reconstruction shows:

- Level index 1 includes RHS lengths 2 and 3.
- Level index 2 includes multi-token LHS and RHS.
- Adjacent token cells use the same 7px pitch, so background-gap segmentation can merge an entire multi-token side into one occupied window.

The control regimes are also described inaccurately. `alter_rules` is not an output-translation mode: it changes the editable objects from bar2 columns to whole LHS/RHS rule sides [tr87.py:996](/Users/nhn/Workspace/Admorphiq/environment_files/tr87/cd924810/tr87.py:996). On the final level, `tree_translation` takes precedence over `double_translation` because the checker uses `if … elif` [tr87.py:1065](/Users/nhn/Workspace/Admorphiq/environment_files/tr87/cd924810/tr87.py:1065). Consequently, the proposed universal “map each bar2 column and navigate its dial” executor is wrong for altered-rule levels.

There is also no solved/gold L0 trace, as the design acknowledges [tr87_frame_only_grammar_design_20260715.md:264](/Users/nhn/Workspace/Admorphiq/docs/tr87_frame_only_grammar_design_20260715.md:264). Thus even the simple end-to-end extract→parse→execute path has not received a frame-only acceptance test.

## R56 sequencing

A TR87 adapter belongs only in the quarantined `script25` package, whose rules explicitly prohibit embedded pixel processing and hardcoded coordinates [adapters25/__init__.py:9](/Users/nhn/Workspace/Admorphiq/src/admorphiq/adapters25/__init__.py:9). Sequence it as:

1. Finish the frozen experiment sequence required by R56.
2. Capture representative TR87 frames/transitions.
3. Add only the generic primitives that survive those captures.
4. Build `adapters25/tr87.py` as a `script25` expressiveness test.
5. Keep `agent25` and hidden-transfer promotion gates unchanged.

A TR87 public-script win cannot promote R56 by itself; the plan requires agent25 non-inferiority, observed tool use and no hidden/proxy regression [r56_codex_toolbase_verdict_20260715.md:243](/Users/nhn/Workspace/Admorphiq/docs/r56_codex_toolbase_verdict_20260715.md:243).

In short: the L0 rotation result is solid, but the proposed segmentation and executor architecture are not yet representative of TR87. Capture level index 1 first; do not build the four primitives and adapter as currently scoped.
