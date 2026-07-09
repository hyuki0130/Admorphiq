"""Graph-search tool — transition-graph frontier-BFS navigation engine.

The proven core of the project's best agent, re-authored clean against the
:class:`~admorphiq.tools.base.Tool` lifecycle. It builds an explicit graph over
frame states (keyed by :func:`~admorphiq.tools.base.base_hash`), records observed
``(state, action) -> next_state`` edges, and proposes actions that walk toward
UNEXPLORED frontier states — the nearest known state that still has an untried
action — so navigation / state-space games get explored systematically.

Algorithm (faithful to the monolith ``GraphFrontierAgent``, minus its optional
HUD/pool/goal/EWM layers):

* Each state's action set is registered ONCE: simple movement actions (ids 1-5)
  first, then segment-derived ACTION6 click candidates (small foreground objects
  first — button-like). Simple-before-click means a fresh state is probed with
  cheap movement before expensive clicks.
* ``propose`` takes an untried action at the current state if one exists;
  otherwise it BFS-walks the observed graph to the nearest state that still has
  an untried action and returns the action path that reaches it; otherwise it
  falls back to a random legal action (the sink-escape hatch).
* ``observe`` folds the just-taken transition into the graph: a no-change
  outcome is a self-loop edge; a change edge's target hash is resolved on the
  next ``propose`` (when the resulting frame is observed).

Game-agnostic: triggers and logic read FRAME OBSERVATIONS only — never any game
identifier, title, internal tag, or hardcoded level sequence.
"""

from __future__ import annotations

import hashlib
import random
from collections import deque
from typing import Any

import numpy as np

from admorphiq.tools.base import (
    Step,
    availability,
    color_histogram,
    connected_components,
    diff_bbox,
    diff_cells,
    frame_2d,
    has_frame,
)
from admorphiq.tools.dealias import DealiasTool

try:
    from admorphiq.planner.goal import score_goal
    from admorphiq.planner.goal_inference import GoalMeasureTracker
    _GOAL_OK = True
except Exception:  # noqa: BLE001 - goal ranking is optional; degrade to pure promise
    _GOAL_OK = False

__all__ = ["GraphSearchTool"]

# Cap on segment-derived ACTION6 click candidates per state (monolith default).
_MAX_CLICKS = 14
# Locality gates for the movement (avatar-mobility) detection signature.
_LOCAL_CELL_FRAC = 0.05   # changed cells must be <= this fraction of the grid
_LOCAL_BBOX_FRAC = 0.15   # changed bbox area must be <= this fraction of the grid
# HUD masking: after this many observed transitions, freeze a mask of cells that
# changed in >= _HUD_FRAC of them (step counters / timers / animated overlays)
# and hash the frame with those cells zeroed, so aliasing (a churning HUD that
# makes every true-state look new) can't explode the state graph.
_HUD_WARMUP = 16
_HUD_FRAC = 0.60
# Max BFS depth the promise-frontier scorer explores before committing to the
# best frontier found so far (beyond this, distance dominates promise anyway).
_FRONTIER_DIST_CAP = 40
# Goal-ranking: track the whole candidate-goal family's trends and blend the
# best-trending goal's proximity into the frontier promise, pulling exploration
# toward states closer to the target the game is actually progressing on (legacy
# GF_GOAL_RANK). Small weight so goal-proximity biases, never overrides, breadth.
_GOAL_WEIGHT = 0.05
# When an EXPLICIT target frame is injected, its proximity (range [-1, 0]) must
# DOMINATE the frontier ranking, not nudge it: at 0.05 the steering was provably
# inert (±0.05 against integer untried-counts up to ~19 — measured on a game
# whose drawn L2 target was plausible and stable yet never pursued). At 50, a
# frontier 2% closer to the target outweighs one extra untried action.
_TARGET_STEER_WEIGHT = 50.0
# Only fold every Nth state into the (expensive) candidate-goal trend tracker.
_GOAL_OBS_STRIDE = 6


def _norm_grid(arr: Any) -> np.ndarray:
    """Normalise any frame-like array to the (H, W) int64 grid used for hashing.

    Mirrors ``base.frame_2d`` for a raw ndarray (drops a leading layer axis, casts
    to int64) so that ``observe``'s ``prev`` frame hashes identically to a frame
    read from an observation in ``propose``.
    """
    a = np.asarray(arr)
    if a.ndim >= 3:
        a = a[0]
    return a.astype(np.int64)


def _downsample(frame: np.ndarray, n: int = 8) -> np.ndarray:
    """Downsample a grid to n×n by block-majority (mode) — a coarse spatial
    signature robust to small shifts, used to compare a frame to a target frame."""
    a = np.asarray(frame)
    if a.ndim != 2 or a.size == 0:
        return np.zeros((n, n), dtype=np.int64)
    h, w = a.shape
    out = np.zeros((n, n), dtype=np.int64)
    ys = np.linspace(0, h, n + 1).astype(int)
    xs = np.linspace(0, w, n + 1).astype(int)
    for i in range(n):
        for j in range(n):
            block = a[ys[i]:max(ys[i] + 1, ys[i + 1]), xs[j]:max(xs[j] + 1, xs[j + 1])]
            if block.size:
                vals, cnts = np.unique(block, return_counts=True)
                out[i, j] = int(vals[int(cnts.argmax())])
    return out


# Interactivity tiers for click candidates (0 = most promising). Ported from
# legacy graph_frontier (R38): the GLOBAL TIER GATE defers the mass of low-tier
# clicks until tier-0 is exhausted everywhere — without it deep discovery burned
# tens of thousands of actions trying every centroid at every state.
_N_TIERS = 3

# Object-hash ladder (legacy R45): when the pixel-hash graph is measurably
# broken — EXPLOSION (new states never recur; every transition mints a fresh
# hash, e.g. a move recolors ~80 cells) or a PERSISTENT SINK (self-loops
# dominate with few distinct states) — rebuild the level graph keyed on the
# frame's OBJECTS (colour, log2-size-bucket, centroid), which absorbs jitter
# while keeping 1-cell movement visible. One activation per level.
_OBJ_WINDOW = 200          # transitions sampled by the instability windows
_OBJ_MIN_STEPS = 1500      # in-level propose calls before the ladder may fire
_OBJ_EXPLODE_FRAC = 0.5    # windowed new-state fraction for the explosion fire
_OBJ_EXPLODE_MOBILE = 12   # min distinct-recent states for the explosion fire
_OBJ_SINK_SELFLOOP = 0.70  # windowed self-loop fraction for the sink fire
_OBJ_SINK_DISTINCT = 6     # max distinct-recent states for the sink fire
_OBJ_MAX_MASK = 256        # skip when the HUD mask is this large (jitter gate)

def _click_candidates(frame: np.ndarray, max_clicks: int = _MAX_CLICKS) -> list[tuple[int, int, int]]:
    """Reduce ACTION6 to a small INTERACTIVITY-tier-ordered set of ``(x, y)`` clicks.

    Segments the frame into 4-connected foreground components (background = the
    most common colour) and returns their centroids ``(x=col, y=row)``, ordered by
    how likely each component is a CONTROL (a button/token/widget you click) vs
    passive backdrop — the ranking legacy graph_frontier proved recovers clears.
    Score (lower = more promising) blends: small area, rare colour, and high local
    contrast (border colours differ from the component's own). Deduplicated by
    centroid, capped at ``max_clicks``.
    """
    grid = np.asarray(frame)
    hist = color_histogram(grid)
    total = float(grid.size) or 1.0
    background = int(np.argmax(hist)) if len(hist) else 0
    comps = connected_components(grid)
    scored: list[tuple[int, float, float, tuple[int, int]]] = []
    for comp in comps:
        area = comp["size"]
        color = comp["color"]
        rarity = hist[color] / total if 0 <= color < len(hist) else 1.0
        contrast = _border_contrast(grid, comp)
        # Legacy _click_tier: accumulate an interactivity score from the same
        # three cues, then bucket by the legacy thresholds (>=2.0 -> 0,
        # >=1.0 -> 1, else bottom).
        area_frac = area / total
        iscore = (
            max(0.0, 1.0 - area_frac / 0.05)
            + max(0.0, 1.0 - rarity / 0.10)
            + contrast
        )
        if iscore >= 2.0:
            tier = 0
        elif iscore >= 1.0:
            tier = 1
        else:
            tier = _N_TIERS - 1
        # Backdrop demotion: a large blob bordered mostly by BACKGROUND is a
        # passive board, never a control (legacy rule, bg_frac > 0.6).
        if area_frac > 0.05 and _border_bg_frac(grid, comp, background) > 0.6:
            tier = _N_TIERS - 1
        cy, cx = comp["centroid"]
        scored.append((tier, float(area), rarity, (int(round(cx)), int(round(cy)))))
    # Tier-first, then smaller-area, then rarer-colour (legacy ordering).
    scored.sort(key=lambda t: (t[0], t[1], t[2]))
    out: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int]] = set()
    for tier, _area, _rar, (x, y) in scored:
        if (x, y) in seen:
            continue
        seen.add((x, y))
        out.append((x, y, tier))
        if len(out) >= max_clicks:
            break
    return out


def _border_bg_frac(grid: np.ndarray, comp: dict[str, Any], background: int) -> float:
    """Fraction of a component's 4-neighbour border cells that are the BACKGROUND
    colour — high when the component sits isolated on the passive board."""
    cells = comp["cells"]
    h, w = grid.shape
    cellset = set(cells)
    border = bg = 0
    for (r, c) in cells:
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in cellset:
                border += 1
                if int(grid[nr, nc]) == background:
                    bg += 1
    return bg / border if border else 0.0


def _border_contrast(grid: np.ndarray, comp: dict[str, Any]) -> float:
    """Fraction of a component's 4-neighbour border cells whose colour differs
    from the component's own — high when the component is an isolated widget."""
    color = comp["color"]
    cells = comp["cells"]
    h, w = grid.shape
    cellset = set(cells)
    border = diff = 0
    for (r, c) in cells:
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in cellset:
                border += 1
                if int(grid[nr, nc]) != color:
                    diff += 1
    return diff / border if border else 0.0


def _step_to_key(step: Step) -> Any:
    """Map a public :data:`Step` to the internal action key used as a graph label."""
    aid, xy = step
    if aid == 6 and xy is not None:
        return ("click", int(xy[0]), int(xy[1]))
    return int(aid)


def _key_to_step(key: Any) -> Step:
    """Inverse of :func:`_step_to_key`."""
    if isinstance(key, tuple) and key and key[0] == "click":
        return (6, (int(key[1]), int(key[2])))
    return (int(key), None)


class GraphSearchTool:
    """Frontier-BFS navigation engine as a harness :class:`Tool`."""

    name = "graph"

    def __init__(self, max_clicks: int = _MAX_CLICKS) -> None:
        self.max_clicks = max_clicks
        self._rng = random.Random(0)
        self.reset()

    # ── lifecycle ────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Drop the per-level graph and frontier (harness calls this on level-up)."""
        # state_hash -> {action_key: next_state_hash}
        self._edges: dict[str, dict[Any, str]] = {}
        # state_hash -> ordered list of untried action_keys (simple before click)
        self._untried: dict[str, list[Any]] = {}
        # state_hash -> {action_key: try_count}
        self._tries: dict[str, dict[Any, int]] = {}
        # state_hash -> {action_key: interactivity tier} (simple actions = -1).
        self._tier: dict[str, dict[Any, int]] = {}
        # Global tier gate (legacy R38): exploration starts restricted to simple
        # actions + tier-0 clicks; a lower tier unlocks only when no in-gate
        # untried action is reachable ANYWHERE — deferring the mass of
        # low-promise clicks that made deep discovery exhaustive.
        self._unlocked_tier = 0
        # Object-hash ladder (legacy R45) instability tracking.
        self._hash_mode = "pixel"
        self._new_window: deque[bool] = deque(maxlen=_OBJ_WINDOW)
        self._loop_window: deque[bool] = deque(maxlen=_OBJ_WINDOW)
        self._recent_states: deque[str] = deque(maxlen=30)
        self._propose_calls = 0
        # next_hash -> list of (prev_hash, action_key) predecessors
        self._preds: dict[str, list[tuple[str, Any]]] = {}
        # A change-transition whose target hash is resolved on the next propose.
        self._pending: tuple[str, Any] | None = None
        # HUD masking accumulators (built from consecutive observed prev frames).
        self._chg: np.ndarray | None = None   # per-cell change count
        self._nchg = 0                          # transitions folded into _chg
        self._prev_obs: np.ndarray | None = None
        self._mask: np.ndarray | None = None    # frozen HUD mask (bool H×W)
        # De-aliasing on the HUD-masked frame: splits hidden-state collisions
        # (same visible/masked frame, different true state) by recent history.
        self._dealias = DealiasTool()
        self._recent: deque[Step] = deque(maxlen=4)
        # Goal ranking: track ALL candidate-goal trends (FILL/COUNT/ORDER/ON_TARGET)
        # and rank frontiers by the goal the game is actually PROGRESSING on — not
        # just FILL. Per-state frame stored so score_goal can evaluate a frontier.
        self._state_frame: dict[str, np.ndarray] = {}
        self._goal: Any = None
        self._goal_tracker = GoalMeasureTracker() if _GOAL_OK else None
        self._goal_obs_count = 0
        self._goal_memo: dict[str, float] = {}
        self._target_grid: np.ndarray | None = None  # injected LLM target frame
        self._scorer = None                           # injected executable goal scorer
        self._target_res = 8                          # its downsample resolution
        # Target-pursuit progress trace (drives target_stalled / redraw gating).
        self._prox_calls = 0
        self._best_prox = float("-inf")
        self._last_improve_call = 0

    def _masked_frame(self, frame: np.ndarray) -> np.ndarray:
        """The frame with frozen-HUD cells zeroed (identity until warmup freeze)."""
        if self._mask is None:
            return frame
        g = frame.copy()
        g[self._mask] = 0
        return g

    def _node_key(self, frame: np.ndarray) -> str:
        """State key = HUD-masked hash, de-aliased by recent action history when
        the masked hash has shown hidden-state ambiguity (composition of HUD
        masking + de-aliasing — the two generic aliasing fixes stacked). In
        OBJECT mode (ladder fired) the key is the object hash instead — the
        pixel-level dealiasing no longer applies to a broken pixel graph."""
        mframe = self._masked_frame(frame)
        if self._hash_mode == "object":
            return _object_key(mframe)
        return self._dealias.key(mframe, self._recent)

    def _maybe_fire_object_hash(self) -> None:
        """Arm the object-hash rung when the pixel graph shows a measured broken
        signature (legacy R45 thresholds). Rebuilds the level graph under object
        keys; pinned until the next reset() (one activation per level)."""
        if (
            self._hash_mode == "object"
            or self._propose_calls < _OBJ_MIN_STEPS
            or len(self._new_window) < _OBJ_WINDOW
            or len(self._loop_window) < _OBJ_WINDOW
        ):
            return
        if self._mask is not None and int(self._mask.sum()) > _OBJ_MAX_MASK:
            return  # jitter gate: a big HUD mask means masking is load-bearing
        new_frac = sum(self._new_window) / len(self._new_window)
        loop_frac = sum(self._loop_window) / len(self._loop_window)
        distinct = len(set(self._recent_states))
        explosion = new_frac >= _OBJ_EXPLODE_FRAC and distinct >= _OBJ_EXPLODE_MOBILE
        sink = loop_frac >= _OBJ_SINK_SELFLOOP and distinct <= _OBJ_SINK_DISTINCT
        if not (explosion or sink):
            return
        self._hash_mode = "object"
        self._edges.clear()
        self._untried.clear()
        self._tries.clear()
        self._tier.clear()
        self._preds.clear()
        self._pending = None
        self._state_frame.clear()
        self._goal_memo.clear()
        self._unlocked_tier = 0
        self._new_window.clear()
        self._loop_window.clear()
        self._recent_states.clear()

    def state_key(self, frame: np.ndarray) -> str:
        """The tool's OWN notion of state identity for the harness's progress
        signal — HUD-masked + de-aliased, so the loop measures whether THIS tool
        is reaching new states (it is, while exploring a click game the raw frame
        makes look static/churny), not raw-frame novelty. Normalises dtype so it
        matches the tool's internal hashing exactly."""
        return self._node_key(_norm_grid(frame))

    def _accumulate_hud(self, prev: np.ndarray) -> None:
        """Fold one frame into the per-cell change map; freeze the HUD mask once
        warmup is reached and drop the (now stale, raw-hashed) graph so it
        rebuilds under masked hashes."""
        if self._mask is not None:
            return
        if self._prev_obs is not None and self._prev_obs.shape == prev.shape:
            if self._chg is None:
                self._chg = np.zeros(prev.shape, dtype=np.int64)
            self._chg += (self._prev_obs != prev).astype(np.int64)
            self._nchg += 1
            if self._nchg >= _HUD_WARMUP and self._chg is not None:
                mask = self._chg >= (_HUD_FRAC * self._nchg)
                # Only bother if the HUD is a minority of the board (else masking
                # would erase the game itself — treat that as "no HUD").
                if 0 < int(mask.sum()) <= mask.size // 3:
                    self._mask = mask
                    self._edges.clear()
                    self._untried.clear()
                    self._tries.clear()
                    self._tier.clear()
                    self._preds.clear()
                    self._pending = None
                    # Masked hashes change on freeze -> aliasing trace + per-state
                    # frame store + goal memo are all keyed on stale hashes.
                    self._dealias.reset()
                    self._state_frame.clear()
                    self._goal_memo.clear()
                    if self._goal_tracker is not None:
                        self._goal_tracker.reset()
                    self._goal = None
                else:
                    self._mask = np.zeros(prev.shape, dtype=bool)  # freeze: no HUD
        self._prev_obs = prev

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Frame-only confidence that this is a graph/navigation game.

        HIGH (0.8) when simple movement actions (ids 1-4) are available AND the
        observed frame-to-frame transitions change small, localized regions
        (the signature of a mobile avatar moving on a static board). Movement
        without such evidence yet is still graph territory (0.45). No movement
        but a click (ACTION6) is offered -> MODERATE (0.4): graph is a general
        discrete-state search that clears many click-state games too, so it is a
        legitimate candidate, not dismissed — its progress-based ownership drops
        it quickly if it truly stalls. Only a game with neither movement nor
        click is not graph's turf (0.1).
        """
        simple_ids, action6_ok = availability(obs)
        if not any(1 <= a <= 4 for a in simple_ids):
            return 0.4 if action6_ok else 0.1
        grids = [g for g in (_obs_grid(f) for f in frames) if g is not None]
        localized = False
        for a, b in zip(grids, grids[1:]):
            if a.shape != b.shape:
                continue
            n = diff_cells(a, b)
            if n == 0:
                continue
            bbox = diff_bbox(a, b)
            if bbox is None:
                continue
            bh, bw = bbox[2] - bbox[0] + 1, bbox[3] - bbox[1] + 1
            size = a.size
            if n <= max(1, _LOCAL_CELL_FRAC * size) and bh * bw <= max(4, _LOCAL_BBOX_FRAC * size):
                localized = True
                break
        return 0.8 if localized else 0.45

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Fold the just-taken transition ``prev --action--> ?`` into the graph.

        The action is marked tried at ``prev``'s state. A no-change outcome
        records a self-loop edge immediately; a change stashes the source so the
        edge's target hash is completed on the next :meth:`propose`.
        """
        prev_grid = _norm_grid(prev)
        self._accumulate_hud(prev_grid)
        # De-aliasing sees the HUD-masked frame + the action taken from it.
        self._dealias.observe(self._masked_frame(prev_grid), action, changed)
        prev_hash = self._node_key(prev_grid)
        self._recent.append(action)
        key = _step_to_key(action)
        untried = self._untried.get(prev_hash)
        if untried and key in untried:
            untried.remove(key)
        self._edges.setdefault(prev_hash, {})
        tries = self._tries.setdefault(prev_hash, {})
        tries[key] = tries.get(key, 0) + 1
        self._loop_window.append(not changed)
        if changed:
            self._pending = (prev_hash, key)
        else:
            self._edges[prev_hash][key] = prev_hash  # self-loop
            self._pending = None

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """Return the next 1..N actions toward an unexplored frontier.

        Resolves any pending change-edge against the now-observed frame, registers
        the current state, then: (1) takes an untried action here if one exists;
        else (2) BFS-walks the graph to the nearest state with an untried action
        and returns the action path reaching it; else (3) a random legal action.
        """
        if not has_frame(obs):
            return []
        frame = frame_2d(obs)
        cur_hash = self._node_key(frame)

        if self._pending is not None:
            p_hash, p_key = self._pending
            self._edges.setdefault(p_hash, {})[p_key] = cur_hash
            self._preds.setdefault(cur_hash, []).append((p_hash, p_key))
            self._pending = None

        self._propose_calls += 1
        self._new_window.append(cur_hash not in self._untried)
        self._recent_states.append(cur_hash)
        self._maybe_fire_object_hash()
        if self._hash_mode == "object":
            cur_hash = self._node_key(frame)  # mode may have just switched

        simple_ids, action6_ok = availability(obs)
        self._ensure_state(cur_hash, frame, simple_ids, action6_ok)
        self._track_goal(cur_hash, frame)
        if self._scorer is not None or self._target_grid is not None:
            # Trace pursuit progress: goal-proximity of the CURRENT board (higher
            # = closer). Feeds target_stalled() so the harness only redraws when
            # the current goal has genuinely stopped paying off.
            prox = None
            if self._scorer is not None:
                try:
                    v = float(self._scorer(frame))
                    prox = v if np.isfinite(v) else None
                except Exception:  # noqa: BLE001
                    prox = None
            else:
                ds = _downsample(frame, self._target_res)
                if ds.shape == self._target_grid.shape:
                    prox = -float(np.mean(ds != self._target_grid))
            if prox is not None:
                self._prox_calls += 1
                if prox > self._best_prox:
                    self._best_prox = prox
                    self._last_improve_call = self._prox_calls

        while True:
            untried = self._gated_untried(cur_hash)
            if untried:
                return [_key_to_step(untried[0])]
            path = self._bfs_path_to_frontier(cur_hash)
            if path:
                return [_key_to_step(k) for k in path]
            # No in-gate untried reachable anywhere: unlock the next click tier
            # (legacy R38 global unlock) and retry before falling to random.
            if self._unlocked_tier < _N_TIERS - 1:
                self._unlocked_tier += 1
                continue
            break

        step = self._random_step(simple_ids, action6_ok, frame)
        return [step] if step is not None else []

    # ── goal ranking (heuristic, no LLM) ─────────────────────────────────────

    def set_external_goal(self, goal: Any) -> None:
        """Inject a goal (e.g. LLM-inferred, richer than the frame-only family)
        for the frontier ranking to steer toward. Used EXCLUSIVELY — the
        candidate-goal trend tracker is disabled so the injected goal is never
        diluted (adding candidates to the tracker was measured to regress). This
        is the hybrid path: LLM infers a target the frame-only family can't
        express, graph's search drives to it via score_goal."""
        self._goal = goal
        self._goal_tracker = None   # exclusive: no frame-only family dilution
        self._goal_memo.clear()

    def _track_goal(self, cur_hash: str, frame: np.ndarray) -> None:
        """Store this state's frame, fold it into the candidate-goal trend tracker,
        and adopt the best-trending goal (the measure the game is progressing on).
        All no-LLM, frame-only — considers the whole GoalSpec family, not just FILL.
        Skipped entirely once an external goal is injected (set_external_goal)."""
        if not _GOAL_OK or self._goal_tracker is None:
            self._state_frame[cur_hash] = frame  # still needed for score_goal
            return
        self._state_frame[cur_hash] = frame
        # Scoring the whole candidate-goal family per state is expensive; throttle
        # to every _GOAL_OBS_STRIDE-th state (the trend only needs a sample of the
        # trajectory, not every frame) so goal-ranking never dominates runtime.
        self._goal_obs_count += 1
        if self._goal_obs_count % _GOAL_OBS_STRIDE != 0:
            return
        try:
            self._goal_tracker.observe(frame)
            best = self._goal_tracker.best_trend()
        except Exception:  # noqa: BLE001
            best = None
        if best is not None:
            goal = best[0]
            if goal is not self._goal:
                self._goal = goal
                self._goal_memo.clear()

    def set_target_frame(self, target: np.ndarray, res: int = 8) -> None:
        """Inject an arbitrary TARGET FRAME (e.g. an LLM-drawn picture of the solved
        board) — a goal representation RICHER than the GoalSpec vocabulary, which
        was measured to be the 25/25 wall. Frontiers are then ranked by how close
        their (downsampled to ``res``×``res``) frame is to this target. Used
        exclusively; the candidate-goal tracker is disabled so it isn't diluted."""
        self._target_res = int(res)
        self._target_grid = _downsample(np.asarray(target), self._target_res)
        self._goal_tracker = None
        self._goal = None
        self._goal_memo.clear()
        # Fresh target -> fresh progress trace (feeds target_stalled()).
        self._prox_calls = 0
        self._best_prox = float("-inf")
        self._last_improve_call = 0

    def set_external_scorer(self, scorer: Any) -> None:
        """Inject an EXECUTABLE goal scorer ``scorer(frame) -> float`` (higher =
        closer to solved) — the most expressive goal representation: it can state
        conditions neither the GoalSpec enum nor a static target frame can
        ("all colour-3 blobs merged", "row sorted by size"). Used exclusively;
        the tracker and any target frame are cleared so nothing dilutes it. The
        scorer must already be sandbox-validated by the caller."""
        self._scorer = scorer
        self._target_grid = None
        self._goal_tracker = None
        self._goal = None
        self._goal_memo.clear()
        self._prox_calls = 0
        self._best_prox = float("-inf")
        self._last_improve_call = 0

    def target_progress(self) -> tuple[float, int]:
        """(best proximity achieved, propose-calls traced) for the current
        injected goal — the depth diagnostic: prox ≈ 0 means the COARSE target
        was reached (steering saturated; the block is finer-grained), a prox far
        below 0 means the search never got close (search-space block)."""
        return (self._best_prox, self._prox_calls)

    def target_stalled(self, window: int) -> bool:
        """True when the injected target/scorer has shown NO proximity improvement
        for ``window`` propose-calls — the REDRAW gate. A progressing goal must
        not be overwritten (measured: blind periodic redraws replaced good
        targets mid-pursuit and lost a proven clear — see rounds/r53); no goal
        at all counts as stalled so the first draw is always allowed."""
        if self._target_grid is None and self._scorer is None:
            return True
        return (self._prox_calls - self._last_improve_call) >= window

    def _goal_proximity(self, node: str) -> float:
        """Frontier goal-proximity (memoized): an injected executable SCORER wins;
        else a TARGET FRAME's negative downsampled distance; else score_goal of
        the tracked/injected GoalSpec; 0 if none."""
        if node in self._goal_memo:
            return self._goal_memo[node]
        fr = self._state_frame.get(node)
        val = 0.0
        if fr is not None and self._scorer is not None:
            try:
                v = float(self._scorer(fr))
                val = v if np.isfinite(v) else 0.0
            except Exception:  # noqa: BLE001
                val = 0.0
        elif fr is not None and self._target_grid is not None:
            # higher = closer: negative fraction of cells that differ from target
            ds = _downsample(fr, self._target_res)
            if ds.shape == self._target_grid.shape:
                val = -float(np.mean(ds != self._target_grid))
        elif fr is not None and self._goal is not None:
            try:
                val = float(score_goal(fr, self._goal))
            except Exception:  # noqa: BLE001
                val = 0.0
        self._goal_memo[node] = val
        return val

    # ── graph internals ──────────────────────────────────────────────────────

    def _ensure_state(
        self, state_hash: str, frame: np.ndarray, simple_ids: list[int], action6_ok: bool
    ) -> None:
        """Register ``state_hash`` with its untried action set if unseen.

        Simple actions (1-5) are registered before any click so a fresh state is
        probed with cheap movement first; ACTION6 clicks come from the salience-
        ordered segment centroids.
        """
        if state_hash in self._untried:
            return
        actions: list[Any] = [int(a) for a in simple_ids]
        tiers: dict[Any, int] = {int(a): -1 for a in simple_ids}
        if action6_ok:
            for x, y, tier in _click_candidates(frame, self.max_clicks):
                key = ("click", int(x), int(y))
                actions.append(key)
                tiers[key] = tier
        self._untried[state_hash] = actions
        self._tier[state_hash] = tiers
        self._edges.setdefault(state_hash, {})
        self._tries.setdefault(state_hash, {})

    def _in_gate(self, state: str, key: Any) -> bool:
        """True when ``key`` at ``state`` is within the unlocked tier. Keys with
        no recorded tier (hand-built graphs, simple actions) are always in-gate."""
        return self._tier.get(state, {}).get(key, -1) <= self._unlocked_tier

    def _gated_untried(self, state: str) -> list[Any]:
        """The state's untried actions currently within the tier gate."""
        return [k for k in (self._untried.get(state) or []) if self._in_gate(state, k)]

    def _bfs_path_to_frontier(self, start: str) -> list[Any] | None:
        """Shortest action path from ``start`` to the nearest frontier state.

        A frontier state is one that still has an untried action. Rather than the
        NEAREST frontier (which re-walks the same exhausted area and burns budget
        on unpromising shells — legacy graph_frontier measured this), collect all
        frontiers reachable within a distance cap and walk to the most PROMISING:
        most untried actions, fewest prior visits, nearer breaks ties. Returns the
        action-key path to it, or None if no frontier is reachable.
        """
        visited: set[str] = {start}
        queue: deque[tuple[str, list[Any]]] = deque()
        for key, nxt in (self._edges.get(start) or {}).items():
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, [key]))
        best_path: list[Any] | None = None
        best_score = -1e18
        while queue:
            node, path = queue.popleft()
            untried = self._gated_untried(node)
            if untried:
                visits = sum((self._tries.get(node) or {}).values())
                # promise: reward untried breadth, penalise re-visits and distance,
                # and steer by goal proximity — DOMINANT for an explicit injected
                # target ([-1,0] scaled to [-50,0]), a light bias for the noisy
                # heuristic tracker goal.
                w = _TARGET_STEER_WEIGHT if self._target_grid is not None else _GOAL_WEIGHT
                score = (
                    len(untried) - 0.5 * visits - 0.25 * len(path)
                    + w * self._goal_proximity(node)
                )
                if score > best_score:
                    best_score, best_path = score, path
            if len(path) >= _FRONTIER_DIST_CAP:
                continue
            for key, nxt in (self._edges.get(node) or {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + [key]))
        return best_path

    def _random_step(
        self, simple_ids: list[int], action6_ok: bool, frame: np.ndarray
    ) -> Step | None:
        """Sample one legal action for the sink-escape fallback (or None if none).

        Draws from the simple ids plus, when ACTION6 is offered, either a segment
        centroid or a fully-random pixel — the raw pixel is what lets a
        single-state click sink (whose every centroid self-loops) eventually land
        on a live cell and re-seed exploration.
        """
        choices: list[Step] = [(int(a), None) for a in simple_ids]
        if action6_ok:
            if self._rng.random() < 0.5:
                cands = _click_candidates(frame, self.max_clicks)
                if cands:
                    x, y, _tier = self._rng.choice(cands)
                    choices.append((6, (int(x), int(y))))
            h, w = frame.shape if frame.ndim == 2 else (64, 64)
            choices.append((6, (self._rng.randrange(w), self._rng.randrange(h))))
        if not choices:
            return None
        return self._rng.choice(choices)


def _object_key(frame: np.ndarray) -> str:
    """Hash a frame by its OBJECTS (legacy R45 _object_hash): md5 of the sorted
    multiset of (colour, size_bucket, centroid_row, centroid_col) tokens.
    Centroids at full cell resolution keep 1-cell movement visible; the log2
    size bucket + dropped interiors absorb intra-object jitter/animation."""
    comps = connected_components(frame)
    tokens = sorted(
        (int(c["color"]), int(c["size"]).bit_length(),
         int(round(c["centroid"][0])), int(round(c["centroid"][1])))
        for c in comps
    )
    return hashlib.md5(repr(tokens).encode()).hexdigest()[:16]


def _obs_grid(x: Any) -> np.ndarray | None:
    """Best-effort (H, W) grid from an observation OR a raw array; None if neither."""
    if has_frame(x):
        return frame_2d(x)
    a = np.asarray(x)
    if a.ndim >= 2:
        return _norm_grid(a)
    return None
