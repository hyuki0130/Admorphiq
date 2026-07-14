codex
## Bottom line

Diagnoses 1, 3, and 5 are directionally correct; 2 is likely but overstated as proven; 4 is wrong. The v4 legality prompt is necessary, but the REPL fix is structurally incomplete and raising `max_tokens` is the wrong default tradeoff.

Most importantly: v3 did not fail merely because Qwen was unaware of the REPL. The agent currently lacks the feedback loop, visual input, and causal history needed to learn a game at all.

## Verdict on diagnoses 1–5

| Diagnosis | Verdict | Adversarial correction |
|---|---|---|
| 1. Illegal MOUSE dominates g50t/ls20 | Accept, incomplete | Correct counts: 55 illegal clicks. But the resulting behavior was worse than the rejection count suggests: rejected/failed proposals silently became deterministic fallbacks. g50t executed inferred `UP` on 36/41 turns; ls20 on 28/34. |
| 2. su15 failures are truncation | Likely, not proven in v3 | All 17 parse failures across all games—not just su15’s eight—took about 30 seconds, exactly consistent with 1000 tokens at ~32–35 tok/s. But v3 recorded neither tokens nor `finish_reason`, so this was inference. |
| 3. REPL absent because prompt omitted it | Observation accepted; root cause rejected | The missing API description explains zero code blocks. It is not the biggest blocker: sandbox output is never returned to Qwen, so inspection cannot inform a subsequent decision. |
| 4. MEMORY static downstream of no REPL | Reject | Nothing mutates `EnvironmentMemory`. Even perfect REPL engagement leaves it empty. |
| 5. Latency output-dominated | Mostly accept | Decode is ~32 tok/s versus prompt throughput ~200–500 tok/s. Output is the larger term, but 5.4–11.3k-character packets still cost material prefill time. Instrument TTFT/decode separately before calling input free. |

One important parser failure: su15 turn 4 is truncated at `Let's try clicking on o30 at (2`, yet the permissive parser recovers the earlier explanatory mention `MOUSE(63,58)`. Thus “parse success” can mean “execute a stale action mentioned in reasoning,” not “execute the model’s intended final answer.” The unanchored search is visible in [agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:216).

## What the analysis missed

These are more consequential than MEMORY engagement:

1. **This is not an interactive REPL.** Code runs once; stdout is recorded and discarded. If the block only calls `crop()`, `compare()`, or `print()`, no action is produced and the agent silently falls back. The v4 instruction “inspect before acting” describes a capability the loop does not provide. See [agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:424).

2. **No image is sent.** The LLM call is explicitly `complete(prompt, None)`. This is currently a text-only segmentation policy, not the proposed multimodal REPL agent. See [agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:401).

3. **Causal feedback is crippled.**
   - `LAST_ACTION` drops mouse row/column and action source.
   - It omits `board_changed`, completion, and outcome.
   - `HistoryTiers.recent` is populated but never serialized.
   - `RECENT_EVENTS` contains event names without turn/action association.

   Consequently Qwen repeatedly tries to reverse-engineer where the previous click occurred. See [agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:495) and [turn_packet.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/turn_packet.py:255).

4. **Hidden fallback dominates actual play.** There were 74/173 turns where the transcript’s chosen action was null, followed by a fallback environment action. The fallback always picks the first movement in `UP, DOWN, LEFT, RIGHT, SPACE`, or center-clicks mouse games. It also bypasses governor validation. See [agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:346).

5. **“Repeat rejection ≈0” masks substantial looping.** Aligning consecutive frame hashes gives 30 no-change transitions out of 168 observable transitions: 12/33 dc22 and 18/40 g50t. Rejected proposals fall back outside `check_single`, so the same fallback can repeat in the same state despite the governor.

6. **Coordinate representation remains ambiguous.** Internally `bbox`, centroid, and `safe_click` are `(row, col)`, but the packet exposes unlabeled arrays. The transcripts contain repeated swaps—for example, bp35 discusses safe-click `(20,14)` and emits `MOUSE(14,20)`; dc22 does the same with `(18,46)` → `(46,18)`. Use named fields or names such as `bbox_rc` and `safe_click_rc`.

7. **Object trimming breaks referential integrity.** Events mention appeared/split IDs that may not be among the 20 retained objects. Qwen explicitly notices this in su15. Changed objects should be retained first; unchanged large objects should be trimmed first. The truncation marker is also removed before serialization. See [turn_packet.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/turn_packet.py:242).

8. **Segmentation events are being mistaken for semantics.** Qwen repeatedly invents “clear newly appeared pieces” strategies from component split/disappearance noise. Adding more access to the same tracker will not fix that without image/raw-crop feedback.

9. **The transcript was not truthful about the executed action.** In v3, null recorded actions still produced fallbacks, and `frame_after_hash` was really the decision-time frame. The later observability commit improves hashes/tokens, but v5 still needs explicit `proposal`, `governor_decision`, `fallback`, and `executed_action`.

10. **`game_id` is always empty.** Lower performance importance, but it weakens transcript correlation and proves the packet is not populated as designed.

## v4 verdict

Let the current v4 run finish—it is useful as a prompt-compliance experiment—but do not repeat v4 unchanged.

The legality reminder is the right minimal fix. On g50t and ls20, the acceptance threshold should be essentially zero illegal MOUSE proposals.

The REPL prompt is not a complete REPL-axis fix. Before judging the arm, implement a bounded tool loop:

1. Qwen emits inspection code.
2. Sandbox runs it.
3. Its bounded stdout/error is returned to Qwen without taking an environment action.
4. Qwen emits an action or another inspection, with at most 1–2 tool rounds.
5. Inspection-only output must never trigger a hidden fallback.

Inviting both code and direct actions is fine if the experiment is described as “REPL-enabled policy versus JSON-only policy.” It is not a pure code-versus-JSON comparison. Direct actions are a valuable fast path once the move is known.

Raising 1000 → 1536 tokens is the weakest v4 change. The previous “keep reasoning brief” instruction was ignored, so a softer four-line instruction should not be trusted to offset a 54% larger ceiling. Prefer:

- Direct action response: constrained JSON, 32–64 output tokens.
- Code response: structured `{mode:"python", code:"..."}`, 256–512 tokens.
- Post-tool action response: constrained JSON, 32–64 tokens.
- Put the action first or use guided decoding so truncation cannot erase it.
- Remove permissive incidental-action recovery.

Also send the current image and restore a complete causal transition before spending another cycle tuning prompts.

## v5 scorecard and gates

### Integrity gates

These must pass before interpreting game capability:

- Illegal proposal rate on movement-only games: **0%; hard fail above 2%**.
- Parse failure: **<1%**.
- Truncation: **<1% direct-action turns; <5% code turns**.
- Hidden fallback: **<1%**, and every fallback explicitly logged and shown next turn.
- Transcript proposal → governor → executed action correlation: **100%**.
- After-state/action correlation: **100%**.
- Sandbox error rate: **<2%**.
- Inspection-only code causing an environment action: **0 cases**.
- Stale/incidental action parser false positives: **0 cases**.

### Capability gates

Primary endpoints:

- Minimum continuation gate: **at least one sanity L1 clear**.
- Strong v5 gate: **L1 clear on both su15 and ls20**, within 300 seconds each.
- Report `time_to_first_clear`, `actions_to_first_clear`, `levels/600s`, and score—not “actions/level” alone, which is undefined for zero-clear runs.
- Wall games are diagnostic; any clear is a strong positive but should not be required to validate basic wiring.

Secondary behavioral metrics:

- Actual action source: direct / code / macro / fallback.
- Unique states per executed action.
- No-change rate and consecutive no-change streak.
- Repeated state-action attempts, including fallback paths.
- Coordinate swaps and off-target clicks.
- Output/input tokens, TTFT, decode time, p50/p95 latency.
- Packet truncation and changed-object coverage.

Latency targets after protocol tightening:

- Direct-action output p50 ≤32 tokens, p95 ≤64.
- Overall call latency p50 ≤8–10s, p95 ≤15s.
- At least **60 executed actions/600s** without macros, roughly double v3.

### REPL engagement and arm decision

Measure meaningful engagement, not just code fences:

- Valid inspection rate on uncertainty-eligible turns: target **≥25%**, floor **10%**.
- Tool-result-to-governed-action completion: **≥95%**.
- Tool output actually returned to the model: **100%**.
- Environment actions consumed by inspection: **0**.

Run matched REPL-enabled and JSON-only arms with the same image, packet, legal-action enforcement, model, wall budget, and direct-action grammar.

Keep the REPL arm if it produces either:

- at least one additional level clear, or
- the same clears with ≥20% fewer environment actions,

without reducing levels/600s by more than 10%.

Kill/pivot to JSON-only if, after at least 100 eligible decisions:

- valid tool engagement remains below 10%, or
- it adds no clears/action-efficiency benefit while p50 decision cost is >1.25× JSON, or
- executed-action throughput is <80% of JSON.

If both arms satisfy integrity gates but still clear neither sanity game, stop prompt iteration. Pivot to multimodal input and causal packet repair.

## Latency priority

First, outside your list: hard-limit output through structured action-first decoding. That is the highest-confidence gain.

Then:

1. **Remove `--enforce-eager` in a measured A/B.** Decode is dominant and CUDA graphs/compilation should attack the ~32 tok/s bottleneck directly. Measure boot time plus steady-state break-even; reduce `--max-model-len` from 131k for this experiment if capture cost is excessive.
2. **Packet trim, but correctness-aware.** Preserve last transition and changed objects; remove repeated unchanged object detail and empty MEMORY fields. Consider prefix caching for the static system prefix.
3. **Governor-gated macros/queues**, only after causal prediction works. They can deliver the largest actions/second improvement on verified navigation. Code blocks that call `action()` multiple times must use the same per-step stop-on-surprise logic; currently they do not.
4. **Speculative decoding**, after the simpler path. It adds draft-model/configuration and acceptance-rate risk.
5. **Fewer-but-bigger REPL turns: do not prioritize.** With output-dominated inference and no working tool feedback, bigger generations worsen the problem. Use short inspect → result → action loops; amortize calls only through verified macros or persisted controller code.

The v5 gating decision should therefore be: repair the REPL semantics and causal packet first, compare it against a constrained JSON arm, and treat serving optimization as secondary until one sanity level clears.
tokens used
