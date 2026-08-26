"""Drive the stamp-paint tool against a live game, and measure what it bids elsewhere.

Purpose: two numbers decide whether a generic tool may ship. How deep it gets on the board
whose mechanic it recovers, in actions against that board's own human baseline; and the
highest confidence it reports on every OTHER sample game, which must be zero — a tool that
bids on a board it cannot solve spends that game's whole budget and costs the tool that could.

Expected feedback:
  `stamppaint_probe.py [title] [cap]`  plays one game and prints levels, the actions each
  level cost, and the baseline it is measured against.
  `stamppaint_probe.py --sweep`        prints the bid on every sample game's first frame.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from admorphiq.tools.stamppaint import StampPaintTool  # noqa: E402


def sweep() -> None:
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    seen: set[str] = set()
    rows: list[tuple[str, float]] = []
    for info in arcade.get_environments():
        key = (info.title or info.game_id).lower().split("-")[0][:4]
        if key in seen:
            continue
        env = arcade.make(info.game_id)
        obs = getattr(env, "observation_space", None)
        if obs is None:
            continue
        seen.add(key)
        # The observation must be read NOW: it does not survive the next make().
        rows.append((key, StampPaintTool().detect([], obs)))
    for key, bid in sorted(rows):
        print(f"  {key}  {bid:.2f}")
    others = [b for k, b in rows if b > 0.0]
    print(f"fired on {len(others)} of {len(rows)} games")


def play(title: str, cap: int) -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    simple = {
        1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
        4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7,
    }
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    baseline = list(getattr(info, "baseline_actions", None) or [])
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = StampPaintTool()
    print(f"{title}: bid {tool.detect([], obs):.2f}   baseline {baseline}")

    done = 0
    acted = 0
    mark = 0
    idle = 0
    while acted < cap and idle < 2:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            print(f"  no proposal at level {done} after {acted} actions")
            break
        idle = 0
        for act, xy in steps:
            if act == 6:
                obs = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
            else:
                obs = env.step(simple[act])
            acted += 1
        now = int(getattr(obs, "levels_completed", done) or 0)
        state = str(getattr(obs, "state", ""))
        if now != done:
            spent = acted - mark
            human = baseline[done] if done < len(baseline) else None
            note = f" vs human {human}" if human else ""
            print(f"  level {now}: cleared in {spent} actions{note}")
            done, mark = now, acted
            tool.reset()
        if "GAME_OVER" in state:
            print(f"  GAME_OVER at {acted} actions")
            break
        if "WIN" in state:
            print("  WIN")
            break
    print(f"{title} stamppaint: {done} levels in {acted} actions")


def main() -> None:
    if "--sweep" in sys.argv:
        sweep()
        return
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    play(args[0] if args else "cd82", int(args[1]) if len(args) > 1 else 600)


if __name__ == "__main__":
    main()
