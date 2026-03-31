"""Ensemble agent for ARC-AGI-3.

Combines multiple strategies and selects the best approach per game:
1. Enhanced frame-diff solver strategies (from solve_games.py)
2. Graph-based exploration (from GraphExplorer)
3. Adaptive strategies: BFS navigation, pattern repetition, wall avoidance

Goal: surpass the 4-game baseline from solve_games.py.
"""

from __future__ import annotations

import hashlib
import itertools
import time
from collections import defaultdict, deque
from typing import Any

import numpy as np

from arcengine import GameAction

from .utils import GameLogger


# ─── Utility functions ──────────────────────────────────────────────

def get_frame(obs: Any) -> np.ndarray:
    """Extract (64, 64) int32 frame from observation."""
    return np.array(obs.frame[0], dtype=np.int32)


def frame_diff(f1: np.ndarray, f2: np.ndarray) -> int:
    return int(np.count_nonzero(f1 - f2))


def frame_hash(frame: np.ndarray) -> str:
    return hashlib.md5(frame.tobytes()).hexdigest()[:16]


def click(env: Any, x: int, y: int) -> Any:
    a6 = GameAction.ACTION6
    a6.set_data({"x": x, "y": y})
    return env.step(a6, data={"x": x, "y": y})


def act(env: Any, aid: int) -> Any:
    return env.step(GameAction.from_id(aid))


def reset(env: Any) -> Any:
    return env.step(GameAction.RESET)


def rare_colors(frame: np.ndarray, max_count: int = 500) -> list[tuple[int, int]]:
    """Return [(color, count)] sorted by ascending count, skipping color 0."""
    unique, counts = np.unique(frame, return_counts=True)
    return [(int(c), int(n)) for n, c in sorted(zip(counts, unique)) if c != 0 and n <= max_count]


def find_color_positions(frame: np.ndarray, color: int) -> np.ndarray:
    """Return Nx2 array of (y, x) positions for a color."""
    return np.argwhere(frame == color)


def detect_player_and_dirs(env: Any, dir_actions: list[int], trials: int = 2) -> tuple[int | None, dict[str, int]]:
    """Detect player color and direction mapping via frame diffs."""
    movement_by_color: dict[int, list[tuple[int, float, float]]] = defaultdict(list)

    for aid in dir_actions:
        for _ in range(trials):
            obs = reset(env)
            if obs is None:
                continue
            f_before = get_frame(obs)
            obs = act(env, aid)
            if obs is None:
                continue
            f_after = get_frame(obs)

            for color in range(1, 16):
                before_mask = f_before == color
                after_mask = f_after == color
                bc = int(before_mask.sum())
                ac = int(after_mask.sum())
                if bc > 0 and ac > 0 and bc < 2000:
                    b_center = np.array(np.where(before_mask)).mean(axis=1)
                    a_center = np.array(np.where(after_mask)).mean(axis=1)
                    dy = float(a_center[0] - b_center[0])
                    dx = float(a_center[1] - b_center[1])
                    if abs(dy) > 0.3 or abs(dx) > 0.3:
                        movement_by_color[color].append((aid, dy, dx))

    if not movement_by_color:
        return None, {}

    # Player = color that moves most consistently
    player_color = max(movement_by_color, key=lambda c: len(movement_by_color[c]))

    # Build direction map
    dir_to_act: dict[str, int] = {}
    for aid, dy, dx in movement_by_color[player_color]:
        if abs(dy) > abs(dx):
            direction = "UP" if dy < 0 else "DOWN"
        else:
            direction = "LEFT" if dx < 0 else "RIGHT"
        dir_to_act[direction] = aid

    return player_color, dir_to_act


# ─── Strategy functions ─────────────────────────────────────────────
# Each returns (levels_completed, strategy_name, actions_used)

def strat_sustained(env: Any, aid: int, steps: int = 80) -> tuple[int, str, int]:
    """Sustained single direction."""
    obs = reset(env)
    used, best, name = 1, 0, ""
    for _ in range(steps):
        obs = act(env, aid)
        used += 1
        if obs.levels_completed > best:
            best = obs.levels_completed
            name = f"sustained_A{aid}"
        if obs.state.name in ("WIN", "GAME_OVER"):
            break
    return best, name, used


def strat_zigzag(env: Any, a1: int, a2: int, length: int, cycles: int = 25) -> tuple[int, str, int]:
    """Zigzag between two actions."""
    obs = reset(env)
    used, best, name = 1, 0, ""
    for _ in range(cycles):
        done = False
        for _ in range(length):
            obs = act(env, a1)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"zig{length}_A{a1}A{a2}"
            if obs.state.name in ("WIN", "GAME_OVER"):
                done = True
                break
        if done:
            break
        for _ in range(length):
            obs = act(env, a2)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"zig{length}_A{a1}A{a2}"
            if obs.state.name in ("WIN", "GAME_OVER"):
                done = True
                break
        if done:
            break
    return best, name, used


def strat_click_rare(env: Any, budget: int = 300) -> tuple[int, str, int]:
    """Click on pixels of rare colors."""
    obs = reset(env)
    used, best, name = 1, 0, ""
    frame = get_frame(obs)
    unique, counts = np.unique(frame, return_counts=True)
    for cnt, color in sorted(zip(counts.tolist(), unique.tolist())):
        if color == 0 or cnt > 500:
            continue
        positions = np.argwhere(frame == color)
        for pos in positions:
            if used >= budget:
                return best, name, used
            cy, cx = int(pos[0]), int(pos[1])
            obs = click(env, cx, cy)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"click_c{color}_({cy},{cx})"
            if obs.state.name == "GAME_OVER":
                obs = reset(env)
                used += 1
                frame = get_frame(obs)
            if obs.state.name == "WIN":
                return best, name, used
    return best, name, used


def strat_raster(env: Any, step_size: int = 1, budget: int = 4100) -> tuple[int, str, int]:
    """Click every pixel in raster order."""
    obs = reset(env)
    used, best, name = 1, 0, ""
    for y in range(0, 64, step_size):
        for x in range(0, 64, step_size):
            if used >= budget:
                return best, name, used
            obs = click(env, x, y)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"raster_({y},{x})"
            if obs.state.name == "GAME_OVER":
                obs = reset(env)
                used += 1
            if obs.state.name == "WIN":
                return best, name, used
    return best, name, used


def strat_move_click(env: Any, aid: int, budget: int = 200) -> tuple[int, str, int]:
    """Move then click on rarest color, alternating."""
    obs = reset(env)
    used, best, name = 1, 0, ""
    for _ in range(budget // 3):
        if used >= budget or obs.state.name == "WIN":
            break
        if obs.state.name == "GAME_OVER":
            obs = reset(env)
            used += 1
            continue
        obs = act(env, aid)
        used += 1
        if obs.levels_completed > best:
            best = obs.levels_completed
            name = f"moveclick_A{aid}"
        if obs.state.name in ("WIN", "GAME_OVER"):
            continue
        frame = get_frame(obs)
        rc = rare_colors(frame, max_count=300)
        for color, cnt in rc[:1]:
            positions = np.argwhere(frame == color)
            if len(positions) > 0:
                center = positions.mean(axis=0)
                cy = max(0, min(63, int(round(center[0]))))
                cx = max(0, min(63, int(round(center[1]))))
                obs = click(env, cx, cy)
                used += 1
                if obs.levels_completed > best:
                    best = obs.levels_completed
                    name = f"moveclick_A{aid}_c{color}"
                break
    return best, name, used


def strat_navigate(env: Any, player_color: int, dir_to_act: dict[str, int],
                   target_color: int, budget: int = 105) -> tuple[int, str, int]:
    """Navigate player towards target color."""
    obs = reset(env)
    used, best, name = 1, 0, ""
    for step in range(budget - 1):
        if obs.state.name in ("WIN", "GAME_OVER"):
            break
        frame = get_frame(obs)
        pp = np.argwhere(frame == player_color)
        tp = np.argwhere(frame == target_color)
        if len(pp) == 0 or len(tp) == 0:
            aids = list(dir_to_act.values())
            if aids:
                obs = act(env, aids[step % len(aids)])
                used += 1
            continue
        pc = pp.mean(axis=0)
        tc = tp.mean(axis=0)
        dy, dx = tc[0] - pc[0], tc[1] - pc[1]
        aid = None
        if abs(dy) >= abs(dx):
            aid = dir_to_act.get("UP") if dy < 0 else dir_to_act.get("DOWN")
        if aid is None:
            aid = dir_to_act.get("LEFT") if dx < 0 else dir_to_act.get("RIGHT")
        if aid is None:
            aids = list(dir_to_act.values())
            aid = aids[step % len(aids)] if aids else None
        if aid is not None:
            obs = act(env, aid)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"nav_c{target_color}"
    return best, name, used


# ─── NEW enhanced strategies ────────────────────────────────────────

def strat_bfs_explore(env: Any, dir_actions: list[int], budget: int = 300) -> tuple[int, str, int]:
    """BFS exploration: track visited states, prefer actions leading to new states."""
    obs = reset(env)
    used, best, name = 1, 0, ""
    visited_hashes: set[str] = set()
    action_change_count: dict[int, int] = defaultdict(int)  # which actions cause changes
    last_hash = frame_hash(get_frame(obs))
    visited_hashes.add(last_hash)

    for step in range(budget - 1):
        if obs.state.name in ("WIN", "GAME_OVER"):
            if obs.state.name == "GAME_OVER":
                obs = reset(env)
                used += 1
                last_hash = frame_hash(get_frame(obs))
                visited_hashes.add(last_hash)
                continue
            break

        if obs.levels_completed > best:
            best = obs.levels_completed
            name = f"bfs_explore"
            # Reset visited on level change
            visited_hashes.clear()

        # Pick action: prefer ones that historically cause changes
        # Try each action, prefer those leading to unvisited states
        best_aid = None
        best_novelty = -1

        # Shuffle to add randomness
        shuffled = list(dir_actions)
        np.random.shuffle(shuffled)

        for aid in shuffled:
            novelty = action_change_count.get(aid, 0)
            if novelty > best_novelty:
                best_novelty = novelty
                best_aid = aid

        # Sometimes try random action for exploration
        if step % 7 == 0 or best_aid is None:
            best_aid = dir_actions[np.random.randint(len(dir_actions))]

        obs = act(env, best_aid)
        used += 1
        new_hash = frame_hash(get_frame(obs))

        if new_hash != last_hash:
            action_change_count[best_aid] += 1

        if new_hash not in visited_hashes:
            visited_hashes.add(new_hash)
            action_change_count[best_aid] += 2  # bonus for truly new state

        if obs.levels_completed > best:
            best = obs.levels_completed
            name = f"bfs_explore"

        last_hash = new_hash

    return best, name, used


def strat_wall_avoid(env: Any, dir_actions: list[int], budget: int = 300) -> tuple[int, str, int]:
    """Movement with wall avoidance: if action doesn't change frame, try another direction."""
    obs = reset(env)
    used, best, name = 1, 0, ""
    current_dir_idx = 0
    stuck_count = 0

    prev_frame = get_frame(obs)

    for step in range(budget - 1):
        if obs.state.name in ("WIN", "GAME_OVER"):
            if obs.state.name == "GAME_OVER":
                obs = reset(env)
                used += 1
                prev_frame = get_frame(obs)
                stuck_count = 0
                continue
            break

        if obs.levels_completed > best:
            best = obs.levels_completed
            name = f"wall_avoid"
            stuck_count = 0

        aid = dir_actions[current_dir_idx % len(dir_actions)]
        obs = act(env, aid)
        used += 1
        new_frame = get_frame(obs)

        if frame_diff(prev_frame, new_frame) == 0:
            stuck_count += 1
            if stuck_count >= 2:
                # Change direction
                current_dir_idx += 1
                stuck_count = 0
        else:
            stuck_count = 0

        if obs.levels_completed > best:
            best = obs.levels_completed
            name = f"wall_avoid"

        prev_frame = new_frame

    return best, name, used


def strat_pattern_repeat(env: Any, avail_actions: list[int], budget: int = 400) -> tuple[int, str, int]:
    """Find action patterns that cause frame changes, then repeat them."""
    obs = reset(env)
    used, best, name = 1, 0, ""

    # Phase 1: Discover which actions cause changes (50 actions)
    effective_actions: list[int] = []
    prev_frame = get_frame(obs)

    for aid in avail_actions:
        if aid in (7, 8):
            continue
        obs_test = act(env, aid)
        used += 1
        new_frame = get_frame(obs_test)
        if frame_diff(prev_frame, new_frame) > 0:
            effective_actions.append(aid)
        prev_frame = new_frame

        if obs_test.levels_completed > best:
            best = obs_test.levels_completed
            name = f"pattern_repeat"
        if obs_test.state.name in ("WIN", "GAME_OVER"):
            if obs_test.state.name == "GAME_OVER":
                obs_test = reset(env)
                used += 1
                prev_frame = get_frame(obs_test)
            else:
                return best, name, used
        obs = obs_test

    if not effective_actions:
        effective_actions = [a for a in avail_actions if a not in (7, 8)]

    if not effective_actions:
        return best, name, used

    # Phase 2: Try sequences of effective actions
    # Try individual repeat
    obs = reset(env)
    used += 1

    for _ in range((budget - used) // 1):
        if used >= budget or obs.state.name == "WIN":
            break
        if obs.state.name == "GAME_OVER":
            obs = reset(env)
            used += 1
            continue

        # Cycle through effective actions
        aid = effective_actions[used % len(effective_actions)]
        obs = act(env, aid)
        used += 1
        if obs.levels_completed > best:
            best = obs.levels_completed
            name = f"pattern_repeat"

    return best, name, used


def strat_click_diff_track(env: Any, budget: int = 400) -> tuple[int, str, int]:
    """Click strategy that tracks which clicks cause the most frame changes."""
    obs = reset(env)
    used, best, name = 1, 0, ""
    frame = get_frame(obs)

    # Phase 1: Sample clicks and track effect sizes
    click_effects: list[tuple[int, int, int]] = []  # (x, y, diff_size)

    # Sample a grid of points
    for y in range(4, 64, 8):
        for x in range(4, 64, 8):
            if used >= budget // 3:
                break
            prev_f = get_frame(obs)
            obs = click(env, x, y)
            used += 1
            new_f = get_frame(obs)
            diff_sz = frame_diff(prev_f, new_f)
            if diff_sz > 0:
                click_effects.append((x, y, diff_sz))

            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"click_diff_({y},{x})"
            if obs.state.name == "GAME_OVER":
                obs = reset(env)
                used += 1
            if obs.state.name == "WIN":
                return best, name, used

    # Phase 2: Focus on areas with high effect
    if click_effects:
        # Sort by effect size descending
        click_effects.sort(key=lambda t: t[2], reverse=True)

        # Re-click around high-effect areas with finer resolution
        for cx, cy, _ in click_effects[:10]:
            for dy in range(-4, 5, 2):
                for dx in range(-4, 5, 2):
                    nx, ny = max(0, min(63, cx + dx)), max(0, min(63, cy + dy))
                    if used >= budget:
                        return best, name, used
                    obs = click(env, nx, ny)
                    used += 1
                    if obs.levels_completed > best:
                        best = obs.levels_completed
                        name = f"click_diff_refine_({ny},{nx})"
                    if obs.state.name == "GAME_OVER":
                        obs = reset(env)
                        used += 1
                    if obs.state.name == "WIN":
                        return best, name, used

    return best, name, used


def strat_spiral_move(env: Any, dir_to_act: dict[str, int], budget: int = 200) -> tuple[int, str, int]:
    """Spiral outward movement pattern: right, down, left, up with increasing lengths."""
    obs = reset(env)
    used, best, name = 1, 0, ""

    spiral_dirs = ["RIGHT", "DOWN", "LEFT", "UP"]
    step_len = 1
    steps_at_len = 0

    for i in range(budget - 1):
        if obs.state.name == "WIN":
            break
        if obs.state.name == "GAME_OVER":
            obs = reset(env)
            used += 1
            step_len = 1
            steps_at_len = 0
            continue

        dir_idx = (i // step_len) % 4
        direction = spiral_dirs[dir_idx]
        aid = dir_to_act.get(direction)

        if aid is None:
            # Skip if this direction isn't available
            aids = list(dir_to_act.values())
            if aids:
                aid = aids[i % len(aids)]
            else:
                break

        obs = act(env, aid)
        used += 1
        if obs.levels_completed > best:
            best = obs.levels_completed
            name = f"spiral"

        steps_at_len += 1
        if steps_at_len >= step_len * 2:
            step_len += 1
            steps_at_len = 0

    return best, name, used


def strat_all_combos(env: Any, dir_actions: list[int], budget: int = 500) -> tuple[int, str, int]:
    """Try all length-3 action sequences, repeat the best one."""
    obs = reset(env)
    used, best, name = 1, 0, ""

    if len(dir_actions) < 2:
        return best, name, used

    best_seq: list[int] = []
    best_seq_levels = 0

    # Try 2 and 3-length combos
    for combo_len in [2, 3]:
        for combo in itertools.product(dir_actions, repeat=combo_len):
            if used >= budget // 2:
                break
            obs = reset(env)
            used += 1
            seq_best = 0
            for _ in range(15):  # repeat combo 15 times
                for aid in combo:
                    if used >= budget // 2 or obs.state.name in ("WIN", "GAME_OVER"):
                        break
                    obs = act(env, aid)
                    used += 1
                    if obs.levels_completed > seq_best:
                        seq_best = obs.levels_completed
                if obs.state.name in ("WIN", "GAME_OVER"):
                    break
            if seq_best > best_seq_levels:
                best_seq_levels = seq_best
                best_seq = list(combo)
            if seq_best > best:
                best = seq_best
                name = f"combo_{'_'.join(str(a) for a in combo)}"

    # Repeat best sequence with remaining budget
    if best_seq and used < budget:
        obs = reset(env)
        used += 1
        while used < budget:
            for aid in best_seq:
                if used >= budget or obs.state.name == "WIN":
                    break
                if obs.state.name == "GAME_OVER":
                    obs = reset(env)
                    used += 1
                    continue
                obs = act(env, aid)
                used += 1
                if obs.levels_completed > best:
                    best = obs.levels_completed
                    name = f"combo_{'_'.join(str(a) for a in best_seq)}_repeat"
            if obs.state.name == "WIN":
                break

    return best, name, used


def strat_click_all_colors(env: Any, budget: int = 500) -> tuple[int, str, int]:
    """Click center of mass of each non-background color, cycling through levels."""
    obs = reset(env)
    used, best, name = 1, 0, ""

    for iteration in range(budget // 16):
        if used >= budget or obs.state.name == "WIN":
            break
        if obs.state.name == "GAME_OVER":
            obs = reset(env)
            used += 1
            continue

        frame = get_frame(obs)
        unique_colors = [c for c in np.unique(frame).tolist() if c != 0]

        for color in unique_colors:
            if used >= budget or obs.state.name in ("WIN", "GAME_OVER"):
                break
            positions = np.argwhere(frame == color)
            if len(positions) == 0:
                continue
            center = positions.mean(axis=0)
            cy = max(0, min(63, int(round(center[0]))))
            cx = max(0, min(63, int(round(center[1]))))
            obs = click(env, cx, cy)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"click_all_c{color}"

        if obs.state.name == "GAME_OVER":
            obs = reset(env)
            used += 1

    return best, name, used


def strat_graph_explore(env: Any, avail: list[int], budget: int = 500) -> tuple[int, str, int]:
    """Graph-based exploration: track state hashes, systematically explore."""
    obs = reset(env)
    used, best, name = 1, 0, ""

    state_graph: dict[str, dict[int, str]] = {}
    visit_count: dict[str, int] = defaultdict(int)
    tried: dict[str, set[int]] = defaultdict(set)

    has_click = 6 in avail
    dir_actions = [a for a in avail if a not in (6, 7, 8)]
    grid_coords = [(x, y) for y in range(4, 64, 16) for x in range(4, 64, 16)]
    grid_idx: dict[str, int] = defaultdict(int)

    cur_hash = frame_hash(get_frame(obs))
    visit_count[cur_hash] += 1
    prev_hash: str | None = None
    prev_action: int | None = None

    for step in range(budget - 1):
        if obs.state.name == "WIN":
            break
        if obs.state.name == "GAME_OVER":
            obs = reset(env)
            used += 1
            cur_hash = frame_hash(get_frame(obs))
            visit_count[cur_hash] += 1
            prev_hash = None
            prev_action = None
            continue

        if obs.levels_completed > best:
            best = obs.levels_completed
            name = "graph_explore"
            # Clear graph on new level
            state_graph.clear()
            visit_count.clear()
            tried.clear()
            grid_idx.clear()

        # Record previous transition
        if prev_hash is not None and prev_action is not None:
            if prev_hash not in state_graph:
                state_graph[prev_hash] = {}
            state_graph[prev_hash][prev_action] = cur_hash

        # Choose action
        chosen_aid = None
        chosen_coords = None

        # Priority 1: untried simple actions
        for aid in dir_actions:
            if aid not in tried[cur_hash]:
                chosen_aid = aid
                break

        # Priority 2: untried grid clicks
        if chosen_aid is None and has_click:
            gi = grid_idx[cur_hash]
            if gi < len(grid_coords):
                chosen_aid = 6
                chosen_coords = grid_coords[gi]
                grid_idx[cur_hash] = gi + 1

        # Priority 3: go to least-visited neighbor
        if chosen_aid is None:
            neighbors = state_graph.get(cur_hash, {})
            if neighbors:
                min_visits = float("inf")
                for ak, nh in neighbors.items():
                    v = visit_count[nh]
                    if v < min_visits:
                        min_visits = v
                        if ak < 1000:
                            chosen_aid = ak
                        else:
                            chosen_aid = 6
                            coord = ak - 1000
                            chosen_coords = (coord % 64, coord // 64)

        # Fallback: random
        if chosen_aid is None:
            usable = [a for a in avail if a not in (7, 8)]
            if usable:
                chosen_aid = usable[np.random.randint(len(usable))]
            else:
                break

        # Execute
        action_key = chosen_aid
        if chosen_aid == 6:
            if chosen_coords is None:
                chosen_coords = (np.random.randint(64), np.random.randint(64))
            action_key = 1000 + chosen_coords[1] * 64 + chosen_coords[0]
            obs = click(env, chosen_coords[0], chosen_coords[1])
        else:
            obs = act(env, chosen_aid)

        used += 1
        tried[cur_hash].add(action_key)
        prev_hash = cur_hash
        prev_action = action_key

        cur_hash = frame_hash(get_frame(obs))
        visit_count[cur_hash] += 1

        if obs.levels_completed > best:
            best = obs.levels_completed
            name = "graph_explore"

    return best, name, used


def strat_move_then_click_grid(env: Any, dir_actions: list[int], budget: int = 400) -> tuple[int, str, int]:
    """After each movement, click a grid of points on current frame."""
    obs = reset(env)
    used, best, name = 1, 0, ""

    for step in range(budget):
        if used >= budget or obs.state.name == "WIN":
            break
        if obs.state.name == "GAME_OVER":
            obs = reset(env)
            used += 1
            continue

        # Move
        if dir_actions:
            aid = dir_actions[step % len(dir_actions)]
            obs = act(env, aid)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"move_click_grid_A{aid}"
            if obs.state.name in ("WIN", "GAME_OVER"):
                continue

        # Click 4 points on current frame
        for gx, gy in [(16, 16), (48, 16), (16, 48), (48, 48)]:
            if used >= budget or obs.state.name in ("WIN", "GAME_OVER"):
                break
            obs = click(env, gx, gy)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"move_click_grid"

    return best, name, used


# ─── Ensemble solver ────────────────────────────────────────────────

class EnsembleAgent:
    """Meta-agent that tries multiple strategies and picks the best."""

    def __init__(self, total_budget: int = 5000, enable_logging: bool = False) -> None:
        self.total_budget = total_budget
        self.enable_logging = enable_logging
        self._logger: GameLogger | None = None

    def solve_game(self, env: Any, game_id: str = "") -> dict:
        """Solve a single game by trying multiple strategies."""
        if self.enable_logging:
            self._logger = GameLogger(game_id=game_id, agent_name="ensemble")

        obs = env.observation_space
        if obs is None:
            return {"game_id": game_id, "error": "No observation",
                    "levels_completed": 0, "win_levels": 0, "cleared": False}

        avail = sorted(obs.available_actions)
        win_levels = obs.win_levels
        dir_actions = [a for a in avail if a not in (6, 7, 8)]
        has_click = 6 in avail

        # Quick player/direction detection
        player_color = None
        dir_to_act: dict[str, int] = {}
        if dir_actions:
            try:
                player_color, dir_to_act = detect_player_and_dirs(env, dir_actions, trials=2)
            except Exception:
                pass

        frame0 = get_frame(reset(env))
        target_colors = [c for c in np.unique(frame0).tolist() if c != 0 and c != player_color]

        best_levels = 0
        best_strategy = ""
        total_actions = 0
        strategies_tried: list[dict] = []

        def try_strat(fn, *args, label: str = "", **kwargs) -> bool:
            nonlocal best_levels, best_strategy, total_actions
            if total_actions >= self.total_budget:
                return False
            try:
                levels, sname, used = fn(env, *args, **kwargs)
            except Exception:
                return False
            total_actions += used
            strat_info = {"name": label or sname, "levels": levels, "actions": used}
            strategies_tried.append(strat_info)
            if self._logger is not None:
                self._logger.log_event("strategy_attempt", strat_info)
            if levels > best_levels:
                best_levels = levels
                best_strategy = sname or label
                if self._logger is not None:
                    self._logger.log_event("strategy_switch", {"strategy": best_strategy, "levels": best_levels})
            return levels > 0

        # === Strategy 1: Sustained directions ===
        for aid in dir_actions:
            if try_strat(strat_sustained, aid, label=f"sustained_A{aid}", steps=80):
                break

        # === Strategy 2: Zigzag pairs ===
        if best_levels == 0 and len(dir_actions) >= 2:
            for length in [1, 2, 3, 5, 7, 10]:
                if best_levels > 0:
                    break
                for a1, a2 in itertools.permutations(dir_actions, 2):
                    if total_actions >= self.total_budget or best_levels > 0:
                        break
                    try_strat(strat_zigzag, a1, a2, length, label=f"zig{length}_A{a1}A{a2}", cycles=25)

        # === Strategy 3: Click rare colors ===
        if best_levels == 0 and has_click:
            remaining = min(500, self.total_budget - total_actions)
            try_strat(strat_click_rare, label="click_rare", budget=remaining)

        # === Strategy 4: Move + click ===
        if best_levels == 0 and has_click and dir_actions:
            for aid in dir_actions:
                if total_actions >= self.total_budget or best_levels > 0:
                    break
                remaining = min(200, self.total_budget - total_actions)
                try_strat(strat_move_click, aid, label=f"moveclick_A{aid}", budget=remaining)

        # === Strategy 5: Navigate to target colors ===
        if best_levels == 0 and dir_to_act and player_color is not None:
            for tc in target_colors:
                if total_actions >= self.total_budget or best_levels > 0:
                    break
                remaining = min(105, self.total_budget - total_actions)
                try_strat(strat_navigate, player_color, dir_to_act, tc,
                          label=f"nav_c{tc}", budget=remaining)

        # === Strategy 6: BFS explore ===
        if best_levels == 0 and dir_actions:
            remaining = min(300, self.total_budget - total_actions)
            try_strat(strat_bfs_explore, dir_actions, label="bfs_explore", budget=remaining)

        # === Strategy 7: Wall avoidance movement ===
        if best_levels == 0 and dir_actions:
            remaining = min(300, self.total_budget - total_actions)
            try_strat(strat_wall_avoid, dir_actions, label="wall_avoid", budget=remaining)

        # === Strategy 8: Pattern repeat ===
        if best_levels == 0:
            remaining = min(400, self.total_budget - total_actions)
            try_strat(strat_pattern_repeat, avail, label="pattern_repeat", budget=remaining)

        # === Strategy 9: Spiral movement ===
        if best_levels == 0 and dir_to_act:
            remaining = min(200, self.total_budget - total_actions)
            try_strat(strat_spiral_move, dir_to_act, label="spiral", budget=remaining)

        # === Strategy 10: Click diff tracking ===
        if best_levels == 0 and has_click:
            remaining = min(400, self.total_budget - total_actions)
            try_strat(strat_click_diff_track, label="click_diff", budget=remaining)

        # === Strategy 11: Click all color centers ===
        if best_levels == 0 and has_click:
            remaining = min(500, self.total_budget - total_actions)
            try_strat(strat_click_all_colors, label="click_all_colors", budget=remaining)

        # === Strategy 12: All combos (short sequences) ===
        if best_levels == 0 and len(dir_actions) >= 2:
            remaining = min(500, self.total_budget - total_actions)
            try_strat(strat_all_combos, dir_actions, label="all_combos", budget=remaining)

        # === Strategy 13: Graph-based systematic explore ===
        if best_levels == 0:
            remaining = min(500, self.total_budget - total_actions)
            try_strat(strat_graph_explore, avail, label="graph_explore", budget=remaining)

        # === Strategy 14: Move then click grid ===
        if best_levels == 0 and has_click and dir_actions:
            remaining = min(400, self.total_budget - total_actions)
            try_strat(strat_move_then_click_grid, dir_actions, label="move_click_grid", budget=remaining)

        # === Strategy 15: Raster scan (last resort) ===
        if best_levels == 0 and has_click:
            remaining = min(4200, self.total_budget - total_actions)
            try_strat(strat_raster, label="raster", step_size=1, budget=remaining)

        if self._logger is not None:
            self._logger.log_summary(
                total_actions=total_actions,
                levels_cleared=best_levels,
                elapsed=0.0,
                extra={"strategy": best_strategy, "strategies_tried": len(strategies_tried)},
            )

        return {
            "game_id": game_id,
            "levels_completed": best_levels,
            "win_levels": win_levels,
            "actions": total_actions,
            "strategy": best_strategy,
            "cleared": best_levels > 0,
            "strategies_tried": strategies_tried,
        }
