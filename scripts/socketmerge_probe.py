"""Drive the socket-merge tool against a live game and report how deep it gets."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.socketmerge import SocketMergeTool  # noqa: E402


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "su15"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    verbose = "-v" in sys.argv
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = SocketMergeTool()
    print(f"  detect={tool.detect([], obs):.2f}  baseline={info.baseline_actions}")
    done = 0
    acted = 0
    idle = 0
    marks: list[tuple[int, int]] = []
    while acted < cap and idle < 6:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            continue
        idle = 0
        for _, xy in steps:
            x, y = xy if xy else (0, 0)
            obs = env.step(GameAction.ACTION6, data={"x": x, "y": y})
            acted += 1
            if verbose:
                print(f"    a{acted} click({x},{y}) reach={tool._reach}")
            new = int(getattr(obs, "levels_completed", done) or 0)
            if new != done:
                marks.append((new, acted))
                print(f"  level {new}: cleared at {acted} actions (reach={tool._reach})")
                done = new
                tool.reset()
            if "GAME_OVER" in str(getattr(obs, "state", "")) or "WIN" in str(getattr(obs, "state", "")):
                print(f"     {obs.state} at {acted}")
                acted = cap
                break
    print(f"{title} socketmerge: {done} levels in {acted} actions; marks={marks}")


if __name__ == "__main__":
    main()
