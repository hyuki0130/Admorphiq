"""Drive the phase tool against a live game and report how deep it gets.

Usage: uv run python scripts/phase_probe.py <title> [action cap]
Prints each level's clear point so the run can be read against the human baseline and the
per-level budget the game itself declares.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.phase import PhaseGridTool  # noqa: E402


def scan() -> None:
    """Report the tool's first-frame bid on every sample game — the false-positive gate."""
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    seen: set[str] = set()
    for info in arcade.get_environments():
        key = (info.title or info.game_id).lower().split("-")[0][:4]
        if key in seen:
            continue
        seen.add(key)
        env = arcade.make(info.game_id)
        obs = env.reset()
        bid = PhaseGridTool().detect([], obs)
        print(f"  {key}: detect={bid:.2f}")


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    if "--scan" in sys.argv:
        scan()
        return

    title = sys.argv[1] if len(sys.argv) > 1 else "dc22"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = PhaseGridTool()
    simple = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
              4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    verbose = "-v" in sys.argv
    done = 0
    acted = 0
    idle = 0
    marks: list[tuple[int, int]] = []
    print(f"  baselines={getattr(info, 'baseline_actions', None)}")
    print(f"  detect={tool.detect([], obs):.2f}")
    while acted < cap:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            print(f"  no proposal at {acted} actions (level {done})")
            if verbose:
                geom = tool._read(__import__("admorphiq.tools.base", fromlist=["x"]).frame_2d(obs))
                if geom is not None:
                    here = tool._at(geom["board"], tool._avatar)
                    goal = tool._at(geom["board"], tool._marker)
                    items = tool._items(geom["board"], here, geom["bg"])
                    print(f"    here={here} goal={goal} items={sorted(items)} "
                          f"visited={sorted(tool._visited)}")
                    b = geom["board"]
                    for row in range(max(0, here[0] - 8), min(b.shape[0], here[0] + 10)):
                        print("    %2d %s" % (row, "".join(
                            "." if v == 0 else format(int(v), "x") for v in b[row])))
                    for it in sorted(items):
                        got = tool._route(geom["board"], here, {it}, geom["bg"])
                        print(f"    -> {it}: {len(got) if got else 'unreachable'}")
            if idle > 2:
                break
            continue
        idle = 0
        if verbose:
            print(f"  [{acted:3d}] steps={steps} deltas={tool._deltas} "
                  f"avatar={tool._avatar} marker={tool._marker} "
                  f"groups={[(gr['click'], len(gr['images']), gr['phase']) for gr in tool._groups]} "
                  f"clicks={len(tool._settled_clicks)} plan={len(tool._plan)} "
                  f"expect={tool._expect}")
        for action, xy in steps:
            if action == 6:
                obs = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
            else:
                obs = env.step(simple[action])
            acted += 1
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new != done:
            marks.append((new, acted))
            print(f"  level {new}: cleared at {acted} actions")
            done = new
        state = str(getattr(obs, "state", ""))
        if "GAME_OVER" in state or "WIN" in state:
            print(f"  {state} at {acted}")
            break
    print(f"{title} phase: {done} levels in {acted} actions  marks={marks}")


if __name__ == "__main__":
    main()
