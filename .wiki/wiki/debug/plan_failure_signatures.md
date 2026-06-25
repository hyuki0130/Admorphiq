---
type: debug
trigger_symptom: plan fn returned 0 levels OR levels stuck after one clear
affects: all strategies/frame_only plan fns
---

# Plan-Failure Signatures — One-Page Lookup

> When a plan fn returns 0 levels, the runtime LLM (R7f multi-turn,
> R23+) reads the failure envelope (`actions used`, `elapsed`,
> `attempted_plans`) and decides whether to swap. This page is the
> compact lookup the LLM consults: per plan, what failure shape it
> emits, and which next-best plan to try.

Each row in the table below is a **falsification signature** — an
observable pattern in the trace that means "this plan is the wrong
fit, swap." The plan's own page
(`strategies/frame_only/<name>.md`) carries the full Observable /
Falsification / Tunable / Next-Best detail; this page is for fast
runtime reasoning when the trace is already in front of you.

## Failure-mode taxonomy (per [[../lessons/inferential_budget_vs_algo_20260423]])

| Mode | Trace signal | What it means |
|---|---|---|
| **Early bail** | `actions ≪ budget`, `elapsed < 1 s`, `levels = 0` | Plan saw entry conditions failing (e.g., no merge pair, no palette) — preserve budget, swap |
| **Search ceiling** | `actions` mid-range, `elapsed > 30 s`, `levels = 0` | Algorithm exhausted state cap — wrong encoding, swap to domain-aware plan |
| **Budget exhausted** | `actions ≈ cap`, `elapsed ≤ time_limit`, `levels = 0` | Algorithm running but not converging — extend per-plan cap or swap to lighter peer |
| **Stuck post-clear** | `levels = 1`, next obs cycle also returns 1 | Multi-level chaining broken; check `_ACTIVE_PREFIX` is being honored |

## Per-plan failure → next-best

### [[../strategies/frame_only/navigation]]

| Failure signature | Likely cause | Try next |
|---|---|---|
| `actions ≪ cap`, `elapsed < 1 s` | `avail_scalar` empty AND no click | early-bail; not a movement env. Try `merge` or `paint_fill` |
| `actions ≈ max_states`, `elapsed ≥ time_limit` | search ceiling — Sokoban-like state space | `bfs_state_space` with bumped `max_states`; if multi-player, no current plan ([[../lessons/sokoban_search_explosion_20260423]]) |
| All four dir probes `diff_pixels = 0` | KA59-v2 dir-silent | re-probe with ACTION6 first ([[../lessons/ka59_v2_action6_semantic_20260423]]) |
| `levels = 1` repeats across obs cycles | prefix not extending ([[../lessons/prefix_aware_navigation_20260423]]) | inspect `_LAST_WIN_SEQUENCE` extension; do NOT re-pick navigation |
| Click responsive ≥ 3 high-diff cells, dir uniform | hybrid that pure-nav misses | `click_then_move` |

### [[../strategies/frame_only/merge]]

| Failure signature | Likely cause | Try next |
|---|---|---|
| Returns `(base, 0)` instantly | `merge_items` empty or len < 2 | not a merge env; try `paint_fill` or `toggle` |
| Returns `(base, k<50)` | no same-color pair at this state ([[../lessons/su15_l1_singleton_colors_20260423]]) | requires downgrade-then-merge primitive (no plan yet); fall back to broader exploration |
| `attempt cap (40)` reached | pairs exist but radius wrong, or sort-mechanic | `paint_fill` or `toggle` (different mechanic class) |

### [[../strategies/frame_only/paint_fill]]

| Failure signature | Likely cause | Try next |
|---|---|---|
| Returns `(base, k<50)` | no palette OR target_color = background | `toggle` (palette absent) |
| All 3×12×2 combos exhausted | composition wrong (palette → cell → executor isn't the right order) | `click_then_move` for CD82-style L2+ ([[../lessons/cd82_paint_palette_signature_20260423]]) |

### [[../strategies/frame_only/toggle]]

| Failure signature | Likely cause | Try next |
|---|---|---|
| `cand_coords` empty | clusters too small or all are palettes/executors | `lights_out` (broader candidate selection) or `click_then_move` |
| Depth-3 enumeration exhausted | wrong shape for plain DFS | `lights_out` (GF(2) algebraic) if NxN grid; `click_then_move` if dir actions present |
| Stencil density ≥ 0.8 on top-K | candidates are display feedback ([[../concepts/gf2_toggle_stencil]]) | `lights_out` with stride-2 retry ([[../lessons/ft09_stride_button_drop_20260423]]) |

### [[../strategies/frame_only/lights_out]]

| Failure signature | Likely cause | Try next |
|---|---|---|
| Cumulative sweep produces 0 frame change | clicks have no effect — wrong env class | `paint_fill` or `merge` |
| Stencil density > 0.8 | top-N cells are coupled display feedback ([[../lessons/gf2_lights_out_stencil_20260423]]) | constraint-indicator detection (no plan yet) — escalate, skip plan |
| Naive 2^N enumeration exhausted, levels = 0 | goal isn't a homogeneous subset | constraint-indicator next-best |
| `responsive_8 = 0`, `responsive_4 ≥ 50` | stride alignment artifact ([[../lessons/ft09_stride_button_drop_20260423]]) | re-run with stride=4 |

### [[../strategies/frame_only/click_then_move]]

| Failure signature | Likely cause | Try next |
|---|---|---|
| `meaningful = []` post-HUD-mask | no real buttons (counter-only env) | `toggle` or `lights_out` |
| `dir_actions = []` | no directional movement | `paint_fill` or `toggle` |
| Pass-1 + pass-2 exhausted | composition isn't click-then-move | `paint_fill` (palette structure) or `navigation` (pure dir) |

### [[../strategies/frame_only/bfs_state_space]]

Same falsifiers as [[../strategies/frame_only/navigation]] plus:
- `prefix` not honored → re-pick `navigation` instead (R20-R22 fix)

### [[../strategies/frame_only/inferential_agent]]

The agent is the universal default. When IT fails:

| Failure signature | Likely cause | Try next |
|---|---|---|
| `no_progress_streak ≥ 12 levels` | systematic probe / entity / goal misclassification | upgrade probe stride to 2 OR pick a single specialised plan directly |
| Phase 1 > 5 % of total budget without entities | probe too coarse | re-run with stride=2 |
| Same `goal["kind"]` cycles, all inner plans 0 | locked on wrong hypothesis | force a specific plan via direct primary pick |

## When NO plan fits

If every plan in the failure → next-best chain returns 0:

1. The env mechanic genuinely has no matching plan in `PLAN_FNS`. Document it as a new lesson + queue a plan-fn sprint (R28a-e).
2. Do NOT spend more budget cycling through the same failed plans — preserve budget for the next env.
3. Mark the trace with `code_fix_proposals` (R26 schema, when implemented) so dev-time can author the missing plan.

## Related

- [[../strategies/frame_only/inferential_agent]] — outer dispatch
- [[../lessons/inferential_budget_vs_algo_20260423]] — taxonomy source
- [[../selector]] — initial routing decision
- [[../concepts/probe_signature]] — observable inputs
- [[budget_starvation]] — when low budget is the real constraint
- [[v1_vs_v2_diagnosis]] — when v2 hash rotation is the real constraint

## Sources

- All `strategies/frame_only/*.md` Falsification + Next-Best sections
- `scripts/inferential_direct_results.json` — failure-mode measurements
- R20-R22 probe scripts
