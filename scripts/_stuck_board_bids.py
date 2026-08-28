"""On the board that actually stops a game, what does EVERY tool say?

`bid_matrix.py` asks every tool about each game's FIRST frame, which is where the specialist is
obviously right. The board that matters is the one where the specialist has just fallen silent —
measured 2026-08-29, every stuck game retires its specialist through the EMPTY path and hands the
level to the general searcher. Whether any OTHER registered tool has a plan there has never been
asked, and rule 7b says to sweep for an unused asset before digging.

Expected feedback: a tool that both bids above zero AND proposes actual steps on that board is an
asset the harness is not using. All-zero bids and empty proposals mean the tool set genuinely has
nothing for this board, and the gap needs new capability rather than better routing.
"""
from __future__ import annotations

import sys


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    title = sys.argv[1]
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    # Play until the agent gives up — that is the board the game is actually lost on.
    for _ in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    lvl = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"{title}: gave up on level {lvl + 1}; retired={sorted(agent._failed)}", flush=True)

    # A FRESH instance of every tool — the ones the run used are poisoned by their own history,
    # and the question is what the tool set can do with this board, not what this run's copies can.
    for tool in default_tools():
        name = tool.name
        try:
            bid = float(tool.detect(frames, obs))
        except Exception as exc:  # noqa: BLE001
            print(f"  {name:12s} detect raised {type(exc).__name__}", flush=True)
            continue
        try:
            steps = tool.propose(frames, obs)
        except Exception as exc:  # noqa: BLE001
            print(f"  {name:12s} bid {bid:.2f}  propose raised {type(exc).__name__}", flush=True)
            continue
        if bid > 0 or steps:
            print(f"  {name:12s} bid {bid:.2f}  proposes {len(steps)} step(s) {steps[:2]}",
                  flush=True)


if __name__ == "__main__":
    main()
