"""Pixel-faithful LS20 step() simulator (L5 push-carry). Replicates
environment_files/ls20/9607627b/ls20.py step()/txnfzvzetn/prpxgfxlcm/ullzqnksoj
at the PIXEL level so the joint BFS can plan over it. Validated by lockstep.

State (mutable): avatar (ax,ay) pixel, token (sh,co,ro), steps_left,
refills_taken(frozenset), mover (mx,mdir).

Static maze (from parse/GT):
  cell = 5
  hard_walls: set[(x,y)] lattice cells that always block (ihdgageizm)
  goal: (x,y); goal_req: (sh,co,ro)
  changers: {(x,y): 'shape'|'color'|'rot'}   (STATIC changers only)
  refills: set[(x,y)]
  pushwalls: list of (sx,sy,dx,dy,w,h)  sprite pixel positions
  fjzuynaokm: set[(x,y)] pixel positions of walls+goal (push-stop set)
  mover: dict with track cells list + rot semantics (mover is a rot changer)
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Optional

CELL = 5


@dataclass(frozen=True)
class Maze:
    hard_walls: frozenset
    goal: tuple
    goal_req: tuple
    changers: tuple  # ((cell, kind), ...)
    refills: frozenset
    pushwalls: tuple  # ((sx,sy,dx,dy,w,h), ...)
    fjzuynaokm: frozenset
    mover_track: tuple  # (mx0, mx1, ...) cells at fixed my, or () if none
    mover_my: int = -1
    step_full: int = 21

    def changer_map(self):
        return dict(self.changers)


def bbox_overlap(ax, ay, bx, by, aw=CELL, ah=CELL, bw=CELL, bh=CELL):
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def carry_dist(maze: Maze, sx, sy, dx, dy, w, h):
    """ullzqnksoj: number of wall-widths the avatar is carried."""
    wall_cx, wall_cy = sx + dx, sy + dy
    found = None
    for k in range(1, 12):
        px = wall_cx + dx * w * k
        py = wall_cy + dy * h * k
        if (px, py) in maze.fjzuynaokm:
            found = k
            break
    if found is None:
        return 0
    return max(0, found - 1)


@dataclass(frozen=True)
class SimState:
    ax: int
    ay: int
    sh: int
    co: int
    ro: int
    steps: int
    taken: frozenset
    mx: int  # mover cell x (or -1 if no mover)
    mdir: int  # mover direction: 1=right, 3=left

    def key(self):
        return (self.ax, self.ay, self.sh, self.co, self.ro, self.steps, self.taken, self.mx, self.mdir)


def mover_advance(maze: Maze, mx: int, mdir: int):
    """One mover step along a horizontal track; bounce at ends. Returns
    (mx', mdir'). Mover advances only on a SUCCESSFUL avatar move (caller
    handles undo-on-block by not calling this)."""
    track = maze.mover_track
    if not track or mx < 0:
        return mx, mdir
    lo, hi = min(track), max(track)
    step = CELL if mdir == 1 else -CELL
    cand = mx + step
    if lo <= cand <= hi:
        return cand, mdir
    mdir = 3 if mdir == 1 else 1
    step = CELL if mdir == 1 else -CELL
    return mx + step, mdir


def step(maze: Maze, s: SimState, action: int) -> SimState:
    """One engine step. action: 1=up 2=down 3=left 4=right.
    Returns the next SimState (win/blocked folded into position/token)."""
    MOVES = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
    dx, dy = MOVES[action]
    # 1. mover steps FIRST (provisional); undoes if the avatar move is blocked.
    prov_mx, prov_mdir = mover_advance(maze, s.mx, s.mdir)
    nx, ny = s.ax + dx * CELL, s.ay + dy * CELL
    # 2. txnfzvzetn: is (nx,ny) blocked? gather effect.
    blocked = False
    # hard wall
    if (nx, ny) in maze.hard_walls:
        blocked = True
    # goal blocks unless matched
    matched_goal = (nx, ny) == maze.goal and (s.sh, s.co, s.ro) == maze.goal_req
    if (nx, ny) == maze.goal and not matched_goal:
        blocked = True
    if blocked:
        # mover undoes -> state stays; avatar stays.
        return s
    # avatar moves.
    ax, ay = nx, ny
    nsh, nco, nro, ntaken = s.sh, s.co, s.ro, s.taken
    # changer effect at destination (static changers)
    cmap = maze.changer_map()
    kind = cmap.get((ax, ay))
    # mover is a rot changer at its NEW cell (post provisional step)
    if maze.mover_track and (ax, ay) == (prov_mx, maze.mover_my):
        kind = "rot"
    if kind == "rot":
        nro = (nro + 1) % 4
    elif kind == "color":
        nco = (nco + 1) % 4
    elif kind == "shape":
        nsh = (nsh + 1) % 6
    # refill
    nsteps = s.steps - 1
    is_refill = (ax, ay) in maze.refills and (ax, ay) not in s.taken
    if is_refill:
        nsteps = maze.step_full
        ntaken = s.taken | {(ax, ay)}
    # 3. push-walls (only when alive). First colliding wall with dist>0 fires.
    if nsteps >= 0:
        for (sx, sy, pdx, pdy, w, h) in maze.pushwalls:
            if bbox_overlap(ax, ay, sx, sy, CELL, CELL, w, h):
                dist = carry_dist(maze, sx, sy, pdx, pdy, w, h)
                if dist > 0:
                    ax += pdx * w * dist
                    ay += pdy * h * dist
                    break
    return SimState(ax, ay, nsh, nco, nro, nsteps, ntaken, prov_mx, prov_mdir)


def is_win(maze: Maze, s: SimState) -> bool:
    return (s.ax, s.ay) == maze.goal and (s.sh, s.co, s.ro) == maze.goal_req
