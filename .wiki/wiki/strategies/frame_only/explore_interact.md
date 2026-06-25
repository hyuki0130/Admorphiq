---
type: strategy
name: explore_interact
generalizes: yes
implementation: src/admorphiq/agent_ensemble.py
dispatched_from: strat_explore_and_interact in agent_ensemble.py
---

# explore_interact

> Explore the map in expanding circles, click rare-color objects in newly-seen frames, and memoize which clicks caused change so they can be replayed after a game-over. Combines movement with interaction — a generic probe for hybrid games.

## Applies When

- A [[../../game_types/hybrid]] game: both directional movement and `ACTION6` clicking matter, and the mechanic is not obvious from discovery alone.
- The agent must move to reveal new state and interact with objects it finds.
- `available_actions` includes at least one directional action (clicking is optional but used when `ACTION6` is present).

## Algorithm

(from `strat_explore_and_interact` in `src/admorphiq/agent_ensemble.py`)

1. Reset env, hash the start frame.
2. Build `dir_actions = avail \ {6, 7, 8}`; note whether `6 ∈ avail` (`has_click`).
3. Explore in expanding circles: for `radius` 1..19, for each direction, move `radius` steps in that direction.
4. After each move burst, if the current frame hash is new and clicking is available, click the centroids of the top-3 rare colors (`rare_colors(frame, max_count=200)`).
5. If a click produced a frame change (`frame_diff > 0`), append `(cx, cy, color)` to `interaction_success`.
6. On `GAME_OVER`, reset and replay the memoized successful clicks before continuing.
7. On `levels_completed` increase, record `name = "explore_interact"` (or `explore_click_c{color}`). Budget-capped (default 800).

## Why It Generalizes

- Uses only `FrameData.frame`, `available_actions`, `state`, `levels_completed`, and frame hashing/diff.
- No sprite tags or attribute reads. Rare-color centroids and frame-diff feedback are computed at runtime, so behavior transfers across version hashes.

## Games Cleared

| Game | v1 | v2 |
|------|-----|-----|
| [[../../games/G50T]] | 1/7 | n/a |

## Observable Signature

The plan is the right pick when at DiscoveryReport time:

- `avail` mixes directional actions and `ACTION6` (hybrid signature).
- The discovery probes are ambiguous — neither pure movement nor pure click clearly dominates.
- New frame states appear as the player moves (exploration reveals more of the map).

## Falsification Signature

The plan has failed AND should be swapped when after execution it returns 0 levels AND:

- The frame hash never changed during exploration (no new states surfaced) — movement is inert.
- No click ever produced a frame change (`interaction_success` empty) — objects are not interactive.
- Budget exhausted at the expanding-circle stage without reaching new regions — the map is larger than the radius-19 sweep covers.

## Tunable Parameters

- `budget`: default 800, range 300-3000. Effect: more exploration/interaction cycles.
- max radius: 19 (`range(1, 20)`). Effect: larger sweep for bigger maps at higher action cost.
- rare-color click count: top-3 (`rc[:3]`), `max_count=200`. Effect: more/fewer candidate clicks per new frame.

## Next-Best

When the falsification signature triggers, try (in priority order):

- [[bfs_state_space]] — when movement is meaningful and a systematic state search beats heuristic exploration.
- [[click_rare]] — when clicking dominates and movement is incidental.
- [[inferential_agent]] — when the game class is genuinely unknown and a probe-then-decide pipeline is warranted.

## Related

- [[../../game_types/hybrid]]
- [[../../games/G50T]]
- [[click_rare]] — shares the rare-color centroid interaction primitive

## Sources

- `src/admorphiq/agent_ensemble.py` — `strat_explore_and_interact` implementation (registry name `explore_interact`)
- 2026-04-20 regression: G50T 1/7 via this strategy
