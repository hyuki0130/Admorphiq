---
type: game_type
examples: [TN36]
refactor_status: brittle_only
---

# Programming Puzzle

> Player encodes a short program via clickable state cells, triggers execution via a "play" button, observes a player/cursor entity execute the program. Goal: reach target cell.

## Identifying features

- `available_actions` typically includes `ACTION6` and usually `RESET`
- Grid layout with **two visually distinct regions**:
  1. "code region" — row/column of cells that toggle color on click (bits/opcodes)
  2. "world region" — player + walls + goal
- Pressing play button in code region triggers animated movement in world region
- Level-up requires player reaching goal

## Discovery protocol

1. Click each candidate cell (random sampling in first 10 actions)
2. Classify cells into:
   - **Bit cells**: toggle persistent state, don't animate player
   - **Play button**: animates player (observable via frame motion magnitude)
   - **World cells**: static or destructive (kill zones cause reset)
3. Map bit combinations → player motion vector (probe with single-bit-set programs)
4. Plan bit pattern to reach goal via BFS on possible movement opcodes

## Related strategies

- [[../concepts/bit_encoding]] — the bit-panel puzzle abstraction (frame-only refactor target)
- [[../strategies/brittle/internal_method_call]] (current TN36 implementation)

## Related games

- [[games/TN36]] — canonical example, 7/7 on v1 via brittle internal call

## Heuristics

- Execution is **asynchronous**: play click returns before motion completes → must wait frames, not rely on immediate state change
- Multi-run programs (checkpoints) suggested when goal requires >N opcodes in one run
