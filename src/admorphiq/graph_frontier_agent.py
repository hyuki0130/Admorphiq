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
"""

from __future__ import annotations

import hashlib
import os
import random
from collections import deque
from typing import Any

import numpy as np

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

# Region-mask defaults (R36c). See module docstring for the rationale.
DEFAULT_REGION_MASK = True
DEFAULT_REGION_LOW = 0.05
DEFAULT_REGION_RATE = 0.7
DEFAULT_REGION_DILATE = 1


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
        hash_pool: int | None = None,
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
        self._dbg_recent = deque(maxlen=30)

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
        print(
            f"[GF] call={self._dbg_calls} lvl={self._last_levels} "
            f"states={n_states} frontier={n_frontier} edges={n_edges} "
            f"bfs_fires={self._dbg_bfs} bfs_fail={self._dbg_bfs_fail} "
            f"random={self._dbg_random} untried={self._dbg_untried} "
            f"mismatch={self._dbg_mismatch} masked={n_masked} "
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

        # HUD estimation: rolling window of per-cell "did this cell change"
        # boolean grids across recent transitions.
        self._hud_window: deque[np.ndarray] = deque(maxlen=_HUD_WINDOW)
        self._hud_mask: np.ndarray | None = None  # cached (64,64) bool, True=HUD

        # Bookkeeping for edge recording across steps.
        self._prev_hash: str | None = None
        self._prev_action_key: Any | None = None
        self._prev_frame: np.ndarray | None = None

        self._level_steps = 0

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

        cur_hash = self._hash(frame)
        if self._debug:
            self._dbg_recent.append(cur_hash)
        simple_ids, action6_ok = _availability(obs)
        self._ensure_state(cur_hash, frame, simple_ids, action6_ok)

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

        # Graph edge: prev_hash --action--> hash(frame under CURRENT mask).
        nxt_hash = self._hash(frame)
        key = self._prev_action_key
        edges = self._edges.setdefault(self._prev_hash, {})
        if self._debug and key in edges and edges[key] != nxt_hash:
            self._dbg_mismatch += 1
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
        for comp in _connected_components(noisy):
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
        pooled = _max_pool(masked, self.hash_pool)
        return hashlib.md5(np.ascontiguousarray(pooled).tobytes()).hexdigest()[:16]

    # ── graph maintenance ──────────────────────────────────────────────────────

    def _ensure_state(
        self,
        state_hash: str,
        frame: np.ndarray,
        simple_ids: list[int],
        action6_ok: bool,
    ) -> None:
        """Register ``state_hash`` with its untried action set if unseen."""
        if state_hash in self._untried:
            return
        actions: list[Any] = list(simple_ids)  # simple actions first
        if action6_ok:
            for (x, y) in self._click_candidates(frame):
                actions.append(("click", x, y))
        self._untried[state_hash] = actions
        self._edges.setdefault(state_hash, {})
        self._tries.setdefault(state_hash, {})

    # ── click candidate segmentation ───────────────────────────────────────────

    def _click_candidates(self, frame: np.ndarray) -> list[tuple[int, int]]:
        """Reduce ACTION6 to a small salience-ordered set of (x, y) click points.

        Segment the frame into 4-connected components per non-background colour
        (background = the single most-frequent colour). Each component yields its
        centroid as a candidate click. Components are ordered by salience —
        smaller area first, then rarer colour first — because interactive buttons
        tend to be small and rare-coloured. Capped at ``max_clicks``.

        Coordinates follow the arcengine convention where ``x`` is the column and
        ``y`` is the row, so a centroid at grid ``(row, col)`` maps to
        ``(x=col, y=row)``.
        """
        return _segment_click_candidates(frame, self.max_clicks)

    # ── policy ─────────────────────────────────────────────────────────────────

    def _policy(
        self,
        state_hash: str,
        simple_ids: list[int],
        action6_ok: bool,
        frame: np.ndarray,
    ) -> Any | None:
        """Pick an action_key for the current state.

        1. Untried action at the current state -> take it (simple before click,
           preserving the registration order).
        2. Otherwise BFS the known graph to the nearest FRONTIER state (one with
           untried actions) and take the first action of that shortest path.
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
        untried = self._untried.get(state_hash) or []
        if untried:
            self._dbg_untried += 1
            return untried[0]

        first_action = self._bfs_to_frontier(state_hash)
        if first_action is not None:
            self._dbg_bfs += 1
            return first_action

        # No untried action and no reachable frontier -> random escape.
        self._dbg_bfs_fail += 1
        escape = self._random_action_key(simple_ids, action6_ok, frame)
        if escape is not None:
            self._dbg_random += 1
            return escape
        return None

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
                    x, y = self._rng.choice(cands)
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
    Pure function of the frame so it is unit-testable in isolation.
    """
    if frame.ndim != 2 or frame.size == 0 or max_clicks <= 0:
        return []

    values, counts = np.unique(frame, return_counts=True)
    background = int(values[int(np.argmax(counts))])
    colour_count = {int(v): int(c) for v, c in zip(values, counts)}

    scored: list[tuple[int, int, int, int]] = []  # (area, colour_freq, x, y)
    for colour in values:
        colour = int(colour)
        if colour == background:
            continue
        mask = frame == colour
        for comp in _connected_components(mask):
            area = len(comp)
            cy = int(round(sum(r for r, _ in comp) / area))
            cx = int(round(sum(c for _, c in comp) / area))
            scored.append((area, colour_count[colour], cx, cy))

    # Salience: smaller area first, then rarer colour first.
    scored.sort(key=lambda t: (t[0], t[1]))
    out: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for _area, _freq, cx, cy in scored:
        if (cx, cy) in seen:
            continue
        seen.add((cx, cy))
        out.append((cx, cy))
        if len(out) >= max_clicks:
            break
    return out


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
