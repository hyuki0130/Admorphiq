"""L7 fog explorer prototype (frame-only): disc-masked parse + accumulated
STATIC memory (walls/floor/goal/static-changers/pushwalls/refills) separated
from DYNAMIC mover observations, frontier exploration to reveal the maze, then
joint-BFS (1 goal + static changers + 1 mover) + open-loop to a live L7 win.
Measures reveal completeness + action cost.
"""
from __future__ import annotations
import math, sys
from collections import Counter, deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import (
    Adapter, _find_avatar, _cell_counts, _classify_changer, _decode_goal_preview,
    _decode_token, _detect_pushwalls_pixel, _find_refill_sprites, _snap_to_lattice,
    _GOAL_BORDER, _PALETTE, _FLOOR_COLOR, _WALL_COLOR, _PLAYABLE_MAX_ROW, _CELL,
)
from admorphiq.adapters25.base import canonical_layer

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4}
MOVES = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
FOG_R = 20.0


def cell_fully_visible(cx, cy, ax, ay):
    """True if the 5x5 cell at (cx,cy) is entirely within the fog radius of the
    avatar center (avatar.y+1.5, avatar.x+1.5) — matching render_interface."""
    ccx, ccy = ax + 1.5, ay + 1.5
    for dx in (0, 4):
        for dy in (0, 4):
            if math.dist((cy + dy, cx + dx), (ccy, ccx)) > FOG_R:
                return False
    return True


class Memory:
    def __init__(self):
        self.static = {}  # cell -> 'floor'|'wall'|'goal'|'shape'|'color'|'refill'
        self.goal_req = None
        self.pushwalls = {}  # (sx,sy) -> (dx,dy)
        self.mover_cells = {"rot": set(), "shape": set(), "color": set()}  # kind -> observed cells (for mover detection)
        self.changer_seen = {}  # cell -> kind (all changer observations)
        self.token = None
        self.ox = self.oy = None


def parse_disc(grid, mem: Memory):
    av = _find_avatar(grid)
    if av is None:
        return None
    ax, ay = av
    mem.ox, mem.oy = ax % _CELL, ay % _CELL
    tok = _decode_token(grid)
    if tok is not None:
        mem.token = tok
    xs = list(range(mem.ox, len(grid[0]) - _CELL + 1, _CELL))
    ys = list(range(mem.oy, len(grid) - _CELL + 1, _CELL))
    # push-walls: detect only those whose line is in the disc
    for (sx, sy, dx, dy) in _detect_pushwalls_pixel(grid):
        if cell_fully_visible(sx, sy, ax, ay):
            mem.pushwalls[(sx, sy)] = (dx, dy)
    # refills (snapped) within disc
    for (rx, ry) in _find_refill_sprites(grid):
        cell = _snap_to_lattice(rx, ry, mem.ox, mem.oy)
        if cell_fully_visible(cell[0], cell[1], ax, ay):
            mem.static[cell] = "refill"
    for x in xs:
        for y in ys:
            if not cell_fully_visible(x, y, ax, ay):
                continue
            hh = _cell_counts(grid, x, y)
            dom = hh.most_common(1)[0][0]
            if y < _PLAYABLE_MAX_ROW and dom == _GOAL_BORDER and sum(hh.get(c, 0) for c in _PALETTE) >= 3:
                mem.static[(x, y)] = "goal"
                if mem.goal_req is None:
                    r = _decode_goal_preview(grid, x, y)
                    if r is not None:
                        mem.goal_req = r
                continue
            kind = _classify_changer(hh, dom) if y < _PLAYABLE_MAX_ROW else None
            if kind is not None:
                mem.changer_seen[(x, y)] = kind
                mem.mover_cells[kind].add((x, y))
                mem.static[(x, y)] = "floor"  # changer sits on floor (passable)
            elif dom == _FLOOR_COLOR:
                mem.static.setdefault((x, y), "floor")
            elif dom == _WALL_COLOR:
                mem.static[(x, y)] = "wall"
    mem.static[av] = "floor"
    return av


def frontier_target(mem: Memory, av):
    """Nearest revealed-floor cell adjacent to an UNrevealed neighbour, by BFS on
    known-floor. Returns (target_cell, path_actions) or None."""
    passable = {c for c, t in mem.static.items() if t in ("floor", "goal", "refill")}
    start = av
    if start not in passable:
        passable = passable | {start}
    q = deque([(start, [])])
    seen = {start}
    best = None
    while q:
        cell, path = q.popleft()
        # is this cell a frontier (has an unrevealed lattice neighbour)?
        for aid, (dx, dy) in MOVES.items():
            nb = (cell[0] + dx * _CELL, cell[1] + dy * _CELL)
            if nb not in mem.static and 0 <= nb[0] < 64 and 0 <= nb[1] < 60:
                best = (cell, path)
                break
        if best:
            return best
        for aid, (dx, dy) in MOVES.items():
            nb = (cell[0] + dx * _CELL, cell[1] + dy * _CELL)
            if nb in passable and nb not in seen:
                seen.add(nb)
                q.append((nb, path + [aid]))
    return None


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=9000)
    steps = 0
    while steps < 9000 and obs.levels_completed < 6:
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    obs = env.step(GameAction.ACTION1)

    mem = Memory()
    explore_actions = 0
    for it in range(400):
        grid = tuple(tuple(r) for r in canonical_layer(obs))
        if not grid or len(grid) < 64 or not grid[0]:
            obs = env.step(A[1]); explore_actions += 1; continue
        av = parse_disc(grid, mem)
        if av is None:
            obs = env.step(A[1]); explore_actions += 1; continue
        # stop condition: goal + both static changers + mover(>=2 cells) known
        movers = {k: cells for k, cells in mem.mover_cells.items() if cells}
        has_goal = any(t == "goal" for t in mem.static.values())
        static_kinds = {k for k, cells in mem.mover_cells.items() if len(cells) == 1}
        mover_kinds = {k for k, cells in mem.mover_cells.items() if len(cells) >= 2}
        ft = frontier_target(mem, av)
        if has_goal and mem.goal_req and len(static_kinds | mover_kinds) >= 3 and mover_kinds and ft is None:
            print(f"REVEALED after {explore_actions} explore actions")
            break
        if ft is None:
            print(f"no frontier after {explore_actions}; revealed cells={len(mem.static)}")
            break
        target, path = ft
        if not path:
            # at frontier: step toward the unrevealed neighbour to reveal it
            acted = False
            for aid, (dx, dy) in MOVES.items():
                nb = (av[0] + dx * _CELL, av[1] + dy * _CELL)
                if nb not in mem.static:
                    obs = env.step(A[aid]); explore_actions += 1; acted = True; break
            if not acted:
                obs = env.step(A[1]); explore_actions += 1
        else:
            obs = env.step(A[path[0]]); explore_actions += 1
    # report reveal
    goalcells = [c for c, t in mem.static.items() if t == "goal"]
    print("goal:", goalcells, "req:", mem.goal_req)
    print("static changers:", {c: k for c, k in mem.changer_seen.items()})
    print("mover cells by kind:", {k: sorted(v) for k, v in mem.mover_cells.items() if v})
    print("pushwalls:", mem.pushwalls)
    print("refills:", [c for c, t in mem.static.items() if t == "refill"])
    print("revealed floor:", sum(1 for t in mem.static.values() if t == 'floor'), "walls:", sum(1 for t in mem.static.values() if t == 'wall'))
    print("GT goal (29,50); GT static shape@(19,40) color@(9,40); GT mover rot vertical x54")
    print("total explore actions:", explore_actions)


if __name__ == "__main__":
    main()
