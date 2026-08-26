---
name: WikiAgent first live-env run (2026-04-21)
description: 40-env Qwen 3 8B WikiAgent bench — 15/40 envs, 36/290 levels (12.41%), classification accuracy 45%
type: project
originSessionId: 96a72d05-e421-4801-9b30-810c293777f0
---
## Headline

Phase 8 Step 3b executed: WikiAgent (Qwen 3 8B + `.wiki/` + probe discovery +
frame-only dispatch) ran end-to-end on all 40 envs served by the ARC Prize API
on 2026-04-21. Result: **15/40 envs cleared, 36/290 levels, classification
accuracy 18/40 = 45%**. Runtime 990s (budget=2000 per strategy, Ollama local).

Compared to same-day ensemble regression (28/40 envs, 54/290 levels = 18.62%),
WikiAgent is ~6 percentage points behind. Expected shape — ensemble tries
~22 strategies per env, WikiAgent tries at most 4 (primary + 3 fallbacks).

## Wins (keep)

- Classification accuracy jumped from the cold-prompt 32/40 → live-env 45/40.
  Live probe signals (per-action pixel diffs, ACTION6 responsive-cell count,
  dominant colors) meaningfully improve the LLM's game_type prediction.
- Title-match rule worked: SU15 → `su15_frame_only`, TN36 → `tn36_frame_only`,
  SB26 → `sb26_sort`. No hallucinated names in the primary slot after the
  whitelist + priority rule was added.
- Easy games fell to generic strategies: FT09 6/6 and CD82 6/6 via
  `click_rare`, SB26 8/8 via `sb26_sort`, TU93 2/9 and AR25 2/8 via
  `bfs_state_space`.

## Losses (know why, don't panic)

- `su15_frame_only` and `tn36_frame_only` scaffolds still return 0 levels.
  Greedy same-color-pair clicks and enumeration-of-bit-subsets aren't enough
  to beat L1 on the current v1 hashes; both need deeper planning.
- Misclassifications: M0R0, CN04, KA59 with `avail=[1..4,6]` often get
  `game_type: click` → `click_rare`. The selector.md rules require
  `avail == [6]` for click, but Qwen still drifts when directional diffs are
  small. Follow-up: tighten the movement rule to "any of 1-4 present →
  never click-only classification".
- RE86 → `bfs_state_space` → 0: state space too large for plain BFS, no
  game-specific frame-only strategy exists.

## Numbers for future reference

- Cold-prompt baseline (2026-04-21 bench_llm.py): classification 32/40 (32%),
  strategy 40/40 (40%).
- Live-env WikiAgent (same day): classification 18/40 (45%), 36 levels
  cleared across 15 envs.
- Delta is the "live-env signal gain" — this is what justifies running the
  agent online vs pre-classifying.

## How to apply

- Treat 45% live-env classification as the **floor** for future runs. Any
  future prompt/wiki change that drops below 45% on the same 40 envs is
  a regression to flag.
- Before investing in more brittle-solver refactors, keep extending the
  `selector.md` dispatch table. The LLM follows it almost mechanically once
  the rule matches — ambiguity is the enemy.
- Expand `default_strategy_registry` as more frame-only strategies land
  (RE86, KA59 next). The LLM picks from the whitelist; a missing strategy
  means the LLM cannot recommend it.
- Do NOT rush to tune Qwen 3 8B via LoRA yet. The gap is mostly strategy
  coverage, not LLM reasoning.

## Artifacts

- `scripts/wiki_agent_results.json` — per-env trace
- `scripts/wiki_agent_run_20260421.log` — full stdout
- `.wiki/wiki/lessons/api_hash_rotation_20260421.md` — why the ensemble
  baseline dropped from 27.34% → 18.62% same-day
