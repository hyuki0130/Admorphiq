---
type: lesson
date: 2026-07-13
games: [SU15]
status: fix landed (stall detection) — root capability gap still open
---

# A stalled merge-drag click is not free — it walks the env toward GAME_OVER

> Live-traced SU15 L3 (post L1+L2 clear) on `merge_drag.py` /
> `WorldModelAgent._merge_drag_step`: once a tile stops responding to the
> vacuum pull, `next_merge_click` recomputes the *identical* target from the
> unchanged frame every call and loops forever. That loop is not neutral —
> continuing to click a genuinely stuck tile accumulates toward
> `GameState.GAME_OVER` (measured: first GAME_OVER at click 22 of a run that
> repeated one dead target 5 times; varying the click between the dead
> target and the tile's own center did not help and only delayed GAME_OVER
> by 2 clicks). Fixed by capping consecutive no-op walk clicks
> (`_MERGE_DRAG_STALL_LIMIT = 3`) so the phase abandons to the interaction
pipeline instead of retrying a dead click toward a loss.

## What the probe showed

Two live instrumented traces (not the SU15 wiki page's brittle
`strat_su15_vacuum` — this is the frame-only `merge_drag.py` capability from
R49) against `su15-1944f8ab`, both driven past L1+L2 (cleared normally in 9
+ 7 clicks) into L3's merge/gather sequence:

**Baseline** (`next_merge_click` called in a bare loop, no caller-level
guard): clicks 1-16 progress normally — same-color tile pairs merge
(`(6,4)` → `(15,9)` → `(11,16)`), tracked via connected-component tile
summaries `(color, size, cx, cy)`. At click 17 the plan proposes `(22, 42)`
to step a color-11/size-16 tile toward the goal. Clicks 17-21 propose the
exact same `(22, 42)` five times running, and the tile inventory is
byte-identical across all five — the click has zero effect. Click 22 (the
sixth issuance of the dead click) flips `state` from
`GameState.NOT_FINISHED` to `GameState.GAME_OVER`.

**Alternation test** (isolate "same exact repeated click" from "tile is
just stuck"): after 2 consecutive no-op clicks on one target, switch to
clicking directly on the stuck tile's own center instead of stepping toward
the goal. Result: the alternate click is *also* a no-op — the tile does not
respond to being clicked directly either — and GAME_OVER still fires, just
2 clicks later (click 24 instead of 22). This rules out "wrong click point"
as the cause and confirms the tile itself has gone genuinely unresponsive to
`ACTION6`, not that the walk math picked a bad target.

**Progress-loss check** (settles a claim from an earlier, unverified
session note that GAME_OVER resets `levels_completed` to 0 and replays
L1+L2): captured the frame immediately after GAME_OVER, then the frame
immediately after the agent's `RESET`. `levels_completed` reads `2` on
BOTH frames — RESET resumes the CURRENT level fresh, it does not replay
earlier levels or drop the counter. **The earlier "catastrophic reset"
framing was wrong; retract it.** GAME_OVER still costs real actions
(RHAE efficiency is squared, so any waste hurts score) and is worth
avoiding, but it is not the run-destroying event it was assumed to be.

## Why it happens (open question, not fully resolved)

The two residual tiles at the point of stall are DIFFERENT colors (11 and
15) — not mergeable with each other — and sit near two static
color-9/size-69 objects that never moved anywhere in the entire ~22-click
trace. [[su15_l1_singleton_colors_20260423]] documented the same structural
gap at L1 under the older `strat_inferential_agent`/`_plan_merge` code path:
SU15 requires a **downgrade-then-merge** sequence (route an over-color
fruit past an enemy to drop it a color, THEN merge), and no current
frame-only plan implements the downgrade half. This L3 stall is consistent
with the same gap recurring deeper in the level: the two leftover tiles
may need a downgrade step before they become mergeable/gatherable, and
`next_merge_click`/`next_drag_click` have no such phase — they only know
"merge same-color" and "walk toward goal," both of which are legitimately
inapplicable once a tile needs an enemy interaction first.

The static color-9/size-69 objects are the leading candidate for "enemy" or
"trigger" entities and were NOT investigated further this session (open for
a follow-up: do they gate the stuck tiles, e.g. does the level require
clicking THEM, or driving a tile toward them, before the stuck tiles free
up?).

## Fix landed (generalizable, not SU15-specific)

`src/admorphiq/world_model_agent.py`: added `_merge_drag_stall`, a per-level
counter of consecutive walk clicks whose credited `_last_changed` was
`False`. `_MERGE_DRAG_STALL_LIMIT = 3` — once 3 consecutive walk clicks
change nothing, `_merge_drag_step` stops calling `next_merge_click` and
falls through to `_interact_step` (the existing generic fallback), instead
of repeating a provably-dead click toward GAME_OVER. This is a caller-level
fix, not a change to `merge_drag.py`'s pure functions — `next_drag_click`
and `next_merge_click` are intentionally stateless/env-free (recomputed
fresh from the live frame every call, per their own docstrings), so stall
memory belongs in the agent's per-level state, not the plan functions.

**Measured effect of the fix**: does NOT unlock SU15 L3 — the interaction
fallback also cannot solve the residual 2-tile state (7 GAME_OVERs still
occurred across a 283-action run, never progressing past L2). The fix's
value is bounded: it stops the specific failure mode of "loop a dead click
until GAME_OVER" and hands the remaining budget to a different pipeline
stage sooner, which is strictly better (or neutral) but is not a substitute
for the missing downgrade-phase capability.

## Falsification signature

- `next_merge_click` / `next_drag_click` return the same `(x, y)` on
  consecutive calls AND the tile inventory (connected components under
  `_MAX_TILE`) is unchanged across those calls → the walk is stalled, not
  progressing.
- Full-frame byte equality is NOT a reliable stall signal — some other
  region of the frame (HUD counter, animation) can change every click even
  when the tracked tiles are frozen. Compare tile-cluster positions
  specifically (as `detect_drag_layout(...).tiles`), not `frame.tobytes()`.

## Next-Best

When `_merge_drag_stall` hits the limit and the phase abandons: currently
falls to generic `_interact_step`, which (measured) also cannot clear SU15
L3. The real next-best is an enemy/downgrade-detection primitive per
[[su15_l1_singleton_colors_20260423]]'s "Cross-color downgrade probe"
proposal — still not implemented as of this session.

## Related

- [[su15_l1_singleton_colors_20260423]] — same root gap (downgrade-then-
  merge) measured at L1 under the older plan-fn architecture; this page is
  the R49-era `merge_drag.py` recurrence at L3.
- [[../games/SU15]]
- [[../strategies/frame_only/merge]] — documents the older `_plan_merge`;
  needs a cross-reference to `merge_drag.py` as the current implementation.
- [[../concepts/merge_mechanic]]

## Sources

- `src/admorphiq/merge_drag.py` (`detect_drag_layout`, `next_drag_click`,
  `next_merge_click`)
- `src/admorphiq/world_model_agent.py` (`_merge_drag_step`,
  `_MERGE_DRAG_STALL_LIMIT`) — fix landed this session
- Live traces against `su15-1944f8ab` via `Arcade(OperationMode.NORMAL)`,
  this session (2026-07-13)
