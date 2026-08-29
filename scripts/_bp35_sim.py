"""A faithful, standalone simulator of bp35 built from the game's own board table.

Purpose: bp35's level 6 is claimed to be blocked by a "crumbling platform". The game's source says
`yuuqpmlxorv` is not a crumbling platform at all — it is a CLICK TOGGLE that swaps with
`oonshderxef` (pass-through) in both directions, and the four shrinking sprites are that swap's
animation. Before building anything, the whole level has to be searched for a solution; a search
needs a model, and a model that is not checked against the engine is a guess.

Expected feedback: `verify` prints ZERO mismatches over random action sequences, or the simulator is
wrong and every search result taken from it is worthless.
"""
from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

GRID_W = 11
PASSABLE = (frozenset(), frozenset({"oonshderxef"}), frozenset({"aknlbboysnc"}),
            frozenset({"aknlbboysnc", "oonshderxef"}))
GEM = "fjlzdjxhant"
SPIKES = (frozenset({"ubhhgljbnpu"}), frozenset({"hzusueifitk"}))
WALL = "xcjjwqfzjfe"
SWITCH = "lrpkmzabbfa"
SOLID_TOGGLE = "yuuqpmlxorv"
PASS_TOGGLE = "oonshderxef"
ONESHOT = "qclfkhjnaac"
SPREAD = "etlsaqqtjvn"
CLICKABLE = (ONESHOT, SPREAD, SOLID_TOGGLE, PASS_TOGGLE, SWITCH)


def load_module():
    p = Path(__file__).resolve().parents[1] / "environment_files/bp35/0a0ad940/bp35.py"
    spec = importlib.util.spec_from_file_location("bp35mod", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules["bp35mod"] = m
    spec.loader.exec_module(m)
    return m


class Sim:
    __slots__ = ("cells", "px", "py", "grav_up", "cam_y", "used", "won", "lost", "h")

    def __init__(self, cells, px, py, grav_up, cam_y):
        self.cells = cells          # dict (x,y) -> frozenset of names (terrain only)
        self.px, self.py = px, py
        self.grav_up = grav_up      # True == vivnprldht == dy of -1
        self.cam_y = cam_y
        self.used = 0
        self.won = False
        self.lost = False

    def clone(self):
        s = Sim(dict(self.cells), self.px, self.py, self.grav_up, self.cam_y)
        s.used, s.won, s.lost = self.used, self.won, self.lost
        return s

    def at(self, x, y):
        return self.cells.get((x, y), frozenset())

    # --- fsvnqdbzrp ------------------------------------------------------------------
    def _fall(self, pos):
        dy = -1 if self.grav_up else 1
        steps = 0
        last = pos
        cur = (pos[0], pos[1] + dy)
        names = self.at(*cur)
        while names in PASSABLE:
            last = cur
            cur = (cur[0], cur[1] + dy)
            names = self.at(*cur)
            steps += 1
        if names == frozenset({GEM}):
            return steps + 1, cur, True, False
        if names in SPIKES:
            return steps + 1, last, False, True
        return steps, last, False, False

    def _cam_to(self, y):
        self.cam_y = y * 6 - 31 + (-5 if self.grav_up else 5)

    # --- pywlvyklps ------------------------------------------------------------------
    def move(self, right: bool):
        self.used += 1
        dx = 1 if right else -1
        tgt = (self.px + dx, self.py)
        if tgt[0] < 0:
            tgt = (0, tgt[1])
            names = frozenset({WALL})
        else:
            names = self.at(*tgt)
        if names == frozenset({GEM}):
            self.px, self.py = tgt
            self.won = True
            return
        if names in PASSABLE:
            steps, fallen, gem, spike = self._fall(tgt)
            if steps == 0:
                self.px, self.py = tgt
            else:
                self.px, self.py = fallen
                self._cam_to(fallen[1])
                if gem:
                    self.won = True
                elif spike:
                    self.lost = True

    # --- pbsitubcfd ------------------------------------------------------------------
    def _drop(self, clicked, forced: bool):
        dy = -1 if self.grav_up else 1
        below = (self.px, self.py + dy)
        if not forced and clicked != below:
            return
        names = self.at(*below)
        if WALL in names or (forced and (names & {SWITCH, SOLID_TOGGLE, ONESHOT, SPREAD})):
            self._cam_to(self.py)          # camera only; source uses the pre-fall y
            self.cam_y = self.py * 6 - 31 + (-5 if self.grav_up else 5)
            return
        steps, fallen, gem, spike = self._fall(below)
        self.px, self.py = fallen
        if gem:
            self.won = True
        elif spike:
            self.lost = True
        self._cam_to(fallen[1])

    # --- gwfodrkvzx ------------------------------------------------------------------
    def click_cell(self, gx, gy):
        """Click the SCREEN pixel that resolves to grid cell (gx, gy). Caller checks on-screen."""
        self.used += 1
        names = self.at(gx, gy)
        if names == frozenset({ONESHOT}):
            self._drop((gx, gy), False)
            self.cells.pop((gx, gy), None)
        elif names == frozenset({SPREAD}):
            spawned = [(gx + dx, gy + dy) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                       if not self.at(gx + dx, gy + dy)]
            self._drop((gx, gy), False)
            self.cells.pop((gx, gy), None)
            for c in spawned:
                self.cells[c] = frozenset({SPREAD})
        elif names == frozenset({SOLID_TOGGLE}):
            self._drop((gx, gy), False)
            self.cells[(gx, gy)] = frozenset({PASS_TOGGLE})
        elif names == frozenset({PASS_TOGGLE}):
            self._drop((gx, gy), False)
            self.cells[(gx, gy)] = frozenset({SOLID_TOGGLE})
        elif names == frozenset({SWITCH}):
            self.grav_up = not self.grav_up
            self._drop((gx, gy), True)
            self.cells.pop((gx, gy), None)

    # --- helpers ---------------------------------------------------------------------
    def on_screen(self, gx, gy):
        sx = gx * 6
        sy = gy * 6 - self.cam_y
        return 0 <= sx <= 63 and 0 <= sy <= 63

    def screen_xy(self, gx, gy):
        return gx * 6, gy * 6 - self.cam_y

    def clickables(self):
        return [(x, y) for (x, y), n in self.cells.items()
                if len(n) == 1 and next(iter(n)) in CLICKABLE and self.on_screen(x, y)]

    def key(self):
        mut = tuple(sorted((x, y, next(iter(n)))
                           for (x, y), n in self.cells.items()
                           if len(n) == 1 and next(iter(n)) in CLICKABLE))
        return (self.px, self.py, self.grav_up, mut)


def from_scene(scene, height=39):
    cells = {}
    for y in range(height):
        for x in range(GRID_W):
            names = frozenset(i.name for i in scene.hdnrlfmyrj.jhzcxkveiw(x, y)
                              if not i.name.startswith("player"))
            if names:
                cells[(x, y)] = names
    p = scene.twdpowducb.qumspquyus
    return Sim(cells, p[0], p[1], scene.vivnprldht, scene.camera.rczgvgfsfb[1])


def make_level(m, level_1based):
    scene = m.uakietkqfso()
    scene.qswcochjodb = level_1based
    scene.ruarvcqajl()
    return scene, from_scene(scene)


def _snap(scene, sim):
    a = (scene.twdpowducb.qumspquyus[0], scene.twdpowducb.qumspquyus[1],
         scene.vivnprldht, scene.camera.rczgvgfsfb[1],
         bool(scene.nkuphphdgrp), bool(scene.jrhqdvdwpsb))
    b = (sim.px, sim.py, sim.grav_up, sim.cam_y, sim.won, sim.lost)
    ta = tuple(sorted((x, y, n) for (x, y), s in from_scene(scene).cells.items() for n in s))
    tb = tuple(sorted((x, y, n) for (x, y), s in sim.cells.items() for n in s))
    return (a, ta), (b, tb)


def verify(level, trials, actions, seed):
    m = load_module()
    bad = 0
    for t in range(trials):
        rng = random.Random(seed * 10007 + t)
        scene, sim = make_level(m, level)
        for i in range(actions):
            opts = ["L", "R"] + [("C", c) for c in sim.clickables()]
            a = rng.choice(opts)
            if a == "L":
                scene.oreuzgjmdx(-1, 0); sim.move(False)
            elif a == "R":
                scene.oreuzgjmdx(1, 0); sim.move(True)
            else:
                gx, gy = a[1]
                sx, sy = sim.screen_xy(gx, gy)
                scene.gwfodrkvzx(sx, sy); sim.click_cell(gx, gy)
            # ⛔ the engine DEFERS every cell mutation, the switch removal and the camera move
            # into the animation queue; `scene.render()` is the tick that runs them. Without it the
            # engine snapshot is a half-applied action and every diff is an artefact of the probe.
            scene.render()
            ea, eb = _snap(scene, sim)
            if ea != eb:
                bad += 1
                print(f"MISMATCH trial={t} step={i} act={a}")
                print("  engine", ea[0])
                print("  sim   ", eb[0])
                da = set(ea[1]) ^ set(eb[1])
                if da:
                    print("  cells diff", sorted(da)[:8])
                break
            if sim.won or sim.lost:
                break
    print(f"level={level} trials={trials} mismatching={bad}")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "verify":
        verify(int(args[1]) if len(args) > 1 else 6,
               int(args[2]) if len(args) > 2 else 40,
               int(args[3]) if len(args) > 3 else 40,
               int(args[4]) if len(args) > 4 else 1)
    else:
        m = load_module()
        scene, sim = make_level(m, 6)
        for y in range(38, -1, -1):
            print(f"y={y:2d} " + "".join(
                {"xcjjwqfzjfe": "o", "qclfkhjnaac": "x", "lrpkmzabbfa": "g", "yuuqpmlxorv": "1",
                 "oonshderxef": "2", "ubhhgljbnpu": "v", "hzusueifitk": "u",
                 "fjlzdjxhant": "+"}.get(next(iter(sim.at(x, y)), ""), "." if not sim.at(x, y) else "?")
                for x in range(GRID_W)))
        print("player", (sim.px, sim.py), "grav_up", sim.grav_up, "cam", sim.cam_y)


if __name__ == "__main__":
    main()
