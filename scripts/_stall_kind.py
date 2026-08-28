"""When a stuck game stalls, does the GAME's own budget end it, or OUR action cap?

The two have opposite prescriptions. If the game's per-level allowance runs out, the tool must play
the level in fewer actions and more search makes it worse. If our cap ends the run with the game
still alive, deeper search is exactly what is missing.

Expected feedback: a GAME_OVER (or a level that stops advancing while actions remain) names the
first case; running to the cap with the state still playable names the second.
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
    lvl = 0
    last_up = 0
    overs = 0
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            print(f"{title}: agent stopped itself at step {step}, level {lvl}")
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        state = str(getattr(obs, "state", ""))
        if state.endswith("GAME_OVER"):
            overs += 1
        now = int(getattr(obs, "levels_completed", lvl) or 0)
        if now != lvl:
            lvl, last_up = now, step
    print(f"{title}: {lvl} levels, {step + 1} actions used of {cap}, "
          f"last level-up at {last_up}, GAME_OVER frames seen {overs}")


if __name__ == "__main__":
    main()
