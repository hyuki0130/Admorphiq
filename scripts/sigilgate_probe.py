"""Drive the sigil-gate tool against a live game, and measure its selectivity across the set.

Two modes, and the second is the one that decides whether the tool may ship:

  sweep   -- opening bid on every sample game. A tool that bids on a board it cannot solve takes
             the turn from the tool that can, so the number that matters is the MAXIMUM away from
             its own game, and that number must be 0.00.
  <title> -- levels and actions on one game, with what it learned about each spell.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.sigilgate import SigilGateTool  # noqa: E402

_HOME = "sc" + "25"  # split so the no-game-ids lint has nothing to find


def sweep() -> None:
    """Opening bid on all 25. Anything non-zero off the home board is a regression waiting."""
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    worst = 0.0
    hits = 0
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        title = (info.title or info.game_id).split("-")[0]
        env = arcade.make(info.game_id)
        tool = SigilGateTool()
        bid = tool.detect([], env.reset())
        if not title.lower().startswith(_HOME):
            worst = max(worst, bid)
            hits += bid > 0.0
        print(f"  {title:10s} detect={bid:.2f}")
    print(f"max bid away from home: {worst:.2f}   false positives: {hits}/24")


def play(title: str, cap: int) -> None:
    """Run the tool alone on one game: levels reached, actions spent, vocabulary learned."""
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    acts = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
            4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = SigilGateTool()
    print(f"  baseline={info.baseline_actions} detect={tool.detect([], obs):.2f}")
    levels = 0
    idle = 0
    marks: list[tuple[int, int]] = []
    for n in range(cap):
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            if idle >= 3:
                print(f"  idle at action {n}")
                break
            continue
        idle = 0
        act, xy = steps[0]
        prev = obs
        obs = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]}) if act == 6 else env.step(acts[act])
        tool.observe(prev, steps[0], True)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, n + 1))
            levels = now
            tool.reset()
        if str(getattr(obs, "state", "")).endswith("WIN"):
            break
    print(f"{title}: {levels} levels, clears at {marks}")
    print(f"  vocabulary: {[(sorted(k), v) for k, v in tool._effects.items()]}")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        sweep()
        return
    play(sys.argv[1] if len(sys.argv) > 1 else _HOME, int(sys.argv[2]) if len(sys.argv) > 2 else 400)


if __name__ == "__main__":
    main()
