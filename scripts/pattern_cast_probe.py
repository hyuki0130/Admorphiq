"""Drive the pattern-cast tool against a live game and report how deep it gets."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.pattern_cast import PatternCastTool  # noqa: E402


def sweep() -> None:
    """Report the tool's opening bid on every sample game — selectivity, measured.

    A tool that bids on a board it cannot solve takes the turn from the tool that can, so
    the number that matters here is the MAXIMUM off its own game, and it must be 0.00.
    """
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    tool = PatternCastTool()
    worst = 0.0
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        title = (info.title or info.game_id).split("-")[0]
        env = arcade.make(info.game_id)
        bid = tool.detect([], env.reset())
        tool.reset()
        if not title.lower().startswith("sc25"):
            worst = max(worst, bid)
        print(f"  {title:10s} detect={bid:.2f}")
    print(f"max bid away from sc25: {worst:.2f}")


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        sweep()
        return
    title = sys.argv[1] if len(sys.argv) > 1 else "sc25"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = PatternCastTool()
    done = 0
    acted = 0
    idle = 0
    acts = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
            4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    print(f"  baseline={info.baseline_actions} detect={tool.detect([], obs):.2f}")
    while acted < cap and idle < 4:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})
            acted += 1
            continue
        idle = 0
        for aid, xy in steps:
            obs = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]}) if aid == 6 \
                else env.step(acts[aid])
            acted += 1
            print(f"    {acted:4d} act={aid} {xy or ''} lvl={obs.levels_completed}")
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new != done:
            print(f"  level {new}: cleared at {acted} actions")
            done = new
        if "GAME_OVER" in str(getattr(obs, "state", "")):
            print(f"     GAME_OVER at {acted}")
            break
    print(f"{title} pattern_cast: {done} levels in {acted} actions")


if __name__ == "__main__":
    main()
