# ARC-AGI-3 Win-Condition Taxonomy → Primitive Roadmap (2026-06-26)

Derived by reading the 25 PUBLIC game sources (`environment_files/<g>/<hash>/<g>.py`),
which expose each game's real `next_level()` / `lose()` logic. Eval = 110
PRIVATE games, so this is a STRUCTURAL PRIOR (the classes recur), not a
per-game hardcode. It defines the algorithm primitives the LLM selects among
and what the LLM must output to parameterize each.

## Classes (with source evidence)

1. **nav-to-target** — e.g. tu93. `next_level()` when every player sprite
   (`get_sprites_by_tag(player)`) is positioned on an exit sprite, within a
   step budget. Moves are direction/rotation commits gated by a walkable-pixel
   condition; player auto-advances. Detection: a small cluster that translates
   under move actions + a distinct target marker. Primitive: 4-dir discovery +
   grid BFS/A* shortest path to the target. LLM supplies: which cluster is the
   target/exit.

2. **merge / accumulate** — e.g. su15. `next_level()` after a merge/overlap
   condition persists (counter `> N`). 2048-style: same-color clusters combine
   to color+1; secondary entities downgrade. Primitive: click/drag to bring
   same-color pairs together (vacuum/attract radius). LLM supplies: which color
   pairs to merge, target color.

3. **pattern-match** — e.g. cd82 (paint), ft09 (lights/toggle).
   - cd82: `next_level()` when `np.array_equal(regionA.pixels[mask],
     regionB.pixels[mask])` — paint region A to MATCH reference region B
     (mask excludes diagonals). Primitive: detect palette + target region +
     paint actions to copy the reference. LLM supplies: source palette, target
     region, paint plan.
   - ft09: `next_level()` when a board predicate `cgj()` holds (lights-out:
     toggles reach target). Primitive: GF(2) toggle solve (already drafted in
     concepts/gf2_toggle_stencil). LLM supplies: toggle cells / target state.

4. **sort / arrange** — e.g. sb26. `next_level()` after items reach target
   order (timer-gated). Primitive: swap/place items to a target sequence. LLM
   supplies: target order, item↔slot mapping.

(Others to map as needed: rotation-match (tr87), spell/sequence (sc25),
push/sokoban (ka59 — note ka59.py is 41k lines, heavy), platformer (bp35).)

## How the LLM + primitives compose (the agent design)

1. Cheap discovery: probe actions, extract entities (connected components),
   record action→effect. Build a COMPACT SYMBOLIC state (no raw pixels).
2. **LLM call (1-3/game, at discovery)**: classify the win-condition CLASS +
   output the parameters that class's primitive needs (target identity, palette,
   order, toggle cells…). json-schema-constrained.
3. Dispatch the matching EFFICIENT primitive with those params; execute
   closed-loop; replan on surprise. Efficiency is squared in the metric, so
   primitives must approach human action counts.
4. On failure/timeout: deterministic fallback (cheap-explore) so we never score
   below the random floor.

## Build order for the primitives (highest leverage first)

- nav-to-target (most games have a movement core; first real points) — R4-B.
- pattern-match toggle/paint (cd82/ft09 — reuse gf2_toggle_stencil).
- merge (su15).
- sort (sb26), then the long tail.

## Discipline
General detection only — no `game_id`/`game_title` branching. The sources are
ground truth for VALIDATION and for designing detectors; the deployed
detectors must trigger on observable frame/probe signatures so they transfer to
the 110 private games.
