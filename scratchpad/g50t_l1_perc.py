"""g50t L1 perception probe: dump all colour-9 regions across several settled
probe moves so we can pick the STATIC one (goal) robustly, offset-agnostic."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer
from admorphiq.kernels import find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
MOVER = 9


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def nines(grid):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] == MOVER:
            cy, cx = reg["centroid"]
            out.append((round(cy, 1), round(cx, 1), reg["size"], reg["bbox"]))
    return out


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    for i, a in enumerate([0, 2, 4, 2, 4, 1, 3]):
        if a:
            obs = env.step(A[a])
        print(f"probe {i} (issued {a}):")
        for reg in nines(canonical_layer(obs)):
            print(f"    centroid=({reg[0]},{reg[1]}) size={reg[2]} bbox={reg[3]}")


if __name__ == "__main__":
    main()
