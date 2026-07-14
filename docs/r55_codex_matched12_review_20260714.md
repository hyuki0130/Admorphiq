codex
## R55 ruling

Accept the analysis and all three recommendations, with one wording correction:

- The tested scheduled audit is net-negative under the 500s evaluation budget.
- It produced no incremental clears.
- “Even at zero cost it adds no clears” is not experimentally established; zero-latency audit was not tested. The defensible conclusion is that there is no observed capability benefit that would justify its current cost.

C2 should be reclassified as an instrumentation/ordering sanity check, not evidence of efficacy.

### What the 28 runs can still answer

Do these offline analyses before closing R55:

- Counterfactual truncation: truncate each OFF stream at its paired ON action count. This separates losses caused by fewer actions from trajectory changes.
- Prefix divergence: verify ON/OFF behavior is identical before audit@12, then identify the first post-audit action divergence.
- Audit-content effect: determine whether the audit changed the stated goal, tool selection, or immediate action sequence.
- Per-call accounting: audit calls, tokens, latency, and actions lost per invocation.
- Near-progress extraction on the ten zero games: levels entered, state novelty, distance moved, objects manipulated—not just final RHAE.

The r11l loss is not a reproducible treatment effect yet. It is one matched pair. More importantly, throughput alone cannot explain it: ON executed 90 actions, while OFF earned L1 at action 46. Audit-induced policy/context divergence is therefore a second plausible cost channel. Report r11l as a causal case study, not an effect estimate.

The ten shared-zero games are likewise a strong screening result, but—with one run per arm—not yet ten reproducible walls.

## Next experiment: decoupled PLAN × NAV

Choose **(c)**. Run a clean audit-OFF 2×2 on the diagnosed navigation walls:

| Cell | PLAN | NAV |
|---|---:|---:|
| Base | OFF | OFF |
| Plan | ON | OFF |
| Nav | OFF | ON |
| Combined | ON | ON |

Games:

- `ls20`
- `g50t`
- `tu93`

Run three matched replicates per cell per game: **36 runs total**.

Keep fixed:

- Sandbox fixes ON
- Audit OFF
- Qwen/base model unchanged
- REPL unchanged
- Temperature 0.0
- 500s hard wall and existing action limits
- Matched initial states/seeds
- Randomized/interleaved cell order

Do not grant treatment cells extra time. Wall-clock utility is the production endpoint.

### Frozen trigger definitions

Before running, freeze and unit-test the trigger logic against existing traces:

- PLAN: fire after 12 consecutive environment actions without objective progress or material state change; cooldown 15 actions; maximum two invocations per run. Generate a short receding-horizon plan from the current goal and recent outcomes, without requiring goal revision.
- NAV: fire after four movement attempts producing no position/topology progress or entering a repeated-state loop; cooldown eight actions; maximum four invocations. Invoke shortest-path only when an observed traversability graph exists; otherwise no-op.
- Combined: independent triggers, but only one intervention may fire on a given action.

Log trigger reason, input state, output, latency, tokens, following actions, and whether progress occurs within the next five actions.

### Promotion gates

Promote a cell only if all of these hold:

1. It produces a new level/clear on a formerly-zero game, reproduced in at least 2/3 replicates.
2. Its median RHAE delta is positive on at least two of the three games.
3. It beats Base in at least 6/9 paired game-replicates.
4. Any action-throughput loss exceeds 20% only if compensated by a reproduced level/clear.
5. If multiple cells pass, choose lexicographically by clears, levels, aggregate RHAE, then simplicity. Do not select Combined merely for a small noisy edge.

Then run the winner versus Base on `r11l`, three matched replicates each. Require the winner to preserve L1 in at least 2/3 runs and avoid more than a 10% aggregate RHAE regression.

If it passes, spend the remaining quota on one full25 evaluation of the winner. Submit only if it beats 5.83. If no cell passes, do not force a full25 treatment run; use the remaining approximately 3.2h for the audit-OFF base coverage map.

This sequence fits roughly within 8–10 GPU-hours and tests an actual capability intervention before paying for broad coverage.

## Audit disposition

**Kill the scheduled audit implementation; park the concept.**

The tune-before-discard requirement has been met for the periodic mechanism: it was correctly instrumented, matched, replicated on its claimed win, and falsified there. Another trigger-tuning cycle is not warranted without evidence that audit content—not merely the sandbox fixes—helps.

Retain the underlying inspection/revision operation only as a model-invocable tool with no automatic calls. That is effectively zero idle cost, but it should be treated as a new affordance experiment later—not as “audit-ON” and not as a prerequisite for PLAN/NAV.

## Submission chain and ablations

Do not relax the submission gates.

Change the ablation structure as follows:

- Sandbox fixes become invariant baseline infrastructure, not an experimental factor.
- Audit is removed from the active submission chain.
- Replace the audit-coupled ablation with the audit-OFF **PLAN × NAV** 2×2 above.
- RHAE/progress can nominate a candidate, but a formerly-zero game needs a reproduced hard outcome before promotion.
- Preserve the full25 run as qualification, not discovery.

Priority after this experiment should be:

1. Decoupled PLAN/NAV
2. Gemma–Qwen matched challenger if PLAN/NAV produces no hard outcome
3. Wall-focused transcript/deep-budget diagnosis
4. JSON-only versus REPL as an interface ablation
5. Base full25 mapping when no qualified treatment exists

The central R55 conclusion stands: the sandbox fixes created the su15 capability; scheduled goal revision did not.
tokens used
