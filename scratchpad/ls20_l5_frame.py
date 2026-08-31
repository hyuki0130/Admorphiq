"""Dump the settled L5 frame + colour-1 pixel map around each GT push-wall,
so we can determine whether the sprite pixel position is frame-recoverable.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter, _find_avatar
from admorphiq.adapters25.base import canonical_layer


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=6000)
    steps = 0
    # drive to L5
    while steps < 6000 and obs.levels_completed < 4:
        if adapter.is_done([], obs):
            break
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    print("reached levels_completed", obs.levels_completed, "@ step", steps)
    # settle: issue one move (up=1) and read the settled 1-layer frame
    for probe in range(3):
        grid = canonical_layer(obs)
        av = _find_avatar(grid)
        print(f"probe {probe}: frame_avatar={av}, gt_avatar=({g.gudziatsk.x},{g.gudziatsk.y})")
        if av is not None:
            break
        obs = env.step(GameAction.ACTION1)
        steps += 1
    grid = canonical_layer(obs)
    H, W = len(grid), len(grid[0])
    # dump colour-1 pixel coordinates
    ones = [(x, y) for y in range(H) for x in range(W) if grid[y][x] == 1]
    print("colour-1 pixel count:", len(ones))
    # GT walls at this moment
    gt = [{"name": w.sprite.name, "x": w.sprite.x, "y": w.sprite.y, "dx": w.dx, "dy": w.dy} for w in g.hasivfwip]
    print("GT walls now:", json.dumps(gt))
    # For each GT wall, print the 5x5 frame block at its sprite pos
    for w in gt:
        wx, wy = w["x"], w["y"]
        block = []
        for r in range(5):
            row = []
            for c in range(5):
                yy, xx = wy + r, wx + c
                row.append(grid[yy][xx] if 0 <= yy < H and 0 <= xx < W else -9)
            block.append(row)
        print(f"wall {w['name']} @({wx},{wy}) dir=({w['dx']},{w['dy']}):")
        for row in block:
            print("   ", row)
    # save the full grid
    Path("scratchpad/ls20_l5_grid.json").write_text(json.dumps({"grid": [list(r) for r in grid], "gt_walls": gt, "avatar": (g.gudziatsk.x, g.gudziatsk.y)}))


if __name__ == "__main__":
    main()
