codex
## Ruling

Accept the narrow claim: **the audit bundle plausibly caused the su15 trajectory to reconsider its goal and clear.**

Reject the stronger wording that the falsifier/alternative structure has been causally established or generalized. One successful trajectory is mechanism evidence, not an effect estimate.

### Corrections to the analysis

1. **su15 is strong temporal evidence, not yet causal proof.**

   The sequence—persistent false model in v6, audit prompt, revised model, subsequent clear—is compelling. But alternatives remain:

   - decoding/server nondeterminism;
   - an incidental successful action batch correlated with the revised prose;
   - the generic “stop and reconsider” instruction, rather than specifically the falsifier/alternative fields;
   - configuration or bug-fix differences between runs.

   Also, “four moving objects into target zones” is closer to the truth, but still not a verified executable model of vacuum/merge/delivery.

2. **The audit counts need correction.**

   A zero-clear level permits only three real `on_audit` events at 12/24/48. Yet ls20 is reported as four. The audit text remains in the prompt during a tool-loop continuation, even after `on_audit` is processed, so transcript appearances can exceed threshold firings ([agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:565), [audit.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/audit.py:50)).

   Instrument explicit `audit_triggered {threshold, action_count, parsed_fields}` events before interpreting audit frequency or idx12→idx13.

3. **Temperature is unresolved.**

   The checked-in client hardcodes `temperature: 0.0`, not 0.2 ([agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:157)). Verify the actual v7 request/config. Even greedy vLLM can have numerical nondeterminism, but this materially changes the replication argument.

4. **Overhead is not demonstrated as low.**

   Audits do not mechanically add environment rounds, but `llm_calls≈actions` does not measure token, latency, or behavioral overhead. And inspections falling from 41–63 to 8–27 is not “slight”; crowd-out remains plausible. Compare per-game inspection rate, output tokens, and wall time against matched OFF runs.

5. **ls20 is likely a planning/control gap, but not purely one.**

   Navigation is indeed the correct mechanic. However, `shortest_path` still requires correctly identifying the player, goal, and passable mask. Diagnose it as a **planning/control gap with a possible perception/walkability component**, not merely failure to call a function.

6. **The leaderboard datapoint does not confirm the generic-agent thesis.**

   It supports “public-specific solver depth transferred weakly in this submission delta.” The REPL arm was not responsible for the hidden improvement and therefore is not independently confirmed by that score.

## v8 decision

**Do a matched 12-game audit OFF/ON experiment, not an unpaired full-25.** It costs roughly the same 4–5 GPU hours and actually answers whether the audit helps.

Use:

`su15, ls20, bp35, dc22, g50t, r11l, sp80, ft09, ar25, sb26, tr87, tu93`

This preserves all five carryovers, adds two positive controls, and covers click/paint, transformation, hidden-mechanic movement, mixed movement, and maze navigation.

Additionally, give su15 three paired OFF/ON replicates total. Interleave the arms and pin commit, initial-frame hash, model, request parameters, and seed where supported.

A reasonable continuation gate is:

- audit ON clears su15 in at least 2/3 runs and materially outperforms OFF;
- the revision and discriminating action precede every ON clear;
- across the 12 games, ON gains at least two clears over OFF without worse aggregate RHAE.

**Do not include the navigation fix or earlier thresholds.** Ship the sandbox fixes into both arms. If this passes, then run the unchanged audit arm on the full 25. Afterward, test navigation separately on `ls20, dc22, g50t, tu93`.

## Efficiency ruling

First extract the `level_up` action ID. The bench continues after L1, so a wall-terminal diagnostic of 107 total actions is not automatically “107 actions to L1” ([bench.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/bench.py:128)). Report:

- actions to first level-up;
- actions before first audit;
- actions between audits;
- actions from revision to level-up;
- actions after level-up.

If L1 genuinely took 107 actions, **post-revision efficiency is the next lever**. Revision occurred around action 24, leaving roughly 83 post-revision actions. Moving the first audit earlier can save at most about 12 actions; even eliminating all 24 pre-revision actions only improves `(12/107)²≈0.013` to `(12/83)²≈0.021`.

Therefore rank the efficiency work:

1. post-revision plan quality and short verified execution;
2. navigation-specific `shortest_path`/plan-then-execute;
3. earlier first audit.

Use short receding-horizon macros with invariants, not long action batches. Clear count remains a valid architecture-discovery metric for one more breadth experiment, but **RHAE and actions-to-clear must now be co-primary**. The competition explicitly squares efficiency and level-weights the result ([README.md](/Users/nhn/Workspace/Admorphiq/README.md:7)).

## Submission-chain gate

The REPL arm has **not earned deployment yet**. It earns a place only when all of these hold:

- at least three reproducible clears across two or more mechanic families;
- at least two are incremental over the LLM-free floor;
- median clear efficiency is within roughly 3× human actions;
- at least one L2+ result demonstrates that learned knowledge amortizes;
- `floor + REPL` beats the floor by at least 5% on paired real RHAE, with no lost floor clears;
- uplift survives metamorphic/OOD variants and a non-oracle router;
- simulated 110-game runtime remains under eight hours.

Integrate it as a zero-action plan proposer or pre-action routed controller—not as a post-stall fallback, because stalled actions permanently damage RHAE. Those are also the existing architectural ship gates ([design consultation](/Users/nhn/Workspace/Admorphiq/docs/r55_codex_design_consultation_20260714.md:484)).
tokens used
