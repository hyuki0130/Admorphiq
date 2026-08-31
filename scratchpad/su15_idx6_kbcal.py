"""Clean knockback calibration: track the value>=2 fruit (the value-5) and its
nearest enemy precisely across a controlled downgrade choreography. Logs the
fruit's (x,y,value) and enemy (x,y,cooldown) each click so the sim's knockback
direction/distance + cooldown accounting can be matched.

Choreography: click on the value-5's own center each step. This vacuums the
value-5 to the click (no move, it's centered) and pulls any nearby enemy toward
it, forcing contact — a clean isolated downgrade sequence.
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
        fr.append([int(f.x), int(f.y), _VAL_BY_COLOR.get(c, -1)])
    en = [[int(e.x), int(e.y), game.yghzqxumz.get(e, 0)] for e in game.fezhhzhih]
    return fr, en


def step(env, cx, cy):
    a = click_action(x=cx, y=cy)
    env.step(a, data=a.action_data.model_dump())


def main():
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("su15")
    env.step(reset_action())
    game = env._game
    game.set_level(6)
    fr, en = snap(game)
    hi = max(fr, key=lambda f: f[2])
    print(f"seed value-5={hi} enemies={en}")
    for k in range(16):
        fr, en = snap(game)
        hi = max(fr, key=lambda f: f[2])
        sz = su15._SIZE[hi[2]]
        # click on the value-5's CENTER — vacuums it in place, pulls nearest enemy in
        cx = hi[0] + sz // 2
        cy = hi[1] + sz // 2
        cx = max(0, min(63, cx)); cy = max(10, min(62, cy))
        # nearest enemy to the value-5 (the one that will contact)
        ne = min(en, key=lambda e: (e[0]+2-cx)**2 + (e[1]+2-cy)**2)
        step(env, cx, cy)
        fr2, en2 = snap(game)
        hi2 = max(fr2, key=lambda f: f[2])
        ne2 = min(en2, key=lambda e: (e[0]+2-hi2[0])**2 + (e[1]+2-hi2[1])**2)
        print(f"[{k:02d}] click({cx},{cy}) v5 {hi}->{hi2}  nearEnemy {ne}->{ne2}  "
              f"nfruit={len(fr2)}")
        if game.level_index != 6:
            break


if __name__ == "__main__":
    main()
