"""Drive the reflect_cover tool against a live game and report how deep it gets.

    uv run python scripts/reflect_cover_probe.py <title> [max_actions]
    uv run python scripts/reflect_cover_probe.py <title> [n] --strict   # under the runner's
                                                    # own action-legality filter
    uv run python scripts/reflect_cover_probe.py --sweep      # detect() over every sample game
"""

from __future__ import annotations

import sys
import time

sys.path.insert(0, "src")

from admorphiq.tools.base import availability  # noqa: E402
from admorphiq.tools.reflect_cover import ReflectCoverTool  # noqa: E402

_SIMPLE = (1, 2, 3, 4, 5, 7)


def _legal(step, simple_ids, action6):
    """The runner's own legality rule (harness/loop.py) — a step it rejects is DROPPED and
    the runner substitutes its own probe move instead."""
    aid, xy = step
    if xy is not None:
        return action6 and aid == 6
    return aid in simple_ids or (aid == 7 and not simple_ids)


def _play(arcade, info, cap: int, strict: bool = False) -> None:
    from arcengine import GameAction

    acts = {i: getattr(GameAction, f"ACTION{i}") for i in _SIMPLE}
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = ReflectCoverTool()
    t0 = time.time()
    base = list(getattr(info, "baseline_actions", None) or [])
    print(f"  detect={tool.detect([], obs):.2f}  human baseline={base}")
    done, acted, idle, marks, over, dropped = 0, 0, 0, [], "", 0
    while acted < cap and idle < 3 and not over:
        steps = tool.propose([], obs)
        if strict:
            simple, click = availability(obs)
            keep = [s for s in steps if _legal(s, simple, click)]
            if steps and not keep:
                dropped += 1
                keep = [(simple[0], None)] if simple else [(6, (32, 32))]
            steps = keep
        if not steps:
            idle += 1
            continue
        idle = 0
        for aid, xy in steps:
            prev = obs
            obs = (env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
                   if aid == 6 else env.step(acts[aid]))
            acted += 1
            tool.observe(prev, (aid, xy), True)
            new = int(getattr(obs, "levels_completed", done) or 0)
            if new != done:
                marks.append((new, acted))
                print(f"  level {new} cleared at {acted} actions ({time.time() - t0:.0f}s)")
                done = new
            state = str(getattr(obs, "state", ""))
            if "GAME_OVER" in state or "WIN" in state:
                over = state
                break
    per = ([marks[0][1]] + [b - a for (_, a), (_, b) in zip(marks, marks[1:])]) if marks else []
    score = [round(min(h / a, 1.0) ** 2, 3) for h, a in zip(base, per)]
    print(f"{info.title}: {done} levels in {acted} actions {over}"
          + (f"  [strict: {dropped} steps rejected by the runner]" if strict else ""))
    print(f"  per level {per} vs human {base[:len(per)]} -> {score}")


def main() -> None:
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    infos = list(arcade.get_environments())
    if sys.argv[1:2] == ["--sweep"]:
        fired = []
        for info in sorted(infos, key=lambda i: i.title or i.game_id):
            env = arcade.make(info.game_id)
            obs = env.reset()
            conf = ReflectCoverTool().detect([], obs)
            if conf > 0:
                fired.append(info.title)
            print(f"  {info.title:<8} detect={conf:.2f}")
        print(f"fires on {len(fired)}/{len(infos)}: {fired}")
        return
    args = [a for a in sys.argv[1:] if a != "--strict"]
    strict = "--strict" in sys.argv
    title = args[0] if args else "ar"
    cap = int(args[1]) if len(args) > 1 else 800
    info = next(i for i in infos if (i.title or i.game_id).lower().startswith(title))
    _play(arcade, info, cap, strict)


if __name__ == "__main__":
    main()
