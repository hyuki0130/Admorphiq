"""Per-action census of lp85 under the shipped harness — what is each action FOR?

Mirrors ``scripts/score_efficiency.py:run_game`` exactly (empty frames list to
is_done/choose_action, restart_on_game_over honoured, BREAK on WIN) and classifies
every action the CyclePressTool emits as PROBE / PLAN / NUDGE / OTHER, tagged with
the level it was spent on read from the engine, never inferred by proximity.

Purpose: level 4 costs 19 actions against a human 16 and the loss is entirely there.
Expected feedback: the per-level breakdown says how many of the 19 are evidence
presses and how many are the solution itself, which is the only thing that says
whether there are three actions to find.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402


def main() -> None:
    seed = sys.argv[1] if len(sys.argv) > 1 else "1"
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from score_efficiency import _make_agent  # the SHIPPED construction, mirrored not re-derived

    from admorphiq.tools import cyclepress as cp

    log: list[dict] = []
    state = {"tag": None, "level": 0}

    orig_probe = cp.CyclePressTool._next_probe
    orig_nudge = cp.CyclePressTool._nudge
    orig_propose = cp.CyclePressTool.propose

    def probe_wrap(self, controls, tiles, marks):
        out = orig_probe(self, controls, tiles, marks)
        if out is not None:
            state["tag"] = "PROBE"
        return out

    def nudge_wrap(self, controls):
        state["tag"] = "NUDGE"
        return orig_nudge(self, controls)

    def propose_wrap(self, frames, obs):
        state["tag"] = None
        plan_before = len(self._plan)
        steps = orig_propose(self, frames, obs)
        tag = state["tag"] or ("PLAN" if steps else "EMPTY")
        log.append({
            "lvl": state["level"],
            "tag": tag,
            "step": steps[0] if steps else None,
            "perms": len(self._perm),
            "pressed": len(self._pairs),
            "inert": len(self._inert),
            "replans": self._replans,
            "confirms": self._confirms,
            "plan_before": plan_before,
            "plan_left": len(self._plan),
            "settled": self._settled,
            "budget_left": self._budget.remaining(self._last_frame),
        })
        return steps

    cp.CyclePressTool._next_probe = probe_wrap
    cp.CyclePressTool._nudge = nudge_wrap
    cp.CyclePressTool.propose = propose_wrap

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(e for e in arcade.get_environments()
                if "lp85" in f"{e.game_id} {e.title or ''}".lower())
    game_id = info.game_id
    baseline = info.baseline_actions
    agent = _make_agent("unified", game_id=game_id)

    env = arcade.make(game_id)
    obs = env.observation_space
    prev = obs.levels_completed
    state["level"] = prev
    total = 0
    this_level = 0
    per_level: list[int] = []
    restart = bool(getattr(agent, "restart_on_game_over", False))

    while total < budget:
        if agent.is_done([], obs):
            break
        action = agent.choose_action([], obs)
        if not isinstance(action, GameAction):
            break
        if action.is_complex():
            obs = env.step(action, data=action.action_data.model_dump())
        else:
            obs = env.step(action)
        if obs is None:
            break
        total += 1
        this_level += 1
        cur = int(obs.levels_completed)
        if cur > prev:
            for _ in range(cur - prev):
                per_level.append(this_level)
                this_level = 0
            prev = cur
            state["level"] = cur
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            this_level += 1
            if obs is None:
                break

    # Census by level and tag. Attribution comes from the engine's own level number,
    # recorded at the moment the action was proposed.
    census: dict[str, dict[str, int]] = {}
    for row in log:
        census.setdefault(str(row["lvl"]), {}).setdefault(row["tag"], 0)
        census[str(row["lvl"])][row["tag"]] += 1

    print(json.dumps({
        "seed": seed,
        "levels_completed": int(prev),
        "total_actions": total,
        "per_level": per_level,
        "baseline": baseline,
        "census": census,
        "tool_calls": len(log),
        "l4_trace": [r for r in log if r["lvl"] == 3],
    }))



if __name__ == "__main__":
    main()
