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
    """One fresh-reset movement gate run (m0r0): warm-up -> directional-probe
    discovery -> compile the coupled-actor oracle -> stepped execution to the exact
    merge, idx0 then idx1 in sequence. Returns the per-run JSON record."""
    env = LiveEnv(game)
    env.reset()
    gs = GroundingService()
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

    # a. WARM-UP — a valid, playing frame the two-actor parse can bind against once
    #    the actor colour + scale are mobility-confirmed in discovery.
    frame: Optional[Grid] = None
    for _ in range(_WARMUP_BUDGET):
        frame = env.frame()
        if frame is None or env.state() in ("GAME_OVER", "NOT_PLAYED"):
            env.reset()
            continue
        break
    if frame is None:
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        print(f"[live] run{run_index} {game}: warm-up found no playing frame", flush=True)
        return record

    def probe(action_id: int) -> Optional[Grid]:
        env.simple_action(action_id)
        return env.frame()

    def two_actors_bound() -> bool:
        actors = gs.movement_actors()
        return actors is not UNKNOWN and len({aid for aid, _p in actors.value}) >= 2

    def reground() -> bool:
        """(Re)bind two-actor grounding on the CURRENT board. The mirror deltas are a
        game constant that accumulates across levels, so idx1 usually needs only the
        new frame fed (positions rebind frame-based). But right after a merge the env
        may still show the merged single-actor win frame before the next board's two
        actors respawn — so if fewer than two actors are visible, ADVANCE the env one
        directional step at a time (observing each transition) until both reappear or
        the discovery budget is spent. Returns True once both actors are bound and the
        delta table is complete."""
        for _ in range(_DISCOVERY_BUDGET):
            cur = env.frame()
            if cur is not None:
                gs.feed(cur)
            if two_actors_bound() and movement_edges_confirmed(gs):
                return True
            before = env.frame()
            after = probe(_M0R0_DIRECTIONS[0])  # advance-and-observe past the win frame
            record["discovery_actions"] += 1
            if after is None:
                return False
            if before is not None:
                gs.feed_transition(before, _M0R0_DIRECTIONS[0], (0, 0), after)
                record["edges_confirmed"] = record["edges_confirmed"] or movement_edges_confirmed(gs)
        return two_actors_bound() and movement_edges_confirmed(gs)

    # b. DISCOVERY — sweep ACTION1-4 until all 8 (actor, direction) edges confirm.
    closed, used, hz = discover_deltas(gs, frame, probe)
    record["discovery_actions"] = used
    record["hazard_resets"] += hz
    record["edges_confirmed"] = closed
    cur = env.frame()
    if cur is not None:
        gs.feed(cur)  # bind the current board's actors + occupancy for the compile
    if not closed or gs.movement_actors() is UNKNOWN:
        record["plan_outcome"] = "GROUNDING_INCOMPLETE"
        record["rebind_events"] = len(gs.rebind_events)
        print(f"[live] run{run_index} {game}: delta table did not complete", flush=True)
        return record

    # c + d. SOLVE + step; on level-up rebind the new board and recompile.
    return execute_movement_instance(env, gs, record, run_index, reground)


def execute_movement_instance(
    env: "LiveEnv",
    gs: GroundingService,
    record: dict[str, Any],
    run_index: int,
    reground: Callable[[], bool],
) -> dict[str, Any]:
    """Step the compiled coupled-actor plan against the live env with per-move
    confirmation, clearing idx0 then idx1. On a level-up the board is a new layout
    epoch (positions + occupancy rebind), so the plan is recompiled for it; a
    recoverable GROUNDING_INCOMPLETE / UNSATISFIABLE triggers a re-ground + recompile."""
    instance = schema_movement.m0r0_oracle_instance()
    plan = compile_movement_hypothesis(instance, gs)
    start_levels = env.levels()
    level_actions = 0
    regroundings = 0
    max_reground = _M0R0_TARGET_LEVELS + 2
    total_budget = _M0R0_LEVEL_BUDGET * _M0R0_TARGET_LEVELS + _DISCOVERY_BUDGET * max_reground + 10
    for _ in range(total_budget):
        frame = env.frame()
        if frame is None:
            env.reset()
            continue
        if env.state() == "WIN":
            record["plan_outcome"] = "CLEARED"
            break
        result = plan.step(frame)
        sol = plan.solve()
        record["states_searched"] = max(record["states_searched"], sol.states_searched)
        if isinstance(result, Terminal):
            if result.status is PlanStatus.DONE:
                record["plan_outcome"] = (
                    "CLEARED"
                    if record["levels_cleared"] >= _M0R0_TARGET_LEVELS or env.state() == "WIN"
                    else "DIVERGED"
                )
                break
            if (
                result.status in (PlanStatus.GROUNDING_INCOMPLETE, PlanStatus.UNSATISFIABLE)
                and regroundings < max_reground
                and reground()
            ):
                regroundings += 1
                plan = compile_movement_hypothesis(instance, gs)
                continue
            record["plan_outcome"] = result.status.value
            break
        if isinstance(result, Move):
            env.simple_action(result.action)
            level_actions += 1
            now = env.levels()
            if now > start_levels + record["levels_cleared"]:
                record["actions_per_level"].append(level_actions)
                record["levels_cleared"] = now - start_levels
                record["merge_event"] = record["merge_event"] or gs.movement_merge_event() is not UNKNOWN
                level_actions = 0
                print(f"[live] run{run_index} m0r0: level {record['levels_cleared']} cleared", flush=True)
                if record["levels_cleared"] >= _M0R0_TARGET_LEVELS:
                    record["plan_outcome"] = "CLEARED"
                    break
                reground()  # the new board: rebind positions + occupancy
                plan = compile_movement_hypothesis(instance, gs)  # fresh solution
                continue
            if level_actions > _M0R0_LEVEL_BUDGET:
                record["plan_outcome"] = "BUDGET"
                break

    record["merge_event"] = record["merge_event"] or gs.movement_merge_event() is not UNKNOWN
    record["rebind_events"] = len(gs.rebind_events)
    if record["plan_outcome"] == "CLEARED" and record["levels_cleared"] < _M0R0_TARGET_LEVELS:
        record["levels_cleared"] = max(record["levels_cleared"], env.levels() - start_levels)
    return record


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
