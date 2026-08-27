"""Drive the mirror tool against a live game and report how deep it gets.

``--trace`` prints, per action, what the tool believes: where it thinks the actors are, what it
has decided each colour DOES, and how long the plan it is following is. That is the diagnosis
this tool needs — a stall here is almost always a colour whose role was read wrong, and the
belief table names it directly.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.mirror import MirrorMergeTool  # noqa: E402


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    trace = "--trace" in sys.argv
    title = args[0] if args else "m0r0"
    cap = int(args[1]) if len(args) > 1 else 900
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = MirrorMergeTool()
    done = 0
    acted = 0
    since = 0
    idle = 0
    acts = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
            4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    print(f"  detect={tool.detect([], obs):.2f}")
    while acted < cap and idle < 3:
        steps = tool.propose([], obs)
        if trace:
            print(f"  a={acted:3d} lvl={done} at={tool.beliefs()} -> {steps}")
        if not steps:
            idle += 1
            obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})
            acted += 1
            since += 1
            continue
        idle = 0
        for aid, xy in steps:
            obs = env.step(acts[aid]) if xy is None else env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
            acted += 1
            since += 1
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new != done:
            print(f"  level {new}: cleared in {since} actions ({acted} total)")
            done = new
            since = 0
        if "GAME_OVER" in str(getattr(obs, "state", "")):
            print(f"     GAME_OVER at {acted} ({since} into level {done + 1})")
            break
    print(f"{title} mirror: {done} levels in {acted} actions")


if __name__ == "__main__":
    main()
