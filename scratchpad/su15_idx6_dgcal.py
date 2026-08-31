"""Empirically calibrate the downgrade dynamics at agent-click granularity.

Drives idx6 on the LIVE engine with a scripted choreography that forces
enemy2 to contact the value-5, logging per click: fruit values+positions,
enemy positions, enemy cooldowns (yghzqxumz), knockback set (ksuxajatq).
Goal: learn how a contact manifests per click (value drop, knockback px,
cooldown in clicks) so the sim can lockstep.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from admorphiq.adapters25 import su15  # noqa: E402
from admorphiq.adapters25.base import reset_action, click_action  # noqa: E402

_VAL_BY_COLOR = {c: v for v, c in enumerate(su15._VAL_COLORS)}


def snap(game):
    fr = []
    for f in game.lkujttxgs:
        px = f.pixels
        c = int(px[px >= 0].max()) if (px is not None and (px >= 0).any()) else -1
        fr.append((int(f.x), int(f.y), _VAL_BY_COLOR.get(c, -1)))
    en = [(int(e.x), int(e.y)) for e in game.fezhhzhih]
    cd = {i: game.yghzqxumz.get(e, 0) for i, e in enumerate(game.fezhhzhih)}
    return fr, en, cd


def step(env, cx, cy):
    a = click_action(x=cx, y=cy)
    env.step(a, data=a.action_data.model_dump())


def main():
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("su15")
    env.step(reset_action())
    game = env._game
    game.set_level(6)
    print("=== idx6 downgrade calibration ===")
    fr, en, cd = snap(game)
    print(f"seed fruits={fr}")
    print(f"seed enemies={en} cd={cd}")
    # Strategy: repeatedly vacuum enemy2 (near value-5) TOWARD the value-5 to force
    # contact. value-5 top-left (51,46), enemy2 (52,56). Click just above value-5.
    for k in range(20):
        fr, en, cd = snap(game)
        v5 = [f for f in fr if f[2] >= 2]
        target = v5[0] if v5 else fr[0]
        # click a couple px above the value-5 center to pull enemy2 up into it
        cx = target[0] + 1
        cy = target[1] - 2
        cx = max(0, min(63, cx)); cy = max(10, min(62, cy))
        step(env, cx, cy)
        fr2, en2, cd2 = snap(game)
        vals = sorted(f[2] for f in fr2)
        print(f"[{k:02d}] click({cx},{cy}) vals={vals} enemies={en2} cd={cd2} "
              f"state={game._state.name if hasattr(game._state,'name') else game._state} lvl={game.level_index}")
        if game.level_index != 6:
            print("  level changed"); break


if __name__ == "__main__":
    main()
