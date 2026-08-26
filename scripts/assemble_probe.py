"""Drive the assemble tool against a live game and report how deep it gets."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.assemble import JigsawAssembleTool  # noqa: E402


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "cn04"
    cap = int(sys.argv[2] if len(sys.argv) > 2 else 400)
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = JigsawAssembleTool()
    simple = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
              4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    done = 0
    acted = 0
    marks = []
    print(f"  detect={tool.detect([], obs):.2f}")
    idle = 0
    while acted < cap and idle < 4:
        steps = tool.propose([], obs)
        if not steps:
            # A cleared board only turns into the next level when something acts; a corner click
            # is the cheapest thing that cannot select a piece.
            idle += 1
            obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})
            acted += 1
            new = int(getattr(obs, "levels_completed", done) or 0)
            if new != done:
                marks.append((new, acted))
                print(f"  level {new}: cleared at {acted} actions")
                done = new
            continue
        idle = 0
        for aid, xy in steps:
            if aid == 6 and xy is not None:
                obs = env.step(GameAction.ACTION6, data={"x": int(xy[0]), "y": int(xy[1])})
            else:
                obs = env.step(simple[aid])
            acted += 1
            new = int(getattr(obs, "levels_completed", done) or 0)
            if new != done:
                marks.append((new, acted))
                print(f"  level {new}: cleared at {acted} actions")
                done = new
                break
        state = str(getattr(obs, "state", ""))
        if "GAME_OVER" in state or "WIN" in state:
            print(f"  {state} at {acted}")
            break
    print(f"{title} assemble: {done} levels in {acted} actions  marks={marks}")


if __name__ == "__main__":
    main()
