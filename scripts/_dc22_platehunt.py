"""Press every INERT control from every cell the tool reaches, and log where one moves a body.

Purpose: dc22 level 6's last wall is the crane.  The gate scaffolding written for it looks for a
control that DISAPPEARS, and the measurement says no control ever does — 230 turns, four distinct
panel sets, and the only one that ever changes is a ring unlocked permanently by a key.  The four
crane drives are DRAWN THE WHOLE TIME at (32,50) (36,46) (36,54) (40,50), arranged as a D-pad, and
they are INERT rather than invisible: the game makes them act only while the avatar overlaps their
pressure plate.  So the signal is not visibility, it is "inert from here, alive from there".

Rule 7g: do not reason about which cell is a plate — press from every cell and look.

Varying parameter FIRST = repetition index (deterministic); second = repair mask (default 7);
third = gantry-model mask (default 7); fourth = presses to spend hunting.
Prints one JSON line per (control, cell) that MOVES something, then a summary.
Rule 7f: any level change names its direction and the resulting number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402
from _dc22_gantryx import apply as apply_gantryx  # noqa: E402
from _dc22_percep import apply as apply_percep  # noqa: E402

STATE: dict = {"n": 0, "level": None, "hits": [], "tried": set(), "budget": 200}


def instrument():
    from admorphiq.tools.gantry import GantryCraneTool, rigid_translation

    orig_act = GantryCraneTool._act

    def _act(self, geom, start, goal, panel):
        # ⛔ Press an inert control from THIS cell before doing anything else.  The board's four
        # crane drives are visible everywhere and act from one cell each; a probe that only fires
        # where the tool happens to have no plan cannot enumerate cells.
        if STATE["n"] < STATE["budget"]:
            for click in panel:
                if self._kind.get(click) not in (None, "idle"):
                    continue
                if (click, start) in STATE["tried"]:
                    continue
                STATE["tried"].add((click, start))
                STATE["n"] += 1
                self._steps = []
                return [self._press(geom, start, click, "probe")]
        return orig_act(self, geom, start, goal, panel)

    GantryCraneTool._act = _act

    def _stall(self):
        self._stalls += 1
        return []

    GantryCraneTool._stall = _stall

    orig_resolve = GantryCraneTool._resolve_press

    def _resolve_press(self, geom, click):
        before = self._before
        board = geom["board"]
        lvl = STATE["level"]
        if lvl == 5 and before is not None and before.shape == board.shape:
            got = rigid_translation(before, board, {self._avatar, self._marker})
            changed = int((before != board).sum())
            if got is not None or changed:
                rec = {"click": list(click),
                       "from": list(self._before_pos) if self._before_pos else None,
                       "changed_px": changed,
                       "slide": [int(got[0][0]), int(got[0][1]), int(got[1].sum())] if got else None}
                STATE["hits"].append(rec)
                print(json.dumps(rec), flush=True)
        return orig_resolve(self, geom, click)

    GantryCraneTool._resolve_press = _resolve_press

    orig_propose = GantryCraneTool.propose

    def propose(self, frames, obs):
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if STATE["level"] is not None and lvl != STATE["level"]:
            print(json.dumps({"LEVEL_MOVED": "UP" if lvl > STATE["level"] else "DOWN",
                              "from": STATE["level"], "to": lvl}), flush=True)
        STATE["level"] = lvl
        return orig_propose(self, frames, obs)

    GantryCraneTool.propose = propose


def main():
    mask = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    gmask = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    STATE["budget"] = int(sys.argv[4]) if len(sys.argv) > 4 else 200
    if mask:
        apply_percep(mask)
    if gmask:
        apply_gantryx(gmask)
    instrument()
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
    slides = [h for h in STATE["hits"] if h["slide"]]
    print(json.dumps({"probe_presses": STATE["n"], "answered": len(STATE["hits"]),
                      "slid": len(slides), "slides": slides[:30],
                      "levels_completed": res.get("levels_completed"),
                      "total_actions": res.get("total_actions"),
                      "game_score": res.get("game_score")}), flush=True)
    _ = np


if __name__ == "__main__":
    main()
