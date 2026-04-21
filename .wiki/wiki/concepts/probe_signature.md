---
type: concept
referenced_by: selector, reasoning/frame_to_strategy_chain, reasoning/discovery_phase
---

# Probe Signature

> The observable fingerprint of a game after 5-10 discovery actions.
> The LLM reasons from this signature — never from `game_title` or
> `game_id` — to pick a primary strategy. See
> [[architecture#Wiki-First-Routing-no-Python-strategy-selection]].

## What's in a probe signature

`discover()` (in `src/admorphiq/hypothesis/wiki_agent.py`) performs
a fixed battery of probes and records:

- `probe_diffs[aid]` — pixel count that changed after ACTION`aid`
  (one reset + one action, compared to the opening frame).
- `probe_diffs[-6]` — shorthand for `click_responsive_cells`: of the
  5 sampled ACTION6 coordinates, how many produced a non-zero diff.
- `probe_diffs[6]` — max pixel diff across the 5 sampled click cells.
- `available_actions` — the env-reported subset of `{1..7}`.
- `dir_map` — post-R2, maps movement action ids to cardinal directions
  when a consistent one-cell displacement of a single color was observed.
- `change_topology` — categorical label over `{tiny, local, widespread,
  everything}` describing the scale of change.
- `color_histogram`, `symmetry_score`, `layer_count` — static frame
  stats.

Together these form the signature the LLM dispatches on.

## Key discriminators

### Probe uniformity vs asymmetry (1-4 ratio)

Define

```
move_probes = [probe_diffs[a] for a in [1,2,3,4] if a in avail]
ratio = max(move_probes) / max(1, min(move_probes))
```

- **Uniform** (ratio ≤ 2). All four directions cause similar-size
  changes. Interpretation: a player sprite is moving across the grid
  in each direction, producing a similar-size frame delta.
  Canonical movement game. `bfs_state_space` over reachable cells is
  the right primary.

- **Asymmetric** (ratio ≥ 5). Some directions barely change the frame
  (probe ≈ 1); others overwrite huge regions (probe ≥ 100). Interpretation:
  directional inputs are NOT moving a player — they are triggering
  level-wide transforms (paint reveal, color cycling, toggle cascades).
  `bfs_state_space` is wasted here because the state graph is
  combinatorial in the *transforms*, not in reachable positions.
  `paint_game` or `click_toggle_detect` are usually right.

A ratio between 2 and 5 is ambiguous; widen discovery by running a
second probe pass before committing.

### Click responsiveness (−6 key)

- `click_responsive_cells == 0` → clicking on 5 sampled coords produced
  no frame change. Two interpretations:
  1. Clicks only work on rare targets (FT09 lights-out shape).
  2. ACTION6 is disabled for this level (rare).
  The signature `avail == [6] AND responsive == 0 AND probe6 == 0` is
  the classic `click_rare` primary + `lights_out` / `paint_game` fallbacks.

- `click_responsive_cells ≥ 3` → the game accepts clicks everywhere on
  the grid. Combined with **asymmetric movement probes** (rule 3b),
  this is paint-style: `paint_game` primary.

- `click_responsive_cells` of 1 or 2 — sparse reactive cells. Pattern-
  click games (SB26, LP85 family). `click_rare` or `click_color_order`
  are good primaries; the sort-puzzle fingerprint (rule 7) depends on
  avail shape, not click responsiveness alone.

### Title preference (secondary)

`game_title` is a hint, not a dispatch key. The LLM may read it from
the prompt and consult `games/<TITLE>.md` if present, but the routing
decision must be recoverable from the probe signature alone. The Kaggle
private test set supplies obfuscated or rotated titles — a rule that
says "pick sb26_sort when title is SB26" breaks the moment the title
changes. A rule that says "pick sb26_sort when avail ⊇ {5,6} and no
1-4 and probe 5 is small" survives rotation.

## Worked reading

**AR25** (movement-hybrid, rule 3a):

```
avail = [1, 2, 3, 4, 5, 6, 7]
probe_diffs = {1: 109, 2: 109, 3: 109, 4: 109, 6: 0, -6: 0}
```

1-4 ratio = 109/109 = 1 → uniform. Click responsive = 0/5 → dead click.
Movement-hybrid: player sprite moves evenly across a grid; click isn't
used. Primary `bfs_state_space`.

**CD82** (paint-hybrid, rule 3b):

```
avail = [1, 2, 3, 4, 5, 6]
probe_diffs = {1: 1, 2: 1, 3: 201, 4: 201, 6: 1, -6: 5}
```

1-4 ratio = 201/1 = 201 → extremely asymmetric. Click responsive = 5/5
→ every click cell reacts. Movement inputs 3 and 4 overwrite large
regions (level-wide paint). Rule 3b: primary `paint_game`.

**FT09** (click-rare, rule 4):

```
avail = [6]
probe_diffs = {6: 0, -6: 0}
```

Click-only, zero response on every sampled cell → rare click targets.
Primary `click_rare`, fallback `lights_out` / `paint_game` to handle
lights-out-style or paint-reveal sub-mechanics.

## Falsification

This concept loses validity if a future bench on a model at the 20B+
scale shows the LLM picking correctly without any signature heuristic
— i.e., pure code-reading of `games/*.md` plus the raw probe dict is
enough. As of 2026-04-21, 8B-class models need the explicit
discriminators above to route AR25 vs CD82 correctly.

## Related

- [[selector]] — the dispatch table this glossary supports
- [[reasoning/discovery_phase]] — how probes are produced
- [[reasoning/frame_to_strategy_chain]] — worked examples
- [[lessons/api_hash_rotation_20260421]] — why title-based rules are
  forbidden on Kaggle

## Sources

- `src/admorphiq/hypothesis/wiki_agent.py::discover`, `::_derive_*`
- `scripts/wiki_agent_results_round3.json` — AR25 / CD82 / FT09
  signatures above are raw excerpts
