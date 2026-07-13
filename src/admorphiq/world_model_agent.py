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
from .delivery import (
    DeliveryPuzzle,
    adjacent_cells,
    bbox_min_corner,
    bfs_path,
    detect_delivery_puzzle,
    detect_mover_by_motion,
    locate_player_cell,
    path_to_actions,
    target_slots,
)
from .general_agent import (
    _EXPLORE_MAX_CLUSTERS,
    _MAX_PLAYER_SIZE,
    _MIN_GOAL_SIZE,
    _MIN_TRANSLATION_PX,
    _MOVE_ACTION_IDS,
    GeneralAgent,
    _avail_ids,
    _occupancy_floor_colors,
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
    select_player_component,
)
from .merge_drag import (
    detect_drag_layout,
    detect_goal_containers,
    drag_probe_target,
    next_merge_click,
)
from .perception.frame_analyzer import FrameAnalyzer
from .rotation import (
    MAX_COMMIT_CLICKS_PER_PIECE,
    RotationPuzzle,
    detect_rotation_puzzle,
    identify_moved_piece,
    piece_matches_target,
)
from .slider import (
    SliderPuzzle,
    clicks_needed,
    detect_slider_puzzle,
    identify_moved_track,
    resolve_goal,
    track_reached_goal,
)
from .sort_match import detect_match_layout, plan_match_placement
from .transform_route import (
    TransformPuzzle,
    build_move_actions,
    detect_sprite_by_motion,
    detect_sprite_candidates,
    detect_transform_puzzle,
    find_active_color,
    find_covering_offset,
    snap_to_axis,
    sprite_bbox_implausible,
)

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
# Consecutive GAME_OVERs on the SAME level (no level-up in between) before
# is_done() stops the run instead of letting the blind retry-the-same-plan
# loop continue. Measured 2026-07-13 (depth survey #2): ft09 and tn36's L2
# fall into unstructured probe/interact, which repeatedly walks the env into
# GAME_OVER — RESET just re-enters the identical phase and repeats the same
# losing pattern. Each of those was eventually cut off by POST_CLEAR_STALL,
# but only after 4 full cycles' worth of wasted budget; a game that never
# clears ANY level first (POST_CLEAR_STALL's `levels_completed >= 1`
# precondition does not apply) has no existing stop condition at all and
# would cycle toward MAX_ACTIONS. 3 mirrors _MERGE_DRAG_STALL_LIMIT's
# precedent (a stall/retry cap, not a hard game-specific number) and is
# comfortably below every measured cycling case's 4-7 repeats, so it never
# cuts a game that is making even slow structured progress.
GAME_OVER_CYCLE_LIMIT = 3
# Bounded probe buffer: the direction map is recomputed from the most recent
# movement probes, so the buffer is capped to keep ``observe`` O(1) per call.
_MOVE_PROBE_CAP = 40

_PHASE_PROBE = "probe"
_PHASE_EXECUTE = "execute"
_PHASE_INTERACT = "interact"
_PHASE_ARRANGE = "arrange"
_PHASE_SORT_MATCH = "sort_match"
_PHASE_MERGE_DRAG = "merge_drag"
_PHASE_ROTATE = "rotate"
_PHASE_SLIDE = "slide"
_PHASE_TRANSFORM = "transform"
_PHASE_DELIVERY = "delivery"

# Max clicks the merge-drag plan issues PER LEVEL before abandoning the
# hypothesis (reset each level in ``_reset_level``). A simple gather walks a tile
# across the board in ~9 clicks (SU15 L1); a full merge chain (SU15 L2: eight
# 1-px tiles combined up to a value-3 tile then gathered) needs ~35. The cap
# covers the deepest measured chain plus animation margin while still bounding
# wasted budget on a non-drag click game whose tiles ignore the pull (caught
# earlier by the test-click confirmation in any case).
_MERGE_DRAG_MAX_CLICKS = 120

# Consecutive walk clicks that change NOTHING before the merge-drag phase
# abandons to interaction. Measured on SU15 L3 (2026-07): once a tile stops
# responding to the pull (a pre-merge phase this plan doesn't model, e.g.
# enemy-downgrade), ``next_merge_click`` recomputes the identical target from
# the unchanged frame every call and loops forever; the live env does not
# treat those no-op clicks as free — after ~6 consecutive no-ops the run hit
# GAME_OVER, which costs a RESET's worth of actions (``levels_completed`` is
# NOT reset by it — confirmed unchanged across GAME_OVER->RESET, so budget is
# lost, not progress). 3 gives the walk room to recover from a single missed
# grab (drag animation lag) while stopping well before the measured
# GAME_OVER threshold.
_MERGE_DRAG_STALL_LIMIT = 3


def _merge_drag_tile_snapshot(layer: np.ndarray, background: int) -> frozenset:
    """Rounded ``(colour, size, cx, cy)`` tuples for every movable tile.

    Used to detect a genuinely stalled merge-drag click: comparing this
    snapshot before/after a click (not full-frame equality, which a HUD or
    resource-counter region can trip on every click regardless of whether the
    tracked tiles moved) is the reliable stall signal. Rounds centroids to 1
    decimal so drag-animation sub-pixel jitter doesn't register as movement.
    Returns an empty frozenset when there is no drag layout at all.
    """
    layout = detect_drag_layout(layer, background)
    if layout is None:
        return frozenset()
    return frozenset(
        (color, size, round(cx, 1), round(cy, 1)) for cx, cy, color, size in layout.tiles
    )


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

        A non-axis-aligned reading (both components nonzero, e.g. ``(-2, -18)``)
        is dropped rather than quantised to a diagonal unit vector. Measured on
        AR25 L3 (2026-07-13): a single mis-probed reading for one action ID
        quantises to a bogus diagonal ``(-1, -1)`` edge; ``grid_bfs`` then
        expands the walkable grid with that action moving off the cardinal
        lattice every OTHER action uses, silently discarding one whole
        direction of real reachability and leaving every goal candidate
        unreachable (``plan_len=0`` from the very first replan — this never
        even reaches the blocked-cell / retry-corroboration logic, since no
        partial plan is ever produced to execute and stall on). This repo's
        navigation model is 4-connected-cardinal only (no game here moves the
        player diagonally per action) so a diagonal quantisation is always a
        probe artefact, never a real mechanic — dropping it just means that
        action id contributes no edge this level, same as an unobserved
        action, instead of corrupting the whole reachability graph.
        """
        keys = self.move_map.keys() if avail is None else [a for a in avail if a in self.move_map]
        out: dict[int, tuple[int, int]] = {}
        for aid in keys:
            dx, dy = self.move_map[aid]
            ucol, urow = _unit(dx), _unit(dy)
            if ucol == 0 and urow == 0:
                continue
            if ucol != 0 and urow != 0:
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
    player = select_player_component(player_comps, layer.shape)

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

    # Occupancy invariant: any cell the player is CURRENTLY observed standing
    # on/adjacent to is proof-by-direct-observation of floor, regardless of
    # what frame_to_cells's probe-derived floor set has or hasn't learned yet.
    # Measured on AR25 L3 (2026-07-13): floor_colors_from_probes only learns
    # a colour once a probe records the player VACATING that cell; a level
    # whose floor colour was never probed this way (plausible right after a
    # level transition, before any successful move) leaves frame_to_cells's
    # ``if floor_colors:`` branch excluding that colour, collapsing walkable
    # from 410/441 (L1/L2) to 57-59/441 (L3) and leaving every goal candidate
    # unreachable. Tried blindly unioning ``{bg}`` in first — that FIXED ar25
    # but broke ls20 (1/7@89 -> 0/7@131 live), confirming background is
    # legitimately a WALL colour on some boards once floor is otherwise known
    # (the exact case frame_to_cells's docstring warns about). Sampling only
    # the colours actually touching the player's OWN footprint is safe on
    # both: it can never blanket-include background unless the player is
    # truly standing on/next to it right now.
    floor = floor_colors_from_probes(model._move_probes, model.player_color, bg)
    floor = floor | _occupancy_floor_colors(layer, player.get("cells"))
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
        # Fingerprint of the transform puzzle just solved (captured in
        # ``choose_action`` right before ``_reset_level`` clears
        # ``_transform_puzzle`` — so it must live OUTSIDE that reset,
        # persisting across the level boundary it describes). Used by the
        # transform gate's staleness check: see its comment in
        # ``_probe_step``.
        self._transform_prev_puzzle_key: frozenset | None = None
        self._reset_level()

    def _reset_level(self) -> None:
        """Clear per-level plan/goal/probe state (called on level-up).

        The EffectModel (control knowledge) is GAME-scope and is NOT cleared
        here; only the per-level discovery / plan / explore bookkeeping resets.
        """
        self._phase = _PHASE_PROBE
        # Consecutive GAME_OVERs since the last genuine level-up (see
        # GAME_OVER_CYCLE_LIMIT). Resetting here — not on every GAME_OVER-
        # triggered RESET, which stays on the same level index — is what
        # makes this a "cycling" counter rather than a total-GAME_OVER count.
        self._game_over_count = 0
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
        # A single no-translation reading can be spurious (a corrupted
        # movement-model entry, a transient animation frame) rather than a
        # real wall — measured on AR25 L3: one bad probe made a cardinal
        # action look diagonal, so a genuinely-open cell got misread as
        # blocked on the FIRST attempt, and that one false wall happened to
        # be a chokepoint that severed every remaining goal candidate. The
        # candidate cell must reproduce on a same-action RETRY before it is
        # committed to _blocked_cells — generic corroboration against any
        # noise source, not scoped to the movement-model root cause.
        self._pending_block: tuple[int, int] | None = None
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
        # ── Click-only MATCH-TO-ORDER sort bookkeeping (sort_match.py) ───────
        # The ordered click/verify plan that places each pool swatch under its
        # matching reference frame, built once per level from the detected
        # layout. None until the sort phase is entered; [] once attempted (so
        # the phase is not re-entered).
        self._sort_plan: list[tuple] | None = None
        self._sort_attempted = False
        # ── Click-only MERGE / gather (drag-to-goal) bookkeeping (merge_drag) ──
        # ``_merge_drag_attempted`` gates the one-shot drag probe per level (a
        # fresh gather each level: SU15 re-lays its tiles + goal every level);
        # ``_merge_drag_probed`` flips True once the test click confirmed the
        # drag pull, after which the gather walk runs; ``_merge_drag_clicks``
        # caps the walk length so a non-drag game abandons quickly.
        # ``_merge_drag_stall`` counts CONSECUTIVE walk clicks that changed
        # nothing (measured SU15 L3: a tile can go permanently unresponsive
        # mid-gather — likely a pre-merge phase, e.g. enemy-downgrade, that
        # this plan doesn't model — and blindly re-clicking it doesn't just
        # waste budget, it walks the game into GAME_OVER (levels_completed
        # is unaffected, but the RESET still costs real actions).
        self._merge_drag_attempted = False
        self._merge_drag_probed = False
        self._merge_drag_clicks = 0
        self._merge_drag_stall = 0
        # ``_merge_drag_goal`` is the goal-container centroid currently being
        # targeted (None = the natural default, the largest/rarest cluster).
        # ``_merge_drag_tried_goals`` accumulates every goal centroid that has
        # been abandoned (probe failed, stalled, or "gather complete" without
        # a level-up) so a multi-goal board (SU15: TWO distinct containers)
        # tries the OTHER goal before giving up entirely, instead of
        # permanently committing to whichever one detect_drag_layout's
        # single-largest-cluster heuristic happened to pick first. Measured
        # live: forcing the correct goal cleared SU15 L3 in 21 actions from a
        # state that, targeted at the default goal, stalls/GAME_OVERs every
        # time without ever clearing.
        self._merge_drag_goal: tuple[float, float] | None = None
        self._merge_drag_tried_goals: list[tuple[float, float]] = []
        # True for exactly one call: right after a goal-switch RESET, telling
        # _merge_drag_step to issue the new goal's probe click directly
        # rather than checking _last_changed (which would be credited to the
        # RESET action itself, meaningless here).
        self._merge_drag_reset_pending = False
        # Snapshot of tile positions/sizes captured right before the last
        # merge_drag click was issued, used to detect a stalled TILE
        # specifically. ``_last_changed`` (full-frame equality) is NOT a
        # reliable stall signal here — measured on SU15: a HUD/resource
        # counter changes on every click regardless of whether the tracked
        # tile moved, so ``_last_changed`` stays True and the stall counter
        # never increments even while a tile is genuinely dead-clicked
        # straight through to GAME_OVER (the falsification signature the
        # lesson page for this exact bug already documented).
        self._merge_drag_last_tiles: frozenset | None = None
        # ── Click-only ROTATION-PUZZLE bookkeeping (rotation.py) ──────────────
        # ``_rotation_attempted`` gates the one-shot detection per level (a
        # fresh piece/reference layout each level). ``_rotation_puzzle`` is the
        # detected pieces/targets/candidates once found. Stage 1 drains
        # ``_rot_probe_queue`` (candidate widget positions, one click each) and
        # folds each result — appended to ``_rot_probe_log`` by the credit block
        # in ``choose_action`` (mirrors ``_arr_probe_log``) — into
        # ``_rot_widget_for_piece`` (piece index -> its widget (x, y)). Stage 2
        # then works ``_rot_commit_queue`` (piece indices with both a target and
        # a known widget), clicking ``_rot_active_piece``'s widget until its
        # live interior matches the target or the per-piece click cap is spent.
        self._rotation_attempted = False
        self._rotation_puzzle: RotationPuzzle | None = None
        self._rot_probe_queue: list[tuple[int, int]] = []
        self._rot_probe_log: list[dict] = []
        self._rot_probe_processed = 0
        self._rot_widget_for_piece: dict[int, tuple[int, int]] = {}
        self._rot_commit_queue: list[int] | None = None
        self._rot_active_piece: int | None = None
        self._rot_clicks_left = 0
        # ── Click-only SLIDER-PUZZLE bookkeeping (slider.py) ───────────────────
        # Mirrors the rotation bookkeeping above exactly, one level down:
        # ``_slide_attempted`` gates one-shot detection per level.
        # ``_slider_puzzle`` is the detected tracks/markers/candidates. Stage 1
        # drains ``_slide_probe_queue`` and folds each result — appended to
        # ``_slide_probe_log`` by the credit block in ``choose_action`` — into
        # ``_slide_track_buttons`` (track index -> {"grow"/"shrink": (x, y)})
        # and ``_slide_track_steps`` (track index -> {"grow"/"shrink": measured
        # step}). Stage 2 works ``_slide_commit_queue`` (tracks with a
        # discovered "grow" button), clicking ``_slide_active_track``'s grow
        # widget toward its resolved goal until the live tip reaches it or the
        # measured click count is spent.
        self._slide_attempted = False
        self._slider_puzzle: SliderPuzzle | None = None
        self._slide_probe_queue: list[tuple[int, int]] = []
        self._slide_probe_log: list[dict] = []
        self._slide_probe_processed = 0
        self._slide_track_buttons: dict[int, dict[str, tuple[int, int]]] = {}
        self._slide_track_steps: dict[int, dict[str, int]] = {}
        self._slide_commit_queue: list[int] | None = None
        self._slide_active_track: int | None = None
        self._slide_goal: int | None = None
        self._slide_clicks_left = 0
        # ── Simple-action TRANSFORM-PUZZLE bookkeeping (transform_route.py) ────
        # ``_transform_attempted`` gates the one-shot detection per level.
        # ``_transform_puzzle`` is the detected targets/sprites once found.
        # Stage 0 drains ``_transform_calib_queue`` ([1,2,3,4] filtered by
        # availability), folding each press's before/after (appended to
        # ``_transform_calib_log`` by the credit block in ``choose_action``,
        # mirroring ``_rot_probe_log``/``_slide_probe_log``) into
        # ``_transform_dir_map`` (action id -> measured (dx, dy)) for the
        # FIXED colour active at level entry (``_transform_active_color``).
        # Stage 1 drains a queued move sequence (``_transform_move_queue``)
        # for whichever sprite was just committed. Stage 2 (no queue pending)
        # re-reads which sprite is NOW active
        # (:func:`transform_route.find_active_color`, purely from the live
        # frame — no probe needed even after an ACTION5 cycle) and, if it is
        # still in ``_transform_colors_needed``, plans + queues its move via
        # :func:`transform_route.find_covering_offset` +
        # :func:`transform_route.build_move_actions`; otherwise presses
        # ACTION5 to cycle, bounded by ``_transform_cycles_left``.
        self._transform_attempted = False
        self._transform_puzzle: TransformPuzzle | None = None
        self._transform_active_color: int | None = None
        self._transform_dir_map: dict[int, tuple[int, int]] = {}
        self._transform_step_size = 0
        # Motion-based sprite reclassification (see the transform_route.py
        # docstrings for detect_sprite_by_motion / sprite_bbox_implausible).
        # Set once in _enter_transform when the naively-detected active
        # sprite's bbox is implausible (measured necessary on RE86 L3: same-
        # colour decoration gap-bridged onto the real sprite through one
        # touching pixel). ``_transform_last_calib_pair`` caches the most
        # recent calibration press's (before, after) frames so Stage 2 can
        # re-derive the CURRENT live sprite footprint by motion instead of
        # the naive (corrupted, for this active colour) whole-layer cluster.
        # False/None on every level whose active sprite is plausibly sized —
        # L1/L2 never set this, so their path is untouched.
        self._transform_motion_mode = False
        self._transform_last_calib_pair: tuple[np.ndarray, np.ndarray] | None = None
        self._transform_calib_queue: list[int] = []
        self._transform_calib_log: list[dict] = []
        self._transform_calib_processed = 0
        self._transform_colors_needed: set[int] = set()
        self._transform_move_queue: list[int] = []
        self._transform_cycles_left = 0
        # Active colours already passed through while cycling toward the
        # NEXT needed colour (reset every time a colour is placed or given
        # up on, so it bounds each search independently) — the primary
        # cycle-termination signal; see the comment where it is checked in
        # _transform_step.
        self._transform_seen_active: set[int | None] = set()
        # A level entered via a real transition can render its FIRST frame
        # still showing the previous level's final board — measured on RE86
        # L2/L3: the target-marker/sprite colours only settle to the true
        # new layout after one more action is taken. Detection failing
        # outright is one signal; the other (measured on L2->L3, worse
        # because it is silent) is detection SUCCEEDING on an exact repeat
        # of the puzzle just solved (see ``_transform_prev_puzzle_key``) —
        # a fully-SOLVED previous board's ring+dot markers stay visually
        # present regardless of satisfaction, so "detected something valid"
        # alone does not mean "this is the new level". Either case triggers
        # ONE settle press + detection retry (see the gate in
        # ``_probe_step``); ``_transform_settle_tried`` bounds this to
        # exactly once so a genuine non-transform level still gives up
        # after one extra action, never loops.
        self._transform_settle_tried = False
        # ── Simple-action DELIVERY (pick-carry-drop) bookkeeping (delivery.py) ──
        # ``_delivery_attempted`` gates the one-shot detection per level.
        # ``_delivery_puzzle`` is the detected items/targets, captured ONCE
        # at entry — a delivered item's marker is absorbed into the
        # player's own rendering and a filled target slot no longer forms a
        # clean single-colour interior, so re-detecting mid-phase is
        # unreliable (see delivery.py's module docstring); progress is
        # tracked in ``_delivery_items_remaining`` / ``_delivery_used_slots``
        # instead. ``_delivery_player_colors`` (the union of colours found
        # at the player's own cells during calibration — never assumed) is
        # what makes any later single-frame player-location lookup
        # orientation-independent, unlike the leading-edge accent colour
        # alone (see :func:`admorphiq.delivery.detect_mover_by_motion`).
        self._delivery_attempted = False
        self._delivery_puzzle: DeliveryPuzzle | None = None
        self._delivery_dir_map: dict[int, tuple[int, int]] = {}
        self._delivery_step_size = 0
        self._delivery_calib_queue: list[int] = []
        self._delivery_calib_log: list[dict] = []
        self._delivery_calib_processed = 0
        self._delivery_player_colors: set[int] | None = None
        self._delivery_player_body_color: int | None = None
        self._delivery_items_remaining: list[int] = []
        self._delivery_used_slots: set[tuple[int, int]] = set()
        self._delivery_action_queue: list[int] = []
        self._delivery_carrying = False
        self._delivery_carry_offset: tuple[int, int] | None = None
        self._delivery_cycles_left = 0

    # ── harness contract ──────────────────────────────────────────────────────

    def is_done(self, frames: list, latest_frame) -> bool:
        """Stop on WIN, on a post-clear stall, on a GAME_OVER cycle, or out of budget.

        WIN is the biggest efficiency lever. The post-clear stall check
        (``POST_CLEAR_STALL``) banks the clears already won and stops the
        proven-futile tail of broad exploration once at least one level is
        cleared and no further level has been gained for the stall window.
        The GAME_OVER-cycle check (``GAME_OVER_CYCLE_LIMIT``) is a SEPARATE,
        earlier stop: a level whose unstructured probe/interact fallback
        repeatedly walks the env into GAME_OVER re-enters the identical
        phase after each RESET and repeats the same losing pattern — banking
        here has no ``levels_completed >= 1`` precondition, so it also
        covers a level that never clears at all (which POST_CLEAR_STALL
        cannot reach, since its precondition never fires).
        """
        if _state_name(latest_frame) == "WIN":
            return True
        if (
            self._levels_completed >= 1
            and self._action_count - self._last_progress_action >= POST_CLEAR_STALL
        ):
            return True
        if self._game_over_count >= GAME_OVER_CYCLE_LIMIT:
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
                # Rotation widget-candidate probe: log the (candidate, before,
                # after) so identify_moved_piece can attribute it to a piece.
                if p.get("rot_probe"):
                    self._rot_probe_log.append(
                        {"candidate": p["coord"], "before": p["before"], "after": layer.copy()}
                    )
                # Slider widget-candidate probe: log the (candidate, before,
                # after) so identify_moved_track can attribute it to a track.
                if p.get("slide_probe"):
                    self._slide_probe_log.append(
                        {"candidate": p["coord"], "before": p["before"], "after": layer.copy()}
                    )
                # Transform calibration press: log the (action_id, before,
                # after) so a fixed-colour sprite's measured shift builds the
                # direction map.
                if p.get("transform_calib"):
                    self._transform_calib_log.append(
                        {"action_id": p["action_id"], "before": p["before"], "after": layer.copy()}
                    )
                # Delivery calibration press: log the (action_id, before,
                # after) so the player's motion-classified shift builds the
                # direction map (see delivery.detect_mover_by_motion).
                if p.get("delivery_calib"):
                    self._delivery_calib_log.append(
                        {"action_id": p["action_id"], "before": p["before"], "after": layer.copy()}
                    )
            self._pending = None
        if leveled:
            self._levels_completed = lvl
            self._last_progress_action = self._action_count
            if self._transform_puzzle is not None:
                self._transform_prev_puzzle_key = frozenset(
                    (t.x, t.y, t.color) for t in self._transform_puzzle.targets
                )
            self._reset_level()

        if state == "GAME_OVER" or layer.size == 0 or not avail:
            self._pending = None
            if state == "GAME_OVER":
                self._game_over_count += 1
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
        if self._phase == _PHASE_SORT_MATCH:
            return self._sort_match_step(layer, avail, latest_frame)
        if self._phase == _PHASE_MERGE_DRAG:
            return self._merge_drag_step(layer, avail, latest_frame)
        if self._phase == _PHASE_ROTATE:
            return self._rotate_step(layer, avail, latest_frame)
        if self._phase == _PHASE_SLIDE:
            return self._slide_step(layer, avail, latest_frame)
        if self._phase == _PHASE_TRANSFORM:
            return self._transform_step(layer, avail, latest_frame)
        if self._phase == _PHASE_DELIVERY:
            return self._delivery_step(layer, avail, latest_frame)
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

        # Click-only MATCH-TO-ORDER sort signature: a SELECT toggle + an ACTION6
        # click are available but NO movement action is (a pure click game), and
        # the frame shows a top reference row + bottom pool row of matching
        # colours. This is the SB26-class sort puzzle — place each pool swatch
        # under its matching reference frame, then verify. Tried ONCE per level
        # (before any other discovery) since the layout is static; on failure
        # the phase abandons back to normal probing. Observation-gated, no
        # game-id reads. Movement games (1-4 present) and the arrangement class
        # (movement + toggle) never reach this branch.
        if (
            not self._sort_attempted
            and _SELECT_TOGGLE_ACTION in avail
            and 6 in avail
            and not any(a in avail for a in (1, 2, 3, 4))
        ):
            self._sort_attempted = True
            bg = self.model.background if self.model.background is not None else 0
            layout = detect_match_layout(layer, bg)
            if layout is not None:
                self._sort_plan = plan_match_placement(layout, _SELECT_TOGGLE_ACTION)
                self._phase = _PHASE_SORT_MATCH
                return self._sort_match_step(layer, avail, latest_frame)

        # Click-only SLIDER-PUZZLE signature: no movement action is available
        # and the frame holds an elongated, mostly-filled bar with a distinct
        # tip cell plus a candidate goal marker along its axis
        # (slider.detect_slider_puzzle). Tried BEFORE the rotation check
        # below: on the measured S5I5 board rotation's ambiguous fallback
        # structurally "succeeds" (every candidate ring matches some other
        # ring's interior shape at a perfect score) even though the true
        # mechanic is a slider, not a rotation — see slider.py's module
        # docstring for the live-trace evidence. A slider track's elongation
        # requirement (long axis >> short axis) cannot be satisfied by a
        # compact rotation-style frame+interior piece, so trying this first
        # does not cost a genuine rotation game anything. On failure the
        # phase falls through to the rotation check. Observation-gated, no
        # game-id reads.
        if (
            not self._slide_attempted
            and 6 in avail
            and not any(a in avail for a in (1, 2, 3, 4))
        ):
            self._slide_attempted = True
            bg = self.model.background if self.model.background is not None else 0
            slide_puzzle = detect_slider_puzzle(layer, bg)
            if slide_puzzle is not None:
                self._slider_puzzle = slide_puzzle
                return self._enter_slide(layer, avail, latest_frame)

        # Click-only ROTATION-PUZZLE signature: no movement action is available
        # (a pure click game, same discriminator as the sort/merge-drag classes
        # above/below) and the frame holds a frame+interior PIECE plus a
        # separate REFERENCE pattern (rotation.detect_rotation_puzzle). Tried
        # ONCE per level, right after the sort-layout check (a different
        # structural fingerprint — frame/interior pieces vs top/bottom matching
        # rows — so the two rarely both fire). On failure the phase abandons
        # back to normal probing. Observation-gated, no game-id reads.
        if (
            not self._rotation_attempted
            and 6 in avail
            and not any(a in avail for a in (1, 2, 3, 4))
        ):
            self._rotation_attempted = True
            bg = self.model.background if self.model.background is not None else 0
            puzzle = detect_rotation_puzzle(layer, bg)
            if puzzle is not None:
                self._rotation_puzzle = puzzle
                return self._enter_rotate(layer, avail, latest_frame)

        # Simple-action TRANSFORM-PUZZLE signature: a select-toggle
        # (ACTION5) AND at least one movement action are available, and the
        # frame holds ring+dot target markers plus a movable sprite of some
        # marker's exact colour (transform_route.detect_transform_puzzle).
        # Tried before movement discovery and before the generic ARRANGEMENT
        # gate below — RE86's large multi-sprite cross shapes are not a
        # single small "player" avatar, so letting movement discovery run
        # first would mislearn one cross as the player; the generic
        # arrangement descend-and-sweep model also does not apply (RE86
        # needs per-colour footprint coverage, not a row descent). On
        # failure the phase falls through to normal probing —
        # detect_transform_puzzle's own structural checks (ring markers +
        # matching-colour sprite) are the actual safety net, not this coarse
        # action-availability gate. Observation-gated, no game-id reads.
        if (
            not self._transform_attempted
            and 5 in avail
            and any(a in avail for a in (1, 2, 3, 4))
        ):
            bg = self.model.background if self.model.background is not None else 0
            transform_puzzle = detect_transform_puzzle(layer, bg)
            stale = False
            if transform_puzzle is not None and self._levels_completed >= 1 and spent == 0:
                # A level entered via a real transition can render its
                # FIRST frame still showing the PREVIOUS level's board —
                # measured on RE86 L2->L3: the previous level's board was
                # already fully SOLVED, yet still structurally "detected" as
                # a valid puzzle (the ring+dot markers stay visually present
                # regardless of whether they're already satisfied), so
                # "detection succeeded" alone cannot distinguish a genuine
                # new level from a stale one. The actual signal is an EXACT
                # match to the puzzle just solved (``_transform_prev_puzzle_key``,
                # captured in ``choose_action`` right before this level's
                # reset) — a coincidentally-identical BUT GENUINELY NEW
                # puzzle is not something this comparison can rule out, but
                # none has been measured; treating an exact repeat as stale
                # is the conservative, evidence-backed call.
                key = frozenset((t.x, t.y, t.color) for t in transform_puzzle.targets)
                stale = key == self._transform_prev_puzzle_key
            if transform_puzzle is not None and not stale:
                self._transform_attempted = True
                self._transform_puzzle = transform_puzzle
                return self._enter_transform(layer, avail, latest_frame)
            if self._levels_completed >= 1 and not self._transform_settle_tried and spent == 0:
                # Detection found nothing, or found only a stale repeat of
                # the just-solved puzzle — retry ONCE after a harmless
                # settle press instead of acting on stale data or
                # permanently giving up (see ``_transform_settle_tried`` in
                # ``_reset_level``).
                self._transform_settle_tried = True
                self._pending = {"action_id": 5, "coord": None, "before": layer.copy()}
                return self._emit(GameAction.from_id(5))
            self._transform_attempted = True

        # Simple-action DELIVERY (pick-carry-drop) signature: the SAME coarse
        # action-availability shape as TRANSFORM (ACTION5 + a movement
        # action) — the two puzzle families are disambiguated by their own
        # structural detectors, not by this gate. Tried right after the
        # transform gate so a transform-shaped board is never mis-routed
        # here (WA30's item markers have a solid multi-cell interior, not
        # transform_route's exactly-one-cell dot, so detect_transform_puzzle
        # already returns None for a genuine delivery board — see
        # delivery.py's module docstring). Observation-gated, no game-id
        # reads.
        if (
            not self._delivery_attempted
            and 5 in avail
            and any(a in avail for a in (1, 2, 3, 4))
        ):
            self._delivery_attempted = True
            bg = self.model.background if self.model.background is not None else 0
            delivery_puzzle = detect_delivery_puzzle(layer, bg)
            if delivery_puzzle is not None:
                self._delivery_puzzle = delivery_puzzle
                return self._enter_delivery(layer, avail, latest_frame)

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
        # Enter EXECUTE unconditionally on a navigate goal and let
        # _execute_step's own candidate rotation (_plan_to_current_goal /
        # _advance_goal) build the first plan, rather than computing one shot
        # here and bailing straight to interact on an empty result. Measured
        # bug (ls20 L2, 2026-07-13): infer_goal's completion_target_colors
        # memory (a colour that changed at a PAST level's completion) can
        # force target_color to a colour that is real but not a goal on the
        # NEW level (measured: a 3px decorative speck), producing a single
        # empty plan_navigation() call with no recovery. enumerate_goal_cells
        # (which _plan_to_current_goal uses) takes no target_color bias at
        # all, so routing through the existing rotation machinery here gives
        # every candidate a chance instead of abandoning after one bad guess.
        if not self._nav_attempted:
            self._nav_attempted = True
            self.goal = infer_goal(layer, self.model)
            if self.goal.kind == "navigate":
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

        # No controllable player, but a click (ACTION6) + a cancel/undo
        # (ACTION7) are available with NO movement and NO selection toggle, AND
        # the frame shows a few small movable tiles plus a distinct goal region →
        # this is the click-drag MERGE / gather class (SU15: a click pulls nearby
        # tiles toward the click point, same-colour tiles overlapping merge into
        # the next tile, and a tile is walked into the goal container). Try this
        # BEFORE the blind-click handoff: detect the layout, probe the drag
        # hypothesis with one short test click, and commit to the merge/gather
        # only if that click moved the tile. The ACTION7 (undo) signal is the
        # discriminator from the pure-click TOGGLE panels (FT09 / TN36 expose
        # ACTION6 only): a manipulation game offers an undo, a toggle grid does
        # not. Movement classes keep the nav path; toggle/arrangement/sort
        # classes are handled above. Observation-only, no game-id reads.
        if (
            self.model.player_color is None
            and 6 in avail
            and 7 in avail
            and not any(a in avail for a in (1, 2, 3, 4, 5))
            and not self._merge_drag_attempted
        ):
            bg = self.model.background if self.model.background is not None else 0
            layout = detect_drag_layout(layer, bg)
            if layout is not None:
                self._merge_drag_attempted = True
                self._phase = _PHASE_MERGE_DRAG
                self._merge_drag_clicks = 0
                self._merge_drag_probed = False
                self._merge_drag_stall = 0
                x, y = drag_probe_target(layout)
                self._pending = {
                    "action_id": 6, "coord": (x, y),
                    "before": layer.copy(), "desc": ("c", x, y),
                }
                return self._emit_click(x, y)

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
        # cell it tried to enter LOOKS like a wall the static pixel heuristic
        # missed. A single such reading can be spurious (see _pending_block's
        # docstring), so the candidate cell must reproduce on a same-action
        # RETRY (the cleared plan replans identically since nothing in the
        # walkability model changed yet, naturally re-attempting the same
        # first move) before it is committed to _blocked_cells. A player
        # stuck even after learning confirmed blocks rotates to the NEXT goal
        # candidate (multi-target levels) rather than bailing immediately.
        if (
            self._exec_prev_cell is not None
            and self._exec_aid is not None
            and cur_cell is not None
        ):
            step = self.model.step_dirs().get(self._exec_aid)
            if step is not None and cur_cell == self._exec_prev_cell:
                wall = (self._exec_prev_cell[0] + step[1], self._exec_prev_cell[1] + step[0])
                if wall == self._pending_block:
                    self._blocked_cells.add(wall)
                    self._pending_block = None
                    self._exec_stuck += 1
                else:
                    self._pending_block = wall
                self._plan = []
            elif cur_cell != self._exec_prev_cell:
                self._exec_stuck = 0
                self._pending_block = None

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

    # ── sort (click-only match-to-order placement) phase ──────────────────────

    def _sort_match_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Drain the match-to-order placement plan one action per call.

        Each plan entry is ``("click", x, y)`` (an ACTION6 placement click) or
        ``("simple", aid)`` (the verify action). When the plan is exhausted the
        level either cleared (the harness sees the level-up and resets) or the
        layout guess was wrong, so control returns to normal interaction rather
        than looping the sort — the plan is short (~human-baseline length) and
        tried once, so a wrong guess costs little. A click whose ACTION6 is gone
        or a simple action no longer available is skipped, keeping the drain
        robust to the verify-animation frames the env interleaves.
        """
        from arcengine import GameAction

        while self._sort_plan:
            kind, *rest = self._sort_plan.pop(0)
            if kind == "click":
                x, y = rest
                if 6 not in avail:
                    continue
                self._pending = {
                    "action_id": 6,
                    "coord": (int(x), int(y)),
                    "before": layer.copy(),
                    "desc": ("c", int(x), int(y)),
                }
                return self._emit_click(int(x), int(y))
            aid = rest[0]
            if aid not in avail:
                continue
            self._pending = {"action_id": aid, "coord": None, "before": layer.copy()}
            return self._emit(GameAction.from_id(aid))

        # Plan exhausted without a level-up → the layout guess did not clear;
        # fall through to the standard interaction pipeline for the remaining
        # budget (the sort phase is not re-entered: _sort_attempted is set).
        self._plan_commit = self._action_count
        self._phase = _PHASE_INTERACT
        return self._interact_step(layer, avail, latest_frame)

    # ── merge-drag (click-only gather to goal) phase ───────────────────────────

    def _merge_drag_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """One action of the click-drag gather: confirm the pull, then walk.

        The phase is entered with a TEST click already issued (the drag probe).
        The first call here reads ``_last_changed`` (the model credited that
        probe before dispatch): if the test click did not change the frame the
        drag hypothesis is FALSE for this game, so the phase abandons to the
        standard interaction pipeline rather than wasting the walk budget. With
        the pull confirmed, each call recomputes :func:`next_drag_click` from the
        LIVE frame (robust to the multi-frame drag animation and to a tile that
        merged mid-walk) and clicks one short step ahead of the goal-farthest
        tile, gathering every tile into the goal region. The harness checks the
        live level-up after each click, so the walk stops the instant the gather
        clears the level. Bails to interaction when the gather is complete
        (nothing left to drag), the walk cap is hit, OR a tile has stopped
        responding to the pull for :data:`_MERGE_DRAG_STALL_LIMIT` consecutive
        clicks (see its docstring — re-clicking a genuinely stuck tile is not
        free, it walks the env toward GAME_OVER).
        """
        bg = self.model.background if self.model.background is not None else 0
        if self._merge_drag_reset_pending:
            # Just RESET for a goal switch (see _try_next_merge_goal): the
            # board is back to the level's pristine layout. Issue the new
            # goal's probe click directly — do not consult _last_changed,
            # which reflects the RESET action, not a real probe.
            self._merge_drag_reset_pending = False
            layout = detect_drag_layout(layer, bg, goal_override=self._merge_drag_goal)
            if layout is not None:
                x, y = drag_probe_target(layout)
                self._pending = {
                    "action_id": 6, "coord": (x, y),
                    "before": layer.copy(), "desc": ("c", x, y),
                }
                return self._emit_click(x, y)
            self._plan_commit = self._action_count
            self._phase = _PHASE_INTERACT
            return self._interact_step(layer, avail, latest_frame)
        current_tiles = _merge_drag_tile_snapshot(layer, bg)
        if not self._merge_drag_probed:
            self._merge_drag_probed = True
            if not self._last_changed:
                # The test click pulled nothing → not a drag game against THIS
                # goal. Try the other goal container before giving up entirely.
                return self._try_next_merge_goal(layer, avail, latest_frame, bg)
        elif self._merge_drag_clicks > 0:
            # A walk click was just credited (not the initial probe): track
            # whether the TRACKED TILES actually moved, not whether the whole
            # frame changed (a HUD/counter region can tick every click while
            # the tiles sit dead-still — see this method's stall-tracking
            # comment above).
            if current_tiles != self._merge_drag_last_tiles:
                self._merge_drag_stall = 0
            else:
                self._merge_drag_stall += 1

        if (
            6 in avail
            and self._merge_drag_clicks < _MERGE_DRAG_MAX_CLICKS
            and self._merge_drag_stall < _MERGE_DRAG_STALL_LIMIT
        ):
            cell = next_merge_click(layer, bg, goal_override=self._merge_drag_goal)
            if cell is not None:
                self._merge_drag_clicks += 1
                self._merge_drag_last_tiles = current_tiles
                x, y = cell
                self._pending = {
                    "action_id": 6, "coord": (x, y),
                    "before": layer.copy(), "desc": ("c", x, y),
                }
                return self._emit_click(x, y)

        # Gather complete (no tile left outside the goal) or cap reached without
        # a level-up. "Complete" can mean the gather genuinely finished with no
        # goal, OR every tile sits close to a goal that just never accepts them
        # (measured on SU15: a 2-goal board where the wrong goal is targeted by
        # default) — try the other goal before handing the budget to interact.
        return self._try_next_merge_goal(layer, avail, latest_frame, bg)

    def _try_next_merge_goal(
        self, layer: np.ndarray, avail: list[int], latest_frame, bg: int
    ):
        """Retry the merge-drag gather against an untried goal, or abandon.

        A board can render MORE THAN ONE goal-coloured container (measured on
        SU15 L3: two distinct diamonds); `detect_drag_layout`'s default picks
        only ONE (the largest/rarest cluster), and that pick is not always the
        one a given level's puzzle wants — tiles walk right up to it and just
        never get accepted, or the initial probe never even pulls. Marks the
        currently-targeted goal as tried, looks for another instance via
        `detect_goal_containers`, and if one exists, restarts the probe/walk
        cycle against it (fresh probe click, reset click/stall counters).
        Falls through to the standard interaction pipeline once every goal
        instance has been tried. Coordinates are matched by rounding to avoid
        float-precision misses on a container that hasn't moved between calls.
        Switching goals RESETs the board first (see the inline comment where
        that happens) so the new goal's attempt starts from the level's
        pristine layout, not one already disturbed by the abandoned attempt.
        """
        from arcengine import GameAction

        def _key(pt: tuple[float, float]) -> tuple[float, float]:
            return (round(pt[0], 1), round(pt[1], 1))

        current = self._merge_drag_goal
        if current is None:
            layout = detect_drag_layout(layer, bg)
            current = layout.goal if layout is not None else None
        if current is not None and _key(current) not in {
            _key(g) for g in self._merge_drag_tried_goals
        }:
            self._merge_drag_tried_goals.append(current)

        candidates = detect_goal_containers(layer, bg)
        tried_keys = {_key(g) for g in self._merge_drag_tried_goals}
        next_goal = next(
            (
                (c[0], c[1])
                for c in candidates
                if _key((c[0], c[1])) not in tried_keys
            ),
            None,
        )
        if next_goal is not None:
            self._merge_drag_goal = next_goal
            self._merge_drag_clicks = 0
            self._merge_drag_stall = 0
            self._merge_drag_probed = False
            # RESET back to the level's pristine layout before trying the new
            # goal. Measured live: the gather sequence that clears the level
            # against goal B only works from a CLEAN board — a live retry that
            # switches goals mid-sequence (after goal A's attempt already
            # dragged tiles around) starts goal B's walk from a DISTURBED
            # layout and diverges from the first gather click onward, ending
            # in GAME_OVER instead of the clear a fresh-board attempt
            # achieves. RESET does not affect levels_completed or the
            # knowledge already accumulated (which goal was tried), only the
            # board's pixel layout — confirmed by the existing GAME_OVER
            # handling elsewhere in this class, which relies on the same
            # fact. `_merge_drag_reset_pending` tells the next call to issue
            # the goal's probe click directly instead of re-checking a stale
            # `_last_changed` credited to the RESET itself.
            self._merge_drag_reset_pending = True
            self._pending = None
            return self._emit(GameAction.RESET)

        self._plan_commit = self._action_count
        self._phase = _PHASE_INTERACT
        return self._interact_step(layer, avail, latest_frame)

    # ── rotation-puzzle (click-exactly, attempt-limited) phase ────────────────

    def _enter_rotate(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Begin the rotation phase: schedule the widget-candidate probe queue.

        ``self._rotation_puzzle`` was just detected by
        :func:`rotation.detect_rotation_puzzle`; its ``candidates`` (piece +
        reference centroids) become the probe queue Stage 1 of
        :meth:`_rotate_step` drains one click at a time.
        """
        self._phase = _PHASE_ROTATE
        self._plan_commit = self._action_count
        self._rot_probe_queue = list(self._rotation_puzzle.candidates)
        self._rot_probe_log = []
        self._rot_probe_processed = 0
        self._rot_widget_for_piece = {}
        self._rot_commit_queue = None
        self._rot_active_piece = None
        self._rot_clicks_left = 0
        return self._rotate_step(layer, avail, latest_frame)

    def _rotate_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """One action of the rotation phase: probe widgets, then click-exactly.

        Stage 1 — fold every newly-credited probe result (appended to
        ``_rot_probe_log`` by the ``choose_action`` credit block) into
        ``_rot_widget_for_piece`` via :func:`identify_moved_piece`, then issue
        the next untried candidate click, but ONLY while a piece with an
        assigned target still lacks a known widget — once every such piece is
        resolved (or the candidate queue runs dry) the probe stops so no
        attempt-counter budget is wasted on candidates that cannot help.
        Stage 2 — work the queue of target-bearing, widget-known pieces one at
        a time: click the active piece's widget, then on the NEXT call check
        the LIVE frame (:func:`piece_matches_target`) before clicking again,
        stopping at a match or at :data:`rotation.MAX_COMMIT_CLICKS_PER_PIECE`
        additional clicks (never re-probes, never clicks anything else — the
        attempt counter punishes any other click). Falls through to normal
        interaction once every resolvable piece is done.
        """
        puzzle = self._rotation_puzzle

        # Stage 1a: fold newly-credited probe results into the widget map.
        while self._rot_probe_processed < len(self._rot_probe_log):
            entry = self._rot_probe_log[self._rot_probe_processed]
            self._rot_probe_processed += 1
            idx = identify_moved_piece(puzzle.pieces, entry["before"], entry["after"])
            if idx is not None and idx not in self._rot_widget_for_piece:
                self._rot_widget_for_piece[idx] = entry["candidate"]

        needs_widget = [
            i
            for i, t in enumerate(puzzle.targets)
            if t is not None and i not in self._rot_widget_for_piece
        ]

        # Stage 1b: probe the next untried candidate, only while some
        # target-bearing piece still lacks a known widget.
        if needs_widget and self._rot_probe_queue and 6 in avail:
            x, y = self._rot_probe_queue.pop(0)
            self._pending = {
                "action_id": 6,
                "coord": (x, y),
                "before": layer.copy(),
                "rot_probe": True,
            }
            return self._emit_click(x, y)

        # Stage 2: click-exactly commit, one piece at a time.
        if self._rot_commit_queue is None:
            self._rot_commit_queue = [
                i
                for i, t in enumerate(puzzle.targets)
                if t is not None and i in self._rot_widget_for_piece
            ]

        if self._rot_active_piece is None:
            if not self._rot_commit_queue:
                self._plan_commit = self._action_count
                self._phase = _PHASE_INTERACT
                return self._interact_step(layer, avail, latest_frame)
            self._rot_active_piece = self._rot_commit_queue.pop(0)
            self._rot_clicks_left = MAX_COMMIT_CLICKS_PER_PIECE

        piece_idx = self._rot_active_piece
        piece = puzzle.pieces[piece_idx]
        target = puzzle.targets[piece_idx]
        if target is not None and piece_matches_target(piece, layer, target):
            # This piece is done — move on to the next without spending a click.
            self._rot_active_piece = None
            return self._rotate_step(layer, avail, latest_frame)
        if self._rot_clicks_left <= 0 or 6 not in avail:
            self._rot_active_piece = None
            return self._rotate_step(layer, avail, latest_frame)

        self._rot_clicks_left -= 1
        x, y = self._rot_widget_for_piece[piece_idx]
        self._pending = {
            "action_id": 6,
            "coord": (x, y),
            "before": layer.copy(),
            "desc": ("c", x, y),
        }
        return self._emit_click(x, y)

    # ── slider-puzzle (grow-to-marker, attempt-limited) phase ─────────────────

    def _enter_slide(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Begin the slide phase: schedule the widget-candidate probe queue.

        Mirrors :meth:`_enter_rotate` exactly: ``self._slider_puzzle`` was
        just detected by :func:`slider.detect_slider_puzzle`; its
        ``candidates`` (button centroids) become the probe queue Stage 1 of
        :meth:`_slide_step` drains one click at a time.
        """
        self._phase = _PHASE_SLIDE
        self._plan_commit = self._action_count
        self._slide_probe_queue = list(self._slider_puzzle.candidates)
        self._slide_probe_log = []
        self._slide_probe_processed = 0
        self._slide_track_buttons = {}
        self._slide_track_steps = {}
        self._slide_commit_queue = None
        self._slide_active_track = None
        self._slide_goal = None
        self._slide_clicks_left = 0
        return self._slide_step(layer, avail, latest_frame)

    def _slide_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """One action of the slide phase: probe buttons, then click-to-goal.

        Stage 1 — fold every newly-credited probe result (appended to
        ``_slide_probe_log`` by the ``choose_action`` credit block) into
        ``_slide_track_buttons``/``_slide_track_steps`` via
        :func:`identify_moved_track`, then issue the next untried candidate
        click, but ONLY while some track still lacks a discovered "grow"
        button — once every track has one (or the candidate queue runs dry)
        the probe stops. Stage 2 — work the queue of tracks with a discovered
        grow button one at a time: resolve its goal
        (:func:`resolve_goal`), compute the MEASURED click count
        (:func:`clicks_needed`, from the probe's own step measurement — never
        assumed), and click the grow widget that many times, re-checking the
        LIVE tip position (:func:`track_reached_goal`) before each click so a
        track that reaches its goal early stops immediately. A track with no
        resolvable goal, or whose grow button was never discovered, is
        skipped without spending a click on it. Falls through to normal
        interaction once every resolvable track is done.
        """
        puzzle = self._slider_puzzle

        # Stage 1a: fold newly-credited probe results into the button map.
        while self._slide_probe_processed < len(self._slide_probe_log):
            entry = self._slide_probe_log[self._slide_probe_processed]
            self._slide_probe_processed += 1
            result = identify_moved_track(puzzle.tracks, entry["before"], entry["after"])
            if result is not None:
                idx, step, direction = result
                buttons = self._slide_track_buttons.setdefault(idx, {})
                if direction not in buttons:
                    buttons[direction] = entry["candidate"]
                    self._slide_track_steps.setdefault(idx, {})[direction] = step

        needs_probe = [
            i
            for i in range(len(puzzle.tracks))
            if "grow" not in self._slide_track_buttons.get(i, {})
        ]

        # Stage 1b: probe the next untried candidate, only while some track
        # still lacks a discovered grow button.
        if needs_probe and self._slide_probe_queue and 6 in avail:
            x, y = self._slide_probe_queue.pop(0)
            self._pending = {
                "action_id": 6,
                "coord": (x, y),
                "before": layer.copy(),
                "slide_probe": True,
            }
            return self._emit_click(x, y)

        # Stage 2: click-to-goal commit, one track at a time.
        if self._slide_commit_queue is None:
            self._slide_commit_queue = [
                i
                for i in range(len(puzzle.tracks))
                if "grow" in self._slide_track_buttons.get(i, {})
            ]

        if self._slide_active_track is None:
            if not self._slide_commit_queue:
                self._plan_commit = self._action_count
                self._phase = _PHASE_INTERACT
                return self._interact_step(layer, avail, latest_frame)
            idx = self._slide_commit_queue.pop(0)
            track = puzzle.tracks[idx]
            goal = resolve_goal(track, puzzle.markers[idx])
            step = self._slide_track_steps.get(idx, {}).get("grow", 0)
            n = clicks_needed(track, goal, step) if goal is not None else 0
            if goal is None or n <= 0:
                # No resolvable goal, or a non-positive measured step — skip
                # this track without spending a click on it.
                return self._slide_step(layer, avail, latest_frame)
            self._slide_active_track = idx
            self._slide_goal = goal
            self._slide_clicks_left = n

        idx = self._slide_active_track
        track = puzzle.tracks[idx]
        if track_reached_goal(layer, track, self._slide_goal):
            # This track is done — move on to the next without spending a click.
            self._slide_active_track = None
            return self._slide_step(layer, avail, latest_frame)
        if self._slide_clicks_left <= 0 or 6 not in avail:
            self._slide_active_track = None
            return self._slide_step(layer, avail, latest_frame)

        self._slide_clicks_left -= 1
        x, y = self._slide_track_buttons[idx]["grow"]
        self._pending = {
            "action_id": 6,
            "coord": (x, y),
            "before": layer.copy(),
            "desc": ("c", x, y),
        }
        return self._emit_click(x, y)

    # ── transform-puzzle (per-colour footprint coverage) phase ────────────────

    def _enter_transform(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Begin the transform phase: identify the active sprite, schedule calibration.

        ``self._transform_puzzle`` was just detected by
        :func:`transform_route.detect_transform_puzzle`.
        :func:`transform_route.find_active_color` reads which sprite is
        currently controllable straight from the frame (no probe needed);
        that FIXED colour is calibrated against ACTION1-4 in
        :meth:`_transform_step`'s Stage 0.

        If the naively-detected active sprite's own bbox is implausibly
        large (:func:`transform_route.sprite_bbox_implausible`), Stage 0/2
        switch to motion-based reclassification
        (:func:`transform_route.detect_sprite_by_motion`) instead of trusting
        the (potentially decoration-corrupted) whole-layer colour cluster —
        see ``_transform_motion_mode``'s comment in ``_reset_level``.
        """
        self._phase = _PHASE_TRANSFORM
        self._plan_commit = self._action_count
        bg = self.model.background if self.model.background is not None else 0
        self._transform_active_color = find_active_color(
            layer, bg, self._transform_puzzle.sprites
        )
        active_sprite = next(
            (s for s in self._transform_puzzle.sprites if s.color == self._transform_active_color),
            None,
        )
        self._transform_motion_mode = active_sprite is not None and sprite_bbox_implausible(
            active_sprite, layer.shape
        )
        self._transform_last_calib_pair = None
        self._transform_dir_map = {}
        self._transform_step_size = 0
        self._transform_calib_queue = [aid for aid in (1, 2, 3, 4) if aid in avail]
        self._transform_calib_log = []
        self._transform_calib_processed = 0
        self._transform_colors_needed = {t.color for t in self._transform_puzzle.targets}
        self._transform_move_queue = []
        # A generous hard safety backstop (not the primary termination — see
        # _transform_seen_active): measured on RE86 L2, ACTION5 needed 2
        # presses to reach one sprite's turn, so "at most len(sprites)
        # presses total" undercounts. 4x sprite count matches that measured
        # overhead with margin.
        self._transform_cycles_left = len(self._transform_puzzle.sprites) * 4
        self._transform_seen_active = set()
        return self._transform_step(layer, avail, latest_frame)

    def _transform_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """One action of the transform phase: calibrate, then place-and-cycle.

        Stage 0 — fold every newly-credited calibration press (appended to
        ``_transform_calib_log`` by the ``choose_action`` credit block) into
        ``_transform_dir_map`` by re-measuring the FIXED
        ``_transform_active_color`` sprite's centroid shift, then issue the
        next queued calibration press. Once drained, derive the MEASURED
        step size (:func:`admorphiq.general_agent._step_cell_size`, reused —
        never assumed).
        Stage 1 — drain any queued move sequence for the sprite just
        committed, one action per call.
        Stage 2 — with no queue pending, re-read which sprite is NOW active
        (:func:`transform_route.find_active_color`, a fresh single-frame
        read — an ACTION5 cycle costs no extra probe click to identify).
        If it is still needed, plan its move
        (:func:`transform_route.find_covering_offset` +
        :func:`transform_route.build_move_actions`) and queue it; a colour
        with no computable offset is given up on (no changer routing — see
        transform_route.py's module docstring) rather than retried
        speculatively. Otherwise press ACTION5 to cycle — termination is
        primarily by ``_transform_seen_active`` (stop once a cycle position
        repeats without new progress; reset every time a colour is placed
        or given up on), with ``_transform_cycles_left`` as a generous hard
        safety backstop, so a puzzle this module cannot fully solve still
        falls through to normal interaction instead of looping.
        """
        from arcengine import GameAction

        bg = self.model.background if self.model.background is not None else 0
        puzzle = self._transform_puzzle
        target_colors = {t.color for t in puzzle.targets}

        # Stage 0a: fold newly-credited calibration presses into the dir_map.
        # Motion mode (see ``_enter_transform``) replaces the naive
        # whole-layer colour cluster with the motion-classified vacated/
        # arrived pair, immune to same-colour decoration by construction
        # (the excluded cells were never in its input domain — see
        # transform_route.detect_sprite_by_motion).
        while self._transform_calib_processed < len(self._transform_calib_log):
            entry = self._transform_calib_log[self._transform_calib_processed]
            self._transform_calib_processed += 1
            if self._transform_motion_mode:
                pair = detect_sprite_by_motion(
                    entry["before"], entry["after"], self._transform_active_color
                )
                if pair is not None:
                    self._transform_last_calib_pair = (entry["before"], entry["after"])
                    sprite_before, sprite_after = pair
                    dx, dy = snap_to_axis(
                        sprite_after.cx - sprite_before.cx, sprite_after.cy - sprite_before.cy
                    )
                    if dx or dy:
                        self._transform_dir_map[entry["action_id"]] = (dx, dy)
                continue
            before_sprites = detect_sprite_candidates(
                entry["before"], bg, {self._transform_active_color}
            )
            after_sprites = detect_sprite_candidates(
                entry["after"], bg, {self._transform_active_color}
            )
            if before_sprites and after_sprites:
                dx = round(after_sprites[0].cx - before_sprites[0].cx)
                dy = round(after_sprites[0].cy - before_sprites[0].cy)
                if dx or dy:
                    self._transform_dir_map[entry["action_id"]] = (dx, dy)

        # Stage 0b: issue the next calibration press.
        if self._transform_calib_queue:
            aid = self._transform_calib_queue.pop(0)
            if aid not in avail:
                return self._transform_step(layer, avail, latest_frame)
            self._pending = {
                "action_id": aid,
                "coord": None,
                "before": layer.copy(),
                "transform_calib": True,
            }
            return self._emit(GameAction.from_id(aid))

        if self._transform_step_size == 0:
            self._transform_step_size = _step_cell_size(self._transform_dir_map)
            if self._transform_step_size <= 0 or not self._transform_dir_map:
                # Calibration found no measurable movement at all — this
                # sprite/level does not fit the model; fall through.
                self._plan_commit = self._action_count
                self._phase = _PHASE_INTERACT
                return self._interact_step(layer, avail, latest_frame)

        # Stage 1: drain a queued move sequence for the committed sprite.
        if self._transform_move_queue:
            aid = self._transform_move_queue.pop(0)
            if aid not in avail:
                self._transform_move_queue = []
                return self._transform_step(layer, avail, latest_frame)
            self._pending = {"action_id": aid, "coord": None, "before": layer.copy()}
            return self._emit(GameAction.from_id(aid))

        # Stage 2: plan the currently active sprite, or cycle to the next.
        # find_active_color only inspects a small window around each
        # candidate's own centroid (see its docstring), so it stays reliable
        # even off the naive (possibly decoration-corrupted) cluster list;
        # only the FULL FOOTPRINT used for offset search needs the motion
        # substitution below.
        live_sprites = detect_sprite_candidates(layer, bg, target_colors)
        active_color = find_active_color(layer, bg, live_sprites)
        if active_color is not None and active_color in self._transform_colors_needed:
            sprite = next((s for s in live_sprites if s.color == active_color), None)
            if (
                self._transform_motion_mode
                and active_color == self._transform_active_color
                and self._transform_last_calib_pair is not None
            ):
                # Re-derive the CURRENT live footprint by motion rather than
                # trusting the naive cluster for this (measured-implausible)
                # colour — ``_transform_last_calib_pair``'s "after" frame is
                # the frame this very call is running on (Stage 0 just folded
                # it, no intervening action), so its arrived-cell cluster is
                # the sprite's footprint AT THE CURRENT position.
                pair = detect_sprite_by_motion(
                    self._transform_last_calib_pair[0],
                    self._transform_last_calib_pair[1],
                    active_color,
                )
                if pair is not None:
                    sprite = pair[1]
            offset = None
            if sprite is not None:
                points = [t for t in puzzle.targets if t.color == active_color]
                offset = find_covering_offset(sprite, points, self._transform_step_size)
            moves = (
                build_move_actions(offset[0], offset[1], self._transform_dir_map, self._transform_step_size)
                if offset is not None
                else []
            )
            if moves:
                self._transform_move_queue = moves
                self._transform_colors_needed.discard(active_color)
                self._transform_seen_active = set()
                return self._transform_step(layer, avail, latest_frame)
            # No computable offset for this colour (needs a changer, or is
            # otherwise unreachable by direct placement) — give up on it,
            # never retried speculatively.
            self._transform_colors_needed.discard(active_color)
            self._transform_seen_active = set()

        # A cycle position that is neither processable now nor NEW tells us
        # we have looped all the way around (back to an active colour we
        # already passed through) without further progress — stop. Measured
        # necessary on RE86 L2: ACTION5 can pass through more distinct
        # active states than there are sprites (2 presses were needed to
        # reach one sprite's turn), so a naive "at most len(sprites) presses"
        # bound gave up before ever reaching a genuinely needed colour.
        # ``_transform_cycles_left`` remains a generous hard safety backstop
        # against a truly unbounded cycle, not the primary termination
        # signal — this seen-set check is.
        if active_color in self._transform_seen_active:
            self._plan_commit = self._action_count
            self._phase = _PHASE_INTERACT
            return self._interact_step(layer, avail, latest_frame)
        self._transform_seen_active.add(active_color)

        if not self._transform_colors_needed or self._transform_cycles_left <= 0 or 5 not in avail:
            self._plan_commit = self._action_count
            self._phase = _PHASE_INTERACT
            return self._interact_step(layer, avail, latest_frame)

        self._transform_cycles_left -= 1
        self._pending = {"action_id": 5, "coord": None, "before": layer.copy()}
        return self._emit(GameAction.from_id(5))

    # ── delivery (pick-carry-drop) phase ───────────────────────────────────────

    def _enter_delivery(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Begin the delivery phase: schedule player motion calibration.

        ``self._delivery_puzzle`` was just detected by
        :func:`delivery.detect_delivery_puzzle`. The player's own colours
        are not assumed (WA30's leading-edge accent relocates to whichever
        side faces the last move — see delivery.py's module docstring), so
        Stage 0 (:meth:`_delivery_step`) motion-calibrates against ACTION1-4
        the same way :meth:`_enter_transform` calibrates a sprite, deriving
        both the direction map AND the player's own colour set from
        whichever cells changed state under each press.
        """
        self._phase = _PHASE_DELIVERY
        self._plan_commit = self._action_count
        self._delivery_dir_map = {}
        self._delivery_step_size = 0
        self._delivery_calib_queue = [aid for aid in (1, 2, 3, 4) if aid in avail]
        self._delivery_calib_log = []
        self._delivery_calib_processed = 0
        self._delivery_player_colors = None
        self._delivery_player_body_color = None
        self._delivery_items_remaining = list(range(len(self._delivery_puzzle.items)))
        self._delivery_used_slots = set()
        self._delivery_action_queue = []
        self._delivery_carrying = False
        self._delivery_carry_offset = None
        # Generous hard safety backstop (not the primary termination — the
        # phase already ends naturally once every item is delivered or a
        # remaining item/delivery proves unreachable): one decrement per
        # sub-task attempt (a pickup leg or a delivery leg), so 2x the item
        # count covers a clean run with margin for a few give-ups.
        self._delivery_cycles_left = len(self._delivery_puzzle.items) * 4
        return self._delivery_step(layer, avail, latest_frame)

    def _delivery_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """One action of the delivery phase: calibrate, then fetch-and-deliver.

        Stage 0 — fold every newly-credited calibration press into
        ``_delivery_dir_map`` via :func:`delivery.detect_mover_by_motion`
        (excluding the known item/target ring+interior colours), and record
        the player's own colour set from the first successful press. Once
        drained, derive the measured step size.
        Stage 1 — drain any queued action sequence for the sub-task
        currently in flight (a fetch-and-pickup leg, or a carry-and-drop
        leg), one action per call.
        Stage 2 — with no queue pending, locate the player on the LIVE frame
        by its own colour set (orientation-independent — see the module
        docstring) and plan the next sub-task: if carrying, BFS to the
        nearest free target slot (accounting for the carried item's FIXED
        pickup-time offset — :func:`delivery.bfs_path`'s ``item_offset``)
        and queue a drop; otherwise BFS to the nearest remaining item's
        adjacent cell, face it, and queue a pickup. A leg that turns out
        unreachable gives up on that specific item (never retried
        speculatively, mirroring transform_route.py's same discipline) and
        the phase moves on; the whole phase falls through to normal
        interaction once nothing remains to plan or ``_delivery_cycles_left``
        is exhausted.
        """
        from arcengine import GameAction

        bg = self.model.background if self.model.background is not None else 0
        puzzle = self._delivery_puzzle
        known_colors: set[int] = set()
        for m in puzzle.items + puzzle.targets:
            known_colors.add(m.ring_color)
            known_colors.add(m.interior_color)

        # Stage 0a: fold newly-credited calibration presses.
        while self._delivery_calib_processed < len(self._delivery_calib_log):
            entry = self._delivery_calib_log[self._delivery_calib_processed]
            self._delivery_calib_processed += 1
            pair = detect_mover_by_motion(entry["before"], entry["after"], known_colors, bg)
            if pair is not None:
                mover_before, mover_after = pair
                dx, dy = snap_to_axis(
                    mover_after.cx - mover_before.cx, mover_after.cy - mover_before.cy
                )
                if dx or dy:
                    self._delivery_dir_map[entry["action_id"]] = (dx, dy)
                if self._delivery_player_colors is None:
                    color_counts = Counter(
                        int(entry["after"][y, x]) for x, y in mover_after.cells
                    )
                    self._delivery_player_colors = set(color_counts)
                    # The player's "body" colour is the LARGER of its two
                    # sub-colours (measured WA30: 12 cells vs the 4-cell
                    # leading-edge accent) — used exclusively for locating
                    # the player once carrying, when the SMALLER colour is
                    # no longer player-exclusive: a picked-up item is ALSO
                    # rendered in it (measured: the item's own ring, still
                    # its own colour before pickup, becomes this same
                    # accent colour once carried), so a colour-mask lookup
                    # against the full set would include the carried item's
                    # cells and undershoot the player's true position by
                    # exactly one grid step toward the carry direction.
                    self._delivery_player_body_color = color_counts.most_common(1)[0][0]

        # Stage 0b: issue the next calibration press.
        if self._delivery_calib_queue:
            aid = self._delivery_calib_queue.pop(0)
            if aid not in avail:
                return self._delivery_step(layer, avail, latest_frame)
            self._pending = {
                "action_id": aid,
                "coord": None,
                "before": layer.copy(),
                "delivery_calib": True,
            }
            return self._emit(GameAction.from_id(aid))

        if self._delivery_step_size == 0:
            self._delivery_step_size = _step_cell_size(self._delivery_dir_map)
            if (
                self._delivery_step_size <= 0
                or not self._delivery_dir_map
                or not self._delivery_player_colors
            ):
                # Calibration found no measurable player movement at all —
                # this board does not fit the model; fall through.
                self._plan_commit = self._action_count
                self._phase = _PHASE_INTERACT
                return self._interact_step(layer, avail, latest_frame)

        # Stage 1: drain a queued action sequence for the sub-task in flight.
        if self._delivery_action_queue:
            aid = self._delivery_action_queue.pop(0)
            if aid not in avail:
                self._delivery_action_queue = []
                return self._delivery_step(layer, avail, latest_frame)
            self._pending = {"action_id": aid, "coord": None, "before": layer.copy()}
            return self._emit(GameAction.from_id(aid))

        # Stage 2: plan the next sub-task, or fall through when nothing is
        # left to plan.
        if self._delivery_cycles_left <= 0 or (
            not self._delivery_carrying and not self._delivery_items_remaining
        ):
            self._plan_commit = self._action_count
            self._phase = _PHASE_INTERACT
            return self._interact_step(layer, avail, latest_frame)

        step = self._delivery_step_size
        bounds = layer.shape
        accent_colors = self._delivery_player_colors - {self._delivery_player_body_color}
        player_cell = locate_player_cell(layer, self._delivery_player_body_color, accent_colors)
        if player_cell is None:
            self._plan_commit = self._action_count
            self._phase = _PHASE_INTERACT
            return self._interact_step(layer, avail, latest_frame)
        by_delta = {delta: aid for aid, delta in self._delivery_dir_map.items()}

        if self._delivery_carrying:
            offset = self._delivery_carry_offset
            item_cells_blocked = {
                bbox_min_corner(puzzle.items[i].cells) for i in self._delivery_items_remaining
            }
            free_slots = [
                slot
                for t in puzzle.targets
                for slot in target_slots(t, step)
                if slot not in self._delivery_used_slots
            ]
            goal_set = {(sx - offset[0], sy - offset[1]) for sx, sy in free_slots}
            path = None if not goal_set else bfs_path(
                item_cells_blocked, player_cell, goal_set, step, bounds, item_offset=offset
            )
            actions = None if path is None else path_to_actions(path, self._delivery_dir_map)
            self._delivery_cycles_left -= 1
            if not free_slots or path is None or actions is None:
                # No free slot reachable while carrying — nothing more this
                # phase can productively do; fall through rather than loop.
                self._plan_commit = self._action_count
                self._phase = _PHASE_INTERACT
                return self._interact_step(layer, avail, latest_frame)
            final_cell = path[-1]
            chosen_slot = (final_cell[0] + offset[0], final_cell[1] + offset[1])
            self._delivery_used_slots.add(chosen_slot)
            self._delivery_carrying = False
            self._delivery_carry_offset = None
            actions.append(5)
            self._delivery_action_queue = actions
            return self._delivery_step(layer, avail, latest_frame)

        # Not carrying: fetch the nearest remaining item.
        item_cell_by_idx = {
            i: bbox_min_corner(puzzle.items[i].cells) for i in self._delivery_items_remaining
        }
        target_idx = min(
            self._delivery_items_remaining,
            key=lambda i: abs(item_cell_by_idx[i][0] - player_cell[0])
            + abs(item_cell_by_idx[i][1] - player_cell[1]),
        )
        item_cell = item_cell_by_idx[target_idx]
        blocked = {
            item_cell_by_idx[i] for i in self._delivery_items_remaining if i != target_idx
        }
        goal_set = set(adjacent_cells(item_cell, step))
        path = bfs_path(blocked, player_cell, goal_set, step, bounds)
        self._delivery_cycles_left -= 1
        if path is None:
            # Unreachable — give up on this item, never retried speculatively.
            self._delivery_items_remaining.remove(target_idx)
            return self._delivery_step(layer, avail, latest_frame)
        actions = path_to_actions(path, self._delivery_dir_map)
        final_cell = path[-1]
        needed_delta = (item_cell[0] - final_cell[0], item_cell[1] - final_cell[1])
        face_aid = by_delta.get(needed_delta)
        if actions is None or face_aid is None:
            self._delivery_items_remaining.remove(target_idx)
            return self._delivery_step(layer, avail, latest_frame)
        if not actions or actions[-1] != face_aid:
            actions.append(face_aid)
        actions.append(5)
        self._delivery_items_remaining.remove(target_idx)
        self._delivery_carrying = True
        self._delivery_carry_offset = needed_delta
        self._delivery_action_queue = actions
        return self._delivery_step(layer, avail, latest_frame)

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
