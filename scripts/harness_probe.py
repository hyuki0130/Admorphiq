"""Run ONE game through the real harness loop and report levels, actions and who acted.

⛔ Why this exists rather than a per-tool probe. Measured 2026-08-27, three distinct ways a tool's
own probe disagrees with the harness: the tool never gets a turn (it bid too low), it clears one
level and the board is taken on the level-up, or — the one no author can see — it holds every step
and still clears fewer levels, because the harness's execution contract differs from the probe's
(it resets tools on a level-up, feeds `observe` only its own transitions, and re-enters `propose`
after every action).

The harness is what is scored. This is the number that counts.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    title = sys.argv[1]
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 500

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    picks: dict[str, int] = {}
    marks: list[tuple[int, int]] = []
    levels = 0
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        picks[str(agent._current)] = picks.get(str(agent._current), 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step + 1))
            levels = now
    top = sorted(picks.items(), key=lambda kv: -kv[1])[:3]
    print(f"{title} HARNESS: {levels} levels in {step + 1} actions   clears at {marks}")
    print(f"   who acted: {dict(top)}")


if __name__ == "__main__":
    main()
