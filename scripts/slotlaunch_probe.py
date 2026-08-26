"""Drive the slot-launch tool against a live game and report how deep it gets."""

from __future__ import annotations

import sys
import time

sys.path.insert(0, "src")

from admorphiq.tools.slotlaunch import SlotLaunchTool  # noqa: E402


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "ka59"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = SlotLaunchTool()
    done = 0
    acted = 0
    idle = 0
    marks: list[tuple[int, int]] = []
    acts = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
            4: GameAction.ACTION4, 5: GameAction.ACTION5}
    print(f"  detect={tool.detect([], obs):.2f}")
    while acted < cap and idle < 3:
        t0 = time.time()
        steps = tool.propose([], obs)
        plan_ms = (time.time() - t0) * 1000
        if not steps:
            idle += 1
            obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})
            acted += 1
            continue
        idle = 0
        print(f"  level {done}: plan {len(steps)} steps in {plan_ms:.0f} ms")
        for aid, xy in steps:
            obs = env.step(acts[aid]) if xy is None else env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
            acted += 1
            new = int(getattr(obs, "levels_completed", done) or 0)
            if new != done:
                marks.append((new, acted))
                print(f"  level {new}: cleared at {acted} actions")
                done = new
                break
            if "GAME_OVER" in str(getattr(obs, "state", "")):
                print(f"     GAME_OVER at {acted}")
                break
        if "GAME_OVER" in str(getattr(obs, "state", "")):
            break
    print(f"{title} slotlaunch: {done} levels in {acted} actions  marks={marks}")


if __name__ == "__main__":
    main()
