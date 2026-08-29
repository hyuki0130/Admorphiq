"""Step onto the cells and LOOK: which dc22 level-6 controls appear and vanish with the avatar.

Purpose: the one wall left on dc22 level 6 is the crane.  The game's source says four drive buttons
are each visible only while the avatar stands on its own pressure plate, and the gate scaffolding
written for that is a NO-OP because no control has ever been OBSERVED to disappear.  Rule 7g says
the source says what is POSSIBLE and only a run says what HAPPENS, so this logs, on EVERY turn of
the last level, the avatar's cell and the exact set of panel buttons — and for every press, whether
the board answered with a rigid translation of one body.

Retirement is disabled for the measurement only: a tool that hands the level back after three
routeless turns cannot be asked what it would have seen on the fortieth.

Varying parameter FIRST = repetition index (deterministic); second = repair mask (default 7);
third = gantry-model mask (default 7); fourth = max actions.
Prints one JSON line per turn on the last level, then a summary line.
Rule 7f: `levels_completed` is printed as a number and any change names its direction.
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

STATE: dict = {"n": 0, "level": None, "rows": [], "slides": []}


def instrument():
    from admorphiq.tools.base import frame_2d
    from admorphiq.tools.gantry import GantryCraneTool, rigid_translation

    orig = GantryCraneTool.propose

    def propose(self, frames, obs):
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if STATE["level"] is not None and lvl != STATE["level"]:
            print(json.dumps({"LEVEL_MOVED": "UP" if lvl > STATE["level"] else "DOWN",
                              "from": STATE["level"], "to": lvl, "at": STATE["n"]}), flush=True)
        STATE["level"] = lvl
        steps = orig(self, frames, obs)
        if lvl < 5:
            return steps
        STATE["n"] += 1
        g = np.asarray(frame_2d(obs), dtype=int)
        geom = self._read(g)
        if geom is None:
            return steps
        start = self._at(geom["board"], self._avatar) if self._avatar >= 0 else None
        panel = self._panel_buttons(g, geom)
        STATE["rows"].append((STATE["n"], tuple(start) if start else None,
                              tuple(sorted(tuple(c) for c in panel))))
        return steps

    GantryCraneTool.propose = propose

    # ⛔ Retirement off for the measurement only.  Three routeless turns end the level for this
    # tool, and the question being asked is what it would see on a cell it has not reached yet.
    def _stall(self):
        self._stalls += 1
        return []

    GantryCraneTool._stall = _stall

    orig_resolve = GantryCraneTool._resolve_press

    def _resolve_press(self, geom, click):
        before = self._before
        board = geom["board"]
        slide = None
        if before is not None and before.shape == board.shape:
            got = rigid_translation(before, board, {self._avatar, self._marker})
            if got is not None:
                slide = (int(got[0][0]), int(got[0][1]), int(got[1].sum()))
        changed = int((before != board).sum()) if before is not None else -1
        if STATE["level"] == 5 and changed:
            STATE["slides"].append((STATE["n"], tuple(click),
                                    tuple(self._before_pos) if self._before_pos else None,
                                    slide if slide else changed))
        return orig_resolve(self, geom, click)

    GantryCraneTool._resolve_press = _resolve_press


def main():
    mask = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    gmask = int(sys.argv[3]) if len(sys.argv) > 3 else 7
    max_actions = int(sys.argv[4]) if len(sys.argv) > 4 else 4000
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
                      max_actions=max_actions)
    rows = STATE["rows"]
    # Every distinct panel set, with the avatar cells it was seen at.
    by_panel: dict = {}
    for _n, start, panel in rows:
        by_panel.setdefault(panel, set()).add(start)
    base = max(by_panel, key=lambda p: len(by_panel[p])) if by_panel else ()
    extra = {p: sorted(set(p) - set(base)) for p in by_panel if set(p) - set(base)}
    print(json.dumps({
        "turns": len(rows),
        "distinct_panels": len(by_panel),
        "modal_panel": [list(c) for c in base],
        "panels_with_extra_buttons": [
            {"extra": [list(c) for c in v],
             "at_cells": [list(c) for c in sorted(x for x in by_panel[p] if x)][:12],
             "turns": len(by_panel[p])}
            for p, v in extra.items()],
        "slides": [[n, list(c), list(p) if p else None, s] for n, c, p, s in STATE["slides"]],
        "levels_completed": res.get("levels_completed"),
        "total_actions": res.get("total_actions"),
        "game_score": res.get("game_score"),
    }), flush=True)


if __name__ == "__main__":
    main()
