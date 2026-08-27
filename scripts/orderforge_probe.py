"""Drive OrderForgeTool alone, and sweep its bid across every sample game.

Four modes, because a tool owes two different things and only one of them is visible from its
own game. ``play`` reports what it can clear on one board -- run it against the archived copy
too, with ``ENVIRONMENTS_DIR`` pointing at the archive, because a tool that keys on a colour
census rather than on the mechanic goes from a confident bid to zero when two cells of four
thousand are redrawn. ``sweep`` reports what it bids on the other twenty-four opening frames,
and ``deep`` on every frame of a real run of each of them, which is the number that decides
whether registering it is safe: in a shared harness a wrong bid does not merely waste its own
turn, it takes the board off the tool that would have solved it. ``deep`` is the one that
matters -- a bid measured here went from 0.00 on all twenty-four title screens to 0.86 on one
of them thirty-nine turns in.

    uv run python scripts/orderforge_probe.py play <title> [budget]
    uv run python scripts/orderforge_probe.py sweep
    uv run python scripts/orderforge_probe.py deep [steps]
    uv run python scripts/orderforge_probe.py harness <title> [budget]

``harness`` is the third and it is the one that counts: it runs the REAL loop with this tool
added to the registered set, so the answer includes who actually got the turns. A tool can play
a game perfectly on its own and never be handed the board.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "src")


def _env(title: str):
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    return arcade.make(info.game_id), info


def play(title: str, cap: int) -> None:
    from arcengine import GameAction

    from admorphiq.tools.orderforge import OrderForgeTool

    env, info = _env(title)
    obs = env.reset()
    tool = OrderForgeTool()
    levels, marks = 0, []
    base = list(getattr(info, "baseline_actions", []) or [])
    for step in range(cap):
        if tool.detect([obs], obs) <= 0.0:
            print(f"[{step}] bid 0 -- withdrawing")
            break
        steps = tool.propose([obs], obs)
        if not steps:
            print(f"[{step}] no plan -- withdrawing")
            break
        _, xy = steps[0]
        obs = env.step(GameAction.ACTION6, data={"x": int(xy[0]), "y": int(xy[1])})
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step + 1))
            levels = now
            tool.reset()
        if str(getattr(obs, "state", "")).endswith("GAME_OVER"):
            print(f"[{step}] board lost")
            break
    print(f"{title}: {levels} levels in {step + 1} actions   clears at {marks}")
    if base:
        cost = [b - a for a, b in zip([0] + [m[1] for m in marks], [m[1] for m in marks])]
        print(f"   per level {cost} vs human {base[:len(cost)]}")


def sweep() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools.orderforge import OrderForgeTool

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    hits = 0
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        name = (info.title or info.game_id).lower()
        try:
            env = arcade.make(info.game_id)
            obs = env.reset()
            bid = OrderForgeTool().detect([obs], obs)
        except Exception as exc:  # noqa: BLE001 - a game that will not load is still a report
            print(f"{name:8s} ERROR {exc}")
            continue
        if bid > 0:
            hits += 1
        print(f"{name:8s} {bid:.3f}")
    print(f"non-zero bids: {hits}")


def deep(cap: int, own: str) -> None:
    """Bid on EVERY frame of a real run of every other game, not just the opening one.

    A first-frame sweep is not the selectivity test the harness applies. The harness re-asks on
    every re-decide, and a board changes: panels open, pieces are cleared, colours are repainted.
    A tool that bids zero on the title screen and 0.9 on level four still takes the board off
    the tool that was solving it.
    """
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.orderforge import OrderForgeTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    worst = 0.0
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        name = (info.title or info.game_id).lower()
        if own and name.startswith(own):
            continue
        env = arcade.make(info.game_id)
        obs = env.reset()
        agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
        probe = OrderForgeTool()
        frames = [obs]
        hi = 0.0
        for _ in range(cap):
            if agent.is_done(frames, obs):
                break
            hi = max(hi, float(probe.detect(frames, obs)))
            act = agent.choose_action(frames, obs)
            data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
            obs = env.step(act, data=data) if data else env.step(act)
            frames.append(obs)
        worst = max(worst, hi)
        print(f"{name:8s} peak bid {hi:.3f}", flush=True)
    print(f"worst bid on another game: {worst:.3f}")


def harness(title: str, cap: int) -> None:
    """Run the real harness loop with this tool alongside the registered ones."""
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.orderforge import OrderForgeTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    env, _ = _env(title)
    obs = env.reset()
    tools = default_tools()
    tools = [OrderForgeTool(), *tools] if os.environ.get("ORDERFORGE_FIRST") else [
        *tools, OrderForgeTool()]
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    picks: dict[str, int] = {}
    marks: list[tuple[int, int]] = []
    levels = step = 0
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
    print(f"{title} HARNESS: {levels} levels in {step + 1} actions   clears at {marks}")
    print(f"   who acted: {dict(sorted(picks.items(), key=lambda kv: -kv[1])[:4])}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    if mode == "deep":
        deep(int(sys.argv[2]) if len(sys.argv) > 2 else 250,
             os.environ.get("ORDERFORGE_OWN", ""))
    elif mode == "harness":
        harness(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1500)
    elif mode == "play":
        play(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 400)
    else:
        sweep()
