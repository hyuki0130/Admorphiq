"""Run the real harness with the shepherd tool added, and check it bids on nothing else.

Two questions, both of which a per-tool probe answers wrongly:

  ``shepherd_probe.py <title> [cap] [--first]``  — the whole game through `harness/loop.py` with the shepherd
  registered alongside the default set, reporting levels, actions and which tool actually acted.
  This is the number that counts: a tool can be perfect alone and still clear fewer levels in the
  harness, because it never gets a turn, or gets the board handed away on a transitional frame.

  ``shepherd_probe.py --sweep [actions]`` — the FIRST-FRAME bid on every sample game, and the bid
  again after a few actions have been spent, since one of the two signals this tool keys on is only
  drawn once something has walked. A tool in a shared harness steals turns from the tool that could
  solve the board, so a bid above zero anywhere else is a defect whatever it scores on its own game.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")


def _no_llm(*_a, **_k):
    raise RuntimeError("LLM-free: the signature fallback is what this measures")


def play(title: str, cap: int, first: bool = False) -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.shepherd import ShepherdRelayTool

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    # ⛔ Registration ORDER decides this, not the bid. The harness keeps whichever tool it picked
    # for the first action across every level-up (deliberately — clearing `_current` there cost
    # measured clears), and it breaks a tie on `detect` by taking the first tool registered. On a
    # board whose deep levels are the point, a tool that bids higher only from level 7 onward
    # therefore never plays at all. `--first` measures the other ranking.
    tools = default_tools()
    tools = [ShepherdRelayTool(), *tools] if first else [*tools, ShepherdRelayTool()]
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
    top = sorted(picks.items(), key=lambda kv: -kv[1])[:4]
    print(f"{title} HARNESS: {levels} levels in {step + 1} actions   clears at {marks}")
    print(f"   who acted: {dict(top)}")


def sweep(actions: int) -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.tools.base import availability
    from admorphiq.tools.shepherd import ShepherdRelayTool
    from admorphiq.types import ActionType, GameAction

    convert = AdmorphiqAdapter._convert_action
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    fired = []
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        name = (info.title or info.game_id).lower()
        env = arcade.make(info.game_id)
        obs = env.reset()
        tool = ShepherdRelayTool()
        first = tool.detect([obs], obs)
        later = first
        # ⛔ Ask again after a few actions. One of the two things this tool keys on is a colour
        # that has been SEEN TO STEP, and on a level's first frame nothing has stepped yet, so a
        # single-frame sweep reports a selectivity this tool does not actually have.
        for _ in range(actions):
            simple, action6 = availability(obs)
            steps = tool.propose([obs], obs)
            step = steps[0] if steps else None
            if step is None or (step[1] is None and step[0] not in simple):
                step = (simple[0], None) if simple else ((6, (32, 32)) if action6 else None)
            if step is None:
                break
            aid, xy = step
            act = (GameAction.coordinate(int(xy[0]), int(xy[1])) if xy is not None
                   else GameAction.simple(ActionType(aid)))
            act = convert(act)
            data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
            obs = env.step(act, data=data) if data else env.step(act)
            later = max(later, tool.detect([obs], obs))
        flag = "  <-- BIDS" if max(first, later) > 0 else ""
        if max(first, later) > 0:
            fired.append(name)
        print(f"{name:10s} first={first:.2f} after{actions}={later:.2f}{flag}")
    print(f"\nbids on {len(fired)} of the sample games: {fired}")


def main() -> None:
    if sys.argv[1] == "--sweep":
        sweep(int(sys.argv[2]) if len(sys.argv) > 2 else 12)
        return
    args = [a for a in sys.argv[1:] if a != "--first"]
    play(args[0], int(args[1]) if len(args) > 1 else 1500, "--first" in sys.argv)


if __name__ == "__main__":
    main()
