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

Env knobs:
  * ``GF_MAX_CLICKS``   (default 14)   — cap on click candidates per frame.
  * ``GF_HUD_THRESHOLD`` (default 0.8) — per-cell change-rate above which a cell
    is masked out of the state hash (always active).
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
   a level, infer a structured :class:`~planner.goal.GoalSpec` from the observed
   probe deltas via :func:`planner.goal_inference.infer_goal` (heuristic by
   default; ``GF_GOAL_LLM`` reserved for a later offline-LLM hook). Re-inferred
   every ``GF_GOAL_RECADENCE`` steps as evidence accumulates. If nothing
   confident is observed the agent stays goal-less (= pre-R41 behaviour).
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

**MEASURED VERDICT (R41, 2026-07-05) — shell mode, default OFF.** Enabling the
knob (``GF_GOAL_RANK=1``) is a real lever on paint/click games but regresses
navigation, so it ships default OFF (baseline untouched, zero regression risk):
  * CD82 L2: 26,965 -> **14,262** actions (−47%, deep clear preserved).
  * VC33 L3 @60k: 55,209 -> **37,966** actions (−31%, deepest level).
  * M0R0 L1: 751 -> 4,076 actions — REGRESSION. The FILL_COLOR heuristic is wrong
    for navigation (its object relocates, it does not fill), and even shell-mode
    within-shell tie-break by that goal delays the clear; M0R0 then misses the
    3,000-action quick budget (quick clears 5/9 -> 4/9), failing "no level lost".
  * Configs tried (tune-before-discard): (a) global blend 0.5 lost CD82 L2
    entirely; (b) shell mode = the wins above; (c) shell + a fill-colour
    accumulation gate restored M0R0 but ALSO killed the CD82 win (CD82's target
    colour does not actually accumulate — the fill-goal helped as a frontier
    ORDERING heuristic, not as a true objective), so the gate was dropped.
  A future round needs a game-type-aware goal (MOVE_TO_REGION for navigation,
  or an offline-LLM goal at discovery) before this can be promoted to default ON.

Goal knobs (all additive; default OFF until acceptance promotes them):
  * ``GF_GOAL_RANK``   (default 0)     — enable goal-directed frontier ranking.
  * ``GF_GOAL_INFER_AFTER`` (default 40)— per-level transitions before the first
    goal inference.
  * ``GF_GOAL_RECADENCE`` (default 300)— steps between goal re-inference.
  * ``GF_GOAL_MAX_WALKS`` (default 400)— consecutive goal-directed frontier picks
    without a new state before falling back to nearest-frontier.
  * ``GF_GOAL_BLEND``  (default 0.5)   — weight in [0,1] of goal-proximity vs
    nearness in the frontier rank (0 = pure nearest, 1 = pure goal-proximity).
"""

from __future__ import annotations

import hashlib
import os
import random
from collections import deque
from typing import Any

import numpy as np

from .planner.goal import GoalSpec, score_goal
from .planner.goal_inference import color_histogram_from_frame, infer_goal

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

# Region-mask defaults (R36c). See module docstring for the rationale.
DEFAULT_REGION_MASK = True
DEFAULT_REGION_LOW = 0.05
DEFAULT_REGION_RATE = 0.7
DEFAULT_REGION_DILATE = 1

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

# Goal-directed frontier ranking defaults (R41). Default OFF: promotion to ON is
# gated on the acceptance probe (deep 9-game set + quick 9-subset). See the
# module docstring "GOAL-DIRECTED FRONTIER RANKING" section for the rationale.
DEFAULT_GOAL_RANK = False
DEFAULT_GOAL_INFER_AFTER = 40
DEFAULT_GOAL_RECADENCE = 300
DEFAULT_GOAL_MAX_WALKS = 400
DEFAULT_GOAL_BLEND = 0.5
# Nearest-shell mode (R41). When True the goal ranker is restricted to the
# NEAREST in-gate frontier shell — it never picks a farther frontier over a
# nearer one, so the systematic BFS shell expansion that reaches barely-in-budget
# deep goals (CD82 L2, VC33 L3) is preserved; the goal only breaks ties among
# equidistant frontiers. This is the gentle/safe blend the R38 promise-frontier
# lesson demands. When False the ranker weighs goal-proximity against distance
# globally within ``frontier_dist`` (aggressive; can abandon deep clears).
DEFAULT_GOAL_SHELL = True
# Per-level cap on stored probe-change records fed to goal inference. Bounded so
# a long level does not grow the list without limit; the most recent probes are
# the most relevant evidence for the current goal.
_GOAL_PROBE_WINDOW = 256

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
        # Optional offline-LLM goal-inference hook (Callable[[str], str]); None by
        # default so the deterministic heuristic is used offline. Reserved for a
        # later round that wires an offline Qwen call at discovery time.
        self._goal_llm_call = None

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
        goal_desc = (
            f"{self._goal.goal_type.value}:{self._goal.color}"
            if self._goal is not None
            else "none"
        )
        print(
            f"[GF] call={self._dbg_calls} lvl={self._last_levels} "
            f"states={n_states} frontier={n_frontier} edges={n_edges} "
            f"bfs_fires={self._dbg_bfs} bfs_fail={self._dbg_bfs_fail} "
            f"random={self._dbg_random} untried={self._dbg_untried} "
            f"mismatch={self._dbg_mismatch} "
            f"selfloop={self._dbg_selfloop} realedge={self._dbg_realedge} "
            f"unstable_win={sum(self._dbg_unstable_window)}/{len(self._dbg_unstable_window)} "
            f"effpool={self._effective_pool} "
            f"masked={n_masked} "
            f"tier_hits={tier_hits} "
            f"goal={goal_desc} goal_walks={self._dbg_goal_walks} "
            f"recent_distinct={distinct_recent}/30",
            flush=True,
        )

    # ── level-scoped state ────────────────────────────────────────────────────

    def _reset_level_state(self) -> None:
        """Drop the graph and HUD stats — called on init and on level-up."""
        # Graph: state_hash -> {action_key: next_state_hash}. action_key is an
        # int for simple actions (1..5) or a ("click", x, y) tuple for ACTION6.
        self._edges: dict[str, dict[Any, str]] = {}
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

        # ── goal-directed ranking state (R41) ──────────────────────────────────
        # Compact frame (int8) cached at first sighting of each state, so the
        # goal scorer can evaluate score_goal(frame_of_state, goal) as a lookup.
        self._state_frame: dict[str, np.ndarray] = {}
        # The inferred level goal (None => goal-less = pre-R41 nearest behaviour).
        self._goal: GoalSpec | None = None
        # Bumped on every re-inference so cached goal scores invalidate cleanly.
        self._goal_version = 0
        # state_hash -> (goal_version, score) memo of score_goal for that state.
        self._goal_score_cache: dict[str, tuple[int, float]] = {}
        # Recent per-probe change summaries (action / changed_cells / new colour)
        # feeding goal inference; bounded to the most-recent evidence.
        self._probe_changes: deque[dict] = deque(maxlen=_GOAL_PROBE_WINDOW)
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

        # Level-up: the state space changed — start a fresh graph.
        levels = _levels_completed(obs)
        if levels > self._last_levels:
            self._reset_level_state()
        self._last_levels = levels

        if state in ("GAME_OVER", "NOT_PLAYED"):
            # Env is being (re)started. Keep the graph, but drop the in-flight
            # edge — the transition FROM the pre-reset state to the revived
            # frame is not a game transition and must not pollute the graph.
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

        cur_hash = self._hash(frame)
        self._recent_states.append(cur_hash)
        if self._debug:
            self._dbg_recent.append(cur_hash)
        self._visits[cur_hash] = self._visits.get(cur_hash, 0) + 1
        simple_ids, action6_ok = _availability(obs)
        self._ensure_state(cur_hash, frame, simple_ids, action6_ok)

        if self.goal_rank:
            # Graph grew => a new state was discovered => the goal ranker is
            # making progress; reset the stall counter (R41). Then (re)infer the
            # goal if enough evidence has accumulated.
            if len(self._untried) > self._graph_size_ckpt:
                self._graph_size_ckpt = len(self._untried)
                self._goal_walks_since_progress = 0
            self._maybe_infer_goal(frame)

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
        self._level_steps += 1

        return self._key_to_action(action_key)

    # ── HUD masking ───────────────────────────────────────────────────────────

    def _record_transition(self, frame: np.ndarray) -> None:
        """Fold the (prev_frame -> frame) diff into HUD stats + the graph edge."""
        if self._prev_frame is None or self._prev_hash is None:
            return

        # HUD stats: which cells changed on THIS transition (raw frames).
        if self._prev_frame.shape == frame.shape:
            changed = self._prev_frame != frame
            self._hud_window.append(changed)
            self._hud_mask = None  # invalidate cache; recompute lazily
            if self.goal_rank:
                self._record_probe_change(frame, changed)

        # Graph edge: prev_hash --action--> hash(frame under CURRENT mask).
        nxt_hash = self._hash(frame)
        key = self._prev_action_key
        edges = self._edges.setdefault(self._prev_hash, {})
        # Collapse signatures (always-on: they drive the adaptive downshift).
        mismatched = key in edges and edges[key] != nxt_hash
        selflooped = nxt_hash == self._prev_hash
        self._sl_window.append(bool(selflooped))
        self._mm_window.append(bool(mismatched))
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
            not self.pool_downshift
            or self._pool_downshifted
            or self._effective_pool <= 1
            or self._level_steps < self.downshift_after
            or len(self._sl_window) < self._sl_window.maxlen
        ):
            return
        # Jitter gate: a large HUD mask means pooling is load-bearing (real
        # jitter), so the high self-loop is not a pool-collapse — spare it.
        mask = self._hud_mask_grid()
        if mask is not None and int(mask.sum()) > self.downshift_max_mask:
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

    # ── goal-directed ranking (R41) ─────────────────────────────────────────────

    def _record_probe_change(
        self, frame: np.ndarray, changed: np.ndarray
    ) -> None:
        """Summarise one transition as a probe-change record for goal inference.

        The HUD mask (when trusted) is subtracted from the changed-cell set so a
        step-counter / animated overlay does not masquerade as the "new colour"
        the goal is trying to grow. Records ``action`` (the key that produced the
        transition), ``changed_cells``, and ``top_new_color`` (the most common
        non-background colour that APPEARED in the changed cells), matching the
        shape :func:`planner.goal_inference.infer_goal` expects.
        """
        mask = self._hud_mask_grid()
        if mask is not None and mask.shape == changed.shape:
            changed = changed & ~mask
        n_changed = int(changed.sum())
        top_new: int | None = None
        if n_changed:
            new_vals = frame[changed]
            new_vals = new_vals[new_vals != 0]  # ignore background appearances
            if new_vals.size:
                vals, counts = np.unique(new_vals, return_counts=True)
                top_new = int(vals[int(np.argmax(counts))])
        self._probe_changes.append(
            {
                "action": self._prev_action_key,
                "changed_cells": n_changed,
                "top_new_color": top_new,
            }
        )

    def _maybe_infer_goal(self, frame: np.ndarray) -> None:
        """(Re)infer the level goal once enough evidence has accumulated (R41).

        The first inference fires after ``goal_infer_after`` transitions; further
        re-inferences fire every ``goal_recadence`` steps so the goal tracks the
        evidence as the graph grows. Inference is CONFIDENCE-gated: if no probe
        introduced a non-background colour the observation is too weak to name a
        goal, so the agent stays goal-less (= pre-R41 nearest behaviour).
        """
        if not self.goal_rank:
            return
        if self._level_steps < self.goal_infer_after:
            return
        due_first = self._last_goal_infer_step < 0
        due_recadence = (
            self._last_goal_infer_step >= 0
            and self._level_steps - self._last_goal_infer_step >= self.goal_recadence
        )
        if not (due_first or due_recadence):
            return
        self._last_goal_infer_step = self._level_steps
        if not any(p.get("top_new_color") is not None for p in self._probe_changes):
            return  # no confident signal yet — remain goal-less
        hist = color_histogram_from_frame(frame)
        new_goal = infer_goal(hist, list(self._probe_changes), self._goal_llm_call)
        if new_goal != self._goal:
            self._goal = new_goal
            self._goal_version += 1  # invalidate cached scores lazily
            self._goal_walks_since_progress = 0  # fresh goal earns a fresh budget

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
        if n < _HUD_MIN_SAMPLES:
            return None
        stacked = np.stack(self._hud_window, axis=0)  # (n, 64, 64) bool
        rate = stacked.mean(axis=0)  # per-cell change fraction
        mask = rate > self.hud_threshold
        if self.region_mask:
            mask = mask | self._region_mask_from_rate(rate, stacked)
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
        """
        mask = self._hud_mask_grid()
        if mask is not None and mask.shape == frame.shape:
            masked = frame.copy()
            masked[mask] = 0
        else:
            masked = frame
        pooled = _max_pool(masked, self._effective_pool)
        return hashlib.md5(np.ascontiguousarray(pooled).tobytes()).hexdigest()[:16]

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
        # Cache a compact frame for the goal scorer (R41). Colours are indices in
        # [0, 15], so int8 is exact and keeps the per-state footprint at ~4 KB.
        if self.goal_rank:
            self._state_frame.setdefault(state_hash, frame.astype(np.int8))
        actions: list[Any] = list(simple_ids)  # simple actions first
        for aid in simple_ids:
            self._action_tier.setdefault(aid, _SIMPLE_TIER)
        if action6_ok:
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

        # Tier-gated exploration (R38). Try, in order, at the current unlocked
        # tier: a local within-tier untried action, then a promise-scored walk to
        # a within-tier frontier. If neither exists, unlock the next tier and
        # retry; only once every tier is exhausted globally do we random-escape.
        while True:
            key = self._best_untried_within_tier(state_hash)
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

    def _best_untried_within_tier(self, state_hash: str) -> Any | None:
        """Return the current state's highest-tier untried action within the gate.

        Only actions whose tier is ``<= _unlocked_tier`` (simple actions carry
        ``_SIMPLE_TIER`` < 0 and are always in-gate) are eligible, so the large
        mass of low-tier clicks stays deferred until the gate widens. Among
        eligible actions the lowest tier wins; ties keep registration order for
        determinism. Returns None when the state has no in-gate untried action.
        """
        untried = self._untried.get(state_hash) or []
        eligible = [
            k for k in untried
            if self._action_tier.get(k, _N_TIERS - 1) <= self._unlocked_tier
        ]
        if not eligible:
            return None
        return min(eligible, key=lambda k: self._action_tier.get(k, _N_TIERS - 1))

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
    Pure function of the frame so it is unit-testable in isolation.
    """
    if frame.ndim != 2 or frame.size == 0 or max_clicks <= 0:
        return []

    values, counts = np.unique(frame, return_counts=True)
    background = int(values[int(np.argmax(counts))])
    colour_count = {int(v): int(c) for v, c in zip(values, counts)}
    total_cells = float(frame.size)
    h, w = frame.shape

    scored: list[tuple[int, int, int, int, int]] = []  # (tier, area, freq, x, y)
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
            scored.append((tier, area, colour_count[colour], cx, cy))

    # Tier-first, then smaller-area, then rarer-colour within a tier.
    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    out: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int]] = set()
    for tier, _area, _freq, cx, cy in scored:
        if (cx, cy) in seen:
            continue
        seen.add((cx, cy))
        out.append((cx, cy, tier))
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
    """Return (list of available simple action ids 1..5, action6_available)."""
    simple_ids: list[int] = []
    action6_ok = False
    for a in getattr(obs, "available_actions", []) or []:
        aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
        if aid is None:
            continue
        if 1 <= aid <= 5:
            simple_ids.append(aid)
        elif aid == 6:
            action6_ok = True
    return simple_ids, action6_ok
