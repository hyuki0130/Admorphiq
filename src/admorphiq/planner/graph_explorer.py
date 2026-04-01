"""Graph-based state exploration — no learning, pure graph search.

Implements the approach used by the ARC-AGI-3 2nd place team (6.71%):
hash frames to identify unique states, record (state, action) -> next_state
transitions as a graph, and use BFS-like exploration to maximize coverage.

Enhanced with:
- Novelty scoring (new color patterns prioritized)
- Change magnitude tracking (prefer actions that cause big frame changes)
- Backtracking to states with untried actions
- Game mechanic detection (movement patterns, timers, gravity)
- Action sequence strategies (multi-step combos for complex games)
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

    # Finer 4x4 grid for second pass
    FINE_GRID_COORDS: list[tuple[int, int]] = [
        (x, y) for y in range(2, 64, 4) for x in range(2, 64, 4)
    ]

    # Common multi-step action sequences to try
    # These cover patterns like: repeated direction, direction+special, zigzag
    ACTION_SEQUENCES: list[list[int]] = [
        # Repeated single direction (gravity/sliding games)
        [1] * 10, [2] * 10, [3] * 10, [4] * 10,
        # Direction + special action (teleport/jump games)
        [1, 5], [2, 5], [3, 5], [4, 5],
        [5, 1], [5, 2], [5, 3], [5, 4],
        # Two-direction combos (navigate around walls)
        [1, 3], [1, 4], [2, 3], [2, 4],
        [3, 1], [3, 2], [4, 1], [4, 2],
        # Longer navigation patterns
        [1, 1, 3], [1, 1, 4], [2, 2, 3], [2, 2, 4],
        [3, 3, 1], [3, 3, 2], [4, 4, 1], [4, 4, 2],
        # Special action combos
        [5, 5], [5, 1, 1], [5, 2, 2], [5, 3, 3], [5, 4, 4],
        # Cancel/undo patterns
        [7, 1], [7, 2], [7, 3], [7, 4], [7, 5],
    ]

    def __init__(self) -> None:
        # state_hash -> {action_key -> next_state_hash}
        self.state_graph: dict[str, dict[int, str]] = {}
        # state_hash -> visit count
        self.visit_count: dict[str, int] = {}
        # (state_hash, action_key) path history
        self.path_history: list[tuple[str, int]] = []
        # Track which action_keys have been tried per state
        self._tried: dict[str, set[int]] = {}
        # ACTION6 grid index per state (tracks next grid coord to try)
        self._grid_idx: dict[str, int] = {}
        # Previous state hash for recording transitions
        self._prev_state_hash: str | None = None
        self._prev_action_key: int | None = None
        # Previous frame for change magnitude tracking
        self._prev_frame: np.ndarray | None = None
        # (state_hash, action_key) -> change magnitude (pixel diff count)
        self._change_magnitude: dict[tuple[str, int], int] = {}
        # state_hash -> color histogram (for novelty)
        self._color_histograms: dict[str, np.ndarray] = {}
        # Global color histogram for novelty comparison
        self._global_color_hist: np.ndarray = np.zeros(16, dtype=np.float64)
        self._global_hist_count: int = 0
        # Track action_keys that caused state changes (not self-loops)
        self._productive_actions: dict[str, set[int]] = {}
        # Fine grid pass flag per state
        self._fine_grid_idx: dict[str, int] = {}

        # --- Game mechanic detection ---
        # action_id -> list of (dy, dx) movements observed
        self._action_movements: dict[int, list[tuple[float, float]]] = {}
        # Detected game type: "unknown", "movement", "sliding", "tetris", "teleport"
        self._detected_game_type: str = "unknown"
        # action_id -> whether it's blocked (no change on repeat)
        self._blocked_actions: dict[int, bool] = {}
        # Track which action sequences have been tried from initial state
        self._sequence_idx: int = 0
        # Pending action sequence to execute
        self._pending_sequence: list[int] = []
        # Step counter for sequence-based exploration
        self._step_count: int = 0
        # Actions sorted by change magnitude (most productive first)
        self._action_priority: list[int] = []
        # Track if initial mechanic probing is done
        self._probing_done: bool = False
        # Number of probing steps done
        self._probe_step: int = 0

    @staticmethod
    def get_state_hash(frame: np.ndarray) -> str:
        """Hash a frame to a unique state identifier.

        Uses full resolution hash for accurate state distinction.
        """
        if frame.ndim == 3:
            flat = frame[0]
        else:
            flat = frame
        return hashlib.md5(flat.tobytes()).hexdigest()

    @staticmethod
    def get_exact_hash(frame: np.ndarray) -> str:
        """Full-resolution hash for exact state comparison."""
        if frame.ndim == 3:
            flat = frame[0]
        else:
            flat = frame
        return hashlib.md5(flat.tobytes()).hexdigest()

    def _compute_color_histogram(self, frame: np.ndarray) -> np.ndarray:
        """Compute normalized color histogram of frame."""
        if frame.ndim == 3:
            flat = frame[0]
        else:
            flat = frame
        hist = np.bincount(flat.ravel().astype(np.int32), minlength=16).astype(np.float64)
        total = hist.sum()
        if total > 0:
            hist /= total
        return hist

    def _novelty_score(self, state_hash: str, frame: np.ndarray) -> float:
        """Compute novelty score for a state based on color histogram divergence."""
        hist = self._compute_color_histogram(frame)
        self._color_histograms[state_hash] = hist

        if self._global_hist_count == 0:
            return 1.0  # First state is maximally novel

        # KL-divergence-like measure (symmetric)
        avg_hist = self._global_color_hist / self._global_hist_count
        # Add small epsilon to avoid log(0)
        eps = 1e-8
        h1 = hist + eps
        h2 = avg_hist + eps
        divergence = float(np.sum(np.abs(h1 - h2)))
        return divergence

    def _update_global_histogram(self, frame: np.ndarray) -> None:
        """Update running average of color histograms."""
        hist = self._compute_color_histogram(frame)
        self._global_color_hist += hist
        self._global_hist_count += 1

    def _detect_mechanics(self, frame: np.ndarray, prev_frame: np.ndarray | None,
                          action_key: int) -> None:
        """Detect game mechanics from action effects."""
        if prev_frame is None:
            return

        flat_now = frame[0] if frame.ndim == 3 else frame
        flat_prev = prev_frame[0] if prev_frame.ndim == 3 else prev_frame

        diff_mask = flat_now != flat_prev
        n_changed = int(diff_mask.sum())

        if action_key < 1000 and action_key <= 5:
            # Track movement patterns per action
            if n_changed == 0:
                self._blocked_actions[action_key] = True
            else:
                self._blocked_actions[action_key] = False
                # Detect center-of-mass movement for each non-bg color
                colors, counts = np.unique(flat_prev, return_counts=True)
                bg_color = int(colors[counts.argmax()])
                for color in colors:
                    if color == bg_color:
                        continue
                    prev_mask = flat_prev == color
                    now_mask = flat_now == color
                    if prev_mask.sum() > 2 and now_mask.sum() > 2:
                        prev_ys, prev_xs = np.where(prev_mask)
                        now_ys, now_xs = np.where(now_mask)
                        dy = float(now_ys.mean() - prev_ys.mean())
                        dx = float(now_xs.mean() - prev_xs.mean())
                        if abs(dy) > 0.3 or abs(dx) > 0.3:
                            self._action_movements.setdefault(action_key, []).append((dy, dx))

        # After enough probing, detect game type
        if self._probe_step >= 8 and self._detected_game_type == "unknown":
            self._infer_game_type()

    def _infer_game_type(self) -> None:
        """Infer game type from observed mechanics."""
        if not self._action_movements:
            self._detected_game_type = "static"
            return

        # Check if actions 1-4 cause consistent directional movement
        directional = 0
        blocked_count = sum(1 for v in self._blocked_actions.values() if v)
        for aid in [1, 2, 3, 4]:
            moves = self._action_movements.get(aid, [])
            if len(moves) >= 1:
                # Check consistency
                dy_avg = sum(m[0] for m in moves) / len(moves)
                dx_avg = sum(m[1] for m in moves) / len(moves)
                if abs(dy_avg) > 0.5 or abs(dx_avg) > 0.5:
                    directional += 1

        # Check for ACTION5 teleport behavior
        has_teleport = False
        a5_moves = self._action_movements.get(5, [])
        if a5_moves:
            for dy, dx in a5_moves:
                if abs(dy) > 10 or abs(dx) > 10:
                    has_teleport = True
                    break

        if directional >= 3 and has_teleport:
            self._detected_game_type = "teleport"  # RE86-like
        elif directional >= 3 and blocked_count >= 1:
            self._detected_game_type = "sliding"  # DC22-like: movement with walls
        elif directional >= 2:
            # Check for gravity (action 2 = no change = can't go down)
            if self._blocked_actions.get(2, False):
                self._detected_game_type = "tetris"  # SK48-like
            else:
                self._detected_game_type = "movement"
        else:
            self._detected_game_type = "complex"

        # Build action priority based on change magnitude
        action_changes: dict[int, float] = {}
        for (sh, ak), mag in self._change_magnitude.items():
            if ak < 1000:
                action_changes[ak] = max(action_changes.get(ak, 0), mag)
        self._action_priority = sorted(action_changes.keys(),
                                       key=lambda a: action_changes[a], reverse=True)

    def _get_sequence_action(self, available_actions: list[int]) -> int | None:
        """Get next action from pending sequence, if any."""
        while self._pending_sequence:
            action = self._pending_sequence.pop(0)
            if action in available_actions:
                return action
        return None

    def _pick_next_sequence(self, available_actions: list[int]) -> bool:
        """Pick the next untried action sequence. Returns True if found."""
        available_set = set(available_actions) - {6}
        while self._sequence_idx < len(self.ACTION_SEQUENCES):
            seq = self.ACTION_SEQUENCES[self._sequence_idx]
            self._sequence_idx += 1
            # Only try sequences where all actions are available
            if all(a in available_set for a in seq):
                self._pending_sequence = list(seq)
                return True
        return False

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
        self._update_global_histogram(frame)
        self._step_count += 1

        if state_hash not in self._tried:
            self._tried[state_hash] = set()
        if state_hash not in self._productive_actions:
            self._productive_actions[state_hash] = set()

        tried = self._tried[state_hash]

        # Track change magnitude from previous action
        if self._prev_frame is not None and self._prev_state_hash is not None and self._prev_action_key is not None:
            if frame.ndim == 3:
                diff = int(np.count_nonzero(frame[0] != self._prev_frame[0] if self._prev_frame.ndim == 3 else frame[0] != self._prev_frame))
            else:
                prev = self._prev_frame[0] if self._prev_frame.ndim == 3 else self._prev_frame
                diff = int(np.count_nonzero(frame != prev))
            self._change_magnitude[(self._prev_state_hash, self._prev_action_key)] = diff
            # Track productive actions (ones that changed state)
            if self.get_state_hash(self._prev_frame) != state_hash:
                self._productive_actions.setdefault(self._prev_state_hash, set()).add(self._prev_action_key)

            # Detect game mechanics during probing phase
            if not self._probing_done:
                self._detect_mechanics(frame, self._prev_frame, self._prev_action_key)
                self._probe_step += 1
                if self._probe_step >= 15:
                    self._probing_done = True
                    if self._detected_game_type == "unknown":
                        self._infer_game_type()

        self._prev_frame = frame.copy()

        # If we have a pending sequence, continue executing it
        if self._pending_sequence:
            seq_action = self._get_sequence_action(available_actions)
            if seq_action is not None:
                self._record_choice(state_hash, seq_action)
                return (seq_action, None, None)

        # Priority 1: Try untried simple actions (ACTION1-5, ACTION7)
        # Sort by: productive in other states > never tried anywhere
        untried_simple = []
        for aid in available_actions:
            if aid == 6:
                continue
            action_key = aid
            if action_key not in tried:
                untried_simple.append(aid)

        if untried_simple:
            # Prefer actions that were productive in other states
            productive_anywhere = []
            for aid in untried_simple:
                for sh, prods in self._productive_actions.items():
                    if aid in prods:
                        productive_anywhere.append(aid)
                        break
            if productive_anywhere:
                choice = productive_anywhere[0]
            else:
                choice = untried_simple[0]
            self._record_choice(state_hash, choice)
            return (choice, None, None)

        # Priority 1.5: After probing, try action sequences for complex games
        if self._probing_done and self._detected_game_type in ("sliding", "tetris", "teleport", "complex"):
            if self._pick_next_sequence(available_actions):
                seq_action = self._get_sequence_action(available_actions)
                if seq_action is not None:
                    self._record_choice(state_hash, seq_action)
                    return (seq_action, None, None)

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

        # Priority 3: Try ACTION6 on non-background pixels
        if action6_available:
            nonbg = self._find_nonbackground_pixels(frame)
            for nx, ny in nonbg:
                action_key = self._action6_key(nx, ny)
                if action_key not in tried:
                    self._record_choice(state_hash, action_key)
                    return (6, nx, ny)

        # Priority 3b: Try ACTION6 at rare-color positions
        if action6_available:
            rare_coords = self._find_rare_color_positions(frame)
            for rx, ry in rare_coords:
                action_key = self._action6_key(rx, ry)
                if action_key not in tried:
                    self._record_choice(state_hash, action_key)
                    return (6, rx, ry)

        # Priority 4: Fine grid pass for ACTION6
        if action6_available:
            fine_start = self._fine_grid_idx.get(state_hash, 0)
            for i in range(fine_start, len(self.FINE_GRID_COORDS)):
                fx, fy = self.FINE_GRID_COORDS[i]
                action_key = self._action6_key(fx, fy)
                if action_key not in tried:
                    self._fine_grid_idx[state_hash] = i + 1
                    self._record_choice(state_hash, action_key)
                    return (6, fx, fy)

        # Priority 5: Navigate to least-visited neighbor, preferring
        # neighbors reached by high-change actions
        graph_entry = self.state_graph.get(state_hash, {})
        if graph_entry:
            best_key = None
            best_score = float("inf")
            for ak, next_hash in graph_entry.items():
                visits = self.visit_count.get(next_hash, 0)
                # Check if the neighbor has untried actions
                neighbor_untried = len(self._get_untried_count(next_hash, available_actions, action6_available))
                # Score: lower is better. Heavily prefer states with untried actions.
                change_mag = self._change_magnitude.get((state_hash, ak), 0)
                score = visits * 10 - neighbor_untried * 100 - change_mag
                if score < best_score:
                    best_score = score
                    best_key = ak

            if best_key is not None:
                self._record_choice(state_hash, best_key)
                return self._key_to_action(best_key)

        # Priority 6: Backtrack — find a state in graph with untried actions, BFS path to it
        backtrack_path = self._find_backtrack_path(state_hash, available_actions, action6_available)
        if backtrack_path:
            first_key = backtrack_path[0]
            self._record_choice(state_hash, first_key)
            return self._key_to_action(first_key)

        # Priority 7: For detected game types, try productive action combos
        if self._action_priority and self._detected_game_type != "unknown":
            # Cycle through most productive actions
            cycle_idx = self._step_count % len(self._action_priority)
            aid = self._action_priority[cycle_idx]
            if aid in available_actions:
                self._record_choice(state_hash, aid)
                return (aid, None, None)

        # Fallback: repeat the action that caused the most change from this state
        if graph_entry:
            best_change_key = max(
                graph_entry.keys(),
                key=lambda ak: self._change_magnitude.get((state_hash, ak), 0),
            )
            self._record_choice(state_hash, best_change_key)
            return self._key_to_action(best_change_key)

        # Last resort: first available action
        if available_actions:
            aid = available_actions[0]
            if aid == 6 and action6_available:
                gx, gy = self.GRID_COORDS[0]
                self._record_choice(state_hash, self._action6_key(gx, gy))
                return (6, gx, gy)
            self._record_choice(state_hash, aid)
            return (aid, None, None)

        return (1, None, None)

    def _get_untried_count(self, state_hash: str, available_actions: list[int], action6_available: bool) -> list[int]:
        """Get count of untried action keys for a state."""
        tried = self._tried.get(state_hash, set())
        untried = []
        for aid in available_actions:
            if aid == 6:
                continue
            if aid not in tried:
                untried.append(aid)
        if action6_available:
            grid_start = self._grid_idx.get(state_hash, 0)
            untried_grid = len(self.GRID_COORDS) - grid_start
            untried.extend([0] * untried_grid)  # placeholder count
        return untried

    def _find_backtrack_path(
        self, current_hash: str, available_actions: list[int], action6_available: bool,
    ) -> list[int] | None:
        """BFS to find path to a state with untried actions."""
        if current_hash not in self.state_graph:
            return None

        queue: deque[tuple[str, list[int]]] = deque([(current_hash, [])])
        visited: set[str] = {current_hash}

        while queue:
            state, path = queue.popleft()
            if len(path) > 30:
                continue

            # Check if this state has untried actions
            if path:  # skip current state
                untried = self._get_untried_count(state, available_actions, action6_available)
                if untried:
                    return path

            for action_key, next_hash in self.state_graph.get(state, {}).items():
                if next_hash not in visited:
                    visited.add(next_hash)
                    queue.append((next_hash, path + [action_key]))

        return None

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
        self._tried.clear()
        self._grid_idx.clear()
        self._fine_grid_idx.clear()
        self._prev_state_hash = None
        self._prev_action_key = None
        self._prev_frame = None
        self._change_magnitude.clear()
        self._color_histograms.clear()
        self._global_color_hist = np.zeros(16, dtype=np.float64)
        self._global_hist_count = 0
        self._productive_actions.clear()
        # Reset mechanic detection (re-probe on new level)
        self._action_movements.clear()
        self._detected_game_type = "unknown"
        self._blocked_actions.clear()
        self._sequence_idx = 0
        self._pending_sequence.clear()
        self._step_count = 0
        self._action_priority.clear()
        self._probing_done = False
        self._probe_step = 0

    def stats(self) -> dict[str, int | str]:
        """Return exploration statistics."""
        total_edges = sum(len(v) for v in self.state_graph.values())
        productive_count = sum(len(v) for v in self._productive_actions.values())
        return {
            "unique_states": len(self.visit_count),
            "total_edges": total_edges,
            "total_visits": sum(self.visit_count.values()),
            "productive_actions": productive_count,
            "game_type": self._detected_game_type,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _action6_key(x: int, y: int) -> int:
        """Encode ACTION6 + coordinates into a unique action key."""
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
    def _find_nonbackground_pixels(frame: np.ndarray, max_positions: int = 64) -> list[tuple[int, int]]:
        """Find positions of non-background pixels for targeted ACTION6."""
        if frame.ndim == 3:
            flat = frame[0]
        else:
            flat = frame

        colors, counts = np.unique(flat, return_counts=True)
        if len(colors) <= 1:
            return []

        bg_color = colors[counts.argmax()]
        non_bg = flat != bg_color
        if not non_bg.any():
            return []

        ys, xs = np.where(non_bg)
        n_samples = min(max_positions, len(ys))
        indices = np.linspace(0, len(ys) - 1, n_samples, dtype=int)
        return [(int(xs[i]), int(ys[i])) for i in indices]

    @staticmethod
    def _find_rare_color_positions(frame: np.ndarray, max_positions: int = 16) -> list[tuple[int, int]]:
        """Find positions of rare colors in the frame for targeted ACTION6."""
        if frame.ndim == 3:
            flat = frame[0]
        else:
            flat = frame

        colors, counts = np.unique(flat, return_counts=True)
        if len(colors) <= 1:
            return []

        order = np.argsort(counts)
        positions = []

        for ci in order:
            if len(positions) >= max_positions:
                break
            color = colors[ci]
            if counts[ci] == counts[order[-1]]:
                continue
            ys, xs = np.where(flat == color)
            if len(ys) == 0:
                continue
            indices = np.linspace(0, len(ys) - 1, min(4, len(ys)), dtype=int)
            for idx in indices:
                positions.append((int(xs[idx]), int(ys[idx])))
                if len(positions) >= max_positions:
                    break

        return positions
