"""Which tool ACTS on each of the 25, so a change to one tool knows its blast radius.

⛔ A tool that bids is not a tool that acts, and only the acting one can regress a game. The
harness re-decides after every action, so the answer is a histogram over the whole run, not the
first pick. One game per job.
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")


def main() -> None:
    from pathlib import Path

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    job = int(sys.argv[1])
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
    titles = sorted(p.name for p in Path("environment_files").iterdir() if p.is_dir())
    if job > len(titles):
        return
    title = titles[job - 1]

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what the harness scores")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    picks: dict[str, int] = {}
    levels = int(getattr(obs, "levels_completed", 0) or 0)
    start = levels
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        picks[str(agent._current)] = picks.get(str(agent._current), 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        levels = int(getattr(obs, "levels_completed", levels) or 0)
    print(json.dumps({"title": title, "levels_completed": levels,
                      "greater_than_start": levels > start,
                      "actions": step + 1,
                      "acted": dict(sorted(picks.items(), key=lambda kv: -kv[1]))}))


if __name__ == "__main__":
    main()
