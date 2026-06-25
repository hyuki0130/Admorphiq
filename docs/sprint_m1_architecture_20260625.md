# ARC-AGI-3 Milestone-1 Sprint — Architecture Decision & Plan (2026-06-25)

Source of truth for the 5-day sprint to June 30. Supersedes the round-1..17
"LLM-routes-among-strategies" framing where it conflicts with the metric below.

## 1. The metric is the whole game (verified from Kaggle Data tab)

Per level: `s = min(human_actions / agent_actions, 1.0)`, then **squared**.
Per game: level-index-weighted mean of level scores. Total: mean over all
games (eval = **110 private unseen games**, 0–100%).

Consequences (load-bearing):

- **Brute force scores ≈ 0 even when it "wins".** A frame-hash BFS that
  clears a level in 374 actions vs a human's ~15 gets `min(15/374)² ≈ 0.0016`.
  Our `bfs_state_space` "clears" are worth almost nothing under this metric.
- **Cheap partial progress across many games beats deep slow solves on few.**
  Real leaderboard: Random agent = **0.18**, stochastic-explore sample =
  **0.25**, top (Tufa/Dries Smit) = **1.21**, gold cutoff ≈ 0.60.
- Therefore the objective is: **on every one of the 110 games, make
  efficient progress; never waste actions.** Efficiency (actions-to-human-
  ratio, squared) dominates raw completion.

## 2. Verified runtime contract

- Official agent base: `agents.agent.Agent` (ARC-AGI-3-Agents repo, provided
  on Kaggle Data tab + as `arc_agi_3_wheels/`). Implement:
  - `is_done(frames, latest_frame) -> bool`
  - `choose_action(frames, latest_frame) -> GameAction`
  - `choose_action_with_data(frames, latest_frame) -> (GameAction, data|None)`
    where `data={"x":int,"y":int}` for ACTION6.
- `GameAction` (from `arcengine`): `.RESET`, `.from_id(1..7)`,
  `.set_data({"x","y"})` for ACTION6.
- `FrameData`: `.frame` = `(num_layers, 64, 64)` int8, cell values 0–15;
  `.state` ∈ {NOT_FINISHED, WIN, GAME_OVER}; `.available_actions`;
  `.levels_completed`.
- Offline execution: `arc_agi/local_wrapper.py` runs games from local files
  (no internet) — this is the Kaggle path. `remote_wrapper.py` is the
  networked API we use in local dev (anonymous key). Eval injects the 110
  private games through the same local interface.
- Hardware: g4-standard-48 = RTX PRO 6000 Blackwell **96GB VRAM**, 180GB RAM,
  **9h total across all 110 games ≈ 5 min/game**. Offline; open-weight LLM OK.

## 3. Architecture decision

**Rejected**: "LLM routes among ~14 brute-force strategies." It optimizes
*completion*, not *efficiency*, so it scores ~0 on the real metric, and it is
tuned to the 25 preview games (zero transfer to 110 unseen).

**Adopted — a single general agent, efficiency-first**, 4 stages run per game
within the ~5-min budget:

1. **Cheap discovery (≤ ~human-scale actions).** Probe each available action
   once or twice; diff frames to learn *action semantics* (which action moves
   what / toggles what / clicks where). Connected-components on the frame to
   extract objects/entities. Budget-bounded — discovery itself must be cheap
   because wasted probe actions also hurt the efficiency ratio.
2. **World model (per-game, learned online).** From the probe diffs, build a
   compact transition model over an **abstract state** (entity positions /
   grid features), NOT raw 64×64 frames. This is what makes efficient
   planning possible.
3. **Goal inference.** Infer the win condition from observed transitions +
   (optionally) an **offline LLM hypothesis** called ONCE at discovery time
   (not per action) — "given these objects and these action effects, what is
   the likely goal?". LLM output is a hypothesis to verify, never a per-step
   oracle (9h/110-game budget forbids per-action LLM calls).
4. **Efficient planning.** A*/greedy/heuristic search in the *abstract* state
   space toward the inferred goal, emitting the shortest action sequence.
   Target: action counts close to human → high squared efficiency. Replan on
   surprise (model mismatch).

LLM role (re-scoped): **rule/goal hypothesis from few frames + abstraction
proposals at discovery time**, a handful of calls per game — not routing,
not per-action. Model fits 96GB easily (14B now; 26B MoE candidate); the
real budget constraint is the 9h wall-clock, so LLM calls stay few + short.

## 4. Reusable vs replace (our existing code)

- **Reuse**: connected-components / entity extraction + probe/observation
  phase from `strategies/inferential.py`; `planner/bfs_solver.py` as a
  *bounded* planner (cap depth hard so it never burns the efficiency ratio);
  the official adapter shape in `adapter.py`.
- **Replace / fix**: `adapter.py` wires the weak CNN `AdmorphiqAgent` — rewire
  to the general agent. Demote raw-frame BFS (`bfs_state_space`) from a
  primary solver to a last-resort fallback (it tanks efficiency).
- **De-prioritize**: the whole LLM-whitelist-routing machinery (rounds
  R7–R16) — keep the wiki/LLM for goal hypothesis, drop strategy-routing as
  the spine.

## 5. Five-day build order (always submission-ready after step B)

- **A. Submission notebook skeleton** (always-ready): install arc_agi from
  local wheels (offline), wrap our agent via `agents.agent.Agent`, run the
  framework's runner/Swarm over all games → auto submission. Validate it
  produces a file with a trivial agent first.
- **B. Wire the real agent + a cheap-explore floor.** Even a disciplined
  cheap-explore agent should beat the 0.18 random / 0.25 sample. SUBMIT to
  get on the board + milestone eligibility (open-source the notebook).
- **C. General agent core** (stages 1–2 + bounded planner). Validate on the
  25 sample games with the **real efficiency-squared score** (build that
  harness; needs a human-action baseline — use `baseline_actions` from
  `EnvironmentInfo` if present, else a proxy).
- **D. Offline LLM backend** (llama-cpp-python + GGUF reusing Ollama blobs, or
  transformers; env-driven dev=Ollama / Kaggle=offline) + goal-hypothesis at
  discovery. Re-submit.
- **E. Iterate rounds** continuously: measure efficiency score on samples,
  improve planning/discovery, re-submit daily (1/day limit).

## 6. Highest-leverage thing to get right

**Efficiency, not completion.** Every design choice is judged by "does this
reduce actions-to-human-ratio on unseen games." A bounded, replanning,
abstract-state planner that solves a few games near-human-efficiently +
cheap non-wasteful exploration everywhere else beats any brute-force solver.

## 7. Open item

Official ARC-AGI-3-Agents runner/Swarm entry-point + exact Kaggle notebook
cells — pull from the provided `ARC-AGI-3-Agents/` (Kaggle Data tab) or the
GitHub repo; needed for step A. Everything else above is verified.
