# Recommended design

Use **(b) Duck-style multimodal code-REPL as the primary agent**, augmented with a narrow version of **(c)**:

> The LLM discovers an environment-specific world model and writes/adapts a controller that persists across levels. Reuse the learned controller—not an exact trajectory and not a public-mechanic solver.

Keep your existing solvers as **zero-action plan proposers** and emergency recovery, not as the main router. Do not make (d) “LLM after baseline stalls” the default: by the time a stall is observable, the wasted actions have already damaged RHAE.

The deployable architecture is therefore:

```text
multimodal Qwen 3.6
        │
        ├── image + structured segmentation + transition ledger
        ├── stateless Python REPL for inspection/planning
        ├── persistent environment theory/controller memory
        └── guarded action executor
                 │
                 ├── one real action by default
                 ├── short macro only with explicit invariants
                 └── existing solvers may submit plans in shadow
```

This is “Duck-plus-memory-and-governor,” not a large hybrid of all four options.

## What the winners actually established

They established that:

- Small, local open-weight LLMs can outperform search-heavy or heavily public-tuned agents on the M1 hidden distribution.
- Both code-REPL and direct vision-policy designs are viable. Duck used a REPL; Reki and forge used JSON actions.
- Multimodal perception, short context, transition feedback, and persistent compact memory are useful ingredients.
- Complexity has a real tax: forge’s best run disabled its extra arbiter machinery, while Tufa reports that its handcrafted tools hurt. The official recap confirms these descriptions. [ARC Prize M1 recap](https://arcprize.org/blog/arc-prize-2026-milestone-1)

They did **not** establish that:

- Code-REPL is intrinsically better than JSON policy. Model, prompt, representation, stochasticity, and harness all differed.
- Hiding the raw grid is optimal. It worked in Duck, but there is no clean published ablation.
- Handcrafted machinery is universally harmful. Tufa showed that particular tools reduced performance in its harness.
- Exact solution replay transfers across levels.
- Any public-25 improvement predicts hidden improvement. The report explicitly says the private set is harder and intentionally OOD with limited mechanic overlap. [ARC-AGI-3 technical report](https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf)
- The M1 ordering will persist on the final hidden set.

Your own 13% proxy-to-hidden transfer is stronger evidence than most published anecdotes: optimizing the public-25 aggregate is currently a dangerous objective.

# 1. Architecture decision

## Why (b) over (a)

A pure JSON policy asks a 27–31B model to simultaneously perceive, remember, infer mechanics, plan, and emit a valid action in one forward pass. It is simple and fast, but tends toward:

- reactive local behavior;
- repeated experiments;
- coordinate hallucinations;
- loss of exact spatial structure;
- brittle 1–4-action queues.

The REPL gives the model free internal computation: it can compare components, inspect transitions, search paths, test geometric hypotheses, and build an explicit level-specific controller without consuming environment actions. Internal reasoning and tool use do not count as game actions under the benchmark definition. [Technical report](https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf)

Duck’s released implementation is especially relevant: it exposes ASCII, connected components, hashes, boundaries, containment, adjacency, transition history, legal actions, and action-result fields while withholding the full numeric grid from the model-facing sandbox. [Duck harness README](https://github.com/Tufalabs/duck-harness/blob/main/ARC3-Inference/README.md)

## Why not the proposed version of (c)

“Discover once, then hand to mechanic-family solvers” assumes hidden mechanics fall into your existing ontology. That is exactly the assumption the private-set design attacks.

The report says:

- environments contain multiple mechanics;
- single-mechanic scaling is an antipattern;
- later levels compose earlier concepts;
- environments are intentionally novel even relative to each other. [Technical report](https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf)

Reuse should therefore occur at three levels:

1. **Facts:** action/object mappings and invariants.
2. **Options:** learned subroutines such as “move object A until relation R.”
3. **Controller code:** a parameterized policy that re-detects objects in each new level.

Do not reuse an exact action trace unless the initial-state signature and predicted intermediate signatures match.

## Why not (d) as the primary strategy

A fallback router cannot guarantee a floor on a single trajectory. If the baseline spends 30 actions before declaring a stall, the LLM inherits a damaged state and score. Conversely, an LLM-first fallback to BFS is nearly scoreless after the LLM’s actions.

Use the baseline only when:

- it can construct a complete plan before taking any action;
- its applicability predicate is structural, not keyed to a public game;
- it predicts at least the first transition;
- execution stops immediately if the prediction fails.

Otherwise, let the LLM see the baseline proposal as one hypothesis. The LLM remains responsible for adaptation.

# 2. Module list

1. **Frame canonicalizer**  
   Handles animation sequences, stable palette IDs, coordinates, frame hashes, and optional HUD candidates.

2. **Segmenter and tracker**  
   Components, stable object IDs, split/merge tracking, relations, shape hashes, motion, and temporal deltas.

3. **Multimodal renderer**  
   Nearest-neighbor image with row/column ticks, object-ID overlays in an optional second image, and fixed color rendering.

4. **Observation store**  
   Raw frames remain available to deterministic code, even if not dumped into the prompt.

5. **Inspection API**  
   `objects()`, `crop()`, `ascii(region)`, `mask(id)`, `compare(t1,t2)`, `relations(id)`, and compact path/geometric utilities.

6. **Python sandbox**  
   Stateless per model call, stdlib plus tightly controlled helpers, bounded output, timeout, and explicit action accounting.

7. **Environment memory**  
   Persistent structured theory, evidence, failed probes, controllers, and level-to-level changes.

8. **Action governor**  
   Legal-action enforcement, repeated state-action prevention, macro preconditions, coordinate checking, and stop-on-surprise.

9. **Shadow solver adapter**  
   Existing solvers may return proposed plan, applicability evidence, and predicted deltas without acting.

10. **Budget scheduler**  
    Per-game wall time, inference tokens, action phase, concurrency fairness, and terminal cutoffs.

11. **Trace/replay system**  
    Every prompt, response, tool call, action, frame, memory mutation, latency, and token count.

12. **Evaluator**  
    Per-level success, action efficiency, time, invalid-action rate, prediction accuracy, and paired comparisons.

# 3. Per-turn perception and prompt

Do not send a full 4,096-cell array every turn. Keep it available through inspection tools. Send one current image plus structured text optimized around changes.

A useful turn packet looks like:

```yaml
GAME:
  game_id: hidden_042
  level: 3
  turn_in_level: 17
  total_actions: 43
  legal_actions: [UP, DOWN, LEFT, RIGHT, SPACE, UNDO, MOUSE]
  coordinate_rule: "MOUSE(row, col), zero-based"

LAST_ACTION:
  action: "LEFT"
  board_changed: true
  level_completed: false
  game_over: false
  reward: 0
  transition_hash: "..."

CHANGE:
  changed_bbox: [r0, c0, r1, c1]
  cells_changed: 18
  appeared: [o12]
  disappeared: []
  moved:
    - {id: o3, from: [21, 12], to: [21, 9]}
  recolored: []
  relations_changed:
    - "o3 now adjacent_left_of o8"

SCENE:
  frame_hash: "..."
  background_color: 0
  regions:
    - {id: region0, bbox: [...], boundary_color: 5, role_guess: unknown}
  objects:
    - id: o3
      bbox: [20, 9, 22, 11]
      centroid: [21, 10]
      colors: {2: 9}
      area: 9
      shape_hash: "..."
      topology: {components: 1, holes: 0}
      touches_boundary: false
      contained_by: region0
      adjacent: [{id: o8, direction: right, gap: 0}]
      change_history: "moved left 3 after LEFT"
      safe_click: [21, 10]

RECENT_EVENTS:
  - "t14 SPACE: no change"
  - "t15 click(o8): o8 changed 4→6"
  - "t16 LEFT: o3 moved toward o8"
  - "t17 LEFT: same causal effect"

MEMORY:
  goal_hypotheses:
    - hypothesis: "place o3 adjacent to recolored o8"
      confidence: 0.72
      evidence: [...]
      counterevidence: [...]
  action_semantics:
    LEFT: "moves o3 three columns unless blocked"
    SPACE: "no observed effect in two distinct states"
  invariants: [...]
  dead_interventions: [...]
  learned_options: [...]
  unresolved_questions: [...]
  current_plan: [...]
```

The current image should precede the text for Gemma; Google explicitly recommends image-before-text for Gemma 4. [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)

## Segmentation requirements

Each component needs:

- stable ID across translation;
- bounding box, area, centroid, exact mask/shape hash;
- color histogram;
- holes, connectedness, symmetry, boundary contact;
- containment and adjacency;
- motion/change history;
- one verified interior click coordinate;
- split, merge, appearance, and disappearance events.

Two cautions:

- Do not permanently mask HUD-like regions. Mark them as `role_candidate: hud` until causal tests support that conclusion.
- Connected components are not always semantic objects. Preserve nested regions, same-shape groups, and exact crops so the model can reject segmentation errors.

## History compaction

Use three tiers:

- **Recent window:** last 4–8 full transitions.
- **Event ledger:** compact causal events from the current level, about 20–40 entries.
- **Persistent environment memory:** 1–2K tokens carried across levels.

Refresh memory on events, not just every tenth step:

- level completion;
- hypothesis confirmation/refutation;
- first observed action effect;
- split/merge/new object;
- repeated no-change signature;
- plan failure;
- before context eviction.

The memory should store falsifiable statements:

```yaml
hypothesis:
prediction:
confidence:
supporting_events:
contradicting_events:
status: active | rejected | confirmed
```

This prevents a plausible early story from becoming permanent fact.

## Action output

Let the code agent call `action()` directly, but govern it:

- One action is the default.
- Permit a 2–8 action macro only if every step has a stated precondition and predicted invariant.
- Stop the macro on unexpected change, unexpected no-change, level completion, or signature mismatch.
- Navigation along a verified empty corridor is batchable; speculative clicking is not.

# 4. Exploration versus efficiency

The right objective is not “minimize exploration.” It is:

> Spend actions on information only when the expected savings across the remaining, more heavily weighted levels exceed the immediate RHAE loss.

The benchmark explicitly makes L1 tutorial-like and later levels compositional and more heavily weighted. [Technical report](https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf)

Use this phase policy:

### L1: bounded identification

- Identify controllable objects and action semantics.
- Prefer interventions that distinguish several hypotheses.
- Test each action type at most once per materially different state unless prior evidence predicts an effect.
- Allow a small exploration premium because L1 has the lowest weight and the knowledge can amortize across all later levels.

### L2: transfer validation

- Start with the L1 controller.
- Spend at most one or two probes validating what changed.
- Convert successful repeated behavior into a parameterized option.

### L3+: composition-first exploitation

- Assume earlier confirmed mechanics remain valid until contradicted.
- Search for new composition or constraints, not entirely new semantics.
- Probe only when uncertainty blocks every plausible plan.

A practical action ranker is:

```text
clear_probability × remaining_level_value
+ information_gain × reuse_horizon
- action_cost
- irreversible_risk
- repeated_intervention_penalty
```

Do not pretend the model’s numerical probabilities are calibrated. Use ordinal ranks and explicit predicted outcomes.

## Undo is not free

Undo is itself one of the environment actions, and the benchmark counts discrete environment interactions. A probe followed by undo normally costs two actions. [Technical report](https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf)

Undo is valuable for:

- preventing death or an expensive reset;
- returning from an irreversible branch;
- conducting a controlled before/probe/undo comparison while retaining the observation in memory.

It is not an RHAE exploit unless the actual competition scorer demonstrably excludes it. Write a scorer-level unit test before assuming anything unusual.

# 5. Model and serving recommendation

## First choice: Qwen 3.6 27B FP8

This has the strongest direct evidence: it powered Duck. Also, the “text-only” premise is incorrect. The official model is a causal LM with a vision encoder and supports image-text input. [Qwen 3.6 27B model card](https://huggingface.co/Qwen/Qwen3.6-27B)

Use it as a multimodal code agent, not merely a segmentation-text model.

## Second choice: Gemma 4 31B

Run it as the matched challenger because:

- Reki and forge provide direct ARC evidence;
- it has strong vision and structured tool-use support;
- your prior Gemma failures tested different harnesses, so they do not kill this design.

Do not decide from generic VQA or coding benchmarks. Decide from paired first-clear/action-efficiency experiments using the same harness.

## gpt-oss-120b

Keep as a later text-only code-agent control. It is a strong tool-using reasoning model and its MXFP4 checkpoint fits in about 80GB, but it is explicitly text-only and leaves less operational headroom. [OpenAI gpt-oss release](https://openai.com/index/introducing-gpt-oss/)

It becomes attractive only if segmentation-text reasoning dominates raw image perception in your kill tests. It is not the first deployment candidate.

## Do not serve two large models

Even if quantized weights technically fit, dual serving costs:

- KV-cache headroom;
- batching throughput;
- startup time;
- operational failure surface;
- a routing problem with no reliable labels.

First measure oracle complementarity: if “best of Qwen and Gemma per game” barely exceeds the better single model, kill the ensemble immediately.

## vLLM versus llama.cpp

Use **vLLM** first. Qwen recommends vLLM ≥0.19.0 for Qwen 3.6, including its reasoning and tool parsers. [Qwen serving documentation](https://huggingface.co/Qwen/Qwen3.6-27B)

llama.cpp is a fallback for a known-good GGUF build. Its multimodal server path remains marked experimental. [llama.cpp multimodal documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/multimodal.md)

Kaggle preflight must verify:

- bundled wheel matches CUDA, PyTorch, and Blackwell;
- all tokenizer, processor, chat-template, config, and model files are local;
- no runtime Hugging Face lookup;
- FP8 kernels work on the actual Kaggle GPU;
- tool and reasoning parsers match the exact checkpoint;
- model startup and first-request compilation fit the notebook budget;
- image decoding dependencies are bundled;
- a deliberately reduced context limit leaves room for concurrent KV cache;
- malformed tool calls cannot crash a game;
- one hung generation cannot starve all 110 games.

Start at 8 concurrent games, then benchmark 12 and 16. Use fair scheduling and a per-game wall-clock cap. Do not assume “1–3 seconds per call” until you have measured P50/P95 with images, thinking tokens, and concurrency.

# 6. Validation strategy

Yes: **build transcript replay first**.

It will not measure model intelligence, but it separates harness regressions from model variance and makes one-hour Kaggle iterations scientifically useful.

Every Kaggle run should save:

- exact prompts and image hashes;
- raw model output and parsed tool calls;
- reasoning/output token counts;
- inference and queue latency;
- sandbox stdout/errors/timeouts;
- every frame and transition;
- memory before/after;
- proposed, accepted, and rejected actions;
- per-level score and terminal reason.

Offline unit tests should cover:

- stable object IDs under movement, recolor, split, and merge;
- animation-frame handling;
- segmentation and diff invariants;
- row/column click convention;
- prompt token budgets and snapshot stability;
- stale-memory prevention;
- malformed JSON/code and self-repair;
- legal-action enforcement;
- macro interruption;
- undo accounting;
- repeated state-action detection;
- deterministic transcript replay;
- sandbox timeout/output limits;
- 110-game scheduling and failure isolation.

Add metamorphic tests: palette permutation, translation, reflection, object reordering, HUD relocation, and irrelevant distractors. Those are more useful OOD checks than adding more public-game-specific rules.

Treat “beat the public 25” as a release gate, not the optimization target. The official report explicitly warns that the public set is only a demonstration interface and is not representative of private performance. Your proxy transfer confirms this.

# 7. Cheapest kill-tests

| Option | Likely failure | Cheapest decisive test |
|---|---|---|
| Vision JSON policy | Reactive loops and coordinate mistakes | Measure repeated state-action rate, invalid clicks, and first-clear action count on 6 diverse games |
| Code REPL | Tool thrashing or syntax failures | Track useful inspection/action ratio, executable-call rate, timeout rate, and actions per successful hypothesis |
| Learned-controller hybrid | Replays traces instead of concepts | Apply controller to translated/recolored/relayout levels; require correct object rebinding and first-transition prediction |
| Baseline-first fallback | Stall detection occurs after score is lost | Replay logs with stall thresholds; compare against an oracle best-of-baseline/LLM router |
| Shadow solver | False applicability on OOD layouts | Require structural predicate and predicted first delta; abort on the first mismatch |
| Qwen | Vision/tool parser or FP8 instability | One Kaggle kernel: cold start, 100 multimodal tool calls, concurrent P95 latency, zero parser crashes |
| Gemma | Weaker code/world-model persistence | Same harness and prompts as Qwen; compare success and actions, not captions |
| gpt-oss | Text perception bottleneck and low headroom | Fixed segmentation transcripts; test whether reasoning gains offset loss of image input and throughput |
| Two-model ensemble | Little complementarity | Compute per-game oracle uplift before implementing routing |
| Reflection memory | Entrenches false theories | Measure contradiction recovery: inject/observe disconfirming transitions and verify hypothesis downgrade |

# 8. Three-round buildout

## Round 1 — Minimal reproducible Duck baseline

Build:

- transcript/replay format;
- segmentation/tracking;
- image renderer;
- stateless REPL;
- action governor;
- Qwen 3.6 FP8 vLLM deployment;
- compact eviction with no elaborate reflection.

Goals:

- zero serving/parser crashes;
- exact offline replay;
- measured P50/P95 latency at 8/12/16 concurrency;
- one paired public-25 result against ChainedAgent.

Kill the project early if Qwen cannot reliably emit executable tool calls or fit the runtime budget.

## Round 2 — Memory and exploration ablations

Add separately:

1. structured environment memory;
2. event-triggered compaction;
3. hypothesis predictions and contradiction tracking;
4. dead-intervention signatures;
5. guarded short macros;
6. L1 exploration/L2 transfer policy.

Run one-variable-at-a-time paired ablations. In a matched subset, compare:

- Qwen code-REPL;
- Qwen direct JSON policy;
- Gemma code-REPL;
- Gemma direct JSON policy.

This answers the architecture question on your own harness instead of importing the winners’ confounded ranking.

## Round 3 — Learned controller plus conservative portfolio

Add:

- environment-specific controller persistence across levels;
- object rebinding on new layouts;
- shadow proposals from existing mechanic solvers;
- prediction-gated handoff;
- global runtime scheduler and degradation modes.

Final ship gates:

- beats ChainedAgent on paired public-25 score;
- does not lose materially on metamorphic/OOD variants;
- completes a simulated 110-game run within 8 hours, preserving one hour of margin;
- no single game can crash or starve the run;
- later-level efficiency improves relative to L1, demonstrating actual knowledge reuse;
- baseline router uplift survives a realizable, non-oracle routing test.

The central bet is not “LLMs are now good at ARC.” It is narrower: **a multimodal coding model with free internal computation can infer an environment-specific program, and the composition of later levels lets that program amortize its discovery cost.** That bet is supported by M1. Exact replay, public mechanic families, and post-stall fallback are not.
tokens used
127,850
# Recommended design

