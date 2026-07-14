codex
## Verdict

- Accept the P0 invalidation of the REPL capability result.
- Do not invalidate all v5 telemetry.
- Amend su15 from “pure goal-inference failure” to “wrong joint mechanic/goal model under a degraded tool path.”
- Reject counter+nudge alone as the goal-revision mechanism.
- Run v6 as a P0-only replication. Do not bundle goal revision.

### 1. What remains meaningful after the sandbox failure

The PYTHONPATH diagnosis is convincing, and the fix is directionally correct. But the current mocked test only proves that `PYTHONPATH` is passed—not that a Kaggle-style path-injected subprocess actually imports and executes the worker. Add a pre-bench real subprocess smoke test and abort the run if it fails.

Metric validity:

| v5 observation | Verdict |
|---|---|
| Illegal MOUSE = 0% | Valid prompt/governor integrity result, conditional on the broken-sandbox response distribution |
| Event action→transition completeness | Valid |
| 70–99% model-chosen | Valid as action provenance for this degraded run |
| REPL usefulness / informed actions | Invalid |
| Clears and capability comparison | Invalid as an evaluation of the REPL arm |
| LLM-call latency | Still meaningful as serving telemetry |
| End-to-end throughput | Confounded: import failures are fast and error text changes subsequent generations |
| su15 behavior | Diagnostic evidence only, not a clean REPL capability diagnosis |

The 70–99% statistic needs narrower wording. It means “not fallback,” not “REPL-informed.” After a failed inspection, v5 gives the model another call containing `ERROR`, and a direct action from that second call is classified as model-chosen. Thus v5 may have reduced fallback through a second-chance call, not through useful inspection ([agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:553)).

Also, action source is not in the authoritative event stream; it is disclosed one transition later through `LAST_ACTION` ([agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:659)). Treat the percentage as transcript-derived provenance, with the terminal action potentially censored.

### 2. su15 diagnosis: wrong goal, but not “perception/dynamics fine”

The “connect the dots” hypothesis is demonstrably wrong against the project’s measured su15 mechanic. su15 is a vacuum/merge/delivery puzzle: clicks attract sprites, same-color objects merge, and target objects must reach goal zones—not a paint/flood game ([SU15.md](/Users/nhn/Workspace/Admorphiq/.wiki/wiki/games/SU15.md:12)).

But the stronger diagnosis is overstated:

- `PREDICT: changed` at 100% establishes only action responsiveness. It says nothing about whether the model understood vacuum attraction, merging, downgrading, or delivery.
- Unique exact states do not exclude random drift, approximate oscillation, or systematically moving the wrong sprites.
- “New green objects appeared” may be component split/appearance churn. If the model interpreted that as object creation, semantic perception was not fine.
- The dead REPL matters causally: the model was denied precisely the transition inspection that could reveal “nearby sprites moved toward the click.”

So my ruling is:

> v5 shows a persistent false joint mechanic/goal hypothesis and absent progress falsification. It does not isolate pure goal inference, and it does not confirm that perception or dynamics were sound.

It is consistent with the project-wide frontier, not confirmation of it.

Transcript discriminators:

- **Memory echo:** t0 cannot originate from MEMORY if memory was empty. Later persistence may be self-conditioning because each correct `changed` prediction writes its rationale into `goal_hypotheses`, then replays it at high confidence.
- **Eviction:** inspect whether each prompt still contained evidence relevant to merging, motion direction, static goal zones, and non-completion. Presently `RECENT_TRANSITIONS` records only action/source/board-change—not accumulated lack of completion or semantic delta ([agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:445)). This is more than eviction: the counterevidence was never represented.
- **Vision:** the rendered board is approximately 790×790, so “image too small” is not the first hypothesis ([vlm_policy.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/vlm_policy.py:97)). But image hashes only prove attachment, not legibility. Save actual PNG blobs or a montage; inspect whether the model recognizes the legend, static goal regions, sprite motion, and merges.
- **Mechanic versus goal:** require spatial predictions such as “sprite A will move toward click,” “A and B will merge,” or “object C will enter region G.” Binary board-change predictions cannot discriminate them.

### 3. Goal revision: use the counter as a trigger, not the mechanism

Counter+nudge alone is too weak and slightly misworded. High action count means the current **goal-or-plan** failed—not necessarily that the goal is wrong. A correct goal plus bad control would receive the wrong intervention.

More importantly, the current “falsifiable memory” is not actually goal-falsifiable. A board-change rationale is stored in `goal_hypotheses`, and any changed board supports it ([agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:472), [turn_packet.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/turn_packet.py:97)). That architecture actively confirms su15’s false story.

My minimal v7 lever would be a counter-triggered mandatory audit at, for example, 12/24/48 actions without a level:

- `GOAL_HYPOTHESIS`
- `EXPECTED_MILESTONE` within a bounded number of actions
- `FALSIFIER`
- `ALTERNATIVE_HYPOTHESIS`
- one action chosen to discriminate current versus alternative

At the first audit, do not force a mechanic switch. Force an informative test. After a declared milestone is missed twice, reject the goal-or-plan and require the alternative.

Keep two prediction channels separate:

- `EFFECT_PREDICT`: immediate board/action dynamics.
- `PROGRESS_PREDICT`: a positive bounded-horizon milestone or target-state change.

Do not use bare “level_completed on the next action” scoring; predicting “no completion” would become the new trivial 100% answer. OCR is not the minimal lever either—the API already supplies exact level completion. Add HUD/legend crops only if saved images show that a meaningful within-level signal is present.

Implementation warning: current `turn_in_level` is actually game-lifetime `_turn`, because it is not reset on level-up, and the transcript’s dedicated field is never populated ([agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:418), [agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:649)). Build a real per-level action counter rather than aliasing it.

### 4. Sequencing ruling

Run v6 P0-only.

A working REPL might itself cause the needed revision by exposing vacuum motion and merges. Bundling the nudge would make a success uninterpretable and could mask whether the architecture already works. The proposed revision mechanism also needs correction before deployment.

Include these non-policy safeguards in v6:

- A real worker smoke test before model boot/play.
- Separate infrastructure/worker errors from model-code errors.
- Hard-abort on worker import failure.
- Report valid inspection→tool result→governed action completion.

If clean v6 still repeats the same false mechanic after receiving valid transition inspection, then v7 should add the structured falsification audit above. That would be strong evidence for a genuine goal-revision deficit.
tokens used
