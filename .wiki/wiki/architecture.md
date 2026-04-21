---
type: reasoning
input_type: design-doc
output_type: architecture-contract
status: load-bearing
first_written: 2026-04-21
---

# Admorphiq Agent Architecture (Phase 8 Restart)

> Three-layer agent design — Cognition (LLM) / Memory (Wiki) / Action (Strategies) — with explicit dev-time vs Kaggle-time boundaries and a self-improvement loop.

This page is the **binding contract** for every script, module, and wiki page touched under Phase 8. If a change contradicts anything here, either the change is wrong or this page needs an update first — never both silently.

## Why we restarted

The pre-2026-04-21 Phase 8 plan was a **linear pipeline**: Wiki seed → frame-only solvers → LLM inference → cleanup. It assumed a one-shot classify-and-dispatch would be enough. Live-env measurements (`memory/project_wiki_agent_first_run.md`) showed the ceiling of that design: 15/40 envs, 36 levels, classification 45%.

The missing capabilities exposed by that run:

1. The LLM received only 5 frame features (`avail`, `layer_count`, `dominant_colors`, `probe_diffs`, `reset_levels`). Not enough signal to separate movement / sokoban / hybrid cleanly.
2. Only 17 of 74 ensemble strategies were exposed to the LLM. Every non-uniform signature (movement strategies needing `dir_actions`, `player_color`) was invisible. So "movement" games mis-routed to `click_rare`.
3. No feedback loop: a failure did not update the wiki, did not add a missing strategy, did not propose a new feature. Same mistake repeated.
4. No regression gate: unrelated changes could silently delete a working score (see [[lessons/api_hash_rotation_20260421]] for how brittle that is).

The restart (R1–R6) replaces the linear pipeline with an agentic loop.

## Three-layer separation

```
┌─ Cognition (LLM) ───────────────────────────────────────┐
│   Dev-time:    Claude Code (long context, code-aware).  │
│   Kaggle-time: Qwen 3 family (offline, tool-calling).   │
│   Reasons, hypothesizes, reflects. Neither writes code │
│   directly — at dev-time, Claude Code IS the reflector  │
│   AND the implementer. Qwen was measured too weak at    │
│   8B-14B for structured reflection on a 40-env trace    │
│   (R4 experiment, 2026-04-21); `scripts/analyze_trace.py│
│   │` does deterministic pattern extraction instead.     │
└───────────────────────┬─────────────────────────────────┘
                        │ reads
                        ▼
┌─ Memory (Wiki + Session) ───────────────────────────────┐
│   .wiki/  = long-term. Cross-linked markdown.           │
│             Dev-time: appended as lessons accumulate.   │
│             Kaggle-time: FROZEN snapshot.               │
│   Session = in-memory dict during a Kaggle run.         │
│             Tracks "this probe → primary failed" so     │
│             the LLM avoids dead ends within the 6h run. │
└───────────────────────┬─────────────────────────────────┘
                        │ invokes
                        ▼
┌─ Action (Strategies) ───────────────────────────────────┐
│   Python callables in src/admorphiq/agent_ensemble.py  │
│   Dev-time: added/rewritten when Cognition proposes it. │
│   Kaggle-time: FROZEN (cannot write .py, cannot reload  │
│                modules safely, no internet).            │
└─────────────────────────────────────────────────────────┘
```

The separation is not ornamental — it tracks what can change when:

| Layer | Dev-time (local) | Kaggle-time (6h run) |
|-------|------------------|----------------------|
| Cognition (LLM weights) | frozen per-bench | frozen |
| Cognition (prompt template) | editable | frozen for a submission |
| Memory (`.wiki/`) | editable | frozen |
| Memory (session state) | N/A | mutable, discarded at run end |
| Action (strategy functions) | editable | frozen |

**The Kaggle column has only session state as mutable.** Everything else ships as an asset. This constraint drives every design choice below.

## Dev-time loop (R4 reflection)

Runs between Kaggle submissions, on a laptop with internet and Claude Code available.

```
┌── 1. Agent run ──────────────────────────────────────────┐
│   scripts/run_wiki_agent.py                              │
│   → scripts/wiki_agent_results.json (per-env trace)      │
└────────────────┬─────────────────────────────────────────┘
                 ▼
┌── 2. Reflection (Cognition) ─────────────────────────────┐
│   scripts/analyze_trace.py    (deterministic, always-on) │
│     Emits scripts/trace_analysis.json with:              │
│       - headline counts                                  │
│       - primary_strategy success rates                   │
│       - pattern flags (dir_map→click misroute,           │
│         wasted_budget, unknown_strategy picks,           │
│         LLM-flagged missing features)                    │
│   Claude Code (dev-time Cognition) reads this JSON and   │
│   authors the proposal inline during a session.          │
│                                                          │
│   scripts/reflect_wiki_agent.py  (LLM-assisted, kept for │
│     future use when a stronger model is available;       │
│     Qwen 3 8B/14B produce degenerate output on this task │
│     per 2026-04-21 R4 experiment — documented, not a     │
│     regression to fix against local 8B-class models)     │
└────────────────┬─────────────────────────────────────────┘
                 ▼
┌── 3. Apply (Claude Code, supervised) ────────────────────┐
│   Claude Code reads the JSON proposal and:               │
│   - writes/updates wiki pages (append-preferred)         │
│   - extends DiscoveryReport with new features            │
│   - writes new strategy functions + registers them       │
│   - opens a commit per logical change                    │
└────────────────┬─────────────────────────────────────────┘
                 ▼
┌── 4. Regression gate ────────────────────────────────────┐
│   scripts/regression_gate.py                             │
│   Compares new run's best_levels per env vs baseline.    │
│   If any env drops → fail → rollback commit.             │
│   If all hold or improve → promote baseline.             │
└────────────────┬─────────────────────────────────────────┘
                 ▼
          commit + go to 1
```

Why Claude Code applies, not Qwen: 8B-class models reliably propose but unreliably implement correct edits into an 8000-line strategy module. Reflection is bounded (read trace, write JSON); implementation is unbounded (diff a large file without breaking callers). Split at that joint.

## Kaggle-time loop

Runs in a single 6h notebook, no disk writes to code paths.

```
for env in environments:
    discovery = discover(env)               # rich features
    session.append(env_id, discovery)

    hypothesis = llm.classify(discovery, wiki, session)
    primary, fallbacks = hypothesis.strategies

    for strat_name in [primary, *fallbacks]:
        result = call_strategy(strat_name, env, budget, ctx)
        session.record(env_id, strat_name, result)
        if result.levels_gained:
            break
        # mid-run reflection: LLM sees what just failed
        hypothesis = llm.refine(discovery, session, failed=strat_name)
```

- `session` is a Python dict — accumulates failure patterns within the run.
- `wiki` pages are read from `.wiki/wiki/` once at startup, cached.
- `call_strategy` goes through a **universal dispatcher** (R3) that derives the extra args each strategy needs from `ctx`.
- `llm.refine` is optional — only invoke if token budget allows. Default fallback order from the initial classification is usually enough.

## Layer contracts

### Cognition → Memory

LLM receives: `{discovery, wiki_slice, session, strategy_whitelist}`.
LLM returns: strict JSON (`game_type`, `primary_strategy`, `fallback_stack`, `rationale`, `confidence`, `features_missing` optional).

`features_missing` lets the LLM flag "I would have classified differently if I saw X" — dev-time reflection consumes this to propose new derivable features.

### Memory → Cognition

`.wiki/` is read through a fixed retrieval recipe in `src/admorphiq/hypothesis/wiki_agent.py`. Order of pages matters (selector first, lessons last) — changing the order requires re-measuring classification accuracy.

### Cognition → Action

Strategy name must be in the whitelist. Whitelist is generated from `default_strategy_registry()` — **all 74 eligible strategies** after R3. Before R3, only 17 are eligible; this is a known gap and is the whole point of R3.

### Action → Memory

Strategy returns `(levels, winning_label, actions_used)`. The caller (WikiAgent.run) also records derived signals (unique states explored, cumulative frame diff, final frame hash) into the session state. These become reflection input.

## Self-improvement boundaries

What "self-improvement" actually means, per layer × time:

| Improvement | Dev-time | Kaggle-time |
|-------------|----------|-------------|
| LLM prompt edits | ✅ via Claude Code | ❌ frozen |
| Wiki page creation | ✅ via reflection + Claude Code | ❌ frozen |
| New strategy function | ✅ via reflection + Claude Code | ❌ frozen |
| Strategy parameter override | ✅ code edit | ⚠️ only if exposed via `ctx` |
| Avoid repeating a failed strategy in same env | ✅ session state can cross-persist via wiki append | ✅ session dict |
| Classification from richer features | ✅ feature added once, used forever | ✅ if feature derivation already shipped |

The column that matters for the competition is **dev-time**: each Kaggle submission ships a snapshot that the dev loop has already hardened.

## LLM Output Shape Enforcement (round 1 load-bearing rule)

The LLM (Qwen 3 8B/14B at 8-16KB prompt length) does NOT reliably follow a
prompt-declared output schema. Three layers are required for robust output,
each fixing a specific failure mode measured on the 2026-04-21 R7 bench
(see [[lessons/schema_enforcement_round1_20260421]] for the version arc).

1. **Strip tooling frontmatter before any content reaches the LLM.** Any
   retrieved wiki page whose body begins with `---\n...---\n` must be
   sanitized via `wiki_retrieval.strip_frontmatter`. Qwen 8B otherwise
   mimics the YAML key-value layout as its own output shape. Not a
   style preference — it's a measured regression (0 levels across 40 envs
   in R7 v1 before the strip landed).

2. **Decoder-level JSON Schema constraint.** Pass a full `json_schema` dict
   via `OllamaBackend.generate(..., json_schema=)` (Ollama 0.5+ accepts it
   as the `format` parameter). Prompt instructions like "emit this JSON"
   are not enough; Qwen creatively renames keys under long context.

3. **Enum-bind fields with a closed value set.** `primary_strategy`,
   `fallback_stack.items`, and `game_type` are all bound to literal enums
   in `_HYPOTHESIS_JSON_SCHEMA`. The decoder physically cannot emit a
   non-whitelist name. Post-hoc filtering (R7e `_validate_whitelist`)
   remains as a defense-in-depth belt but should never fire in the steady
   state.

4. **`uniqueItems: true` on choice arrays.** Prevents the LLM from padding
   `fallback_stack` with duplicates. 2026-04-21 R7 v3 observed 4/40 envs
   where Qwen repeated the same strategy 2-4 times.

These four rules are prerequisites for every new LLM-produced structured
output the project adds. A new endpoint that bypasses any of them will
fail in the same shape.

## Routing Rules Require Python Reinforcement

A routing rule expressed only in markdown (`selector.md` table, inline
prompt text) does NOT reliably shape Qwen's picks. The R6 and R7 benches
both measured envs where the LLM ignored a rule present in the prompt
(FT09 / CD82 / SB26 / AR25 on title-match; see
[[lessons/selector_is_advisory_not_enforced_20260421]] and
[[lessons/schema_enforcement_round1_20260421]]).

Principle: any routing rule the project depends on ships with two
implementations —

- **Wiki text** (human-readable, LLM-hint): `selector.md` rows, page prose.
- **Python enforcement** (runtime guarantee): either as a decoder constraint
  (enum), a deterministic seed in the retrieval (R7b `derive_seed_pages`),
  or a post-processing augmentation of the LLM output.

The two must say the same thing; they are audited in lockstep. If only
the wiki text exists, the rule is advisory and will be ignored some of the
time. If only the Python enforcement exists, the rule is opaque and the
LLM cannot reason about edge cases — add a wiki page.

## Falsification

This architecture is wrong if any of these become true:

- Live-env run with feature-rich DiscoveryReport (R2) + full 74-strategy whitelist (R3) **does not improve** over the 2026-04-21 baseline (15/40, 36 lvl). Either the features don't carry signal the LLM can use, or the extra strategies don't help beyond the generic ones. In that case the LLM is not the bottleneck — raw strategy implementations are, and the investment should redirect to R3-only (expose strategies) without R2 or LLM upgrade.
- Reflection (R4) proposes changes that **consistently fail the regression gate (R5)**. Means the LLM's meta-reasoning is too weak at 8B, and reflection should be driven by Claude Code directly with the LLM demoted to "assistant to the reviewer."
- Kaggle submission runtime blows past 6h once rich discovery and reflection loops are added. 6h is a hard notebook-kill deadline — exceeding it loses the entire submission, so runtime budget is mandatory, not optional. Mitigation ladder (apply cheapest first, stop once under budget):
  1. Per-env time-box (cap N minutes per game, skip to next)
  2. Reduce `budget_per_strategy` (3000 → 1500)
  3. Cache classifications by probe signature (same probe → reuse previous hypothesis without re-calling LLM)
  4. Disable mid-run `llm.refine()` (keep initial classify + fallback_stack, no per-failure re-query)
  5. Shrink `fallback_stack` length (3 → 1)
  6. Drop to 1-shot classification with fixed `selector.md` dispatch (no LLM-picked fallbacks)
  7. Last resort: disable WikiAgent entirely and fall back to the pre-R1 ensemble dispatcher

  Steps 1–3 preserve quality. 4–5 trade some fallback flexibility. 6–7 are design regressions and should be avoided unless 1–5 are insufficient. Falsification fires only if **steps 1–5 all fail** to bring the run under 6h — that's when the richer design itself is at fault, not just the budget knobs.

## Related

- [[selector.md]] — current dispatch rules (expands under R3)
- [[reasoning/discovery_phase]] — what `discover()` should observe (expands under R2)
- [[reasoning/frame_to_strategy_chain]] — the LLM's decision template
- [[reasoning/hypothesis_check]] — post-execution validation
- [[lessons/api_hash_rotation_20260421]] — why the regression gate (R5) is non-optional
- [[lessons/brittle_tells]] — what the reflection module must flag as "do not propose this kind of strategy"
- [[reasoning/benchmark_protocol]] — cold-prompt vs live-env bench split

## Sources

- `src/admorphiq/hypothesis/wiki_agent.py` — current WikiAgent (baseline for R2/R3)
- `src/admorphiq/hypothesis/__init__.py:16-57` — `default_strategy_registry()` (17/74 strategies exposed — the R3 gap)
- `src/admorphiq/agent_ensemble.py` — 74 strategy functions (the universe)
- `scripts/wiki_agent_results.json` — 2026-04-21 live-env baseline trace
- `memory/project_wiki_agent_first_run.md` — why the restart was needed
- `memory/feedback_preserve_framework.md` — don't collapse dev-time and Kaggle-time concerns
