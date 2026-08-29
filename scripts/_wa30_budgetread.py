"""Can BudgetReader read wa30's declared budgets off the frame?

`tools/budget.py` exists, its docstring records that thirteen of the twenty-five games declare a
per-level budget and END on overrun, and exactly ONE tool imports it. shepherd — which plays every
wa30 level and spends 508 actions against level 9's allowance of 70 — does not, and its own docstring
lists reading the drawn budget as "still untested".

Before wiring anything, check the reader works here: play wa30 and compare what it reports against
the game's declared StepCounter per level (200, 70, 100, 100, 125, 75, 125, 150, 70).
"""
from __future__ import annotations


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.budget import BudgetReader

    declared = {1: 200, 2: 70, 3: 100, 4: 100, 5: 125, 6: 75, 7: 125, 8: 150, 9: 70}

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("wa30"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    reader = BudgetReader()
    frames = [obs]
    lvl = 0
    n = 0
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        n += 1
        fr = getattr(obs, "frame", None)
        if fr:
            reader.observe(fr[-1])
        now = int(getattr(obs, "levels_completed", lvl) or 0)
        if now != lvl:
            print(f"  level {lvl + 1}: reader total={reader.total()} remaining={reader.remaining()}"
                  f"  declared={declared.get(lvl + 1)}  spent={n}", flush=True)
            lvl, n = now, 0
            reader.reset()
    print(f"  level {lvl + 1} (stuck): reader total={reader.total()}"
          f" remaining={reader.remaining()}  declared={declared.get(lvl + 1)}  spent={n}",
          flush=True)


if __name__ == "__main__":
    main()
