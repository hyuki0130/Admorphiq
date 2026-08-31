"""Dev-time L5 ground-truth dumper + L1-L4 floor confirmation.

Drives the CURRENT adapter through L1-L4 (confirming the 4/7 floor and
capturing each level's parsed pushwall dict as a regression fixture), then at
L5 entry settles and dumps the engine's ground-truth sprite positions
(avatar, push-walls with dir/width, mover track, changers, goal, blocking set)
so the pixel-faithful model can be built against known targets.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

from admorphiq.adapters25.ls20 import Adapter, _detect_pushwalls, _parse, _find_avatar  # noqa: E402
from admorphiq.adapters25.base import canonical_layer  # noqa: E402


def grid_of(obs):
    return canonical_layer(obs)


def dump_game_state(g, tag):
    out = {"tag": tag}
    av = g.gudziatsk
    out["avatar"] = {"x": av.x, "y": av.y, "w": av.width, "h": av.height}
    walls = []
    for w in g.hasivfwip:
        walls.append({
            "name": w.sprite.name,
            "x": w.sprite.x, "y": w.sprite.y,
            "w": w.width, "h": w.height,
            "dx": w.dx, "dy": w.dy,
            "start_x": w.start_x, "start_y": w.start_y,
        })
    out["pushwalls"] = walls
    movers = []
    for m in g.wsoslqeku:
        movers.append({"x": m._sprite.x, "y": m._sprite.y, "cell": m._cell,
                       "track_x": m.bfdcztirdu.x, "track_y": m.bfdcztirdu.y,
                       "track_w": m.bfdcztirdu.width, "track_h": m.bfdcztirdu.height})
    out["movers"] = movers
    goals = []
    for gg in g.plrpelhym:
        goals.append({"x": gg.x, "y": gg.y})
    out["goals"] = goals
    return out


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=6000)
    fixtures = {}
    prev_levels = obs.levels_completed
    l5_dumped = False
    steps = 0
    while steps < 6000:
        levels = obs.levels_completed
        if levels >= 4 and not l5_dumped:
            # We just entered L5 (0-indexed levels_completed==4). Settle: the
            # entry frame is a stale 2-layer transition; issue a couple probes.
            gt = dump_game_state(g, f"L5_entry_levels={levels}")
            gt["frame_avatar"] = _find_avatar(grid_of(obs))
            Path("scratchpad/ls20_l5_gt.json").write_text(json.dumps(gt, indent=2))
            print("=== L5 GROUND TRUTH dumped ===")
            print(json.dumps(gt, indent=2))
            l5_dumped = True
            break
        # Record parsed pushwalls per level (fixture) when adapter first parses.
        grid = grid_of(obs)
        parsed = _parse(grid)
        if parsed is not None and levels not in fixtures:
            fixtures[levels] = {str(k): list(v) for k, v in parsed["pushwalls"].items()}
        if adapter.is_done([], obs):
            break
        action = adapter.choose_action([], obs)
        if not isinstance(action, GameAction):
            break
        if action.is_complex():
            obs = env.step(action, data=action.action_data.model_dump())
        else:
            obs = env.step(action)
        if obs is None:
            break
        steps += 1
        if obs.levels_completed > prev_levels:
            print(f"  cleared level -> levels_completed={obs.levels_completed} @ step {steps}")
            prev_levels = obs.levels_completed
    print("levels_completed:", obs.levels_completed if obs else "?")
    print("fixtures (parsed pushwalls per level index):")
    print(json.dumps(fixtures, indent=2))
    Path("scratchpad/ls20_l1l4_pushwall_fixtures.json").write_text(json.dumps(fixtures, indent=2))


if __name__ == "__main__":
    main()
