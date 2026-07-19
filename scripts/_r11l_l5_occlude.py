"""DISPOSABLE: is the L5 colour-8 (rengnt) collectible occlusion STATIC (fixed
arena) or does driving the active collector's legs reveal it? Gates the Pass-3
navigation design (one-shot plan vs closed-loop re-observe). Frame-only checks;
env._game read only to place clicks on the selected leg."""
from __future__ import annotations

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

from admorphiq.adapters25.base import canonical_layer
from admorphiq.adapters25.r11l import Adapter


def counts(obs):
    g = np.array(canonical_layer(obs))
    return {c: int((g == c).sum()) for c in (8, 9, 11, 14, 10)}


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("r11l")
    obs = env.step(GameAction.RESET)
    game = env._game  # noqa: SLF001
    ad = Adapter()
    steps = 0
    while steps < 6000:
        if ad.is_done([], obs):
            break
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        if obs is None:
            break
        steps += 1
        if obs.state.name == "GAME_OVER":
            obs = env.step(GameAction.RESET)
            steps += 1
            continue
        if int(getattr(obs, "levels_completed", 0) or 0) >= 4:
            break

    print(f"L5 entry colour counts: {counts(obs)}")
    sel = game.wiayqaumjug
    print(f"selected leg: {sel.name if sel else None} @({sel.x},{sel.y})" if sel else "no selection")

    # Drag the currently-selected leg to several open interior cells and re-scan.
    for (gx, gy) in [(20, 20), (45, 20), (20, 45), (45, 45), (30, 30)]:
        # click cell in FRAME coords = (x=col, y=row); engine maps display->grid.
        act = GameAction.ACTION6
        obs = env.step(act, data={"x": gx, "y": gy})
        # settle a couple frames
        for _ in range(2):
            if obs.state.name in ("WIN", "GAME_OVER"):
                break
            obs = env.step(GameAction.ACTION6, data={"x": gx, "y": gy})
        lv = int(getattr(obs, "levels_completed", 0) or 0)
        print(f"after drag->({gx},{gy}): state={obs.state.name} lv={lv} counts={counts(obs)}")
        if obs.state.name in ("WIN", "GAME_OVER"):
            print("  (terminal — stop)")
            break


if __name__ == "__main__":
    main()
