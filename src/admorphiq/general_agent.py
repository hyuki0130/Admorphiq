"""Efficiency-first general agent: cheap discovery + efficient grid navigation.

This is the first increment of the Milestone-1 architecture
(`docs/sprint_m1_architecture_20260625.md`). The competition metric squares
the human/agent action-efficiency ratio, so the spine is *efficiency*, not
*completion*: a level cleared in a small multiple of the human action count
scores well, brute force in hundreds scores ~0.

Pipeline (per level, driven one action at a time by the harness):

1. **Cheap discovery** (``_PHASE_DISCOVERY``) — probe each available movement
   action (1-5, 7) once; diff the canonical layer before/after; detect the
   *player* as the small connected component that TRANSLATES, and learn the
   action -> (dx, dy) cell-shift map. Bounded to ``DISCOVERY_BUDGET`` actions.
2. **Entity extraction** — connected-components on the canonical layer to find
   the player, obstacle/wall cells (large clusters / background), and a goal
   (a distinct rare cluster).
3. **Efficient nav plan** (``_PHASE_EXECUTE``) — if a player + plausible goal
   are found and the direction map is known, BFS over the GRID CELL state
   (player position, walls blocking) for the SHORTEST path, translate to the
   learned action sequence, and emit those actions. On level-up, re-discover
   and re-plan. When no player/goal is identified, fall back to a disciplined
   cheap-explore (``_PHASE_EXPLORE``).

The agent reads ONLY the official frame observation (``frame``, ``state``,
``available_actions``, ``levels_completed``); no game internals, no
game-title / game-id branching, no hardcoded sequences. It is therefore
general and transfers to the private Kaggle test set.

The grid-abstraction and BFS logic are pure functions (``infer_direction_map``,
``grid_bfs``, ``frame_to_cells`` ...) so they can be unit-tested without an env.
"""

from __future__ import annotations

import random
from collections import Counter, deque

import numpy as np

# ── Tunables ────────────────────────────────────────────────────────────────

# Movement (no-coordinate) actions we probe during discovery, in id order.
_MOVE_ACTION_IDS: tuple[int, ...] = (1, 2, 3, 4, 5, 7)
# Max actions spent on discovery probing per level. Kept small — wasted probe
# actions also hurt the efficiency ratio (human L1 baselines are ~16-42). We
# probe each movement action up to twice (cumulatively): a player wall-bound at
# the start often becomes free to move other directions after the first probe,
# so a second pass recovers directions a single pass misses.
DISCOVERY_BUDGET = 12
_DISCOVERY_PASSES = 2
# A connected component is "small" enough to be a player if it is at most this
# many cells (players are compact sprites, not background fields).
_MAX_PLAYER_SIZE = 64
# A real player sprite is more than a single pixel; size-1 movers are cursor /
# anti-aliasing dots that track the player but give a noisy 1-pixel step.
_MIN_PLAYER_SIZE = 3
# A player colour appears in only a few instances (typically 1). Colours with
# more components than this tile the background / maze and are not the player.
_MAX_PLAYER_INSTANCES = 3
# Minimum component size to be considered a real object (filters single-pixel
# HUD flicker / anti-aliasing).
_MIN_COMPONENT_SIZE = 1
# A goal marker must be at least this large; single-pixel rare colours are
# anti-aliasing / cursor artefacts, not the target.
_MIN_GOAL_SIZE = 3
# Epsilon-greedy exploration rate in the cheap-explore fallback.
_EXPLORE_EPSILON = 0.15
# Consecutive EXECUTE steps with no player-cell change before bailing to
# cheap-explore (the abstract model is too wrong to navigate).
_STUCK_LIMIT = 4


# ── Pure connected-components / entity helpers ───────────────────────────────


def canonical_layer(frame: list | np.ndarray) -> np.ndarray:
    """Return the canonical (top-most) 2-D layer of a multi-layer frame.

    ``frame`` is ``(num_layers, 64, 64)`` int values 0-15. The last layer is
    the canonical render surface (matches the repo's StochasticGoose
    convention). Returns an empty ``(0, 0)`` array when there is no frame.
    """
    arr = np.asarray(frame)
    if arr.size == 0:
        return np.zeros((0, 0), dtype=np.int32)
    if arr.ndim == 3:
        return arr[-1].astype(np.int32)
    if arr.ndim == 2:
        return arr.astype(np.int32)
    return arr.reshape(arr.shape[-2:]).astype(np.int32)


def connected_components(
    layer: np.ndarray, background: int | None = None, min_size: int = _MIN_COMPONENT_SIZE
) -> list[dict]:
    """4-connected components of same-colour cells, excluding the background.

    Returns one dict per component with keys ``color``, ``size``, ``cx``,
    ``cy`` (centroid, column/row), and ``cells`` (set of (row, col)).
    Background defaults to the single most frequent colour.
    """
    if layer.size == 0:
        return []
    if background is None:
        vals, counts = np.unique(layer, return_counts=True)
        background = int(vals[int(counts.argmax())])

    h, w = layer.shape
    visited = np.zeros((h, w), dtype=bool)
    out: list[dict] = []
    for sy in range(h):
        for sx in range(w):
            if visited[sy, sx]:
                continue
            color = int(layer[sy, sx])
            if color == background:
                visited[sy, sx] = True
                continue
            cells: list[tuple[int, int]] = []
            stack = [(sy, sx)]
            while stack:
                y, x = stack.pop()
                if y < 0 or y >= h or x < 0 or x >= w or visited[y, x]:
                    continue
                if int(layer[y, x]) != color:
                    continue
                visited[y, x] = True
                cells.append((y, x))
                stack.extend(((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)))
            if len(cells) < min_size:
                continue
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            out.append(
                {
                    "color": color,
                    "size": len(cells),
                    "cx": sum(xs) / len(xs),
                    "cy": sum(ys) / len(ys),
                    "cells": set(cells),
                }
            )
    return out


def _candidate_shifts(
    before: np.ndarray, after: np.ndarray, background: int
) -> list[tuple[dict, tuple[float, float]]]:
    """All small before-components that translated >= ~1 cell to an after twin.

    Each result is ``(before_component, (dx, dy))``. Unlike a single best
    match this returns every plausible mover, so a 1-pixel cursor cannot
    mask the real (larger, multi-probe-consistent) player — selection across
    probes is left to :func:`infer_direction_map`.
    """
    before_comps = connected_components(before, background)
    # Count components per colour in the BEFORE frame. A colour that tiles the
    # maze (many identical blocks) produces spurious nearest-twin "shifts", so
    # only treat colours with few instances as plausible movers — players are
    # rare-instance sprites, not repeated wall tiles.
    color_count: Counter[int] = Counter(c["color"] for c in before_comps)
    cb = [
        c
        for c in before_comps
        if _MIN_PLAYER_SIZE <= c["size"] <= _MAX_PLAYER_SIZE
        and color_count[c["color"]] <= _MAX_PLAYER_INSTANCES
    ]
    ca = connected_components(after, background)
    by_color: dict[int, list[dict]] = {}
    for c in ca:
        by_color.setdefault(c["color"], []).append(c)

    out: list[tuple[dict, tuple[float, float]]] = []
    for b in cb:
        cands = by_color.get(b["color"], [])
        if not cands:
            continue
        nearest = min(
            cands,
            key=lambda a: (a["cx"] - b["cx"]) ** 2 + (a["cy"] - b["cy"]) ** 2,
        )
        if abs(nearest["size"] - b["size"]) > max(2, b["size"] // 2):
            continue
        dx = nearest["cx"] - b["cx"]
        dy = nearest["cy"] - b["cy"]
        if (dx * dx + dy * dy) ** 0.5 <= 0.99:  # require ~1 cell of movement
            continue
        out.append((b, (dx, dy)))
    return out


def infer_direction_map(
    probes: list[dict], background: int
) -> tuple[dict[int, tuple[int, int]], dict | None]:
    """Learn the action -> (dx, dy) cell-shift map from movement probes.

    ``probes`` is a list of ``{"aid", "before", "after"}`` (frames as 2-D
    arrays). Returns ``(dir_map, player_component)`` where ``dir_map`` maps an
    action id to a quantised step ``(dx, dy)`` in pixels, and
    ``player_component`` is the chosen player.

    Two-pass selection: first tally, per colour, how many *distinct action
    directions* moved a component of that colour and the total shift. The
    player is the colour with the most distinct directions (tie-broken by
    total shift, then by larger size to skip 1-pixel cursor sprites). The
    dir_map is then built only from that player colour's moves — so a tiny
    cursor that happens to translate cannot hijack the mapping.
    """
    # color -> {"dirs": {aid: (rdx, rdy)}, "shift": float, "size": int, "comp": dict}
    tally: dict[int, dict] = {}
    for probe in probes:
        for comp, (dx, dy) in _candidate_shifts(probe["before"], probe["after"], background):
            rdx, rdy = int(round(dx)), int(round(dy))
            if rdx == 0 and rdy == 0:
                continue
            color = comp["color"]
            entry = tally.setdefault(
                color, {"dirs": {}, "shift": 0.0, "size": comp["size"], "comp": comp}
            )
            entry["dirs"][probe["aid"]] = (rdx, rdy)
            entry["shift"] += (rdx * rdx + rdy * rdy) ** 0.5
            entry["size"] = max(entry["size"], comp["size"])
    if not tally:
        return {}, None

    def _rank(item: tuple[int, dict]) -> tuple:
        _, e = item
        return (len(e["dirs"]), e["shift"], e["size"])

    best_color, best = max(tally.items(), key=_rank)
    return dict(best["dirs"]), best["comp"]


def floor_colors_from_probes(
    probes: list[dict], player_color: int, background: int
) -> set[int]:
    """Colours revealed where the player vacated — i.e. the walkable floor.

    For each probe, take the player's cells in the ``before`` frame and read
    what colour occupies those same cells in ``after``. Where the player has
    moved away, the revealed colour is the floor the player stood on. The
    background is always implicitly floor and is excluded from the returned
    set (callers add it separately). The player colour is excluded (the player
    may not have fully vacated a multi-cell footprint).
    """
    floor: set[int] = set()
    for probe in probes:
        before = probe.get("before")
        after = probe.get("after")
        if before is None or after is None or before.shape != after.shape:
            continue
        player_mask = before == player_color
        if not player_mask.any():
            continue
        revealed = after[player_mask]
        for v in np.unique(revealed):
            c = int(v)
            if c not in (player_color, background):
                floor.add(c)
    return floor


def _step_cell_size(dir_map: dict[int, tuple[int, int]]) -> int:
    """Estimate the grid cell size (pixels per move) from the shift vectors.

    Uses the smallest non-zero absolute component of any learned step. Falls
    back to 1 when nothing usable is present.
    """
    mags: list[int] = []
    for dx, dy in dir_map.values():
        for v in (abs(dx), abs(dy)):
            if v > 0:
                mags.append(v)
    if not mags:
        return 1
    return max(1, min(mags))


def frame_to_cells(
    layer: np.ndarray,
    cell: int,
    player_color: int,
    background: int,
    floor_colors: set[int] | None = None,
) -> tuple[np.ndarray, str]:
    """Downsample the pixel layer to a coarse grid, classifying walkability.

    Each ``cell``x``cell`` block becomes one grid cell. A block is a WALL
    (``False`` = blocked) when its dominant colour is a *solid obstacle*: not
    the background, not the player, and not one of the observed ``floor_colors``
    (colours the player was seen standing on during discovery), and the block
    is (near-)uniformly that colour. Background / player / floor / mixed blocks
    are walkable (``True``).

    ``floor_colors`` is the key generalisation lever: in many games the
    walkable floor is itself a non-background colour, so without it almost the
    whole maze is mislabelled as wall. When None, only background + player are
    treated as walkable.

    Returns ``(walkable_grid, mode)``. ``mode`` is ``"grid"`` when the layer
    divided cleanly; informational only.
    """
    if layer.size == 0 or cell <= 0:
        return np.ones((0, 0), dtype=bool), "empty"
    if floor_colors:
        # We observed the actual walkable floor: trust it. The global
        # most-frequent colour is then NOT assumed walkable — on coloured-floor
        # mazes the most-frequent colour is the WALL field, so including it
        # inverts walkability (the ls20-class bug).
        walkable_colors = set(floor_colors) | {player_color}
    else:
        walkable_colors = {background, player_color}
    h, w = layer.shape
    gh, gw = h // cell, w // cell
    if gh == 0 or gw == 0:
        return np.ones((1, 1), dtype=bool), "degenerate"
    walkable = np.ones((gh, gw), dtype=bool)
    for gy in range(gh):
        for gx in range(gw):
            block = layer[gy * cell : (gy + 1) * cell, gx * cell : (gx + 1) * cell]
            vals, counts = np.unique(block, return_counts=True)
            dom = int(vals[int(counts.argmax())])
            dom_frac = counts.max() / block.size
            if dom not in walkable_colors and dom_frac >= 0.75:
                walkable[gy, gx] = False
    return walkable, "grid"


def grid_bfs(
    walkable: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    step_dirs: dict[int, tuple[int, int]],
) -> list[int] | None:
    """Shortest action sequence from ``start`` cell to ``goal`` cell.

    ``walkable`` is a 2-D bool grid (``True`` = passable). ``start``/``goal``
    are ``(row, col)``. ``step_dirs`` maps an action id to a unit grid step
    ``(d_col, d_row)`` (note: x = col, y = row). Moves into blocked or
    out-of-bounds cells are rejected. Returns the list of action ids, or None
    if unreachable.
    """
    gh, gw = walkable.shape
    if gh == 0 or gw == 0:
        return None
    sr, sc = start
    gr, gc = goal
    if not (0 <= sr < gh and 0 <= sc < gw and 0 <= gr < gh and 0 <= gc < gw):
        return None
    if not walkable[gr, gc]:
        return None
    if start == goal:
        return []

    visited = {start}
    queue: deque[tuple[tuple[int, int], list[int]]] = deque([(start, [])])
    while queue:
        (r, c), path = queue.popleft()
        for aid, (dcol, drow) in step_dirs.items():
            nr, nc = r + drow, c + dcol
            if not (0 <= nr < gh and 0 <= nc < gw):
                continue
            if not walkable[nr, nc]:
                continue
            if (nr, nc) in visited:
                continue
            npath = path + [aid]
            if (nr, nc) == goal:
                return npath
            visited.add((nr, nc))
            queue.append(((nr, nc), npath))
    return None


def pick_goal_cell(
    layer: np.ndarray,
    cell: int,
    player_color: int,
    background: int,
) -> tuple[int, int] | None:
    """Choose the most plausible goal grid-cell.

    The goal is the centroid (in grid coordinates) of the rarest non-player,
    non-background colour cluster — distinct rare clusters are usually the
    target / exit. Returns ``(row, col)`` or None when nothing qualifies.
    """
    comps = [
        c
        for c in connected_components(layer, background)
        if c["color"] != player_color and c["size"] >= _MIN_GOAL_SIZE
    ]
    if not comps:
        return None
    # Rarest colour overall (fewest cells of that colour) → most likely target.
    color_area: Counter[int] = Counter()
    for c in comps:
        color_area[c["color"]] += c["size"]
    rare_color = min(color_area, key=lambda k: color_area[k])
    rare_comps = [c for c in comps if c["color"] == rare_color]
    # Largest cluster of the rare colour (the actual goal marker).
    target = max(rare_comps, key=lambda c: c["size"])
    gr = int(round(target["cy"])) // cell
    gc = int(round(target["cx"])) // cell
    gh, gw = layer.shape[0] // cell, layer.shape[1] // cell
    gr = max(0, min(gh - 1, gr))
    gc = max(0, min(gw - 1, gc))
    return (gr, gc)


# ── Agent FSM ────────────────────────────────────────────────────────────────

_PHASE_DISCOVERY = "discovery"
_PHASE_EXECUTE = "execute"
_PHASE_EXPLORE = "explore"


class GeneralAgent:
    """Stateful efficiency-first agent driven one action per call.

    Harness-friendly: exposes ``is_done(frames, latest_frame)`` and
    ``choose_action(frames, latest_frame)`` accepting the raw arcengine
    observation (``.frame``, ``.state``, ``.available_actions``,
    ``.levels_completed``). It owns no env; it only observes the frame the
    harness hands it and emits the next action.
    """

    MAX_ACTIONS = 600

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._action_count = 0
        self._levels_completed = 0
        self._reset_level_state()

    def _reset_level_state(self) -> None:
        """Clear all per-level discovery / plan state (called on level-up)."""
        self._phase = _PHASE_DISCOVERY
        self._probe_idx = 0
        self._probes: list[dict] = []
        self._pending_probe: dict | None = None
        self._dir_map: dict[int, tuple[int, int]] = {}
        self._player_color: int | None = None
        self._background: int | None = None
        # Closed-loop execution bookkeeping.
        self._last_player_cell: tuple[int, int] | None = None
        self._stuck_steps = 0
        # Cheap-explore fallback bookkeeping.
        self._explore_last_sig: tuple = ()
        self._explore_pending: int | None = None
        self._explore_tries: Counter[int] = Counter()
        self._explore_changes: Counter[int] = Counter()
        self._explore_cursor = 0

    # ── official-shaped interface ────────────────────────────────────────────

    def is_done(self, frames: list, latest_frame) -> bool:
        """Stop on WIN (biggest efficiency lever) or when out of budget."""
        if _state_name(latest_frame) == "WIN":
            return True
        return self._action_count >= self.MAX_ACTIONS

    def choose_action(self, frames: list, latest_frame):
        """Emit the next action for the current observation."""
        from arcengine import GameAction

        self._maybe_level_up(latest_frame)

        avail = _avail_ids(latest_frame)
        layer = canonical_layer(getattr(latest_frame, "frame", latest_frame))

        if _state_name(latest_frame) == "GAME_OVER" or layer.size == 0 or not avail:
            return self._emit(GameAction.RESET)

        if self._background is None and layer.size:
            vals, counts = np.unique(layer, return_counts=True)
            self._background = int(vals[int(counts.argmax())])

        if self._phase == _PHASE_DISCOVERY:
            return self._discovery_step(layer, avail, latest_frame)
        if self._phase == _PHASE_EXECUTE:
            return self._execute_step(layer, avail, latest_frame)
        return self._explore_step(layer, avail, latest_frame)

    # ── level-transition handling ────────────────────────────────────────────

    def _maybe_level_up(self, latest_frame) -> None:
        lvl = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if lvl > self._levels_completed:
            self._levels_completed = lvl
            # New level: discard the old plan and re-discover.
            self._reset_level_state()

    # ── discovery phase ──────────────────────────────────────────────────────

    def _discovery_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Probe one movement action; record before/after for the previous one."""
        from arcengine import GameAction

        # Credit the probe issued on the previous call (its "after" is now).
        if self._pending_probe is not None:
            self._pending_probe["after"] = layer
            self._probes.append(self._pending_probe)
            self._pending_probe = None

        move_actions = [a for a in _MOVE_ACTION_IDS if a in avail] * _DISCOVERY_PASSES
        budget_hit = (
            self._probe_idx >= len(move_actions) or self._action_count >= DISCOVERY_BUDGET
        )
        if budget_hit:
            self._finish_discovery(layer, avail)
            # Re-dispatch into whatever phase discovery selected.
            if self._phase == _PHASE_EXECUTE:
                return self._execute_step(layer, avail, latest_frame)
            return self._explore_step(layer, avail, latest_frame)

        aid = move_actions[self._probe_idx]
        self._probe_idx += 1
        self._pending_probe = {"aid": aid, "before": layer}
        return self._emit(GameAction.from_id(aid))

    def _finish_discovery(self, layer: np.ndarray, avail: list[int]) -> None:
        """Build the direction map, then choose the next phase.

        We require a *planable* path to a goal (BFS returns a non-empty action
        list) before committing to the EXECUTE phase. Execution itself is
        closed-loop (re-planned each step), so we do not store the path here.
        """
        bg = self._background if self._background is not None else 0
        self._dir_map, player = infer_direction_map(self._probes, bg)
        if player is not None:
            self._player_color = player["color"]

        plan = self._try_build_plan(layer, avail)
        if plan:
            self._phase = _PHASE_EXECUTE
            self._last_player_cell = None
            self._stuck_steps = 0
        else:
            self._phase = _PHASE_EXPLORE

    def _try_build_plan(self, layer: np.ndarray, avail: list[int]) -> list[int] | None:
        """Grid-BFS a shortest path from player to goal. None if not possible."""
        if not self._dir_map or self._player_color is None:
            return None
        bg = self._background if self._background is not None else 0
        cell = _step_cell_size(self._dir_map)

        # Locate the player component in the CURRENT frame.
        player_comps = [
            c
            for c in connected_components(layer, bg)
            if c["color"] == self._player_color and c["size"] <= _MAX_PLAYER_SIZE
        ]
        if not player_comps:
            return None
        player = max(player_comps, key=lambda c: c["size"])

        goal = pick_goal_cell(layer, cell, self._player_color, bg)
        if goal is None:
            return None

        floor_colors = floor_colors_from_probes(self._probes, self._player_color, bg)
        walkable, _ = frame_to_cells(
            layer, cell, self._player_color, bg, floor_colors=floor_colors
        )
        if walkable.size == 0:
            return None
        gh, gw = walkable.shape
        start = (
            max(0, min(gh - 1, int(round(player["cy"])) // cell)),
            max(0, min(gw - 1, int(round(player["cx"])) // cell)),
        )
        # The goal marker cell may itself be flagged non-walkable (it is a
        # coloured object); force it passable so BFS can terminate there.
        gh, gw = walkable.shape
        if 0 <= goal[0] < gh and 0 <= goal[1] < gw:
            walkable[goal[0], goal[1]] = True

        # Direction map quantised to unit grid steps (one cell per move).
        step_dirs: dict[int, tuple[int, int]] = {}
        for aid in avail:
            if aid not in self._dir_map:
                continue
            dx, dy = self._dir_map[aid]
            ucol = _unit(dx)
            urow = _unit(dy)
            if ucol == 0 and urow == 0:
                continue
            step_dirs[aid] = (ucol, urow)
        if not step_dirs:
            return None

        return grid_bfs(walkable, start, goal, step_dirs)

    # ── execute phase (closed-loop) ──────────────────────────────────────────

    def _execute_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Re-plan from the live frame and emit the first action of the path.

        Closed-loop execution is robust to abstraction errors (wrong cell
        pitch, mislabelled walls): each step re-locates the player and
        re-runs BFS toward the goal, so a blocked or surprising move
        self-corrects on the next call instead of drifting open-loop. A
        stuck-counter bails to cheap-explore when the player stops making
        progress (the abstraction is too wrong to navigate).
        """
        from arcengine import GameAction

        cur_cell = self._current_player_cell(layer)
        if cur_cell is not None and cur_cell == self._last_player_cell:
            self._stuck_steps += 1
        else:
            self._stuck_steps = 0
        self._last_player_cell = cur_cell

        if self._stuck_steps >= _STUCK_LIMIT:
            self._phase = _PHASE_EXPLORE
            return self._explore_step(layer, avail, latest_frame)

        plan = self._try_build_plan(layer, avail)
        if not plan:
            # No path (reached goal cell already, or unreachable) → explore.
            self._phase = _PHASE_EXPLORE
            return self._explore_step(layer, avail, latest_frame)
        aid = plan[0]
        if aid not in avail:
            self._phase = _PHASE_EXPLORE
            return self._explore_step(layer, avail, latest_frame)
        return self._emit(GameAction.from_id(aid))

    def _current_player_cell(self, layer: np.ndarray) -> tuple[int, int] | None:
        """Grid cell of the player in the live frame (for the stuck-counter)."""
        if self._player_color is None or not self._dir_map:
            return None
        bg = self._background if self._background is not None else 0
        cell = _step_cell_size(self._dir_map)
        comps = [
            c
            for c in connected_components(layer, bg)
            if c["color"] == self._player_color and c["size"] <= _MAX_PLAYER_SIZE
        ]
        if not comps:
            return None
        p = max(comps, key=lambda c: c["size"])
        return (int(round(p["cy"])) // cell, int(round(p["cx"])) // cell)

    # ── cheap-explore fallback ───────────────────────────────────────────────

    def _explore_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Disciplined cheap explore: prefer change-producing actions, click rare."""
        from arcengine import GameAction

        sig = layer.tobytes()
        if self._explore_pending is not None and self._explore_pending != 0:
            self._explore_tries[self._explore_pending] += 1
            if sig != self._explore_last_sig:
                self._explore_changes[self._explore_pending] += 1
        self._explore_last_sig = sig
        self._explore_pending = None

        if 6 in avail:
            target = self._rare_centroid(layer)
            if target is not None:
                return self._emit_click(*target)

        simple = [a for a in _MOVE_ACTION_IDS if a in avail]
        if simple:
            choice = self._pick_explore_simple(simple)
            self._explore_pending = choice
            return self._emit(GameAction.from_id(choice))

        if 6 in avail:
            return self._emit_click(32, 32)
        return self._emit(GameAction.RESET)

    def _pick_explore_simple(self, simple: list[int]) -> int:
        under = [a for a in simple if self._explore_tries[a] < 1]
        if under:
            return under[0]
        if self._rng.random() < _EXPLORE_EPSILON:
            return self._rng.choice(simple)
        rates = {a: self._explore_rate(a) for a in simple}
        best = max(rates.values())
        useful = [a for a in simple if rates[a] >= 0.8 * best] if best > 0 else simple
        choice = useful[self._explore_cursor % len(useful)]
        self._explore_cursor += 1
        return choice

    def _explore_rate(self, aid: int) -> float:
        t = self._explore_tries[aid]
        return self._explore_changes[aid] / t if t else 0.0

    def _rare_centroid(self, layer: np.ndarray) -> tuple[int, int] | None:
        if layer.size == 0:
            return None
        bg = self._background if self._background is not None else int(layer[0, 0])
        comps = [c for c in connected_components(layer, bg) if c["color"] != bg]
        if not comps:
            return None
        color_area: Counter[int] = Counter()
        for c in comps:
            color_area[c["color"]] += c["size"]
        rare = min(color_area, key=lambda k: color_area[k])
        rc = [c for c in comps if c["color"] == rare]
        target = max(rc, key=lambda c: c["size"])
        return (int(round(target["cx"])), int(round(target["cy"])))

    # ── action emission ──────────────────────────────────────────────────────

    def _emit(self, action):
        self._action_count += 1
        return action

    def _emit_click(self, x: int, y: int):
        from arcengine import GameAction

        action = GameAction.ACTION6
        action.set_data({"x": int(max(0, min(63, x))), "y": int(max(0, min(63, y)))})
        self._action_count += 1
        return action


# ── small obs-shape helpers ──────────────────────────────────────────────────


def _unit(v: int) -> int:
    return (v > 0) - (v < 0)


def _state_name(frame) -> str:
    state = getattr(frame, "state", None)
    if state is None:
        return "PLAYING"
    return getattr(state, "name", str(state))


def _avail_ids(frame) -> list[int]:
    raw = getattr(frame, "available_actions", None) or []
    out: list[int] = []
    for a in raw:
        aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
        if aid is not None and int(aid) != 0:
            out.append(int(aid))
    return out
