---
type: concept
instantiating_games: [TR87, LS20]
detection_frame_only: yes
---

# Rotation State

> Some games expose piece orientation (0°, 90°, 180°, 270°) as the discrete state variable. An action rotates the selected piece by one step; the goal is to match a reference orientation configuration.

## Definition

A game uses the rotation-state abstraction if:
- Each piece has a clear "forward" asymmetry (L-shape, arrow, colored corner)
- An action (often ACTION1/2) rotates the selected piece by one quarter turn
- Another action (often ACTION3/4 or click) changes which piece is selected
- The level goal is a specific orientation per piece

## Detection heuristics (frame-only)

1. Probe ACTION1 with a piece selected — observe whether the piece's pixel pattern rotates 90° while staying in place.
2. If yes, rotation action confirmed.
3. Probe ACTION3 — observe whether a highlight/cursor moves to the next piece.
4. Identify the reference pattern by finding a persistent region that doesn't respond to any rotation action.

## Instantiating games

| Game | Role | Notes |
|------|------|-------|
| [[../games/TR87]] | canonical rotation | ACTION1/2 rotate, ACTION3/4 select |
| [[../games/LS20]] | combined rotation + matching | each cell has color + shape + rotation |

## Key abstractions

- **Piece** — a rotatable sprite with orientation attribute 0–3
- **Reference** — target orientation pattern visible in the frame
- **Selection cursor** — which piece is currently active

## Solver pattern

For each piece:
1. Read current orientation (compare pixel pattern to canonical orientations)
2. Read target orientation from reference
3. Compute minimum rotation count (0 / 1 / 2 / -1 == 3)
4. Apply rotations; advance selection; repeat

If rotation action costs a step and selection advance costs a step, the plan is a straightforward integer sum; no search needed.

## Related concepts

- [[sprite_cluster]]
- [[frame_hashing]]

## Related games

- [[../games/TR87]]
- [[../games/LS20]]

## Sources

- `src/admorphiq/agent_ensemble.py` — `strat_tr87_rotation`, `strat_ls20_grid`
