"""Graph-based state exploration — no learning, pure graph search.

Implements the approach used by the ARC-AGI-3 2nd place team (6.71%):
hash frames to identify unique states, record (state, action) -> next_state
transitions as a graph, and use BFS-like exploration to maximize coverage.
"""

from __future__ import annotations

import hashlib
from collections import deque

import numpy as np


class GraphExplorer:
    """State graph-based exploration — no learning, pure search."""

    # 8x8 grid points for systematic ACTION6 coordinate coverage
    GRID_COORDS: list[tuple[int, int]] = [
        (x, y) for y in range(4, 64, 8) for x in range(4, 64, 8)
    ]

    def __init__(self) -> None:
        # state_hash -> {action_key -> next_state_hash}
        self.state_graph: dict[str, dict[int, str]] = {}
        # state_hash -> visit count
        self.visit_count: dict[str, int] = {}
        # (state_hash, action_key) path history
        self.path_history: list[tuple[str, int]] = []
        # BFS frontier: action_keys to try from known states
        self._bfs_queue: deque[tuple[str, int]] = deque()
        # Track which action_keys have been tried per state
        self._tried: dict[str, set[int]] = {}
        # ACTION6 grid index per state (tracks next grid coord to try)
        self._grid_idx: dict[str, int] = {}
        # Previous state hash for recording transitions
        self._prev_state_hash: str | None = None
        self._prev_action_key: int | None = None

    @staticmethod
    def get_state_hash(frame: np.ndarray) -> str:
        """Hash a frame to a unique state identifier."""
        return hashlib.md5(frame.tobytes()).hexdigest()

    def choose_action(
        self,
        frame: np.ndarray,
        available_actions: list[int],
        action6_available: bool,
    ) -> tuple[int, int | None, int | None]:
        """Choose next action using graph-based exploration.

        Returns (action_id, x_or_none, y_or_none).
        action_id is 1-7. x,y are set only for ACTION6.
        """
        state_hash = self.get_state_hash(frame)
        self.visit_count[state_hash] = self.visit_count.get(state_hash, 0) + 1

        if state_hash not in self._tried:
            self._tried[state_hash] = set()

        tried = self._tried[state_hash]

        # Priority 1: Try untried simple actions (ACTION1-5, ACTION7)
        for aid in available_actions:
            if aid == 6:
                continue  # handle ACTION6 separately
            action_key = aid
            if action_key not in tried:
                self._record_choice(state_hash, action_key)
                return (aid, None, None)

        # Priority 2: Try ACTION6 with grid coordinates
        if action6_available:
            grid_start = self._grid_idx.get(state_hash, 0)
            for i in range(grid_start, len(self.GRID_COORDS)):
                gx, gy = self.GRID_COORDS[i]
                action_key = self._action6_key(gx, gy)
                if action_key not in tried:
                    self._grid_idx[state_hash] = i + 1
                    self._record_choice(state_hash, action_key)
                    return (6, gx, gy)

        # Priority 3: Try ACTION6 at rare-color positions
        if action6_available:
            rare_coords = self._find_rare_color_positions(frame)
            for rx, ry in rare_coords:
                action_key = self._action6_key(rx, ry)
                if action_key not in tried:
                    self._record_choice(state_hash, action_key)
                    return (6, rx, ry)

        # Priority 4: All actions tried — go to least-visited neighbor
        graph_entry = self.state_graph.get(state_hash, {})
        if graph_entry:
            best_key = None
            min_visits = float("inf")
            for ak, next_hash in graph_entry.items():
                v = self.visit_count.get(next_hash, 0)
                if v < min_visits:
                    min_visits = v
                    best_key = ak

            if best_key is not None:
                self._record_choice(state_hash, best_key)
                return self._key_to_action(best_key)

        # Fallback: random available action
        if available_actions:
            aid = available_actions[0]
            if aid == 6 and action6_available:
                gx, gy = self.GRID_COORDS[0]
                self._record_choice(state_hash, self._action6_key(gx, gy))
                return (6, gx, gy)
            self._record_choice(state_hash, aid)
            return (aid, None, None)

        # Nothing available
        return (1, None, None)

    def record_transition(self, next_frame: np.ndarray) -> None:
        """Record the transition from previous state to current state."""
        if self._prev_state_hash is None or self._prev_action_key is None:
            return

        next_hash = self.get_state_hash(next_frame)

        if self._prev_state_hash not in self.state_graph:
            self.state_graph[self._prev_state_hash] = {}
        self.state_graph[self._prev_state_hash][self._prev_action_key] = next_hash

    def on_level_complete(self) -> None:
        """Reset graph for a new level."""
        self.state_graph.clear()
        self.visit_count.clear()
        self.path_history.clear()
        self._bfs_queue.clear()
        self._tried.clear()
        self._grid_idx.clear()
        self._prev_state_hash = None
        self._prev_action_key = None

    def stats(self) -> dict[str, int]:
        """Return exploration statistics."""
        total_edges = sum(len(v) for v in self.state_graph.values())
        return {
            "unique_states": len(self.visit_count),
            "total_edges": total_edges,
            "total_visits": sum(self.visit_count.values()),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _action6_key(x: int, y: int) -> int:
        """Encode ACTION6 + coordinates into a unique action key."""
        # Use 1000 + y*64 + x to avoid collision with simple action ids (1-7)
        return 1000 + y * 64 + x

    @staticmethod
    def _key_to_action(key: int) -> tuple[int, int | None, int | None]:
        """Decode action key back to (action_id, x, y)."""
        if key < 1000:
            return (key, None, None)
        coord = key - 1000
        x = coord % 64
        y = coord // 64
        return (6, x, y)

    def _record_choice(self, state_hash: str, action_key: int) -> None:
        """Record that we chose this action from this state."""
        self._tried[state_hash].add(action_key)
        self.path_history.append((state_hash, action_key))
        self._prev_state_hash = state_hash
        self._prev_action_key = action_key

    @staticmethod
    def _find_rare_color_positions(frame: np.ndarray, max_positions: int = 16) -> list[tuple[int, int]]:
        """Find positions of rare colors in the frame for targeted ACTION6."""
        if frame.ndim == 3:
            # Multi-layer: use first layer
            flat = frame[0]
        else:
            flat = frame

        # Count color frequencies
        colors, counts = np.unique(flat, return_counts=True)
        if len(colors) <= 1:
            return []

        # Sort by frequency (ascending = rarest first), skip background (most common)
        order = np.argsort(counts)
        positions = []

        for ci in order:
            if len(positions) >= max_positions:
                break
            color = colors[ci]
            # Skip the most common color (likely background)
            if counts[ci] == counts[order[-1]]:
                continue
            ys, xs = np.where(flat == color)
            if len(ys) == 0:
                continue
            # Sample up to 4 positions per color
            indices = np.linspace(0, len(ys) - 1, min(4, len(ys)), dtype=int)
            for idx in indices:
                positions.append((int(xs[idx]), int(ys[idx])))
                if len(positions) >= max_positions:
                    break

        return positions
