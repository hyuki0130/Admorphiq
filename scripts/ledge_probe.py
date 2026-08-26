"""Drive the ledge tool against a live game and report how deep it gets."""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.ledge import LedgeTool  # noqa: E402


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "bp35"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    verbose = "-v" in sys.argv
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = LedgeTool()
    done = 0
    acted = 0
    idle = 0
    deaths = 0
    acts = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
            4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    print(f"  detect={tool.detect([], obs):.2f}  human={list(getattr(info, 'baseline_actions', None) or [])}")
    marks: list[int] = []
    while acted < cap and idle < 20:
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
            if verbose:
                print(f"   {acted:4d} act={aid} {xy or ''} lvl={obs.levels_completed} {obs.state}")
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new != done:
            marks.append(acted)
            print(f"  level {new}: cleared at {acted} actions")
            done = new
        if "GAME_OVER" in str(getattr(obs, "state", "")):
            deaths += 1
            print(f"     GAME_OVER at {acted} (death {deaths})")
            obs = env.step(GameAction.RESET)
            if deaths > 12:
                break
    base = list(getattr(info, "baseline_actions", None) or [])
    spent = [b - a for a, b in zip([0] + marks, marks)]
    scores = [min(base[i] / max(1, spent[i]), 1.0) ** 2 for i in range(len(spent)) if i < len(base)]
    weights = list(range(1, len(base) + 1))
    game = sum((i + 1) * s for i, s in enumerate(scores)) / sum(weights) if base else 0.0
    print(f"  per level: spent={spent} human={base[:len(spent)]} scores={[round(s, 3) for s in scores]}")
    print(f"{title} ledge: {done} levels in {acted} actions, {deaths} deaths, game_score={game:.4f}")


if __name__ == "__main__":
    main()
