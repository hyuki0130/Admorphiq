"""Study push-wall rendering in the SETTLED L5 frame vs GT, to derive a
frame-only detector. Dumps colour-1 pixels and the 5x5 block at each GT wall.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter, _find_avatar
from admorphiq.adapters25.base import canonical_layer


def settle(env, obs, g):
    """Step until a single-layer frame whose _find_avatar matches GT."""
    for _ in range(8):
        grid = canonical_layer(obs)
        av = _find_avatar(grid)
        if av is not None and av == (g.gudziatsk.x, g.gudziatsk.y):
            return grid
        obs = env.step(GameAction.ACTION1)
    return canonical_layer(obs)


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=6000)
    steps = 0
    while steps < 6000 and obs.levels_completed < 4:
        if adapter.is_done([], obs):
            break
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    grid = settle(env, obs, g)
    av = _find_avatar(grid)
    print("settled avatar", av, "gt", (g.gudziatsk.x, g.gudziatsk.y))
    H, W = len(grid), len(grid[0])
    ones = [(x, y) for y in range(H) for x in range(W) if grid[y][x] == 1]
    print("colour-1 pixels:", len(ones), sorted(ones))
    gt = [{"name": w.sprite.name, "x": w.sprite.x, "y": w.sprite.y, "dx": w.dx, "dy": w.dy} for w in g.hasivfwip]
    for w in gt:
        wx, wy = w["x"], w["y"]
        print(f"\nwall {w['name']} @({wx},{wy}) dir=({w['dx']},{w['dy']}):")
        for r in range(-1, 6):
            row = []
            for c in range(-1, 6):
                yy, xx = wy + r, wx + c
                row.append(grid[yy][xx] if 0 <= yy < H and 0 <= xx < W else -9)
            print("   ", "r%+d" % r, row)
    Path("scratchpad/ls20_l5_settled.json").write_text(json.dumps({
        "grid": [list(r) for r in grid], "gt_walls": gt,
        "avatar": av, "ones": [list(o) for o in ones]}))


if __name__ == "__main__":
    main()
