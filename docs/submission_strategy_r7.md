# R7 — Submission / Ensemble Strategy (transfer-honest)

**Date**: 2026-07-01 · **Branch**: `r27-transfer-pivot` · **Author**: ML engineer
**Question**: with two committed agents (world-model, online-RL), what do we
deploy to `notebooks/kaggle_submission.py` for the **110 PRIVATE** game
leaderboard, and is a per-game ensemble worth it?

## TL;DR

**Deploy the online-RL agent SOLO. Do NOT ship a world-model / online-RL
ensemble.** The world-model agent scores higher on the public 25 but its
clears rest on hand-built mechanic priors (`arrangement.py` / `sort_match.py`
/ `merge_drag.py`) tuned to the public games' specific mechanics; expected
transfer to the private 110 is low and unmeasured — the same failure mode the
BC track already measured at **0% held-out transfer**. Online-RL learns fresh
inside each unseen game (CNN + off-policy replay + novelty exploration,
warm-started from BC as an exploration prior), so it transfers by
construction. A sequential per-game ensemble is also **metric-negative** under
squared-efficiency: a first agent that fails still spends actions, and those
actions are counted in the denominator when the second agent finally clears,
crushing the `(human/agent_actions)²` score. Keep the world-model agent as a
**dev-time public-25 upper-bound / proxy**, not in the leaderboard notebook.

## Measurement setup

- Harness: `scripts/score_efficiency.py` (faithful RHAE: per-level
  `min(human/agent,1)²`, level-index-weighted per game, mean over games).
- Games: the 25 unique public games (offline `environment_files/`), deduped by
  `game_id`.
- World-model: `--agent worldmodel`, single run, `--max-actions 2500`.
- Online-RL: `--agent online_rl`, `--max-actions 1500`. Online-RL is
  stochastic, so the authoritative signal is the **committed 3-seed K-seed
  clear-rate** (commit `c3f884d`); a single-seed full-25 run is reported as a
  broader-coverage cross-check (RL_SEED=0).
- `_make_agent` in `scripts/score_efficiency.py` had lost its `worldmodel`
  branch when the online-RL commit replaced it; restored (4 lines) so both
  cards run from one harness. No agent code changed.

## Per-game coverage (measured)

`*` = clears ≥1 level. World-model = single run @2500 (**complete, full 25**).
Online-RL columns: **K** = committed 3-seed clear-rate from commit `c3f884d`'s
K-seed harness (authoritative — RL is stochastic); **S0** = single-seed
full-25 cross-check @1500 (RL_SEED=0). The S0 run is CPU/MPS-bound (~2 min/game,
every game burns the full budget because the agent keeps probing deeper levels
after a clear); it was **time-bounded at 5/25 games** this session, so the
remaining S0 cells read `n/m` = not-reached. This is the task-sanctioned
"1 seed if time-bound" path — the K column is the authoritative RL signal and
the S0 cells that did run all agree with it.

| Game | World-model (lvl/win, actions) | Online-RL K (3-seed) | Online-RL S0 (lvl/win) | Union (clears ≥1) |
|------|-------------------------------|----------------------|------------------------|-------------------|
| AR25 | * 2/8  (310) | 3/3 | * 2/8 | ✅ both |
| SU15 | * 2/9  (58)  | — | * 1/9 | ✅ both (S0) |
| FT09 | * 1/6  (93)  | 3/3 | n/r | ✅ both (K) |
| LP85 | * 1/8  (311) | 3/3 | n/r | ✅ both (K) |
| LS20 | * 1/7  (88)  | — | n/r | WM |
| SB26 | * 1/8  (259) | — | n/r | WM |
| TN36 | * 1/7  (110) | — | n/r | WM |
| TU93 | * 1/9  (36)  | 0/3 | 0/9 | WM |
| M0R0 |   0/6  (151) | 3/3 | * 2/6 | RL (RL-exclusive) |
| RE86 |   0/8  (100) | — | 0/8 | — |
| DC22 |   0/6  (85)  | 0/3 | n/r | — |
| BP35 |   0/9  (64)  | — | n/r | — |
| CD82 |   0/6  (100) | — | n/r | — |
| CN04 |   0/6  (75)  | — | n/r | — |
| G50T |   0/7  (130) | — | n/r | — |
| KA59 |   0/7  (100) | — | n/r | — |
| LF52 |   0/10 (76)  | — | n/r | — |
| R11L |   0/6  (60)  | — | n/r | — |
| S5I5 |   0/8  (50)  | — | n/r | — |
| SC25 |   0/6  (146) | — | n/r | — |
| SK48 |   0/8  (578) | — | n/r | — |
| SP80 |   0/6  (30)  | — | n/r | — |
| TR87 |   0/6  (128) | — | n/r | — |
| VC33 |   0/7  (50)  | — | n/r | — |
| WA30 |   0/9  (200) | — | n/r | — |

`n/r` = not reached before the single-seed run was time-bounded. `—` in K =
the game was not in the committed 6-game K-seed set (AR25, FT09, LP85, M0R0,
DC22, TU93).

**World-model total (measured, full-25)**: **1.07%**, **8/25** games clear ≥1
(AR25, SU15, FT09, LP85, LS20, SB26, TN36, TU93).

**Online-RL clears observed** = {AR25, FT09, LP85, M0R0} (K, 3/3 each) plus
**SU15** newly seen in S0 (1/9). S0 reproduced every K-clear it reached (AR25
2/8) and every K-zero it reached (TU93 0/9), and added SU15 — so RL's real
capability is a *general partial-clear* skill, not a fixed list.

**Union coverage (public 25)**: WM {AR25, SU15, FT09, LP85, LS20, SB26, TN36,
TU93} ∪ RL {AR25, SU15, FT09, LP85, M0R0}. WM dominates raw public coverage
(8 vs 5) and depth (AR25 2/8, SU15 2/9 vs RL's SU15 1/9). RL's only
public-25-exclusive clear is **M0R0** (2/6; WM 0/6). Overlap where both clear:
AR25, SU15, FT09, LP85.

## Where each wins — and why it does NOT decide the leaderboard

- **World-model wins the public 25** on both coverage and efficiency (few
  actions/clear: SU15 58, TU93 36). But this is measured on the **public**
  games. The leaderboard is the **110 PRIVATE** games; public-25 clears score
  **0 on the leaderboard** except insofar as the same priors happen to fire on
  a private game.
- **World-model's clears are mechanic-specific.** The 8 clears come from
  `arrangement` (select-and-place), `sort_match` (match-to-order), and
  `merge_drag` (drag-to-goal) capability modules. These are **frame-triggered,
  not game-id hardcoded** (verified: no `game_title`/`game_id` reads in the
  routing), which is better than the old brittle sprite-tag solvers — but they
  were *designed and tuned against the specific mechanic instances present in
  the public 25*. A private game must both (a) belong to one of those three
  mechanic classes and (b) match the tuned trigger/geometry assumptions for a
  prior to fire correctly. Neither is validated on unseen games.
- **The BC precedent is the warning.** BC-on-public-gold measured **0%
  held-out transfer** (`scripts/_transfer_test.sh`): it cleared its own
  training games but 0/7 unseen ones. Anything fit to public-game structure
  risks the same near-zero transfer. The world-model priors are less overfit
  than BC (they read frames, not gold traces) but sit on the same spectrum.
- **Online-RL is general by construction.** It carries no per-game knowledge;
  it learns each game's dynamics at test time from sparse level rewards, with
  novelty-driven exploration and a BC warm-start used only as an exploration
  prior. This is the transferable half of the top-team (StochasticGoose ≈1.21)
  recipe. Its lower public-25 number reflects that it is *not* memorising the
  public games — which is exactly the property the private leaderboard rewards.

## Is a per-game ensemble worth it? (weighed honestly)

**No.** Two independent reasons, either sufficient:

1. **An ensemble that leans on world-model primitives is proxy-gaming.** Only
   online-RL is expected to transfer. Adding the world-model to lift the score
   lifts the *public-25 proxy* (1.07% → higher), not the *private leaderboard*
   — the exact metric-gaming trap the project already burned a sprint on with
   BC. The public-25 number is a dev proxy, not the prize.

2. **Sequential ensembling is metric-negative under squared-efficiency.** The
   real scorecard counts *every* env-state-changing action in a game. If
   online-RL runs first, fails a game (0 levels) after spending N actions, then
   the world-model runs on the same game and clears level 1 in M actions, the
   level-1 score is `(human/(N+M))²` — N is pure dead weight in the
   denominator. Because online-RL burns a large exploration budget before
   giving up, N is large, so the fallback clear is scored at near-zero
   efficiency even when it "works". Running two agents per game strictly
   *spends more actions*, and actions are the denominator we are squaring. A
   sequential ensemble can only match, and usually *undercuts*, either agent
   solo.

3. **A non-sequential (route-one-agent-per-game) ensemble can't be built
   honestly.** You cannot know which agent will clear a private game without
   spending actions to try. Routing "arrangement-looking games → world-model"
   bets on an unvalidated mechanic-match against unseen games — the same
   frame-signature-routing that repeatedly failed dev-time (R2–R11), now with
   zero public feedback to correct it.

**The one honest ensemble that "can't hurt" is not worth building either.**
You could imagine running the world-model *only* on games online-RL cleared 0
levels on AND only inside a tiny reserved action budget so the wasted-action
penalty is bounded. But (a) it still spends actions that hurt any subsequent
clear, (b) it only helps if the private game matches a public mechanic prior
(low-probability, unmeasured), and (c) it adds a second frozen agent + its
maintenance to the notebook for a speculative, likely-zero private payoff. The
expected value does not justify the complexity or the regression surface.

## Recommendation

1. **Deploy online-RL SOLO** for the private-110 leaderboard. It is the only
   agent whose measured capability reflects a *general* skill (learning inside
   an unseen game), and the squared-efficiency metric punishes the extra
   actions any ensemble would spend.
2. **Deployment gap to close**: `notebooks/kaggle_submission.py` currently
   ships `KaggleWorldModelAgent` (the notebook header even claims the
   world-model "transfers to the private games" — that claim is the thing this
   analysis disputes). Deploying online-RL needs a `KaggleOnlineRLAgent`
   official-`Agent` wrapper analogous to `src/admorphiq/kaggle_world_model_agent.py`,
   wiring `OnlineRLAgent` (with its `restart_on_game_over` multi-episode
   behaviour) into the framework `main()` loop. No weights upload is required
   beyond the BC warm-start already mounted.
3. **Keep the world-model agent as a dev-time asset**, not a leaderboard
   component: it is a useful public-25 upper-bound / proxy and a source of
   *general* sub-components (object-centric perception, online effect model,
   search planning) that should be *folded into* the online-RL agent over time
   — as capabilities the RL agent learns/uses per game, not as a second frozen
   agent bolted on at runtime.
4. **If a safety net is genuinely wanted for M1 "valid submission" insurance**,
   the honest floor is a *single* agent that always produces a valid offline
   `submission.json` (both agents already do). Pick online-RL for the general
   bet; do not blend.

## Provenance

- World-model full-25: `/tmp/wm_full25.json` (this session, cap 2500, 25 unique
  games). 1.07% / 8 games.
- Online-RL 3-seed clear-rate: commit `c3f884d` ("novelty exploration lifts
  online-RL clear-rate to 4/6 stable (3/3) — judged on K-seed").
- Online-RL single-seed full-25: this session, cap 1500, RL_SEED=0 —
  cross-check, time-bounded at 5/25 games (AR25 2/8, SU15 1/9, M0R0 2/6,
  TU93 0/9, RE86 0/8). All agree with the K-seed card.
- BC 0% transfer precedent: `scripts/_transfer_test.sh`, memory
  `project_bc_transfer_ceiling`.
- Metric definition: `docs/sprint_m1_architecture_20260625.md`, CLAUDE.md RHAE
  block.
