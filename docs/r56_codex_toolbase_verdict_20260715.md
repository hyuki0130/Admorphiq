# R56 Codex verdict — tool-base completeness strategy (2026-07-15)

> Consultation brief: user proposal that the hand-built tool layer ALONE should clear all
> 25 public games as the LLM's foundation. Brief archived in session scratchpad;
> full verdict below (codex exec --sandbox read-only, 2026-07-15 00:31-00:35 KST).

## Verdict

Do **not** make “finish the current LLM-free solver card to 25/25” the R56 objective. That optimizes public semantic coverage, and the measured hidden transfer—0.14 to 0.20 despite a major public gain—is strong evidence that this axis is saturating.

Do make this the R56 objective:

> Build a namespace-safe generic kernel library such that thin, quarantined scripts can compose it to clear the public games, while the LLM can compose the same kernels online on unseen games.

That preserves the user’s “tools are capable hands” model without putting handcrafted public-game brains into the agent.

The distinction is:

- **Wrong:** autonomous mechanic-family solvers clear 25/25.
- **Right:** generic kernels are expressive enough that scripts supplying the mechanic hypothesis and role assignments can clear 25/25.

The eventual scripted 25/25 target is sound as a **library expressiveness test**, but it must not be the promotion metric. Hidden transfer and LLM-agent performance remain the promotion metrics.

## Were the current solvers developed generically?

They are runtime frame-only, which is good, but they are not neutral generic tools. They are public-exemplar-derived semantic solvers.

The source comments show extensive tuning from particular boards: fixed CD82 canvas geometry and win masking, SU15 distance thresholds, SB26 screen bands and slot pitch, WA30 item/target rendering, RE86 active-marker behavior, and S5I5 bar structure. Several modules explicitly began from wiki or legacy solver knowledge and then replaced internal reads with frame-visible equivalents.

So the accurate characterization is:

> They were developed generically within known mechanic families, using sample games and live measurements. They were not decomposed into game-agnostic perception, dynamics, and computation primitives.

That explains both results: strong public performance and weak hidden transfer.

## Proposed decomposition

| Current asset | Namespace-safe extraction | Keep out of the namespace |
|---|---|---|
| [ring_paint.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/ring_paint.py:140) | Learn an overwrite mask from before/after frames; `plan_overwrites(initial, target, learned_operators, compare_mask)`; generic graph path over caller-supplied nodes/edges | Fixed 10×10 canvas, ring positions, launch/arrow masks, hardcoded arrow coordinates, off-diagonal win rule, `detect_paint_layout`, current `nav_path` |
| [merge_drag.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/merge_drag.py:199) | Region features; object tracking; motion vectors; `point_toward`; pair selection under a caller-supplied predicate; online estimation of click-induced displacement | Largest region = goal, all others = tiles, same color = mergeable, farthest-first gathering, SU15-derived radii, `next_drag_click`, `next_merge_click` |
| [delivery.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/delivery.py:196) | Closed-frame detection; size clustering; multi-color motion tracking; bbox/slot tiling; configuration-space BFS; path-to-action conversion using a measured action map | Small rings = items, large rings = targets, player body/accent interpretation, pickup/carry/drop policy, `detect_delivery_puzzle` |
| [rotation.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/rotation.py:260) | `detect_framed_patterns`; crop/pad masks; dihedral transform generation; IoU scoring; bipartite assignment; changed-region attribution | Calling patterns “rotatable pieces,” inferring references, mechanic applicability, geometric widget guesses, `detect_rotation_puzzle`, click-until-match controller |
| [slider.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/slider.py:159) | Elongated-region detection; axis/endpoints; extent measurement; point-to-axis projection; attribute a transition to the changed region | Foreign cell = tip, button rings control bars, nearest forward marker = goal, grow-only policy, `detect_slider_puzzle`, `resolve_goal` |
| [transform_route.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/transform_route.py:417) | Gap-tolerant clustering; motion-isolated object extraction; axis snapping; `covering_offsets(shape, points)`; convert offsets through a supplied action map | Ring dot = required color, same-color cluster = movable sprite, center foreign pixel = active selector, ACTION5 cycling, `detect_transform_puzzle` |
| [sort_match.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/sort_match.py:208) | Row/column grouping; multiset comparison; hollow-box/connector extraction; region graph construction; assignment and caller-directed graph traversal | Top = target, bottom = pool, middle = slots, fixed six-pixel slot grammar, DFS/revisit consumption semantics, ACTION5 verify, `detect_portal_sort` plan |
| [graph_search.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/tools/graph_search.py:289) | State canonicalization variants with confidence; observed transition store; shortest known path; reachable frontier query; caller-supplied scorer | Salience-generated click policy, autonomous `propose`, novelty ownership, automatic tier unlocking, random sink escape, implicit goal inference |
| [world_model_agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/world_model_agent.py:301) | `segment_objects`; transition observation; measured action map; change probability; click-effect evidence; passive `predict(action)`; explicit-input path planning | `infer_goal`, `plan_interaction`, rare-object action ranking, family routing, all `_enter_*`/`_*_step` controllers, fallback policy |

The existing planners divide similarly:

- `StateGraph` and pure search/assignment routines are safe.
- `BFSSolver` and `SequenceSolver` are offline evaluators, not model tools: they own resets, environment calls, winning detection, and action expenditure.
- Goal scoring is safe only when the LLM explicitly supplies the goal.
- Goal inference and autonomous frontier exploration remain policy.

A useful initial library would be only six intent-level groups:

1. `regions_and_relations`
2. `track_motion_and_effects`
3. `shortest_path` / `configuration_path`
4. `shape_transforms_and_assignment`
5. `learned_operators_and_search`
6. `rewrite_derivations`

This is richer internally without presenting 30 unrelated functions to the 27B.

## Tool adoption

A richer **flat namespace would make adoption worse**. The present failure to call `shortest_path` is not evidence that the model needs five more planners. It may be failing to:

- commit to a navigation hypothesis;
- construct a passability mask;
- remember the tool;
- emit valid executable code;
- or trust the result enough to act.

The better interface is declared-intent offloading:

1. The model declares a typed problem: navigation, transform matching, assignment, rewrite derivation, and so on.
2. It supplies the semantic inputs: roles, start, goal, masks, rules, constraints.
3. The system automatically invokes the corresponding pure kernel.
4. The model receives the result and chooses the action.

That avoids an applicability classifier: the **model** selected the intent and supplied the semantics. The tool only computed.

For example, after a structured navigation declaration, the harness may call `shortest_path` automatically. Requiring the model to remember the Python function name adds no intelligence and is not part of the north-star division of labor.

Expose additional groups progressively through `help("shape")` or after a declared intent. Do not print every signature in the permanent system prompt.

## Sequencing and experiments

Do not alter the running experiments.

1. **Finish engagement.** This establishes whether the model can reliably produce executable decisions and use feedback.
2. **Finish basenav.** This establishes whether intent-matched nudging makes one existing pure primitive usable.
3. **Run the currently specified full25 qualification unchanged.** It remains the qualification run for the frozen R55 treatment.
4. **Begin R56 decomposition behind a new flag.**

R56 should then have two separate scoreboards:

- **`script25`: kernel expressiveness.** Quarantined scripts compose generic kernels across public games. Public adapters are never model-visible.
- **`agent25`: LLM competence.** The LLM receives only namespace-safe kernels and must supply roles, goals, and hypotheses.

Do not report `script25` as agent capability. A public improvement cannot promote R56 unless:

- the safe-kernel agent improves or is non-inferior on `agent25`;
- relevant tool use is observed rather than merely exposed;
- and hidden/proxy transfer does not regress.

For `script25` to be meaningful, adapters may assign roles and declare mechanic hypotheses, but may not contain hardcoded coordinates, palettes, target sequences, low-level pixel algorithms, or their own search implementations. Otherwise the “tool completeness” test becomes another solver portfolio under a different directory name.

## TR87 and the banked walls

Build the pure rewrite kernel in R56; do not defer it until the rest of 25/25.

A namespace-safe API would look more like:

```python
derive_rewrites(
    source_tokens,
    rules,
    max_depth,
    strategy="parallel",  # or leftmost, all_matches
) -> [{"result": ..., "proof": ...}]
```

The tool receives explicit tokens, rules, and derivation semantics. It does not know about TR87, bars, dials, levels, or actions. It should return derivations and proof traces.

Then keep these out of the namespace:

- TR87 rule-table extraction assumptions;
- interpretation of the upper panel as LHS/RHS;
- decoding its per-level mode;
- dial-state calibration;
- cursor movement and dial execution.

Those belong initially in a quarantined `script25` adapter. Later the LLM can reconstruct them using generic symbol extraction, grouping, motion tracking, and cycle planning.

For the other walls:

- **BP35:** build learned object dynamics and configuration-space planning, not a gravity-platformer solver.
- **DC22:** build transparent state canonicalization and action-conditioned change masks, not a button-then-exit policy.
- **G50T:** improve passive action-effect and relation-delta learning, not an explore/interact controller.
- **SC25:** build generic pattern/set constraint and sequence-search kernels; do not expose known spell patterns.
- **CD82/depth:** extract learned overwrite operators; remove fixed launch masks from the reusable layer.

## R56 decision

Name the direction something like **Primitive Firewall and Scripted Composition**.

Its binding objective should be:

> Preserve the public solver card as a quarantined oracle, extract its reusable perception/dynamics/computation kernels, prove those kernels sufficient through thin scripted composition, and improve LLM adoption through declared-intent offloading. Do not spend R56 finishing public semantic controllers.

So: **yes to eventual scripted 25/25 kernel completeness; no to autonomous no-LLM 25/25 as the intermediate optimization target.** The former builds hands. The latter keeps building a second, public-trained brain.
tokens used
156,622
## Verdict

Do **not** make “finish the current LLM-free solver card to 25/25” the R56 objective. That optimizes public semantic coverage, and the measured hidden transfer—0.14 to 0.20 despite a major public gain—is strong evidence that this axis is saturating.

Do make this the R56 objective:

> Build a namespace-safe generic kernel library such that thin, quarantined scripts can compose it to clear the public games, while the LLM can compose the same kernels online on unseen games.

That preserves the user’s “tools are capable hands” model without putting handcrafted public-game brains into the agent.

The distinction is:

- **Wrong:** autonomous mechanic-family solvers clear 25/25.
- **Right:** generic kernels are expressive enough that scripts supplying the mechanic hypothesis and role assignments can clear 25/25.

The eventual scripted 25/25 target is sound as a **library expressiveness test**, but it must not be the promotion metric. Hidden transfer and LLM-agent performance remain the promotion metrics.

## Were the current solvers developed generically?

They are runtime frame-only, which is good, but they are not neutral generic tools. They are public-exemplar-derived semantic solvers.

The source comments show extensive tuning from particular boards: fixed CD82 canvas geometry and win masking, SU15 distance thresholds, SB26 screen bands and slot pitch, WA30 item/target rendering, RE86 active-marker behavior, and S5I5 bar structure. Several modules explicitly began from wiki or legacy solver knowledge and then replaced internal reads with frame-visible equivalents.

So the accurate characterization is:

> They were developed generically within known mechanic families, using sample games and live measurements. They were not decomposed into game-agnostic perception, dynamics, and computation primitives.

That explains both results: strong public performance and weak hidden transfer.

## Proposed decomposition

| Current asset | Namespace-safe extraction | Keep out of the namespace |
|---|---|---|
| [ring_paint.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/ring_paint.py:140) | Learn an overwrite mask from before/after frames; `plan_overwrites(initial, target, learned_operators, compare_mask)`; generic graph path over caller-supplied nodes/edges | Fixed 10×10 canvas, ring positions, launch/arrow masks, hardcoded arrow coordinates, off-diagonal win rule, `detect_paint_layout`, current `nav_path` |
| [merge_drag.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/merge_drag.py:199) | Region features; object tracking; motion vectors; `point_toward`; pair selection under a caller-supplied predicate; online estimation of click-induced displacement | Largest region = goal, all others = tiles, same color = mergeable, farthest-first gathering, SU15-derived radii, `next_drag_click`, `next_merge_click` |
| [delivery.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/delivery.py:196) | Closed-frame detection; size clustering; multi-color motion tracking; bbox/slot tiling; configuration-space BFS; path-to-action conversion using a measured action map | Small rings = items, large rings = targets, player body/accent interpretation, pickup/carry/drop policy, `detect_delivery_puzzle` |
| [rotation.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/rotation.py:260) | `detect_framed_patterns`; crop/pad masks; dihedral transform generation; IoU scoring; bipartite assignment; changed-region attribution | Calling patterns “rotatable pieces,” inferring references, mechanic applicability, geometric widget guesses, `detect_rotation_puzzle`, click-until-match controller |
| [slider.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/slider.py:159) | Elongated-region detection; axis/endpoints; extent measurement; point-to-axis projection; attribute a transition to the changed region | Foreign cell = tip, button rings control bars, nearest forward marker = goal, grow-only policy, `detect_slider_puzzle`, `resolve_goal` |
| [transform_route.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/transform_route.py:417) | Gap-tolerant clustering; motion-isolated object extraction; axis snapping; `covering_offsets(shape, points)`; convert offsets through a supplied action map | Ring dot = required color, same-color cluster = movable sprite, center foreign pixel = active selector, ACTION5 cycling, `detect_transform_puzzle` |
| [sort_match.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/sort_match.py:208) | Row/column grouping; multiset comparison; hollow-box/connector extraction; region graph construction; assignment and caller-directed graph traversal | Top = target, bottom = pool, middle = slots, fixed six-pixel slot grammar, DFS/revisit consumption semantics, ACTION5 verify, `detect_portal_sort` plan |
| [graph_search.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/tools/graph_search.py:289) | State canonicalization variants with confidence; observed transition store; shortest known path; reachable frontier query; caller-supplied scorer | Salience-generated click policy, autonomous `propose`, novelty ownership, automatic tier unlocking, random sink escape, implicit goal inference |
| [world_model_agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/world_model_agent.py:301) | `segment_objects`; transition observation; measured action map; change probability; click-effect evidence; passive `predict(action)`; explicit-input path planning | `infer_goal`, `plan_interaction`, rare-object action ranking, family routing, all `_enter_*`/`_*_step` controllers, fallback policy |

The existing planners divide similarly:

- `StateGraph` and pure search/assignment routines are safe.
- `BFSSolver` and `SequenceSolver` are offline evaluators, not model tools: they own resets, environment calls, winning detection, and action expenditure.
- Goal scoring is safe only when the LLM explicitly supplies the goal.
- Goal inference and autonomous frontier exploration remain policy.

A useful initial library would be only six intent-level groups:

1. `regions_and_relations`
2. `track_motion_and_effects`
3. `shortest_path` / `configuration_path`
4. `shape_transforms_and_assignment`
5. `learned_operators_and_search`
6. `rewrite_derivations`

This is richer internally without presenting 30 unrelated functions to the 27B.

## Tool adoption

A richer **flat namespace would make adoption worse**. The present failure to call `shortest_path` is not evidence that the model needs five more planners. It may be failing to:

- commit to a navigation hypothesis;
- construct a passability mask;
- remember the tool;
- emit valid executable code;
- or trust the result enough to act.

The better interface is declared-intent offloading:

1. The model declares a typed problem: navigation, transform matching, assignment, rewrite derivation, and so on.
2. It supplies the semantic inputs: roles, start, goal, masks, rules, constraints.
3. The system automatically invokes the corresponding pure kernel.
4. The model receives the result and chooses the action.

That avoids an applicability classifier: the **model** selected the intent and supplied the semantics. The tool only computed.

For example, after a structured navigation declaration, the harness may call `shortest_path` automatically. Requiring the model to remember the Python function name adds no intelligence and is not part of the north-star division of labor.

Expose additional groups progressively through `help("shape")` or after a declared intent. Do not print every signature in the permanent system prompt.

## Sequencing and experiments

Do not alter the running experiments.

1. **Finish engagement.** This establishes whether the model can reliably produce executable decisions and use feedback.
2. **Finish basenav.** This establishes whether intent-matched nudging makes one existing pure primitive usable.
3. **Run the currently specified full25 qualification unchanged.** It remains the qualification run for the frozen R55 treatment.
4. **Begin R56 decomposition behind a new flag.**

R56 should then have two separate scoreboards:

- **`script25`: kernel expressiveness.** Quarantined scripts compose generic kernels across public games. Public adapters are never model-visible.
- **`agent25`: LLM competence.** The LLM receives only namespace-safe kernels and must supply roles, goals, and hypotheses.

Do not report `script25` as agent capability. A public improvement cannot promote R56 unless:

- the safe-kernel agent improves or is non-inferior on `agent25`;
- relevant tool use is observed rather than merely exposed;
- and hidden/proxy transfer does not regress.

For `script25` to be meaningful, adapters may assign roles and declare mechanic hypotheses, but may not contain hardcoded coordinates, palettes, target sequences, low-level pixel algorithms, or their own search implementations. Otherwise the “tool completeness” test becomes another solver portfolio under a different directory name.

## TR87 and the banked walls

Build the pure rewrite kernel in R56; do not defer it until the rest of 25/25.

A namespace-safe API would look more like:

```python
derive_rewrites(
    source_tokens,
    rules,
    max_depth,
    strategy="parallel",  # or leftmost, all_matches
) -> [{"result": ..., "proof": ...}]
```

The tool receives explicit tokens, rules, and derivation semantics. It does not know about TR87, bars, dials, levels, or actions. It should return derivations and proof traces.

Then keep these out of the namespace:

- TR87 rule-table extraction assumptions;
- interpretation of the upper panel as LHS/RHS;
- decoding its per-level mode;
- dial-state calibration;
- cursor movement and dial execution.

Those belong initially in a quarantined `script25` adapter. Later the LLM can reconstruct them using generic symbol extraction, grouping, motion tracking, and cycle planning.

For the other walls:

- **BP35:** build learned object dynamics and configuration-space planning, not a gravity-platformer solver.
- **DC22:** build transparent state canonicalization and action-conditioned change masks, not a button-then-exit policy.
- **G50T:** improve passive action-effect and relation-delta learning, not an explore/interact controller.
- **SC25:** build generic pattern/set constraint and sequence-search kernels; do not expose known spell patterns.
- **CD82/depth:** extract learned overwrite operators; remove fixed launch masks from the reusable layer.

## R56 decision

Name the direction something like **Primitive Firewall and Scripted Composition**.

Its binding objective should be:

> Preserve the public solver card as a quarantined oracle, extract its reusable perception/dynamics/computation kernels, prove those kernels sufficient through thin scripted composition, and improve LLM adoption through declared-intent offloading. Do not spend R56 finishing public semantic controllers.

So: **yes to eventual scripted 25/25 kernel completeness; no to autonomous no-LLM 25/25 as the intermediate optimization target.** The former builds hands. The latter keeps building a second, public-trained brain.
