"""Local smoke test for KaggleBCAgent via REMOTE (NORMAL) mode.

Proves the official Agent run-loop + the trained BC policy produce valid
actions (including an ACTION6 with x/y) and reach a terminal/level state
without crashing. Drives the agent directly (no HTTP scorecard server)
against a single game with a low MAX_ACTIONS — fast, not a full regression.

Run: uv run python scripts/smoke_kaggle_bc_agent.py
"""

from __future__ import annotations

from arc_agi import Arcade, OperationMode
from arcengine import GameState

# Importing the agent installs the lightweight `agents` package shim.
from admorphiq.kaggle_bc_agent import KaggleBCAgent

NUM_GAMES = 1
MAX_ACTIONS = 40


def run_game(arc: Arcade, game_id: str) -> dict:
    env = arc.make(game_id)
    if env is None:
        return {"game_id": game_id, "error": "make() returned None"}

    agent = KaggleBCAgent(
        card_id="smoke",
        game_id=game_id,
        agent_name="kagglebc",
        ROOT_URL="local",
        record=False,
        arc_env=env,
    )
    agent.MAX_ACTIONS = MAX_ACTIONS

    raw = env.observation_space
    if raw is None:
        return {"game_id": game_id, "error": "no observation after make()"}
    frame = agent._convert_raw_frame_data(raw)

    state_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    action6_coords: list[tuple[int, int]] = []
    actions = 0
    while not agent.is_done([frame], frame) and actions < MAX_ACTIONS:
        action = agent.choose_action([frame], frame)
        action_counts[action.name] = action_counts.get(action.name, 0) + 1
        data = action.action_data.model_dump() if action.is_complex() else None
        if data is not None:
            action6_coords.append((data.get("x"), data.get("y")))
        raw = env.step(action, data=data)
        if raw is None:
            break
        frame = agent._convert_raw_frame_data(raw)
        agent.action_counter += 1
        actions += 1
        state_counts[str(frame.state)] = state_counts.get(str(frame.state), 0) + 1

    return {
        "game_id": game_id,
        "model_loaded": agent._bc._loaded,
        "actions": actions,
        "final_state": str(frame.state),
        "levels_completed": frame.levels_completed,
        "won": frame.state == GameState.WIN,
        "action_dist": action_counts,
        "action6_count": len(action6_coords),
        "action6_sample_coords": action6_coords[:5],
        "state_dist": state_counts,
    }


def main() -> None:
    arc = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arc.get_environments()
    print(f"Discovered {len(envs)} environments.")
    seen: set[str] = set()
    chosen = []
    for e in envs:
        base = e.game_id.split("-")[0]
        if base in seen:
            continue
        seen.add(base)
        chosen.append(e)
        if len(chosen) >= NUM_GAMES:
            break
    print(f"Smoke-testing: {[e.game_id for e in chosen]}\n")

    for env_info in chosen:
        print(f"=== {env_info.game_id} ({getattr(env_info, 'title', '?')}) ===")
        try:
            result = run_game(arc, env_info.game_id)
        except Exception as exc:  # noqa: BLE001 - smoke test: report, don't crash
            import traceback

            traceback.print_exc()
            result = {"game_id": env_info.game_id, "error": repr(exc)}
        for k, v in result.items():
            print(f"  {k}: {v}")
        print()


if __name__ == "__main__":
    main()
