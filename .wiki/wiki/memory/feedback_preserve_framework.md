---
name: Preserve the Framework — Don't Rewrite to Match Local Constraints
description: When a test/framework is portable by design, do not fold local-environment coupling into it; build a separate driver instead
type: feedback
originSessionId: 96a72d05-e421-4801-9b30-810c293777f0
---
## Rule

When a framework is intentionally portable (scripts/bench_llm.py, src/admorphiq/llm/*), never rewrite its core interface to include local-environment coupling (live `Arcade` handles, hardware-specific paths, dev-only fixtures). If a richer scenario is needed, build a **separate driver** that composes the framework; keep the framework clean.

## Why

- The benchmark / registry was designed to run anywhere: Kaggle notebook, Colab, remote server, CI. Folding in `arc_agi.Arcade` or `arcengine.GameAction` ties it to the dev box.
- Rewrites lose history: commit messages get muddied ("fix benchmark" vs "add deployment-driver"), reviewers can't tell what changed.
- User on 2026-04-21 pushed back: *"벤치마크도 나중에 어디서든 할 수 있잖아! 더 나은 환경 어디서든..."* — the framework must remain portable so it can be rerun later in richer hardware without patching first.

## How to apply

When tempted to "enrich" a framework function with local observation data:
1. Stop. Ask: would a Kaggle notebook still be able to run this function as-is?
2. If no → the right place is a new driver script, e.g. `scripts/bench_llm_with_live_env.py`, which imports the framework and feeds it a richer prompt generator.
3. Preserve the existing portable signatures. Accept that the cold-prompt baseline the framework produces is the useful, comparable number across environments.
4. Document the separation explicitly: "this script is a cold-prompt baseline; see X for live-env driver".

## What NOT to do

- Change `PROMPT_TEMPLATE` to require live env observations.
- Add `Arcade` instantiation inside `run_candidate`.
- Make `load_wiki_context()` depend on reset-and-probe results.
- Mix framework identity (clean, portable) with driver identity (env-coupled).

## Evidence

- 2026-04-21 Qwen 3 8B bench results (32%/40% cold-prompt baseline) are directly comparable across machines because the framework is pure. If it had embedded `Arcade.make(...)`, comparing local vs Kaggle numbers would require additional assumptions.
