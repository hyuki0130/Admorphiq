"""DISPOSABLE: resolve the r11l L5 grid->frame map and label each game element's
frame footprint, so the frame-only detector can be designed. Uses the engine's
own camera transform (the interface render formula) for labelling only."""
from __future__ import annotations

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.adapters25.r11l import Adapter


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("r11l")
    obs = env.step(GameAction.RESET)
    game = env._game  # noqa: SLF001
    adapter = Adapter()
    steps = 0
    while steps < 6000:
        if adapter.is_done([], obs):
            break
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        if obs is None:
            break
        steps += 1
        if obs.state.name == "GAME_OVER":
            obs = env.step(GameAction.RESET); steps += 1; continue
        if int(getattr(obs, "levels_completed", 0) or 0) >= 4:
            break

    grid = np.array(canonical_layer(obs))
    bg = most_common_color(grid.tolist())
    cam = game.camera
    scale, x_off, y_off = cam._calculate_scale_and_offset()
    print(f"L5 in {steps} steps; scale={scale} x_off={x_off} y_off={y_off} cam=({cam.x},{cam.y}) bg={bg}")

    def to_frame(sx, sy, w, h):
        fx = int((sx + w // 2 - cam.x) * scale + x_off)  # column
        fy = int((sy + h // 2 - cam.y) * scale + y_off)  # row
        return fy, fx  # (row, col)

    def patch(fr, fc, rad=3):
        vals = {}
        for r in range(fr - rad, fr + rad + 1):
            for c in range(fc - rad, fc + rad + 1):
                if 0 <= r < grid.shape[0] and 0 <= c < grid.shape[1]:
                    v = int(grid[r, c])
                    if v != bg:
                        vals[v] = vals.get(v, 0) + 1
        return vals

    print("\n=== elements -> frame(row,col) + non-bg colour histogram in a 7x7 patch ===")
    for name, d in game.kacotwgjcyq.items():
        for role in ("roduyfsmiznvg", "gosubdcyegamj"):
            s = d[role]
            if s:
                fr, fc = to_frame(s.x, s.y, s.width, s.height)
                print(f"  {role:14s} {name:14s} grid({s.x},{s.y}) {s.width}x{s.height} "
                      f"-> frame({fr},{fc}) patch={patch(fr, fc)}")
        for lg in d["lecfirgqbwunn"]:
            fr, fc = to_frame(lg.x, lg.y, lg.width, lg.height)
            print(f"  {'leg':14s} {name:14s} grid({lg.x},{lg.y}) -> frame({fr},{fc}) patch={patch(fr, fc, 2)}")
    for c in game.owuypsqbino:
        col = {int(x) for x in np.unique(c.pixels) if x > 0}
        fr, fc = to_frame(c.x, c.y, c.width, c.height)
        print(f"  {'collectible':14s} {c.name:22s} col={col} grid({c.x},{c.y}) "
              f"-> frame({fr},{fc}) patch={patch(fr, fc)}")


if __name__ == "__main__":
    main()
