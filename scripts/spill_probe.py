"""Drive the spill tool against a live game and report how deep it gets.

Prints, per level, the actions the tool spent and the running total, so the numbers can be read
against the level's own declared budget and the human baseline.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.spill import SpillRouteTool  # noqa: E402


def sweep(depth: int) -> None:
    """Bid on every sample game, so the cost this tool imposes on the other boards is measured.

    A tool cannot see what its own confidence takes away from the others, so the number that
    matters is the HIGHEST bid it makes on a board it was not built for — measured here on the
    opening frame and again after a walk into the game, since a mechanic can appear a level deep.
    """
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    walk = [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4,
            GameAction.ACTION5, GameAction.ACTION7]
    worst = 0.0
    for info in arcade.get_environments():
        name = (info.title or info.game_id).lower()
        env = arcade.make(info.game_id)
        obs = env.reset()
        tool = SpillRouteTool()
        top = tool.detect([], obs)
        for i in range(depth):
            act = walk[i % len(walk)]
            obs = (env.step(GameAction.ACTION6, data={"x": (i * 7) % 64, "y": (i * 11) % 64})
                   if i % 3 == 2 else env.step(act))
            top = max(top, tool.detect([], obs))
            if "GAME_OVER" in str(getattr(obs, "state", "")):
                obs = env.reset()
        print(f"  {name[:12]:14s} {top:.2f}")
        if not name.startswith("sp80"):
            worst = max(worst, top)
    print(f"max bid away from home: {worst:.2f}")


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    if sys.argv[1:2] == ["--sweep"]:
        sweep(int(sys.argv[2]) if len(sys.argv) > 2 else 40)
        return
    title = sys.argv[1] if len(sys.argv) > 1 else "sp80"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = SpillRouteTool()
    acts = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
            4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    print(f"  detect={tool.detect([], obs):.2f}")
    done = 0
    acted = 0
    mark = 0
    idle = 0
    while acted < cap and idle < 3:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            continue
        idle = 0
        for aid, xy in steps:
            if aid == 6:
                obs = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
            else:
                obs = env.step(acts[aid])
            acted += 1
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new != done:
            print(f"  level {new}: cleared in {acted - mark} actions (total {acted})")
            done, mark = new, acted
        state = str(getattr(obs, "state", ""))
        if "GAME_OVER" in state or "WIN" in state:
            print(f"  {state} at {acted}")
            break
    print(f"{title} spill: {done} levels in {acted} actions")


if __name__ == "__main__":
    main()
