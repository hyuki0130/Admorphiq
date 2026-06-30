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

from .arrangement import (
    learn_selection_modes,
    plan_descend_and_sweep,
)
from .general_agent import (
    _EXPLORE_MAX_CLUSTERS,
    _MAX_PLAYER_SIZE,
    _MIN_GOAL_SIZE,
    _MIN_TRANSLATION_PX,
    _MOVE_ACTION_IDS,
    GeneralAgent,
    _avail_ids,
    _state_name,
    _step_cell_size,
    _unit,
    build_action_sequences,
    canonical_layer,
    connected_components,
    corridor_color_from_probes,
    edge_grid_bfs,
    enumerate_goal_cells,
    floor_colors_from_probes,
    frame_to_cells,
    goal_centroid_px,
    grid_bfs,
    infer_direction_map,
    pick_goal_cell,
    pick_next_probe,
    player_centroid,
    select_explore_action,
)
from .perception.frame_analyzer import FrameAnalyzer

# ── Tunables ─────────────────────────────────────────────────────────────────

# Max actions spent on RECENTERING-AWARE movement discovery per level. A naive
# single sweep mislearns a wall-bound player (only the unblocked directions get a
# vector); recentering re-probes blocked actions after a freeing move, so the cap
# must leave room for those retries. Matches ``GeneralAgent.DISCOVERY_BUDGET``.
MOVE_PROBE_BUDGET = 16
# Total probe budget per level (movement discovery + ACTION6 click probing). The
# click sweep runs from where movement discovery left off up to this cap. Probe
# actions count against the squared-efficiency ratio (human L1 baselines ~16-42),
# but a level NOT cleared scores 0 — so the budget is wide enough to find the
# responsive cells of a click puzzle, while still bounded.
PROBE_BUDGET = 40
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
# Consecutive PLANNED moves that fail to translate the player (the cell ahead
# is a wall the static pixel-walkability heuristic mislabelled as open) before
# the navigation plan is abandoned for interaction. Each blocked move is first
# fed back as a learned wall cell and the path is re-planned around it; only a
# genuinely boxed-in player (no alternate route after this many learned blocks)
# bails. Kept tight so a truly stuck plan converts to exploration fast, but >1
# so a single mislabelled edge is corrected by replanning, not a bail.
EXECUTE_STUCK_LIMIT = 4
# When the structured world-model path (probe → navigate → interact) gains NO
# new level for this many actions, it has demonstrably stalled on this game
# class. The world model's own interaction lacks the GF(2) toggle / paint
# pattern primitives some games (lights-out, bit-panel) require, so it can loop
# its rotate-explore indefinitely without ever completing such a level. At that
# point the remaining budget is handed to a fresh GeneralAgent running its full
# proven discovery→nav→pattern→explore pipeline — the broad systematic
# exploration that catches those classes. The threshold sits above the slowest
# observed structured clear (ar25 L1 stumbles in the world model's interact
# rotate by ~540 actions) so every game the structured path CAN clear completes
# before the hand-off; the fallback only ever ADDS clears on games the world
# model would otherwise score 0 on (ft09 toggle, tn36 bit-panel).
NO_PROGRESS_FALLBACK = 650
# Post-clear EXPLOIT-then-STOP watchdog. The competition metric is per-level
# ``min(human/agent_actions, 1)**2`` — once a level is recorded, the actions
# spent AFTER it neither improve that level's score nor (measured) ever clear
# the next level on the games this agent reaches: AR25 clears L1 in 30 actions
# then wanders 512 more to GAME_OVER; LP85 clears L1 in 61 then loops the
# fallback to the 1250 cap. Those tails are pure waste against the shared 9h
# wall-clock the 110-game eval runs under. So once >=1 level has been cleared, a
# stall of this many actions with NO further level-up means broad exploration
# has demonstrably failed to find the next level — STOP and bank the clears. The
# window resets on every level-up, so a genuinely-progressing multi-level game
# is never cut; and it is wide enough (> the largest L2 human baseline among
# reached games + a full discovery+nav budget) that any next level clearable
# fast enough to score non-negligibly under the squared metric completes before
# the watchdog fires.
POST_CLEAR_STALL = 250
# Bounded probe buffer: the direction map is recomputed from the most recent
# movement probes, so the buffer is capped to keep ``observe`` O(1) per call.
_MOVE_PROBE_CAP = 40

_PHASE_PROBE = "probe"
_PHASE_EXECUTE = "execute"
_PHASE_INTERACT = "interact"
_PHASE_ARRANGE = "arrange"

# Simple action commonly used as the SELECTION toggle in arrangement games
# (cycles which entity the move actions drive). Detected, not assumed: the
# arrangement phase only engages when this action is available AND probing
# confirms it changes the per-mode movement map without itself translating a
# single player. ARC-AGI-3 maps ACTION5 to this role on the measured games.
_SELECT_TOGGLE_ACTION = 5
# Max distinct candidate arrangement plans the agent executes live before giving
# up on the arrangement hypothesis and falling through to interaction. Each
# candidate is a short sequence (~human-baseline length); the systematic sweep
# over alignment-entity offsets converges within a handful of tries on the
# measured games, and a cap keeps a non-arrangement game from burning budget.
_ARRANGE_MAX_CANDIDATES = 18


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


def rare_color_cells(
    layer: np.ndarray,
    background: int,
    max_colors: int = 8,
    max_cells: int = 400,
    prefer_colors: set[int] | None = None,
) -> list[tuple[int, int]]:
    """Individual cells of the rarest non-background colours, rarest colour first.

    The interactive surface of a click puzzle is its rare-colour object pixels
    (buttons / markers), NOT the common background field. Clicking a background
    or common-colour cell never drives the reward (``levels_completed``) up and,
    in a game with a lose state, can be fatal — so the reward-driven interaction
    search walks the rare-colour cells exclusively, rarest colour first then
    raster order within a colour. ``prefer_colors`` (e.g. the colour set that
    changed at a PAST level completion) is tried ahead of everything else, so
    reward attribution carries across levels. Pure / env-free → unit-testable.
    Returns ``(x, y)`` pixel coordinates.
    """
    if layer.size == 0:
        return []
    prefer = prefer_colors or set()
    vals, counts = np.unique(layer, return_counts=True)
    by_count = sorted(
        (
            (int(v), int(c))
            for v, c in zip(vals.tolist(), counts.tolist())
            if int(v) != background
        ),
        key=lambda vc: (vc[0] not in prefer, vc[1]),
    )
    out: list[tuple[int, int]] = []
    for color, _ in by_count[:max_colors]:
        ys, xs = np.where(layer == color)
        cells = sorted(zip(xs.tolist(), ys.tolist()), key=lambda p: (p[1], p[0]))
        for x, y in cells:
            out.append((int(x), int(y)))
            if len(out) >= max_cells:
                return out
    return out


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


def plan_navigation(
    layer: np.ndarray,
    model: EffectModel,
    goal: Goal,
    blocked: set[tuple[int, int]] | None = None,
    goal_cell_override: tuple[int, int] | None = None,
) -> list[int]:
    """Shortest action-id path from the player to the goal, in the learned model.

    Builds the walkable grid (``frame_to_cells`` with the floor colours the
    player was seen standing on) and runs ``grid_bfs`` over the learned unit
    ``step_dirs``. ``blocked`` is an optional set of grid ``(row, col)`` cells
    the agent learned impassable at runtime (a planned move into them did not
    translate the player); BFS routes around them so a wall the static pixel
    heuristic missed cannot trap the plan in a re-issue loop (the ls20 bug).
    Returns ``[]`` when no player, no learned directions, no goal,
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

    # Preferred model: edge-walkable node grid keyed on the corridor colour. This
    # is the only model that navigates interleaved-pitch mazes where a node
    # renders as wall colour but its connecting edge is the open corridor — the
    # tu93 class, where the node-dominant model below labels the whole board a
    # wall and BFS returns no path. The corridor colour is derived from the
    # player's move midpoints, so it is fully observation-driven. Falls back to
    # the node-dominant model when no corridor colour was observed.
    corridor = corridor_color_from_probes(model._move_probes, model.player_color, bg)
    if corridor is not None and goal_cell_override is None:
        goal_px = goal_centroid_px(layer, model.player_color, bg, target_color=goal.target_color)
        if goal_px is not None:
            edge_plan = edge_grid_bfs(
                layer,
                (player["cx"], player["cy"]),
                cell,
                goal_px,
                step_dirs,
                corridor,
                model.player_color,
                bg,
            )
            if edge_plan is not None:
                return edge_plan

    goal_cell = goal_cell_override or pick_goal_cell(
        layer, cell, model.player_color, bg, target_color=goal.target_color
    )
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
    return grid_bfs(walkable, start, goal_cell, step_dirs, blocked=blocked) or []


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

    # Hard per-game action cap. Sized so the structured world-model path keeps
    # its full working budget AND, on a stall, the GeneralAgent fallback gets a
    # fresh GeneralAgent-equivalent budget (~600) on top — see
    # NO_PROGRESS_FALLBACK. (WIN / GAME_OVER still stop the game far earlier on
    # the games either path can clear.)
    MAX_ACTIONS = 1250

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed
        self._rng = random.Random(seed)
        self._action_count = 0
        self._levels_completed = 0
        self.model = EffectModel()
        self.goal: Goal | None = None
        # Action count at the last level-up (0 at game start). The structured
        # path is judged stalled when it gains no level for
        # NO_PROGRESS_FALLBACK actions past this mark, engaging the fallback.
        self._last_progress_action = 0
        # GeneralAgent exploration fallback, created lazily on stall (see
        # _activate_fallback). None while the structured path is driving.
        self._fallback: GeneralAgent | None = None
        self._reset_level()

    def _reset_level(self) -> None:
        """Clear per-level plan/goal/probe state (called on level-up).

        The EffectModel (control knowledge) is GAME-scope and is NOT cleared
        here; only the per-level discovery / plan / explore bookkeeping resets.
        """
        self._phase = _PHASE_PROBE
        self._level_base = self._action_count
        self._pending: dict | None = None
        # Recentering-aware movement-discovery bookkeeping (mirrors GeneralAgent).
        self._move_targets: list[int] | None = None
        self._move_disc_done = False
        self._disc_attempts: Counter = Counter()
        self._disc_last_moved = False
        self._disc_last_probe_aid: int | None = None
        # One-shot attempt to build a navigation plan once movement is learned.
        self._nav_attempted = False
        # ACTION6 click-probe queue (built lazily for click-capable games).
        self._click_queue: list[tuple[int, int]] | None = None
        # Navigation plan + closed-loop prediction.
        self._plan: list[int] = []
        self._plan_commit = self._action_count
        self._pred_player: tuple[float, float] | None = None
        # Runtime-learned impassable grid cells (row, col): a planned move that
        # did NOT translate the player marks the cell it tried to enter as a
        # wall the static pixel heuristic missed, so the replan routes around
        # it instead of re-issuing the same blocked action (the ls20 stuck-loop).
        self._blocked_cells: set[tuple[int, int]] = set()
        # Player grid cell at the previous execute step, and the count of
        # consecutive planned moves that produced no player translation.
        self._exec_prev_cell: tuple[int, int] | None = None
        self._exec_aid: int | None = None
        self._exec_stuck = 0
        # Multi-target navigation: ordered goal-cell candidates and a cursor.
        # A collection level (visit several markers) is cleared by rotating to
        # the next candidate when the current one is reached / proves
        # unreachable, instead of bailing to undirected interaction after one.
        self._goal_cells: list[tuple[int, int]] | None = None
        self._goal_idx = 0
        self._goal_cell: tuple[int, int] | None = None
        # Explore / interaction bookkeeping (keyed by candidate descriptor so the
        # try/change stats survive a candidate-list rebuild as the frame evolves).
        self._xp_tries: Counter = Counter()
        self._xp_changes: Counter = Counter()
        self._xp_last_desc: tuple | None = None
        self._last_changed = False
        self._xp_cursor = 0
        # Bounded sequence-search bookkeeping (runs after the single-action sweep
        # identifies the frame-changers), mirroring GeneralAgent's explorer.
        self._seq_sweep_queue: list[tuple] | None = None
        self._seq_built = False
        self._seq_list: list[tuple] = []
        self._seq_i = 0
        self._seq_pos = 0
        # ── Multi-entity ARRANGEMENT bookkeeping (select-and-place) ──────────
        # The selection model (per-mode movement maps + toggle action) learned
        # by sweeping the selection space live, and the systematic-search state:
        # the ordered probe schedule, the model, the candidate plan currently
        # being executed, and the set of candidate plans already tried (so a
        # failed candidate's displaced frame yields a NEW alignment offset on the
        # next replan instead of repeating). See ``src/admorphiq/arrangement.py``.
        self._arr_probe_queue: list[tuple] | None = None
        self._arr_probe_log: list[dict] = []
        self._arr_model = None
        # The arrangement executes in two stages once the model is learned:
        # (1) ``_arr_descend`` — the queued action plan that brings the primary
        #     group onto the goal-marker row (descended ONCE);
        # (2) the alignment SWEEP — single alignment-entity steps, alternating
        #     direction outward (0, -1, +1, -2, +2, ...), checking the live
        #     level-up after each, so the level clears the moment the alignment
        #     column is right WITHOUT a risky full re-descent / restore. The
        #     sweep offsets are pre-ordered in ``_arr_sweep`` (each a small action
        #     list: a toggle to the alignment mode then one alignment move).
        self._arr_descend: list[int] | None = None
        self._arr_sweep: list[list[int]] | None = None
        self._arr_sweep_plan: list[int] = []
        self._arr_executed = 0

    # ── harness contract ──────────────────────────────────────────────────────

    def is_done(self, frames: list, latest_frame) -> bool:
        """Stop on WIN, on a post-clear stall, or when out of budget.

        WIN is the biggest efficiency lever. The post-clear stall check
        (``POST_CLEAR_STALL``) banks the clears already won and stops the
        proven-futile tail of broad exploration once at least one level is
        cleared and no further level has been gained for the stall window.
        """
        if _state_name(latest_frame) == "WIN":
            return True
        if (
            self._levels_completed >= 1
            and self._action_count - self._last_progress_action >= POST_CLEAR_STALL
        ):
            return True
        return self._action_count >= self.MAX_ACTIONS

    def choose_action(self, frames: list, latest_frame):
        """Emit the next action for the current observation."""
        from arcengine import GameAction

        # Once the exploration fallback has engaged it owns the rest of the game.
        if self._fallback is not None:
            return self._fallback_step(frames, latest_frame)

        layer = canonical_layer(getattr(latest_frame, "frame", latest_frame))
        avail = _avail_ids(latest_frame)
        state = _state_name(latest_frame)
        self.model.set_background(layer)
        bg = self.model.background if self.model.background is not None else 0

        # Credit the action issued last call (its "after" is the current frame)
        # into the GAME-scope model BEFORE any per-level reset.
        lvl = int(getattr(latest_frame, "levels_completed", 0) or 0)
        leveled = lvl > self._levels_completed
        if self._pending is not None and layer.size:
            p = self._pending
            if p["before"].shape == layer.shape:
                self.model.observe(p["action_id"], p["coord"], p["before"], layer, level_up=leveled)
                self._last_changed = not np.array_equal(p["before"], layer)
                # Explore credit: did this candidate change the frame?
                desc = p.get("desc")
                if desc is not None:
                    self._xp_tries[desc] += 1
                    if self._last_changed:
                        self._xp_changes[desc] += 1
                # Discovery credit: count the probe attempt + did the player move?
                if p.get("disc_probe"):
                    aid = p["action_id"]
                    self._disc_attempts[aid] += 1
                    self._disc_last_probe_aid = aid
                    self._disc_last_moved = self._probe_moved(aid, p["before"], layer, bg)
                # Arrangement selection-mode probe: log the (action, before, after)
                # so learn_selection_modes can build the per-mode movement map.
                if p.get("arr_probe"):
                    self._arr_probe_log.append(
                        {"action": p["action_id"], "before": p["before"], "after": layer.copy()}
                    )
            self._pending = None
        if leveled:
            self._levels_completed = lvl
            self._last_progress_action = self._action_count
            self._reset_level()

        if state == "GAME_OVER" or layer.size == 0 or not avail:
            self._pending = None
            return self._emit(GameAction.RESET)

        # Structured path stalled (no new level for NO_PROGRESS_FALLBACK
        # actions) → hand the remaining budget to the exploration fallback.
        if self._action_count - self._last_progress_action >= NO_PROGRESS_FALLBACK:
            self._activate_fallback()
            return self._fallback_step(frames, latest_frame)

        if self._phase == _PHASE_PROBE:
            return self._probe_step(layer, avail, latest_frame)
        if self._phase == _PHASE_EXECUTE:
            return self._execute_step(layer, avail, latest_frame)
        if self._phase == _PHASE_ARRANGE:
            return self._arrange_step(layer, avail, latest_frame)
        return self._interact_step(layer, avail, latest_frame)

    def choose_action_with_data(self, frames: list, latest_frame):
        """Official-base wrapper: return ``(action, data)`` with ACTION6 x/y."""
        action = self.choose_action(frames, latest_frame)
        data = getattr(action, "action_data", None)
        if data is not None:
            return action, {"x": int(data.x), "y": int(data.y)}
        return action, None

    # ── exploration fallback (delegates to GeneralAgent's full pipeline) ──────

    def _activate_fallback(self) -> None:
        """Switch control to a fresh GeneralAgent for the rest of the game.

        Called once when the structured world-model path has stalled (no new
        level for ``NO_PROGRESS_FALLBACK`` actions). The GeneralAgent runs its
        full proven discovery→nav→pattern→explore pipeline against the live
        frame — the broad systematic exploration (including the GF(2) toggle /
        paint primitives the world model lacks) that clears toggle / sequence
        games the world model alone cannot. The structured model is abandoned;
        any pending probe is dropped so it is not credited against the
        fallback's actions.
        """
        self._fallback = GeneralAgent(seed=self._seed)
        self._pending = None

    def _fallback_step(self, frames: list, latest_frame):
        """Delegate one action to the GeneralAgent fallback, counting it as ours.

        GeneralAgent maintains its own action counter; we additionally advance
        ``_action_count`` so ``is_done``'s budget cap still bounds the whole
        game and the harness's per-call accounting stays consistent.

        The fallback clears levels INSIDE its own pipeline, invisible to our
        level counter — so we mirror the frame's ``levels_completed`` here.
        Without this the post-clear stall watchdog could never fire on a
        fallback-driven game (no-player click games hand off before any clear),
        leaving LP85/FT09/TN36 to grind their full budget after L1 is banked.
        """
        lvl = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if lvl > self._levels_completed:
            self._levels_completed = lvl
            self._last_progress_action = self._action_count
        action = self._fallback.choose_action(frames, latest_frame)
        self._action_count += 1
        return action

    # ── probe phase: recentering movement discovery, then click probing ────────

    def _probe_moved(
        self, aid: int, before: np.ndarray, after: np.ndarray, bg: int
    ) -> bool:
        """Did the just-credited move probe translate the player? (env-free).

        A clean entry in the model's ``move_map`` is decisive; otherwise fall
        back to a live player-centroid shift so a blocked / no-op probe (which
        ``infer_direction_map`` never records) is still detectable as unmoved.
        """
        if aid in self.model.move_map:
            return True
        pc = self.model.player_color
        if pc is None:
            return False
        b = player_centroid(before, pc, bg)
        a = player_centroid(after, pc, bg)
        if b is None or a is None:
            return False
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 >= _MIN_TRANSLATION_PX

    def _probe_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        from arcengine import GameAction

        spent = self._action_count - self._level_base

        # On a level PAST the first, where the player/move controls are already
        # learned (GAME-scope) yet a selection-toggle action + several movable
        # entities are present, try the multi-entity ARRANGEMENT capability
        # BEFORE the recentering movement-discovery sweep below — that sweep
        # issues real (non-undone) moves that scramble the level's piece layout,
        # and the arrangement search depends on a near-pristine layout to keep
        # its alignment-offset sweep on a stable reference. The arrangement probe
        # schedule undoes each move, so it preserves the layout; if the learned
        # selection model turns out NOT to be a real arrangement (no
        # vertically-controllable primary + separate alignment entity), the phase
        # abandons back to interaction. Gated to non-first levels so no game's L1
        # discovery path is touched (the 6-game regression is L1-driven).
        if (
            self._levels_completed >= 1
            and self.model.player_color is not None
            and self._arr_probe_queue is None
            and _SELECT_TOGGLE_ACTION in avail
            and not self._move_disc_done
            and spent == 0
            and self._arrange_enabled(layer, avail)
        ):
            return self._enter_arrange(layer, avail, latest_frame)

        if self._move_targets is None:
            self._move_targets = [a for a in _MOVE_ACTION_IDS if a in avail]

        # Phase 1: recentering-aware movement discovery. A naive single sweep
        # mislearns a wall-bound player — the blocked directions never get a
        # vector, leaving a 2-direction map the planner cannot navigate with
        # (the tu93 failure). ``pick_next_probe`` re-probes a blocked action
        # after a freeing counter-move so every reachable direction is learned.
        if self._move_targets and not self._move_disc_done:
            if spent >= MOVE_PROBE_BUDGET:
                self._move_disc_done = True
            else:
                kind, aid = pick_next_probe(
                    self._move_targets,
                    self.model.move_map,
                    dict(self._disc_attempts),
                    self._disc_last_moved,
                    self._disc_last_probe_aid,
                )
                if kind == "recenter" and aid in avail:
                    # A relocation move (still observed by the model, but it is
                    # NOT counted as a probe attempt of any target).
                    self._disc_last_probe_aid = None
                    self._disc_last_moved = False
                    self._pending = {"action_id": aid, "coord": None, "before": layer.copy()}
                    return self._emit(GameAction.from_id(aid))
                if kind == "probe" and aid in avail:
                    self._pending = {
                        "action_id": aid,
                        "coord": None,
                        "before": layer.copy(),
                        "disc_probe": True,
                    }
                    return self._emit(GameAction.from_id(aid))
                self._move_disc_done = True

        # Once movement is learned, try a navigation plan BEFORE spending click
        # probes — navigation is the highest-value, most efficient plan kind.
        if not self._nav_attempted:
            self._nav_attempted = True
            self.goal = infer_goal(layer, self.model)
            if self.goal.kind == "navigate":
                plan = plan_navigation(layer, self.model, self.goal)
                if plan:
                    self._plan = list(plan)
                    self._pred_player = None
                    self._phase = _PHASE_EXECUTE
                    self._plan_commit = self._action_count
                    return self._execute_step(layer, avail, latest_frame)
            # No single-player navigation plan, but a selection-toggle action +
            # several movable entities → this is the multi-entity ARRANGEMENT
            # class (AR25-L2). Enter arrangement NOW, before the click-probe
            # sweep below displaces the pieces (the sweep moves them, shifting
            # the alignment offset the systematic search depends on). The
            # selection-toggle move probes have already been folded into the
            # model, so the pieces are near their level-start configuration.
            if (
                self._arr_probe_queue is None
                and _SELECT_TOGGLE_ACTION in avail
                and self._arrange_enabled(layer, avail)
            ):
                return self._enter_arrange(layer, avail, latest_frame)

        # No controllable player learned after movement discovery → this is a
        # pure click / toggle / bit-panel game. The world model has no nav plan
        # here and its blind click interaction is BOTH ineffective AND can trip a
        # lose-state before any action-count stall is ever detected (measured:
        # tn36 game-over by ~61 actions, ft09 by ~454). Hand off NOW — before
        # spending a single click probe — to the GeneralAgent's disciplined
        # discovery→pattern→explore pipeline, which owns the GF(2) toggle / paint
        # primitives these classes need and clears them without tripping the
        # lose-state. Movement games (a player WAS learned) keep the structured
        # world-model path, which is what clears the navigation classes.
        if self.model.player_color is None:
            self._activate_fallback()
            return self._fallback_step([], latest_frame)

        # Phase 2: ACTION6 click probing for a movement game whose navigation
        # goal could not be planned (no-movement games handed off above). Probe
        # rare-colour cluster centroids (the plausible buttons / markers) first,
        # then a coarse lattice, so a responsive cell anywhere is eventually hit.
        if 6 in avail:
            if self._click_queue is None:
                self._click_queue = self._build_click_probes(layer)
            # A movement game keeps the tight nav-secondary probe budget (the
            # wide reward-driven sweep belonged to the no-movement path, which
            # now hands off to the exploration fallback instead).
            cap = PROBE_BUDGET
            if spent < cap and self._click_queue:
                x, y = self._click_queue.pop(0)
                self._pending = {
                    "action_id": 6,
                    "coord": (x, y),
                    "before": layer.copy(),
                    "desc": ("c", x, y),
                }
                return self._emit_click(x, y)

        return self._finish_probe(layer, avail, latest_frame)

    def _build_click_probes(self, layer: np.ndarray) -> list[tuple[int, int]]:
        """Ordered ACTION6 probe cells for the reward-driven interaction search.

        The interactive surface of a click puzzle is its rare-colour object
        CELLS, not the common background field — so the search walks every cell
        of the rarest colours (rarest first; see :func:`rare_color_cells`),
        which is where the cell that drives ``levels_completed`` up actually
        lives. A colour that drove a PAST level completion is tried first
        (reward attribution carried across levels). The coarse lattice is kept
        only as a trailing fallback for games whose button sits on a common
        colour, reached after the rare-colour surface is exhausted.
        """
        bg = self.model.background if self.model.background is not None else 0
        out: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for cell in rare_color_cells(layer, bg, prefer_colors=self.model.completion_target_colors()):
            if cell not in seen:
                seen.add(cell)
                out.append(cell)
        half = PROBE_GRID_STRIDE // 2
        for y in range(half, 64, PROBE_GRID_STRIDE):
            for x in range(half, 64, PROBE_GRID_STRIDE):
                if (x, y) not in seen:
                    seen.add((x, y))
                    out.append((x, y))
        return out

    def _finish_probe(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Probing exhausted with no navigation plan → arrangement, else interact."""
        if self.goal is None:
            self.goal = infer_goal(layer, self.model)
        # No navigation plan formed, but a selection-toggle action + multiple
        # movable entities → try the multi-entity arrangement capability before
        # undirected interaction (the AR25-L2 select-and-place class). Gate is
        # observation-only.
        if (
            self._arr_probe_queue is None
            and _SELECT_TOGGLE_ACTION in avail
            and self._arrange_enabled(layer, avail)
        ):
            return self._enter_arrange(layer, avail, latest_frame)
        self._plan_commit = self._action_count
        self._phase = _PHASE_INTERACT
        return self._interact_step(layer, avail, latest_frame)

    # ── execute (navigation) phase ────────────────────────────────────────────

    def _execute_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        from arcengine import GameAction

        bg = self.model.background if self.model.background is not None else 0
        cur = (
            player_centroid(layer, self.model.player_color, bg)
            if self.model.player_color is not None
            else None
        )
        cur_cell = self._player_cell(cur)

        # Blocked-move detection: the move emitted last execute step had a known
        # nonzero unit step, yet the player's grid cell did NOT change -> the
        # cell it tried to enter is a wall the static pixel heuristic missed.
        # Learn that cell as impassable, abandon the now-invalid plan, and let
        # the replan below route around it (the ls20 stuck-loop fix). A player
        # stuck even after learning blocks rotates to the NEXT goal candidate
        # (multi-target levels) rather than bailing immediately.
        if (
            self._exec_prev_cell is not None
            and self._exec_aid is not None
            and cur_cell is not None
        ):
            step = self.model.step_dirs().get(self._exec_aid)
            if step is not None and cur_cell == self._exec_prev_cell:
                wall = (self._exec_prev_cell[0] + step[1], self._exec_prev_cell[1] + step[0])
                self._blocked_cells.add(wall)
                self._exec_stuck += 1
                self._plan = []
            elif cur_cell != self._exec_prev_cell:
                self._exec_stuck = 0

        if self._exec_stuck >= EXECUTE_STUCK_LIMIT:
            # Current target is unreachable from here even after learning walls.
            # Advance to the next goal candidate and replan; bail only when all
            # candidates are exhausted.
            self._exec_stuck = 0
            self._plan = []
            if not self._advance_goal(layer):
                return self._switch_to_interact(layer, avail, latest_frame)

        # Surprise check: the model predicted where the player would land last
        # step; a large mismatch (other than a clean block) means the learned
        # dynamics are wrong here, so replan to the current goal candidate.
        if self._pred_player is not None and cur is not None:
            dist = (
                (cur[0] - self._pred_player[0]) ** 2 + (cur[1] - self._pred_player[1]) ** 2
            ) ** 0.5
            if dist > SURPRISE_PX:
                self._plan = self._plan_to_current_goal(layer)

        # Bail-fast: a navigation plan that has not cleared the level in far more
        # than the human budget is the wrong model — switch to interaction.
        if self._action_count - self._plan_commit > EXECUTE_BAIL:
            return self._switch_to_interact(layer, avail, latest_frame)

        if not self._plan:
            self._plan = self._plan_to_current_goal(layer)
            # Empty plan to the current candidate (reached or unreachable) ->
            # rotate to the next candidate; bail when none remain.
            while not self._plan:
                if not self._advance_goal(layer):
                    return self._switch_to_interact(layer, avail, latest_frame)
                self._plan = self._plan_to_current_goal(layer)

        aid = self._plan.pop(0)
        if aid not in avail:
            self._plan = []
            return self._switch_to_interact(layer, avail, latest_frame)

        shift = self.model.predict_player_shift(aid)
        self._pred_player = (cur[0] + shift[0], cur[1] + shift[1]) if (shift and cur) else None
        self._exec_prev_cell = cur_cell
        self._exec_aid = aid
        self._pending = {"action_id": aid, "coord": None, "before": layer.copy()}
        return self._emit(GameAction.from_id(aid))

    def _ensure_goal_cells(self, layer: np.ndarray) -> None:
        """Lazily enumerate the ordered goal-cell candidates for this level."""
        if self._goal_cells is None:
            bg = self.model.background if self.model.background is not None else 0
            cell = _step_cell_size(self.model.move_map)
            self._goal_cells = enumerate_goal_cells(layer, cell, self.model.player_color, bg)
            self._goal_idx = 0
            self._goal_cell = self._goal_cells[0] if self._goal_cells else None

    def _advance_goal(self, layer: np.ndarray) -> bool:
        """Move the goal cursor to the next candidate; False when exhausted.

        Each rotation clears the per-target stuck count and the learned-block
        set is kept (walls are level-invariant). Returns True while a fresh
        candidate is available to plan toward.
        """
        self._ensure_goal_cells(layer)
        if not self._goal_cells:
            return False
        self._goal_idx += 1
        self._exec_stuck = 0
        if self._goal_idx >= len(self._goal_cells):
            return False
        self._goal_cell = self._goal_cells[self._goal_idx]
        return True

    def _plan_to_current_goal(self, layer: np.ndarray) -> list[int]:
        """BFS plan to the current goal candidate (override), else the default.

        With candidates enumerated, navigation aims explicitly at the current
        marker cell so a multi-target level can be swept one marker at a time.
        Falls back to the default rarest-colour goal when no candidates exist.
        """
        self._ensure_goal_cells(layer)
        goal = self.goal or infer_goal(layer, self.model)
        return plan_navigation(
            layer, self.model, goal,
            blocked=self._blocked_cells,
            goal_cell_override=self._goal_cell,
        )

    def _player_cell(self, centroid: tuple[float, float] | None) -> tuple[int, int] | None:
        """Player centroid (cx, cy) -> grid (row, col) at the learned cell pitch.

        Returns None when the player is unlocated or no movement was learned (no
        pitch to quantise by). Pure helper for blocked-move detection.
        """
        if centroid is None or not self.model.move_map:
            return None
        cell = _step_cell_size(self.model.move_map)
        return (int(round(centroid[1])) // cell, int(round(centroid[0])) // cell)

    def _switch_to_interact(self, layer: np.ndarray, avail: list[int], latest_frame):
        # A navigation plan that did not clear the level is the FIRST signal that
        # this may be a multi-entity ARRANGEMENT level (one player → one target →
        # one path is the wrong model when several pieces must each be placed and
        # a selection action cycles which piece moves). Before falling through to
        # undirected interaction, try the arrangement capability when its enabling
        # conditions hold: the selection-toggle action is available and not yet
        # probed this level. This is observation-gated, not game-id-gated.
        if (
            self._arr_probe_queue is None
            and _SELECT_TOGGLE_ACTION in avail
            and self._arrange_enabled(layer, avail)
        ):
            return self._enter_arrange(layer, avail, latest_frame)
        self._plan_commit = self._action_count
        self._phase = _PHASE_INTERACT
        return self._interact_step(layer, avail, latest_frame)

    # ── arrangement (select-and-place multi-entity) phase ─────────────────────

    def _arrange_enabled(self, layer: np.ndarray, avail: list[int]) -> bool:
        """Cheap gate: are there several sizeable movable-looking entities?

        The arrangement search is only worth its probe cost when the frame holds
        at least two distinct non-background coloured objects large enough to be
        pieces (the selection toggle alone is not enough — a pure toggle game has
        no movable entities). Counts distinct colours with a sizeable component;
        ``>= 2`` qualifies. Frame-only, no game-id / internal reads.
        """
        bg = self.model.background if self.model.background is not None else 0
        from .arrangement import entity_centroids

        return len(entity_centroids(layer, bg)) >= 2

    def _enter_arrange(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Begin the arrangement phase: schedule the live selection-mode probes.

        The probe schedule sweeps each selection mode: within a mode, probe each
        move action (with an immediate inverse to undo it so the sweep does not
        drift the pieces), then issue the selection toggle to advance to the next
        mode. The resulting ``before/after`` log feeds
        :func:`learn_selection_modes`. Two modes are scheduled (the measured
        count); an extra toggle at the end restores selection to mode 0.
        """
        self._phase = _PHASE_ARRANGE
        self._plan_commit = self._action_count
        moves = [a for a in (1, 2, 3, 4) if a in avail]
        inv = {1: 2, 2: 1, 3: 4, 4: 3}
        schedule: list[tuple] = []
        n_modes = 2
        # Probe each of the ``n_modes`` selection modes (model mode 0 = the mode
        # active NOW). Within a mode, probe each move (undone immediately so the
        # layout is preserved); a single toggle separates modes. After visiting
        # all modes the hardware sits in the LAST mode, so issue
        # ``n_modes - last_mode`` (= 1 for two modes, a full extra cycle back to
        # 0) closing toggles to return the hardware to model mode 0 — the mode
        # the candidate plans assume as their starting selection. Total toggles is
        # then ``n_modes`` (even for two modes → back to start), fixing the
        # off-by-one that previously left the hardware one toggle out of phase and
        # made every candidate execute in the wrong selection mode.
        for mode in range(n_modes):
            for a in moves:
                schedule.append(("probe", a))
                if inv[a] in avail:
                    schedule.append(("undo", inv[a]))
            if mode < n_modes - 1:
                schedule.append(("toggle", _SELECT_TOGGLE_ACTION))
        # Closing toggles: from the last visited mode (n_modes-1) advance the
        # cyclic selection back to 0.
        for _ in range((n_modes - (n_modes - 1)) % n_modes or n_modes):
            schedule.append(("toggle", _SELECT_TOGGLE_ACTION))
        self._arr_probe_queue = schedule
        self._arr_probe_log = []
        return self._arrange_step(layer, avail, latest_frame)

    def _arrange_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """One action of the arrangement phase: probe modes, then sweep candidates.

        Stage 1 — drain the live mode-probe schedule, logging each
        (action, before, after) so :func:`learn_selection_modes` can build the
        per-mode movement map.
        Stage 2 — with the model learned, repeatedly generate candidate plans
        from the LIVE frame (shortest first), execute the shortest untried one,
        and let the env confirm the WIN. A failed candidate displaces the pieces;
        the next replan from the displaced frame yields a different alignment
        offset, so the systematic sweep advances without repeating. Falls through
        to interaction once the candidate budget is spent.
        """
        from arcengine import GameAction

        bg = self.model.background if self.model.background is not None else 0

        # Stage 1: live selection-mode probing.
        if self._arr_probe_queue:
            kind, aid = self._arr_probe_queue.pop(0)
            if aid not in avail:
                # Skip a probe whose action vanished; keep draining the schedule.
                return self._arrange_step(layer, avail, latest_frame)
            if kind in ("probe", "toggle"):
                self._pending = {
                    "action_id": aid,
                    "coord": None,
                    "before": layer.copy(),
                    "arr_probe": True,
                    "arr_kind": kind,
                }
            else:  # undo move — observed by the model but not logged as a probe
                self._pending = {"action_id": aid, "coord": None, "before": layer.copy()}
            return self._emit(GameAction.from_id(aid))

        # Build the selection model once the schedule has drained.
        if self._arr_model is None:
            self._arr_model = learn_selection_modes(
                self._arr_probe_log, bg, toggle_action=_SELECT_TOGGLE_ACTION
            )
            if not self._arr_model.any_movement():
                return self._abandon_arrange(layer, avail, latest_frame)

        # Stage 2a: descend the primary group ONCE onto the goal-marker row.
        # Planned from the live (post-probe) layout, and executed before any
        # alignment sweep — moving the alignment entity afterwards does not change
        # the primary's row, so the level clears the instant the alignment column
        # is right, with no risky re-descent / restore that could overshoot the
        # board edge and trip a lose-state (measured on AR25: restoring the
        # descent UP game-overs).
        if self._arr_descend is None:
            self._arr_descend, self._arr_sweep = plan_descend_and_sweep(
                layer, bg, self._arr_model
            )
            if self._arr_descend is None:
                return self._abandon_arrange(layer, avail, latest_frame)
        if self._arr_descend:
            aid = self._arr_descend.pop(0)
            if aid not in avail:
                self._arr_descend = []
                return self._arrange_step(layer, avail, latest_frame)
            self._pending = {"action_id": aid, "coord": None, "before": layer.copy()}
            return self._emit(GameAction.from_id(aid))

        # Stage 2b: alignment SWEEP. Each entry is a short action list (toggle into
        # the alignment mode + one alignment-entity step) tried in outward order
        # (0, then toward the goal marker, then the other side); the live level-up
        # check between entries (handled by the harness on the next call) ends the
        # game the moment the alignment column is right.
        if not self._arr_sweep_plan:
            if not self._arr_sweep or self._arr_executed >= _ARRANGE_MAX_CANDIDATES:
                return self._abandon_arrange(layer, avail, latest_frame)
            self._arr_sweep_plan = list(self._arr_sweep.pop(0))
            self._arr_executed += 1
            if not self._arr_sweep_plan:
                return self._arrange_step(layer, avail, latest_frame)

        aid = self._arr_sweep_plan.pop(0)
        if aid not in avail:
            self._arr_sweep_plan = []
            return self._arrange_step(layer, avail, latest_frame)
        self._pending = {"action_id": aid, "coord": None, "before": layer.copy()}
        return self._emit(GameAction.from_id(aid))

    def _abandon_arrange(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Arrangement inapplicable/exhausted → resume the normal probe pipeline.

        When the learned selection model is NOT a real arrangement (no movement,
        or no vertically-controllable primary), the level may still be a normal
        navigation / interaction level, so control returns to the standard probe
        phase (movement discovery → navigation → interaction) rather than jumping
        straight to undirected interaction. The arrangement queue is marked done
        (set to ``[]``) so this phase is not re-entered for the level.
        """
        self._arr_probe_queue = []
        self._phase = _PHASE_PROBE
        self._move_disc_done = False
        self._move_targets = None
        self._nav_attempted = False
        return self._probe_step(layer, avail, latest_frame)

    # ── interact (greedy + bounded sequence search) phase ─────────────────────

    def _interact_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Disciplined interaction in three stages (reuses GeneralAgent's proven
        explorer primitives so a level completing on a single click, a short
        action SEQUENCE, or a delayed-effect cell is all reachable).

        1. **Single-action sweep** — try each candidate once (one-input clears).
        2. **Bounded sequence search** — short combos built ONLY from the
           observed frame-changers via :func:`build_action_sequences`.
        3. **Rotate fallback** — :func:`select_explore_action` keeps spending the
           remaining budget on changers while periodically revisiting the pool.
        """
        from arcengine import GameAction

        candidates = self._build_interact_candidates(layer, avail)
        if not candidates:
            if 6 in avail:
                self._pending = {
                    "action_id": 6, "coord": (32, 32),
                    "before": layer.copy(), "desc": ("c", 32, 32),
                }
                return self._emit_click(32, 32)
            return self._emit(GameAction.RESET)

        if not self._seq_built:
            if self._seq_sweep_queue is None:
                self._seq_sweep_queue = list(candidates)
            while self._seq_sweep_queue:
                d = self._seq_sweep_queue.pop(0)
                if self._xp_tries.get(d, 0) == 0:
                    return self._emit_desc(d, layer)
            self._build_sequence_search(avail)
            self._seq_built = True

        act = self._next_sequence_action(layer, avail)
        if act is not None:
            return act

        desc, self._xp_cursor = select_explore_action(
            candidates, self._xp_tries, self._xp_changes, self._xp_cursor
        )
        if desc is None:
            if 6 in avail:
                self._pending = {
                    "action_id": 6, "coord": (32, 32),
                    "before": layer.copy(), "desc": ("c", 32, 32),
                }
                return self._emit_click(32, 32)
            return self._emit(GameAction.RESET)
        return self._emit_desc(desc, layer)

    def _build_interact_candidates(self, layer: np.ndarray, avail: list[int]) -> list[tuple]:
        """Ordered, availability-filtered interaction descriptors.

        Most-promising first: cells/actions the online model already saw doing
        something (``plan_interaction``), then the raw move actions, then the
        rare-cluster / lattice click probes — de-duplicated preserving order.
        """
        out: list[tuple] = []
        seen: set[tuple] = set()

        def _add(desc: tuple) -> None:
            ok = (desc[0] == "m" and desc[1] in avail) or (desc[0] == "c" and 6 in avail)
            if ok and desc not in seen:
                seen.add(desc)
                out.append(desc)

        for desc in plan_interaction(layer, self.model):
            _add(desc)
        for a in _MOVE_ACTION_IDS:
            _add(("m", a))
        if 6 in avail:
            for cell in self._click_queue or self._build_click_probes(layer):
                _add(("c", int(cell[0]), int(cell[1])))
        return out

    def _build_sequence_search(self, avail: list[int]) -> None:
        """Stage the bounded sequence search from the observed frame-changers.

        Tokens are the move actions that changed the frame during the sweep
        (still available) followed by up to three frame-changing click targets,
        busiest first. With no observed changer the list stays empty and the
        explorer falls straight through to the rotate fallback.
        """
        move_tokens = [
            a
            for a in _MOVE_ACTION_IDS
            if a in avail and self._xp_changes.get(("m", a), 0) > 0
        ]
        click_changers = [
            d for d in self._xp_changes if d[0] == "c" and self._xp_changes.get(d, 0) > 0
        ]
        click_changers.sort(key=lambda d: -self._xp_changes[d])
        click_tokens: list[tuple] = click_changers[:3] if 6 in avail else []
        tokens: list = list(move_tokens) + list(click_tokens)
        self._seq_list = build_action_sequences(tokens)
        self._seq_i = 0
        self._seq_pos = 0

    def _next_sequence_action(self, layer: np.ndarray, avail: list[int]):
        """Emit the next token of the current combo, or None when exhausted.

        A pure-repeat combo is abandoned the moment a token already emitted
        within it failed to change the frame (repeating a wall-hit is wasted
        budget); heterogeneous combos run to completion. Tokens referencing a
        now-unavailable action skip the whole combo.
        """
        while self._seq_i < len(self._seq_list):
            seq = self._seq_list[self._seq_i]
            if self._seq_pos > 0 and not self._last_changed and len(set(seq)) == 1:
                self._seq_i += 1
                self._seq_pos = 0
                continue
            if self._seq_pos >= len(seq):
                self._seq_i += 1
                self._seq_pos = 0
                continue
            token = seq[self._seq_pos]
            desc = ("m", token) if isinstance(token, int) else token
            if (desc[0] == "m" and desc[1] not in avail) or (desc[0] == "c" and 6 not in avail):
                self._seq_i += 1
                self._seq_pos = 0
                continue
            self._seq_pos += 1
            return self._emit_desc(desc, layer)
        return None

    # ── action emission (records pending so the model keeps learning) ──────────

    def _emit_desc(self, desc: tuple, layer: np.ndarray):
        from arcengine import GameAction

        if desc[0] == "m":
            aid = desc[1]
            self._pending = {
                "action_id": aid, "coord": None,
                "before": layer.copy(), "desc": ("m", aid),
            }
            return self._emit(GameAction.from_id(aid))
        _, x, y = desc
        self._pending = {
            "action_id": 6, "coord": (int(x), int(y)),
            "before": layer.copy(), "desc": ("c", int(x), int(y)),
        }
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
