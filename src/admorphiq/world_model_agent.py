"""Object-centric ONLINE world-model agent for ARC-AGI-3 (R28 first increment).

The R27 held-out transfer test measured 0% transfer for behaviour cloning: a
policy trained on public gold memorises the 25 preview games and clears 0 of 7
unseen holdout games. The leaderboard is 110 PRIVATE unseen games, so the spine
must LEARN AT TEST TIME, per game, from the agent's OWN interaction — nothing
baked in from public gold. This module is the first bounded increment of that
general path (see ``docs/r28_world_model_agent.md``).

Four stages, each a separately-testable pure function/class:

1. **Perception → objects** (:func:`segment_objects`) — 4-connected colour
   components of the canonical frame layer, game-agnostic.
2. **Online world model** (:class:`EffectModel`) — built fresh per game from the
   agent's probes: the player's per-action pixel shift (``move_map``), per-action
   change probability, per-cell click responsiveness, and the colour signature
   that correlated with past level completions. Compact ABSTRACT state, not a raw
   64×64 predictor.
3. **Goal inference** (:func:`infer_goal`) — navigate / interact / explore from
   the model + observation, preferring a completion-correlated target colour.
4. **Search-based planning** (:func:`plan_navigation`, :func:`plan_interaction`)
   — shortest-path BFS through the learned dynamics toward the goal (short
   sequences, because the metric squares efficiency).

The agent reads ONLY the official observation (``.frame``, ``.state``,
``.available_actions``, ``.levels_completed``). No game-id / game-title
branching, no game-internal / sprite-tag reads — so it transfers to the private
test set.

It reuses the repo's proven perception primitives rather than reinventing them:
``connected_components`` and the navigation grid helpers from
:mod:`admorphiq.general_agent`, and
:class:`admorphiq.perception.frame_analyzer.FrameAnalyzer` for per-action object
effect measurement.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from .general_agent import (
    _EXPLORE_MAX_CLUSTERS,
    _MAX_PLAYER_SIZE,
    _MIN_GOAL_SIZE,
    _MOVE_ACTION_IDS,
    _avail_ids,
    _state_name,
    _step_cell_size,
    _unit,
    canonical_layer,
    connected_components,
    floor_colors_from_probes,
    frame_to_cells,
    grid_bfs,
    infer_direction_map,
    pick_goal_cell,
    player_centroid,
)
from .perception.frame_analyzer import FrameAnalyzer

# ── Tunables ─────────────────────────────────────────────────────────────────

# Max actions spent probing per level. Probe actions count against the squared
# efficiency ratio (human L1 baselines are ~16-42), so the budget is tight.
PROBE_BUDGET = 20
# Coarse ACTION6 probe lattice stride (px): clicks scattered on a regular grid so
# a responsive cell anywhere on the board is eventually hit during discovery.
PROBE_GRID_STRIDE = 16
# A learned player shift this far (px) from where the model predicted the player
# would land counts as a model SURPRISE → replan from the live frame.
SURPRISE_PX = 4.0
# Max actions a committed navigation plan may run WITHOUT a level-up before it is
# abandoned for greedy interaction. The metric gives no partial credit, so a
# navigation plan that has not cleared the level in far more than the human
# budget is the wrong model — keep it tight (navigation clears fast or never).
EXECUTE_BAIL = 50
# Bounded probe buffer: the direction map is recomputed from the most recent
# movement probes, so the buffer is capped to keep ``observe`` O(1) per call.
_MOVE_PROBE_CAP = 40

_PHASE_PROBE = "probe"
_PHASE_EXECUTE = "execute"
_PHASE_INTERACT = "interact"


# ── Stage (a): perception → objects ──────────────────────────────────────────


def segment_objects(layer: np.ndarray, background: int | None = None) -> list[dict]:
    """Segment a frame layer into game-agnostic objects (colour components).

    Thin reuse wrapper over :func:`admorphiq.general_agent.connected_components`
    (the repo's shared object-extraction primitive). Returns one dict per
    4-connected same-colour component, excluding the background, with keys
    ``color``, ``size``, ``cx``, ``cy``, ``cells``.
    """
    return connected_components(layer, background)


# ── Stage (b): online world model ────────────────────────────────────────────


@dataclass
class ActionStat:
    """Online change statistics for one action key (a simple-action id, or 6)."""

    tried: int = 0
    changed: int = 0
    total_pixels: int = 0
    changed_colors: Counter = field(default_factory=Counter)


class EffectModel:
    """Per-game transition model learned ONLINE from the agent's own probes.

    Rebuilt fresh for each game (no public gold), so its competence transfers to
    unseen games by construction. It is a compact ABSTRACT model — entity
    translations + per-action change statistics — that the planner simulates,
    not a raw-frame predictor.
    """

    def __init__(self) -> None:
        self.background: int | None = None
        self.player_color: int | None = None
        # action id -> (dx, dy) player pixel shift (col, row).
        self.move_map: dict[int, tuple[int, int]] = {}
        # action key -> ActionStat (key is a simple-action id, or 6 for ACTION6).
        self.action_stats: dict[int, ActionStat] = {}
        # Bounded movement-probe buffer feeding infer_direction_map.
        self._move_probes: list[dict] = []
        # Per-cell ACTION6 responsiveness observations.
        self.click_obs: list[dict] = []
        # Colour signatures recorded at each observed level completion.
        self.completion_sigs: list[dict] = []

    def set_background(self, layer: np.ndarray) -> None:
        """Latch the background (most-frequent colour) from the first frame."""
        if self.background is None and layer.size:
            vals, counts = np.unique(layer, return_counts=True)
            self.background = int(vals[int(counts.argmax())])

    def observe(
        self,
        action_id: int,
        coord: tuple[int, int] | None,
        before: np.ndarray,
        after: np.ndarray,
        level_up: bool = False,
    ) -> dict:
        """Fold one (action, before, after) transition into the model.

        Single online-update entry point — called for discovery probes AND real
        plan moves, so the model keeps improving across the whole game. Reuses
        :meth:`FrameAnalyzer.analyze_action` for the per-colour diff; updates the
        change statistics, the player/direction map (movement actions), the
        per-cell click responsiveness (ACTION6), and the completion signature
        when ``level_up`` is set. Returns the diff result for inspection.
        """
        bg = self.background if self.background is not None else 0
        analyzer = FrameAnalyzer()
        res = analyzer.analyze_action(before, after, action_id, coord)
        changed = bool(res["frame_changed"])

        stat = self.action_stats.setdefault(action_id, ActionStat())
        stat.tried += 1
        if changed:
            stat.changed += 1
            stat.total_pixels += int(res["changed_pixels"])
            for color in _changed_colors(before, after):
                stat.changed_colors[color] += 1

        if action_id in _MOVE_ACTION_IDS:
            self._move_probes.append({"aid": action_id, "before": before, "after": after})
            if len(self._move_probes) > _MOVE_PROBE_CAP:
                self._move_probes = self._move_probes[-_MOVE_PROBE_CAP:]
            self.move_map, player = infer_direction_map(self._move_probes, bg)
            if player is not None:
                self.player_color = player["color"]

        if coord is not None:
            self.click_obs.append(
                {"x": coord[0], "y": coord[1], "changed": changed, "pixels": int(res["changed_pixels"])}
            )

        if level_up:
            self.completion_sigs.append(
                {
                    "action_id": action_id,
                    "coord": coord,
                    "colors": _changed_colors(before, after),
                }
            )
        return res

    def change_prob(self, key: int) -> float:
        """Laplace-smoothed ``P(frame changes | action key)`` (0.5 if untried)."""
        stat = self.action_stats.get(key)
        if stat is None or stat.tried == 0:
            return 0.5
        return (stat.changed + 1) / (stat.tried + 2)

    def predict_player_shift(self, action_id: int) -> tuple[int, int] | None:
        """One-step prediction: the player's (dx, dy) pixel shift, or None."""
        return self.move_map.get(action_id)

    def step_dirs(self, avail: list[int] | None = None) -> dict[int, tuple[int, int]]:
        """Quantise ``move_map`` to unit grid steps ``(d_col, d_row)`` per action.

        When ``avail`` is given, only available actions are included. Zero-vector
        actions are dropped. This is the dynamics the navigation planner expands.
        """
        keys = self.move_map.keys() if avail is None else [a for a in avail if a in self.move_map]
        out: dict[int, tuple[int, int]] = {}
        for aid in keys:
            dx, dy = self.move_map[aid]
            ucol, urow = _unit(dx), _unit(dy)
            if ucol == 0 and urow == 0:
                continue
            out[aid] = (ucol, urow)
        return out

    def responsive_clicks(self) -> list[tuple[int, int]]:
        """Cells where an ACTION6 click was observed to change the frame.

        De-duplicated by (x, y), ordered by the largest observed change first.
        """
        best: dict[tuple[int, int], int] = {}
        for obs in self.click_obs:
            if not obs["changed"]:
                continue
            cell = (obs["x"], obs["y"])
            best[cell] = max(best.get(cell, 0), obs["pixels"])
        return [c for c, _ in sorted(best.items(), key=lambda kv: -kv[1])]

    def completion_target_colors(self) -> set[int]:
        """Colours whose regions changed at past level completions (goal signal)."""
        out: set[int] = set()
        for sig in self.completion_sigs:
            out.update(sig["colors"])
        return out


def _changed_colors(before: np.ndarray, after: np.ndarray) -> set[int]:
    """Set of colour indices that appeared or vanished at any cell on the diff."""
    if before.shape != after.shape:
        return set()
    mask = before != after
    if not mask.any():
        return set()
    vals = set(np.unique(before[mask]).tolist()) | set(np.unique(after[mask]).tolist())
    return {int(v) for v in vals}


# ── Stage (c): goal inference ─────────────────────────────────────────────────


@dataclass
class Goal:
    """Inferred per-level objective. ``kind`` in {navigate, interact, explore}."""

    kind: str
    target_color: int | None = None


def infer_goal(layer: np.ndarray, model: EffectModel) -> Goal:
    """Infer the level objective from the learned model + the current frame.

    Navigation is preferred when a player and a plausible goal region exist;
    otherwise interaction when the model has observed any responsive click or a
    high-change action; otherwise disciplined exploration. A colour that changed
    at a past level completion (``completion_target_colors``) and is present now
    is used as the preferred goal colour over the rarest-colour heuristic.
    """
    bg = model.background if model.background is not None else 0
    present = set(np.unique(layer).tolist()) if layer.size else set()
    target = next(
        (
            c
            for c in model.completion_target_colors()
            if c in present and c != bg and c != model.player_color
        ),
        None,
    )

    if model.player_color is not None and model.move_map:
        cell = _step_cell_size(model.move_map)
        if pick_goal_cell(layer, cell, model.player_color, bg, target_color=target) is not None:
            return Goal("navigate", target)

    responsive = bool(model.responsive_clicks())
    high_change = any(model.change_prob(k) > 0.5 for k in model.action_stats)
    if responsive or high_change:
        return Goal("interact", target)
    return Goal("explore", target)


# ── Stage (d): search-based planning ──────────────────────────────────────────


def plan_navigation(layer: np.ndarray, model: EffectModel, goal: Goal) -> list[int]:
    """Shortest action-id path from the player to the goal, in the learned model.

    Builds the walkable grid (``frame_to_cells`` with the floor colours the
    player was seen standing on) and runs ``grid_bfs`` over the learned unit
    ``step_dirs``. Returns ``[]`` when no player, no learned directions, no goal,
    or the goal is unreachable. The expanded transition IS the learned per-action
    shift, so this is search inside the world model — and BFS returns the
    shortest sequence, which the squared-efficiency metric rewards.
    """
    if model.player_color is None or not model.move_map:
        return []
    bg = model.background if model.background is not None else 0
    cell = _step_cell_size(model.move_map)
    step_dirs = model.step_dirs()
    if not step_dirs:
        return []

    player_comps = [
        c
        for c in connected_components(layer, bg)
        if c["color"] == model.player_color and c["size"] <= _MAX_PLAYER_SIZE
    ]
    if not player_comps:
        return []
    player = max(player_comps, key=lambda c: c["size"])

    goal_cell = pick_goal_cell(layer, cell, model.player_color, bg, target_color=goal.target_color)
    if goal_cell is None:
        return []

    floor = floor_colors_from_probes(model._move_probes, model.player_color, bg)
    walkable, _ = frame_to_cells(layer, cell, model.player_color, bg, floor_colors=floor)
    if walkable.size == 0:
        return []
    gh, gw = walkable.shape
    start = (
        max(0, min(gh - 1, int(round(player["cy"])) // cell)),
        max(0, min(gw - 1, int(round(player["cx"])) // cell)),
    )
    if 0 <= goal_cell[0] < gh and 0 <= goal_cell[1] < gw:
        # The goal marker is a coloured object → force its cell passable so BFS
        # can terminate there.
        walkable[goal_cell[0], goal_cell[1]] = True
    return grid_bfs(walkable, start, goal_cell, step_dirs) or []


def plan_interaction(layer: np.ndarray, model: EffectModel) -> list[tuple]:
    """Ordered interaction candidates, most-promising first (greedy over effect).

    Descriptors are ``("c", x, y)`` for an ACTION6 click and ``("m", aid)`` for a
    simple action. Order: cells observed responsive → rare-cluster centroids
    (plausible-but-untried click targets) → frame-changing simple actions by
    descending change probability. Consumed one per call by the agent, so every
    emitted action feeds back into :meth:`EffectModel.observe`.
    """
    bg = model.background if model.background is not None else 0
    out: list[tuple] = []
    seen: set[tuple] = set()

    def _add(desc: tuple) -> None:
        if desc not in seen:
            seen.add(desc)
            out.append(desc)

    for x, y in model.responsive_clicks():
        _add(("c", int(x), int(y)))

    comps = [c for c in connected_components(layer, bg) if c["size"] >= _MIN_GOAL_SIZE]
    for c in sorted(comps, key=lambda c: -c["size"])[:_EXPLORE_MAX_CLUSTERS]:
        _add(("c", int(round(c["cx"])), int(round(c["cy"]))))

    move_keys = [k for k in model.action_stats if k in _MOVE_ACTION_IDS]
    for aid in sorted(move_keys, key=lambda a: -model.change_prob(a)):
        if model.change_prob(aid) > 0.5:
            _add(("m", int(aid)))
    return out


# ── Agent FSM ─────────────────────────────────────────────────────────────────


class WorldModelAgent:
    """Stateful object-centric online world-model agent, one action per call.

    Harness contract (shared with ``GeneralAgent`` / ``BCPolicyAgent`` and
    ``scripts/score_efficiency.py``): ``is_done(frames, latest_frame)`` and
    ``choose_action(frames, latest_frame)`` over the raw arcengine observation,
    plus ``choose_action_with_data`` for the official base. Owns no env.

    Control knowledge (``move_map``, ``player_color``) is GAME-scope and persists
    across levels (controls are level-invariant; only the layout changes); plan /
    goal / probe state is per-level.
    """

    MAX_ACTIONS = 600

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._action_count = 0
        self._levels_completed = 0
        self.model = EffectModel()
        self.goal: Goal | None = None
        self._reset_level()

    def _reset_level(self) -> None:
        """Clear per-level plan/goal/probe state (called on level-up)."""
        self._phase = _PHASE_PROBE
        self._level_base = self._action_count
        self._probe_queue: list[tuple] | None = None
        self._pending: dict | None = None
        self._plan: list[int] = []
        self._plan_commit = self._action_count
        self._pred_player: tuple[float, float] | None = None
        self._interact_queue: list[tuple] = []
        self._interact_cursor = 0

    # ── harness contract ──────────────────────────────────────────────────────

    def is_done(self, frames: list, latest_frame) -> bool:
        """Stop on WIN (the biggest efficiency lever) or when out of budget."""
        if _state_name(latest_frame) == "WIN":
            return True
        return self._action_count >= self.MAX_ACTIONS

    def choose_action(self, frames: list, latest_frame):
        """Emit the next action for the current observation."""
        from arcengine import GameAction

        layer = canonical_layer(getattr(latest_frame, "frame", latest_frame))
        avail = _avail_ids(latest_frame)
        state = _state_name(latest_frame)
        self.model.set_background(layer)

        # Credit the action issued last call (its "after" is the current frame)
        # into the GAME-scope model BEFORE any per-level reset.
        lvl = int(getattr(latest_frame, "levels_completed", 0) or 0)
        leveled = lvl > self._levels_completed
        if self._pending is not None and layer.size:
            p = self._pending
            if p["before"].shape == layer.shape:
                self.model.observe(p["action_id"], p["coord"], p["before"], layer, level_up=leveled)
            self._pending = None
        if leveled:
            self._levels_completed = lvl
            self._reset_level()

        if state == "GAME_OVER" or layer.size == 0 or not avail:
            self._pending = None
            return self._emit(GameAction.RESET)

        if self._phase == _PHASE_PROBE:
            return self._probe_step(layer, avail, latest_frame)
        if self._phase == _PHASE_EXECUTE:
            return self._execute_step(layer, avail, latest_frame)
        return self._interact_step(layer, avail, latest_frame)

    def choose_action_with_data(self, frames: list, latest_frame):
        """Official-base wrapper: return ``(action, data)`` with ACTION6 x/y."""
        action = self.choose_action(frames, latest_frame)
        data = getattr(action, "action_data", None)
        if data is not None:
            return action, {"x": int(data.x), "y": int(data.y)}
        return action, None

    # ── probe phase ───────────────────────────────────────────────────────────

    def _build_probe_queue(self, avail: list[int]) -> list[tuple]:
        """Each available move once, then a coarse ACTION6 lattice (if 6 avail)."""
        queue: list[tuple] = [("m", a) for a in _MOVE_ACTION_IDS if a in avail]
        if 6 in avail:
            half = PROBE_GRID_STRIDE // 2
            for y in range(half, 64, PROBE_GRID_STRIDE):
                for x in range(half, 64, PROBE_GRID_STRIDE):
                    queue.append(("c", x, y))
        return queue

    def _probe_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        if self._probe_queue is None:
            self._probe_queue = self._build_probe_queue(avail)
        spent = self._action_count - self._level_base
        if spent >= PROBE_BUDGET or not self._probe_queue:
            return self._finish_probe(layer, avail, latest_frame)
        return self._emit_desc(self._probe_queue.pop(0), layer)

    def _finish_probe(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Infer the goal, build a plan, and dispatch the post-probe phase."""
        self.goal = infer_goal(layer, self.model)
        self._plan_commit = self._action_count
        if self.goal.kind == "navigate":
            plan = plan_navigation(layer, self.model, self.goal)
            if plan:
                self._plan = list(plan)
                self._pred_player = None
                self._phase = _PHASE_EXECUTE
                return self._execute_step(layer, avail, latest_frame)
        self._interact_queue = plan_interaction(layer, self.model)
        self._interact_cursor = 0
        self._phase = _PHASE_INTERACT
        return self._interact_step(layer, avail, latest_frame)

    # ── execute (navigation) phase ────────────────────────────────────────────

    def _execute_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        from arcengine import GameAction

        bg = self.model.background if self.model.background is not None else 0

        # Surprise check: the model predicted where the player would land last
        # step; a large mismatch means the learned dynamics are wrong here.
        if self._pred_player is not None and self.model.player_color is not None:
            cur = player_centroid(layer, self.model.player_color, bg)
            if cur is not None:
                dist = (
                    (cur[0] - self._pred_player[0]) ** 2 + (cur[1] - self._pred_player[1]) ** 2
                ) ** 0.5
                if dist > SURPRISE_PX:
                    self._plan = plan_navigation(layer, self.model, self.goal or infer_goal(layer, self.model))

        # Bail-fast: a navigation plan that has not cleared the level in far more
        # than the human budget is the wrong model — switch to interaction.
        if self._action_count - self._plan_commit > EXECUTE_BAIL:
            return self._switch_to_interact(layer, avail, latest_frame)

        if not self._plan:
            self._plan = plan_navigation(layer, self.model, self.goal or infer_goal(layer, self.model))
            if not self._plan:
                return self._switch_to_interact(layer, avail, latest_frame)

        aid = self._plan.pop(0)
        if aid not in avail:
            self._plan = []
            return self._switch_to_interact(layer, avail, latest_frame)

        shift = self.model.predict_player_shift(aid)
        cur = (
            player_centroid(layer, self.model.player_color, bg)
            if self.model.player_color is not None
            else None
        )
        self._pred_player = (cur[0] + shift[0], cur[1] + shift[1]) if (shift and cur) else None
        self._pending = {"action_id": aid, "coord": None, "before": layer.copy()}
        return self._emit(GameAction.from_id(aid))

    def _switch_to_interact(self, layer: np.ndarray, avail: list[int], latest_frame):
        self._interact_queue = plan_interaction(layer, self.model)
        self._interact_cursor = 0
        self._plan_commit = self._action_count
        self._phase = _PHASE_INTERACT
        return self._interact_step(layer, avail, latest_frame)

    # ── interact (greedy) phase ───────────────────────────────────────────────

    def _interact_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        from arcengine import GameAction

        live = self._live_candidates(avail)
        if not live:
            return self._emit(GameAction.RESET)
        desc = live[self._interact_cursor % len(live)]
        self._interact_cursor += 1
        return self._emit_desc(desc, layer)

    def _live_candidates(self, avail: list[int]) -> list[tuple]:
        """Currently-usable interaction descriptors (availability-filtered).

        Rebuilds from the model's queue (clicks need ACTION6 available; moves
        need their id available); falls back to the raw available simple actions
        so the agent always has something live to try.
        """
        live: list[tuple] = []
        for desc in self._interact_queue:
            if desc[0] == "c" and 6 in avail:
                live.append(desc)
            elif desc[0] == "m" and desc[1] in avail:
                live.append(desc)
        if not live:
            live = [("m", a) for a in avail if a in _MOVE_ACTION_IDS]
        return live

    # ── action emission (records pending so the model keeps learning) ──────────

    def _emit_desc(self, desc: tuple, layer: np.ndarray):
        from arcengine import GameAction

        if desc[0] == "m":
            aid = desc[1]
            self._pending = {"action_id": aid, "coord": None, "before": layer.copy()}
            return self._emit(GameAction.from_id(aid))
        _, x, y = desc
        self._pending = {"action_id": 6, "coord": (int(x), int(y)), "before": layer.copy()}
        return self._emit_click(int(x), int(y))

    def _emit(self, action):
        self._action_count += 1
        return action

    def _emit_click(self, x: int, y: int):
        from arcengine import GameAction

        action = GameAction.ACTION6
        action.set_data({"x": int(max(0, min(63, x))), "y": int(max(0, min(63, y)))})
        self._action_count += 1
        return action
