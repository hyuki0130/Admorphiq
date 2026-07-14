codex
Pick **(b): activate the pre-specified fallback**. The trace replay has already established the frozen stall predicates are structurally incapable of measuring this wall. Do not spend the run testing them.

### Final frozen triggers

| Cell factor | Eligibility | First fire | Cooldown | Maximum |
|---|---|---:|---:|---:|
| NAV | Current declared `GOAL_HYPOTHESIS` matches the existing frozen nav-signature | First model-decision boundary after declaration | 8 executed environment actions | 4/run |
| PLAN | Current declared goal **and milestone** are nonempty | First model-decision boundary after declaration | 15 executed environment actions | 2/run |

Both are unconditional subject to semantic eligibility, cooldown, and cap:

- Remove board-change, novelty, repeated-state, movement-stall, and level-stall predicates.
- Cooldowns count executed environment actions, not LLM/tool rounds.
- An injection consumes its cooldown and cap even if the model ignores the nudge.
- Level-up invalidates the active goal and eligibility until a new goal is declared. Per-run caps and cooldown history persist.
- Repeating the same declaration does not reset cooldown. Replacing it with a materially different qualifying goal makes it eligible, but does not bypass cooldown.
- Do not add an audit or extra call to solicit a goal; Audit remains OFF.

For NAV, remove the controller’s `has_traversability_graph` gate. The nudge’s purpose is to make the model construct `start`, `goals`, and `passable_mask`; inability or refusal to do that is treatment noncompliance to log, not grounds for suppressing treatment.

Keep the existing payloads unchanged:

- NAV: the current `shortest_path` nudge.
- PLAN: the current governed 2–5-step receding-horizon macro nudge.

### Combined cell

Keep independent cooldowns and caps, with at most one injection per model-decision boundary:

1. NAV has precedence when both are ready.
2. PLAN remains pending—it does not lose eligibility or consume budget.
3. PLAN fires at the next decision boundary if still eligible.

Thus the four cells remain the literal crossing of the two enabled flags; Base receives neither mechanism.

This is preferable to (d). “No level progress for 12 actions” is merely a delayed schedule because level progress is effectively the terminal outcome. It adds no diagnostic information, spends 12 permanently costly actions before treatment, and was not the pre-specified fallback.

Promotion gates, matched seeds, interleaving, budgets, payloads, and follow-up qualification remain unchanged. Before launching, replay the amended controller over the traces and require mechanically nonzero NAV and PLAN exposure; then freeze the commit and run.
tokens used
