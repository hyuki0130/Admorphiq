"""Characterize L7 (Fog): confirm the proximity-fog mechanic, count fogged vs
visible frame, and dump GT structure (goals/movers/pushwalls) to decide whether
L7 is 'L6 mechanics + partial observability' (explore-then-plan) or new."""
from __future__ import annotations
import json, sys
from collections import Counter
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
    adapter = Adapter(giveup=9000)
    steps = 0
    while steps < 9000 and obs.levels_completed < 6:
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
        if obs is None:
            print("obs None @", steps); return
    print("reached levels_completed", obs.levels_completed, "@", steps)
    # settle a couple frames
    for _ in range(2):
        obs = env.step(GameAction.ACTION1)
    print("Fog flag (GT oeuabekjf):", g.oeuabekjf)
    print("GT goals:", [((gg.x, gg.y), (g.ldxlnycps[i], g.yjdexjsoa[i], g.ehwheiwsk[i])) for i, gg in enumerate(g.plrpelhym)])
    print("GT n_movers:", len(g.wsoslqeku), "n_pushwalls:", len(g.hasivfwip))
    print("GT avatar:", (g.gudziatsk.x, g.gudziatsk.y), "token:", (g.fwckfzsyc, g.hiaauhahz, g.cklxociuu))
    print("GT life:", g._step_counter_ui.current_steps, g._step_counter_ui.osgviligwp, g._step_counter_ui.efipnixsvl)
    grid = canonical_layer(obs)
    H, W = len(grid), len(grid[0])
    hist = Counter(v for row in grid for v in row)
    print("frame colour histogram (top):", hist.most_common(6))
    av = _find_avatar(grid)
    print("frame avatar:", av)
    # the fog paints cells >20px from avatar center with a single colour: find it
    # by checking a far corner cell's colour
    import math
    if av:
        cx, cy = av[0] + 1.5, av[1] + 1.5
        far = [(x, y) for y in range(H) for x in range(W) if math.dist((y, x), (cy, cx)) > 20.0]
        near = [(x, y) for y in range(H) for x in range(W) if math.dist((y, x), (cy, cx)) <= 20.0]
        far_colors = Counter(grid[y][x] for x, y in far)
        print("FOG: far-from-avatar (>20px) colour histogram:", far_colors.most_common(4))
        print("near (<=20px) distinct colours:", len(set(grid[y][x] for x, y in near)),
              "far distinct colours:", len(set(grid[y][x] for x, y in far)))
    # can we parse the maze from a single fogged frame? count goal-border cells visible
    goal_cells_visible = sum(1 for y in range(0, H - 4, 5) for x in range(0, W - 4, 5)
                             if grid[y][x] == 5)
    print("colour-5 pixels visible in frame:", sum(1 for row in grid for v in row if v == 5))


if __name__ == "__main__":
    main()
