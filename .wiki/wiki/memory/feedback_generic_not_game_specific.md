---
name: Stay Generic, Not Game-Specific
description: When strengthening math/algorithm layers, every decision branch must run on frame observations or feature signatures, never game-title strings
type: feedback
originSessionId: eba5cc76-48c0-4391-bce2-39b48288934e
---
When a new algorithm or plan fn is being added, verify that every
conditional branch in the logic reads only from:

- frame pixels / cluster extraction
- observable feature signatures (`merge_items` count, `probe_diffs`,
  `click_responsive_cells`, `dir_map`, etc.)
- entity-map outputs (`player`, `executors`, `palettes`,
  `goal_regions`)

NOT from `game_title` or `game_id`. Title strings may only appear
in provenance comments describing WHICH trace validated the logic;
they must never reach `if ... ==` or dict keying.

**Why**: Kaggle private test set has no title parity with preview
games. Title-based dispatch scored 37 levels in round 3 bench but
collapsed on v2 hashes and would collapse harder on private test.
Rounds R4+ enforce Wiki-First Routing; R16-R22 extended the same
discipline to low-level plan-fn heuristics.

**How to apply**: before committing any new conditional, grep the
new code for title-like tokens (game abbreviations, sprite tag
names). If found in conditionals, rewrite as a feature-signature
check. If the feature doesn't exist yet, add it to
`DiscoveryReport` or `entity_phase` first.

**Example violations to watch for**:
- `if game_title == "SU15": ...` — banned
- `if "paint" in game_name: ...` — banned
- `if sprite_has_tag("Hkx"): ...` — banned (internal access)

**Example permitted patterns**:
- `if len(entity_map["merge_items"]) >= 3: ...` — feature signature
- `if goal["kind"] == "navigation": ...` — goal-phase classifier
- `if A.sum() / n**2 > 0.8: return False  # coupled display` —
  measured observable

Rounds R16-R22 (2026-04-23): all math additions (`_measure_toggle_stencil`,
`_gf2_solve`, `_rank_subsets_by_prediction`, prefix-aware
`_plan_navigation`, loosened `merge_items` threshold) pass this
check. The user's repeated concern ("수학적 함수 강화한다면서 또
게임에 따라 맞춰서 코딩하고 범용적이지 않게 만드는거 아니지?")
is the enforcement standard.
