"""Validation harness: score the ARC-AGI-3 agent using the real competition metric.

Metric (exact implementation):
  Per level:   s = min(human_actions / agent_actions, 1.0) ** 2
  Per game:    weighted mean over completed levels, weight = 1-indexed level index.
               Only completed levels contribute a positive numerator; uncompleted
               levels contribute 0 and are NOT included in the weighted sum —
               but they ARE included in the denominator because the game's total
               possible weight is the sum of all level indices up to win_levels.
               Choice rationale: the competition penalises partial completion by
               spreading total weight over all levels, including those not cleared.
               A game with 3 levels and only level-1 cleared earns
               weight_sum=1 in the numerator vs denominator weight_sum=1+2+3=6,
               so game_score = (1*s1) / 6.  This matches the spirit of
               "efficiency of full-game completion".
  Total:       arithmetic mean of per-game scores across games with baselines.
               Games lacking baseline_actions are excluded and reported separately.

Usage:
  uv run python scripts/score_efficiency.py --agent ensemble [--games 5] \\
      [--out scripts/efficiency_score.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402

from admorphiq.adapter import AdmorphiqAdapter  # noqa: E402
from admorphiq.general_agent import GeneralAgent  # noqa: E402


def _make_agent(name: str, game_id: str | None = None):
    """Build the agent object for the given ``--agent`` name.

    Both agents expose the harness contract ``is_done(frames, latest_frame)``
    / ``choose_action(frames, latest_frame)`` over the raw arcengine
    observation, so the run loop is agent-agnostic.

    ``game_id`` is threaded through so per-game-aware agents (the online RL
    agent's progress log) can label their output.
    """
    if name == "graph_frontier":
        from admorphiq.graph_frontier_agent import GraphFrontierAgent

        # Training-free HUD-masked state-graph + frontier-BFS agent. Knobs are
        # read from GF_MAX_CLICKS / GF_HUD_THRESHOLD / GF_GIVEUP env vars inside
        # the agent, so no wiring is needed here.
        return GraphFrontierAgent()
    if name in ("random", "stochastic"):
        import os

        from admorphiq.random_agent import _STOCHASTIC_SEED_OFFSET, RandomAgent

        # Calibration baselines (R34): uniform-random action selection; the
        # "stochastic" variant avoids immediately repeating a no-op action.
        seed_env = os.environ.get("RL_SEED", "").strip()
        base_seed = int(seed_env) if seed_env else None
        if name == "stochastic":
            seed = None if base_seed is None else base_seed + _STOCHASTIC_SEED_OFFSET
            return RandomAgent(seed=seed, avoid_repeat_noop=True)
        return RandomAgent(seed=base_seed, avoid_repeat_noop=False)
    if name == "general":
        return GeneralAgent()
    if name == "paint_flood":
        from admorphiq.paint_flood_agent import PaintFloodAgent

        # LLM-free paint tool: detect click-flood mechanic -> click fill points.
        return PaintFloodAgent()
    if name == "worldmodel":
        from admorphiq.world_model_agent import WorldModelAgent

        return WorldModelAgent()
    if name == "online_rl":
        import os

        from admorphiq.online_rl_agent import OnlineRLAgent

        # Warm-start from BC v6 as an exploration prior unless disabled
        # (RL_NO_WARMSTART=1 trains the per-game policy from scratch).
        warmstart = os.environ.get("RL_NO_WARMSTART", "").strip().lower() not in (
            "1", "true", "yes", "on",
        )
        # RL_SEED makes the stochastic agent reproducible — single-run clear/miss
        # is variance, so the K-seed harness varies this to measure a clear-RATE.
        seed_env = os.environ.get("RL_SEED", "").strip()
        seed = int(seed_env) if seed_env else None
        return OnlineRLAgent(warmstart=warmstart, seed=seed, game_id=game_id)
    if name == "bc":
        import os

        from admorphiq.bc_agent import DEFAULT_WEIGHTS, BCPolicyAgent

        # Optional override so a freshly-trained checkpoint (e.g. bc_policy_v2.pt)
        # can be scored without touching the agent. Falls back to the default.
        weights = os.environ.get("BC_WEIGHTS") or DEFAULT_WEIGHTS
        return BCPolicyAgent(weights_path=weights)
    if name == "ensemble_bc":
        from admorphiq.ensemble_bc_agent import EnsembleBCAgent

        return EnsembleBCAgent()
    return AdmorphiqAdapter()

# ─────────────────────────────── scoring maths ──────────────────────────────


def level_score(human_actions: int, agent_actions: int) -> float:
    """Return the per-level efficiency score.

    s = min(human_actions / agent_actions, 1.0) ** 2

    Args:
        human_actions: Baseline action count for this level (from EnvironmentInfo).
        agent_actions: Number of actions the agent used to clear this level.

    Returns:
        Score in [0.0, 1.0].  Returns 0.0 when agent_actions <= 0.
    """
    if agent_actions <= 0:
        return 0.0
    ratio = human_actions / agent_actions
    return min(ratio, 1.0) ** 2


def game_score(
    per_level_scores: list[float],
    win_levels: int,
) -> float:
    """Return the per-game weighted mean efficiency score.

    Weights are 1-indexed level indices: level 1 → weight 1, level k → weight k.
    The denominator is the sum of ALL level weights (1+2+…+win_levels), so
    uncompleted levels reduce the game score even though they contribute 0 to
    the numerator.

    Args:
        per_level_scores: List of per-level scores in order (index 0 = level 1).
                          May be shorter than win_levels if some levels were not reached.
        win_levels: Total number of levels in the game.

    Returns:
        Score in [0.0, 1.0].
    """
    if win_levels <= 0:
        return 0.0
    total_weight = sum(range(1, win_levels + 1))  # 1+2+…+win_levels
    numerator = sum((i + 1) * s for i, s in enumerate(per_level_scores))
    return numerator / total_weight


def total_score(game_scores: list[float]) -> float:
    """Return the arithmetic mean of per-game scores.

    Args:
        game_scores: One score per game that had a usable baseline.

    Returns:
        Score in [0.0, 1.0], or 0.0 if the list is empty.
    """
    if not game_scores:
        return 0.0
    return sum(game_scores) / len(game_scores)


# ─────────────────────────────── run loop ───────────────────────────────────

_MAX_ACTIONS = 50_000  # per-game budget (matches WikiAgent default)


def run_game(
    arcade: Arcade,
    game_id: str,
    baseline: list[int] | None,
    agent_name: str = "ensemble",
    max_actions: int = _MAX_ACTIONS,
) -> dict[str, Any]:
    """Run one game with the selected agent and record per-level action counts.

    Returns a dict with keys:
      game_id, title, win_levels, levels_completed,
      per_level (list of {level, agent_actions, human_actions, score}),
      game_score, has_baseline, error (only on failure)
    """
    adapter = _make_agent(agent_name, game_id=game_id)

    env = arcade.make(game_id)
    if env is None:
        return {"game_id": game_id, "error": "make() returned None"}

    obs = env.observation_space
    if obs is None:
        return {"game_id": game_id, "error": "No observation_space after make()"}

    win_levels: int = obs.win_levels
    prev_levels: int = obs.levels_completed
    action_count_total: int = 0
    action_count_this_level: int = 0
    level_action_counts: list[int] = []  # actions used per completed level (1-indexed order)

    start = time.time()

    # Agents that learn online across attempts (e.g. the test-time RL agent)
    # need many episodes of the SAME game: on GAME_OVER they RESET and keep
    # their per-game model/buffer instead of the run ending. This is faithful
    # to the real eval (the agent keeps acting until WIN or the action budget;
    # GAME_OVER just resets the current attempt) — action_count_total keeps
    # accumulating, so the squared-efficiency metric still penalises waste.
    restart_on_game_over = bool(getattr(adapter, "restart_on_game_over", False))

    while action_count_total < max_actions:
        if adapter.is_done([], obs):
            break

        action = adapter.choose_action([], obs)
        if not isinstance(action, GameAction):
            break

        if action.is_complex():
            obs = env.step(action, data=action.action_data.model_dump())
        else:
            obs = env.step(action)

        if obs is None:
            break

        action_count_total += 1
        action_count_this_level += 1

        current_levels: int = obs.levels_completed
        if current_levels > prev_levels:
            # One or more level transitions happened (usually exactly one).
            for _ in range(current_levels - prev_levels):
                level_action_counts.append(action_count_this_level)
                action_count_this_level = 0
            prev_levels = current_levels

        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart_on_game_over:
                break
            # Revive the env for the next attempt; the agent keeps learning.
            obs = env.step(GameAction.RESET)
            action_count_total += 1
            action_count_this_level += 1
            if obs is None:
                break

    elapsed = time.time() - start
    levels_completed: int = obs.levels_completed if obs else prev_levels
    # Record the LLM goal hypothesis (when the general agent ran with an LLM)
    # so the bench output shows what the reasoning layer proposed per game.
    llm_hypothesis = getattr(adapter, "last_hypothesis", None)

    # Build per-level records.
    per_level: list[dict[str, Any]] = []
    level_scores: list[float] = []

    for idx, agent_acts in enumerate(level_action_counts):
        level_num = idx + 1  # 1-indexed
        if baseline is not None and idx < len(baseline):
            human_acts = baseline[idx]
            ls = level_score(human_acts, agent_acts)
        else:
            human_acts = None
            ls = 0.0  # no baseline for this level → 0 contribution

        per_level.append(
            {
                "level": level_num,
                "agent_actions": agent_acts,
                "human_actions": human_acts,
                "score": round(ls, 6),
            }
        )
        level_scores.append(ls)

    has_baseline = baseline is not None and len(baseline) > 0
    gscore = game_score(level_scores, win_levels) if has_baseline else None

    return {
        "game_id": game_id,
        "win_levels": win_levels,
        "levels_completed": levels_completed,
        "elapsed_s": round(elapsed, 2),
        "total_actions": action_count_total,
        "per_level": per_level,
        "game_score": round(gscore, 6) if gscore is not None else None,
        "has_baseline": has_baseline,
        "llm_hypothesis": llm_hypothesis,
    }


# ─────────────────────────────── CLI ────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Score agent efficiency against ARC-AGI-3 competition metric."
    )
    p.add_argument(
        "--agent",
        default="ensemble",
        help="Agent name tag recorded in output (default: ensemble). "
        "Currently only 'ensemble' (AdmorphiqAdapter) is wired up.",
    )
    p.add_argument(
        "--games",
        default="all",
        help="Number of games to run (integer) or 'all' (default: all).",
    )
    p.add_argument(
        "--titles",
        default=None,
        help="Comma-separated case-insensitive title/id substrings to filter "
        "games (e.g. 'tu93,ar25,dc22,m0r0'). Overrides --games when set.",
    )
    p.add_argument(
        "--out",
        default="scripts/efficiency_score.json",
        help="Output JSON path (default: scripts/efficiency_score.json).",
    )
    p.add_argument(
        "--max-actions",
        type=int,
        default=_MAX_ACTIONS,
        help=f"Per-game action budget (default: {_MAX_ACTIONS}). Lower it for "
        "fast diagnostic runs — clears that exceed the cap score ~0 under the "
        "squared efficiency metric anyway, so the signal is preserved.",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = arcade.get_environments()

    if args.titles:
        wanted = [t.strip().lower() for t in args.titles.split(",") if t.strip()]
        seen_ids: set[str] = set()
        filtered = []
        for e in envs:
            hay = f"{e.game_id} {e.title or ''}".lower()
            if any(w in hay for w in wanted) and e.game_id not in seen_ids:
                seen_ids.add(e.game_id)
                filtered.append(e)
        envs = filtered
    elif args.games != "all":
        n = int(args.games)
        envs = envs[:n]

    print(f"Scoring {len(envs)} game(s) with agent '{args.agent}' …", flush=True)

    results: list[dict[str, Any]] = []
    scored_game_scores: list[float] = []
    n_excluded = 0

    for i, env_info in enumerate(envs):
        game_id = env_info.game_id
        title = env_info.title or game_id
        baseline = env_info.baseline_actions  # list[int] | None

        print(
            f"  [{i + 1}/{len(envs)}] {game_id} ({title}) "
            f"baseline={baseline} …",
            flush=True,
        )

        try:
            result = run_game(arcade, game_id, baseline, agent_name=args.agent,
                              max_actions=args.max_actions)
        except Exception as exc:
            result = {"game_id": game_id, "error": str(exc)}

        result["title"] = title
        results.append(result)

        if "error" in result:
            print(f"    ERROR: {result['error']}", flush=True)
            n_excluded += 1
            continue

        if not result.get("has_baseline"):
            print(
                f"    no_baseline — excluded from total score "
                f"(levels_completed={result['levels_completed']}/{result['win_levels']})",
                flush=True,
            )
            n_excluded += 1
            continue

        gs = result["game_score"]
        scored_game_scores.append(gs)
        print(
            f"    levels={result['levels_completed']}/{result['win_levels']}  "
            f"game_score={gs:.4f}  actions={result['total_actions']}",
            flush=True,
        )

    tscore = total_score(scored_game_scores)
    n_scored = len(scored_game_scores)

    summary = {
        "agent": args.agent,
        "n_games_run": len(envs),
        "n_games_scored": n_scored,
        "n_excluded": n_excluded,
        "total_score": round(tscore, 6),
        "total_score_pct": round(tscore * 100, 3),
        "games": results,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(
        f"\nTotal score: {tscore:.4f} ({tscore * 100:.2f}%)  "
        f"[{n_scored}/{len(envs)} games scored, {n_excluded} excluded]",
        flush=True,
    )
    print(f"Output written to: {out_path}", flush=True)


if __name__ == "__main__":
    main()
