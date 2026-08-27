"""Drive the instruction-word tool against a live game and report how deep it gets.

The whole animation matters here — one action returns the entire stack of frames the run produced,
and that stack is the only place the meaning of an instruction is visible — so this driver hands
the tool the raw observation and never flattens it.

    uv run python scripts/progbits_probe.py [title] [action cap]
    uv run python scripts/progbits_probe.py --sweep     # every sample game's bid on its first frame
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.progbits import ProgramBitsTool  # noqa: E402


def sweep() -> None:
    """Every sample game's opening bid. A tool ships only at 0.00 on the games it does not own."""
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    worst = 0.0
    for info in sorted(arcade.get_environments(), key=lambda i: i.title or i.game_id):
        title = (info.title or info.game_id).lower()
        env = arcade.make(info.game_id)
        bid = ProgramBitsTool().detect([], env.reset())
        if bid:
            print(f"  {title:<12} {bid:.2f}")
        if not title.startswith("tn36"):
            worst = max(worst, bid)
    print(f"highest bid on a game that is not this tool's: {worst:.2f}")


def play(title: str, cap: int) -> None:
    import numpy as np
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = ProgramBitsTool()
    print(f"  detect={tool.detect([], obs):.2f}")
    done, acted, idle = 0, 0, 0
    marks: list[str] = []
    while acted < cap and idle < 4:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            continue
        idle = 0
        for aid, xy in steps:
            if aid == 6:
                obs = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
            else:
                obs = env.step(getattr(GameAction, f"ACTION{aid}"))
            acted += 1
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new > done:
            marks.append(f"L{new}@{acted}")
            print(f"  level {new} cleared at {acted} actions")
            done = new
            tool.reset()
        if "GAME_OVER" in str(getattr(obs, "state", "")):
            print(f"  GAME_OVER at {acted}")
            break
        if not len(np.asarray(obs.frame)):
            break
    print(f"{title} progbits: {done} levels in {acted} actions  [{', '.join(marks)}]")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--sweep":
        sweep()
        return
    play(sys.argv[1] if len(sys.argv) > 1 else "tn36",
         int(sys.argv[2]) if len(sys.argv) > 2 else 400)


if __name__ == "__main__":
    main()
