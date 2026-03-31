"""Frame-based state transition graph for exploration planning."""

from __future__ import annotations

import hashlib
from collections import deque

import numpy as np


class StateGraph:
    """Track state transitions and plan exploration via BFS."""

    def __init__(self) -> None:
        self.graph: dict[str, dict[int, str]] = {}  # hash -> {action_id -> next_hash}
        self.frames: dict[str, np.ndarray] = {}  # hash -> frame
        self.visits: dict[str, int] = {}  # hash -> visit count
        self.scores: dict[str, float] = {}  # hash -> best score seen at this state

    @staticmethod
    def hash_frame(frame: np.ndarray) -> str:
        """Compute a compact hash of a frame array."""
        return hashlib.md5(frame.tobytes()).hexdigest()[:16]

    def add_state(self, frame: np.ndarray) -> str:
        """Add a state (frame) to the graph. Returns its hash."""
        h = self.hash_frame(frame)
        if h not in self.graph:
            self.graph[h] = {}
            self.frames[h] = frame.copy()
            self.visits[h] = 0
        self.visits[h] += 1
        return h

    def add_transition(self, from_hash: str, action_id: int, to_hash: str) -> None:
        """Record a state transition."""
        if from_hash in self.graph:
            self.graph[from_hash][action_id] = to_hash

    def get_neighbors(self, state_hash: str) -> dict[int, str]:
        """Get known transitions from a state."""
        return self.graph.get(state_hash, {})

    def get_path_to_least_visited(self, current_hash: str) -> list[int] | None:
        """BFS to find the shortest action path to the least-visited reachable state.

        Returns a list of action IDs, or None if no path found.
        """
        if current_hash not in self.graph:
            return None

        # BFS
        queue: deque[tuple[str, list[int]]] = deque([(current_hash, [])])
        visited: set[str] = {current_hash}
        best_path: list[int] | None = None
        best_visit_count = float("inf")

        while queue:
            state, path = queue.popleft()

            # Check if this state is less visited
            visit_count = self.visits.get(state, 0)
            if path and visit_count < best_visit_count:
                best_visit_count = visit_count
                best_path = path

            # Limit search depth
            if len(path) >= 20:
                continue

            for action_id, next_hash in self.graph.get(state, {}).items():
                if next_hash not in visited:
                    visited.add(next_hash)
                    queue.append((next_hash, path + [action_id]))

        return best_path

    def get_unvisited_actions(self, state_hash: str, available_actions: list[int]) -> list[int]:
        """Get actions not yet tried from this state."""
        known = self.graph.get(state_hash, {})
        return [a for a in available_actions if a not in known]

    def get_least_visited_action(self, state_hash: str, available_actions: list[int]) -> int:
        """Choose the action leading to the least-visited next state.

        If some actions haven't been tried yet, prefer those.
        Falls back to random choice from available actions.
        """
        # Prefer untried actions
        untried = self.get_unvisited_actions(state_hash, available_actions)
        if untried:
            return int(np.random.choice(untried))

        # Among tried actions, pick the one leading to least-visited state
        transitions = self.graph.get(state_hash, {})
        best_action = available_actions[0]
        best_visits = float("inf")

        for action_id in available_actions:
            if action_id in transitions:
                next_hash = transitions[action_id]
                v = self.visits.get(next_hash, 0)
                if v < best_visits:
                    best_visits = v
                    best_action = action_id

        return best_action

    @property
    def num_states(self) -> int:
        return len(self.graph)

    @property
    def num_transitions(self) -> int:
        return sum(len(t) for t in self.graph.values())

    def clear(self) -> None:
        """Reset the graph."""
        self.graph.clear()
        self.frames.clear()
        self.visits.clear()
        self.scores.clear()
