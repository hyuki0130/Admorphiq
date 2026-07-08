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

import random
from collections import deque
from typing import Any

import numpy as np

from admorphiq.tools.base import (
    Step,
    availability,
    base_hash,
    connected_components,
    diff_bbox,
    diff_cells,
    frame_2d,
    has_frame,
)

__all__ = ["GraphSearchTool"]

# Cap on segment-derived ACTION6 click candidates per state (monolith default).
_MAX_CLICKS = 14
# Locality gates for the movement (avatar-mobility) detection signature.
_LOCAL_CELL_FRAC = 0.05   # changed cells must be <= this fraction of the grid
_LOCAL_BBOX_FRAC = 0.15   # changed bbox area must be <= this fraction of the grid


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


def _click_candidates(frame: np.ndarray, max_clicks: int = _MAX_CLICKS) -> list[tuple[int, int]]:
    """Reduce ACTION6 to a small salience-ordered set of ``(x, y)`` click points.

    Segments the frame into 4-connected foreground components (background = the
    most common colour) and returns their centroids as ``(x=col, y=row)`` — the
    ACTION6 convention. Smaller components first: a small blob is more likely a
    button/token than a large passive field. Deduplicated, capped at ``max_clicks``.
    """
    comps = connected_components(frame)
    comps.sort(key=lambda c: (c["size"], c["centroid"]))
    out: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for comp in comps:
        cy, cx = comp["centroid"]
        x, y = int(round(cx)), int(round(cy))
        if (x, y) in seen:
            continue
        seen.add((x, y))
        out.append((x, y))
        if len(out) >= max_clicks:
            break
    return out


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
        # next_hash -> list of (prev_hash, action_key) predecessors
        self._preds: dict[str, list[tuple[str, Any]]] = {}
        # A change-transition whose target hash is resolved on the next propose.
        self._pending: tuple[str, Any] | None = None

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Frame-only confidence that this is a graph/navigation game.

        HIGH (0.8) when simple movement actions (ids 1-4) are available AND the
        observed frame-to-frame transitions change small, localized regions
        (the signature of a mobile avatar moving on a static board). Movement
        without such evidence yet is still graph territory (0.45). No movement
        actions at all -> LOW (0.1): clicks/transforms are other tools' turf.
        """
        simple_ids, _ = availability(obs)
        if not any(1 <= a <= 4 for a in simple_ids):
            return 0.1
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
        prev_hash = base_hash(_norm_grid(prev))
        key = _step_to_key(action)
        untried = self._untried.get(prev_hash)
        if untried and key in untried:
            untried.remove(key)
        self._edges.setdefault(prev_hash, {})
        tries = self._tries.setdefault(prev_hash, {})
        tries[key] = tries.get(key, 0) + 1
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
        cur_hash = base_hash(frame)

        if self._pending is not None:
            p_hash, p_key = self._pending
            self._edges.setdefault(p_hash, {})[p_key] = cur_hash
            self._preds.setdefault(cur_hash, []).append((p_hash, p_key))
            self._pending = None

        simple_ids, action6_ok = availability(obs)
        self._ensure_state(cur_hash, frame, simple_ids, action6_ok)

        untried = self._untried.get(cur_hash) or []
        if untried:
            return [_key_to_step(untried[0])]

        path = self._bfs_path_to_frontier(cur_hash)
        if path:
            return [_key_to_step(k) for k in path]

        step = self._random_step(simple_ids, action6_ok, frame)
        return [step] if step is not None else []

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
        if action6_ok:
            for x, y in _click_candidates(frame, self.max_clicks):
                actions.append(("click", int(x), int(y)))
        self._untried[state_hash] = actions
        self._edges.setdefault(state_hash, {})
        self._tries.setdefault(state_hash, {})

    def _bfs_path_to_frontier(self, start: str) -> list[Any] | None:
        """Shortest action path from ``start`` to the nearest frontier state.

        A frontier state is one that still has an untried action. Returns the
        ordered list of action keys that walks there (self-loops are skipped
        naturally by the visited set), or None if none is reachable.
        """
        visited: set[str] = {start}
        queue: deque[tuple[str, list[Any]]] = deque()
        for key, nxt in (self._edges.get(start) or {}).items():
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, [key]))
        while queue:
            node, path = queue.popleft()
            if self._untried.get(node):
                return path
            for key, nxt in (self._edges.get(node) or {}).items():
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + [key]))
        return None

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
                    x, y = self._rng.choice(cands)
                    choices.append((6, (int(x), int(y))))
            h, w = frame.shape if frame.ndim == 2 else (64, 64)
            choices.append((6, (self._rng.randrange(w), self._rng.randrange(h))))
        if not choices:
            return None
        return self._rng.choice(choices)


def _obs_grid(x: Any) -> np.ndarray | None:
    """Best-effort (H, W) grid from an observation OR a raw array; None if neither."""
    if has_frame(x):
        return frame_2d(x)
    a = np.asarray(x)
    if a.ndim >= 2:
        return _norm_grid(a)
    return None
