"""g50t L1 SLAM stage 4: with CORRECT player tracking, discover the plate(s) and
confirm the barrier-open mechanic frame-only.

Now that the player is trackable and the world is static, drive the real player
to each colour-8 frontier cell and measure whether standing there (or seating a
ghost via ACTION5) EXPANDS the reachable floor region. Uses the slide-aware
detector: barrier cells = floor cells ADDED after the body seats (a slide vacates
one cell), not a floor-expansion during approach.
"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer
from admorphiq.kernels import find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL, FLOOR, CIRC = 6, 5, 8
MOVE = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
VEC = {v: k for k, v in MOVE.items()}


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def nine(grid):
    out = []
    for reg in find_regions(grid, background=None):
        if reg["color"] != 9:
            continue
        r0 = reg["bbox"][0]
        if r0 < 7 or r0 > 58 or not (8 <= reg["size"] <= 40):
            continue
        out.append(reg)
    return out


class L1:
    def __init__(self, env):
        self.env = env
        self.off = None
        self.goal_cell = None
        self.player_cell = None

    def to_cell(self, cy, cx):
        return (round((cy - self.off[0]) / CELL), round((cx - self.off[1]) / CELL))

    def player_px(self, grid):
        regs = nine(grid)
        cands = [(r["centroid"][0], r["centroid"][1]) for r in regs]
        gc = self.goal_cell
        if gc is not None:
            cands = [c for c in cands if self.to_cell(*c) != gc] or cands
        if self.player_cell is not None and self.off is not None:
            pc = self.player_cell
            return min(cands, key=lambda c: abs(self.to_cell(*c)[0] - pc[0]) + abs(self.to_cell(*c)[1] - pc[1]))
        return cands[0] if cands else None

    def floor(self, grid):
        h, w = len(grid), len(grid[0])
        cells = set()
        i = 0
        while self.off[0] + i * CELL < h - 2:
            j = 0
            while self.off[1] + j * CELL < w - 2:
                if grid[self.off[0] + i * CELL][self.off[1] + j * CELL] == FLOOR:
                    cells.add((i, j))
                j += 1
            i += 1
        return cells

    def cell_color(self, grid, cell):
        r, c = self.off[0] + cell[0] * CELL, self.off[1] + cell[1] * CELL
        if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
            return grid[r][c]
        return -1

    def reachable(self, floor, start):
        seen = {start}
        parent = {}
        q = deque([start])
        while q:
            cur = q.popleft()
            for a, (dr, dc) in MOVE.items():
                n = (cur[0] + dr, cur[1] + dc)
                if n in floor and n not in seen:
                    seen.add(n)
                    parent[n] = (cur, a)
                    q.append(n)
        return seen, parent

    def path_to(self, parent, target):
        cells = []
        cur = target
        while cur in parent:
            cells.append(cur)
            cur = parent[cur][0]
        return cells[::-1]

    def step(self, a):
        obs = self.env.step(A[a])
        return canonical_layer(obs)

    def drive_to(self, grid, target_path):
        """Drive player through the ordered cells (lag-1 closed-loop). Returns
        (grid, arrived_bool). A step that doesn't displace within 3 tries = wall."""
        for tgt in target_path:
            tries = 0
            while self.player_cell != tgt and tries < 4:
                dr = max(-1, min(1, tgt[0] - self.player_cell[0]))
                dc = max(-1, min(1, tgt[1] - self.player_cell[1]))
                vec = (dr, dc) if (dr, dc) in VEC else ((dr, 0) if dr else (0, dc))
                a = VEC.get(vec)
                if a is None:
                    return grid, False
                grid = self.step(a)
                px = self.player_px(grid)
                if px:
                    self.player_cell = self.to_cell(*px)
                tries += 1
            if self.player_cell != tgt:
                return grid, False
        return grid, True

    def identify(self):
        obs = self.env.observation_space
        grid = self.step(2)  # snap probe
        regs = nine(grid)
        id_cells = [(r["centroid"][0], r["centroid"][1]) for r in regs]
        for a in [2, 4, 1, 3, 2, 4, 1, 3]:
            grid = self.step(a)
            regs = nine(grid)
            now = [(r["centroid"][0], r["centroid"][1]) for r in regs]
            moved = [c for c in now if all(abs(c[0]-o[0])+abs(c[1]-o[1]) > 2 for o in id_cells)]
            static = [c for c in now if any(abs(c[0]-o[0])+abs(c[1]-o[1]) <= 2 for o in id_cells)]
            if moved:
                self.off = (int(round(moved[0][0])) % CELL, int(round(moved[0][1])) % CELL)
                self.player_cell = self.to_cell(*moved[0])
                self.goal_cell = self.to_cell(*static[0]) if static else None
                return grid
            id_cells = now
        return grid


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1")
        return
    g = L1(env)
    grid = g.identify()
    print(f"off={g.off} player={g.player_cell} goal={g.goal_cell}")
    floor = g.floor(grid)
    reach, parent = g.reachable(floor, g.player_cell)
    print(f"floor={len(floor)} reachable={len(reach)} goal_in_reach={g.goal_cell in reach}")

    # colour-8 frontier cells adjacent to the reachable region
    frontier = set()
    for cell in reach:
        for dr, dc in MOVE.values():
            n = (cell[0] + dr, cell[1] + dc)
            if n not in reach and g.cell_color(grid, n) == CIRC:
                frontier.add(n)
    print(f"colour-8 frontier candidates: {sorted(frontier)}")

    # try each: navigate to an adjacent reachable cell, step onto the candidate,
    # measure reachable expansion (slide-aware: floor added after seating).
    for cand in sorted(frontier):
        # re-derive reachable from current player each attempt
        reach, parent = g.reachable(g.floor(grid), g.player_cell)
        approach = None
        for dr, dc in MOVE.values():
            nb = (cand[0] - dr, cand[1] - dc)
            if nb in reach:
                approach = nb
                break
        if approach is None:
            print(f"  cand {cand}: no reachable approach, skip")
            continue
        floor_before = g.floor(grid)
        reach_before = len(g.reachable(floor_before, g.player_cell)[0])
        path = g.path_to(parent, approach) + [cand]
        grid, arrived = g.drive_to(grid, path)
        floor_after = g.floor(grid)
        added = floor_after - floor_before
        reach_after = len(g.reachable(floor_after, g.player_cell)[0]) if g.player_cell in floor_after else 0
        print(f"  cand {cand}: arrived={arrived} player={g.player_cell} "
              f"floor_added={sorted(added)} reach {reach_before}->{reach_after}")


if __name__ == "__main__":
    main()
