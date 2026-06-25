---
type: game_type
examples: [AR25, DC22, M0R0, SP80, LF52, BP35]
refactor_status: frame_only_works
---

# Movement Game

> Player navigates a 2D grid; actions map to directions; walls block; goal reached by path. Most generalizable game type — frame-only BFS suffices for many.

## Identifying features

- `available_actions` includes a subset of `{ACTION1, ACTION2, ACTION3, ACTION4}` for directions
- ACTION6 may or may not be used (sometimes for teleports/clicks)
- Frame has a **mover sprite** — a connected cluster of pixels that shifts position between frames in response to directional actions
- Deterministic: same action from same frame → same next frame

## Discovery protocol

1. Press each direction once; observe which sprite moved
2. Build direction → action mapping by motion vector
3. Treat all non-moving, non-background pixels as walls
4. Treat goal signal as frame change that triggers `levels_completed` increment

## Canonical strategy

[[strategies/frame_only/bfs_state_space]] — works out of the box for clean movement games.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[games/AR25]] | 2/8 | 2/8 | bfs_state_space ✅ |
| DC22 | 1/6 | 1/6 | bfs_state_space ✅ |
| M0R0 | 2/6 | 2/6 | bfs_state_space ✅ |
| SP80 | 1/6 | 1/6 | bfs_state_space ✅ |
| [[games/TU93]] | 2/9 | 2/9 | tu93_maze (brittle — refactor target) |
| LF52 | 0/10 | n/a | currently failing (regression to investigate) |
| BP35 | 1/9 | n/a | platformer variant (gravity) |

## Edge cases

- **Gravity** (BP35): actions trigger physics, not direct movement → BFS state branching explodes; needs separate [[game_types/platformer]] handling
- **Push blocks** (KA59): movement pushes sprites → [[game_types/sokoban]]
- **Large reachable space**: BFS cap blows out; consider IDA* or heuristic pruning

## Related

- [[strategies/frame_only/bfs_state_space]]
- [[../concepts/frame_hashing]]
