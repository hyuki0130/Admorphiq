"""Run the tether tool alone on one sample game and report what each level cost.

Reports, per level, the actions the tool spent against the game's own human baseline, plus
the tool's bid on this board and the highest bid it makes on any OTHER sample game — the two
numbers that decide whether registering it is a gain or a theft of another game's turn.

    uv run python scripts/tether_probe.py                # play, then sweep the other games
    uv run python scripts/tether_probe.py --game r11l    # a different board
    uv run python scripts/tether_probe.py --no-sweep
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

from admorphiq.tools.base import frame_2d, levels_completed, state_name  # noqa: E402
from admorphiq.tools.tether import TetherCentroidTool  # noqa: E402


def _act(env, step):
    aid, xy = step
    if xy is None:
        return env.step(GameAction.from_id(aid))
    return env.step(GameAction.ACTION6, data={"x": int(xy[0]), "y": int(xy[1])})


def play(arcade, game_id: str, baseline: list[int] | None, budget: int, verbose: bool) -> None:
    tool = TetherCentroidTool()
    env = arcade.make(game_id)
    obs = env.observation_space
    print(f"bid on first frame: {tool.detect([], obs):.2f}")

    used = 0
    per_level: list[int] = []
    since = 0
    level = levels_completed(obs)
    queue: list[tuple[int, tuple[int, int] | None]] = []
    stalls = 0
    while used < budget:
        if not queue:
            queue = list(tool.propose([], obs))
            if verbose:
                print(f"  [plan @level {levels_completed(obs)}] {queue}")
            if not queue:
                if verbose:
                    grid = np.array(frame_2d(obs))
                    print(f"  no plan at level {levels_completed(obs)}:")
                    for row in grid:
                        print("   " + "".join("0123456789abcdef"[int(v)] for v in row))
                stalls += 1
                if stalls > 3:
                    print("no plan; stopping")
                    break
                obs = env.step(GameAction.RESET)
                tool.reset()
                continue
            stalls = 0
        step = queue.pop(0)
        before = np.array(frame_2d(obs))
        obs = _act(env, step)
        used += 1
        since += 1
        if verbose:
            same = np.array_equal(before, np.array(frame_2d(obs)))
            print(f"  {used:3d} click {step[1]}  changed={not same}  "
                  f"level={levels_completed(obs)}  state={state_name(obs)}")
        now = levels_completed(obs)
        if now > level:
            for _ in range(now - level):
                per_level.append(since)
                since = 0
            level = now
            queue.clear()
            tool.reset()
        if state_name(obs) == "WIN":
            break
        if state_name(obs) == "GAME_OVER":
            print(f"  GAME_OVER after {used} actions (level {level})")
            obs = env.step(GameAction.RESET)
            used += 1
            since += 1
            queue.clear()
            tool.reset()

    print(f"\nlevels cleared: {level}   actions total: {used}")
    for i, n in enumerate(per_level):
        human = baseline[i] if baseline and i < len(baseline) else None
        ratio = f"  human={human}  ratio={n / human:.2f}x" if human else ""
        print(f"  level {i + 1}: {n} actions{ratio}")


def sweep(arcade, skip: str) -> None:
    """The bid this tool makes on every OTHER sample game — it must be 0.00 everywhere."""
    tool = TetherCentroidTool()
    worst = 0.0
    for info in arcade.get_environments():
        if info.game_id == skip:
            continue
        env = arcade.make(info.game_id)
        obs = env.observation_space
        if obs is None:
            continue
        conf = tool.detect([], obs)
        tool.reset()
        if conf > 0:
            print(f"  {info.game_id}: {conf:.2f}")
        worst = max(worst, conf)
    print(f"max bid elsewhere: {worst:.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="r11l")
    ap.add_argument("--budget", type=int, default=400)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-sweep", action="store_true")
    args = ap.parse_args()

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    infos = [e for e in arcade.get_environments() if args.game in e.game_id]
    if not infos:
        raise SystemExit(f"no sample game matching {args.game!r}")
    info = infos[0]
    print(f"{info.game_id}  baseline={info.baseline_actions}")
    start = time.time()
    play(arcade, info.game_id, info.baseline_actions, args.budget, args.verbose)
    print(f"({time.time() - start:.1f}s)")
    if not args.no_sweep:
        print("\n-- bid on the other sample games --")
        sweep(arcade, info.game_id)


if __name__ == "__main__":
    main()
