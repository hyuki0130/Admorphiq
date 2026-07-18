"""re86 L8 TRUE changer-station model (dev-time): dump each tag-0007 station
sprite's recolour colour (source uses pixels[1,1]) + bbox (x,y,w,h), and inspect
Sprite.collides_with, to resolve the unexplained ->14 recolour and get the exact
recolour trigger boxes for the reorder build.
"""
from __future__ import annotations
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction, Sprite
from admorphiq.adapters25.re86 import Adapter, _station_boxes
from admorphiq.adapters25.base import canonical_layer

A = {i: getattr(GameAction, f"ACTION{i}") for i in range(1, 6)}
STATION = "0007dtbisvazhv"


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def main():
    print("=== Sprite.collides_with source ===")
    try:
        print(inspect.getsource(Sprite.collides_with))
    except Exception as e:  # noqa: BLE001
        print("(unavailable)", e)

    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    s = 0
    while s < 6000 and int(getattr(obs, "levels_completed", 0) or 0) < 7 and not ad.is_done([], obs):
        obs = step(env, ad.choose_action([], obs)); s += 1
    for _ in range(3):
        obs = step(env, A[5])
    g = canonical_layer(obs)
    fr_stations, fr_boxes = _station_boxes(g)
    print(f"\n_station_boxes (frame parse): {fr_stations}")

    print("\n=== tag-0007 station sprites (TRUE) ===")
    for sp in env._game.current_level.get_sprites_by_tag(STATION):
        px = sp.pixels
        c11 = int(px[1, 1])
        print(f"  station recolour_colour(px[1,1])={c11} bbox x={sp.x} y={sp.y} w={sp.width} h={sp.height} "
              f"(rows {sp.y}-{sp.y + sp.height - 1} cols {sp.x}-{sp.x + sp.width - 1})")


if __name__ == "__main__":
    main()
