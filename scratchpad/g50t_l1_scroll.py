"""g50t L1 scroll diagnostic (task #83): is the frame a SCROLLING camera?

Reach L1, then issue single moves (with lag flush via wall-nudge that does NOT
displace) and record: player cell + a floor-set fingerprint each step. If the
floor set shifts on every displacing move, the frame is a scrolling/re-centering
camera and absolute frame-cell parsing cannot yield stable world coords.

Clean method: after each REAL move, flush lag by re-reading LAG frames with NO
further action issued between reads is impossible (obs only updates on step), so
we issue a KNOWN wall move (into the top border) and detect displacement by
comparing player cell; we report raw sequence so scroll is visible directly.
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

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL, FLOOR, MOVER = 6, 5, 9
HUD_ROW = 9


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def player_cell(grid):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != MOVER or not (7 <= reg["bbox"][0] <= 58 and 8 <= reg["size"] <= 40):
            continue
        out.append((reg["bbox"][0] // CELL, reg["bbox"][1] // CELL))
    return min(out) if out else None


def floor_fp(grid):
    h, w = len(grid), len(grid[0])
    cells = set()
    i = 0
    while i * CELL + 3 < h and i < HUD_ROW:
        j = 0
        while j * CELL + 3 < w:
            if grid[i * CELL + 3][j * CELL + 3] == FLOOR:
                cells.add((i, j))
            j += 1
        i += 1
    return frozenset(cells)


def floor_bbox(grid):
    """Pixel bbox of the largest colour-5 region = the play-area floor sprite."""
    best = None
    for reg in find_regions(grid, background=None):
        if reg["color"] == FLOOR and (best is None or reg["size"] > best["size"]):
            best = reg
    return best["bbox"] if best else None


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    grid = canonical_layer(obs)
    print(f"L1 start: player={player_cell(grid)} floor_bbox={floor_bbox(grid)} floor_n={len(floor_fp(grid))}")
    # issue a sequence of single moves; report player + floor fingerprint delta each
    seq = [2, 2, 2, 4, 4, 4, 1, 1, 1, 3, 3, 3, 2, 4, 1, 3]  # long varied walk
    prev_fp = floor_fp(grid)
    prev_bbox = floor_bbox(grid)
    for k, a in enumerate(seq):
        obs = env.step(A[a])
        g = canonical_layer(obs)
        fp = floor_fp(g)
        bb = floor_bbox(g)
        changed = len(fp ^ prev_fp)
        bbox_shift = None
        if bb and prev_bbox:
            bbox_shift = (bb[0] - prev_bbox[0], bb[1] - prev_bbox[1])
        print(f"  step{k} act={a} player={player_cell(g)} floor_bbox={bb} "
              f"bbox_shift={bbox_shift} floor_symdiff={changed}")
        prev_fp = fp
        prev_bbox = bb


if __name__ == "__main__":
    main()
