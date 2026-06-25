---
type: lesson
date: 2026-06-25
rounds: R16
severity: warn
first_seen: 2026-06-25 round 16 14B bench
status: resolved — reorder reverted, proven order restored
---

# Front-Loading Env-Specific Seeds Regressed 14B Routing (R16)

> Reordering `derive_seed_pages` to place env-specific seeds (game_type /
> concept / `games/<TITLE>`) BEFORE the generic prose pages (selector +
> reasoning) lost 6 levels on the 14B bench (14 → 8). The proven order —
> decision_tree, failure playbook, selector, reasoning, THEN env-specific
> last — was restored. Seed ORDER is a benched decision, never a hunch.

## Symptom

After the R16 seed reorder, the 14B WikiAgent bench cleared 6 envs / 8
levels, down from the R23 14B reference's 10 envs / 14 levels (same model,
same envs). Regressions on LS20, M0R0, SC25, SP80. The primary-strategy
distribution shifted: `click_select_move` 12 → 0, `click_toggle_detect`
4 → 19.

## Root Cause

`derive_seed_pages` was changed (B2) so env-specific seeds were placed
right after the compact `decision_tree`, ahead of `selector.md` and the
reasoning chain. The hypothesis was that an 8B/14B reader, whose attention
degrades with position, should see the highest-signal pages for THIS env
first ("Finding 1": seeds saturate the char budget, so late seeds get
truncated).

The hypothesis was wrong for routing. Demoting `selector.md` and the
reasoning chain below the env-specific pages removed the dispatch prose
that steers Qwen toward `click_select_move`; with the game_type page
leading instead, the model anchored on `click_toggle_detect`, which clears
fewer of these games. The generic dispatch scaffolding being read EARLY
matters more than the env-specific page being read early.

## Prevention

- Seed ORDER in `wiki_retrieval.derive_seed_pages` is a benched decision.
  `architecture.md`: "changing the order requires re-measuring
  classification accuracy." Never ship a reorder on intuition.
- "Finding 1" (backlink graph barely traversed at runtime; seeds saturate
  budget) is a real observation but does NOT imply env-specific seeds
  should lead. The generic dispatch prose (`selector`, reasoning) is the
  routing backbone and must stay near the front.

## Recovery

Reverted `derive_seed_pages` to the proven order: `decision_tree`,
`debug/plan_failure_signatures`, `selector`, `reasoning/frame_to_strategy_chain`,
`reasoning/discovery_phase`, THEN env-specific seeds appended last. A
confirmation bench (B2 reverted, graph hygiene + 5 new strategy pages kept)
returned 10 envs / 14 levels with the identical primary-pick distribution
to the R23 reference — proving the reorder was the sole cause and the
graph-hygiene changes are routing-neutral.

## Falsification

If a future bench shows env-specific-first seeding ≥ the proven order on
BOTH 8B and 14B across ≥ 2 runs, this lesson is wrong and the reorder
should return. Until measured, env-specific seeds stay last.

## Related

- [[../reasoning/wiki_retrieval_recipe]]
- [[api_hash_rotation_20260421]]
- [[selector_is_advisory_not_enforced_20260421]]
- [[../strategies/frame_only/click_then_move]]
