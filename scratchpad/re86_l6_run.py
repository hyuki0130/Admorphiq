"""re86 L6 build runner — measure the Adapter on the CORRECT 8af5384d file.

Uses ``ar.make("re86")`` (the loader lesson: the full id ``re86-8af5384d`` mis-
resolves to the v1 4e57566e variant locally; ``make("re86")`` loads the true
8af5384d file — confirm from the "Successfully loaded ... from
environment_files/re86/8af5384d/re86.py" log line). Reports per-level action
counts + game_score using the faithful squared-efficiency metric.

Usage: uv run python scratchpad/re86_l6_run.py [max_actions] [reps]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402

from admorphiq.adapters25.re86 import Adapter  # noqa: E402


def level_score(human: int, agent: int) -> float:
    return min(human / agent, 1.0) ** 2 if agent else 0.0


def game_score(level_scores: list[float], win_levels: int) -> float:
    num = sum((i + 1) * s for i, s in enumerate(level_scores))
    den = sum(range(1, win_levels + 1))
    return num / den if den else 0.0


def run(arc: Arcade, max_actions: int) -> dict:
    ad = Adapter(giveup=max_actions + 10)
    env = arc.make("re86")
    obs = env.observation_space
    win_levels = obs.win_levels
    info = getattr(env, "env_info", None)
    if callable(info):
        info = info()
    baseline = list(getattr(info, "baseline_actions", None) or getattr(obs, "baseline_actions", None) or [])
    prev = obs.levels_completed
    total = 0
    this_lvl = 0
    per_level: list[int] = []
    while total < max_actions:
        if ad.is_done([], obs):
            break
        a = ad.choose_action([], obs)
        if not isinstance(a, GameAction):
            break
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        if obs is None:
            break
        total += 1
        this_lvl += 1
        if obs.levels_completed > prev:
            for _ in range(obs.levels_completed - prev):
                per_level.append(this_lvl)
                this_lvl = 0
            prev = obs.levels_completed
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER and getattr(ad, "restart_on_game_over", False):
            obs = env.step(GameAction.RESET)
            total += 1
            this_lvl += 1
            if obs is None:
                break
    lvls = obs.levels_completed if obs else prev
    ls = [level_score(baseline[i], per_level[i]) for i in range(len(per_level)) if i < len(baseline)]
    gs = game_score(ls, win_levels) if baseline else None
    return {
        "levels_completed": lvls,
        "win_levels": win_levels,
        "per_level_actions": per_level,
        "baseline": baseline,
        "game_score": gs,
        "total_actions": total,
    }


def main() -> None:
    max_actions = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    arc = Arcade(operation_mode=OperationMode.OFFLINE)
    for rep in range(reps):
        r = run(arc, max_actions)
        gs = f"{r['game_score']:.4f}" if r["game_score"] is not None else "n/a"
        print(
            f"rep{rep}: levels={r['levels_completed']}/{r['win_levels']} "
            f"game_score={gs} per_level={r['per_level_actions']} "
            f"baseline={r['baseline']} total={r['total_actions']}"
        )


if __name__ == "__main__":
    main()
