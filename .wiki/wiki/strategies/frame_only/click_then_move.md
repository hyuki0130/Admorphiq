---
type: strategy
name: click_then_move
generalizes: yes
implementation: src/admorphiq/strategies/inferential.py::_plan_click_then_move
dispatched_from: inferential_agent.PLAN_FNS["click_then_move"]
---

# click_then_move (plan fn)

> R13 plan for hybrids where a button press + 2-3 step movement
> clears the level (CD82 pattern: click top arrow at (37,4) advances
> game state, then left/right movement positions the player). HUD
> masking (R12) is what makes this plan viable — without it every
> click looks responsive and the top-K selection is dominated by step
> counters.

## Applies When

- `goal["kind"] ∈ {navigation, paint_fill, click_then_move}` (often
  routed as a fallback when navigation alone misses).
- `avail ⊇ {1..4, 6}` — both directional movement and click.
- HUD-masked click probes show ≥ 1 cell with `diff_magnitude ≥ 10`.

## Algorithm

1. Filter clicks to `meaningful = [c for c in clicks
   if diff_magnitude ≥ 10]`, sort descending, take top 6.
2. Get directional actions `dir_actions = [a for a in scalar
   if 1 ≤ a ≤ 4]`. If empty, return `(0, 0)`.
3. Pass 1 (single-button + ≤ 2 movement steps):
   - For each button c in meaningful:
     For d1 in dir_actions ∪ {None}:
       For d2 in dir_actions ∪ {None}:
         Reset, click c, then act d1 (if not None), act d2 (if not None).
         On level advance, return success.
4. Pass 2 (two-button + ≤ 1 movement step):
   - For each (a, b) in meaningful × meaningful (i ≠ j):
     For d in dir_actions ∪ {None}:
       Reset, click a, click b, optionally act d.
       On level advance, return success.
5. Return `(base_levels, used)` on bail.

## Why It Generalizes

- HUD-masked diff_magnitude is a frame-level signal, not a game
  internal.
- Directional action set comes from `available_actions`, not hardcoded.
- Pass-1 / pass-2 structure handles both single-button games (click
  arrow + nudge) and dual-button games (select target + commit).

## Observable Signature

- `avail ⊇ {1..4, 6}`.
- HUD-masked click probe shows ≥ 1 cell with `diff_magnitude ≥ 10`.
- Direction probes uniform (ratio ≤ 2) so player movement is real.
- Cluster centroids include at least one outside the HUD-mask zone
  (i.e., the button is a real interaction point, not a counter).

## Falsification Signature

- `meaningful = []` (every click probe filtered out post-HUD-mask):
  no real buttons; route to [[toggle]] or [[lights_out]].
- `dir_actions = []`: no directional movement; route to [[paint_fill]]
  or [[toggle]].
- Both passes exhausted with `levels = 0`: composition isn't
  click-then-move — try [[paint_fill]] (click → executor) or
  [[navigation]] (pure dir-BFS with click_coords).

## Tunable Parameters

- `top_K` meaningful clicks: 6. Effect: more covers wider button sets;
  larger K explodes pass-1 to `K × |dir|² × 4` resets.
- Movement depth: 2 (pass 1) / 1 (pass 2). Effect: 3-step pass adds
  another factor `|dir|`.
- `diff_magnitude` filter threshold: 10. Effect: lower includes
  marginal cells (post-HUD they're often valid); higher tightens.
- Pass 2 enabled by default. Effect: doubles button-pair search; turn
  off for budget-tight runs.
- HUD mask threshold (set in `observation_phase`): 0.8 (cells changing
  under ≥ 80% of probes flagged as HUD). Effect: lower mask catches
  more counters; higher misses subtle counters.

## Next-Best

When the falsification signature triggers:

- [[paint_fill]] — when palettes/executors emerge on the retry
  observation (palette pattern wasn't visible on first probe).
- [[navigation]] — when pass-1/pass-2 budget exhausted but
  `_ACTIVE_PREFIX` isn't propagating (try direct nav with click_coords
  injected).
- [[toggle]] — when meaningful clicks exist but movement isn't required
  (level advances on click alone with no nudge).

## Limitations

- Pass 1 has `K × |dir|² × 4` reset-replay cost — on a 4-direction game
  with K=6 that's 96 × replay-prefix-cost per attempt cluster.
- Two-button / one-step in pass 2 is not commutative with movement
  (some games require move-then-click-then-move which isn't enumerated).
- HUD masking has thresholds that occasionally false-positive a real
  button (mask threshold 0.8, see Tunable Parameters).

## Related

- [[navigation]] — peer plan; use this when navigation alone fails on
  hybrids.
- [[paint_fill]] — peer plan with palette/executor structure.
- [[../../lessons/cd82_paint_palette_signature_20260423]] — HUD-mask
  observation enabling this plan.
- [[inferential_agent]] — outer loop.
- [[../../games/CD82]] — canonical instantiation.

## Sources

- `src/admorphiq/strategies/inferential.py:1313-1404`
- R12 HUD mask commit `84e53d1`
- R13 commit `a70bf92`
- `scripts/probe_cd82.py` — instrumented trace
