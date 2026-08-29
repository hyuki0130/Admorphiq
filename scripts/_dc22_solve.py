"""Does driving dc22's switch actually open the level?

The switch is confirmed reachable — a click at (24,48) or (24,52) advances one tile through four
types. What is NOT yet confirmed is the payoff: that some tile state lets the route through. Press
the switch k times, hand the board back to the agent, and see whether it clears.

Expected feedback: a clear at some k proves the tile state is the blocker and makes "press the
switch, then route" the whole fix. No clear at any k means the tile is not what stops gantry, and a
tool built for it would have been wasted.
"""
from __future__ import annotations

import sys


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.types import GameAction

    k = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("dc22"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    for _ in range(4000):
        if int(getattr(obs, "levels_completed", 0) or 0) >= 5:
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    if int(getattr(obs, "levels_completed", 0) or 0) < 5:
        print("did not reach level 6")
        return

    for _ in range(k):
        obs = env.step(agent._convert(GameAction.coordinate(48, 24)),
                       data={"x": 48, "y": 24})
        frames.append(obs)
    # Hand it back and let the tools play on with the switch in this state.
    for _ in range(600):
        if int(getattr(obs, "levels_completed", 0) or 0) != 5:
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    lvl = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"switch pressed {k}x -> levels_completed {lvl}"
          f"{'   LEVEL 6 CLEARED' if lvl > 5 else ''}")


if __name__ == "__main__":
    main()
