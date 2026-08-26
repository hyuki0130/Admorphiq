---
name: Per-Game Mechanic Analysis
description: Detailed analysis of each game's mechanics, what works, what doesn't, and hypotheses for solving
type: project
---

## Graph Agent 결과: 10/25 게임, 6.04% (2026-04-01 업데이트)

### BFS Solver 추가 (NEW)
- TU93: 2/9 levels — BFS game-state solver (L1=18steps, L2=8steps)
- LS20: 1/7 — also solvable by BFS (13 steps)
- BFS works by replaying from RESET, hashing frames, doing BFS on state graph
- Multi-level: chains solutions as prefixes (RESET → L1_solution → L2_BFS)
- Best for movement-only games with ≤4-5 simple actions, no clicks

### 이전 결과: 9/25 게임, 4.95% (2026-04-01)

| Game | Solver | Details |
|------|--------|---------|
| M0R0 | Graph explorer | movement game, graph-only solve |
| CN04 | Graph explorer | sliding puzzle |
| FT09 | Toggle solver | 4 clicks, toggle puzzle |
| LP85 | Graph explorer | static, click game |
| SP80 | Sequence solver | A4,A4,A4,A5 (4 steps) |
| VC33 | Sequence solver | click(60,32) x3 |
| LS20 | Graph explorer | complex |
| CD82 | Sequence solver | A3,A2,A2,A4,A5 (5 steps) |
| TN36 | Toggle solver | 7 clicks, 11 toggle groups |

## 미클리어 16게임 상세 분석

### TU93 (movement, A1-4, 9 levels) — SOURCE CODE ANALYZED, PARTIALLY SOLVED
- Maze navigation puzzle on 3px grid (nodes at every 6px)
- Player tag "albwnmiahg", exits tag "xboyuzuyxv"
- Maze sprite tag "vhlesexlqd", pixel==2 means corridor
- 3-phase step: phase 0 (player move), phase 1 (animate), phase 2 (check win/obstacles)
- Companions (vllvfeggte, zzuxulcort, natiyqayts) move with player
- Step budgets: 20-60 per level
- BFS solver solves L1 (18 steps) and L2 (8 steps)
- L3+ fails: likely deeper solutions or prefix replay too expensive
- Potential improvement: optimize BFS with pruning, or hardcode L3+ from source

### RE86 (movement, A1-5, 8 levels)
- Player: color 0 (1px), shadow: color 9 (56px follows player)
- A1=up(3px), A2=down, A3=left, A4=right
- A5 = FIXED TELEPORT between (36,45) and (21,27) — useless
- Navigate-to-any-color doesn't solve. Not a "reach the goal" game.
- 32K unique states in 50K actions. Likely pattern/arrangement puzzle.

### WA30 (movement, A1-5, 9 levels) — SOURCE CODE ANALYZED
- Sokoban delivery puzzle on 4px grid (16x16)
- Player tag "wbmdvjhthc", items tag "geezpjgiyd"
- A5 = pickup/drop items. Win: all items at target positions (`wyzquhjerd`)
- Has built-in BFS pathfinding. Move budget per level (lose when 0).
- Simple pickup-deliver heuristic failed. Needs proper Sokoban solver.

### TR87 (transform, A1-4, 6 levels) — SOURCE CODE ANALYZED
- Rotation/value matching puzzle
- A1/A2 = cycle values up/down, A3/A4 = select element
- 20+ positions, 20+ values = 20^20 combinations — brute force impossible
- Budget: 128 moves (levels 1-5), 256 (level 6+)
- 39K unique states in 50K actions

### SU15 (click, A6+7, 9 levels) — SOURCE CODE ANALYZED
- Fruit/vacuum puzzle. Click fruits -> vacuum -> match goals
- 15 toggle groups (too many for 2^N brute force)
- "vacuum" -> "win" state transitions
- 47K states in 200K actions but 0 levels

### DC22 (hybrid, A1-4+6, 6 levels)
- Movement + click game. 3 toggle groups but brute force fails.
- Goes GAME_OVER after ~10K actions (move budget)

### SK48, TU93, SB26, BP35, G50T, LF52, SC25, AR25, KA59, R11L, S5I5
- Various types, all resist toggle/sequence/zigzag/random approaches
- Most go GAME_OVER after exhausting move budget

## Toggle Solver Results (all 25 games)
- FT09: 8 groups -> SOLVED (4 clicks)
- TN36: 11 groups -> SOLVED (7 clicks)
- SU15: 15 groups -> too many for brute force
- Others with groups (CN04:2, LP85:2, DC22:3, KA59:2, SB26:4, LF52:6, BP35:8, S5I5:5, R11L:2, VC33:2, CD82:2): brute force fails, not pure toggle puzzles

## Sequence Solver Results (all 25 games, up to 50K combos)
- SP80: A4,A4,A4,A5 -> SOLVED
- VC33: click(60,32) x3 -> SOLVED (needs 4px grid scan, 8px misses it)
- CD82: A3,A2,A2,A4,A5 -> SOLVED
- All others: no short sequence solves

## Key Observations
1. Games with move budgets go GAME_OVER after 5-10K actions
2. Remaining games need source code analysis -> hardcoded solutions
3. Pure exploration (even 200K actions) doesn't solve complex puzzle games
4. Sequence brute-force works for games solvable in <=8 steps from reset
