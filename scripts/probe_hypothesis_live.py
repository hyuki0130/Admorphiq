"""R95b STEP (vi): the live oracle-gate driver.

Runs the FULL R95b production pipeline against the live offline env — grounding
warm-up, cycle discovery (the honest fix for gold's one-directionality), compile
the ORACLE hypothesis instance, and step the compiled plan to clear levels — and
records a per-run + gate verdict. No LLM anywhere; no adapter imports (the plan
dispatches on schema tags only). The build agent produces this SCRIPT; the actual
3-run gate is launched by the maintainer as a background shell (measurements never
run inside an agent).

Per run (frozen contract):
  a. WARM-UP  — RESET, feed frames until the family parse binds cells.
  b. DISCOVERY (ft09) — bidirectional same-cell probe clicks on <= 3 cells until
     the ordered cycle CLOSES (grounding min-probe), budget <= 30 actions; if it
     cannot close -> GROUNDING_INCOMPLETE for the run (the honest 60%-risk outcome).
  c. SOLVE   — compile schema.<game>_oracle_instance via compile_hypothesis (the
     ft09 plan uses the LIVE-acquired cycle) and step the plan against the env,
     every click resolved through grounding at action time; failure surfaces
     recorded verbatim.
  d. ft09: clear idx0 then CONTINUE to idx1 in the same run (<= 150 actions/level);
     sc25: pattern phase to a genuine cast + guard handover (<= 60 actions), then
     stop (navigation excluded).

Usage (launched by the maintainer as a background shell):
  ARC_ENVIRONMENTS_DIR=... uv run python scripts/probe_hypothesis_live.py \
      --game ft09 --runs 3 --out out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402

from admorphiq.hypothesis_select import schema, schema_movement  # noqa: E402
from admorphiq.hypothesis_select.compiler import (  # noqa: E402
    Click,
    PlanStatus,
    Terminal,
    compile_hypothesis,
)
from admorphiq.hypothesis_select.compiler_movement import (  # noqa: E402
    Move,
    compile_movement_hypothesis,
)
from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService  # noqa: E402

Grid = tuple[tuple[int, ...], ...]

_WARMUP_BUDGET = 8
_DISCOVERY_BUDGET = 30
_DISCOVERY_CLICKS_PER_CELL = 4  # forward + reverse edge, twice each (min-probe)
_FT09_LEVEL_BUDGET = 150
_SC25_PHASE_BUDGET = 60
_FT09_TARGET_LEVELS = 2  # idx0 + idx1 in sequence
_SC25_TARGET_LEVELS = 1  # the pattern-phase cast

_M0R0_DIRECTIONS = (1, 2, 3, 4)  # the directional simple actions swept in discovery
_M0R0_LEVEL_BUDGET = 150  # solve <= 150 actions/level (frozen contract)
_M0R0_TARGET_LEVELS = 2  # idx0 + idx1 in sequence
_MOVEMENT_ACTORS = ("actor_a", "actor_b")


# ── pure helpers (unit-tested; no env) ──────────────────────────────────────


def discover_cycle(
    gs: GroundingService, probe: Callable[[int, int], Optional[Grid]], budget: int = _DISCOVERY_BUDGET
) -> tuple[bool, int]:
    """Close the ordered colour cycle by walking RESPONSIVE cells both ways along
    their cycle until grounding's min-probe rule accepts a single cycle, or the
    budget is spent. ``probe(x, y) -> next grid`` applies a click and returns the
    resulting frame (``None`` if the env ended). Returns ``(closed, actions_used)``.

    Responsiveness-adaptive: many ft09 cells are already satisfied / inert, so a
    blind fixed subset wastes the budget on cells that never change. Each cell is
    TEST-clicked once; only if the clicked cell's own colour changed is it clicked
    further (up to a few times, to walk forward + reverse edges). This is the
    honest fix for gold's one-directionality — the live agent supplies the reverse
    edges gold never shows."""
    from admorphiq.hypothesis_select.parse import _cell_class

    cells = gs.cells()
    if cells is UNKNOWN:
        return False, 0
    actions = 0
    for cell_id, _centroid in cells.value:
        for attempt in range(_DISCOVERY_CLICKS_PER_CELL):
            if gs.get_ordered_cycle() is not UNKNOWN:
                return True, actions
            if actions >= budget:
                return False, actions
            coord = gs.resolve_click(cell_id)
            if coord is UNKNOWN:
                break  # cell vanished / rebind — move to the next
            before = gs._prev_grid
            bbox = gs._cells[cell_id].bbox
            before_colour = _cell_class(before, bbox)
            x, y = coord.value
            after = probe(x, y)
            actions += 1
            if after is None:
                return gs.get_ordered_cycle() is not UNKNOWN, actions
            gs.feed_transition(before, 6, (x, y), after)
            if attempt == 0 and _cell_class(after, bbox) == before_colour:
                break  # inert cell — one test click was enough, move on
    return gs.get_ordered_cycle() is not UNKNOWN, actions


def movement_edges_confirmed(gs: GroundingService, directions: tuple[int, ...] = _M0R0_DIRECTIONS) -> bool:
    """Whether every ``(actor, direction)`` per-actor delta edge is min-probe
    acquired — the movement analogue of the closed cycle. Two actors x the swept
    directions must all appear in the grounded delta table."""
    d = gs.movement_deltas()
    if d is UNKNOWN:
        return False
    have = set(d.value.keys())
    need = {(aid, a) for aid in _MOVEMENT_ACTORS for a in directions}
    return need <= have


def unconfirmed_directions(
    gs: GroundingService, directions: tuple[int, ...] = _M0R0_DIRECTIONS
) -> set[tuple[str, int]]:
    """The ``(actor, direction)`` edges NOT yet min-probe acquired — the re-probe
    targets when a plan over the confirmed subset does not reach the goal."""
    d = gs.movement_deltas()
    have = set() if d is UNKNOWN else set(d.value.keys())
    return {(aid, a) for aid in _MOVEMENT_ACTORS for a in directions} - have


def discover_deltas(
    gs: GroundingService,
    initial: Grid,
    probe: Callable[[int], Optional[Grid]],
    budget: int = _DISCOVERY_BUDGET,
    directions: tuple[int, ...] = _M0R0_DIRECTIONS,
) -> tuple[bool, int, int]:
    """Sweep the directional simple actions, feeding each observed transition to the
    grounding, until every ``(actor, direction)`` delta edge is min-probe-confirmed
    or the budget is spent. ``probe(action) -> next grid`` applies one simple action
    and returns the resulting frame (``None`` if the env ended). Returns ``(all edges
    confirmed, actions used, hazard soft-resets observed)``.

    A collision-blocked or hazard-reset probe records NO delta edge (the grounding's
    collision-safe/hazard-safe accounting), so a sweep may leave edges open — the
    loop repeats sweeps until the table completes, stopping early after two sweeps
    that add no new edge (the graph is as complete as this board's reachability
    allows). Hazard soft-resets DURING discovery are counted (they are real actions
    and consume the budget), per the frozen contract."""
    before = initial
    used = 0
    hazard_resets = 0
    stale_sweeps = 0
    while used < budget and not movement_edges_confirmed(gs, directions):
        edges_before = _delta_edge_count(gs)
        for action in directions:
            if used >= budget or movement_edges_confirmed(gs, directions):
                break
            haz0 = _hazard_cell_count(gs)
            after = probe(action)
            used += 1
            if after is None:
                return movement_edges_confirmed(gs, directions), used, hazard_resets
            gs.feed_transition(before, action, (0, 0), after)
            hazard_resets += max(0, _hazard_cell_count(gs) - haz0)
            before = after
        if _delta_edge_count(gs) == edges_before:
            stale_sweeps += 1
            if stale_sweeps >= 2:
                break
        else:
            stale_sweeps = 0
    return movement_edges_confirmed(gs, directions), used, hazard_resets


def _delta_edge_count(gs: GroundingService) -> int:
    d = gs.movement_deltas()
    return 0 if d is UNKNOWN else len(d.value)


def _hazard_cell_count(gs: GroundingService) -> int:
    h = gs.movement_hazard_cells()
    return 0 if h is UNKNOWN else len(h.value)


_WAIT_K = 6  # max consecutive waits on a transient obstacle (the patroller's period clears it)


def transient_snapshot(gs: GroundingService) -> set[tuple[int, int]]:
    """The CURRENT cells occupied by a patrolling/transient obstacle — a per-frame
    SNAPSHOT the plan routes around (never learned as a static wall)."""
    t = gs.movement_transient_obstacles()
    return set() if t is UNKNOWN else {(int(r), int(c)) for r, c in t.value}


_BLOCK_TTL = 4  # recompiles a route-around block survives without re-confirmation before it EXPIRES


def refresh_blocks(
    blocked_at: dict[tuple[int, int], int],
    predicted: Optional[tuple[tuple[int, int], tuple[int, int]]],
    obs_now: Optional[list[tuple[int, int]]],
    recompiles: int,
) -> dict[tuple[int, int], int]:
    """Refresh the BLOCKED-NOW timestamp map (the primary transient sensor, no colour
    perception): STAMP each cell an actor was just blocked from (predicted − observed)
    with ``recompiles`` (add/refresh) and DROP any cell now occupied/passable (observation
    trumps inference — a cell an actor stands on cannot be a wall). A block observation is
    evidence about NOW, so it also carries a lifetime (see :func:`decay_blocks`)."""
    occupied = set(obs_now or [])
    blocked = (set(predicted) - occupied) if predicted else set()
    updated = {cell: t for cell, t in blocked_at.items() if cell not in occupied}
    for cell in blocked:
        updated[cell] = recompiles
    return updated


def decay_blocks(
    blocked_at: dict[tuple[int, int], int], recompiles: int, ttl: int = _BLOCK_TTL
) -> tuple[dict[tuple[int, int], int], set[tuple[int, int]]]:
    """Expire block entries not re-confirmed within ``ttl`` recompiles — a one-off
    patroller position an actor can never observe-clear (it is forbidden from entering it)
    must not accumulate into permanent fiction. Returns ``(kept_map, expired_cells)``."""
    kept = {cell: t for cell, t in blocked_at.items() if recompiles - t <= ttl}
    return kept, set(blocked_at) - set(kept)


def flip_flop_cells(
    blocked: set[tuple[int, int]],
    cleared_at: dict[tuple[int, int], int],
    recompiles: int,
    window: int = 2,
) -> set[tuple[int, int]]:
    """Just-blocked cells that were CLEARED from the route-around set within the last
    ``window`` recompiles — a bounce indicating a PERIODIC obstacle being CHASED (the
    patroller oscillates between a cell pair; greedy branch-switching follows it forever).
    Committing to WAIT on these (re-attempt in place, sampling a later phase) beats
    endlessly flipping the map between the bounce pair."""
    return {c for c in blocked if 0 <= recompiles - cleared_at.get(c, -1 - window) <= window}


def background_colour(frame: Any) -> int:
    """The floor colour of a frame — the modal pixel value (majority = background).
    Frame-diff cells whose CURRENT colour equals this are a just-VACATED footprint;
    a non-background changed cell is a mover's CURRENT footprint."""
    arr = np.asarray(frame)
    return int(np.bincount(arr.ravel()).argmax())


def frame_diff_cells(
    prev_frame: Any,
    cur_frame: Any,
    scale: int,
    exclude: set[tuple[int, int]],
) -> dict[tuple[int, int], int]:
    """MODEL-FREE per-cell frame diff: every ``scale``x``scale`` grid cell whose pixel
    content changed between the two frames and is NOT in ``exclude`` (the actor
    footprints across the transition), mapped to its CURRENT-frame centre colour. A
    moving obstacle appears here as its (entered plus vacated) footprint each step —
    colour-independent, so it sees a patroller the compact-mobile-colour heuristic
    misses. Empty when only the actors moved."""
    prev = np.asarray(prev_frame)
    cur = np.asarray(cur_frame)
    h, w = cur.shape
    changed = prev != cur
    out: dict[tuple[int, int], int] = {}
    for r in range(h // scale):
        for c in range(w // scale):
            if (r, c) in exclude:
                continue
            if changed[r * scale:(r + 1) * scale, c * scale:(c + 1) * scale].any():
                cr = min(h - 1, r * scale + scale // 2)
                cc = min(w - 1, c * scale + scale // 2)
                out[(r, c)] = int(cur[cr, cc])
    return out


def _move_observed(gs: GroundingService) -> Optional[list[tuple[int, int]]]:
    """The current observed actor cells (sorted), or None — the confirmation view the
    step-level instrumentation logs against the plan's predicted successor."""
    actors = gs.movement_actors()
    if actors is UNKNOWN:
        return None
    return sorted((int(r), int(c)) for _aid, (r, c) in actors.value)


def clean_block_wall(
    predicted: Optional[tuple[tuple[int, int], tuple[int, int]]],
    prev_obs: Optional[list[tuple[int, int]]],
    obs_now: Optional[list[tuple[int, int]]],
) -> Optional[tuple[int, int]]:
    """The single wall cell revealed by a CLEAN independent_stay block: exactly ONE
    predicted target went unreached, its partner DID reach its predicted cell, and an
    actor stayed at a pre-move cell. Returns that unreached cell (the wall), or None
    when the divergence is AMBIGUOUS (both actors off-prediction, or a predicted merge
    that did not occur) — nothing is learned then (avoids the pure-background false
    positives the naive predicted-minus-observed rule produced)."""
    if predicted is None or obs_now is None or prev_obs is None:
        return None
    pa, pb = predicted
    if pa == pb:
        return None  # a predicted merge that did not happen is ambiguous
    now_set, prev_set = set(obs_now), set(prev_obs)
    unreached = {pa, pb} - now_set
    partner_reached = bool({pa, pb} & now_set)
    actor_stayed = bool(prev_set & now_set)
    if len(unreached) == 1 and partner_reached and actor_stayed:
        return next(iter(unreached))
    return None


def noop_block_walls(
    predicted: Optional[tuple[tuple[int, int], tuple[int, int]]],
    prev_obs: Optional[list[tuple[int, int]]],
    obs_now: Optional[list[tuple[int, int]]],
) -> set[tuple[int, int]]:
    """The walls revealed by a TOTAL NO-OP frame (``obs_now == prev_obs`` — no actor
    moved, settle already spent): every predicted target NOT currently actor-occupied
    is a wall. This handles a PLANNED-STAY + partner-block (one predicted target is the
    stayer's own cell = reached, one is blocked → 1 wall) AND a double independent_stay
    block (both blocked → 2 walls) uniformly. Two simultaneous independent blocks are
    consistent with independent_stay (NOT the all-or-nothing mutant). Empty otherwise."""
    if predicted is None or obs_now is None or prev_obs is None:
        return set()
    if set(obs_now) != set(prev_obs):
        return set()  # not a total no-op frame
    now_set = set(obs_now)
    return {cell for cell in predicted if cell not in now_set}


def walls_to_unlearn(
    learned_walls: set[tuple[int, int]], obs_now: Optional[list[tuple[int, int]]]
) -> set[tuple[int, int]]:
    """OBSERVATION TRUMPS INFERENCE: any cell currently occupied by an actor cannot be a
    wall (the actor is standing on it) — return the learned walls to invalidate. A
    clean-block attribution can be a false positive (a stay misattributed to a target
    the actor later enters from another direction); the live observation overrides it."""
    return learned_walls & set(obs_now or [])


def block_learn_decision(
    candidates: set[tuple[int, int]],
    learned_walls: set[tuple[int, int]],
    block_count: dict[tuple[int, int], int],
    retries: int = 1,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """TRANSIENT-BLOCK TOLERANCE: a candidate wall cell is LEARNED only after it has
    blocked more than ``retries`` times; its first block(s) trigger a RETRY instead (the
    same action is re-emitted after a recompile, giving a MOVING obstacle a step to clear
    — if it does, the retry passes and nothing false is learned). Increments
    ``block_count`` per fresh candidate. Returns ``(to_learn, to_retry)`` cells."""
    to_learn: set[tuple[int, int]] = set()
    to_retry: set[tuple[int, int]] = set()
    for cell in candidates:
        if cell in learned_walls:
            continue
        block_count[cell] = block_count.get(cell, 0) + 1
        (to_learn if block_count[cell] > retries else to_retry).add(cell)
    return to_learn, to_retry


def joint_reset_hazards(
    predicted: Optional[tuple[tuple[int, int], tuple[int, int]]],
    prev_obs: Optional[list[tuple[int, int]]],
    obs_now: Optional[list[tuple[int, int]]],
) -> set[tuple[int, int]]:
    """The hazards revealed by a JOINT SOFT-RESET: both actors teleported to a home far
    from BOTH their previous positions AND their predicted targets (L1 > 1 from every
    such cell) — a reset triggered by entering a hazard, not ordinary motion. The cells
    the plan tried to ENTER (the predicted targets) are the hazards. Empty otherwise."""
    if predicted is None or obs_now is None or prev_obs is None:
        return set()
    prev_set, now_set = set(prev_obs), set(obs_now)
    if now_set == prev_set:
        return set()  # nobody moved — not a reset
    reference = prev_set | set(predicted)

    def far(cell: tuple[int, int]) -> bool:
        return all(abs(cell[0] - r[0]) + abs(cell[1] - r[1]) > 1 for r in reference)

    if all(far(c) for c in now_set):
        return set(predicted)
    return set()


def _target_levels(game: str) -> int:
    """The frozen-contract level target a run must reach to count as CLEARED."""
    if game == "sc25":
        return _SC25_TARGET_LEVELS
    if game == "m0r0":
        return _M0R0_TARGET_LEVELS
    return _FT09_TARGET_LEVELS


def gate_verdict(runs: list[dict[str, Any]], game: str) -> str:
    """PASS iff every run met the game's FROZEN-contract success criterion, else
    FAIL. ft09 = the required levels cleared (idx0+idx1). sc25 = the pattern-phase
    cast handover (contract: cast + guard, navigation excluded), scored on
    ``cast_and_handover`` NOT levels — a genuine sc25 run has levels_cleared 0."""
    if not runs:
        return "FAIL"
    if game == "sc25":
        return "PASS" if all(r.get("cast_and_handover") for r in runs) else "FAIL"
    target = _target_levels(game)
    ok = all(
        r.get("plan_outcome") == "CLEARED" and r.get("levels_cleared", 0) >= target
        for r in runs
    )
    return "PASS" if ok else "FAIL"


# ── live env wrapper (env I/O; exercised only under the real gate) ───────────


class LiveEnv:
    """A thin wrapper over the offline arc env: RESET, click, and frame/state/level
    reads, using the same boot + action-conversion path as
    ``scripts/probe_patch_loop``."""

    def __init__(self, game: str) -> None:
        from admorphiq.adapter import AdmorphiqAdapter

        arcade, match = _find_game(game)
        self._env = arcade.make(match.game_id)
        self._convert = AdmorphiqAdapter._convert_action
        self._obs: Any = self._env.observation_space

    def reset(self) -> None:
        from arcengine import GameAction as EngineGameAction

        self._obs = self._env.step(EngineGameAction.RESET)

    def click(self, x: int, y: int) -> None:
        from admorphiq.types import ActionType, GameAction

        _ = ActionType  # imported for symmetry with the shared driver path
        action = self._convert(GameAction.coordinate(int(x), int(y)))
        self._obs = (
            self._env.step(action, data=action.action_data.model_dump())
            if action.is_complex()
            else self._env.step(action)
        )

    def simple_action(self, action_id: int) -> None:
        """Apply a simple (non-coordinate) action ACTION1-4 — the directional moves
        the movement family probes and executes."""
        from admorphiq.types import ActionType, GameAction

        action = self._convert(GameAction.simple(ActionType(int(action_id))))
        self._obs = self._env.step(action)

    def frame(self) -> Optional[Grid]:
        from admorphiq.tools.base import frame_2d, has_frame

        if not has_frame(self._obs):
            return None
        arr = np.asarray(frame_2d(self._obs))
        if arr.ndim == 3:
            arr = arr[-1]
        return tuple(tuple(int(v) for v in row) for row in arr)

    def state(self) -> str:
        from admorphiq.tools.base import state_name

        return state_name(self._obs)

    def levels(self) -> int:
        from admorphiq.tools.base import levels_completed

        return int(levels_completed(self._obs) or 0)


def _find_game(game_query: str) -> tuple[Any, Any]:
    import os

    from arc_agi import Arcade, OperationMode

    envs_dir = os.environ.get("ARC_ENVIRONMENTS_DIR")
    arcade = (
        Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=envs_dir)
        if envs_dir
        else Arcade(operation_mode=OperationMode.OFFLINE)
    )
    want = game_query.strip().lower()
    match = next(
        (e for e in arcade.get_environments() if want in f"{e.game_id} {e.title or ''}".lower()),
        None,
    )
    if match is None:
        raise SystemExit(f"no game matching {game_query!r}")
    return arcade, match


# ── one run of the gate against the live env ─────────────────────────────────


def run_once(game: str, run_index: int) -> dict[str, Any]:
    """One fresh-reset gate run. Returns the per-run JSON record."""
    if game == "m0r0":
        return run_movement_once(game, run_index)
    env = LiveEnv(game)
    env.reset()
    gs = GroundingService()
    instance = schema.ft09_oracle_instance() if game == "ft09" else schema.sc25_oracle_instance()
    target_levels = _FT09_TARGET_LEVELS if game == "ft09" else _SC25_TARGET_LEVELS
    level_budget = _FT09_LEVEL_BUDGET if game == "ft09" else _SC25_PHASE_BUDGET

    record: dict[str, Any] = {
        "run": run_index,
        "levels_cleared": 0,
        "actions_per_level": [],
        "discovery_actions": 0,
        "plan_outcome": "BUDGET",
        "rebind_events": 0,
        "cycle_acquired": False,
        "cast_and_handover": False,
    }

    # a. WARM-UP — feed frames until the family parse binds.
    for _ in range(_WARMUP_BUDGET):
        frame = env.frame()
        if frame is None or env.state() in ("GAME_OVER", "NOT_PLAYED"):
            env.reset()
            continue
        gs.feed(frame)
        if gs.cells() is not UNKNOWN:
            break
    if gs.cells() is UNKNOWN:
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        print(f"[live] run{run_index} {game}: warm-up failed to bind cells", flush=True)
        return record

    def probe(x: int, y: int) -> Optional[Grid]:
        env.click(x, y)
        return env.frame()

    def rediscover() -> bool:
        """(Re)acquire the current board's cycle (ft09 only). Returns True when the
        cycle is closed (or not needed for sc25). The grounding reset its
        cycle-edge evidence on the reveal/level-up rebind, so this acquires the NEW
        board's own alphabet cleanly."""
        if game != "ft09":
            return True
        if gs.get_ordered_cycle() is not UNKNOWN:
            return True
        closed, used = discover_cycle(gs, probe)
        record["discovery_actions"] += used
        record["cycle_acquired"] = record["cycle_acquired"] or closed
        return closed

    # b. DISCOVERY (ft09 only — sc25's binary flip needs no cycle).
    if not rediscover():
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        print(f"[live] run{run_index} {game}: initial cycle did not close", flush=True)
        return record

    # c + d. SOLVE — step the plan; on a recoverable failure after a reveal /
    # level-up (a new board with its own cycle), re-discover + recompile and go on.
    return execute_instance(
        env, gs, game, instance, target_levels, level_budget, record, run_index, rediscover
    )


def execute_instance(
    env: "LiveEnv",
    gs: GroundingService,
    game: str,
    instance: Any,
    target_levels: int,
    level_budget: int,
    record: dict[str, Any],
    run_index: int,
    rediscover: Callable[[], bool],
) -> dict[str, Any]:
    """Compile ``instance`` and live-execute it to an outcome (mutating + returning
    ``record``). The SINGLE execution path shared by the oracle gate (run_once) and
    the canned-instance MODEL gate (probe_hypothesis_model): the same step loop,
    the same sc25 cast-handover scoring, the same re-discovery-on-recoverable-failure
    recompile. ``rediscover`` (re)acquires the current board's grounding when a
    reveal/level-up produces a new board."""
    plan = compile_hypothesis(instance, gs)
    start_levels = env.levels()
    level_actions = 0
    flips = 0  # genuine flip clicks the plan emitted (sc25 cast evidence)
    rediscoveries = 0
    max_rediscover = target_levels + 2
    total_budget = level_budget * target_levels + _DISCOVERY_BUDGET * max_rediscover + 10
    for _ in range(total_budget):
        frame = env.frame()
        if frame is None:
            env.reset()
            continue
        if env.state() == "WIN":
            record["plan_outcome"] = "CLEARED"
            break
        result = plan.step(frame)
        if isinstance(result, Terminal):
            if result.status is PlanStatus.DONE:
                if game == "sc25":
                    # The FROZEN contract scores sc25 idx0 at the pattern phase only
                    # (cast + guard handover; navigation excluded), so success is the
                    # Phase-1 guard StableForReads(2) ^ RolesStateEqual(toggle_grid,
                    # preview) after a GENUINE cast — NOT a level clear (levels stays
                    # 0, which is correct). RolesStateEqual = an empty base-XOR diff;
                    # StableForReads(2) = it holds on a 2nd read of the settled grid;
                    # a genuine cast = >=1 real flip AND an observed cast colour.
                    stable = False
                    confirm = env.frame()
                    if confirm is not None:
                        gs.feed(confirm)
                        again = gs.pattern_diff()
                        stable = again is not UNKNOWN and not again.value
                    record["cast_and_handover"] = bool(
                        flips >= 1 and gs.cast_colour_seen() and stable
                    )
                    record["plan_outcome"] = (
                        "CAST_HANDOVER" if record["cast_and_handover"] else "DIVERGED"
                    )
                    break
                # ft09: DONE is a genuine clear iff the required levels cleared / WIN;
                # otherwise the plan finished without the game agreeing = a DIVERGENCE.
                record["plan_outcome"] = (
                    "CLEARED"
                    if record["levels_cleared"] >= target_levels or env.state() == "WIN"
                    else "DIVERGED"
                )
                break
            if (
                result.status in (PlanStatus.GROUNDING_INCOMPLETE, PlanStatus.UNSATISFIABLE)
                and rediscoveries < max_rediscover
                and rediscover()
            ):
                rediscoveries += 1
                plan = compile_hypothesis(instance, gs)  # solve the revealed board
                continue
            record["plan_outcome"] = result.status.value
            break
        if isinstance(result, Click):
            env.click(result.x, result.y)
            level_actions += 1
            flips += 1
            now = env.levels()
            if now > start_levels + record["levels_cleared"]:
                record["actions_per_level"].append(level_actions)
                record["levels_cleared"] = now - start_levels
                level_actions = 0
                print(f"[live] run{run_index} {game}: level {record['levels_cleared']} cleared", flush=True)
                if record["levels_cleared"] >= target_levels:
                    record["plan_outcome"] = "CLEARED"
                    break
            if level_actions > level_budget:
                record["plan_outcome"] = "BUDGET"
                break

    record["rebind_events"] = len(gs.rebind_events)
    if record["plan_outcome"] == "CLEARED" and record["levels_cleared"] < target_levels:
        record["levels_cleared"] = max(record["levels_cleared"], env.levels() - start_levels)
    return record


def run_movement_once(game: str, run_index: int) -> dict[str, Any]:
    """One fresh-reset movement gate run (m0r0): for EACH level board a FRESH
    grounding + full directional RE-DISCOVERY -> compile the coupled-actor oracle ->
    stepped execution to the exact merge. Per-board re-grounding is the doctrine (as
    ft09 re-acquires its cycle per board): measured 2026-07-23, m0r0's model must NOT
    carry idx0 into idx1 — idx0's gold path never exercises one direction (so that
    edge is unconfirmed), and the first action right after a level transition is
    ABSORBED by a settling frame (the idx1 gold's first action moves nothing). A fresh
    per-board sweep confirms THIS board's own edges and spends the settling frame
    before the plan executes. Returns the per-run JSON record."""
    env = LiveEnv(game)
    env.reset()
    record: dict[str, Any] = {
        "run": run_index,
        "levels_cleared": 0,
        "actions_per_level": [],
        "discovery_actions": 0,
        "plan_outcome": "BUDGET",
        "states_searched": 0,
        "merge_event": False,
        "hazard_resets": 0,
        "rebind_events": 0,
        "edges_confirmed": False,
    }
    for _level_ordinal in range(_M0R0_TARGET_LEVELS):
        outcome, rebinds = run_movement_level(env, record, run_index)
        record["rebind_events"] += rebinds
        if outcome != "CLEARED":
            record["plan_outcome"] = outcome
            return record
        record["levels_cleared"] += 1
        record["merge_event"] = True  # the m0r0 level-complete condition IS the actor merge
        print(f"[live] run{run_index} m0r0: level {record['levels_cleared']} cleared", flush=True)
        if record["levels_cleared"] >= _M0R0_TARGET_LEVELS:
            record["plan_outcome"] = "CLEARED"
            break
    return record


def run_movement_level(env: "LiveEnv", record: dict[str, Any], run_index: int) -> tuple[str, int]:
    """Clear ONE level board with a FRESH grounding: warm-up -> directional-probe
    RE-DISCOVERY on this board (which also spends the absorbed post-transition
    settling action) -> compile -> stepped per-move confirmation until this level
    clears. Returns ``(outcome, rebind_events)`` with outcome CLEARED / DIVERGED /
    GROUNDING_INCOMPLETE / BUDGET."""
    gs = GroundingService()

    def probe(action_id: int) -> Optional[Grid]:
        env.simple_action(action_id)
        return env.frame()

    # a. WARM-UP — a valid playing frame to seed discovery.
    frame: Optional[Grid] = None
    for _ in range(_WARMUP_BUDGET):
        frame = env.frame()
        if frame is None or env.state() in ("GAME_OVER", "NOT_PLAYED"):
            env.reset()
            continue
        break
    if frame is None:
        return "GROUNDING_INCOMPLETE", len(gs.rebind_events)

    # b. RE-DISCOVERY — sweep ACTION1-4 on THIS board. The first post-transition
    #    action is absorbed by the settling frame and records no edge, so the sweep
    #    repeats until the settled board responds. Full-alphabet knowledge is NOT
    #    required: m0r0's gold clears idx0 without ever using one direction, and idx1's
    #    geometry leaves one (actor, up) edge unconfirmable from the start positions.
    closed, used, hz = discover_deltas(gs, frame, probe)
    record["discovery_actions"] += used
    record["hazard_resets"] += hz
    record["edges_confirmed"] = record["edges_confirmed"] or closed
    cur = env.frame()
    if cur is not None:
        gs.feed(cur)  # bind this board's actors + occupancy for the compile
    if gs.movement_actors() is UNKNOWN:
        print(f"[live] run{run_index} m0r0: no two-actor bind on this board", flush=True)
        return "GROUNDING_INCOMPLETE", len(gs.rebind_events)

    # c. Compile over the CONFIRMED edge subset (the compiler's action alphabet is the
    #    actions confirmed for BOTH actors). Only if no plan to the goal exists in that
    #    alphabet do we RE-PROBE the unconfirmed directions from the actors' CURRENT
    #    (moved) positions — bounded by the remaining discovery budget — before falling
    #    to the honest GROUNDING_INCOMPLETE / UNSATISFIABLE surface.
    instance = schema_movement.m0r0_oracle_instance()
    probe_budget = max(0, _DISCOVERY_BUDGET - used)
    reprobes = 0
    # SEED occupancy from discovery's collision-blocked targets (free, high-confidence
    # wall evidence) so the plan routes around known walls before execution begins.
    seeded = gs.movement_blocked_targets()
    learned_walls: set[tuple[int, int]] = set() if seeded is UNKNOWN else set(seeded.value)
    learned_hazards: set[tuple[int, int]] = set()
    unwalled: set[tuple[int, int]] = set()  # grounded walls an actor was seen on (false-wall override)
    if learned_walls:
        print(
            f"[live] run{run_index} m0r0: seeded {len(learned_walls)} wall(s) from discovery blocks",
            flush=True,
        )
    while True:
        plan = compile_movement_hypothesis(
            instance, gs, extra_walls=learned_walls | transient_snapshot(gs),
            extra_hazards=learned_hazards, unwalled=unwalled,
        )
        sol = plan.solve()
        record["states_searched"] = max(record["states_searched"], sol.states_searched)
        if sol.status in (PlanStatus.SOLVABLE, PlanStatus.DONE):
            break
        missing = unconfirmed_directions(gs)
        if not missing or probe_budget <= 0 or reprobes >= 2:
            print(
                f"[live] run{run_index} m0r0: no plan over confirmed alphabet "
                f"({sol.status.value}); missing edges {sorted(missing)}, "
                f"states searched {sol.states_searched}",
                flush=True,
            )
            return sol.status.value, len(gs.rebind_events)
        base = env.frame()
        if base is None:
            return sol.status.value, len(gs.rebind_events)
        _closed2, used2, hz2 = discover_deltas(gs, base, probe, budget=probe_budget)
        record["discovery_actions"] += used2
        record["hazard_resets"] += hz2
        probe_budget -= used2
        reprobes += 1
        cur = env.frame()
        if cur is not None:
            gs.feed(cur)

    # d. Step the SOLVABLE plan until THIS level clears.
    start_levels = env.levels()
    level_actions = 0
    settle_allowance = 1  # the first action after a level transition is absorbed (measured)
    max_learned = 12  # online-learning cap (walls and hazards each)
    max_recompiles = 40  # total recompiles/level before the honest surface (cause-logged)
    recompiles = 0
    block_count: dict[tuple[int, int], int] = {}  # per-cell block tally for retry-before-learn
    churn_cells: set[tuple[int, int]] = set()  # toggled cells (learned-then-invalidated) — NEVER learn
    wait_count: dict[tuple[int, int], int] = {}  # per-cell consecutive waits on a transient obstacle
    blocked_at: dict[tuple[int, int], int] = {}  # cell -> recompile it last blocked (route around; TTL-decayed)
    cleared_at: dict[tuple[int, int], int] = {}  # recompile index a cell last cleared (flip-flop detection)
    prev_obs = _move_observed(gs)
    prev_frame_grid: Optional[Any] = None  # the frame before the last engine step (frame-diff sensor)
    for _ in range(_M0R0_LEVEL_BUDGET + 10):
        frame = env.frame()
        if frame is None:
            env.reset()
            continue
        if env.levels() > start_levels or env.state() == "WIN":
            record["actions_per_level"].append(level_actions)
            return "CLEARED", len(gs.rebind_events)
        result = plan.step(frame)
        sol = plan.solve()
        record["states_searched"] = max(record["states_searched"], sol.states_searched)
        cursor = plan._cursor
        predicted = plan._traj[cursor] if 0 <= cursor < len(plan._traj) else None
        # FRAME-DIFF TRANSIENT PERCEPTION (colour-independent, replaces the compact-
        # mobile-colour heuristic): the cells that changed since the last engine step,
        # minus BOTH actor footprints, are the mover's (entered + vacated) trail; the
        # non-background ones are its CURRENT position. Empty on a no-engine-step
        # recompile (the frame is unchanged), so `frame_transient` carries the freshest
        # engine step's evidence into the divergence handling below.
        scale = gs._move_scale or 1
        actor_colour = gs._move_actor_colour
        frame_transient: set[tuple[int, int]] = set()
        if prev_frame_grid is not None:
            cur_actors = set(_move_observed(gs) or [])
            diff = frame_diff_cells(
                prev_frame_grid, frame, scale, exclude=cur_actors | set(prev_obs or [])
            )
            if diff:
                bg = background_colour(frame)
                # A mover's CURRENT footprint is a changed cell whose colour is neither the
                # floor (a just-vacated trail) NOR the actor's own colour (an actor block
                # straddling a cell boundary leaks its colour into the neighbour cell — a
                # false mover the centroid-cell exclusion alone misses).
                frame_transient = {
                    cell for cell, col in diff.items() if col != bg and col != actor_colour
                }
                print(
                    f"[live] run{run_index} m0r0 framediff step {level_actions}: "
                    f"changed-nonactor {sorted(diff.items())}, "
                    f"transient(mover) {sorted(frame_transient)}",
                    flush=True,
                )
        prev_frame_grid = frame
        if isinstance(result, Terminal):
            if result.status is PlanStatus.DONE:
                if env.levels() > start_levels or env.state() == "WIN":
                    record["actions_per_level"].append(level_actions)
                    return "CLEARED", len(gs.rebind_events)
                return "DIVERGED", len(gs.rebind_events)
            if result.status is PlanStatus.DIVERGED:
                obs_now = _move_observed(gs)
                occupied = set(obs_now or [])
                cause: Optional[str] = None
                snapshot = frame_transient  # current mover cells from the frame diff (never learned)
                # OBSERVATION TRUMPS INFERENCE (learned + grounded walls). A learned wall an
                # actor now stands on, OR one the frame diff shows MOVING (a patroller the
                # static learner mis-learned), cannot be a static wall — it is invalidated and
                # joins the NEVER-LEARN churn set. This continuously un-poisons learned_walls.
                freed = walls_to_unlearn(learned_walls, obs_now) | (learned_walls & frame_transient)
                if freed:
                    learned_walls -= freed
                    churn_cells |= freed
                    for cell in freed:
                        block_count.pop(cell, None)
                    print(
                        f"[live] run{run_index} m0r0 unlearned wall(s) {sorted(freed)} (occupied/moving) "
                        f"at step {level_actions}",
                        flush=True,
                    )
                occ = gs.movement_occupancy()
                grounded = set() if occ is UNKNOWN else {(int(r), int(c)) for r, c in occ.value.blocked_cells}
                new_unwalled = (grounded & occupied) - unwalled
                if new_unwalled:
                    unwalled |= new_unwalled
                    churn_cells |= new_unwalled
                    print(
                        f"[live] run{run_index} m0r0 unwalled grounded wall(s) {sorted(new_unwalled)} "
                        f"(occupied) at step {level_actions}",
                        flush=True,
                    )
                # BLOCKED-NOW is the primary transient sensor: a cell an actor was just blocked
                # from is routed around THIS recompile (temporary, never permanent); it clears
                # the moment an actor is observed ON it (observation) and EXPIRES via TTL if never
                # re-confirmed (a one-off patroller position an actor can never observe-clear).
                blocked = (set(predicted) - occupied) if predicted else set()
                for cell in set(blocked_at) & occupied:
                    cleared_at[cell] = recompiles  # record the clear (flip-flop history)
                blocked_at = refresh_blocks(blocked_at, predicted, obs_now, recompiles)
                blocked_at, expired = decay_blocks(blocked_at, recompiles)
                if expired:
                    print(
                        f"[live] run{run_index} m0r0 expired block(s) {sorted(expired)} at step {level_actions}",
                        flush=True,
                    )
                blocked_now = set(blocked_at)
                chasing = {
                    c for c in flip_flop_cells(blocked, cleared_at, recompiles) if wait_count.get(c, 0) < _WAIT_K
                }
                waived: set[tuple[int, int]] = set()
                if settle_allowance > 0 and obs_now is not None and obs_now == prev_obs:
                    settle_allowance -= 1
                    cause = f"settle from {obs_now}"
                elif chasing and recompiles < max_recompiles:
                    # FLIP-FLOP: a periodic obstacle bounces across a cell pair; committing to WAIT
                    # on the chased cells (re-attempt in place, sampling a later phase) beats
                    # endlessly flipping the map between the bounce pair.
                    for c in chasing:
                        wait_count[c] = wait_count.get(c, 0) + 1
                    waived = chasing
                    k = max(wait_count[c] for c in chasing)
                    cause = f"wait (flip-flop at {sorted(chasing)}) {k}/{_WAIT_K}"
                elif recompiles < max_recompiles:
                    hazards = joint_reset_hazards(predicted, prev_obs, obs_now) - learned_hazards
                    if hazards and len(learned_hazards) + len(hazards) <= max_learned:
                        # a JOINT soft-reset teleport: the entered cells are unseen hazards
                        learned_hazards |= hazards
                        record["hazard_resets"] += 1
                        cause = f"learned-hazard {sorted(hazards)} ({len(learned_hazards)} total)"
                    else:
                        # STATIC-WALL candidates (total no-op -> planned-stay/double; else clean
                        # block), RETRIED once. NEVER learn a churn/transient cell — blocked_now
                        # handles those temporarily; only a persistent NON-churn block is learned.
                        if obs_now is not None and obs_now == prev_obs:
                            candidates = noop_block_walls(predicted, prev_obs, obs_now)
                        else:
                            clean = clean_block_wall(predicted, prev_obs, obs_now)
                            candidates = {clean} if clean is not None else set()
                        candidates -= churn_cells | snapshot
                        to_learn, to_retry = block_learn_decision(candidates, learned_walls, block_count)
                        if to_learn and len(learned_walls) + len(to_learn) <= max_learned:
                            learned_walls |= to_learn
                            for cell in to_learn:
                                block_count.pop(cell, None)
                            cause = f"learned-wall {sorted(to_learn)} ({len(learned_walls)} total)"
                        elif to_retry:
                            cause = f"retry-block {sorted(to_retry)}"
                        else:
                            cause = f"route-around {sorted(blocked_now)}" if blocked_now else (
                                f"ambiguous predicted {predicted} observed {obs_now}"
                            )
                if cause is None and (freed or new_unwalled):
                    cause = f"invalidate-only walls={sorted(freed)} unwalled={sorted(new_unwalled)}"
                if cause is not None and recompiles < max_recompiles:
                    recompiles += 1
                    # `waived` cells (a flip-flop bounce being waited on) are NOT walled — the
                    # plan re-attempts them in place rather than routing around.
                    walls = learned_walls | (blocked_now - waived) | snapshot
                    plan = compile_movement_hypothesis(
                        instance, gs, extra_walls=walls, extra_hazards=learned_hazards, unwalled=unwalled,
                    )
                    # UNSAT-FLUSH: stale accumulated blocks can over-wall the map into a false
                    # UNSATISFIABLE. Keep only blocks refreshed within the last recompile (the
                    # freshest evidence) and retry ONCE — decay's on-demand form.
                    if plan.solve().status is PlanStatus.UNSATISFIABLE:
                        fresh_blocks = {c for c, t in blocked_at.items() if recompiles - t <= 1}
                        flushed = set(blocked_at) - fresh_blocks
                        if flushed:
                            blocked_at = {c: t for c, t in blocked_at.items() if c in fresh_blocks}
                            blocked_now = set(blocked_at)
                            walls = learned_walls | (blocked_now - waived) | snapshot
                            cause = f"{cause} + unsat-flush retry (dropped {sorted(flushed)})"
                            plan = compile_movement_hypothesis(
                                instance, gs, extra_walls=walls, extra_hazards=learned_hazards, unwalled=unwalled,
                            )
                    # WAIT: if routing around STILL has no solution, the block is a churn/transient
                    # obstacle on the ONLY path — re-attempt (wait) up to K, rather than surfacing
                    # UNSATISFIABLE prematurely.
                    if plan.solve().status is PlanStatus.UNSATISFIABLE:
                        waitable = {
                            c for c in (blocked_now & (churn_cells | snapshot)) if wait_count.get(c, 0) < _WAIT_K
                        }
                        if waitable:
                            for c in waitable:
                                wait_count[c] = wait_count.get(c, 0) + 1
                            k = max(wait_count[c] for c in waitable)
                            cause = f"{cause} + wait (blocked {sorted(waitable)}) {k}/{_WAIT_K}"
                            plan = compile_movement_hypothesis(
                                instance, gs, extra_walls=walls - waitable,
                                extra_hazards=learned_hazards, unwalled=unwalled,
                            )
                    print(f"[live] run{run_index} m0r0 recompile ({cause}) at step {level_actions}", flush=True)
                    continue
                colour = gs._move_actor_colour
                regions = gs._move_regions_of(frame, colour) if colour is not None else []
                print(
                    f"[live] run{run_index} m0r0 DIVERGED (recompile cap) at step {level_actions} (cursor {cursor}): "
                    f"predicted {predicted}, observed {obs_now}; raw actor regions "
                    f"{[(round(c[0]), round(c[1])) for c, _s, _b in regions]}",
                    flush=True,
                )
            return result.status.value, len(gs.rebind_events)
        if isinstance(result, Move):
            print(
                f"[live] run{run_index} m0r0 step {level_actions}: action {result.action}, "
                f"predicted-next {predicted}, observed-now {_move_observed(gs)}",
                flush=True,
            )
            prev_obs = _move_observed(gs)  # actors BEFORE this action (for the absorption test)
            for cell in set(prev_obs or []):
                blocked_at.pop(cell, None)  # a cell an actor now occupies is passable — clear it
            env.simple_action(result.action)
            level_actions += 1
            if env.levels() > start_levels:
                record["actions_per_level"].append(level_actions)
                return "CLEARED", len(gs.rebind_events)
            if level_actions > _M0R0_LEVEL_BUDGET:
                return "BUDGET", len(gs.rebind_events)
    return "BUDGET", len(gs.rebind_events)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, choices=["ft09", "sc25", "m0r0"])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    runs: list[dict[str, Any]] = []
    for i in range(args.runs):
        print(f"[live] === {args.game} run {i + 1}/{args.runs} ===", flush=True)
        runs.append(run_once(args.game, i))
        print(f"[live] run {i} record: {runs[-1]}", flush=True)

    verdict = gate_verdict(runs, args.game)
    summary = {"game": args.game, "runs": runs, "gate_verdict": verdict}
    Path(args.out).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[live] GATE VERDICT ({args.game}): {verdict}", flush=True)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
