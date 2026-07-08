"""Training-free HUD-masked state-graph + frontier-BFS agent.

This is the deep-level mechanism shared by every top ARC-AGI-3 graph agent
(Blind Squirrel; arXiv 2512.24156 "Graph-Based Exploration", median 30/52
levels; Executable-World-Model 32.58%). It does NOT learn a policy or a neural
forward model — it builds an EXPLICIT graph of the exact observed transitions
and walks that graph. Because it is training-free there is no warm-start / no
transfer question at all: the graph is rebuilt fresh inside every unseen game.

The five ingredients (each dissolves one of our historical walls):

1. **HUD MASK** — status bars, step counters and animated overlays change on
   almost every step regardless of action. Hashing the RAW frame therefore
   makes every state near-unique and the graph infinite. We track per-cell
   change counts over recent transitions and MASK (zero) any cell that changes
   in more than ``hud_threshold`` of transitions. With the HUD masked, real
   game states RECUR, so the graph is finite and the transition model is the
   observed graph itself — exact, free, no accuracy question (walls #1, #4).

2. **STATE HASH / GRAPH** — a node is the hash of the HUD-masked frame; an edge
   is an exact observed ``(state, action) -> next_state`` transition. We keep
   per-state untried-action sets and predecessor links for shortest-path walks.

3. **CLICK CANDIDATES** — ACTION6's 4096 coordinates are reduced to a small,
   salience-ordered set of connected-component centroids (buttons are small and
   rare-coloured, so smaller/rarer components rank first). This turns ACTION6
   into ``K`` discrete actions (walls: search branching factor).

4. **FRONTIER BFS** — if the current state has an untried action, take it. Else
   BFS over the KNOWN graph to the nearest state that still has untried actions
   (a "frontier" state) and take the first action of that shortest path. No goal
   is needed until a level-clear is observed (wall #3).

5. **LEVEL-UP** — when ``levels_completed`` increases, the state space changed;
   reset the graph + HUD stats and continue with the new level (fresh graph).

Harness contract: ``is_done(frames, latest_frame)`` /
``choose_action(frames, latest_frame)`` over the raw arcengine observation,
returning an official ``GameAction`` — identical to :class:`RandomAgent` and
:class:`OnlineRLAgent`. Action plumbing (internal ``GameAction`` -> official
``GameAction`` with ``set_data`` for ACTION6) is reused verbatim from
:meth:`AdmorphiqAdapter._convert_action`. ``restart_on_game_over = True`` so
the runner RESETs on GAME_OVER and the agent keeps its graph (transitions stay
valid) — it just re-localises by hashing the revived frame.

**REGION MASK (R36c)** — the per-cell threshold above fails on games that carry
a MOVING-DIGIT counter (SP80/CN04/LS20/BP35): a multi-digit display repaints
100-235 cells every action, but each *individual* cell only changes when the
glyph differs there, so no single cell's change-rate crosses ``hud_threshold``
— yet collectively the digits break every hash and states never recur (measured
R36b: SP80 730 distinct states / 3000 actions, masked=0, 0 clears). The fix
masks whole *regions*: build a binary "noisy" map of cells whose change-rate
exceeds a LOW threshold (``GF_REGION_LOW``, 0.05), take its connected components,
DILATE each by ``GF_REGION_DILATE`` cells, and mask every region whose aggregate
(union-of-cells) per-step change-rate is high (``GF_REGION_RATE``, 0.7 — the
region changes on most steps even though its cells flicker). A moving digit
display is exactly such a region: individually low-rate cells, collectively
high-rate. Enabled by default (``GF_REGION_MASK=1``); the per-cell mask still
runs and its result is UNION-ed with the region mask.

**MOVING-BAND MASK (R44)** — a third masking class for a marker that moves ONE
cell per action along a fixed row/column (S5I5 row-63 counter, DC22 row-63,
SB26 row-53 decrementer). Each individual track cell changes only when the marker
passes (rate ~= 1/track_len ≪ ``GF_REGION_LOW``) so the per-cell mask misses it,
yet the marker repaints EVERY step so no raw frame recurs and pool=1 hashing forks
a fresh state per action (measured S5I5: after the pool downshift, states 21 → 454
over 4000 actions, 0 clears). The detector watches the per-transition changed-cell
sets for the signature "a small (≤ ``GF_BAND_MAX_CELLS``) changed set, dense over
its span (≥ ``GF_BAND_DENSITY``), confined to a thin strip (≤ ``GF_BAND_THICKNESS``)
whose centroid DRIFTS monotonically (≥ ``GF_BAND_MONOTONE``) a real distance
(≥ ``GF_BAND_MIN_DRIFT``)", then masks the whole swept track (accumulated union,
dilated by ``GF_BAND_DILATE``). Confirmed within ~16 marker steps (far before the
pool-downshift guard), UNION-ed into the mask stack, and — being a masked counter,
not sub-cell jitter — subtracted from the downshift jitter gate so pool=1 stays
viable once the band recurs. Monotonicity is the discriminator against a controlled
player (which reverses); ``GF_BAND_DENSITY`` stays at 0.5 because lowering it
falsely masked CD82's paint region / AR25's player (measured regression). MEASURED
(R44): dissolves the explosion — S5I5 states 330 → 64 @4000, DC22 explosion → 435
recurring — with zero regression (quick-8 identical, TU93 L3, CD82 L2). It does NOT
by itself clear these games: the residue is a semantic sink (S5I5 slider toggles
between 2 states; DC22 pool-tension; SB26 large sort state-space) — the other two
R43 deep levers (object-hash, goal-planning).

**OBJECT-SEGMENTED HASH (R45)** — the third and final rung of the hash ladder,
resolving the pool-tension the pixel modes cannot. Max-pool=2 absorbs sub-cell
jitter but CONFLATES a 1-2 cell real object move (the moved object pools back to
the same block, so a genuine transition self-loops — measured DC22: 25 states, a
sink where every move is invisible and the random-escape thrashes 1718x with 0
clears); pool=1 keeps the move distinct but EXPLODES on the jitter (DC22 557+
states; G50T after its pool downshift 259+ growing; SC25 1026+ at pool2). Neither
pool factor is right because the noise (intra-object jitter) and the signal (whole-
object position) live at the SAME pixel scale. The object hash separates them by
representing the state by its OBJECTS, not its raw pixels:

  Segment the (HUD/band-mask-subtracted) frame into 4-connected components per
  non-background colour. The state key is the hash of the SORTED multiset of
  ``(colour, size_bucket, centroid_row, centroid_col)`` tokens — centroid at FULL
  cell resolution (so a 1-cell object move IS a new state) but component area
  coarsened to a log2 ``size_bucket`` and the component's INTERIOR/SHAPE dropped
  entirely (so sprite jitter/animation that flips a few interior pixels leaves the
  colour, size-bucket and rounded centroid unchanged -> SAME key). This delivers
  jitter-absorption AND movement-sensitivity simultaneously.

Adaptive activation (``GF_OBJ_HASH=auto``, default): the pixel-hash ladder
(pool=2 -> pool=1 downshift) stays the default; object-hash is the THIRD rung,
armed only after the no-progress guard (``downshift_after`` in-level actions with
no level-up — so every game clearing within that budget is untouched) and the same
jitter-mask gate as the downshift (a large HUD mask means pooling is load-bearing;
skip). It then fires on either broken-graph signature the pool ladder could not
fix:
  * **explosion** — windowed new-state fraction ``>= GF_OBJ_EXPLODE_FRAC`` while
    still mobile (distinct-recent ``>= GF_OBJ_EXPLODE_MOBILE``): pixel states are
    not recurring (G50T pool1, SC25 pool2).
  * **persistent sink** — windowed self-loop fraction ``>= GF_OBJ_SINK_SELFLOOP``
    with low distinct-recent (``<= GF_OBJ_SINK_DISTINCT``), where the pool
    downshift will NOT rescue it (either already at pool=1, or self-loop below the
    stronger ``downshift_selfloop`` cut so the downshift never triggers — DC22's
    0.73 sink). Strong sinks (self-loop ``>= downshift_selfloop``) are left to the
    pool downshift first; only if pool=1 still sinks does object-hash take over.
On a fire the level graph is rebuilt with the object hash and the mode is pinned
for the rest of the level (one activation per level). ``GF_OBJ_HASH=on`` forces
object-hash from the first frame; ``off`` restores the pre-R45 pixel-only ladder.

Env knobs:
  * ``GF_MAX_CLICKS``   (default 14)   — cap on click candidates per frame.
  * ``GF_HUD_THRESHOLD`` (default 0.8) — per-cell change-rate above which a cell
    is masked out of the state hash (always active).
  * ``GF_BAND_MASK``    (default 1)    — enable the monotone-moving-band mask.
  * ``GF_BAND_WINDOW``  (default 48)   — recent small-change transitions retained.
  * ``GF_BAND_MIN_SAMPLES`` (default 16) — marker records before a band confirms.
  * ``GF_BAND_MAX_CELLS`` (default 12) — max changed cells for a "marker step".
  * ``GF_BAND_THICKNESS`` (default 3)  — max band thickness (thin axis).
  * ``GF_BAND_MIN_DRIFT`` (default 6)  — min extent along the drift axis.
  * ``GF_BAND_MONOTONE`` (default 0.7) — min dominant-sign fraction of centroid
    deltas (the discriminator vs a reversing controlled player).
  * ``GF_BAND_DENSITY`` (default 0.5)  — min fraction of transitions that are
    marker steps (0.5 spares paint/navigation content that drifts for a stretch).
  * ``GF_BAND_DILATE`` (default 1)     — dilation of the swept-track mask.
  * ``GF_REGION_MASK``  (default 1)    — enable region-level HUD masking.
  * ``GF_REGION_LOW``   (default 0.05) — per-cell change-rate above which a cell
    joins the "noisy" candidate map for region grouping.
  * ``GF_REGION_RATE``  (default 0.7)  — aggregate region change-rate (fraction
    of transitions on which ANY cell in the region changed) above which the whole
    region is masked.
  * ``GF_REGION_DILATE`` (default 1)   — cells to dilate each noisy region by
    before masking, to cover glyph edges the low threshold missed.
  * ``GF_GIVEUP``       (default 8000) — per-level action cap after which
    :meth:`is_done` gives up (the runner ``--max-actions`` also bounds it).
  * ``GF_STICKY_MASK``  (default 1)    — make the HUD mask MONOTONIC (once a cell
    is masked it stays masked) so the state-hash is stationary and real states
    recur. Fixes the R39 state-explosion class (rolling-window mask oscillation).
  * ``GF_REGION_MAX_FRAC`` (default 0.30) — a noisy region wider than this
    fraction of the frame is treated as the play field, not a HUD, and is left
    visible. Guards the sticky union against whole-board-animation blindness.

**SALIENCE-TIERED PRIORITIZATION (R38)** — uniform exploration wastes most of
the budget on unpromising frontiers (measured CD82 L2: 26,965 actions). Three
cost-cutting levers, all frame-only / game-agnostic:

1. **Click-candidate tiers** — click candidates are bucketed into
   ``_N_TIERS`` interactivity tiers (small / rare-coloured / high-contrast /
   not-background-hugging → high tier). A state's local untried pick takes the
   highest-tier action available; low tiers are only tried when high tiers are
   locally exhausted (and are further deferred by the frontier scorer).
2. **Frontier prioritization** — instead of walking to the NEAREST frontier,
   score every reachable frontier by promise (best untried tier, few visits,
   proximity to the last state where a level cleared) discounted by path length
   (``promise / (1 + path_len)``) and walk to the best within ``GF_FRONTIER_DIST``.
3. **Simple-action ordering** — untried simple actions (1-5) are tried before
   untried clicks in a fresh state (5 vs K, and usually movement).

New knobs (preserve all existing knobs + GF_DEBUG counters):
  * ``GF_TIER_PRIORITY`` (default 1)   — enable tiered local pick + frontier
    promise scoring. 0 restores the pre-R38 nearest-frontier BFS behaviour.
  * ``GF_FRONTIER_DIST`` (default 12)  — max path length the promise-scored
    frontier search will consider; beyond it, promise is dominated by distance.
  * ``GF_VISIT_PENALTY`` (default 0.15)— per-visit promise decrement so the
    scorer spreads exploration instead of re-walking the same frontier.
  * ``GF_RECENCY_BONUS`` (default 1.0) — promise bonus for a frontier at/near
    the state where the last level-up happened (recently-changed region).

**GOAL-DIRECTED FRONTIER RANKING (R41)** — R40 diagnosed the deep-level cost as
NOT a defect: the graph is healthy but explores EXHAUSTIVELY while the goal is
far (CD82 L2 burned 26,965 actions of uniform frontier-walking; VC33 L3 55,209).
RHAE squares efficiency, so cutting that discovery cost is the top lever.

Unlike the R33 forward-model goal planner (blocked by per-game model accuracy),
the GRAPH holds the ACTUAL frame of every discovered state, so
:func:`planner.goal.score_goal` can rank frontier states DIRECTLY — no forward
model, no accuracy wall. The lever:

1. **Goal acquisition** — after the first ``GF_GOAL_INFER_AFTER`` transitions of
   a level, infer a structured :class:`~planner.goal.GoalSpec` via the R46
   :class:`~planner.goal_inference.GoalMeasureTracker`, which watches the
   candidate-goal family (fill / count / ORDER / ON_TARGET) over productive
   transitions and adopts the measure trending most consistently upward — OR the
   goal TYPE carried from a prior level's clear (:meth:`_maybe_infer_goal`).
   Re-inferred every ``GF_GOAL_RECADENCE`` steps. If nothing confident is
   observed the agent stays goal-less (= pre-R41 behaviour). (R46 REPLACED the
   R41 FILL_COLOR ``infer_goal`` heuristic with this semantic tracker.)
2. **Goal-directed ranking** — when the local state is exhausted and the agent
   must walk to a frontier, rank reachable in-gate frontiers by
   ``score_goal(frame_of_state, goal)`` blended with nearness (``GF_GOAL_BLEND``)
   instead of strictly nearest-first. The graph caches each state's frame at
   discovery so the score is a lookup, not a re-observation.
3. **Graceful degradation** — R38's promise-frontier LOST deep clears when it
   overrode distance, so goal ranking must not get stuck on a WRONG goal: after
   ``GF_GOAL_MAX_WALKS`` consecutive goal-directed frontier picks WITHOUT the
   graph growing (no new state discovered), it falls back to nearest-frontier
   until a new state appears, then re-enables. Local untried actions at the
   current state are always tried first (unchanged).

**MEASURED VERDICT (R46, 2026-07-06) — semantic goals, default OFF.** R46 added
the ORDER / ON_TARGET measures + the semantic measure-trend/level-jump inference
+ the stall gate (:meth:`_goal_engaged`), then A/B-measured knob-ON on the 9
blocked semantic games @30000 against the zero-loss guard:
  * ZERO new level clears in BOTH shell and global mode (KA59 1/7, SB26 1/8 held
    at baseline; s5i5 / su15 / g50t / sc25 / dc22 / re86 / wa30 stayed 0). Those
    games need action SEQUENCING (push boxes in order, sort a permutation) — the
    near-solved states are never discovered by frontier BFS, so ranking the
    discovered frontier by goal-proximity has nothing to steer to.
  * CD82 L2 REGRESSED 2/6 -> 1/6 in BOTH modes: the semantic tracker infers a
    wrong goal for CD82 (ON_TARGET, not the R41 FILL that helped) and the stall
    gate engages on CD82's legitimately-long L2 walk, derailing the clear.
  So the lever is harmful-and-inert on this substrate and ships default OFF
  (byte-identical zero-loss, verified: CD82 2/6, TU93 3/9). The measures +
  inference + gate remain validated infrastructure, reachable via
  ``GF_GOAL_RANK=1``, for a future round that pairs them with a world model able
  to REACH near-solved states (not merely rank the ones exploration finds).
  NOTE: because R46 replaced the R41 FILL inference, knob-ON no longer reproduces
  the R41 CD82/VC33 discovery-cost speedups (those relied on FILL as a frontier
  ORDERING heuristic); reviving them is a config of the tracker, not a revert.

Goal knobs (all additive; default OFF — see the R46 verdict above):
  * ``GF_GOAL_RANK``   (default 0)     — enable goal-directed frontier ranking.
  * ``GF_GOAL_INFER_AFTER`` (default 40)— per-level transitions before the first
    goal inference.
  * ``GF_GOAL_RECADENCE`` (default 300)— steps between goal re-inference.
  * ``GF_GOAL_ENGAGE_AFTER`` (default 2000)— per-level actions before the stall
    gate lets goal ranking engage (below it, pre-R46 nearest-BFS behaviour).
  * ``GF_GOAL_ENGAGE_FRONTIER`` (default 25)— min in-gate frontier states for the
    stall signature (small frontier => not stalled => goal stays disengaged).
  * ``GF_GOAL_OBSERVE_STRIDE`` (default 8)— productive transitions between
    measure-tracker observations (bounds the flood-fill cost).
  * ``GF_GOAL_MAX_WALKS`` (default 400)— consecutive goal-directed frontier picks
    without a new state before falling back to nearest-frontier.
  * ``GF_GOAL_BLEND``  (default 0.5)   — weight in [0,1] of goal-proximity vs
    nearness in the frontier rank (0 = pure nearest, 1 = pure goal-proximity).
  * ``GF_OBJ_HASH``    (default auto)  — object-segmented hash mode: ``auto``
    (arm the third rung adaptively), ``on`` (force from the first frame), ``off``
    (pixel-only ladder, pre-R45).
  * ``GF_OBJ_EXPLODE_FRAC`` (default 0.5) — windowed new-state fraction above
    which the pixel hash is judged to be exploding (states not recurring).
  * ``GF_OBJ_EXPLODE_MOBILE`` (default 12) — min distinct-recent for the
    explosion trigger (an explosion is mobile; a frozen sink is not).
  * ``GF_OBJ_SINK_SELFLOOP`` (default 0.70) — windowed self-loop fraction above
    which a low-distinct state is judged a persistent (pool-unfixable) sink.
  * ``GF_OBJ_SINK_DISTINCT`` (default 6) — max distinct-recent for the sink
    trigger.
"""

from __future__ import annotations

import hashlib
import os
import random
from collections import deque
from typing import Any

import numpy as np

from .planner.goal import GoalSpec, GoalType, score_goal
from .planner.goal_inference import (
    GoalMeasureTracker,
    instantiate_goal_type,
)

# Number of recent transitions kept for HUD change-rate estimation. A rolling
# window keeps the mask responsive to level changes without unbounded memory.
_HUD_WINDOW = 64

# Minimum transitions observed before the HUD mask is trusted. Below this we
# hash the raw frame — with too few samples the change-rate is noise.
_HUD_MIN_SAMPLES = 8

# Env-knob defaults (module constants so tests can import them).
DEFAULT_MAX_CLICKS = 14
DEFAULT_HUD_THRESHOLD = 0.8
DEFAULT_GIVEUP = 8000

# Max-pool factor applied to the HUD-masked frame before hashing (R36d). Sub-cell
# jitter/animation (measured M0R0 71%%->18%%, CD82 68%%->11%% unique states under
# 2x2 max-pool) breaks the raw hash so states never recur; pooling absorbs it
# while preserving gross game structure. 1 disables pooling.
DEFAULT_HASH_POOL = 2

# Adaptive pool-downshift defaults (R42). See the module docstring section
# "ADAPTIVE POOL DOWNSHIFT". The hash max-pool (DEFAULT_HASH_POOL) absorbs
# sub-cell jitter so jitter-heavy games (M0R0/CD82/CN04) recur — but it also
# COLLAPSES small real object-moves on other games, so a genuine transition
# hashes back to the SAME state (a self-loop) or a stale edge is overwritten (a
# mismatch). The graph then has no reachable frontier and the agent random-walks
# in place forever (measured SB26/S5I5 bfs_fail ~95% of steps, 0 clears; TU93
# mismatch 1686/8000, states never recur). Setting hash_pool=1 fixes those but
# REGRESSES the jitter games (measured CD82/CN04/M0R0/VC33 all lose levels), so a
# global switch is wrong. Instead: keep pooling by default, and DOWNSHIFT to
# pool=1 only when a level has run a long time WITHOUT progress AND its hashing
# is demonstrably collapsing real states (high windowed self-loop OR mismatch).
# The "no level-up for N in-level actions" guard is the primary safety — every
# level that clears within N actions is untouched (measured: M0R0-L1 clears at
# 751, CD82-L1 342, LP85 809, all < N). The instability gate then spares the slow
# but healthy deep clears whose hashing is NOT collapsing (CD82-L2 self-loop 51%
# / mismatch 2%; VC33-L3 52% / 1% — both well under the thresholds).
# Two orthogonal collapse signatures fire the downshift (both gated by the
# no-progress guard above):
#   * SELF-LOOP sink — a real move hashes back to the SAME state. Measured
#     windowed self-loop fraction: SB26 0.96 / S5I5 0.94 / FT09 0.97 (targets) vs
#     the slow but pool-DEPENDENT clearers SK48 0.85 / TR87 0.74 and the deep
#     clears CD82-L2 0.51 / VC33 0.52 (must spare). The 0.90 cut captures the
#     targets and spares SK48 (pool=1 measured to BREAK SK48/TR87, unlike FT09).
#   * MOVING collapse — pooling conflates distinct MOVING-object positions so the
#     same (state,action) resolves to different next-states (edge mismatch) while
#     the agent is still MOBILE. Measured: TU93 mismatch 0.19 with recent_distinct
#     26/30 (target: pool=1 clears L1+L2) vs TR87 mismatch 0.38 but recent_distinct
#     9/30 (a SINK — pool=1 breaks it) and DC22 4/30. The mobility gate
#     (recent_distinct high) is what separates the moving-object game whose
#     pooling merely nondeterminises its edges from a stuck sink.
DEFAULT_POOL_DOWNSHIFT = True
DEFAULT_DOWNSHIFT_AFTER = 1500
DEFAULT_DOWNSHIFT_SELFLOOP = 0.90
DEFAULT_DOWNSHIFT_MISMATCH = 0.15
# Min distinct-recent states (of the 30-wide recency window) for the MOVING
# collapse trigger — a mobility gate that spares low-distinct sinks (TR87/DC22).
DEFAULT_DOWNSHIFT_MOBILE = 20
# Max HUD-masked cells for a downshift to be eligible. Pooling exists to absorb
# sub-cell JITTER; a game with a large HUD mask already has real jitter that
# pooling is load-bearing for, so its high self-loop is NOT a pool-collapse and a
# downshift would strip a pooling it needs (measured: SK48 masks 550-1007 cells
# and pool=1 BREAKS its clear; its recent-distinct stays ~3 even after a downshift
# — pool=1 does not unstick it). The true pool-collapse targets carry a tiny mask
# (S5I5 50 / SB26 0 / DC22 44 / TU93 85 / FT09 0), so a 256-cell (~6% of 4096) cap
# admits them and spares the jittery clearers. CD82-L2 (mask 0) is admitted here
# but spared by its low self-loop/mismatch instead — the gates are independent.
DEFAULT_DOWNSHIFT_MAX_MASK = 256
# Rolling window over which the self-loop / mismatch fractions are measured. Wide
# enough to be stable, far narrower than DEFAULT_DOWNSHIFT_AFTER so it is full by
# the time the guard opens.
_INSTABILITY_WINDOW = 200

# Object-segmented hash defaults (R45). See the module docstring "OBJECT-SEGMENTED
# HASH" section. Object-hash is the THIRD rung of the hash ladder, armed
# adaptively when the pixel ladder (pool=2 -> pool=1) cannot produce a usable
# recurring graph. Two broken-graph signatures fire it, both gated by the same
# no-progress guard (``downshift_after``) and jitter-mask gate (``downshift_max_mask``)
# the pool downshift uses:
#   * EXPLOSION — windowed new-state fraction (transitions whose next-hash was
#     never seen this level) >= DEFAULT_OBJ_EXPLODE_FRAC while still mobile
#     (distinct-recent >= DEFAULT_OBJ_EXPLODE_MOBILE). Pixel states are not
#     recurring so no frontier saturates (measured G50T pool1 259+ growing / SC25
#     pool2 1026+; both mobile ~16-22 distinct-recent).
#   * PERSISTENT SINK — windowed self-loop fraction >= DEFAULT_OBJ_SINK_SELFLOOP
#     with low distinct-recent (<= DEFAULT_OBJ_SINK_DISTINCT), that the pool
#     downshift will NOT rescue: either already at pool=1, or the self-loop sits
#     BELOW the stronger ``downshift_selfloop`` (0.90) cut so the downshift never
#     triggers (measured DC22: self-loop 0.73, distinct-recent 4 — a real 1-cell
#     move pools back to the same block and self-loops, but 0.73 < 0.90 so pool=1
#     is never reached; and pool=1 would only explode on the same jitter). Strong
#     sinks (self-loop >= downshift_selfloop) are left to the pool downshift FIRST;
#     only if pool=1 STILL sinks does object-hash take over.
# The healthy deep clears are spared by the no-progress guard (they clear within
# ``downshift_after``) or by having neither signature (CD82-L2 self-loop 0.51 and a
# revisiting graph -> new-state-frac well under 0.5; VC33-L3 similar) — verified in
# the acceptance no-loss set.
DEFAULT_OBJ_HASH = "auto"  # auto | on | off
DEFAULT_OBJ_EXPLODE_FRAC = 0.5
DEFAULT_OBJ_EXPLODE_MOBILE = 12
DEFAULT_OBJ_SINK_SELFLOOP = 0.70
DEFAULT_OBJ_SINK_DISTINCT = 6

# Region-mask defaults (R36c). See module docstring for the rationale.
DEFAULT_REGION_MASK = True
DEFAULT_REGION_LOW = 0.05
DEFAULT_REGION_RATE = 0.7
DEFAULT_REGION_DILATE = 1

# Monotone-moving-band mask defaults (R44). See the "MOVING-BAND MASK" module
# docstring section. Both the per-cell HUD mask (change-rate) and the region mask
# MISS a small marker that moves ONE cell per action along a fixed row/column: a
# 1-cell counter/cursor changes each individual cell only when it passes (rate ~=
# 1/track_len << region_low), yet it repaints EVERY step so no raw frame ever
# recurs and pool=1 hashing forks a fresh state per action (measured S5I5: after
# the pool downshift, states 21 -> 454 over 4000 actions, 0 clears; SB26 655 ->
# 1322). This detector watches the per-transition changed-cell sets for the
# signature "a small set of cells that changes on (almost) every transition and
# whose centroid DRIFTS monotonically along one axis", then masks the whole thin
# band it sweeps (the accumulated union, dilated) so the marker becomes invisible
# and real states recur — which lets pool=1 become viable for exactly this class.
DEFAULT_BAND_MASK = True
# Recent small-change transitions retained for band inference (rolling window).
DEFAULT_BAND_WINDOW = 48
# Minimum small-change records before a band can be confirmed. ~16 marker steps is
# enough to see a coherent drift yet fires far before the downshift guard (1500).
DEFAULT_BAND_MIN_SAMPLES = 16
# A transition changing at most this many cells is a "marker step" candidate. A
# 1-cell marker moving leaves ~2 changed cells (old off + new on); a small multi-
# digit cursor a few more. Above this the step carried real game change and is
# skipped for band inference (but still counts toward the transition total).
DEFAULT_BAND_MAX_CELLS = 12
# Max thickness (rows for a horizontal band, cols for a vertical one). A HUD
# counter/cursor track is thin (1-3 cells); a real play field is not.
DEFAULT_BAND_THICKNESS = 3
# Minimum extent along the drift axis before a thin strip counts as a TRACK —
# guards against masking a stationary 1-cell flicker (that is the per-cell mask's
# job) and demands the marker actually moved.
DEFAULT_BAND_MIN_DRIFT = 6
# Minimum fraction of consecutive centroid deltas sharing the dominant sign
# (monotone drift, wrap-tolerant). A controlled player reverses direction and
# fails this; a counter/cursor advances one way (with occasional wrap) and passes.
DEFAULT_BAND_MONOTONE = 0.7
# Minimum fraction of transitions (over the record span) that are marker steps —
# encodes "the marker moves on (almost) EVERY transition regardless of action".
# Measured at 0.5: an every-step auto-counter (S5I5/DC22 row-63, density ~= 1.0)
# is caught while paint/navigation content that DRIFTS monotonically for a stretch
# is spared — lowering to 0.3 falsely masked CD82's paint region (L2 efficiency
# 0.0012 -> 0.0003) and AR25's player (2 -> 0 levels), so 0.5 is the safe floor.
# (SB26's row-53 decrementer moves on < 0.5 of steps and is therefore NOT caught;
# its explosion is a large sort state-space, not chiefly the marker — see R44.)
DEFAULT_BAND_DENSITY = 0.5
# Cells to dilate the accumulated track by, covering the marker's leading edge
# (its next position is one cell beyond the current union) and glyph edges.
DEFAULT_BAND_DILATE = 1

# Sticky-mask defaults (R39). The pre-R39 mask was recomputed every step from a
# 64-step rolling window, so it OSCILLATED (measured AR25: masked 0 -> 158 -> 330
# -> 0 across snapshots). An oscillating mask makes the state-hash NON-STATIONARY:
# the same real frame hashes differently at different times, so real states never
# recur and the graph never saturates (measured: 9 of 17 zero-clear games had
# states ~= choose_action calls). The fix makes the mask MONOTONIC — once a cell
# is judged HUD it stays masked, so the hash converges (measured CN04 1288 -> 12
# states, L1 cleared with no regression on the 8 clearing games). The area cap
# stops a whole-board animation from being masked into total blindness (measured
# LS20: a 675-cell region crossed agg-rate > 0.7 and the sticky union grew to all
# 4096 cells -> every frame hashed equal); a region wider than the cap fraction is
# the play field, not a HUD, and is left visible.
DEFAULT_STICKY_MASK = True
DEFAULT_REGION_MAX_FRAC = 0.30

# Salience-tiered prioritization defaults (R38). See module docstring.
DEFAULT_TIER_PRIORITY = True
# Gate + promise default OFF (R38): both perturb the exact nearest-BFS
# trajectory that reaches barely-in-budget deep goals (measured CD82 L2 clears
# at 26,965/30,000 actions — any reordering loses it). Tier ORDERING (local pick
# + registration order + frontier-shell tie-break when promise is on) is the
# safe, always-on lever. Gate/promise are opt-in knobs for games that benefit.
DEFAULT_TIER_GATE = False
DEFAULT_FRONTIER_DIST = 12
DEFAULT_VISIT_PENALTY = 0.0
DEFAULT_RECENCY_BONUS = 0.0

# Goal-directed frontier ranking defaults. R41 kept this OFF because a GLOBAL
# fill-goal helped paint/click but hurt navigation. R46 added the semantic
# measures (ORDER / ON_TARGET), the measure-trend + level-clear-jump inference,
# and the stall gate (:meth:`_goal_engaged`), then A/B-measured the lever on the
# 9 blocked semantic games @30000 vs the zero-loss guard:
#
#   * BOTH shell and global ranking produced ZERO new level clears on the 9
#     games (KA59 1/7, SB26 1/8 held at baseline; the other 7 stayed 0). Those
#     games need action SEQUENCING (push boxes in order, sort a permutation) —
#     the near-solved states are simply never discovered by frontier BFS, so
#     ranking the discovered frontier by goal-proximity has nothing to steer to.
#   * BOTH modes REGRESSED CD82's deep clear (L2 2/6 -> 1/6): once the stall gate
#     engages on CD82's legitimately-long L2 frontier walk, the goal reorders the
#     frontier and derails the clear.
#
# The lever is therefore harmful-and-inert on this substrate, so it ships OFF by
# default (byte-identical zero-loss). The measures + inference + gating remain as
# validated infrastructure, reachable via GF_GOAL_RANK=1, for a future round that
# pairs them with a world model able to REACH near-solved states (not just rank
# the ones exploration happens to find). See scripts/rounds/R46/.
DEFAULT_GOAL_RANK = False
DEFAULT_GOAL_INFER_AFTER = 40
DEFAULT_GOAL_RECADENCE = 300
DEFAULT_GOAL_MAX_WALKS = 400
DEFAULT_GOAL_BLEND = 0.5
# Nearest-shell mode (R41). When True the goal ranker is restricted to the
# NEAREST in-gate frontier shell — it never picks a farther frontier over a
# nearer one, so the systematic BFS shell expansion that reaches barely-in-budget
# deep goals (CD82 L2, TU93 L3, VC33 L3) is preserved BY CONSTRUCTION; the goal
# only breaks ties among equidistant frontiers.
#
# R46 measured the alternative (global mode, DEFAULT_GOAL_SHELL=False): once the
# stall gate engaged on CD82's legitimately-long L2 frontier walk it derailed the
# clear (2/6 -> 1/6) while producing ZERO new clears on the 9 blocked semantic
# games — those need action SEQUENCING the frontier graph never discovers, not
# distance-to-goal ranking. So shell mode stays the default: the semantic
# measures + inference ship live and gated, but never at the cost of a deep clear.
DEFAULT_GOAL_SHELL = True
# Stall gate (R46). Goal ranking ENGAGES only after a level has consumed at least
# this many actions without clearing while the reachable frontier is still large
# (>= DEFAULT_GOAL_ENGAGE_FRONTIER in-gate frontier states). Tuned so every game
# that clears within the quick budget stays in pre-R46 nearest-BFS behaviour.
DEFAULT_GOAL_ENGAGE_AFTER = 2000
DEFAULT_GOAL_ENGAGE_FRONTIER = 25
# Productive (frame-changing) transitions between measure-tracker observations.
# Bounds the flood-fill cost of scoring the candidate-goal family per level.
DEFAULT_GOAL_OBSERVE_STRIDE = 8

# ── Measure-guided expansion (R47) defaults ──────────────────────────────────
#
# R46 ranked WHICH already-discovered frontier STATE to walk to (goal-proximity
# of seen states) — that only reorders visits and measured ZERO new clears. R47
# instead guides WHICH UNTRIED ACTION to EXPAND: it credits ACTION CLASSES
# (buckets) by the average delta of the inferred goal measure they produce, then
# runs best-first EXPANSION toward high-measure reachable states whose untried
# actions belong to a PRODUCTIVE bucket. This is A*-flavoured expansion toward
# measure-improving territory — what sokoban / sort / merge need (each productive
# push / placement raises the on-target / order count, a climbable gradient).
#
# Default OFF (byte-identical zero-loss): with the flag off, ``_goal_active`` is
# False so every goal / measure code path is inert exactly as before R47. The
# gate (:meth:`_r47_engaged`) additionally protects the fast-clearing set — it
# engages only once a level has stalled (``goal_engage_after`` actions, still-large
# frontier), so games that clear quickly never enter measure-guided mode.
DEFAULT_MEASURE_EXPAND = False
# Weight of a bucket's mean measure-delta in the productive-expansion rank,
# relative to the frontier state's own goal measure (measure dominates; credit
# breaks ties toward action classes that historically moved the measure up).
DEFAULT_MEASURE_CREDIT_W = 1.0
# Penalty subtracted from a bucket's credit per GAME_OVER attributed to it — a
# bucket whose action immediately preceded death is regressive and deprioritised.
DEFAULT_MEASURE_DEATH_W = 4.0
# Minimum measure-delta samples before a bucket's mean credit is trusted; below
# it the bucket is neutral (credit 0), so it is neither preferred nor a "productive"
# expansion target until enough evidence accrues (discovery precedes exploitation).
DEFAULT_MEASURE_MIN_SAMPLES = 3

# Sentinel tier for simple actions (1-5): strictly better than any click tier
# (>= 0) so simple actions are tried before clicks in a fresh state (R38 §3).
_SIMPLE_TIER = -1


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


class GraphFrontierAgent:
    """HUD-masked explicit state graph with frontier-driven BFS traversal.

    Args:
        max_clicks: Cap on the number of segment-based ACTION6 click candidates
            derived per frame. Defaults to the ``GF_MAX_CLICKS`` env var / 14.
        hud_threshold: Per-cell change-rate above which a cell is treated as HUD
            (animated / counter) and masked out of the state hash. Defaults to
            the ``GF_HUD_THRESHOLD`` env var / 0.8.
        giveup: Per-level action cap after which :meth:`is_done` returns True.
            Defaults to the ``GF_GIVEUP`` env var / 8000.
    """

    def __init__(
        self,
        max_clicks: int | None = None,
        hud_threshold: float | None = None,
        giveup: int | None = None,
        region_mask: bool | None = None,
        region_low: float | None = None,
        region_rate: float | None = None,
        region_dilate: int | None = None,
        band_mask: bool | None = None,
        band_window: int | None = None,
        band_min_samples: int | None = None,
        band_max_cells: int | None = None,
        band_thickness: int | None = None,
        band_min_drift: int | None = None,
        band_monotone: float | None = None,
        band_density: float | None = None,
        band_dilate: int | None = None,
        sticky_mask: bool | None = None,
        region_max_frac: float | None = None,
        hash_pool: int | None = None,
        pool_downshift: bool | None = None,
        downshift_after: int | None = None,
        downshift_selfloop: float | None = None,
        downshift_mismatch: float | None = None,
        tier_priority: bool | None = None,
        tier_gate: bool | None = None,
        frontier_dist: int | None = None,
        visit_penalty: float | None = None,
        recency_bonus: float | None = None,
        goal_rank: bool | None = None,
        goal_infer_after: int | None = None,
        goal_recadence: int | None = None,
        goal_max_walks: int | None = None,
        goal_blend: float | None = None,
        goal_shell: bool | None = None,
        obj_hash: str | None = None,
        obj_explode_frac: float | None = None,
        obj_explode_mobile: int | None = None,
        obj_sink_selfloop: float | None = None,
        obj_sink_distinct: int | None = None,
        measure_expand: bool | None = None,
        measure_credit_w: float | None = None,
        measure_death_w: float | None = None,
        measure_min_samples: int | None = None,
    ) -> None:
        from .adapter import AdmorphiqAdapter  # heavy import, kept lazy

        self._convert_action = AdmorphiqAdapter._convert_action

        self.max_clicks = max_clicks if max_clicks is not None else _env_int(
            "GF_MAX_CLICKS", DEFAULT_MAX_CLICKS
        )
        self.hud_threshold = (
            hud_threshold
            if hud_threshold is not None
            else _env_float("GF_HUD_THRESHOLD", DEFAULT_HUD_THRESHOLD)
        )
        self.giveup = giveup if giveup is not None else _env_int(
            "GF_GIVEUP", DEFAULT_GIVEUP
        )
        # Executable-world-model pruning (R52, default OFF => byte-identical).
        # After GF_EWM_MIN_OBS observed transitions an LLM synthesizes a
        # predict_next_frame from the agent's OWN observations (adaptive
        # multi-config, train-fit selected — see admorphiq.ewm.synthesizer);
        # if its fit over all observations reaches GF_EWM_MIN_FIT, untried
        # actions the model predicts as no-change are deprioritized within
        # their tier. Frame observations only — no game ids.
        # GF_EWM = no-change pruning (R52, measured NULL). GF_EWM_PLAN =
        # goal-conditioned forward planning (R53) — the proper LLM use. Either
        # flag turns on observation logging + one-shot synthesis; each then
        # consumes the kept model differently. Both default OFF => byte-identical.
        self.ewm_prune = _env_bool("GF_EWM", False)
        self.ewm_plan = _env_bool("GF_EWM_PLAN", False)
        self.ewm_enabled = self.ewm_prune or self.ewm_plan
        self.ewm_min_fit = _env_float("GF_EWM_MIN_FIT", 0.8)
        self.ewm_min_obs = _env_int("GF_EWM_MIN_OBS", 30)
        self.ewm_model = os.environ.get("GF_EWM_MODEL", "gpt-oss:20b")
        self.ewm_plan_horizon = _env_int("GF_EWM_PLAN_HORIZON", 2)
        self.ewm_plan_conf = _env_float("GF_EWM_PLAN_CONF", 0.55)
        # Dead-signature action prior (R53 lever 3, default OFF => byte-identical).
        # A game-agnostic, LLM-FREE efficiency prior: an action CLASS (bucket)
        # that has been tried >= GF_DEAD_SIG_MIN times and NEVER produced a
        # hash-level state change is treated as inert and its untried members
        # sort last within their tier — saving probe actions (raises squared-
        # efficiency) without ever removing an action. Empirical, not predicted.
        self.dead_sig = _env_bool("GF_DEAD_SIG", False)
        self.dead_sig_min = _env_int("GF_DEAD_SIG_MIN", 8)
        # Hidden-state de-aliasing (US-11, R53; default OFF => byte-identical).
        # The novel primitive: split a state that ALIASES (same base+action ->
        # different next, i.e. partial observability) by recent action-history.
        self.dealias = _env_bool("GF_DEALIAS", False)
        # LLM goal inference (R53; default OFF). The transform/arrangement games
        # (re86, dc22) plateau because the HEURISTIC goal is wrong; let the
        # offline LLM infer the target once at discovery, feeding the existing
        # goal-directed frontier machinery. Needs goal_active + an ollama model.
        self.llm_goal = _env_bool("GF_LLM_GOAL", False)
        self.llm_goal_model = os.environ.get("GF_LLM_GOAL_MODEL", "gemma4:31b-it-q8_0")
        self.llm_goal_host = os.environ.get("GF_LLM_GOAL_HOST", "http://localhost:11434")
        self._ewm_obs: list[tuple[np.ndarray, int, np.ndarray]] = []
        self._ewm_result: Any = None
        self._ewm_attempted = False
        self._ewm_pred_cache: dict[Any, bool] = {}
        self._ewm_synthesize: Any = None  # injectable for tests; lazy default
        self.hash_pool = hash_pool if hash_pool is not None else _env_int(
            "GF_HASH_POOL", DEFAULT_HASH_POOL
        )

        # Adaptive pool downshift (R42). See DEFAULT_POOL_DOWNSHIFT.
        self.pool_downshift = (
            pool_downshift
            if pool_downshift is not None
            else _env_bool("GF_POOL_DOWNSHIFT", DEFAULT_POOL_DOWNSHIFT)
        )
        self.downshift_after = (
            downshift_after
            if downshift_after is not None
            else _env_int("GF_DOWNSHIFT_AFTER", DEFAULT_DOWNSHIFT_AFTER)
        )
        self.downshift_selfloop = (
            downshift_selfloop
            if downshift_selfloop is not None
            else _env_float("GF_DOWNSHIFT_SELFLOOP", DEFAULT_DOWNSHIFT_SELFLOOP)
        )
        self.downshift_mismatch = (
            downshift_mismatch
            if downshift_mismatch is not None
            else _env_float("GF_DOWNSHIFT_MISMATCH", DEFAULT_DOWNSHIFT_MISMATCH)
        )
        self.downshift_mobile = _env_int(
            "GF_DOWNSHIFT_MOBILE", DEFAULT_DOWNSHIFT_MOBILE
        )
        self.downshift_max_mask = _env_int(
            "GF_DOWNSHIFT_MAX_MASK", DEFAULT_DOWNSHIFT_MAX_MASK
        )

        # Region-level HUD masking (R36c) — groups low-rate flickering cells (a
        # moving-digit counter) into regions and masks whole high-rate regions.
        self.region_mask = (
            region_mask
            if region_mask is not None
            else _env_bool("GF_REGION_MASK", DEFAULT_REGION_MASK)
        )
        self.region_low = (
            region_low
            if region_low is not None
            else _env_float("GF_REGION_LOW", DEFAULT_REGION_LOW)
        )
        self.region_rate = (
            region_rate
            if region_rate is not None
            else _env_float("GF_REGION_RATE", DEFAULT_REGION_RATE)
        )
        self.region_dilate = (
            region_dilate
            if region_dilate is not None
            else _env_int("GF_REGION_DILATE", DEFAULT_REGION_DILATE)
        )

        # Monotone-moving-band mask (R44) — detects a small marker drifting one
        # cell per action along a thin row/column track and masks the whole band.
        self.band_mask = (
            band_mask
            if band_mask is not None
            else _env_bool("GF_BAND_MASK", DEFAULT_BAND_MASK)
        )
        self.band_window = (
            band_window
            if band_window is not None
            else _env_int("GF_BAND_WINDOW", DEFAULT_BAND_WINDOW)
        )
        self.band_min_samples = (
            band_min_samples
            if band_min_samples is not None
            else _env_int("GF_BAND_MIN_SAMPLES", DEFAULT_BAND_MIN_SAMPLES)
        )
        self.band_max_cells = (
            band_max_cells
            if band_max_cells is not None
            else _env_int("GF_BAND_MAX_CELLS", DEFAULT_BAND_MAX_CELLS)
        )
        self.band_thickness = (
            band_thickness
            if band_thickness is not None
            else _env_int("GF_BAND_THICKNESS", DEFAULT_BAND_THICKNESS)
        )
        self.band_min_drift = (
            band_min_drift
            if band_min_drift is not None
            else _env_int("GF_BAND_MIN_DRIFT", DEFAULT_BAND_MIN_DRIFT)
        )
        self.band_monotone = (
            band_monotone
            if band_monotone is not None
            else _env_float("GF_BAND_MONOTONE", DEFAULT_BAND_MONOTONE)
        )
        self.band_density = (
            band_density
            if band_density is not None
            else _env_float("GF_BAND_DENSITY", DEFAULT_BAND_DENSITY)
        )
        self.band_dilate = (
            band_dilate
            if band_dilate is not None
            else _env_int("GF_BAND_DILATE", DEFAULT_BAND_DILATE)
        )

        # Sticky (monotonic) HUD mask + play-field area cap (R39). See the
        # DEFAULT_STICKY_MASK note for the non-stationary-hash rationale.
        self.sticky_mask = (
            sticky_mask
            if sticky_mask is not None
            else _env_bool("GF_STICKY_MASK", DEFAULT_STICKY_MASK)
        )
        self.region_max_frac = (
            region_max_frac
            if region_max_frac is not None
            else _env_float("GF_REGION_MAX_FRAC", DEFAULT_REGION_MAX_FRAC)
        )

        # Salience-tiered prioritization (R38) — tier local picks + promise-score
        # frontiers so the budget concentrates on likely-interactive regions.
        self.tier_priority = (
            tier_priority
            if tier_priority is not None
            else _env_bool("GF_TIER_PRIORITY", DEFAULT_TIER_PRIORITY)
        )
        # Tier gate (R38): when on, exploration is restricted to simple + tier-0
        # clicks until that gate is globally exhausted, THEN unlocks lower tiers.
        # When off, all tiers are in-gate from the start (tier ordering still
        # applies to the local pick + frontier scorer, but nothing is deferred).
        self.tier_gate = (
            tier_gate
            if tier_gate is not None
            else _env_bool("GF_TIER_GATE", DEFAULT_TIER_GATE)
        )
        self.frontier_dist = (
            frontier_dist
            if frontier_dist is not None
            else _env_int("GF_FRONTIER_DIST", DEFAULT_FRONTIER_DIST)
        )
        self.visit_penalty = (
            visit_penalty
            if visit_penalty is not None
            else _env_float("GF_VISIT_PENALTY", DEFAULT_VISIT_PENALTY)
        )
        self.recency_bonus = (
            recency_bonus
            if recency_bonus is not None
            else _env_float("GF_RECENCY_BONUS", DEFAULT_RECENCY_BONUS)
        )

        # Goal-directed frontier ranking (R41) — infer a structured goal from
        # observed probe deltas and rank frontiers by proximity to it, so the
        # budget walks TOWARD the level-complete condition instead of exhausting
        # every frontier uniformly. Default OFF (see DEFAULT_GOAL_RANK).
        self.goal_rank = (
            goal_rank
            if goal_rank is not None
            else _env_bool("GF_GOAL_RANK", DEFAULT_GOAL_RANK)
        )
        self.goal_infer_after = (
            goal_infer_after
            if goal_infer_after is not None
            else _env_int("GF_GOAL_INFER_AFTER", DEFAULT_GOAL_INFER_AFTER)
        )
        self.goal_recadence = (
            goal_recadence
            if goal_recadence is not None
            else _env_int("GF_GOAL_RECADENCE", DEFAULT_GOAL_RECADENCE)
        )
        self.goal_max_walks = (
            goal_max_walks
            if goal_max_walks is not None
            else _env_int("GF_GOAL_MAX_WALKS", DEFAULT_GOAL_MAX_WALKS)
        )
        self.goal_blend = (
            goal_blend
            if goal_blend is not None
            else _env_float("GF_GOAL_BLEND", DEFAULT_GOAL_BLEND)
        )
        self.goal_shell = (
            goal_shell
            if goal_shell is not None
            else _env_bool("GF_GOAL_SHELL", DEFAULT_GOAL_SHELL)
        )
        # Stall gate + observe stride (R46). See the DEFAULT_GOAL_ENGAGE_* notes.
        self.goal_engage_after = _env_int(
            "GF_GOAL_ENGAGE_AFTER", DEFAULT_GOAL_ENGAGE_AFTER
        )
        self.goal_engage_frontier = _env_int(
            "GF_GOAL_ENGAGE_FRONTIER", DEFAULT_GOAL_ENGAGE_FRONTIER
        )
        self.goal_observe_stride = _env_int(
            "GF_GOAL_OBSERVE_STRIDE", DEFAULT_GOAL_OBSERVE_STRIDE
        )

        # Object-segmented hash (R45) — the third rung of the hash ladder. See the
        # module docstring "OBJECT-SEGMENTED HASH" section and DEFAULT_OBJ_* notes.
        obj_hash_raw = (
            obj_hash
            if obj_hash is not None
            else os.environ.get("GF_OBJ_HASH", "").strip().lower() or DEFAULT_OBJ_HASH
        )
        self.obj_hash = obj_hash_raw if obj_hash_raw in ("auto", "on", "off") else DEFAULT_OBJ_HASH
        self.obj_explode_frac = (
            obj_explode_frac
            if obj_explode_frac is not None
            else _env_float("GF_OBJ_EXPLODE_FRAC", DEFAULT_OBJ_EXPLODE_FRAC)
        )
        self.obj_explode_mobile = (
            obj_explode_mobile
            if obj_explode_mobile is not None
            else _env_int("GF_OBJ_EXPLODE_MOBILE", DEFAULT_OBJ_EXPLODE_MOBILE)
        )
        self.obj_sink_selfloop = (
            obj_sink_selfloop
            if obj_sink_selfloop is not None
            else _env_float("GF_OBJ_SINK_SELFLOOP", DEFAULT_OBJ_SINK_SELFLOOP)
        )
        self.obj_sink_distinct = (
            obj_sink_distinct
            if obj_sink_distinct is not None
            else _env_int("GF_OBJ_SINK_DISTINCT", DEFAULT_OBJ_SINK_DISTINCT)
        )

        # Measure-guided expansion (R47) — credit action classes by the goal
        # measure they move, then expand toward high-measure states via productive
        # buckets. Default OFF (see DEFAULT_MEASURE_EXPAND). Reuses the R46 stall
        # gate (goal_engage_after / goal_engage_frontier) and goal inference.
        self.measure_expand = (
            measure_expand
            if measure_expand is not None
            else _env_bool("GF_MEASURE_EXPAND", DEFAULT_MEASURE_EXPAND)
        )
        self.measure_credit_w = (
            measure_credit_w
            if measure_credit_w is not None
            else _env_float("GF_MEASURE_CREDIT_W", DEFAULT_MEASURE_CREDIT_W)
        )
        self.measure_death_w = (
            measure_death_w
            if measure_death_w is not None
            else _env_float("GF_MEASURE_DEATH_W", DEFAULT_MEASURE_DEATH_W)
        )
        self.measure_min_samples = (
            measure_min_samples
            if measure_min_samples is not None
            else _env_int("GF_MEASURE_MIN_SAMPLES", DEFAULT_MEASURE_MIN_SAMPLES)
        )
        # Goal inference + per-state frame caching + measure tracking are shared by
        # BOTH the R46 goal ranker and the R47 measure-guided expander. This single
        # switch gates all of it so that with both features OFF (the default) every
        # goal code path stays inert — byte-identical to pre-R46/R47 behaviour.
        # GF_EWM_PLAN also needs goal inference running so the forward-model
        # rollout has a goal to climb (R53).
        self._goal_active = (
            self.goal_rank or self.measure_expand or self.ewm_plan or self.llm_goal
        )
        self._llm_goal_done = False

        # Carried goal TYPE across level boundaries (R46). When a level clears, the
        # measure-tracker's best-jump goal type is snapshotted here so the NEXT
        # level re-instantiates the same goal shape on its own colours (deep levels
        # are where the squared-efficiency metric pays off). Persists across
        # _reset_level_state (which the per-level graph state does not).
        self._carried_goal_type: GoalType | None = None
        self._carried_axis = 0

        # The runner (scripts/score_efficiency.py) reads this flag: on GAME_OVER
        # it RESETs the env and lets the agent keep acting. Our observed
        # transitions remain valid across a reset, so we keep the graph.
        self.restart_on_game_over = True

        # Deterministic RNG for the random-escape fallback (sink-breaking).
        self._rng = random.Random(0)

        # Debug instrumentation (env-gated: GF_DEBUG=1). Cumulative across
        # levels; a line is printed every GF_DEBUG_EVERY choose_action calls so
        # a single seconds-long probe reveals whether the graph grows, the
        # frontier BFS fires, and how often the observed next state disagrees
        # with the edge we recorded (edge nondeterminism).
        self._debug = os.environ.get("GF_DEBUG", "").strip() in ("1", "true", "yes")
        self._debug_every = _env_int("GF_DEBUG_EVERY", 500)
        self._dbg_calls = 0
        self._dbg_bfs = 0
        self._dbg_mismatch = 0
        self._dbg_bfs_fail = 0
        self._dbg_random = 0
        self._dbg_untried = 0
        # Self-loop vs real-move edge counters. A self-loop edge (recorded
        # next_hash == source hash) means the action changed the LIVE env but the
        # hashed state did not — the signature of the hash collapsing distinct
        # real states (over-pooling). A high self-loop fraction discriminates a
        # "pool-collapse sink" from a genuine small-cycle stall (which cycles
        # among DISTINCT hashes, so its edges are real moves).
        self._dbg_selfloop = 0
        self._dbg_realedge = 0
        # Rolling window of "hash-unstable" transition flags (self-loop OR
        # edge-mismatch). A high windowed fraction is the pool-collapse signature.
        self._dbg_unstable_window: deque[bool] = deque(maxlen=200)
        self._dbg_recent = deque(maxlen=30)
        # Per-tier count of local untried picks (index = tier; last slot = simple).
        self._dbg_tier_hits = [0] * (_N_TIERS + 1)
        # Count of goal-directed frontier picks taken this level (R41 debug).
        self._dbg_goal_walks = 0

        self._last_levels = 0
        self._reset_level_state()

    def _debug_tick(self) -> None:
        if not self._debug:
            return
        self._dbg_calls += 1
        if self._dbg_calls % self._debug_every != 0:
            return
        n_states = len(self._untried)
        n_frontier = sum(1 for v in self._untried.values() if v)
        n_edges = sum(len(e) for e in self._edges.values())
        mask = self._hud_mask_grid()
        n_masked = int(mask.sum()) if mask is not None else 0
        # cycle detection: how many DISTINCT states in the last 30 visits?
        distinct_recent = len(set(self._dbg_recent))
        tier_hits = "/".join(str(x) for x in self._dbg_tier_hits)
        new_frac = (
            sum(self._new_state_window) / len(self._new_state_window)
            if self._new_state_window
            else 0.0
        )
        if self._goal is not None:
            eng = "eng" if self._goal_engaged() else "wait"
            goal_desc = (
                f"{self._goal.goal_type.value}:{self._goal.color}"
                f",{self._goal.color_b},ax{self._goal.axis}[{eng}]"
            )
        else:
            carried = self._carried_goal_type.value if self._carried_goal_type else "-"
            goal_desc = f"none(carry={carried})"
        if self._band_confirmed and self._band_mask is not None:
            axis = "H" if self._band_horizontal else "V"
            band_desc = (
                f"{axis}[{self._band_lo_line}-{self._band_hi_line}]"
                f":{int(self._band_mask.sum())}"
            )
        else:
            band_desc = f"none({len(self._band_records)}rec)"
        # R47 measure trace: current goal measure + the most-productive bucket.
        measure_s = "-"
        bucket_best_s = "-"
        if self.measure_expand and self._goal is not None and self._recent_states:
            mval = self._goal_score(self._recent_states[-1])
            if mval != float("-inf"):
                measure_s = f"{mval:.1f}"
            if self._bucket_delta_n:
                bb = max(self._bucket_delta_n, key=lambda b: self._bucket_credit(b))
                bucket_best_s = f"{bb}:{self._bucket_credit(bb):.2f}"
        print(
            f"[GF] call={self._dbg_calls} lvl={self._last_levels} "
            f"states={n_states} frontier={n_frontier} edges={n_edges} "
            f"bfs_fires={self._dbg_bfs} bfs_fail={self._dbg_bfs_fail} "
            f"random={self._dbg_random} untried={self._dbg_untried} "
            f"mismatch={self._dbg_mismatch} "
            f"selfloop={self._dbg_selfloop} realedge={self._dbg_realedge} "
            f"unstable_win={sum(self._dbg_unstable_window)}/{len(self._dbg_unstable_window)} "
            f"effpool={self._effective_pool} mode={self._hash_mode} "
            f"newfrac={new_frac:.2f} "
            f"masked={n_masked} band={band_desc} "
            f"tier_hits={tier_hits} "
            f"goal={goal_desc} goal_walks={self._dbg_goal_walks} "
            f"measure={measure_s} bucket_best={bucket_best_s} "
            f"measure_walks={self._dbg_measure_walks} "
            f"recent_distinct={distinct_recent}/30",
            flush=True,
        )

    # ── level-scoped state ────────────────────────────────────────────────────

    def _reset_level_state(self) -> None:
        """Drop the graph and HUD stats — called on init and on level-up."""
        # Graph: state_hash -> {action_key: next_state_hash}. action_key is an
        # int for simple actions (1..5) or a ("click", x, y) tuple for ACTION6.
        self._edges: dict[str, dict[Any, str]] = {}
        # Dead-signature (GF_DEAD_SIG): per action-CLASS bucket, how many tries
        # produced NO hash-change (inert) vs any change (active). Level-scoped:
        # an action inert in one level may matter in the next.
        self._ds_inert: dict[Any, int] = {}
        self._ds_active: dict[Any, int] = {}
        # De-aliasing (GF_DEALIAS): bases observed to alias + recent action k-gram.
        self._aliased_bases: set[str] = set()
        self._action_hist: deque[Any] = deque(maxlen=2)
        self._last_base: str | None = None
        self._prev_base: str | None = None
        self._llm_goal_done = False   # LLM goal inferred once per level (GF_LLM_GOAL)
        # state_hash -> ordered list of untried action_keys.
        self._untried: dict[str, list[Any]] = {}
        # state_hash -> per-action try count (for graceful least-tried fallback).
        self._tries: dict[str, dict[Any, int]] = {}
        # Predecessor links for shortest-path reconstruction:
        # state_hash -> list of (prev_state_hash, action_key).
        self._preds: dict[str, list[tuple[str, Any]]] = {}
        # action_key -> salience tier (0 = most promising). Simple actions 1-5
        # get the top tier so they are preferred over any click. Used by the
        # tiered local pick and the frontier promise scorer (R38).
        self._action_tier: dict[Any, int] = {}
        # state_hash -> number of times the agent has stood on this node
        # (visit count). Feeds the frontier promise penalty so exploration
        # spreads instead of re-walking the same frontier (R38).
        self._visits: dict[str, int] = {}
        # The state hash the agent most recently ENTERED via a genuine state
        # change (nxt != prev) — a proxy for the recently-changed region the
        # frontier scorer is drawn toward (R38). Reset with the graph.
        self._last_change_hash: str | None = None
        # Globally-unlocked click tier (R38). With the gate on, exploration
        # starts restricted to simple actions + tier-0 clicks; only when no such
        # untried action is reachable anywhere does the agent unlock the next
        # tier. This defers the large mass of low-promise clicks that made deep
        # discovery exhaustive (CD82 L2 burned 26,965 actions trying every
        # centroid at every state). With the gate off, all tiers are unlocked
        # from the start (ordering still applies, nothing is deferred).
        self._unlocked_tier = 0 if getattr(self, "tier_gate", True) else _N_TIERS - 1

        # HUD estimation: rolling window of per-cell "did this cell change"
        # boolean grids across recent transitions.
        self._hud_window: deque[np.ndarray] = deque(maxlen=_HUD_WINDOW)
        self._hud_mask: np.ndarray | None = None  # cached (64,64) bool, True=HUD
        # Monotonically-growing HUD mask (R39): the union of every per-step mask
        # seen this level. NOT invalidated between steps (unlike ``_hud_mask``),
        # so the hash function stabilises instead of oscillating. Reset per level.
        self._sticky_mask: np.ndarray | None = None

        # ── monotone-moving-band detection state (R44) ──────────────────────────
        # Running transition counter (small AND large steps) for the density gate.
        self._band_t = 0
        # Recent small-change transitions: (t, row_idx array, col_idx array).
        self._band_records: deque[tuple[int, np.ndarray, np.ndarray]] = deque(
            maxlen=self.band_window
        )
        # Set once a coherent drifting band is confirmed; then the accumulated
        # track (dilated) is masked and grows monotonically as the marker sweeps.
        self._band_confirmed = False
        self._band_horizontal = True  # True = thin in rows (drifts along cols)
        self._band_lo_line = 0  # inclusive thin-axis lower bound of the band
        self._band_hi_line = 0  # inclusive thin-axis upper bound of the band
        self._band_accum: np.ndarray | None = None  # (64,64) bool swept-cell union
        self._band_mask: np.ndarray | None = None  # (64,64) bool dilated band mask

        # Bookkeeping for edge recording across steps.
        self._prev_hash: str | None = None
        self._prev_action_key: Any | None = None
        self._prev_frame: np.ndarray | None = None

        self._level_steps = 0

        # Adaptive pool downshift (R42) — always-on (independent of GF_DEBUG).
        # ``_effective_pool`` is the pool factor the hash actually uses this
        # level; it starts at the configured ``hash_pool`` and drops to 1 on a
        # confirmed collapse. ``_pool_downshifted`` caps it at one downshift per
        # level. The two rolling windows carry the collapse signatures, and
        # ``_recent_states`` feeds the mobility gate (distinct-recent count).
        self._effective_pool = self.hash_pool
        self._pool_downshifted = False
        self._sl_window: deque[bool] = deque(maxlen=_INSTABILITY_WINDOW)
        self._mm_window: deque[bool] = deque(maxlen=_INSTABILITY_WINDOW)
        self._recent_states: deque[str] = deque(maxlen=30)

        # Object-segmented hash (R45). ``_hash_mode`` selects which hash the state
        # key uses this level: "pixel" (the pool ladder, default) or "object". In
        # ``on`` mode it starts "object"; ``auto`` starts "pixel" and the third-rung
        # activation (:meth:`_maybe_activate_object_hash`) flips it once, resetting
        # the graph. ``_new_state_window`` tracks, per transition, whether the
        # next-hash was never seen this level — its windowed fraction is the
        # explosion signature (states not recurring).
        self._hash_mode = "object" if self.obj_hash == "on" else "pixel"
        self._obj_hash_activated = False
        self._new_state_window: deque[bool] = deque(maxlen=_INSTABILITY_WINDOW)

        # ── goal-directed ranking state (R41 + R46 semantic measures) ───────────
        # Compact frame (int8) cached at first sighting of each state, so the
        # goal scorer can evaluate score_goal(frame_of_state, goal) as a lookup.
        self._state_frame: dict[str, np.ndarray] = {}
        # The inferred level goal (None => goal-less = pre-R41 nearest behaviour).
        self._goal: GoalSpec | None = None
        # Bumped on every re-inference so cached goal scores invalidate cleanly.
        self._goal_version = 0
        # state_hash -> (goal_version, score) memo of score_goal for that state.
        self._goal_score_cache: dict[str, tuple[int, float]] = {}
        # Semantic-progress measure tracker (R46): watches the candidate-goal
        # family over productive transitions to infer WHICH measure trends toward
        # the level clear (within-level trend + level-clear jump snapshot).
        self._measure_tracker = GoalMeasureTracker()
        # Productive transitions since the last measure observation (stride gate).
        self._productive_since_observe = 0
        # Level step at which the goal was last (re)inferred; -1 = never.
        self._last_goal_infer_step = -1
        # Consecutive goal-directed frontier picks WITHOUT the graph growing.
        # When it reaches goal_max_walks the ranker falls back to nearest until a
        # new state is discovered, so a WRONG goal cannot stall the agent (R41).
        self._goal_walks_since_progress = 0
        # Graph size (# states) at the last discovery checkpoint; growth past it
        # resets the stall counter above.
        self._graph_size_ckpt = 0
        self._dbg_goal_walks = 0

        # ── measure-guided expansion state (R47) ────────────────────────────────
        # action_key -> its ACTION-CLASS bucket. A bucket is ("s", id) for a
        # simple action or ("c", colour, size_bucket) for a click, so actions of
        # the same visual class share credit (the goal measure they tend to move).
        self._action_bucket: dict[Any, Any] = {}
        # bucket -> running sum / count of the inferred goal-measure DELTA observed
        # when an action of that bucket was taken (its mean is the bucket credit).
        self._bucket_delta_sum: dict[Any, float] = {}
        self._bucket_delta_n: dict[Any, int] = {}
        # bucket -> count of GAME_OVERs whose immediately-preceding action was of
        # that bucket (regressive evidence, subtracted from credit).
        self._bucket_deaths: dict[Any, int] = {}
        # Debug: measure-guided expansion picks taken this level.
        self._dbg_measure_walks = 0
        # Debug: goal-conditioned WM-planning picks taken this level (R53).
        self._dbg_ewm_plans = 0

    # ── harness contract ─────────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        obs = latest_frame
        if _state_name(obs) == "WIN":
            return True
        return self._level_steps >= self.giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        self._debug_tick()
        obs = latest_frame
        state = _state_name(obs)

        # Level-up: the state space changed — start a fresh graph. Before wiping
        # the per-level measure tracker, snapshot which progress measure JUMPED
        # over the cleared level and carry its TYPE forward, so the next level
        # re-instantiates the same goal shape on its own colours (R46).
        levels = _levels_completed(obs)
        if levels > self._last_levels:
            if self._goal_active:
                jump = self._measure_tracker.best_jump()
                if jump is not None:
                    self._carried_goal_type = jump.goal_type
                    self._carried_axis = jump.axis
            self._reset_level_state()
        self._last_levels = levels

        if state in ("GAME_OVER", "NOT_PLAYED"):
            # Env is being (re)started. Keep the graph, but drop the in-flight
            # edge — the transition FROM the pre-reset state to the revived
            # frame is not a game transition and must not pollute the graph.
            # GAME_OVER learning (R47): the action taken immediately BEFORE death
            # is regressive; credit its bucket with a death so measure-guided
            # expansion deprioritises that action class going forward.
            if (
                self.measure_expand
                and state == "GAME_OVER"
                and self._prev_action_key is not None
            ):
                b = self._bucket_of(self._prev_action_key)
                self._bucket_deaths[b] = self._bucket_deaths.get(b, 0) + 1
            self._prev_hash = None
            self._prev_action_key = None
            self._prev_frame = None
            return self._reset_action()

        if not _has_frame(obs):
            return self._reset_action()

        frame = _frame_2d(obs)

        # Record the transition produced by our previous action, and update the
        # HUD change statistics from the raw before/after frames.
        self._record_transition(frame)
        self._maybe_downshift_pool()
        self._maybe_activate_object_hash()

        cur_hash = self._hash(frame)
        self._recent_states.append(cur_hash)
        if self._debug:
            self._dbg_recent.append(cur_hash)
        self._visits[cur_hash] = self._visits.get(cur_hash, 0) + 1
        simple_ids, action6_ok = _availability(obs)
        self._ensure_state(cur_hash, frame, simple_ids, action6_ok)

        if self._goal_active:
            # Graph grew => a new state was discovered => the goal ranker is
            # making progress; reset the stall counter (R41). Then (re)infer the
            # goal if enough evidence has accumulated.
            if len(self._untried) > self._graph_size_ckpt:
                self._graph_size_ckpt = len(self._untried)
                self._goal_walks_since_progress = 0
            self._maybe_infer_goal(frame)

        # Goal-conditioned world-model planning (R53, GF_EWM_PLAN): when a
        # high-fit synthesized model AND an inferred goal exist, roll the model
        # out over the current candidates and take the goal-maximising move.
        # Additive: declines (returns None) below the confidence floor, so
        # exploration is unchanged whenever the model is not trusted.
        action_key = None
        if self.ewm_plan and self._ewm_result is not None and self._goal is not None:
            action_key = self._ewm_plan_action(frame, simple_ids, action6_ok)
        if action_key is None:
            action_key = self._policy(cur_hash, simple_ids, action6_ok, frame)
        if action_key is None:
            # No action available at all — reset gracefully.
            self._prev_hash = None
            self._prev_action_key = None
            self._prev_frame = None
            return self._reset_action()

        # Remember what we did FROM this state so the next call can record the
        # resulting edge.
        self._prev_hash = cur_hash
        self._prev_action_key = action_key
        self._prev_frame = frame
        if self.dealias:
            self._prev_base = self._last_base   # base of the state we act FROM
            self._action_hist.append(action_key)  # history that reaches the next state
        self._level_steps += 1

        return self._key_to_action(action_key)

    # ── HUD masking ───────────────────────────────────────────────────────────

    def _record_transition(self, frame: np.ndarray) -> None:
        """Fold the (prev_frame -> frame) diff into HUD stats + the graph edge."""
        if self._prev_frame is None or self._prev_hash is None:
            return

        # EWM observation log (R52, GF_EWM only): raw transitions become the
        # few-shot evidence for world-model synthesis. Bounded; RESET and
        # unknown keys are skipped (predict_next_frame has no RESET concept).
        if self.ewm_enabled and self._prev_frame.shape == frame.shape:
            if len(self._ewm_obs) < 4 * self.ewm_min_obs:
                idx = self._ewm_action_idx(self._prev_action_key)
                if idx is not None:
                    self._ewm_obs.append(
                        (self._prev_frame.copy(), idx, frame.copy())
                    )
            if not self._ewm_attempted and len(self._ewm_obs) >= self.ewm_min_obs:
                self._ewm_try_synthesize()

        # HUD stats: which cells changed on THIS transition (raw frames).
        if self._prev_frame.shape == frame.shape:
            changed = self._prev_frame != frame
            self._hud_window.append(changed)
            self._hud_mask = None  # invalidate cache; recompute lazily
            # Feed the moving-band detector BEFORE the edge hash below, so a
            # newly-masked band takes effect on this very transition's next-hash.
            self._band_observe(changed)
            if self._goal_active and bool(changed.any()):
                # Productive transition: fold this frame's measure vector into the
                # trend tracker at the observe stride (flood-fill cost bound).
                self._productive_since_observe += 1
                if self._productive_since_observe >= self.goal_observe_stride:
                    self._productive_since_observe = 0
                    self._measure_tracker.observe(frame)

        # Graph edge: prev_hash --action--> hash(frame under CURRENT mask).
        nxt_hash = self._hash(frame)
        key = self._prev_action_key
        edges = self._edges.setdefault(self._prev_hash, {})
        # Collapse signatures (always-on: they drive the adaptive downshift).
        mismatched = key in edges and edges[key] != nxt_hash
        # De-aliasing: a mismatch means the SOURCE base state is partially
        # observable (same base+action -> different next). Flag its base so
        # future visits split by action-history and the graph stops corrupting.
        if self.dealias and mismatched and self._prev_base is not None:
            self._aliased_bases.add(self._prev_base)
        selflooped = nxt_hash == self._prev_hash
        self._sl_window.append(bool(selflooped))
        # Dead-signature bookkeeping (GF_DEAD_SIG): attribute this outcome to the
        # action CLASS so a bucket that only ever self-loops can be deprioritised.
        if self.dead_sig and key is not None:
            b = self._bucket_of(key)
            if selflooped:
                self._ds_inert[b] = self._ds_inert.get(b, 0) + 1
            else:
                self._ds_active[b] = self._ds_active.get(b, 0) + 1
        self._mm_window.append(bool(mismatched))
        # New-state signal (R45): the object-hash explosion trigger reads how often
        # a transition lands on a never-before-seen node. ``_ensure_state`` for this
        # frame has not run yet this step, so ``nxt_hash not in self._untried`` is
        # True exactly on the FIRST sighting of the state — i.e. a non-recurring
        # (forked) transition. A saturating pixel graph drives this toward 0; a
        # jitter-explosion keeps it near 1.
        self._new_state_window.append(nxt_hash not in self._untried)
        if self._debug:
            if mismatched:
                self._dbg_mismatch += 1
            if selflooped:
                self._dbg_selfloop += 1
            else:
                self._dbg_realedge += 1
            self._dbg_unstable_window.append(bool(mismatched or selflooped))
        edges[key] = nxt_hash
        # Mark the action tried at the source state.
        untried = self._untried.get(self._prev_hash)
        if untried is not None and key in untried:
            untried.remove(key)
        tries = self._tries.setdefault(self._prev_hash, {})
        tries[key] = tries.get(key, 0) + 1
        # Predecessor link (avoid self-loops in the search graph).
        if nxt_hash != self._prev_hash:
            preds = self._preds.setdefault(nxt_hash, [])
            if (self._prev_hash, key) not in preds:
                preds.append((self._prev_hash, key))
            # Track the most recently ENTERED changed state — the frontier
            # promise scorer is drawn toward its neighbourhood (R38).
            self._last_change_hash = nxt_hash

        # Measure-guided expansion credit (R47): attribute the inferred goal-
        # measure delta of THIS transition to the action-class bucket that
        # produced it, so best-first expansion can prefer buckets that
        # historically raised the measure (a self-loop contributes a 0 delta,
        # informative evidence that this action class is inert at that state).
        if self.measure_expand and self._goal is not None:
            self._credit_bucket_delta(self._prev_hash, nxt_hash, frame, key)

    # ── executable-world-model pruning (R52) ─────────────────────────────────────

    def _ewm_action_idx(self, action_key: Any) -> int | None:
        """Map a graph action_key to the EWM combined-logit index, or None.

        Simple keys 1..5 -> ACTION1..5 (idx 0..4); click keys -> coordinate
        indices. RESET/ACTION6-bare/ACTION7 have no predict_next_frame
        semantics and are excluded from the observation log.
        """
        from .ewm.core import COORD_OFFSET, GRID, NUM_SIMPLE_ACTIONS

        if isinstance(action_key, tuple) and action_key and action_key[0] == "click":
            _, x, y = action_key
            return COORD_OFFSET + int(y) * GRID + int(x)
        if isinstance(action_key, int) and 1 <= action_key <= NUM_SIMPLE_ACTIONS:
            return action_key - 1
        return None

    def _ewm_try_synthesize(self) -> None:
        """One-shot world-model synthesis from the agent's own observations.

        Runs at most once per game (the LLM call is expensive); the result is
        kept only when its fit over ALL observations reaches ``ewm_min_fit`` —
        a low-fit model would deprioritize the wrong actions.
        """
        self._ewm_attempted = True
        from .ewm.core import Transition

        transitions = [
            Transition(frame=f, action_idx=a, next_frame=n)
            for f, a, n in self._ewm_obs
        ]
        synth = self._ewm_synthesize
        if synth is None:
            from .ewm.core import OllamaChat
            from .ewm.synthesizer import synthesize_world_model

            def synth(ts: Any) -> Any:
                return synthesize_world_model(ts, OllamaChat(), self.ewm_model)

        try:
            result = synth(transitions)
        except Exception:  # noqa: BLE001 - LLM/network failure degrades to OFF
            result = None
        if result is not None and result.train_fit >= self.ewm_min_fit:
            self._ewm_result = result
        if self._debug:
            fit = getattr(result, "train_fit", None)
            print(f"[GF-EWM] synthesized fit={fit} kept={self._ewm_result is not None}")

    def _ewm_predicts_nochange(self, frame: np.ndarray, action_key: Any) -> bool:
        """True when the accepted world model predicts this action changes nothing.

        Uncertainty (no model, unmappable key, prediction error/timeout, wrong
        shape) counts as CHANGE — never deprioritize on doubt. Cached per
        (state, key) via the caller's state hash context; cache is size-capped.
        """
        if self._ewm_result is None:
            return False
        idx = self._ewm_action_idx(action_key)
        if idx is None:
            return False
        from .ewm.core import _run_with_timeout, action_call_args

        action, xy = action_call_args(idx)
        try:
            pred = _run_with_timeout(
                self._ewm_result.fn, (frame.tolist(), action, xy), 0.05
            )
            pred_arr = np.asarray(pred, dtype=np.int16)
        except Exception:  # noqa: BLE001 - treat any failure as "change"
            return False
        if pred_arr.shape != frame.shape:
            return False
        return bool((pred_arr == frame).all())

    def _ewm_plan_candidates(
        self, frame: np.ndarray, simple_ids: list[int], action6_ok: bool
    ) -> list[int]:
        """Combined-logit action indices to roll out: available simple actions
        plus this frame's segment-click candidates (same set the graph agent
        explores). Frame-only; capped by ``max_clicks``.
        """
        from .ewm.core import COORD_OFFSET, GRID

        cands = [i - 1 for i in simple_ids if 1 <= i <= 5]  # ACTION1..5 -> 0..4
        if action6_ok:
            for x, y in _segment_click_candidates(frame, self.max_clicks):
                cands.append(COORD_OFFSET + int(y) * GRID + int(x))
        return cands

    def _ewm_plan_action(
        self, frame: np.ndarray, simple_ids: list[int], action6_ok: bool
    ) -> Any | None:
        """Pick the goal-maximising next action via forward-model rollout.

        Wraps the kept world model as a planner forward model, asks
        :func:`planner.goal.goal_directed_plan` for the best first move over the
        current candidates, and maps the chosen combined index back to a graph
        action_key. Returns None when the planner declines (low confidence) or
        no candidates exist, so the caller falls back to novelty exploration.
        """
        from .ewm.core import COORD_OFFSET, NUM_SIMPLE_ACTIONS
        from .ewm.forward_model import EWMForwardModel
        from .planner.goal import goal_directed_plan

        cands = self._ewm_plan_candidates(frame, simple_ids, action6_ok)
        if not cands:
            return None
        fwd = EWMForwardModel(self._ewm_result.fn, self._ewm_result.train_fit)
        result = goal_directed_plan(
            frame, self._goal, cands, fwd,
            horizon=self.ewm_plan_horizon,
            confidence_floor=self.ewm_plan_conf,
        )
        if result.action_idx is None:
            return None
        if self._debug:
            self._dbg_ewm_plans = getattr(self, "_dbg_ewm_plans", 0) + 1
        idx = int(result.action_idx)
        if idx < NUM_SIMPLE_ACTIONS:
            return idx + 1
        coord = idx - COORD_OFFSET
        from .ewm.core import GRID

        y, x = divmod(coord, GRID)
        return ("click", int(x), int(y))

    # ── monotone-moving-band detection (R44) ─────────────────────────────────────

    def _band_observe(self, changed: np.ndarray) -> None:
        """Fold one transition's changed-cell set into the moving-band detector.

        A "marker step" is a transition changing at most ``band_max_cells`` cells
        (a 1-cell counter/cursor move leaves ~2 changed cells). Large-change
        (productive) steps only advance the transition counter used by the density
        gate. Before confirmation, marker steps accumulate as records and
        :meth:`_try_confirm_band` looks for the drift signature. After
        confirmation, in-band marker cells extend the swept-track union and the
        dilated band mask grows monotonically so the marker stays invisible as it
        reaches new positions.
        """
        if not self.band_mask:
            return
        self._band_t += 1
        n = int(changed.sum())
        if not (0 < n <= self.band_max_cells):
            return
        ys, xs = np.nonzero(changed)
        ys = ys.astype(np.intp)
        xs = xs.astype(np.intp)
        if self._band_confirmed:
            self._grow_band(ys, xs)
            return
        self._band_records.append((self._band_t, ys, xs))
        self._try_confirm_band()

    def _grow_band(self, ys: np.ndarray, xs: np.ndarray) -> None:
        """Add in-band marker cells to the swept-track union and rebuild the mask.

        Only cells inside the confirmed thin band (``[lo_line, hi_line]`` on the
        band's thin axis) are added, so an unrelated small game change on another
        row never balloons the band. The mask is the union dilated by
        ``band_dilate`` to cover the marker's leading edge.
        """
        assert self._band_accum is not None
        if self._band_horizontal:
            keep = (ys >= self._band_lo_line) & (ys <= self._band_hi_line)
        else:
            keep = (xs >= self._band_lo_line) & (xs <= self._band_hi_line)
        if not keep.any():
            return
        before = int(self._band_accum.sum())
        self._band_accum[ys[keep], xs[keep]] = True
        if int(self._band_accum.sum()) != before:
            self._band_mask = _dilate_grid(self._band_accum, self.band_dilate)

    def _try_confirm_band(self) -> None:
        """Confirm a monotone-moving band from the accumulated marker records.

        The signature (all three required): the marker cells lie in a THIN strip
        along one axis (``<= band_thickness``) that EXTENDS along the other axis
        (``>= band_min_drift`` — the marker actually moved); the marker steps are
        DENSE over their transition span (``>= band_density`` — occur on almost
        every transition); and the per-record centroid along the drift axis is
        MONOTONE (``>= band_monotone`` of consecutive deltas share the dominant
        sign, wrap-tolerant). On confirmation the swept union of in-band cells is
        seeded and the dilated band mask is built.
        """
        recs = self._band_records
        if len(recs) < self.band_min_samples:
            return
        all_r = np.concatenate([ys for _, ys, _ in recs])
        all_c = np.concatenate([xs for _, _, xs in recs])
        rmin, rmax = int(all_r.min()), int(all_r.max())
        cmin, cmax = int(all_c.min()), int(all_c.max())
        row_ext = rmax - rmin + 1
        col_ext = cmax - cmin + 1
        horizontal = row_ext <= self.band_thickness and col_ext >= self.band_min_drift
        vertical = col_ext <= self.band_thickness and row_ext >= self.band_min_drift
        # Exactly one orientation must qualify: both => too square (a blob), and
        # neither => no thin drifting track yet.
        if horizontal == vertical:
            return

        if horizontal:
            centroids = [(t, float(xs.mean())) for t, _ys, xs in recs]
            lo_line, hi_line = rmin, rmax
        else:
            centroids = [(t, float(ys.mean())) for t, ys, _xs in recs]
            lo_line, hi_line = cmin, cmax
        centroids.sort(key=lambda tc: tc[0])
        ts = [t for t, _ in centroids]
        cs = [c for _, c in centroids]

        # Density: marker steps must cover most transitions over their span.
        span = ts[-1] - ts[0]
        if span <= 0 or len(recs) / (span + 1) < self.band_density:
            return

        # Monotonicity: dominant-sign fraction of consecutive centroid deltas.
        pos = neg = 0
        for i in range(1, len(cs)):
            d = cs[i] - cs[i - 1]
            if d > 0.4:
                pos += 1
            elif d < -0.4:
                neg += 1
        moves = pos + neg
        if moves == 0 or max(pos, neg) / moves < self.band_monotone:
            return

        # Confirmed — seed the swept union from every in-band record cell.
        self._band_confirmed = True
        self._band_horizontal = horizontal
        self._band_lo_line = lo_line
        self._band_hi_line = hi_line
        accum = np.zeros((64, 64), dtype=bool)
        for _t, ys, xs in recs:
            if horizontal:
                keep = (ys >= lo_line) & (ys <= hi_line)
            else:
                keep = (xs >= lo_line) & (xs <= hi_line)
            accum[ys[keep], xs[keep]] = True
        self._band_accum = accum
        self._band_mask = _dilate_grid(accum, self.band_dilate)

    # ── adaptive pool downshift (R42) ────────────────────────────────────────────

    def _maybe_downshift_pool(self) -> None:
        """Drop the hash pool to 1 when pooling is collapsing real states (R42).

        Fires at most once per level, and only after the level has run
        ``downshift_after`` in-level actions WITHOUT a level-up (the guard that
        makes every level clearing within that budget untouchable). On top of the
        guard, one of two collapse signatures must hold over the rolling window:

        * **self-loop sink** — the windowed fraction of transitions that hashed
          back to the SAME state is ``>= downshift_selfloop``; a real move is
          invisible to the hash, so no frontier is reachable.
        * **moving collapse** — the windowed edge-mismatch fraction is
          ``>= downshift_mismatch`` WHILE the agent is still mobile
          (``distinct-recent >= downshift_mobile``); pooling is merging distinct
          moving-object positions into one nondeterministic node.

        A third gate spares jitter-heavy levels regardless of self-loop: if the
        current HUD mask covers more than ``downshift_max_mask`` cells, pooling is
        load-bearing (real sub-cell jitter) and its high self-loop is not a
        pool-collapse — measured SK48 masks ~1100 cells, its recent-distinct stays
        ~3 even at pool=1 (a downshift does not unstick it, only strips a pooling
        its slow clear needs).

        On a fire it rebuilds the level graph with an unpooled hash (real states
        become distinct again) and pins ``_effective_pool = 1`` for the rest of
        the level. Jitter-heavy levels never reach the guard (they clear fast),
        never cross the thresholds (their pooling is doing its job), or are held
        back by the mask gate — this is why a global ``hash_pool=1`` regresses
        them but the adaptive downshift does not.
        """
        if (
            self._hash_mode == "object"
            or not self.pool_downshift
            or self._pool_downshifted
            or self._effective_pool <= 1
            or self._level_steps < self.downshift_after
            or len(self._sl_window) < self._sl_window.maxlen
        ):
            return
        # Jitter gate: a large HUD mask means pooling is load-bearing (real
        # jitter), so the high self-loop is not a pool-collapse — spare it. The
        # moving-band mask (R44) is a masked COUNTER, not sub-cell jitter, so it is
        # subtracted before the gate: masking a drifting counter must not block the
        # very pool=1 downshift that makes its now-recurring states usable.
        mask = self._hud_mask_grid()
        if mask is not None:
            jitter = mask & ~self._band_mask if self._band_mask is not None else mask
            if int(jitter.sum()) > self.downshift_max_mask:
                return
        sl_frac = sum(self._sl_window) / len(self._sl_window)
        mm_frac = sum(self._mm_window) / len(self._mm_window)
        distinct = len(set(self._recent_states))
        selfloop_sink = sl_frac >= self.downshift_selfloop
        moving_collapse = (
            mm_frac >= self.downshift_mismatch and distinct >= self.downshift_mobile
        )
        if not (selfloop_sink or moving_collapse):
            return
        self._reset_level_state()
        self._effective_pool = 1
        self._pool_downshifted = True

    # ── object-segmented hash activation (R45) ────────────────────────────────────

    def _maybe_activate_object_hash(self) -> None:
        """Flip the hash to object-segmented mode when the pixel ladder is broken.

        The THIRD rung of the hash ladder (after pool=2 -> pool=1 downshift). Fires
        at most once per level, in ``auto`` mode only, and only after the same
        no-progress guard (``downshift_after`` in-level actions with no level-up) and
        jitter-mask gate the pool downshift uses — so every game clearing within that
        budget, and every game whose large HUD mask means pooling is load-bearing, is
        untouched. On top of the guard, one of two pool-unfixable broken-graph
        signatures must hold over the rolling windows:

        * **explosion** — windowed new-state fraction ``>= obj_explode_frac`` while
          still mobile (distinct-recent ``>= obj_explode_mobile``): the pixel hash
          keeps forking never-seen states so no frontier saturates (G50T at pool=1
          after its downshift; SC25 at pool=2).
        * **persistent sink** — windowed self-loop fraction ``>= obj_sink_selfloop``
          with low distinct-recent (``<= obj_sink_distinct``), where the pool
          downshift will NOT rescue it: either already at ``_effective_pool == 1``,
          or the self-loop sits below the stronger ``downshift_selfloop`` cut so the
          downshift never triggers (DC22's 0.73 sink — a real 1-cell move pools back
          to the same block; pool=1 is never reached and would only re-explode on the
          same jitter). Strong sinks (self-loop ``>= downshift_selfloop``) are left to
          the pool downshift first; only a residual sink at pool=1 reaches here.

        On a fire the level graph is rebuilt (the pool state hashes now become object
        hashes, so real states become distinct-and-recurring) and the mode is pinned
        for the rest of the level.
        """
        if (
            self.obj_hash != "auto"
            or self._hash_mode == "object"
            or self._obj_hash_activated
            or self._level_steps < self.downshift_after
            or len(self._new_state_window) < self._new_state_window.maxlen
            or len(self._sl_window) < self._sl_window.maxlen
        ):
            return
        # Jitter-mask gate: a large HUD mask (minus the moving-band counter) means
        # pooling absorbs real sub-cell jitter and is load-bearing — the object hash
        # would have to re-derive that absorption per component; leave such levels on
        # the pixel ladder (same guard the pool downshift uses).
        mask = self._hud_mask_grid()
        if mask is not None:
            jitter = mask & ~self._band_mask if self._band_mask is not None else mask
            if int(jitter.sum()) > self.downshift_max_mask:
                return
        new_frac = sum(self._new_state_window) / len(self._new_state_window)
        sl_frac = sum(self._sl_window) / len(self._sl_window)
        distinct = len(set(self._recent_states))
        explosion = new_frac >= self.obj_explode_frac and distinct >= self.obj_explode_mobile
        pool_unfixable_sink = (
            self._effective_pool == 1 or sl_frac < self.downshift_selfloop
        )
        persistent_sink = (
            sl_frac >= self.obj_sink_selfloop
            and distinct <= self.obj_sink_distinct
            and pool_unfixable_sink
        )
        if not (explosion or persistent_sink):
            return
        self._reset_level_state()
        self._hash_mode = "object"
        self._obj_hash_activated = True

    # ── goal-directed ranking (R41 routing + R46 semantic inference) ────────────

    def _goal_engaged(self) -> bool:
        """Stall signature that gates goal-ranked frontier selection (R46).

        Goal ranking only overrides the nearest-frontier BFS once (a) the level
        has consumed ``goal_engage_after`` actions WITHOUT clearing and (b) the
        reachable in-gate frontier is still large (``goal_engage_frontier`` +
        states) — the "graph is healthy but BFS is wandering far from the goal"
        signature R40 diagnosed. Games that clear quickly never reach the gate,
        so they keep the exact pre-R46 nearest-BFS trajectory (zero-loss).
        """
        if self._level_steps < self.goal_engage_after:
            return False
        n_frontier = sum(1 for v in self._untried.values() if v)
        return n_frontier >= self.goal_engage_frontier

    # ── measure-guided expansion (R47) ─────────────────────────────────────────

    def _r47_engaged(self) -> bool:
        """Stall signature that gates measure-guided expansion (R47).

        Identical gate shape to :meth:`_goal_engaged` (a level has consumed
        ``goal_engage_after`` actions without clearing while the reachable
        frontier is still large) PLUS a confidently-inferred goal measure. Games
        that clear quickly never reach the gate, so they keep the exact pre-R47
        nearest-BFS trajectory — the gating is what protected the clearing set in
        R46 and is reused verbatim here.
        """
        return self._goal is not None and self._goal_engaged()

    def _bucket_of(self, action_key: Any) -> Any:
        """Return the action-CLASS bucket of ``action_key``.

        ``("s", id)`` for a simple action, ``("c", colour, size_bucket)`` for a
        registered click. A click not seen through :meth:`_ensure_state` (e.g. a
        raw-pixel random-escape) has no visual class on record and maps to the
        catch-all ``("c", -1, -1)`` so credit/death bookkeeping stays total.
        """
        b = self._action_bucket.get(action_key)
        if b is not None:
            return b
        if isinstance(action_key, tuple) and action_key and action_key[0] == "click":
            return ("c", -1, -1)
        return ("s", int(action_key))

    def _bucket_credit(self, bucket: Any) -> float:
        """Credit of an action-class bucket (higher = more measure-productive).

        ``mean(measure_delta) - death_w * deaths``. A bucket with fewer than
        ``measure_min_samples`` delta observations is untrusted and contributes a
        zero mean (so it is neutral, never "productive"), but a death still
        deprioritises it — a class that killed the agent is avoided even before
        its measure trend is trusted.
        """
        n = self._bucket_delta_n.get(bucket, 0)
        mean = self._bucket_delta_sum.get(bucket, 0.0) / n if n >= self.measure_min_samples else 0.0
        return mean - self.measure_death_w * self._bucket_deaths.get(bucket, 0)

    def _credit_bucket_delta(
        self, prev_hash: str, nxt_hash: str, nxt_frame: np.ndarray, action_key: Any
    ) -> None:
        """Fold this transition's goal-measure delta into its bucket's credit (R47).

        The measure of both endpoints comes from the memoised :meth:`_goal_score`
        (one flood-fill per DISTINCT state, not per transition), so the credit
        update is bounded by the graph size. Skips silently when either endpoint's
        frame is uncached (only possible before a goal is set, where this is not
        called).
        """
        self._state_frame.setdefault(nxt_hash, nxt_frame.astype(np.int8))
        m_prev = self._goal_score(prev_hash)
        m_next = self._goal_score(nxt_hash)
        if m_prev == float("-inf") or m_next == float("-inf"):
            return
        bucket = self._bucket_of(action_key)
        self._bucket_delta_sum[bucket] = self._bucket_delta_sum.get(bucket, 0.0) + (
            m_next - m_prev
        )
        self._bucket_delta_n[bucket] = self._bucket_delta_n.get(bucket, 0) + 1

    def _best_productive_untried(self, node: str) -> tuple[Any, float] | None:
        """Best in-gate untried action at ``node`` whose bucket is PRODUCTIVE.

        Among the node's untried actions within the current tier gate, returns
        the ``(action_key, credit)`` of the one whose bucket has the highest
        credit, but only if that credit is strictly positive (a productive class
        that historically moved the measure up and has not been death-flagged).
        Returns None when the node has no in-gate untried action in a productive
        bucket — the expander then does not treat this node as a target.
        """
        best_key: Any | None = None
        best_credit = 0.0
        for k in self._untried.get(node) or []:
            if self._action_tier.get(k, _N_TIERS - 1) > self._unlocked_tier:
                continue
            credit = self._bucket_credit(self._bucket_of(k))
            if credit > best_credit:
                best_credit = credit
                best_key = k
        if best_key is None:
            return None
        return best_key, best_credit

    def _measure_guided_pick(self, start: str) -> Any | None:
        """Best-first EXPANSION toward measure-improving territory (R47 core).

        BFS the observed graph from ``start`` (including ``start`` itself at
        distance 0, bounded by ``frontier_dist``). Every reachable state that has
        an in-gate untried action in a PRODUCTIVE bucket
        (:meth:`_best_productive_untried`) is a candidate, ranked lexicographically
        by (goal measure of the state, that bucket's credit, nearness). The best
        candidate is expanded: if it is the current state its productive untried
        action is returned directly; otherwise the first action of the shortest
        path toward it is returned so the agent walks there and expands on arrival.

        Returns None when no productive-bucket expansion is reachable — the caller
        then falls through to the ordinary tier walk (untried-anywhere → nearest
        frontier), so R47 only ever ADDS a preference, never removes a fallback.
        """
        best_rank: tuple[float, float, int] | None = None
        best_first: Any | None = None  # None => expand at start locally
        best_local_key: Any | None = None

        # start at distance 0 (a local productive expansion is allowed).
        pk = self._best_productive_untried(start)
        if pk is not None:
            key, credit = pk
            best_rank = (self._goal_score(start), self.measure_credit_w * credit, 0)
            best_first = None
            best_local_key = key

        visited: set[str] = {start}
        queue: deque[tuple[str, Any, int]] = deque()
        for k, nxt in (self._edges.get(start) or {}).items():
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, k, 1))
        while queue:
            node, first_action, path_len = queue.popleft()
            if path_len > self.frontier_dist:
                break  # BFS is nondecreasing in distance; nothing closer remains
            pk = self._best_productive_untried(node)
            if pk is not None:
                _key, credit = pk
                rank = (self._goal_score(node), self.measure_credit_w * credit, -path_len)
                if best_rank is None or rank > best_rank:
                    best_rank = rank
                    best_first = first_action
                    best_local_key = None
            for k, nxt in (self._edges.get(node) or {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, first_action, path_len + 1))

        if best_rank is None:
            return None
        return best_local_key if best_first is None else best_first

    def _maybe_infer_goal(self, frame: np.ndarray) -> None:
        """(Re)infer the level goal from the semantic-measure tracker (R46).

        Fires first after ``goal_infer_after`` transitions, then every
        ``goal_recadence`` steps. Two evidence sources, in priority order:

        1. **Carried type** — if a prior level clear snapshotted a goal TYPE
           (``_carried_goal_type``), re-instantiate that shape on THIS level's
           colours. This is the cross-level transfer that targets deep levels.
        2. **Within-level trend** — otherwise adopt the measure moving most
           consistently upward under productive actions, if one is confident.

        Leaving ``_goal`` None keeps the pre-R41 nearest behaviour, so an
        unconfident level simply never ranks by goal.
        """
        if not self._goal_active:
            return
        if self._level_steps < self.goal_infer_after:
            return
        # LLM goal inference (GF_LLM_GOAL): once per level, let the offline model
        # infer the target from the frame's colour histogram; feeds the same
        # goal-directed machinery below. Falls through to the heuristic on any
        # failure (offline-safe).
        if self.llm_goal and not self._llm_goal_done:
            self._llm_goal_done = True
            goal = self._infer_goal_via_llm(frame)
            if goal is not None:
                self._goal = goal
                return
        due_first = self._last_goal_infer_step < 0
        due_recadence = (
            self._last_goal_infer_step >= 0
            and self._level_steps - self._last_goal_infer_step >= self.goal_recadence
        )
        if not (due_first or due_recadence):
            return
        self._last_goal_infer_step = self._level_steps

        new_goal: GoalSpec | None = None
        if self._carried_goal_type is not None:
            new_goal = instantiate_goal_type(
                frame, self._carried_goal_type, self._carried_axis
            )
        if new_goal is None:
            trend = self._measure_tracker.best_trend()
            if trend is not None:
                new_goal = trend[0]
        if new_goal is not None and new_goal != self._goal:
            self._goal = new_goal
            self._goal_version += 1  # invalidate cached scores lazily
            self._goal_walks_since_progress = 0  # fresh goal earns a fresh budget

    def _infer_goal_via_llm(self, frame: np.ndarray):
        """Ask the offline model to infer the level goal (GF_LLM_GOAL).

        Reuses planner.goal_inference.infer_goal with an ollama-backed llm_call;
        returns a GoalSpec or None (None => caller keeps the heuristic path). All
        failures degrade to None so the agent never blocks.
        """
        import json
        import urllib.request

        from .planner.goal_inference import color_histogram_from_frame, infer_goal

        def _ollama(prompt: str) -> str:
            body = {
                "model": self.llm_goal_model, "stream": False, "think": False,
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0.0, "num_ctx": 8192, "num_predict": 200},
            }
            req = urllib.request.Request(
                f"{self.llm_goal_host}/api/chat", data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())["message"]["content"]

        try:
            hist = color_histogram_from_frame(frame)
            return infer_goal(hist, [], llm_call=_ollama, grid_shape=frame.shape)
        except Exception:  # noqa: BLE001 - offline-safe: keep heuristic on failure
            return None

    def _goal_score(self, node: str) -> float:
        """Cached goal-proximity score of ``node``'s frame (higher = closer).

        Memoised per (goal_version, node) so re-ranking frontiers each frontier
        walk is a dict lookup, not a re-scan. Returns ``-inf`` for a node whose
        frame was never cached (should not happen for graph states, but keeps
        the ranker total).
        """
        frame = self._state_frame.get(node)
        if frame is None or self._goal is None:
            return float("-inf")
        cached = self._goal_score_cache.get(node)
        if cached is not None and cached[0] == self._goal_version:
            return cached[1]
        s = score_goal(frame, self._goal)
        self._goal_score_cache[node] = (self._goal_version, s)
        return s

    def _hud_mask_grid(self) -> np.ndarray | None:
        """Return the cached (64,64) HUD bool mask (True = mask out), or None.

        The mask is the UNION of two components:

        * **Per-cell** — a cell is HUD if it changed in more than
          ``hud_threshold`` of the recent transitions (catches a static cell
          that flips on almost every step, e.g. a fixed 1-pixel timer dot).
        * **Region** (R36c, when ``region_mask``) — cells changing above the low
          ``region_low`` threshold are grouped into 4-connected components,
          dilated by ``region_dilate``; any region whose *aggregate* change-rate
          (fraction of transitions on which ANY of its cells changed) exceeds
          ``region_rate`` is masked whole. This catches a moving-digit counter
          whose individual cells stay below ``hud_threshold`` yet collectively
          repaint on most steps (the R36b SP80/CN04/LS20/BP35 blocker).

        Below ``_HUD_MIN_SAMPLES`` observed transitions the mask is untrusted
        and None is returned (state hash uses the raw frame).
        """
        if self._hud_mask is not None:
            return self._hud_mask
        n = len(self._hud_window)
        # The moving-band mask (R44) is trusted on its OWN sample budget
        # (band_min_samples marker steps), independent of the per-cell change-rate
        # window, so it can apply even before the per-cell mask is trusted.
        band = self._band_mask
        if n < _HUD_MIN_SAMPLES:
            if band is None:
                return None
            mask = band.copy()
        else:
            stacked = np.stack(self._hud_window, axis=0)  # (n, 64, 64) bool
            rate = stacked.mean(axis=0)  # per-cell change fraction
            mask = rate > self.hud_threshold
            if self.region_mask:
                mask = mask | self._region_mask_from_rate(rate, stacked)
            if band is not None:
                mask = mask | band
        if self.sticky_mask:
            # Monotonic union: once a cell is HUD it stays HUD, so the hash stops
            # oscillating and real states recur (R39). ``_sticky_mask`` survives
            # the per-step ``_hud_mask`` invalidation, so the union only grows.
            if self._sticky_mask is None or self._sticky_mask.shape != mask.shape:
                self._sticky_mask = mask.copy()
            else:
                self._sticky_mask |= mask
            mask = self._sticky_mask
        self._hud_mask = mask
        return self._hud_mask

    def _region_mask_from_rate(
        self, rate: np.ndarray, stacked: np.ndarray
    ) -> np.ndarray:
        """Build the region component of the HUD mask from change statistics.

        Args:
            rate: (64,64) per-cell fraction of recent transitions on which the
                cell changed.
            stacked: (n,64,64) bool "did this cell change on transition t" window
                used to compute a region's aggregate change-rate.

        Returns:
            (64,64) bool mask: True for cells inside a high-aggregate-rate region.
        """
        noisy = rate > self.region_low
        out = np.zeros_like(noisy, dtype=bool)
        if not noisy.any():
            return out
        # A region wider than ``region_max_frac`` of the frame is the play field,
        # not a HUD widget — masking it would blind the agent (R39). Skip it so a
        # whole-board animation (LS20: a 675-cell region crossing agg-rate > 0.7)
        # never enters the sticky union and grows to cover every cell.
        max_region = self.region_max_frac * float(rate.size)
        for comp in _connected_components(noisy):
            if len(comp) > max_region:
                continue
            rows = np.fromiter((r for r, _ in comp), dtype=np.intp, count=len(comp))
            cols = np.fromiter((c for _, c in comp), dtype=np.intp, count=len(comp))
            # Aggregate region change-rate: on what fraction of transitions did
            # ANY cell in this region change? A moving-digit display repaints on
            # (almost) every step even though each glyph cell flickers rarely.
            region_changed_per_step = stacked[:, rows, cols].any(axis=1)
            agg_rate = float(region_changed_per_step.mean())
            if agg_rate > self.region_rate:
                self._paint_dilated(out, rows, cols)
        return out

    def _paint_dilated(
        self, out: np.ndarray, rows: np.ndarray, cols: np.ndarray
    ) -> None:
        """Set ``out`` True for the given cells dilated by ``region_dilate``.

        Dilation covers glyph edges the ``region_low`` threshold missed — a
        digit's outer stroke may change on fewer than ``region_low`` of steps
        yet still belong to the counter display.
        """
        h, w = out.shape
        d = self.region_dilate
        r0 = max(0, int(rows.min()) - d)
        r1 = min(h, int(rows.max()) + d + 1)
        c0 = max(0, int(cols.min()) - d)
        c1 = min(w, int(cols.max()) + d + 1)
        # Dilate the exact component cells (not the bounding box) so a sparse
        # noisy component does not swallow an unrelated stable neighbour region;
        # the per-cell dilation still bridges the glyph strokes.
        if d <= 0:
            out[rows, cols] = True
            return
        local = np.zeros((r1 - r0, c1 - c0), dtype=bool)
        local[rows - r0, cols - c0] = True
        dilated = local.copy()
        for dr in range(-d, d + 1):
            for dc in range(-d, d + 1):
                if dr == 0 and dc == 0:
                    continue
                shifted = np.zeros_like(local)
                sr0, sr1 = max(0, dr), local.shape[0] + min(0, dr)
                sc0, sc1 = max(0, dc), local.shape[1] + min(0, dc)
                tr0, tr1 = max(0, -dr), local.shape[0] + min(0, -dr)
                tc0, tc1 = max(0, -dc), local.shape[1] + min(0, -dc)
                shifted[sr0:sr1, sc0:sc1] = local[tr0:tr1, tc0:tc1]
                dilated |= shifted
        out[r0:r1, c0:c1] |= dilated

    def _base_hash(self, frame: np.ndarray) -> str:
        """The pre-de-aliasing state hash (object multiset or HUD-masked pool)."""
        if self._hash_mode == "object":
            return self._object_hash(frame)
        mask = self._hud_mask_grid()
        if mask is not None and mask.shape == frame.shape:
            masked = frame.copy()
            masked[mask] = 0
        else:
            masked = frame
        pooled = _max_pool(masked, self._effective_pool)
        return hashlib.md5(np.ascontiguousarray(pooled).tobytes()).hexdigest()[:16]

    def _hash(self, frame: np.ndarray) -> str:
        """Hash the (HUD-masked, max-pooled) frame so real states recur.

        Two independent noise absorbers stack here:

        * **HUD mask** zeroes cells that flip on almost every step (counters /
          animated overlays), so a static-but-flickering pixel does not fork the
          state.
        * **Max-pool** (``hash_pool`` factor) coarsens the frame before hashing.
          Several games (M0R0, CD82, CN04) carry sub-cell jitter — a token that
          nudges a pixel or an anti-aliased edge — that no per-cell HUD rule
          catches, yet it makes every raw frame unique so the graph never
          recurs (measured: M0R0 71%%->18%%, CD82 68%%->11%% distinct states
          under 2x2 pooling). Pooling absorbs it while preserving gross layout.

        In object-hash mode (R45) the key is the object multiset instead — see
        :meth:`_object_hash`.
        """
        base = self._base_hash(frame)
        self._last_base = base
        # Hidden-state DE-ALIASING (GF_DEALIAS, default OFF => byte-identical):
        # once a base state is observed to ALIAS (same base+action -> different
        # next, i.e. partial observability), split it by recent action-history so
        # the two true-states separate. Only aliased bases get the suffix, so the
        # graph does not explode. The novel primitive no M1 winner has.
        if self.dealias and base in self._aliased_bases:
            kgram = ",".join(str(a) for a in self._action_hist)
            return hashlib.md5(f"{base}|{kgram}".encode()).hexdigest()[:16]
        return base

    def _object_hash(self, frame: np.ndarray) -> str:
        """Hash the frame by its OBJECTS, not its raw pixels (R45).

        The (HUD/band-mask-subtracted) frame is segmented into 4-connected
        components per non-background colour. The key is the md5 of the SORTED
        multiset of ``(colour, size_bucket, centroid_row, centroid_col)`` tokens:

        * ``centroid_row/col`` at FULL cell resolution (rounded component centroid),
          so a 1-cell object move produces a DIFFERENT key — movement is visible.
        * ``size_bucket`` = ``area.bit_length()`` (a log2 bucket), and the
          component's interior/shape is dropped entirely, so intra-object jitter
          that flips a few pixels leaves colour + bucket + rounded centroid
          unchanged — the SAME key. Jitter is absorbed.

        The HUD/band mask is subtracted by repainting masked cells to the background
        colour so a counter/animation never spawns phantom components. Pure of
        ``_effective_pool`` (object mode ignores pooling). Fast: one
        :func:`_connected_components` pass per non-background colour, ~1 ms/frame.
        """
        work = frame
        mask = self._hud_mask_grid()
        values, counts = np.unique(work, return_counts=True)
        background = int(values[int(np.argmax(counts))])
        if mask is not None and mask.shape == work.shape and mask.any():
            work = frame.copy()
            work[mask] = background
            values, counts = np.unique(work, return_counts=True)
            background = int(values[int(np.argmax(counts))])
        tokens: list[tuple[int, int, int, int]] = []
        for colour in values:
            colour = int(colour)
            if colour == background:
                continue
            comp_mask = work == colour
            for comp in _connected_components(comp_mask):
                area = len(comp)
                cy = int(round(sum(r for r, _ in comp) / area))
                cx = int(round(sum(c for _, c in comp) / area))
                tokens.append((colour, area.bit_length(), cy, cx))
        tokens.sort()
        return hashlib.md5(repr(tokens).encode()).hexdigest()[:16]

    # ── graph maintenance ──────────────────────────────────────────────────────

    def _ensure_state(
        self,
        state_hash: str,
        frame: np.ndarray,
        simple_ids: list[int],
        action6_ok: bool,
    ) -> None:
        """Register ``state_hash`` with its untried action set if unseen.

        Simple actions (1-5) are registered first and always ranked above any
        click via a sentinel tier ``_SIMPLE_TIER`` (< 0) so requirement 3
        (try simple before clicks in a fresh state) holds for both the local
        pick and the frontier promise scorer. Click candidates carry their
        interactivity tier from :func:`_segment_click_candidates_tiered`.
        """
        if state_hash in self._untried:
            return
        # Cache a compact frame for the goal scorer (R41/R47). Colours are indices
        # in [0, 15], so int8 is exact and keeps the per-state footprint at ~4 KB.
        if self._goal_active:
            self._state_frame.setdefault(state_hash, frame.astype(np.int8))
        actions: list[Any] = list(simple_ids)  # simple actions first
        for aid in simple_ids:
            self._action_tier.setdefault(aid, _SIMPLE_TIER)
            if self.measure_expand:
                self._action_bucket.setdefault(aid, ("s", int(aid)))
        if action6_ok:
            if self.measure_expand:
                # Rich segmentation carries the target's colour + size bucket so a
                # click's action-CLASS (its visual family) can accrue measure credit.
                for (x, y, tier, colour, size_bucket) in _segment_click_candidates_rich(
                    frame, self.max_clicks
                ):
                    key = ("click", x, y)
                    actions.append(key)
                    prev = self._action_tier.get(key)
                    self._action_tier[key] = tier if prev is None else min(prev, tier)
                    self._action_bucket.setdefault(key, ("c", int(colour), int(size_bucket)))
            else:
                for (x, y, tier) in self._click_candidates(frame):
                    key = ("click", x, y)
                    actions.append(key)
                    # A cell may recur across states; keep its best (lowest) tier.
                    prev = self._action_tier.get(key)
                    self._action_tier[key] = tier if prev is None else min(prev, tier)
        self._untried[state_hash] = actions
        self._edges.setdefault(state_hash, {})
        self._tries.setdefault(state_hash, {})

    # ── click candidate segmentation ───────────────────────────────────────────

    def _click_candidates(self, frame: np.ndarray) -> list[tuple[int, int, int]]:
        """Reduce ACTION6 to a small tier-ordered set of ``(x, y, tier)`` clicks.

        Segment the frame into 4-connected components per non-background colour
        (background = the single most-frequent colour). Each component yields its
        centroid as a candidate click, bucketed into an interactivity tier
        (0 = most likely a control: small, rare-coloured, high-contrast, not
        background-hugging). Returned tier-first so the caller tries the most
        promising clicks before the rest. Capped at ``max_clicks``.

        Coordinates follow the arcengine convention where ``x`` is the column and
        ``y`` is the row, so a centroid at grid ``(row, col)`` maps to
        ``(x=col, y=row)``.
        """
        return _segment_click_candidates_tiered(frame, self.max_clicks)

    # ── policy ─────────────────────────────────────────────────────────────────

    def _policy(
        self,
        state_hash: str,
        simple_ids: list[int],
        action6_ok: bool,
        frame: np.ndarray,
    ) -> Any | None:
        """Pick an action_key for the current state.

        1. Untried action at the current state -> take it. With
           ``tier_priority`` (R38) the highest-tier untried action wins (simple
           actions rank above every click; clicks by ascending interactivity
           tier). Without it, registration order (simple before click).
        2. Otherwise pick a FRONTIER state and take the first action toward it.
           With ``tier_priority`` the frontier is chosen by PROMISE discounted by
           path length (:meth:`_best_frontier`); without it, the nearest frontier
           by edge count (:meth:`_bfs_to_frontier`). Concentrating the budget on
           promising frontiers is the whole point of R38 — uniform nearest-first
           exploration burned 26,965 actions on CD82 L2.
        3. If no frontier is reachable in the known graph, take a **true random
           action** from the currently-available set (R36d). This is the
           escape hatch for the self-absorbing-sink stall: over-masking or edge
           nondeterminism can collapse the current node into a state whose every
           observed out-edge loops back to itself, so BFS (which skips
           self-loops) reports "no frontier" forever. The previous fallback
           RESET into that same sink — the revived frame re-hashed to the same
           node and the agent burned the whole budget re-selecting RESET
           (measured SP80: bfs_fires froze at 55, recent_distinct=1/30, 0
           clears). A random action executes against the LIVE env and can knock
           the game into a genuinely different real state that the collapsed
           graph could not represent, re-seeding exploration.
        4. Only if there is no legal action at all does this return None (the
           caller then RESETs). That happens on empty-availability screens, not
           on exhausted-but-live states.
        """
        if not self.tier_priority:
            # Pre-R38 behaviour: registration-order local pick, nearest frontier.
            untried = self._untried.get(state_hash) or []
            if untried:
                self._dbg_untried += 1
                return untried[0]
            first_action = self._bfs_to_frontier(state_hash)
            if first_action is not None:
                self._dbg_bfs += 1
                return first_action
            self._dbg_bfs_fail += 1
            escape = self._random_action_key(simple_ids, action6_ok, frame)
            if escape is not None:
                self._dbg_random += 1
                return escape
            return None

        # Measure-guided expansion (R47): once a level has STALLED and a goal
        # measure is confidently inferred, prefer expanding an untried action in a
        # PRODUCTIVE bucket at a HIGH-measure reachable state (A*-flavoured
        # expansion toward measure-improving territory) BEFORE the uniform tier
        # walk. Returns None when no productive-bucket expansion is reachable, so
        # exploration below is unchanged for every non-engaged / early step.
        if self.measure_expand and self._r47_engaged():
            key = self._measure_guided_pick(state_hash)
            if key is not None:
                self._dbg_measure_walks += 1
                return key

        # Tier-gated exploration (R38). Try, in order, at the current unlocked
        # tier: a local within-tier untried action, then a promise-scored walk to
        # a within-tier frontier. If neither exists, unlock the next tier and
        # retry; only once every tier is exhausted globally do we random-escape.
        while True:
            key = self._best_untried_within_tier(state_hash, frame)
            if key is not None:
                self._dbg_untried += 1
                self._count_tier_hit(key)
                return key

            first_action = self._best_frontier(state_hash)
            if first_action is not None:
                self._dbg_bfs += 1
                return first_action

            if self._unlocked_tier < _N_TIERS - 1:
                self._unlocked_tier += 1
                continue  # widen the tier gate and re-evaluate this state
            break

        # No within-any-tier untried action and no reachable frontier -> escape.
        self._dbg_bfs_fail += 1
        escape = self._random_action_key(simple_ids, action6_ok, frame)
        if escape is not None:
            self._dbg_random += 1
            return escape
        return None

    def _best_untried_within_tier(
        self, state_hash: str, frame: np.ndarray | None = None
    ) -> Any | None:
        """Return the current state's highest-tier untried action within the gate.

        Only actions whose tier is ``<= _unlocked_tier`` (simple actions carry
        ``_SIMPLE_TIER`` < 0 and are always in-gate) are eligible, so the large
        mass of low-tier clicks stays deferred until the gate widens. Among
        eligible actions the lowest tier wins; ties keep registration order for
        determinism. Returns None when the state has no in-gate untried action.

        With an accepted world model (R52, GF_EWM), actions the model predicts
        as no-change sort AFTER predicted-change actions within the same tier —
        deprioritized, never removed, so a wrong model costs ordering only.
        """
        untried = self._untried.get(state_hash) or []
        eligible = [
            k for k in untried
            if self._action_tier.get(k, _N_TIERS - 1) <= self._unlocked_tier
        ]
        if not eligible:
            return None
        if self._ewm_result is not None and self.ewm_prune and frame is not None:
            if len(self._ewm_pred_cache) > 50_000:
                self._ewm_pred_cache.clear()

            def _nochange(k: Any) -> bool:
                ck = (state_hash, k)
                if ck not in self._ewm_pred_cache:
                    self._ewm_pred_cache[ck] = self._ewm_predicts_nochange(frame, k)
                return self._ewm_pred_cache[ck]

            return min(
                eligible,
                key=lambda k: (
                    self._action_tier.get(k, _N_TIERS - 1), _nochange(k)
                ),
            )
        if self.dead_sig:
            # Empirically-inert action classes sort last within their tier.
            return min(
                eligible,
                key=lambda k: (
                    self._action_tier.get(k, _N_TIERS - 1), self._bucket_is_dead(k)
                ),
            )
        return min(eligible, key=lambda k: self._action_tier.get(k, _N_TIERS - 1))

    def _bucket_is_dead(self, action_key: Any) -> bool:
        """True if this action's CLASS has only ever self-looped (GF_DEAD_SIG).

        A bucket is 'dead' once it has >= ``dead_sig_min`` inert (self-loop)
        observations and ZERO state-changing observations. Conservative: any
        single change revives the class, so a genuinely-useful action is never
        permanently suppressed.
        """
        b = self._bucket_of(action_key)
        return (
            self._ds_active.get(b, 0) == 0
            and self._ds_inert.get(b, 0) >= self.dead_sig_min
        )

    def _count_tier_hit(self, key: Any) -> None:
        """Increment the debug per-tier local-pick counter (no-op if not debug)."""
        if not self._debug:
            return
        tier = self._action_tier.get(key, _N_TIERS - 1)
        # Simple actions land in the last slot; click tiers 0..N-1 in their slot.
        idx = _N_TIERS if tier == _SIMPLE_TIER else min(tier, _N_TIERS - 1)
        self._dbg_tier_hits[idx] += 1

    def _in_gate_best_tier(self, node: str) -> int | None:
        """Best (lowest) untried tier at ``node`` that is within the tier gate.

        Returns None when ``node`` has no untried action at or below the
        currently unlocked tier — such a node is NOT a frontier for the current
        gate and the promise search skips it.
        """
        best: int | None = None
        for k in self._untried.get(node) or []:
            tier = self._action_tier.get(k, _N_TIERS - 1)
            if tier <= self._unlocked_tier and (best is None or tier < best):
                best = tier
        return best

    def _frontier_promise(self, best_tier: int, node: str) -> float:
        """Distance-free promise of an in-gate frontier ``node`` (higher better).

        Used only to break ties AMONG frontiers at the SAME shortest distance, so
        it never overrides BFS shell expansion (that expansion is what reaches
        deep goals — CD82 L2). Rewards a better in-gate untried tier, proximity to
        the most-recently-changed region, and fewer prior visits. See R38 docs.
        """
        tier_term = float(_N_TIERS - best_tier)  # tier-0 highest, tier-2 lowest
        visit_term = self.visit_penalty * self._visits.get(node, 0)
        recency_term = (
            self.recency_bonus
            if self._last_change_hash is not None and node == self._last_change_hash
            else 0.0
        )
        return tier_term + recency_term - visit_term

    def _goal_ranked_frontier(self, start: str) -> Any | None:
        """First action toward the best goal-ranked in-gate frontier (R41).

        BFS the observed graph from ``start`` (bounded by ``frontier_dist``),
        collecting every reachable in-gate frontier with the first action out of
        ``start`` on its shortest path and that path's length. Each frontier is
        ranked by a blend of goal-proximity and nearness::

            rank = goal_blend * goal_norm + (1 - goal_blend) * 1/(1 + path_len)

        where ``goal_norm`` is the frontier's :meth:`_goal_score` min-max
        normalised across the candidate set (so the unnormalised, goal-type-
        specific score magnitude never dominates the distance term). The first
        action of the highest-rank frontier is returned.

        Returns None when NO in-gate frontier lies within ``frontier_dist`` — the
        caller then finds the nearest one unbounded, so goal ranking degrades
        gracefully to plain nearest-BFS instead of stalling on a far/wrong goal.

        In ``goal_shell`` mode (default) the candidate set is restricted to the
        NEAREST in-gate frontier shell, so the goal never overrides distance — it
        only breaks ties among equidistant frontiers, preserving the BFS shell
        expansion that reaches barely-in-budget deep goals (R38 lesson).
        """
        candidates: list[tuple[str, Any, int]] = []  # (node, first_action, len)
        visited: set[str] = {start}
        queue: deque[tuple[str, Any, int]] = deque()
        for key, nxt in (self._edges.get(start) or {}).items():
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, key, 1))
        while queue:
            node, first_action, path_len = queue.popleft()
            if path_len > self.frontier_dist:
                break  # BFS is nondecreasing in distance; nothing closer remains
            # In shell mode, once the nearest in-gate shell is collected, deeper
            # nodes cannot be candidates — stop as soon as a farther shell begins.
            if self.goal_shell and candidates and path_len > candidates[0][2]:
                break
            if self._in_gate_best_tier(node) is not None:
                candidates.append((node, first_action, path_len))
            for key, nxt in (self._edges.get(node) or {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, first_action, path_len + 1))

        if not candidates:
            return None

        scores = [self._goal_score(node) for node, _, _ in candidates]
        lo, hi = min(scores), max(scores)
        span = hi - lo
        best_action: Any | None = None
        best_rank = float("-inf")
        for (_, first_action, path_len), s in zip(candidates, scores):
            goal_norm = (s - lo) / span if span > 0.0 else 0.0
            dist_term = 1.0 / (1.0 + path_len)
            rank = self.goal_blend * goal_norm + (1.0 - self.goal_blend) * dist_term
            if rank > best_rank:
                best_rank = rank
                best_action = first_action
        return best_action

    def _best_frontier(self, start: str) -> Any | None:
        """First action toward a reachable in-gate frontier (R38).

        BFS the observed graph from ``start``, carrying the first action out of
        ``start`` on the shortest path to each node. A node counts as a frontier
        only if it has an untried action WITHIN the current tier gate. Behaviour
        depends on whether promise scoring is active:

        * **Promise inactive** (``visit_penalty == 0 and recency_bonus == 0``,
          the safe default) — return the FIRST in-gate frontier in BFS order,
          i.e. the nearest, exactly like plain nearest-BFS. This preserves the
          systematic shell expansion that reaches deep goals; measured on CD82
          this reproduces the baseline L2 clear at 26,965 actions bit-for-bit.
        * **Promise active** — among the NEAREST frontier shell only, break ties
          by promise (better in-gate tier, closer to the recently-changed region,
          fewer visits). Distance is never overridden — a farther frontier can
          never beat a nearer one — so deep-goal coverage is retained while the
          within-shell choice is nudged toward promise. ``frontier_dist`` caps
          how deep the tie-break is computed.

        Returns None when no in-gate frontier is reachable (the caller then
        unlocks the next tier, or random-escapes).

        **Goal-directed ranking (R41)** — when a goal is inferred and the stall
        cap is not exceeded, the reachable in-gate frontiers within
        ``frontier_dist`` are ranked by ``score_goal`` blended with nearness
        (``goal_blend``) instead of strictly nearest-first, so the budget walks
        toward the level-complete condition. If no in-gate frontier is within
        ``frontier_dist`` the goal branch declines and the code below finds the
        nearest one unbounded — so goal ranking never gets the agent stuck.
        """
        if (
            self.goal_rank
            and self._goal is not None
            and self.goal_blend > 0.0
            and self._goal_walks_since_progress < self.goal_max_walks
            and self._goal_engaged()
        ):
            goal_action = self._goal_ranked_frontier(start)
            if goal_action is not None:
                self._goal_walks_since_progress += 1
                self._dbg_goal_walks += 1
                return goal_action

        promise_active = self.visit_penalty != 0.0 or self.recency_bonus != 0.0

        visited: set[str] = {start}
        # node -> (first_action_out_of_start, path_len)
        queue: deque[tuple[str, Any, int]] = deque()
        for key, nxt in (self._edges.get(start) or {}).items():
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, key, 1))

        nearest_dist: int | None = None
        best_action: Any | None = None
        best_promise = float("-inf")

        while queue:
            node, first_action, path_len = queue.popleft()
            # BFS visits in nondecreasing distance; once the nearest in-gate
            # frontier shell is finished, deeper nodes cannot improve the pick.
            if nearest_dist is not None and path_len > nearest_dist:
                break
            best_tier = self._in_gate_best_tier(node)
            if best_tier is not None:
                if not promise_active:
                    # Nearest-BFS-first: return immediately (no reordering).
                    return first_action
                nearest_dist = path_len
                if path_len <= self.frontier_dist:
                    promise = self._frontier_promise(best_tier, node)
                    if promise > best_promise:
                        best_promise = promise
                        best_action = first_action
                elif best_action is None:
                    best_action = first_action
            for key, nxt in (self._edges.get(node) or {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, first_action, path_len + 1))

        return best_action

    def _random_action_key(
        self, simple_ids: list[int], action6_ok: bool, frame: np.ndarray
    ) -> Any | None:
        """Uniformly sample one legal action_key for the sink-escape fallback.

        Draws from the available simple ids plus, when ACTION6 is offered, a
        click that is EITHER a segment centroid OR a fully-random (x, y) pixel.
        The random-pixel option is essential for single-state sinks whose escape
        requires clicking a cell the segmentation never proposes: FT09 collapses
        to one state with 14 self-looping centroid clicks (measured: states=1,
        random escape fired every step yet never left because it only re-picked
        those 14 dead centroids). A uniform pixel draw eventually lands on a
        live cell and re-seeds exploration. Returns None only when nothing is
        available.
        """
        choices: list[Any] = list(simple_ids)
        if action6_ok:
            # Half the ACTION6 mass on salient centroids, half on a raw pixel.
            if self._rng.random() < 0.5:
                cands = self._click_candidates(frame)
                if cands:
                    x, y, _tier = self._rng.choice(cands)
                    choices.append(("click", int(x), int(y)))
            h, w = frame.shape if frame.ndim == 2 else (64, 64)
            choices.append(("click", self._rng.randrange(w), self._rng.randrange(h)))
        if not choices:
            return None
        return self._rng.choice(choices)

    def _bfs_to_frontier(self, start: str) -> Any | None:
        """Shortest path (by edge count) from ``start`` to a frontier state.

        Returns the FIRST action_key of that path, or None if no state with
        untried actions is reachable in the observed graph. The start state is
        never itself treated as the frontier (its untried set is empty here, or
        the caller would have taken it directly).
        """
        # first_action carried with each queued node = the action taken out of
        # `start` on the shortest path currently reaching that node.
        visited: set[str] = {start}
        queue: deque[tuple[str, Any]] = deque()
        for key, nxt in (self._edges.get(start) or {}).items():
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, key))

        while queue:
            node, first_action = queue.popleft()
            if self._untried.get(node):
                return first_action
            for key, nxt in (self._edges.get(node) or {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, first_action))
        return None

    # ── action plumbing ─────────────────────────────────────────────────────────

    def _key_to_action(self, action_key: Any) -> Any:
        from .types import ActionType, GameAction

        if isinstance(action_key, tuple) and action_key and action_key[0] == "click":
            _, x, y = action_key
            internal = GameAction.coordinate(int(x), int(y))
        else:
            internal = GameAction.simple(ActionType(int(action_key)))
        return self._convert_action(internal)

    def _reset_action(self) -> Any:
        from .types import GameAction

        return self._convert_action(GameAction.reset())


# ── segmentation (module-level so tests can call it directly) ─────────────────


def _max_pool(frame: np.ndarray, k: int) -> np.ndarray:
    """Max-pool a 2D int frame into non-overlapping ``k``x``k`` blocks.

    Returns the frame unchanged when ``k <= 1`` or it does not tile evenly (the
    trailing rows/cols are dropped from the pooled view only, never from the
    hash-of-raw fallback). Pure function so tests can call it directly.
    """
    if k <= 1 or frame.ndim != 2:
        return frame
    h, w = frame.shape
    ph, pw = h // k, w // k
    if ph == 0 or pw == 0:
        return frame
    trimmed = frame[: ph * k, : pw * k]
    return trimmed.reshape(ph, k, pw, k).max(axis=(1, 3))


def _dilate_grid(grid: np.ndarray, d: int) -> np.ndarray:
    """Return ``grid`` binary-dilated by ``d`` cells (8-connectivity per step).

    A pure function so the moving-band mask (R44) and tests can call it directly.
    Returns a copy at ``d <= 0``. Dilation covers the marker's leading edge (its
    next position lies one cell beyond the current swept union) and glyph edges.
    """
    if d <= 0:
        return grid.copy()
    out = grid.copy()
    for _ in range(d):
        cur = out
        nxt = cur.copy()
        nxt[1:, :] |= cur[:-1, :]
        nxt[:-1, :] |= cur[1:, :]
        nxt[:, 1:] |= cur[:, :-1]
        nxt[:, :-1] |= cur[:, 1:]
        nxt[1:, 1:] |= cur[:-1, :-1]
        nxt[1:, :-1] |= cur[:-1, 1:]
        nxt[:-1, 1:] |= cur[1:, :-1]
        nxt[:-1, :-1] |= cur[1:, 1:]
        out = nxt
    return out


def _segment_click_candidates(frame: np.ndarray, max_clicks: int) -> list[tuple[int, int]]:
    """Return up to ``max_clicks`` salience-ordered (x, y) component centroids.

    See :meth:`GraphFrontierAgent._click_candidates` for the salience rationale.
    Pure function of the frame so it is unit-testable in isolation. This is the
    tier-agnostic view (tier information is dropped) kept for callers/tests that
    only need the ordered coordinate list.
    """
    return [(x, y) for x, y, _tier in _segment_click_candidates_tiered(frame, max_clicks)]


# Number of salience tiers a click candidate can fall into. Tier 0 is the most
# likely-interactive (small, rare-coloured, high-contrast, not background-hugging);
# higher tier index = less promising. The policy exhausts a state's tier-0
# candidates before its tier-1, etc., and the frontier scorer rewards states
# still holding low-index (high-promise) untried tiers.
_N_TIERS = 3


def _segment_click_candidates_tiered(
    frame: np.ndarray, max_clicks: int
) -> list[tuple[int, int, int]]:
    """Return up to ``max_clicks`` click candidates as ``(x, y, tier)`` triples.

    Thin projection of :func:`_segment_click_candidates_rich` that drops the
    per-candidate colour and size-bucket (kept for the callers/tests that only
    need the tier-ordered coordinate list). See the rich function for the full
    salience-tier rationale.
    """
    return [
        (x, y, tier)
        for x, y, tier, _colour, _size in _segment_click_candidates_rich(
            frame, max_clicks
        )
    ]


def _segment_click_candidates_rich(
    frame: np.ndarray, max_clicks: int
) -> list[tuple[int, int, int, int, int]]:
    """Return click candidates as ``(x, y, tier, colour, size_bucket)`` quintuples.

    Each non-background 4-connected component contributes its centroid. Every
    component is scored for *interactivity likelihood* from purely visual cues
    and bucketed into one of ``_N_TIERS`` tiers (0 = most likely interactive):

    * **small area** — buttons/tokens are small; a huge blob is usually board
      background or a wall.
    * **rare colour** — a colour that paints few cells is more likely a control
      than a fill colour.
    * **high local contrast** — a component whose border colours differ from its
      own colour stands out (isolated widget) rather than blending into a field.
    * **not background-adjacent-huge** — a large component whose neighbours are
      mostly background is a passive backdrop; it is demoted to the lowest tier.

    The list is returned tier-first (all tier-0 before any tier-1) and, within a
    tier, smaller-area / rarer-colour first, so a caller consuming it in order
    naturally tries the most promising clicks first. Deduplicated by centroid.
    Pure function of the frame so it is unit-testable in isolation. The extra
    ``colour`` and ``size_bucket`` (``area.bit_length()``) fields let the R47
    measure-guided expander bucket clicks by their target's visual class.
    """
    if frame.ndim != 2 or frame.size == 0 or max_clicks <= 0:
        return []

    values, counts = np.unique(frame, return_counts=True)
    background = int(values[int(np.argmax(counts))])
    colour_count = {int(v): int(c) for v, c in zip(values, counts)}
    total_cells = float(frame.size)
    h, w = frame.shape

    # (tier, area, freq, x, y, colour, size_bucket)
    scored: list[tuple[int, int, int, int, int, int, int]] = []
    for colour in values:
        colour = int(colour)
        if colour == background:
            continue
        mask = frame == colour
        for comp in _connected_components(mask):
            area = len(comp)
            cy = int(round(sum(r for r, _ in comp) / area))
            cx = int(round(sum(c for _, c in comp) / area))
            tier = _click_tier(
                comp, colour, area, colour_count[colour],
                total_cells, frame, background, h, w,
            )
            scored.append(
                (tier, area, colour_count[colour], cx, cy, colour, area.bit_length())
            )

    # Tier-first, then smaller-area, then rarer-colour within a tier.
    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    out: list[tuple[int, int, int, int, int]] = []
    seen: set[tuple[int, int]] = set()
    for tier, _area, _freq, cx, cy, colour, size_bucket in scored:
        if (cx, cy) in seen:
            continue
        seen.add((cx, cy))
        out.append((cx, cy, tier, colour, size_bucket))
        if len(out) >= max_clicks:
            break
    return out


def _click_tier(
    comp: list[tuple[int, int]],
    colour: int,
    area: int,
    colour_freq: int,
    total_cells: float,
    frame: np.ndarray,
    background: int,
    h: int,
    w: int,
) -> int:
    """Bucket one component into an interactivity tier (0 = most promising).

    A small "interactivity score" is accumulated from visual cues, then mapped
    to a tier. See :func:`_segment_click_candidates_tiered` for the cue rationale.
    Returns an int in ``[0, _N_TIERS - 1]``.
    """
    area_frac = area / total_cells
    border = _component_border_colours(comp, frame, colour, h, w)

    # A large blob whose neighbourhood is dominated by background is a passive
    # backdrop / board — least likely interactive. Demote straight to bottom tier.
    if area_frac > 0.05 and border:
        bg_frac = sum(1 for v in border if v == background) / len(border)
        if bg_frac > 0.6:
            return _N_TIERS - 1

    score = 0.0
    # Smaller is more button-like. area_frac ~0 -> ~1.0, ~0.05 -> ~0.
    score += max(0.0, 1.0 - area_frac / 0.05)
    # Rarer colour is more control-like.
    score += max(0.0, 1.0 - colour_freq / total_cells / 0.10)
    # High border contrast: fraction of neighbouring cells with a DIFFERENT
    # colour than this component. An isolated widget scores high.
    if border:
        score += sum(1 for v in border if v != colour) / len(border)

    # Map the [0, 3] score to a tier (higher score -> lower/better tier index).
    if score >= 2.0:
        return 0
    if score >= 1.0:
        return 1
    return _N_TIERS - 1


def _component_border_colours(
    comp: list[tuple[int, int]], frame: np.ndarray, colour: int, h: int, w: int
) -> list[int]:
    """Return the colours of 4-neighbour cells that lie OUTSIDE the component.

    Cells whose neighbour is interior to the component are skipped, so the result
    describes the component's border neighbourhood.
    """
    comp_set = set(comp)
    border: list[int] = []
    for r, c in comp:
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in comp_set:
                border.append(int(frame[nr, nc]))
    return border


def _connected_components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """4-connected components of a boolean grid, each a list of (row, col)."""
    h, w = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    comps: list[list[tuple[int, int]]] = []
    for r in range(h):
        for c in range(w):
            if not mask[r, c] or visited[r, c]:
                continue
            comp: list[tuple[int, int]] = []
            stack = [(r, c)]
            visited[r, c] = True
            while stack:
                cr, cc = stack.pop()
                comp.append((cr, cc))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < h and 0 <= nc < w and mask[nr, nc] and not visited[nr, nc]:
                        visited[nr, nc] = True
                        stack.append((nr, nc))
            comps.append(comp)
    return comps


# ── observation helpers (tolerant of arcengine obs shape; mirror random_agent) ─


def _state_name(obs: Any) -> str:
    state = getattr(obs, "state", None)
    return getattr(state, "name", str(state) if state is not None else "")


def _has_frame(obs: Any) -> bool:
    fr = getattr(obs, "frame", None)
    return fr is not None and len(fr) > 0


def _frame_2d(obs: Any) -> np.ndarray:
    """Return a (64, 64) int array from the observation's first frame layer."""
    fr = getattr(obs, "frame", None)
    arr = np.asarray(fr)
    if arr.ndim >= 3:
        arr = arr[0]
    return arr.astype(np.int64)


def _levels_completed(obs: Any) -> int:
    v = getattr(obs, "levels_completed", None)
    if v is None:
        score = getattr(obs, "score", None)
        if isinstance(score, dict):
            v = score.get("levels_completed")
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _availability(obs: Any) -> tuple[list[int], bool]:
    """Return (list of coordinate-free simple action ids, action6_available).

    Simple ids are the no-coordinate movement commands 1-5, plus ACTION7 **only
    when the game offers no 1-5 movement at all**. ACTION7 is a real,
    level-advancing command on some titles — SU15 exposes ONLY ``[6, 7]`` — and
    dropping it left such a game with a single usable action (click), unclearable
    because a command it needs was never in the agent's set (R43 action-space
    -miss). It is gated to the no-movement case on purpose: titles that DO offer
    1-5 (AR25/BP35/LF52/SK48 — all in the clearing set) already clear without
    ACTION7, and adding a mostly-self-looping "undo/cancel" as a top-priority
    simple action there measurably destabilised them (SB26 collapsed into a
    self-loop sink). Gating to "no 1-5 present" targets exactly the class where
    ACTION7 is unambiguously load-bearing and provably touches none of the
    movement-having clearers. ``6`` remains the coordinate (click) action.
    """
    simple_ids: list[int] = []
    action6_ok = False
    has_action7 = False
    for a in getattr(obs, "available_actions", []) or []:
        aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
        if aid is None:
            continue
        if 1 <= aid <= 5:
            simple_ids.append(aid)
        elif aid == 6:
            action6_ok = True
        elif aid == 7:
            has_action7 = True
    if has_action7 and not simple_ids:
        simple_ids.append(7)
    return simple_ids, action6_ok
