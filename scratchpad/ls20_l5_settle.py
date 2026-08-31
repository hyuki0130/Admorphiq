from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter, _find_avatar
from admorphiq.adapters25.base import canonical_layer


def nlayers(obs):
    fr = getattr(obs, "frame", None)
    if fr is None:
        return None
    try:
        return len(fr)
    except Exception:
        return "?"


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
    print("reached L5 @", steps, "levels", obs.levels_completed)
    for i in range(6):
        grid = canonical_layer(obs)
        av = _find_avatar(grid)
        print(f"step {i}: nlayers={nlayers(obs)} frame_av={av} gt_av=({g.gudziatsk.x},{g.gudziatsk.y}) mover=({g.wsoslqeku[0]._sprite.x},{g.wsoslqeku[0]._sprite.y})")
        obs = env.step(GameAction.ACTION1)
        steps += 1
    # Now dump the settled single-layer grid + GT
    grid = canonical_layer(obs)
    gt = [{"name": w.sprite.name, "x": w.sprite.x, "y": w.sprite.y, "dx": w.dx, "dy": w.dy} for w in g.hasivfwip]
    Path("scratchpad/ls20_l5_grid.json").write_text(json.dumps({
        "grid": [list(r) for r in grid], "gt_walls": gt,
        "avatar": (g.gudziatsk.x, g.gudziatsk.y),
        "mover": (g.wsoslqeku[0]._sprite.x, g.wsoslqeku[0]._sprite.y),
        "goal": [(gg.x, gg.y) for gg in g.plrpelhym],
    }))
    print("saved settled grid; gt_av=", (g.gudziatsk.x, g.gudziatsk.y))


if __name__ == "__main__":
    main()
