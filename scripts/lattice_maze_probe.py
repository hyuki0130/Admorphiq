"""Drive the lattice-maze tool against a live game and report the walk, level by level.

Reports what the deliverable needs: levels cleared, the actions each level cost, and the bid the
tool makes on the first frame. Run with a title prefix; with ``--all`` it sweeps every sample game
and prints the bid, which is the false-positive check.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.lattice_maze import LatticeMazeTool  # noqa: E402


def _arcade():
    from arc_agi import Arcade, OperationMode
    return Arcade(operation_mode=OperationMode.OFFLINE)


def sweep() -> None:
    """Bid on the first frame of every sample game — anything but our own must be 0.00."""
    arcade = _arcade()
    rows = []
    for info in arcade.get_environments():
        title = (info.title or info.game_id)
        env = arcade.make(info.game_id)
        obs = env.reset()
        try:
            bid = LatticeMazeTool().detect([], obs)
        except Exception as exc:  # noqa: BLE001 - a parse failure is a 0 bid, not a crash
            print(f"  {title:24s} ERROR {exc}")
            bid = -1.0
        rows.append((bid, title))
    rows.sort(reverse=True)
    for bid, title in rows:
        print(f"  {title:24s} {bid:.2f}")


def play(title: str, cap: int) -> None:
    from arcengine import GameAction
    arcade = _arcade()
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = LatticeMazeTool()
    acts = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
            4: GameAction.ACTION4, 5: GameAction.ACTION5}
    print(f"  bid on the first frame: {tool.detect([], obs):.2f}")
    done, acted, idle, mark = 0, 0, 0, 0
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
        if new > done:
            print(f"  level {new}: cleared in {acted - mark} actions (total {acted})")
            done, mark = new, acted
            tool.reset()
        if "GAME_OVER" in str(getattr(obs, "state", "")):
            print(f"  GAME_OVER at {acted} actions — env reset")
            obs = env.reset()
            tool.reset()
            mark = acted
    print(f"{title}: {done} levels in {acted} actions")


def main() -> None:
    if "--all" in sys.argv:
        sweep()
        return
    title = sys.argv[1] if len(sys.argv) > 1 else "tu"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    play(title, cap)


if __name__ == "__main__":
    main()
