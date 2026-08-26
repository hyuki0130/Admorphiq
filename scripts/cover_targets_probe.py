"""Drive the cover-targets tool against a live game and report how deep it gets."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.cover_targets import CoverTargetsTool  # noqa: E402


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "re86"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = CoverTargetsTool()
    done = 0
    acted = 0
    idle = 0
    marks = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
             4: GameAction.ACTION4, 5: GameAction.ACTION5}
    print(f"  detect={tool.detect([], obs):.2f}")
    started = 0
    while acted < cap and idle < 4:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            obs = env.step(GameAction.ACTION5)
            acted += 1
            continue
        idle = 0
        for aid, _ in steps:
            obs = env.step(marks[aid])
            acted += 1
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new != done:
            print(f"  level {new}: cleared at {acted} actions (+{acted - started})")
            started = acted
            done = new
            tool.reset()
        if "GAME_OVER" in str(getattr(obs, "state", "")):
            print(f"     GAME_OVER at {acted}")
            break
    print(f"{title} cover_targets: {done} levels in {acted} actions")


if __name__ == "__main__":
    main()
