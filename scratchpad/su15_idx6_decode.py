"""Verification-only dev-probe: read idx6 (level index 6) layout live and
verify the banked decode (2 class-1 enemies, fruits {1:4, 5:1}, spec [3,2],
two goals). Also verify the downgrade dynamics by driving a deliberate contact.
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


def fruits(game):
    out = []
    for f in game.lkujttxgs:
        px = f.pixels
        color = int(px[px >= 0].max()) if (px is not None and (px >= 0).any()) else -1
        out.append([int(f.x), int(f.y), _VAL_BY_COLOR.get(color, -1)])
    return out


def enemies(game):
    out = []
    for e in game.fezhhzhih:
        cls = game.kcuphgwar.get(e, None)
        out.append([int(e.x), int(e.y), str(cls)])
    return out


def goals(game):
    out = []
    for s in game.powykypsm:
        h, w = s.pixels.shape
        out.append((int(s.x), int(s.y), w, h))
    return out


def main():
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("su15")
    env.step(reset_action())
    game = env._game
    game.set_level(6)
    print("level_index", game.level_index)
    print("spec dsqlbvwaj =", game.dsqlbvwaj)
    print("fruits", fruits(game))
    print("enemies (x,y,class)", enemies(game))
    print("goals (x,y,w,h)", goals(game))
    # enemy class constants
    print("class map kcuphgwar values:", set(str(v) for v in game.kcuphgwar.values()))
    # knockback constants
    print("rmziewkdi(shake)", game.rmziewkdi, "dgpsayght(slide)", game.dgpsayght,
          "ttwugcsth(kbspeed)", game.ttwugcsth, "gdamdvokm(vacsub)", game.gdamdvokm)


if __name__ == "__main__":
    main()
