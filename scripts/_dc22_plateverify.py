"""dc22 level 6: park the avatar on each PLATE and ask every drive.  Is the plate frame-visible?

DECODED from the level's own data (`environment_files/dc22/fdcac232/dc22.py`, `levels[5]`), then
asked of the running game because the source says what is POSSIBLE (rule 7g):

  control sprite        game (x,y)   key   what it drives   its plate (`njvd-rolo`)  game (x,y)
  crzsjq-up-1           (49,31)      b     crane UP         sprite_81-1              (34,56)
  crzsjq-lersnf-2       (49,39)      h     crane DOWN       sprite_81-4              (34,60)
  crzsjq-lersnf-1       (45,35)      e     crane LEFT       sprite_81                (32,58)
  crzsjq-riidpd-1       (53,35)      a     crane RIGHT      sprite_81-2              (36,58)
  crzsjq-grawwq-1       (47,17)      g     GRAB             none — a `piyqze` pickup

All five are `buezna` + `sys_click` and ship `visible=False`.  `yuonzbouxb()` runs at the top of
every step and makes exactly those controls whose key matches a plate the avatar OVERLAPS visible
and intangible, hiding the rest; `xodizggcom` skips invisible sprites, so a control whose plate is
not underfoot is a dead click at a cell that still draws its console art.  That is why
`_dc22_rail.py` measured all four drives inert over 23 presses each from (49,28) while
`/tmp/pfan_dc22pt17.jsonl` has the same (32,50) sliding a 28-pixel body from (55,34): frame row 55
col 34 overlaps plate `b` at frame rows 56-57 cols 34-35.

The four plates are a D-PAD ON THE BOARD around frame (58,34), mirroring the console's own D-pad.

Two questions only a run can answer:
  1. does each plate enable exactly its own drive (and does the crane's TRACK refuse some anyway)?
  2. does standing on a plate change the PANEL's PIXELS?  If it does, a frame-only tool can learn
     "this control is enabled from here" by walking; if it does not, the only route is to press
     every silent control from every cell, which is what the previous arm spent 382 presses on.

  arg 1 = repetition (fan slot).  arg 2 = presses per parked cell (default 2).
  arg 3 = `_dc22_percep` mask, arg 4 = `_dc22_gantryx` mask.

⛔ The first version of this probe planned from the START cell and `_plan_full` called all eight
plate cells UNREACHABLE — correctly: the cluster is reached only through the aimed teleport, which
needs a `piyqze` pickup first.  So the sweep now WAITS until the tool has carried itself into the
cluster (frame rows 50-62, cols 28-40) under its own steam and only then parks, which is the only
position from which the question "does each plate enable its own drive" can be asked.
Rule 7x: driven by the scorer's own `run_game`.  Rule 7f: the level count prints as a number.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402

# Frame (row, col) = game (y, x).  A plate is 2x2; the avatar is 2x2 and steps 2 px, so a cell
# one row above a plate still overlaps it.
TARGETS = [(55, 34), (57, 34), (59, 34), (60, 34), (58, 32), (57, 32), (58, 36), (57, 36)]
OUT: list = []
S = {"armed": False, "walked": 0, "i": 0, "phase": "route", "left": 0, "route": [], "pressed": 0,
     "prev": None, "click": None, "at": None, "panel": None}


def instrument(per_cell: int):
    from admorphiq.tools.base import frame_2d
    from admorphiq.tools.gantry import GantryCraneTool, rigid_translation

    orig = GantryCraneTool.propose

    def propose(self, frames, obs):
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl < 5:
            return orig(self, frames, obs)
        if not S["armed"]:
            out0 = orig(self, frames, obs)
            g0 = np.asarray(frame_2d(obs), dtype=int)
            geom0 = self._read(g0)
            if geom0 is not None and self._avatar >= 0:
                at0 = self._at(np.asarray(geom0["board"], dtype=int), self._avatar)
                if at0 and at0 in ((55, 34), (57, 34)):
                    S["armed"] = True
                    OUT.append({"ARMED_AT": list(at0)})
            return out0
        g = np.asarray(frame_2d(obs), dtype=int)
        geom = self._read(g)
        if geom is None or self._avatar < 0:
            return []
        board = np.asarray(geom["board"], dtype=int)
        here = self._at(board, self._avatar)
        strip = g[geom["top"]:geom["bot"] + 1, geom["panel"]:]
        ph = hashlib.md5(strip.tobytes()).hexdigest()[:8]
        # Resolve the press just made.
        if S["click"] is not None and S["prev"] is not None and S["prev"].shape == board.shape:
            slide = rigid_translation(S["prev"], board, {self._avatar, self._marker})
            OUT.append({"parked": list(S["at"]) if S["at"] else None,
                        "click": list(S["click"]),
                        "moved": slide is not None,
                        "delta": [int(slide[0][0]), int(slide[0][1])] if slide else None,
                        "changed": int((S["prev"] != board).sum()),
                        "panel": S["panel"]})
            S["click"] = None
        if S["i"] >= len(TARGETS):
            return []
        want = TARGETS[S["i"]]
        if S["phase"] == "route":
            if here == want:
                S["phase"], S["left"] = "press", per_cell * 4
                # ⛔ Ask the tool's OWN floor rule about the cell the avatar is demonstrably
                # standing in.  If it answers "not floor", the rule is wrong here and that — not
                # the board — is why `_plan_full` refuses to move inside the warp pocket.
                lay = self._world(board, self._config(), self._off)
                grid = self._standable(lay)
                win = [(y, x) for y in range(max(0, here[0] - 6), min(grid.shape[0], here[0] + 7))
                       for x in range(max(0, here[1] - 6), min(grid.shape[1], here[1] + 7))
                       if grid[y][x]]
                OUT.append({"ARRIVED": list(want), "panel": ph,
                            "standable_here": bool(grid[here[0]][here[1]])
                            if here[0] < grid.shape[0] and here[1] < grid.shape[1] else None,
                            "standable_in_window": len(win),
                            "floor_colour_here": int(board[here[0]][here[1]]),
                            "bg": int(self._bg), "not_floor": sorted(self._not_floor),
                            "visited": len(self._visited),
                            # ⛔ The claim "the planner cannot route inside the pocket" was first
                            # made from an arming cell in a DIFFERENT pocket. Ask it here, where
                            # the raw walk demonstrably works, before believing it.
                            "plan_len": {f"{t[0]},{t[1]}":
                                         len(self._plan_full(board, here, {t}))
                                         for t in ((55, 34), (59, 34), (57, 32), (57, 36))
                                         if t != here},
                            "deltas": {str(a): list(d) for a, d in sorted(self._deltas.items())},
                            "step": int(self._step()),
                            "settled": bool(self._settled_model()),
                            # Which of the avatar's own one-step neighbours the tool believes it
                            # may stand in.  If this is empty the BFS cannot leave the origin and
                            # every goal is "unreachable" for a reason that is not the goal.
                            "nbrs_in_grid": {str(a): bool(
                                0 <= here[0] + d[0] < grid.shape[0]
                                and 0 <= here[1] + d[1] < grid.shape[1]
                                and grid[here[0] + d[0]][here[1] + d[1]])
                                for a, d in sorted(self._deltas.items())}})
                return propose(self, frames, obs)
            # ⛔ Not `_plan_full`: from a warp destination the tool's own world model calls every
            # cell unreachable — including the one the avatar came from — because a cell it has
            # never stood on reads as the board's ground.  Rule 7y: ask the BOARD by doing.  The
            # walk is greedy along the deltas the tool measured for the four simple actions.
            if S["walked"] >= 24:
                OUT.append({"GAVE_UP": list(want), "at": list(here) if here else None,
                            "walked": S["walked"]})
                S["i"] += 1
                S["walked"] = 0
                return propose(self, frames, obs)
            best, bestd = None, None
            for a, d in sorted(self._deltas.items()):
                cand = abs(here[0] + d[0] - want[0]) + abs(here[1] + d[1] - want[1])
                if bestd is None or cand < bestd:
                    best, bestd = a, cand
            if best is None:
                OUT.append({"NO_DELTAS": list(want)})
                S["i"] += 1
                return propose(self, frames, obs)
            S["walked"] += 1
            self._pending, self._kindof = None, ""
            return [(best, None)]
        panel = self._panel_buttons(g, geom)
        drives = [c for c in panel if 30 <= c[0] <= 42 and 44 <= c[1] <= 56]
        if not drives or S["left"] <= 0:
            S["i"] += 1
            S["phase"], S["route"], S["walked"] = "route", [], 0
            return propose(self, frames, obs)
        pick = drives[(per_cell * 4 - S["left"]) % len(drives)]
        S["left"] -= 1
        S["prev"], S["click"], S["at"], S["panel"] = board.copy(), pick, here, ph
        self._pending, self._kindof = None, ""
        return [(6, (pick[1], pick[0]))]

    GantryCraneTool.propose = propose


def main():
    rep = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    per_cell = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    pmask = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    gmask = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    if pmask:
        from _dc22_percep import apply as apply_percep
        apply_percep(pmask)
    if gmask:
        from _dc22_gantryx import apply as apply_gantryx
        apply_gantryx(gmask)
    instrument(per_cell)
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"result": "NO_GAME"}), flush=True)
        return
    ei = envs[0]
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="unified",
                      max_actions=4000)
    hits = [r for r in OUT if r.get("moved")]
    print(json.dumps({"rep": rep, "pmask": pmask, "gmask": gmask, "levels_completed": int(res.get("levels_completed") or 0),
                      "total_actions": res.get("total_actions"),
                      "game_score": res.get("game_score"),
                      "records": len(OUT), "hits": len(hits),
                      "panels": sorted({r["panel"] for r in OUT if r.get("panel")}),
                      "armed": [r["ARMED_AT"] for r in OUT if "ARMED_AT" in r],
                      "arrived": [r["ARRIVED"] for r in OUT if "ARRIVED" in r],
                      "gave_up": [r["GAVE_UP"] for r in OUT if "GAVE_UP" in r]}),
          flush=True)
    for r in OUT[:200]:
        print(json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
