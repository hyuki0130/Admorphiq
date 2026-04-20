---
type: strategy
name: bfs_state_space
generalizes: yes
implementation: src/admorphiq/planner/bfs_solver.py
dispatched_from: strat_bfs_state_space in agent_ensemble.py
---

# bfs_state_space

> Generic breadth-first search over frame-hashed states. Depends only on observable frame + action response. Generalizes across game versions.

## When to use

- Deterministic transitions (pressed action produces same next-frame given same start-frame)
- Small reachable state set (≤ ~500K states)
- Level-up signal is observable (either via `state` change or `levels_completed` increment)

## Algorithm

1. Hash current frame into a compact key (downsample 64×64 → 16×16 + color palette)
2. Initialize BFS queue with current state
3. For each popped state:
   - Try every `available_action`
   - Observe resulting frame; re-hash
   - If already visited, skip
   - If level_up flagged, record path and return
   - Else enqueue
4. Budget-capped (default 500K expansions, 20K actions)

## Why it generalizes

- Uses only `FrameData.frame`, `FrameData.available_actions`, `FrameData.levels_completed`
- No sprite tag reads, no attribute access on game object
- Works on any game where frame = state

## Games cleared on both v1 and v2

| Game | v1 | v2 |
|------|-----|-----|
| AR25 | 2/8 | 2/8 |
| DC22 | 1/6 | 1/6 |
| M0R0 | 2/6 | 2/6 |
| SP80 | 1/6 | 1/6 |

## Limitations

- Slow on games with large state branching factor (e.g. ACTION6 × 4096 coordinates)
- Fails silently when level-up signal isn't coupled to frame state (e.g. TN36 where program is executed asynchronously)

## Related

- [[strategies/frame_only/frame_hashing]]
- [[game_types/movement]]
- Compatible refactor base for [[strategies/brittle/internal_method_call]]
