"""dc22 — is the one-pixel condemnation the UPSTREAM blocker, and does a MIXED-TILE rule free
the crane's plates without freeing the crane's RAIL?

Purpose. Rule 7ak measured that `_standable`/`_solid` condemn an avatar-sized tile when ANY pixel
carries a condemned colour, and that dc22's four crane plates are 2x2 sprites drawn `[[1,0],[0,C]]`
sitting on standable ground — so colour 0, which is the crane's RAIL and is condemned CORRECTLY,
condemns the plates too. The repair already measured negative struck colour 0 out of `_not_floor`
entirely, which also makes the rail itself read as floor; that is a different rule from this one.

The rule measured here (R4) keeps the board's GROUND condemning a tile on one pixel — a hole is a
hole — and lets a LEARNED colour condemn only a tile that is ENTIRELY condemned colours: a wall is
a solid body, one pixel of it inside an otherwise solid tile is decoration. The rail is a 4x4 flat
block of colour 0, so every 2x2 tile inside it stays refused; a plate is 3/4 something else.

Reported for the level the tool is on, under three rules — R1 any-bad (current), R2 all-bad,
R4 ground-any + condemned-all — the standable-tile count, the four plate tiles, and the size of the
avatar's reachable region.

TWO CONTROLS, rule 7aj:
  * POSITIVE — the four plate tiles must be REFUSED under R1 and ACCEPTED under R4. If R1 accepts
    them the premise of rule 7ak is wrong and nothing below means anything.
  * NEGATIVE — on a level where `_not_floor` is empty the three rules are identical BY
    CONSTRUCTION, and the probe asserts it. A difference there is a broken instrument, not a
    finding. Levels 1-5 are also reported so the blast radius on the levels this game already
    clears is a number and not a hope.

Varying parameter FIRST = repetition index (this probe is deterministic, so the fan measures a
RATE and not a draw).  Second = actions handed to a fresh gantry; third = target level index
(0-based, default 5 = the last).  Prints ONE JSON line.
Rule 7f: any level change is reported with its DIRECTION and the resulting level number.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402

# Plate positions read from the game's own source (`sprite_81*`, tag `njvd-rolo`) on level 6, as
# LEVEL coordinates (y, x). They are used only to LOOK UP tiles in the measured board — nothing
# here is fed to a tool, and the probe prints each tile's pixels so the lookup can be checked.
L6_PLATES = {"e_left": (58, 32), "b_up": (56, 34), "a_right": (58, 36), "h_down": (60, 34)}
L6_KEYS = {"g_grab": (48, 34), "d_cycle": (18, 6)}


def standable(layout, side, bg, not_floor, rule):
    """Boolean grid of avatar-sized tiles that are floor, under one of three rules."""
    layout = np.asarray(layout)
    ground = layout == bg
    condemned = np.zeros_like(ground)
    for c in not_floor:
        condemned |= layout == c
    if rule == "R1":
        bad = ground | condemned
        want_zero = True
    elif rule == "R2":
        bad = ~(ground | condemned)          # count the GOOD pixels; zero good == all bad
        want_zero = False
    else:                                      # R4
        bad = ground
        want_zero = True
    h, w = bad.shape
    if h < side or w < side:
        return np.zeros((0, 0), dtype=bool)

    def window(mask):
        acc = np.zeros((h + 1, w + 1), dtype=np.int32)
        acc[1:, 1:] = mask.astype(np.int32).cumsum(0).cumsum(1)
        return acc[side:, side:] - acc[:-side, side:] - acc[side:, :-side] + acc[:-side, :-side]

    if rule == "R2":
        return window(bad) > 0
    ok = window(bad) == 0 if want_zero else window(bad) > 0
    if rule == "R4":
        # …and a tile every pixel of which is a condemned colour is a wall.
        ok &= window(condemned) < side * side
    return ok


def reach(grid, start, deltas):
    """Cells the avatar can walk to from `start` over `grid`, using the measured move deltas."""
    if not grid.size or start is None:
        return set()
    sy, sx = start
    if not (0 <= sy < grid.shape[0] and 0 <= sx < grid.shape[1]) or not grid[sy, sx]:
        return set()
    seen = {start}
    stack = [start]
    while stack:
        y, x = stack.pop()
        for dy, dx in deltas:
            n = (y + dy, x + dx)
            if n in seen:
                continue
            if 0 <= n[0] < grid.shape[0] and 0 <= n[1] < grid.shape[1] and grid[n[0], n[1]]:
                seen.add(n)
                stack.append(n)
    return seen


class Probe:
    """Generic tools until the target level, then a FRESH gantry, then read its own state."""

    def __init__(self, budget, target):
        self.inner = SE._make_agent("unified", game_id="dc22")
        self.budget, self.target = budget, target
        self.tool = None
        self.used = 0
        self.queue = []
        self.report = None
        self.start_level = None
        self.moved = []

    def is_done(self, frames, obs):
        if obs.levels_completed >= self.target:
            return self.used >= self.budget
        return self.inner.is_done(frames, obs)

    def choose_action(self, frames, obs):
        from admorphiq.tools.gantry import GantryCraneTool
        if obs.levels_completed < self.target:
            return self.inner.choose_action(frames, obs)
        if self.tool is None:
            self.tool = GantryCraneTool()
            self.tool.reset()
            self.start_level = int(obs.levels_completed)
        if int(obs.levels_completed) != self.start_level:
            self.moved.append({"from": self.start_level, "to": int(obs.levels_completed),
                               "direction": "UP" if obs.levels_completed > self.start_level else "DOWN"})
            self.start_level = int(obs.levels_completed)
        self.used += 1
        t = self.tool
        if not self.queue:
            steps = t.propose(frames, obs)
            self.queue = list(steps) if steps else []
            if self.used >= self.budget or t._dead or t._retired or not self.queue:
                self.measure(obs)
                self.used = self.budget
        if not self.queue:
            return self._act(1, None)
        aid, xy = self.queue.pop(0)
        return self._act(aid, xy)

    @staticmethod
    def _act(aid, xy):
        from admorphiq.adapter import AdmorphiqAdapter
        from admorphiq.types import ActionType
        from admorphiq.types import GameAction as AGA
        if xy is not None:
            return AdmorphiqAdapter._convert_action(AGA.coordinate(int(xy[0]), int(xy[1])))
        return AdmorphiqAdapter._convert_action(AGA.simple(ActionType(aid)))

    def measure(self, obs):
        from admorphiq.tools.base import frame_2d
        if self.report is not None:
            return
        t = self.tool
        g = frame_2d(obs)
        geom = t._read(g)
        rec = {"level": int(obs.levels_completed), "budget_used": self.used,
               "dead": bool(t._dead), "retired": bool(t._retired),
               "not_floor": sorted(int(c) for c in t._not_floor),
               "side": int(t._side), "avatar_colour": int(t._avatar),
               "deltas": {str(k): list(v) for k, v in t._deltas.items()},
               "kinds": {str(k): v for k, v in t._kind.items()},
               "drives": [list(c) for c in t._drives()],
               "objects": len(t._objects), "warps": len(t._warps)}
        if geom is None:
            rec["read"] = None
            self.report = rec
            return
        board = np.asarray(geom["board"])
        top, right = int(geom["top"]), int(geom["panel"])
        bg, side = int(geom["bg"]), int(geom["side"])
        rec["read"] = {"top": top, "bot": int(geom["bot"]), "panel_col": right,
                       "board_shape": list(board.shape), "bg": bg,
                       "rare": [int(v) for v in geom["rare"]]}
        rec["panel_buttons"] = [list(c) for c in t._panel_buttons(g, geom)]
        start = t._at(board, t._avatar) if t._avatar >= 0 else None
        rec["avatar_cell"] = list(start) if start else None
        # The avatar's own move deltas if it has measured them, else the lattice its tiles sit on.
        deltas = list(t._deltas.values()) or [(side, 0), (-side, 0), (0, side), (0, -side)]
        rec["deltas_used"] = [list(d) for d in deltas]

        cells = {}
        if rec["level"] == 5:
            for name, (y, x) in {**L6_PLATES, **L6_KEYS}.items():
                cells[name] = (y - top, x)
        rec["probe_cells"] = {k: list(v) for k, v in cells.items()}
        rec["rules"] = {}
        for rule in ("R1", "R2", "R4"):
            grid = standable(board, side, bg, t._not_floor, rule)
            entry = {"standable": int(grid.sum()) if grid.size else 0,
                     "reach": len(reach(grid, tuple(start) if start else None, deltas))}
            entry["cells"] = {
                name: (bool(grid[y, x]) if grid.size and 0 <= y < grid.shape[0] and 0 <= x < grid.shape[1] else None)
                for name, (y, x) in cells.items()}
            entry["reachable_cells"] = {}
            r = reach(grid, tuple(start) if start else None, deltas)
            for name, c in cells.items():
                entry["reachable_cells"][name] = tuple(c) in r
            rec["rules"][rule] = entry
        # What the probe cells actually LOOK like, so the lookup can be checked rather than trusted.
        rec["tiles"] = {name: [[int(v) for v in row]
                               for row in board[y:y + side, x:x + side]]
                        for name, (y, x) in cells.items()
                        if 0 <= y < board.shape[0] and 0 <= x < board.shape[1]}
        # NEGATIVE CONTROL: with nothing condemned the three rules are the same rule.
        blank = standable(board, side, bg, set(), "R1")
        rec["control_negative"] = {
            "no_condemned_R1_eq_R4": bool(np.array_equal(
                blank, standable(board, side, bg, set(), "R4"))),
            "no_condemned_R1_eq_R2": bool(np.array_equal(
                blank, standable(board, side, bg, set(), "R2"))),
        }
        self.report = rec


def main():
    rep = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    target = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"result": "NO_GAME"}), flush=True)
        return
    ei = envs[0]
    ag = Probe(budget, target)
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="mixedtile",
                      max_actions=4000, adapter_factory=lambda: ag)
    out = {"rep": rep, "budget": budget, "target_level": target,
           "levels_completed": res.get("levels_completed"),
           "total_actions": res.get("total_actions"),
           "level_changes": ag.moved,
           "report": ag.report}
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
