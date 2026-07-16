"""g50t lag CALIBRATION: issue a KNOWN action sequence from a known L1 position
and log the observed player cell BEFORE each env.step. Pins the exact
observation-lag index so the observer attributes each move correctly.

If env.step(a) returns state-before-a, then obs read at call t reflects actions
through a_{t-2} (frame available when CHOOSING a_t reflects through a_{t-2}).
This prints, per call: the action about to be issued and the cell observed in the
frame that action will be chosen from — so O_t vs O_{t-1} reveals a_{t-2}'s effect.
"""
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
NAME = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT"}
CELL, MOVER = 6, 9


def derive_off(grid):
    for reg in find_regions(grid, background=None):
        if reg["color"] == MOVER and 8 <= reg["size"] <= 40 and 7 <= reg["bbox"][0] <= 58:
            cy, cx = reg["centroid"]
            return (int(round(cy)) % CELL, int(round(cx)) % CELL)
    return None


def movers(grid, off):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != MOVER or not (7 <= reg["bbox"][0] <= 58 and 8 <= reg["size"] <= 40):
            continue
        cy, cx = reg["centroid"]
        out.append((round((cy - off[0]) / CELL), round((cx - off[1]) / CELL)))
    return out


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = env.observation_space
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    grid = canonical_layer(obs)
    off = derive_off(grid)
    goal = (3, 4)
    seq = [1, 1, 1, 1, 1, 3, 3, 3, 2, 2, 2]  # UPx5 (to top), LEFTx3, DOWNx3
    print("off", off, "| seq:", [NAME[a] for a in seq])
    for i, a in enumerate(seq):
        grid = canonical_layer(obs)
        ms = [c for c in movers(grid, off) if c != goal]
        O = ms[0] if ms else None
        print(f"  call {i}: obs={O}  -> issue {NAME[a]}")
        obs = env.step(A[a])
    grid = canonical_layer(obs)
    ms = [c for c in movers(grid, off) if c != goal]
    print(f"  final obs={ms[0] if ms else None}")


if __name__ == "__main__":
    main()
