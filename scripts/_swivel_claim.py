"""Which games does `swivel` actually act on? Measured, not inferred from `detect`'s source.

A tool's cost to the tool SET is invisible to the tool's own author (rule 8), so before touching
`swivel` this names every board it takes a turn on. The candidates are the ACTION6-only games —
`detect` returns 0.0 the moment any simple action is offered — plus `cn04`, whose action set is
not a literal in its source.

Reports, per game: how many actions each tool took, the level reached, and whether swivel ever
DELEGATED (it hands boards with no one-way control to the telescoping planner from inside itself,
so a change here can move a game swivel does not appear to plan).

Run:  bash scripts/pfan.sh swivclaim scripts/_swivel_claim.py 7 "400" 4
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")

TITLES = ["ft09", "lp85", "r11l", "s5i5", "tn36", "vc33", "cn04"]


def main() -> None:
    job = int(sys.argv[1])
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    title = TITLES[(job - 1) % len(TITLES)]

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    sw = agent.tools.get("swivel")
    frames = [obs]
    who: dict[str, int] = {}
    delegated = False
    best = 0
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        who[str(agent._current)] = who.get(str(agent._current), 0) + 1
        if sw is not None and getattr(sw, "_delegate", None) is not None:
            delegated = True
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        best = max(best, int(getattr(obs, "levels_completed", 0) or 0))
    print(json.dumps({"game": title, "actions": step + 1, "levels": best,
                      "swivel_acted": who.get("swivel", 0),
                      "swivel_delegated": delegated, "who": who}))


if __name__ == "__main__":
    main()
