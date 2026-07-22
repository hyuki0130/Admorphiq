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

from admorphiq.hypothesis_select import schema  # noqa: E402
from admorphiq.hypothesis_select.compiler import (  # noqa: E402
    Click,
    PlanStatus,
    Terminal,
    compile_hypothesis,
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


def gate_verdict(runs: list[dict[str, Any]], game: str) -> str:
    """PASS iff every run cleared the game's required levels (ft09 idx0+idx1;
    sc25 the pattern-phase cast), else FAIL."""
    if not runs:
        return "FAIL"
    target = _FT09_TARGET_LEVELS if game == "ft09" else _SC25_TARGET_LEVELS
    ok = all(r.get("plan_outcome") == "CLEARED" and r.get("levels_cleared", 0) >= target for r in runs)
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
    plan = compile_hypothesis(instance, gs)
    start_levels = env.levels()
    level_actions = 0
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
                # DONE = the hypothesis believes the objective satisfied. Genuine
                # CLEARED iff the required levels cleared / WIN; otherwise the plan
                # finished without the game agreeing = an honest DIVERGENCE.
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, choices=["ft09", "sc25"])
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
