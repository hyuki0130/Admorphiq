"""Measure the clone-walk tool THROUGH THE REAL HARNESS, and audit what else it claims.

Two things a tool author has to show and neither can be shown by a tool's own private probe:

  ``--game <title>``  runs `scripts/harness_probe.py`'s loop with this tool registered alongside
      the deployed set, so the number reported is the harness's — the one that is scored. A tool
      that clears a level in its own driver and never gets a turn in the harness has measured
      nothing.

  ``--falsepos``      asks `detect()` about the FIRST FRAME of every sample game. A tool must
      answer 0.0 everywhere its mechanic is absent: a consolation bid takes the turn from the
      tool that could have solved that board, and one such bid was measured taking a game from
      0.4762 to 0.0476. The audit prints every non-zero bid; anything but a single claim is a
      defect in the detector, not a detail.

Both run against the offline arcade, LLM-free, so the routing is the signature fallback — the
same path the deployed card takes.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")


def _tools():
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.clonewalk import CloneWalkTool

    return [*default_tools(), CloneWalkTool()]


def run_game(title: str, cap: int) -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
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
    top = sorted(picks.items(), key=lambda kv: -kv[1])[:4]
    print(f"{title} HARNESS: {levels} levels in {step + 1} actions   clears at {marks}")
    print(f"   who acted: {dict(top)}")


def false_positives() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools.clonewalk import CloneWalkTool

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    claimed: list[tuple[str, float]] = []
    for info in arcade.get_environments():
        name = (info.title or info.game_id).lower()
        env = arcade.make(info.game_id)
        obs = env.reset()
        bid = CloneWalkTool().detect([], obs)
        if bid > 0.0:
            claimed.append((name, bid))
        print(f"  {name:<24} bid {bid:.2f}")
    print(f"CLAIMED {len(claimed)} of the sample games: {claimed}")


def main() -> None:
    args = sys.argv[1:]
    if "--falsepos" in args:
        false_positives()
        return
    title = args[args.index("--game") + 1] if "--game" in args else args[0]
    cap = int(args[args.index("--cap") + 1]) if "--cap" in args else 1500
    run_game(title, cap)


if __name__ == "__main__":
    main()
