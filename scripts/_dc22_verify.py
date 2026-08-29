"""Does ONE click at (x=8, y=26) clear dc22's level 6 from arrival?

The sweep that found it clicks sequentially, so by the time it reached that cell it had already made
hundreds of clicks. The win may depend on that history rather than on the cell. Reach level 6 and
click it once.
"""
from __future__ import annotations


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.types import GameAction

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("dc22"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    n = 0
    for _ in range(4000):
        if int(getattr(obs, "levels_completed", 0) or 0) >= 5:
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        n += 1
        if n % 150 == 0:
            print(f"  ...{n} actions", flush=True)
    if int(getattr(obs, "levels_completed", 0) or 0) < 5:
        print("did not reach level 6", flush=True)
        return
    print(f"reached level 6 in {n} actions", flush=True)
    obs = env.step(agent._convert(GameAction.coordinate(8, 26)), data={"x": 8, "y": 26})
    lvl = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"ONE click at x=8,y=26 -> levels_completed {lvl}"
          f"{'   CLEARED' if lvl > 5 else '   no'}", flush=True)


if __name__ == "__main__":
    main()
