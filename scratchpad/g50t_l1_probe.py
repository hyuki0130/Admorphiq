"""g50t L1 ground-truth probe: clear L0 via the adapter, then at L1 identify
spawn+goal by motion, map the floor grid, and MEASURE (a) the one-frame lag
(N same-dir steps -> how many cell moves) and (b) col-8 lateral passability
(which rows have a real LEFT exit). Frame-only reads; GT cross-check for counts.
"""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer
from admorphiq.kernels import find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL, FLOOR, MOVER, CIRC = 6, 5, 9, 8


def movers(grid, off):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != MOVER:
            continue
        r0 = reg["bbox"][0]
        if r0 < 7 or r0 > 58 or not (8 <= reg["size"] <= 40):
            continue
        cy, cx = reg["centroid"]
        out.append((round((cy - off[0]) / CELL), round((cx - off[1]) / CELL), reg["size"]))
    return out


def floor_cells(grid, off):
    h, w = len(grid), len(grid[0])
    cells = set()
    i = 0
    while off[0] + i * CELL < h:
        j = 0
        while off[1] + j * CELL < w:
            if grid[off[0] + i * CELL][off[1] + j * CELL] == FLOOR:
                cells.add((i, j))
            j += 1
        i += 1
    return cells


def cell_color(grid, off, cell):
    r, c = off[0] + cell[0] * CELL, off[1] + cell[1] * CELL
    return grid[r][c] if 0 <= r < len(grid) and 0 <= c < len(grid[0]) else -1


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = env.observation_space
    ad = Adapter(giveup=2000)
    steps = 0
    while steps < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    lv = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"reached L{lv} @ {steps} state={str(obs.state)[-10:]}")
    if lv != 1:
        print("did NOT reach L1"); return
    # settle transition frame: hold a blocked-ish move until stable
    grid = canonical_layer(obs)
    off = None
    for _ in range(6):
        obs = env.step(A[1]); steps += 1
        grid = canonical_layer(obs)
        mv = movers(grid, (0, 0))
        if mv:
            cy = mv[0]
            off = (int(round(cy[0])) * 0, 0)  # placeholder
    # derive offset from a mover centroid
    for reg in find_regions(grid, background=None):
        if reg["color"] == MOVER and 8 <= reg["size"] <= 40 and 7 <= reg["bbox"][0] <= 58:
            cy, cx = reg["centroid"]
            off = (int(round(cy)) % CELL, int(round(cx)) % CELL)
            break
    print("offset", off)
    print("movers@L1(settled):", movers(grid, off))
    fc = floor_cells(grid, off)
    print(f"floor cells: {len(fc)}")
    # identify player by a probe move (down usually free)
    before = movers(grid, off)
    obs = env.step(A[2]); steps += 1
    grid2 = canonical_layer(obs)
    after = movers(grid2, off)
    print("before", before, "after DOWN", after)

    # === MEASURE one-frame lag: 5 DOWN steps, log observed player cell each ===
    print("=== lag test: issue UP x1 then LEFT x6 along assumed top corridor ===")
    # first get to a known spot; just log raw: 6 LEFT from current
    cur = canonical_layer(obs)
    def pcell(g):
        ms = movers(g, off)
        return ms[0][:2] if ms else None
    seq = []
    for k in range(8):
        p0 = pcell(canonical_layer(obs))
        obs = env.step(A[3]); steps += 1  # LEFT
        p1 = pcell(canonical_layer(obs))
        seq.append((p0, p1))
    print("LEFT sequence (obs_before, obs_after):", seq)

    # === col-8 lateral passability: from several rows, try LEFT, see if moved ===
    print("=== NOTE: see LEFT sequence for lag; GT cross-check ===")
    g = env._game
    lvl = g.current_level
    for tag in ["medyellngi", "gilbljmfbc", "kjrcloicja"]:
        sp = lvl.get_sprites_by_tag(tag)
        print(f"  GT {tag} ({len(sp)}):", [(s.x, s.y) for s in sp])


if __name__ == "__main__":
    main()
