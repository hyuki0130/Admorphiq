# Codex verdict — the EXPLANATION layer: harness-enforced protocol compiler (2026-07-15)

> Design consultation on teaching the weak offline LLM to use the kernel suite
> (user directive: tools clear the publics + explain them to the local model).
> Verdict: protocol compiler with typed intents + enforced state machine, NOT a bigger wiki.

## Verdict

Build the EXPLANATION layer as a **harness-enforced protocol compiler**, not a larger wiki.

The 27B model should choose semantics—roles, hypotheses, goals—but it should not need to remember kernel names, reproduce invocation syntax, or voluntarily follow a checklist. Once it declares an intent, the harness must validate the declaration, invoke the kernel automatically, and constrain the next response to either use or explicitly reject the result.

That is the only design consistent with the measured schema-enforcement history and the current zero-adoption failure. The existing NAV treatment is still advisory prose layered onto free-text declarations ([agent.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/repl_agent/agent.py:107)); the R56 target already calls for automatic invocation after typed declaration ([verdict](/Users/nhn/Workspace/Admorphiq/docs/r56_codex_toolbase_verdict_20260715.md:68)).

## 1. Artifact stack, in priority order

| Priority | Artifact | Expected behavioral effect |
|---|---|---|
| P0 | Typed intent schemas + enforced state machine | Largest. Eliminates invalid names, forgotten calls, missing slots, and silent ignoring of results. |
| P1 | Mechanic-family protocol cards | Teaches how to gather evidence, fill semantic slots, order kernels, manage memory, and falsify a family. |
| P2 | Executable win-condition typology | Forces contrasting goal hypotheses and automatically runs cheap detectors; prevents “I never considered that goal type.” |
| P3 | Abstracted worked packets | Helps imitation and schema completion. Useful only after the interface is constrained; dangerous as raw public-game transcripts. |
| Never runtime-visible | Raw adapter journeys, game pages, catalog prose | Valuable provenance for humans/compiler input, but too long and too anchoring for the model. |

Intent schemas are infrastructure, not optional explanatory prose. Use them identically in both arms of the later content A/B.

### Proposed artifact tree

```text
explanation/
  manifest.yaml
  intents/
    select.schema.json
    navigation.schema.json
    transform_match.schema.json
    toggle_linear.schema.json
    rewrite.schema.json
    ...
  playbooks/
    navigation.yaml
    click_induced_motion.yaml
    toggle_linear.yaml
    rare_target_probe.yaml
    ...
  goals/
    typology.yaml
    detectors/
      elimination.yaml
      uniformity.yaml
      pattern_match.yaml
      containment.yaml
      arrival.yaml
      ...
  examples/
    navigation.jsonl
    toggle_linear.jsonl
    ...
  provenance/                 # BUILD-ONLY; excluded from Kaggle package
    adapter_lessons/*.yaml
```

Add a packaging lint that rejects runtime artifacts containing public game IDs/titles, adapter imports, absolute coordinates, fixed palettes, or provenance text.

## 2. Enforced runtime protocol

Use a two-stage decoder contract rather than one large `oneOf` schema.

1. **SELECT_INTENT**

   Decoder enum over a short dynamic allowlist:

   ```json
   {
     "intent": "navigation | toggle_linear | click_motion | transform_match | rewrite | unknown",
     "support": ["evidence:17", "evidence:22"]
   }
   ```

2. **FILL_INTENT**

   The chosen intent becomes a single-item allowlist, and only its schema is exposed. Navigation, for example:

   ```json
   {
     "intent": "navigation",
     "mover": "region:7",
     "start": "cell:12",
     "goals": ["cell:31"],
     "passable_mask": "mask:4",
     "action_map": "action_map:2",
     "goal_hypothesis": "goal:3",
     "support": ["evidence:17", "evidence:22"],
     "falsifier": "mover_does_not_follow_planned_step"
   }
   ```

   Semantic fields should reference harness-owned observation objects where possible. Do not ask the model to print a 64×64 mask.

3. **COMPUTE**

   The harness validates references and automatically calls the mapped kernel. Invalid declarations cause no environment action; return a compact missing/contradictory-slot repair packet.

4. **CONSUME_RESULT**

   The next decoder schema permits only:

   ```json
   {"decision":"execute","plan_id":"p8","step":0}
   ```

   or:

   ```json
   {
     "decision":"reject",
     "plan_id":"p8",
     "contradiction":"evidence:29",
     "next_intent":"unknown"
   }
   ```

   This prevents the current “tool result was available but the model ignored it” failure. A result cannot be bypassed by an unrelated action.

5. **VERIFY**

   After execution, the harness evaluates the declared prediction and the playbook’s falsifiers. Strong contradictions revoke the intent immediately; repeated weak contradictions consume a small strike budget and then revoke it.

Schemas enforce procedure, not semantic correctness. The `unknown`/probe escape route is mandatory so a wrong family is never forced indefinitely.

## 3. Mechanic-family playbooks

Write playbooks as machine-readable protocol cards, not essays:

```yaml
id: click_induced_motion.v1
activation:
  requires_all:
    - legal_action.mouse
    - discrete_regions_present
  supporting:
    - click_offset_correlates_with_region_motion
    - source_motion_points_toward_click
  contraindications:
    - two_click_sequence_required_for_any_motion

roles:
  required: [source_region, destination_relation]
  hypotheses_only: [container, merge_partner]

confirm:
  probe: click_ahead_of_source
  prediction: source_region_moves_toward_click
  max_attempts: 3

pipeline:
  - op: find_regions
  - op: track_objects
  - op: motion_vectors
  - op: point_toward

decision_rules:
  - when: source_did_not_move
    do: increase_absolute_offset
  - when: source_vanished_near_partner
    do: count_as_successful_merge

falsification:
  strong:
    - second_click_moves_previously_selected_object_but_first_click_never_does
  weak:
    - tracked_source_does_not_move_as_predicted
  weak_strikes: 2
  on_reject: return_to_intent_selection

memory:
  game_scope: [effective_offset]
  level_scope: [role_assignments, dead_sources]
  attempt_scope: [pending_prediction]

budgets:
  confirmation_actions: 3
  committed_actions_before_recheck: 2
```

Required fields for every playbook:

- Observable activation and contraindication predicates.
- Required semantic roles and slots.
- One cheapest discriminating probe.
- Ordered kernel pipeline.
- Decision table, not narrative recommendations.
- Strong and weak falsifiers.
- Action/strike budget.
- Memory lifetime: action, attempt, level, or game.
- Recovery transition.
- Build-only provenance and supersession version.

### Important SU15 correction

Do not publish “fraction-of-remaining-distance escalation” as the final transferable lesson. The current iteration explicitly falsifies that parameterization: as the source approaches its target, the absolute offset shrinks below the effective threshold. The corrected lesson is **adaptive absolute click-ahead distance**, with source-specific outcome attribution ([su15.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/adapters25/su15.py:21)).

This demonstrates why playbooks need versioned provenance and falsification. Adapter prose should be compiled only after the latest measurement supersedes earlier lessons.

Other strong transferable lessons include:

- Toggle systems: derive candidates from rendered regions, identify the observationally active subset, measure a self-inverse stencil, then solve declared target hypotheses ([ft09.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/adapters25/ft09.py:24)).
- Navigation: keep learned controls at game scope, spatial passability at level scope, and hazard memory across restarts within the same level ([m0r0.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/adapters25/m0r0.py:36)).
- Outcome attribution must track the intended source object; “something somewhere changed” is insufficient evidence.

## 4. Win-condition typology

Do not make the model read a prose checklist of every goal type.

Turn R57 into an executable `GoalLedger`:

- At first observation, after a material transition, and after level-up, automatically run all cheap zero-action detector sketches.
- Return only the top evidence and contradictions, capped to a few entries.
- Require either two distinct competing goal hypotheses or an explicit `insufficient_evidence` declaration.
- Keep `unknown` available.
- Goal type and mechanic intent must remain separate. “Arrival” does not imply ordinary navigation; “uniformity” does not prove GF(2).

Example result:

```json
{
  "goal_candidates": [
    {"id":"goal:3","type":"containment","support":["e12","e18"],"against":["e21"]},
    {"id":"goal:4","type":"elimination","support":["e18"],"against":[]}
  ],
  "unresolved_tests":["whether region:7 must vanish or enter region:2"]
}
```

R57 currently contains 67 level-up events across 24 games; TR87 has no extracted event. Treat this as provisional mining coverage, not a completed runtime typology. An entry should not ship until its detector can consume pre-clear observable state without relying on the level-up label.

## 5. Injection policy

| Time | Inject |
|---|---|
| Persistent system prompt | Objective, action discipline, protocol states, requirement to cite observation handles. No catalog or playbooks. |
| First frame/material change | Neutral signature digest and compact GoalLedger output. |
| Intent selection | Dynamic enum only; ideally 3–6 relevant computation intents plus `unknown`. No mechanic advice yet. |
| After intent declaration | One selected playbook, its slot schema, and relevant kernel contract. |
| After kernel execution | Compact result with `plan_id`, assumptions, and predicted first-step effect. |
| Schema/semantic repair failure | One abstract worked packet for that exact intent. |
| Level-up | Drop level-scoped roles and plans; retain only explicitly game-scoped learned dynamics. |

Budgets:

- Persistent protocol: ≤450 tokens.
- Signature/goal digest: ≤250 tokens.
- Selected playbook: ≤500 tokens.
- Kernel result: ≤300 tokens.
- Worked packet: ≤350 tokens, first activation or repair only.
- Never inject the full catalog or more than one playbook.

Retrieval-on-signature should retrieve neutral evidence/questions before selection. Actual “how to solve this family” content belongs after intent declaration, otherwise retrieval itself becomes the anchor.

## 6. Grounding and falsification

Key playbooks on causal signatures, not appearance:

- Navigation: directional actions repeatedly displace a tracked region and blocked moves produce no displacement—not “looks like a maze.”
- Toggle-linear: repeated clicks have stable XOR-like footprints and two identical clicks restore state—not “looks like a button grid.”
- Click-induced motion: offset clicks move the tracked source toward the click—not “large region probably means goal.”
- Rewrite: stable token groups and measured rewrite relations—not “top panel resembles TR87.”

Enforce these rules:

- Appearance-only evidence cannot activate a family.
- At least two independent support signals, or one strong discriminating transition, are required.
- Support and contradictions must be observation handles, not prose claims.
- Every committed hypothesis has a bounded verification horizon.
- One failed defining invariant or two failed ordinary predictions forces decommitment.
- The harness, not the model, manages strike counts and memory resets.
- Every playbook must name the next alternative state; “try harder” is invalid.

Worked examples should be counterfactualized packets: remove title/image/full grid, remap colors and coordinates, retain only roles, relations, evidence handles, schema output, kernel result, and verification outcome. Include one success and one falsification example per family.

## 7. Agent25 A/B

Keep declared-intent enforcement identical in both primary arms:

- **D0:** typed intent + validation + automatic kernel invocation, but only raw slot definitions.
- **D1:** same substrate plus GoalLedger, post-intent playbook, and repair-only worked packet.

This isolates the knowledge layer. Run free-text versus typed-intent separately as an interface preflight, not as the explanation-content A/B.

### First games

Start with:

- Targets: `ls20`, `g50t`, `tu93`—the diagnosed navigation walls.
- Regression guards: `r11l`, then `su15`.
- Three matched replicates, interleaved, same seeds/model/temperature/wall time/action cap.

After the navigation slice, add `m0r0`, `ft09`, `su15`, and `lp85` as mechanic-family qualification cases, then matched12 and full `agent25`.

### Metrics and gates

Measure the adoption funnel:

1. Pre-registered signature opportunity.
2. Intent selected.
3. Semantic slots valid.
4. Kernel automatically invoked.
5. Result consumed or evidencefully rejected.
6. Predicted effect verified.
7. Intent abandoned when its falsifier fires.

Adoption is a fidelity gate, not a promotion outcome:

- ≥95% decoder/schema validity.
- ≥80% semantically valid intent packages on eligible opportunities.
- 100% invocation after a valid declaration.
- ≥80% result consumption/rejection compliance.
- Material improvement over D0 in slot validity or result use.

Promotion still requires hard outcomes:

- A new formerly-zero level/clear reproduced in at least 2/3 runs.
- Positive median faithful-RHAE delta on at least two of the three target games.
- No lost guard clear.
- Aggregate RHAE non-inferior; >20% throughput loss requires a reproduced new clear.
- Full `agent25` non-inferiority and no hidden/proxy-transfer regression.

In short: **adoption diagnoses whether the interface worked; new walls prove capability; RHAE decides whether it ships.**

## 8. Sequencing and first 1-day build

Do not change engagement or basenav while running.

Interpret basenav diagnostically:

- `nav_fires == 0`: the missing component is forced intent/goal declaration.
- NAV fires but no call: automatic invocation is necessary.
- Calls occur with invalid masks/roles: slot schemas and protocol card are necessary.
- Valid paths are returned but ignored: enforce `CONSUME_RESULT`.
- Paths are followed but do not help: the navigation semantics or applicability evidence is wrong.

The first 1-day artifact should be **Navigation Vertical Slice v0**, not a broad playbook library:

- `select.schema.json`
- `navigation.schema.json`
- `navigation.yaml`
- One abstract success packet and one wrong-navigation/falsification packet.
- Harness states `SELECT → FILL → COMPUTE → CONSUME → VERIFY`.
- Telemetry for the full adoption funnel.
- Tests proving invalid declarations spend zero actions, valid declarations auto-call the kernel, arbitrary result bypass is rejected, and falsifiers decommit.
- Quarantine lint proving no game identity or adapter content enters the runtime package.
- Replay against existing basenav transcripts, followed by the matched live A/B only after basenav lands.

Continue R56 adapters in parallel, but require every iteration to emit a build-only lesson record with `observed`, `hypothesis`, `result`, `supersedes`, `generalizable_protocol`, and `nontransferable_details`. That gives you a disciplined pipeline from measured adapter knowledge to safe runtime cards without turning the 25 publics into a second hidden selector.
