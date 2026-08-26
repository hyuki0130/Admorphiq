---
name: No Python augmentation — wiki is the only lever
description: Do NOT add Python-level post-processing to patch LLM mistakes. Enrich the wiki so the LLM reasons correctly from frame observations alone.
type: feedback
originSessionId: eba5cc76-48c0-4391-bce2-39b48288934e
---
**Rule**: Do not add Python post-processing helpers (`_augment_*`, fallback injection, whitelist-based overrides) to work around LLM mistakes on the bench. The correct fix is always to enrich `.wiki/` so the LLM can reason about the decision from frame observations alone.

**Why**: User explicitly and repeatedly said this, with escalating frustration across rounds 2-3. Three reasons:

1. **Python augmentation is hardcoding in disguise.** `_augment_with_title_match` used `game_title` (unavailable/obfuscated on Kaggle private test set) to inject specific strategy names — pure dead weight for deployment. Rule-3 / rule-4 augmentations stacked game-specific strategies into `fallback_stack` to rescue known-failure envs, which is the same pattern as the analytical solvers (FT09 lights_out, CD82 paint_game) the project has been trying to remove since Phase 6.

2. **Fallback stacking is metric gaming.** Giving the LLM 4 shots per env (primary + 3 fallbacks) lets the bench score go up without the LLM actually understanding the game. It makes R2/R3 look like progress (19→37→47 levels) but none of that transfers to unseen games because the fallback picks came from Python, not Qwen's reasoning.

3. **The architecture is Karpathy LLM-Wiki on purpose.** `.wiki/wiki/architecture.md` says Cognition (LLM) reasons from Memory (wiki) and calls Action (strategies). Python post-processing inserts a fourth layer that short-circuits Cognition. If the LLM picks wrong, the signal is "wiki doesn't explain this case well enough" — not "add a Python branch."

**How to apply**: When the bench trace shows Qwen made a wrong pick, the fix sequence is:

1. Identify the observable signature that distinguishes the correct answer (probe asymmetry, click responsiveness, color histogram, symmetry, etc. — the R2 DiscoveryReport features).
2. Open the relevant `.wiki/wiki/` page (`selector.md`, a `game_types/*.md`, a `reasoning/*.md`, or a `concepts/*.md`).
3. Write the discriminator in prose that ties the observable signature to the right strategy. Include the reasoning chain: "signature X means Y because Z".
4. Re-bench. If Qwen still picks wrong, the wiki is still not clear enough — iterate the wiki, not the code.
5. NEVER add `_augment_*` helpers, NEVER inject strategies into fallback_stack from Python, NEVER use `game_title` as a decision key.

**Exception**: Observable-only decoder constraints (JSON schema enum on strategy names, `uniqueItems`) are fine — those force the LLM output into the valid space without making decisions for it. Python reasoning about which strategy to pick is not fine.

**Rollback debt**: Rounds 2-3 introduced `_augment_with_title_match`, `_augment_click_only_rule4`, `_augment_hybrid_rule3` in `src/admorphiq/hypothesis/wiki_agent.py`. All three are violations of this rule. They must be removed and the equivalent guidance moved into wiki pages so Qwen reaches the same answer via reasoning.
