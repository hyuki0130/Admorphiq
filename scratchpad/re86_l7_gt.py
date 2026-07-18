"""re86 L7 ground-truth: read the target sprites (tag 0054) + movable sprites
(tag 0031) + changer stations (tag 0007) + obstacle (0003) directly from the
game to settle target geometry and per-piece reshape tags."""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
TARGET_TAG = "0054xnsuqceejm"
MOV_TAG = "0031cppcuvqlbi"
STATION_TAG = "0007dtbisvazhv"
OBST_TAG = "0003dlchiwseii"


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def sprite_cells(s):
    """non-(-1) cells of a sprite in ABS coords with colour."""
    out = []
    for i in range(s.height):
        for j in range(s.width):
            v = int(s.pixels[i, j])
            if v != -1:
                out.append((s.y + i, s.x + j, v))
    return out


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    from admorphiq.adapters25.re86 import Adapter
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    steps = 0
    while steps < 4000 and int(getattr(obs, "levels_completed", 0) or 0) < 6 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = step(env, a)
        steps += 1
    print(f"L7 at {steps}")
    g = env._game
    lvl = g.current_level

    print("=== TARGET sprites (0054) ===")
    for s in lvl.get_sprites_by_tag(TARGET_TAG):
        cells = sprite_cells(s)
        cols = Counter(v for _r, _c, v in cells if v != 4)
        # cells that are not border (4)
        core = [(r, c, v) for r, c, v in cells if v != 4]
        print(f"  sprite @({s.y},{s.x}) {s.width}x{s.height} colours(non-4)={dict(cols)} tags={s.tags}")
        for r, c, v in sorted(core):
            print(f"       ({r},{c})={v}")

    print("=== MOVABLE sprites (0031) ===")
    for s in lvl.get_sprites_by_tag(MOV_TAG):
        cols = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
        col = cols.most_common(1)[0][0] if cols else -1
        print(f"  colour={col} @({s.y},{s.x}) {s.width}x{s.height} tags={s.tags}")
        # print the pixel grid compactly
        for i in range(s.height):
            row = "".join(("." if int(s.pixels[i, j]) == -1 else ("O" if int(s.pixels[i, j]) == 0 else str(int(s.pixels[i, j]) % 10))) for j in range(s.width))
            print(f"       {row}")

    print("=== STATION sprites (0007) ===")
    for s in lvl.get_sprites_by_tag(STATION_TAG):
        print(f"  centre={int(s.pixels[1,1])} @({s.y},{s.x}) {s.width}x{s.height}")

    print("=== OBSTACLE (0003) ===")
    for s in lvl.get_sprites_by_tag(OBST_TAG):
        print(f"  @({s.y},{s.x}) {s.width}x{s.height}")


if __name__ == "__main__":
    main()
