"""Run ONE game through the real harness loop with the peg-jump tool registered.

⛔ This is the harness, not a private loop. `scripts/harness_probe.py` is the number that counts,
but it can only measure tools the registry already ships; this runs the SAME `UnifiedAgent` with
the same LLM-free signature fallback and the same execution contract, with `PegJumpTool` added to
the default set. Any difference between the two runs is therefore attributable to the tool.

    uv run python scripts/pegjump_probe.py <game-title-prefix> [max-actions] [--without]

`--without` drops the tool again, so the before/after pair is one command apart.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.pegjump import PegJumpTool

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    without = "--without" in sys.argv
    if not args:
        raise SystemExit(__doc__)
    title = args[0]
    cap = int(args[1]) if len(args) > 1 else 3000

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    tools = list(default_tools())
    if not without:
        tools.append(PegJumpTool())

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
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
    tag = "WITHOUT pegjump" if without else "WITH pegjump"
    top = sorted(picks.items(), key=lambda kv: -kv[1])[:4]
    print(f"{title} HARNESS ({tag}): {levels} levels in {step + 1} actions   clears at {marks}")
    print(f"   who acted: {dict(top)}")


if __name__ == "__main__":
    main()
