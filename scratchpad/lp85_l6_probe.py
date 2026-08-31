"""Drive the real lp85 adapter to L6 and inspect ground-truth vs adapter detection.

Run: uv run python scratchpad/lp85_l6_probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))

from arc_agi import Arcade, OperationMode  # noqa: E402
from admorphiq.adapters25.lp85 import (  # noqa: E402
    Adapter,
    _planner_background,
    _scale_unit,
    _detect_buttons,
    _detect_marker_colors,
    _detect_movers,
    _detect_dests,
    _cluster_frame_centres,
    _cint,
)
from admorphiq.adapters25.base import canonical_layer, most_common_color  # noqa: E402
from admorphiq.kernels import find_regions  # noqa: E402
from arcengine import GameAction  # noqa: E402

TARGET_LEVEL = 5  # 0-indexed L6


def raw_game(env):
    for attr in ("_game", "game", "_env", "env"):
        g = getattr(env, attr, None)
        if g is not None and hasattr(g, "current_level"):
            return g
    # deep search
    for name in dir(env):
        try:
            v = getattr(env, name)
        except Exception:
            continue
        if hasattr(v, "current_level"):
            return v
    return None


def dump_ground_truth(game):
    lvl = game.current_level
    print(f"  level_name={getattr(game, 'ucybisahh', '?')}  grid_size={lvl.grid_size}")
    for tag in ("bghvgbtwcb", "fdgmtkfrxl", "goal", "goal-o"):
        sprites = lvl.get_sprites_by_tag(tag)
        pts = [(s.x, s.y, s.width, s.height) for s in sprites]
        print(f"  tag {tag!r}: {len(sprites)} -> {pts}")
    # button sprites
    btns = [s for s in lvl._sprites if s.tags and "button" in s.tags[0]]
    ring_ids = {}
    for s in btns:
        parts = s.tags[0].split("_")
        if len(parts) == 3:
            ring_ids.setdefault(parts[1], []).append(parts[2])
    print(f"  button sprites: {len(btns)}  distinct ring ids: {sorted(ring_ids)}")


def dump_detection(grid):
    bg = _planner_background(grid)
    regions = find_regions(grid, background=bg)
    unit = _scale_unit(regions, bg)
    import math
    solid_min = max(3, unit // 2)
    span = max(6, 3 * math.isqrt(unit))
    print(f"  DETECT: bg={sorted(bg)}  unit={unit}  solid_min={solid_min}  span={span}")
    buttons = _detect_buttons(regions)
    marker = _detect_marker_colors(regions, solid_min, span)
    movers = _detect_movers(regions, marker, solid_min)
    dests = _detect_dests(regions, marker, solid_min, span)
    print(f"  buttons={len(buttons)}  marker_colors={sorted(marker)}")
    print(f"  movers({len(movers)})={movers}")
    print(f"  dests({len(dests)})={dests}")
    # Per-marker-colour breakdown: solids vs corner-dots, and clustering
    for c in sorted(marker | frozenset()):
        solids = [(_cint(r), r["size"]) for r in regions if int(r["color"]) == c and int(r["size"]) >= solid_min]
        dots = [(_cint(r), r["size"]) for r in regions if int(r["color"]) == c and int(r["size"]) < solid_min]
        print(f"    color {c}: solids={solids}")
        print(f"    color {c}: {len(dots)} sub-solid dots={[d[0] for d in dots]}")
        centres = _cluster_frame_centres([d[0] for d in dots], span)
        print(f"    color {c}: clustered frame centres (span={span}) = {centres}")
    # FULL dump of the real marker colour (11) and the HUD-suspect (5)
    for c in (11, 5):
        allr = sorted(
            ((int(r["size"]), _cint(r)) for r in regions if int(r["color"]) == c),
            reverse=True,
        )
        print(f"  >>> ALL color-{c} regions ({len(allr)}): {allr}")
    # Run the REAL adapter detect to see DETECT_OK + multipress flag
    from admorphiq.adapters25.lp85 import Adapter as _A
    a = _A()
    ok = a._detect(grid)
    print(f"  >>> REAL _detect() = {ok}   multipress={a._multipress}  "
          f"buttons={len(a._buttons)}  marker={sorted(a._marker_colors)}")
    print(f"  >>> _detect movers via mover_cells: {a._mover_cells(grid)}")
    print(f"  >>> _detect dests: {a._dests}")
    # Also: ALL marker-candidate colours (any colour appearing as a solid block)
    solid_colors = {}
    for r in regions:
        if int(r["color"]) not in (8, 14) and int(r["size"]) >= solid_min:
            solid_colors.setdefault(int(r["color"]), []).append((_cint(r), int(r["size"])))
    print(f"  ALL solid-block colours (potential markers): {sorted(solid_colors)}")
    for c, lst in sorted(solid_colors.items()):
        dots = [(_cint(r), r["size"]) for r in regions if int(r["color"]) == c and int(r["size"]) < solid_min]
        centres = _cluster_frame_centres([d[0] for d in dots], span)
        frame_ok = bool(centres)
        print(f"    solid color {c}: {len(lst)} solids, {len(dots)} dots -> {len(centres)} frames  is_marker={frame_ok}")


def main():
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("lp85")
    obs = env.observation_space
    game = raw_game(env)
    print(f"raw game found: {game is not None}  win_levels={obs.win_levels}")

    adapter = Adapter()
    steps = 0
    captured = False
    while steps < 6000:
        if obs.levels_completed >= TARGET_LEVEL:
            # settle one inert click then diagnose
            grid = canonical_layer(obs)
            print(f"\n=== REACHED L{obs.levels_completed+1} at step {steps} ===")
            if game is not None:
                dump_ground_truth(game)
            print(f"  grid dims: {len(grid)}x{len(grid[0])}  bg(most_common)={most_common_color(grid)}")
            dump_detection(grid)
            captured = True
            break
        if adapter.is_done([], obs):
            print(f"adapter is_done at step {steps}, levels={obs.levels_completed}")
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
    if not captured:
        print(f"did NOT reach L6; final levels={obs.levels_completed if obs else '?'} steps={steps}")


if __name__ == "__main__":
    main()
