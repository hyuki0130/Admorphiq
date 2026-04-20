---
type: concept
instantiating_games: [ALL]
detection_frame_only: yes
---

# Frame Hashing

> A compact fingerprint of the current frame used to deduplicate states in BFS/graph search. Enables tractable state-space exploration despite the nominally huge frame space.

## Definition

`frame_hash(frame) -> int or str` is a function that maps a full frame (multi-layer 64×64 int8 grid) to a compact key such that two frames with the same hash represent equivalent game states.

Typical implementation:
1. Downsample each layer to 16×16 (or smaller) by max-pool or majority-vote
2. Concatenate layers
3. `hashlib.md5(bytes).hexdigest()`

## Why it matters

The raw frame space has `16^(64*64*N)` states — intractable. But most of this is irrelevant detail (background decoration, animation frames). Hashing at reduced resolution collapses equivalents:
- Two frames that differ only by idle animation → same hash → not re-expanded
- Two frames differing only in a pixel noise → same hash (if downsampling is coarse enough) → not re-expanded

BFS can then run over the hashed state space, which is typically small (1K–100K states per level).

## Detection heuristics

Not applicable — this is a design primitive, not a game feature to detect.

## Design tradeoffs

| Parameter | Finer | Coarser |
|-----------|-------|---------|
| Downsample size | Distinguishes more states | Merges semantically equivalent states |
| Connectivity | Preserves spatial structure | Reduces state count |
| Layers merged | Captures all info | May conflate distinct concepts |

Rule of thumb: start with 16×16 downsample. If BFS finishes without solving, coarsen to 8×8. If BFS never distinguishes key states, refine.

## Pitfalls

- **Too coarse**: two distinct states hash the same → BFS reports cycle incorrectly → missed solutions
- **Too fine**: state explosion → BFS out of budget
- **Layer ordering**: hashing layers in inconsistent order produces different hashes for identical states; fix an order

## Instantiating games

| Game | Notes |
|------|-------|
| [[../games/AR25]] | BFS over frame-hash reaches 2/8 on both v1 and v2 |
| [[../games/M0R0]] | BFS over frame-hash reaches 2/6 on both v1 and v2 |
| [[../games/DC22]], [[../games/SP80]] | similar |

## Related concepts

- [[sprite_cluster]] — the raw primitive before hashing
- [[../strategies/frame_only/bfs_state_space]] — consumer of frame hashes

## Sources

- `src/admorphiq/planner/bfs_solver.py`
- `src/admorphiq/utils/buffer.py` — MD5 dedup already used in ExperienceBuffer
