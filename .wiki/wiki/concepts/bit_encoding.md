---
type: concept
instantiating_games: [TN36]
detection_frame_only: yes
---

# Bit Encoding (Programming-Puzzle Opcode)

> A row of clickable cells encodes a binary number (or opcode) by their toggle state. A separate "play" button executes the encoded program, usually moving a cursor/player on another part of the frame.

## Definition

- Programming-puzzle games have two frame regions:
  - **Code region**: a row/column of N cells, each independently toggleable by ACTION6
  - **World region**: a player/cursor navigates a grid

- Each bit is worth `2^i` or mapped to a specific opcode (e.g. "move right", "move down").
- The code value = sum of active-bit values.
- Pressing the play button runs the program once: the player executes the corresponding movement sequence.

## Detection heuristics (frame-only)

1. Look for a row of equal-sized cells aligned on one axis, separated by uniform spacing → candidate **code region**.
2. Find a distinct clickable cell near (but not in) the code row → candidate **play button**.
3. Probe a single bit: click one cell, observe frame diff — only that cell changes. The cell is "live".
4. Click play — if the player moves by a certain vector, the code is active. Try single-bit combinations to discover the bit-to-direction map.

## Instantiating games

| Game | Role | Notes |
|------|------|-------|
| [[../games/TN36]] | canonical | 7 levels, bit-encoded movement programs, multi-run with checkpoints on late levels |

## Key abstractions

- **Bit cell** — clickable, toggles on/off
- **Play button** — triggers program execution
- **Checkpoint** — persistent state that allows multi-run programs (L6/L7 of TN36)
- **Kill zone** — cells that end the level if the player enters

## Solver pattern

1. During discovery: map each bit to its output vector (direction + distance).
2. Plan a path from start to goal using BFS over (player_pos, bit_pattern) combinations.
3. For multi-run levels: pause at checkpoints to reset/flip bits, then continue.

The current `strat_tn36_puzzle` shortcuts this by calling `frame.zpzcmabenn(val)` directly — brittle, fails on v2. See [[../lessons/v2_hash_obfuscation]].

## Frame-only refactor plan

Phase 8 Step 2a: replace the `zpzcmabenn` call with:
- Bit detection from frame via color clustering of the code region
- Bit-to-direction mapping learned during discovery
- Plan generated via BFS, applied as a sequence of ACTION6 clicks on bit cells + one click on play

## Related concepts

- [[sprite_cluster]]
- [[frame_hashing]]

## Related games

- [[../games/TN36]]

## Sources

- `src/admorphiq/agent_ensemble.py:5956-6043` — `strat_tn36_puzzle`
- TN36 source: `environment_files/tn36/ab4f63cc/tn36.py` (v1)
- Commit `5e8562a` — first introduction of the brittle solver
