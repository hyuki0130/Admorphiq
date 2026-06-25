---
type: lesson
date: 2026-04-23
rounds: R19
games: [KA59]
status: closed — diagnosis settled, no plan currently solves v2
---

# KA59 v2 added ACTION6 — directional probes go silent (R19)

> The `ka59-9f096b4a` (v1) → `ka59-38d34dbb` (v2) hash rotation
> didn't just rename attributes. It added `ACTION6` to the
> available-action set, and the underlying mechanic shifted so
> single direction presses no longer move any sprite. Probing
> with ACTION1-4 alone now returns `dir_transitions = 0/0/0/0`,
> which the dispatcher reads as "non-movement game" — wrong
> classification, downstream plan picks fail.

## What the raw probe showed

`scripts/probe_ka59_raw.py` bypasses `observation_phase` and
calls `env.step(GameAction.from_id(aid))` from a fresh reset for
each `aid in {1, 2, 3, 4}`. On `ka59-38d34dbb`:

```
KA59 ka59-38d34dbb base_levels=0 avail=[1,2,3,4,5,6,7]
base frame shape=(64, 64) unique_colors=[0, 2, 3, 4, ...]
  action 1: diff_pixels=0 state=NORMAL levels=0
  action 2: diff_pixels=0 state=NORMAL levels=0
  action 3: diff_pixels=0 state=NORMAL levels=0
  action 4: diff_pixels=0 state=NORMAL levels=0

-- action-pair sweep --
  1,1: diff_pixels=0 levels=0
  2,2: diff_pixels=0 levels=0
  3,3: diff_pixels=0 levels=0
  4,4: diff_pixels=0 levels=0
```

Zero pixels change under any direction press, single or doubled.
On v1 the same probe sequence produced 70+ pixel diffs per
direction (player avatar shifted one cell).

## Why it matters

The dispatcher's [[../concepts/probe_signature]] uniformity rule
reads:

> Uniform (ratio ≤ 2) → canonical movement game →
> `bfs_state_space` is the right primary.

The rule assumes `min(move_probes) ≥ 1`. On v2 KA59
`min == max == 0`, so the ratio is `0/0` (treated as ambiguous)
and the agent silently classifies the env as "click only" —
which then dispatches click-rare or paint-game heuristics, none
of which suit a sokoban. The brittle `strat_ka59_sokoban` with
its hardcoded L1-L4 push sequences was the only thing that
produced any clears on v1; on v2 the sequences are nonsensical
because the action mapping shifted.

## Concrete semantic shift

The `avail` list grew `[1,2,3,4,5,7]` → `[1,2,3,4,5,6,7]`. The
addition of `6` (click) co-occurs with an internal change where
plain direction presses no longer commit a move. The most likely
explanation (not yet confirmed by source-reading): v2 requires
the agent to *select* the player to move via ACTION6 before
ACTION1-4 will displace it, making it a 2-player cooperative
sokoban with an explicit selection step. The R19 hypothesis page
(in `.wiki/wiki/games/KA59.md`) calls this out as
"`(player, block_set)` state with explicit selection" — the
required state for a proper push-BFS plan.

## Falsification signature

`avail ⊇ {1,2,3,4,6}` AND every direction probe `diff_pixels = 0`
AND a single ACTION6 click on a movable cluster *does* produce
displacement on the *next* direction press. That signature
distinguishes "mechanic became movement+selection" from
"mechanic became click-only" — the dispatcher cannot route from
direction probes alone.

## Why this generalises

Any v2 hash that adds an action without removing an old one is a
candidate for this pattern. Probing the *old* actions gives a
silent profile, the dispatcher misclassifies, the brittle solver
fails, and the generic fallbacks have wrong priors. The fix is
not "ban brittle solvers" (that's R5) and not "loosen the
dispatcher" — it's "probe the new action *first* and feed the
result back into the dispatcher's signature."

## Decision

Document the falsification signature here so the runtime LLM
can recognise dir-zero KA59-class envs and request a probe pass
that includes ACTION6 *before* deciding the goal kind. The
proper plan (`_plan_push_bfs` with selection-aware state) is
queued for a future sprint; until then, KA59 v2 stays at 0.

## Related

- [[../games/KA59]]
- [[../lessons/v2_hash_obfuscation]] — the broader rotation pattern
- [[../lessons/api_hash_rotation_20260421]] — the day v2 dropped
- [[../lessons/sokoban_search_explosion_20260423]] — why naive BFS won't catch up
- [[../concepts/probe_signature]]
- [[../concepts/pushable_block]]

## Sources

- `scripts/probe_ka59_raw.py` — raw direction probe
- `scripts/probe_ka59.py` — instrumented inferential trace
- `scripts/inferential_direct_results.json` — KA59 6533 actions, 0 levels
- R19 commit `fcc39ea`
