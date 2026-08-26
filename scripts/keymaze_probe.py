"""Drive the keyed-lock maze tool against a live game and report how deep it gets."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.keymaze import KeyMazeTool  # noqa: E402


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "ls"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = KeyMazeTool()
    acts = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
            4: GameAction.ACTION4, 5: GameAction.ACTION5}
    done, acted, idle = 0, 0, 0
    marks: list[str] = []
    print(f"  detect={tool.detect([], obs):.2f}")
    while acted < cap and idle < 3:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            continue
        idle = 0
        for aid, _ in steps:
            obs = env.step(acts[aid])
            acted += 1
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new != done:
            marks.append(f"L{new} @{acted}")
            print(f"  level {new}: cleared at {acted} actions")
            done = new
            tool.reset()
        if "GAME_OVER" in str(getattr(obs, "state", "")):
            print(f"     GAME_OVER at {acted} — resetting")
            obs = env.reset()
            tool.reset()
    print(f"{title} keymaze: {done} levels in {acted} actions  [{', '.join(marks)}]")


if __name__ == "__main__":
    main()
