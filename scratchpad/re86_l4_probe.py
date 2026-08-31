"""Probe re86 L4: dump movables / gates / changer stations (frame + GT), confirm
the recolour mechanic + the reset-on-different-station behavior."""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter
from admorphiq.adapters25.base import canonical_layer


def dump_gt(g, tag):
    print(f"--- GT {tag} ---")
    lvl = g.current_level
    movs = lvl.get_sprites_by_tag("0031cppcuvqlbi")
    for m in movs:
        px = m.pixels
        cols = Counter(int(v) for row in px for v in row if v != -1)
        print(f"  movable pos=({m.x},{m.y}) size=({m.width}x{m.height}) colors={dict(cols)}")
    chs = lvl.get_sprites_by_tag("0007dtbisvazhv")
    print(f"  changer stations ({len(chs)}):")
    for c in chs:
        print(f"    station pos=({c.x},{c.y}) size=({c.width}x{c.height}) center_color={int(c.pixels[1,1])}")
    gates = lvl.get_sprites_by_tag("vzuwsebntu") or lvl.get_sprites_by_tag("0004vzuwsebntu")
    # try any gate-ish tag
    for t in ["vzuwsebntu"]:
        gg = lvl.get_sprites_by_tag(t)
        if gg:
            print(f"  gates[{t}] ({len(gg)}):", [(s.x, s.y, int(s.pixels[s.height//2, s.width//2])) for s in gg][:12])


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=9000)
    steps = 0
    while steps < 9000 and obs.levels_completed < 3:
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    print("reached L4 @", steps, "levels", obs.levels_completed)
    # settle a couple frames
    for _ in range(2):
        obs = env.step(GameAction.ACTION5)
        steps += 1
    dump_gt(g, "L4 initial")
    grid = canonical_layer(obs)
    hist = Counter(v for row in grid for v in row)
    print("frame hist top:", hist.most_common(10))


if __name__ == "__main__":
    main()
