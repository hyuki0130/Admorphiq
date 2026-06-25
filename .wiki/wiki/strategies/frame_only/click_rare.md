---
type: strategy
name: click_rare
generalizes: yes
implementation: src/admorphiq/agent_ensemble.py
dispatched_from: strat_click_rare in agent_ensemble.py
---

# click_rare

> Click every pixel of each rare (non-background, low-count) color in ascending count order until a click advances the level. Reads only `FrameData.frame` pixels — generalizes across game versions.

## Applies When

- `ACTION6(x, y)` is in `available_actions` and is the progression action.
- The winning interaction is a single click on a small, distinctly-colored region (a button, gem, or marker).
- Directional actions have no or minimal effect, so the level advances by clicking, not moving.

This is the executable side of the [[../../concepts/rare_color_click]] concept.

## Algorithm

(from `strat_click_rare` in `src/admorphiq/agent_ensemble.py`)

1. Reset env, snapshot `frame`.
2. Histogram the frame: `np.unique(frame, return_counts=True)`.
3. Sort `(count, color)` ascending — rarest non-zero colors first.
4. Skip `color == 0` (background) and any color with `count > 500` (too common to be a marker).
5. For each rare color, iterate over every pixel position (`np.argwhere(frame == color)`) and `ACTION6(cx, cy)` on it.
6. On `levels_completed` increase, record the winning color/coord into `name`.
7. On `GAME_OVER`, reset and re-read the frame. On `WIN`, return immediately.
8. Budget-capped (default 300 actions).

## Why It Generalizes

- Uses only `FrameData.frame`, `FrameData.state`, `FrameData.levels_completed`.
- No sprite tag reads, no game-object attribute access.
- The "rare color" heuristic is computed per-frame at runtime, so it transfers to re-obfuscated version hashes (see [[../../lessons/v2_hash_obfuscation]]).

## Games Cleared

| Game | v1 | v2 |
|------|-----|-----|
| [[../../games/LP85]] | 1/8 | n/a |
| [[../../games/VC33]] | 1/7 | 1/7 |

## Observable Signature

The plan is the right pick when at DiscoveryReport time:

- `ACTION6` is in `avail` and directional probes (1-4) are dead or near-dead (`change_topology == inert` for moves).
- The frame has one or more small clusters of a distinctly rare color (count 1-20) on an otherwise uniform background.
- Click-responsiveness is sparse (1-3 high-diff cells), not broadly responsive.

## Falsification Signature

The plan has failed AND should be swapped when after execution it returns 0 levels AND:

- Every rare-color pixel was clicked (`used` reached `budget`) with no `levels_completed` increase — the winning interaction is not a single rare-color click.
- A `GAME_OVER` is triggered on most clicks — clicking is harmful here (e.g. a movement/avoidance game misclassified).
- Click responsiveness was broad (many cells diff > 100) — the game is paint/toggle, not single-marker click.

## Tunable Parameters

- `budget`: default 300, range 100-4096. Effect: more pixels probed at higher action cost.
- count ceiling (`cnt > 500` skip): default 500. Effect: lower it to skip common colors faster; raise to include larger clusters as candidates.
- Click order: rarest color first. Effect: prioritises the most marker-like clusters; reorder toward larger clusters if the rarest are decorative.

## Next-Best

When the falsification signature triggers, try (in priority order):

- [[explore_interact]] — when directional actions DO produce motion and clicking alone is not enough (move-then-click composition).
- [[seq_search]] — when no single click advances and the trigger may be an action sequence rather than a coordinate.
- [[bfs_state_space]] — when the env is actually movement-driven and click responsiveness was a decoration.

## Related

- [[../../concepts/rare_color_click]] — the concept this strategy instantiates
- [[../../game_types/click]]
- [[../../games/LP85]], [[../../games/VC33]]

## Sources

- `src/admorphiq/agent_ensemble.py` — `strat_click_rare` implementation
- 2026-04-20 regression: LP85 and VC33 cleared via this strategy
