"""Does wa30 fail its last level on the BUDGET rather than on understanding?

Level 9 declares StepCounter 70 — the tightest allowance in the game, against 200 on level 1 — and
the tool clears 8 of 9. If it spends more than 70 actions there, the level is lost to efficiency and
not to a missing mechanic, which is a completely different repair.

⛔ Direction named explicitly (rule 7f): report the level number, never just "it changed".
"""
from __future__ import annotations


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("wa30"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    lvl = 0
    spent: dict[int, int] = {}
    tool: dict[int, str] = {}
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", lvl) or 0)
        if now != lvl:
            print(f"  level {lvl + 1} -> {now + 1} after {spent.get(lvl, 0)} actions"
                  f" (tool {tool.get(lvl)})", flush=True)
            lvl = now
        spent[lvl] = spent.get(lvl, 0) + 1
        tool[lvl] = str(agent._current)
    print(f"stopped at level {lvl + 1}; actions on it {spent.get(lvl, 0)}"
          f" (tool {tool.get(lvl)}); the level's own budget is 70", flush=True)


if __name__ == "__main__":
    main()
