codex
# Binding verdict

Ship a **generic perception-and-computation REPL**, not a no-tools REPL and not a solver portfolio. Generic tools may describe evidence or solve a problem explicitly formulated by the LLM; they must not infer the game’s goal, mechanic, applicability, or next action.

## 1. Round‑1 namespace

Exact default namespace:

```text
objects(), crop(), ascii(), mask(), compare(), relations()
shortest_path(start, goals, passable_mask)
action_outcomes(state=None), is_dead(action, state=None)
action(...)
```

| Candidate | R1 verdict | Binding design |
|---|---:|---|
| Segmentation/tracking | **SHIP** | Core substrate. Preserve raw crops and masks so the LLM can reject bad object boundaries. This is consistent with Duck’s actual positive finding. |
| Dead-signature tracking | **SHIP, revised** | Expose observed `(canonical state, exact action) → outcomes`. Keep the governor’s exact repeat rejection. Coarse click-block suppression is advisory only. Do **not** ship the current six-attempt, 8×8-block policy unchanged; it is redundant with the governor and spends too many actions before helping. |
| BFS-to-cell | **SHIP** | Pure `shortest_path()`. The LLM must supply start, goals, and passability. The tool must not decide which object is the player, which cell is the goal, or which colors are walls. |
| Graph-frontier explorer | **DO NOT SHIP** | Generic in code, but it is an autonomous action policy optimizing novelty. Its measured action explosions make it unsuitable for RHAE. Keep it offline for transcript analysis only. |
| Click-sweep heuristic | **DO NOT SHIP** | No blind lattice/raster probing. Keep segmentation-derived `safe_click` coordinates and let the LLM select among them. |
| Mechanic-family solvers | **NOT IN THE NAMESPACE** | Run log-only in shadow if useful for evaluation; do not put their proposals in the prompt. “Zero-action” prevents direct damage but not anchoring. Their 13% hidden transfer is insufficient. Later, test an explicitly requested `shadow_proposals()` call as a separate ablation. |
| Learned/synthesized dynamics | **NOT R1** | Add as a Round‑2 feature flag, described below. Do not contaminate the currently running baseline. |

This narrows the earlier R55 design: its inspection API remains correct, but the proposed shadow-solver portfolio should not be model-visible by default. See the existing [R55 module boundary](/Users/nhn/Workspace/Admorphiq/docs/r55_codex_design_consultation_20260714.md:94).

The game-specific line is crossed when shipped code contains any of:

- game IDs, known layouts, palette/coordinate constants, mechanic-family routing;
- built-in assumptions about player, target, reward, or progress;
- an applicability classifier that selects a solver or action;
- public-game traces or templates.

A per-game helper learned from live evidence may become game-specific. That is acceptable because it is created online, auditable, reversible, and deleted at the game boundary.

## 2. Minimal tool-evolution experiment

Build **per-game persistent pure helpers**, surviving turns and levels but never games.

Minimal API:

```text
define_helper(name, source, tests, description)
helpers()
drop_helper(name)
```

Rules:

- Helpers accept explicit Inspector data and return JSON-serializable results.
- No `action()`, environment access, filesystem, network, or mutable hidden state.
- Maximum 8 helpers / 8 KB total.
- Compile and tests must pass in the restricted sandbox.
- Version every change; automatically roll back a failing revision.
- Inject accepted helpers into subsequent stateless REPL calls.
- Record definitions, revisions, invocations, failures, and whether results informed an action.

Do **not** start with dev-time global library evolution. It confounds releases and invites public-game overfitting. Promote a helper globally only later, after human review and held-out metamorphic/cross-game evidence.

Cheapest credible experiment: an 8-game paired multi-level A/B using the same model, decoding, budgets, and game set:

- A: current REPL.
- B: current REPL plus persistent helpers.

Scale it only if:

1. A valid helper is reused on at least two later decisions, including a later level, in at least 3/8 games; and
2. B improves aggregate L2+ RHAE by at least 5%, **or** reduces L2+ model calls by at least 15% with no loss in clears or RHAE.

If either condition fails in two matched runs, kill runtime tool evolution. Transcript replay alone can validate mechanics, but cannot establish performance signal.

## 3. Learned WM as a tool

**Yes: Round 2 should include it as a single-factor ablation. It is not inherently the specific-tool trap.**

But do **not** expose the current `WorldModelTool` unchanged. It embeds “more foreground objects = progress” and autonomously proposes probes/actions, which turns a dynamics model into a questionable policy [here](/Users/nhn/Workspace/Admorphiq/src/admorphiq/tools/world_model.py:18) and [here](/Users/nhn/Workspace/Admorphiq/src/admorphiq/tools/world_model.py:188).

Replace that surface with:

```text
predict(action) -> {
  status: known | unknown,
  support,
  p_change,
  expected_changed_bbox,
  expected_object_relation_deltas,
  possible_next_signatures,
  confidence
}
```

Binding constraints:

- Automatically fit from this game’s observed transitions.
- Return `unknown` for unsupported counterfactuals; never fabricate a neutral prediction.
- No progress scalar, goal inference, candidate generation, action ranking, or governor veto.
- Use predictions only for LLM planning and macro stop-on-surprise.
- Keep exact-state statistics level-local; retain only abstract action/effect regularities across levels.
- Test R28 first. Do not ship the EWM exact-frame synthesizer until it beats R28 on **prequential action-effect prediction**, not just frame reconstruction.

Tolani validates the learned-WM design class, not your existing R28 implementation. Kill the R28 overlay if confident predictions cover under 20% of evaluation transitions or have under 80% change/no-change accuracy, or if the interactive A/B does not improve RHAE.

## 4. Ship gate and ablations

The current Round‑1 ship gate does **not** move. Finish and preserve the running Qwen baseline. Tool evolution, WM, graph exploration, and solver proposals must not block it.

Add only two namespace gates:

- every R1 helper passes palette/translation/reflection/HUD metamorphic tests;
- no helper other than `action()` can request or select an environment action.

Keep the original Qwen/Gemma × REPL/JSON 2×2. Give all four arms the same rendered image and structured segmentation packet so perception is not the hidden confound.

After selecting the best cell, run sequential overlays:

1. core vs `+persistent_helpers`;
2. core vs `+passive_WM`;
3. only if both win independently, test `+helpers+WM`;
4. test model-visible mechanic proposals separately.

Do not expand the primary 2×2 into a combinatorial tool matrix. The corrected conclusion is:

> **Generic perception and explicit computation ship. Learned per-game machinery is measured next. Handcrafted semantic policies remain outside the default agent.**
tokens used
53,240
# Binding verdict

Ship a **generic perception-and-computation REPL**, not a no-tools REPL and not a solver portfolio. Generic tools may describe evidence or solve a problem explicitly formulated by the LLM; they must not infer the game’s goal, mechanic, applicability, or next action.

## 1. Round‑1 namespace

Exact default namespace:

```text
objects(), crop(), ascii(), mask(), compare(), relations()
shortest_path(start, goals, passable_mask)
action_outcomes(state=None), is_dead(action, state=None)
action(...)
```

| Candidate | R1 verdict | Binding design |
|---|---:|---|
| Segmentation/tracking | **SHIP** | Core substrate. Preserve raw crops and masks so the LLM can reject bad object boundaries. This is consistent with Duck’s actual positive finding. |
| Dead-signature tracking | **SHIP, revised** | Expose observed `(canonical state, exact action) → outcomes`. Keep the governor’s exact repeat rejection. Coarse click-block suppression is advisory only. Do **not** ship the current six-attempt, 8×8-block policy unchanged; it is redundant with the governor and spends too many actions before helping. |
| BFS-to-cell | **SHIP** | Pure `shortest_path()`. The LLM must supply start, goals, and passability. The tool must not decide which object is the player, which cell is the goal, or which colors are walls. |
| Graph-frontier explorer | **DO NOT SHIP** | Generic in code, but it is an autonomous action policy optimizing novelty. Its measured action explosions make it unsuitable for RHAE. Keep it offline for transcript analysis only. |
| Click-sweep heuristic | **DO NOT SHIP** | No blind lattice/raster probing. Keep segmentation-derived `safe_click` coordinates and let the LLM select among them. |
| Mechanic-family solvers | **NOT IN THE NAMESPACE** | Run log-only in shadow if useful for evaluation; do not put their proposals in the prompt. “Zero-action” prevents direct damage but not anchoring. Their 13% hidden transfer is insufficient. Later, test an explicitly requested `shadow_proposals()` call as a separate ablation. |
| Learned/synthesized dynamics | **NOT R1** | Add as a Round‑2 feature flag, described below. Do not contaminate the currently running baseline. |

This narrows the earlier R55 design: its inspection API remains correct, but the proposed shadow-solver portfolio should not be model-visible by default. See the existing [R55 module boundary](/Users/nhn/Workspace/Admorphiq/docs/r55_codex_design_consultation_20260714.md:94).

The game-specific line is crossed when shipped code contains any of:

- game IDs, known layouts, palette/coordinate constants, mechanic-family routing;
- built-in assumptions about player, target, reward, or progress;
- an applicability classifier that selects a solver or action;
- public-game traces or templates.

A per-game helper learned from live evidence may become game-specific. That is acceptable because it is created online, auditable, reversible, and deleted at the game boundary.

## 2. Minimal tool-evolution experiment
