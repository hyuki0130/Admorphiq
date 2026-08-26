"""Drive the instruction-word tool against a live game and report how deep it gets.

The whole animation matters here — one action returns the entire frame stack the run produced —
so this driver hands the tool the raw observation and never flattens it.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.progbits import ProgramBitsTool  # noqa: E402


def main() -> None:
    import numpy as np
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "tn36"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
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
            print(f"  idle at {acted} actions vocab={tool._vocab}")
            b = tool._perceive(np.asarray(obs.frame)[-1])
            print("     board", None if b is None else (b.piece, b.goal, b.bar.read(np.asarray(obs.frame)[-1])))
            continue
        idle = 0
        if len(steps) == 1 and steps[0] == getattr(tool, "_run_step", None):
            print(f"    RUN @{acted} bad={sorted(tool._bad)}")
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
        _ = np
    print(f"{title} progbits: {done} levels in {acted} actions  [{', '.join(marks)}]")


if __name__ == "__main__":
    main()
