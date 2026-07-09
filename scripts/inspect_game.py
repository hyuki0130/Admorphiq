"""Dump what actions actually DO in a game — reveal the mechanic from observation.

Before building a tool for a game class, you must know how the game responds.
This runs a systematic action sweep (each simple action, then a grid of clicks)
and prints, per action: changed-cell count, changed bounding box, the distinct
colours before/after, and whether levels_completed advanced. No solving, no
assumptions — just the observable transition, so the right tool can be designed.

Usage (on the VM): uv run python scripts/inspect_game.py --game ft09 --clicks 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import numpy as np  # noqa: E402

from admorphiq.tools.base import (  # noqa: E402
    availability,
    color_histogram,
    diff_bbox,
    diff_cells,
    frame_2d,
    has_frame,
    levels_completed,
    state_name,
)


def _colors(frame: np.ndarray) -> list[int]:
    h = color_histogram(frame)
    return [int(c) for c in range(len(h)) if h[c] > 0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--clicks", type=int, default=16)
    a = ap.parse_args()

    from arc_agi import Arcade, OperationMode

    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.types import ActionType, GameAction

    convert = AdmorphiqAdapter._convert_action
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    want = a.game.strip().lower()
    match = next((e for e in arcade.get_environments()
                  if want in f"{e.game_id} {e.title or ''}".lower()), None)
    if match is None:
        raise SystemExit(f"no game matching {a.game!r}")
    env = arcade.make(match.game_id)
    obs = env.observation_space

    simple_ids, action6 = availability(obs)
    print(f"game={a.game} state={state_name(obs)} simple_ids={simple_ids} "
          f"action6={action6} colors={_colors(frame_2d(obs))}", flush=True)

    def step(internal, label):
        nonlocal obs
        before = frame_2d(obs) if has_frame(obs) else None
        lv0 = levels_completed(obs)
        act = convert(internal)
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        if obs is None:
            print(f"{label}: env ended")
            return False
        after = frame_2d(obs) if has_frame(obs) else None
        if before is not None and after is not None and before.shape == after.shape:
            n = diff_cells(before, after)
            bb = diff_bbox(before, after)
            lv1 = levels_completed(obs)
            flag = " *LEVEL+*" if lv1 > lv0 else ""
            print(f"{label}: changed={n} bbox={bb} colors={_colors(after)} "
                  f"state={state_name(obs)}{flag}", flush=True)
        return True

    # sweep simple actions
    for aid in simple_ids:
        step(GameAction.simple(ActionType(aid)), f"ACTION{aid}")
    # sweep a grid of clicks
    if action6:
        f = frame_2d(obs)
        h, w = f.shape
        stp = max(1, min(h, w) // 4)
        i = 0
        for y in range(stp // 2, h, stp):
            for x in range(stp // 2, w, stp):
                if i >= a.clicks:
                    break
                step(GameAction.coordinate(x, y), f"CLICK({x},{y})")
                i += 1


if __name__ == "__main__":
    main()
