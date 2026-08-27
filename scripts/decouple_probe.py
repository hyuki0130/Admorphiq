"""Drive the decouple tool alone, and sweep what it BIDS on every sample game.

Two questions, because a tool owes the set two different things and only one of them is about
its own board:

    decouple_probe.py play <title> [cap]     does it clear, in how many actions per level
    decouple_probe.py bids                   what does it bid on all 25 — must be 0.00 on 24

Set ENVIRONMENTS_DIR to point at an archived copy to check the answer survives a re-render.
"""

from __future__ import annotations

import sys
import time

sys.path.insert(0, "src")


def _arcade():
    from arc_agi import Arcade, OperationMode
    return Arcade(operation_mode=OperationMode.OFFLINE)


def play(title: str, cap: int) -> None:
    from admorphiq.tools.decouple import CoupledPairTool

    arcade = _arcade()
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = CoupledPairTool()
    frames = [obs]
    levels = 0
    marks: list[tuple[int, int]] = []
    queue: list = []
    idle = 0
    began = time.time()
    step = 0
    for step in range(cap):
        if not queue:
            queue = list(tool.propose(frames, obs))
            if not queue:
                # What the harness does with an empty proposal, so the count here is the count there.
                idle += 1
                if idle > 8:
                    print(f"   no plan at step {step}")
                    break
                queue = [(1, None)]
            else:
                idle = 0
        aid, xy = queue.pop(0)
        act = _convert(aid, xy)
        obs = env.step(act, data={"x": xy[0], "y": xy[1]}) if xy else env.step(act)
        frames.append(obs)
        if str(getattr(obs, "state", "")).endswith("WIN"):
            levels += 1
            marks.append((levels, step + 1))
            print("   WON")
            break
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step + 1))
            levels = now
            tool.reset()
            queue = []
    per = [b - a for a, b in zip([0] + [m[1] for m in marks], [m[1] for m in marks])]
    print(f"{title}: {levels} levels in {step + 1} actions   clears at {marks}")
    print(f"   per-level actions: {per}   baseline {info.baseline_actions}   "
          f"elapsed {time.time() - began:.1f}s")


def _convert(aid: int, xy):
    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.types import ActionType, GameAction
    ga = GameAction.coordinate(int(xy[0]), int(xy[1])) if xy else GameAction.simple(ActionType(aid))
    return AdmorphiqAdapter._convert_action(ga)


def bids(depth: int) -> None:
    """Highest bid seen over `depth` actions of each game.

    ⛔ Reading only the first frame is a known blind spot: a mechanic that appears at level 2 is
    invisible to it, in BOTH directions — a tool gated on depth looks inert, and a tool that would
    fire wrongly at depth looks clean. Playing on is the cheapest thing that sees any of it.
    """
    from admorphiq.tools.decouple import CoupledPairTool

    arcade = _arcade()
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        env = arcade.make(info.game_id)
        obs = env.reset()
        tool = CoupledPairTool()
        top, when, levels = 0.0, 0, 0
        for step in range(depth):
            try:
                bid = float(tool.detect([obs], obs))
            except Exception as exc:  # noqa: BLE001 — a throw is a zero bid AND a defect to see
                print(f"   {(info.title or info.game_id):<10} RAISED {exc}")
                break
            if bid > top:
                top, when = bid, step
            acts = list(getattr(obs, "available_actions", []) or [])
            ids = [int(getattr(a, "value", a)) for a in acts]
            simple = [i for i in ids if 1 <= i <= 5]
            pick = simple[step % len(simple)] if simple else 6
            xy = (7 + (step * 11) % 50, 7 + (step * 17) % 50)
            obs = env.step(_convert(pick, None)) if pick != 6 \
                else env.step(_convert(6, xy), data={"x": xy[0], "y": xy[1]})
            levels = max(levels, int(getattr(obs, "levels_completed", 0) or 0))
            if str(getattr(obs, "state", "")).endswith(("GAME_OVER", "WIN")):
                obs = env.reset()
        else:
            print(f"   {(info.title or info.game_id):<10} max bid {top:.2f} (first at step {when}, "
                  f"reached level {levels + 1})")


if __name__ == "__main__":
    if sys.argv[1] == "bids":
        bids(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    else:
        play(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1200)
