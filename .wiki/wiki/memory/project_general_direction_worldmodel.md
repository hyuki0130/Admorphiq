---
name: project_general_direction_worldmodel
description: "The general path to private-game score = object-centric perception + online (test-time) world model + search planning + RL; BC is a warm-start, not the destination"
metadata: 
  node_type: memory
  type: project
  originSessionId: c7e91ecf-c8c0-4c3c-bd62-4722ff123df5
---

R27+ direction (decided 2026-06-29 with the user). The lever for the 110 PRIVATE
games is an agent that does its learning **at test time, per game**, not from
public gold:

1. **Perception → objects** — segment frames into entities/color regions
   (game-agnostic; `FrameAnalyzer` exists). No game-id / sprite-tag reads.
2. **Online world model** — from the agent's own probes, learn "action X changes
   object Y" *per game* in the first tens of actions (`src/admorphiq/world_model/`).
   This is what transfers — it is rebuilt fresh per game.
3. **Goal inference** — detect the level-complete condition via the model + a
   small reasoning step (heuristic, or the offline LLM at discovery).
4. **Search-based planning** — BFS/MCTS in the learned model → short action
   sequences (the squared-efficiency metric rewards efficiency).
5. **RL on top** — online policy improvement per game; **BC = warm-start prior**
   biasing exploration, not the final policy.

**Why:** the top team (StochasticGoose, ≈1.21) is CNN+RL, but the load-bearing
half is online RL that adapts per game at TEST time — not BC on a public set.
We initially copied the transferable-weak half (see [[project_bc_transfer_ceiling]]).
This direction matches Chollet's framing (efficiency of skill acquisition in
novel situations).

**How to apply:** two-layer plan — ship BC v6 for M1 (safety net), build this
general agent as the R27+ climb toward M2/final/the $350K bonus. Don't
blind-benchmark the top team; copy the *online-learning* idea, not the
public-gold BC. RL redesign tracked in [[feedback_rl_not_abandoned]]. Doc:
docs/sprint_m1_architecture_20260625.md.
