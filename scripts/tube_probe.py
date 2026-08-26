"""Drive the tube tool against a live game and report how deep it gets.

Reports levels cleared, actions spent, and the per-level human baseline the score is
measured against, so a run is comparable to the metric without a second tool.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.tube import TubeOrderTool  # noqa: E402


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "sk48"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(
        i for i in arcade.get_environments()
        if (i.title or i.game_id).lower().startswith(title)
    )
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = TubeOrderTool()
    acts = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
            4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    base = list(info.baseline_actions or [])
    print(f"{title}: baselines {base}")
    done = 0
    acted = 0
    mark = 0
    print(f"  detect={tool.detect([], obs):.2f}")
    while acted < cap:
        steps = tool.propose([], obs)
        if not steps:
            print(f"  no plan at level {done} after {acted} actions")
            break
        for aid, _ in steps:
            prev = obs
            obs = env.step(acts[aid])
            acted += 1
            tool.observe(getattr(prev, "frame", [None])[-1], (aid, None), True)
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new != done:
            human = base[done] if done < len(base) else None
            print(f"  level {done} cleared in {acted - mark} actions (human {human})")
            mark, done = acted, new
            tool.reset()
        if "GAME_OVER" in str(getattr(obs, "state", "")):
            print(f"  GAME_OVER at {acted}")
            break
    print(f"{title} tube: {done} levels in {acted} actions")


if __name__ == "__main__":
    main()
