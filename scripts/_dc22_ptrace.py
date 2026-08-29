"""Play the WHOLE dc22 game with the perception repairs and log gantry's own state on level 6.

Purpose: the carried piece pair is a fact the tool accumulates over the levels that clear, so a
tool handed the last level cold does not have it — a fresh-tool trace answers a different question
from the one the harness asks.  This wraps `GantryCraneTool.propose` on the harness's OWN instance
and logs, on the last level only, what the tool sees and what it decides.

Varying parameter FIRST = repetition index (deterministic); second = repair mask (default 7);
third = gantry-model mask (0 = off); fourth = max actions.
Prints one JSON line per logged step, then the game's own result line.
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

STATE = {"n": 0, "level": None}


def instrument():
    from admorphiq.tools.base import frame_2d
    from admorphiq.tools.gantry import GantryCraneTool

    orig = GantryCraneTool.propose

    def propose(self, frames, obs):
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if STATE["level"] is not None and lvl != STATE["level"]:
            print(json.dumps({"LEVEL_MOVED": "UP" if lvl > STATE["level"] else "DOWN",
                              "from": STATE["level"], "to": lvl}), flush=True)
        STATE["level"] = lvl
        was_ret, was_dead = bool(self._retired), bool(self._dead)
        steps = orig(self, frames, obs)
        if lvl >= 5 and (self._retired and not was_ret) or (self._dead and not was_dead):
            g0 = np.asarray(frame_2d(obs), dtype=int)
            geom0 = self._read(g0)
            print(json.dumps({
                "RETIRED_AT": STATE["n"] + 1,
                "reason_stalls": int(self._stalls),
                "geom_none": geom0 is None,
                "start": (list(self._at(geom0["board"], self._avatar) or [])
                          if geom0 is not None and self._avatar >= 0 else None),
                "goal": (list(self._at(geom0["board"], self._marker) or [])
                         if geom0 is not None and self._marker >= 0 else None),
                "dead": bool(self._dead), "retired": bool(self._retired),
                "slid": {str(len(k)): {f"{c[0]},{c[1]}": list(d) for c, d in v.items()}
                         for k, v in self._slid.items()},
                "shape_known": self._shape is not None,
                "slidcell": [list(c) for c in getattr(self, "_slidcell", [])],
            }), flush=True)
        if lvl < 5:
            return steps
        STATE["n"] += 1
        n = STATE["n"]
        if n > 1 and n % 10 and not (self._dead or self._retired) and steps:
            return steps
        g = np.asarray(frame_2d(obs), dtype=int)
        geom = self._read(g)
        start = goal = None
        board_w = None
        why = None
        if geom is None:
            from collections import Counter

            from _dc22_percep import squares_of_side

            from admorphiq.tools import phase as P
            top, bot = P._chrome_span(g)
            split = P._split_columns(g, top, bot)
            why = {"span": [int(top), int(bot)], "split": list(split) if split else None}
            if split:
                left = g[top:bot + 1, 0:split[0]]
                whole = g[top:bot + 1, :]
                why["pieces_left"] = list(P._pieces(left) or [])
                for c in (self._avatar, self._marker):
                    why[f"sq_left_{c}"] = squares_of_side(left, c, self._side or 2)
                    why[f"sq_whole_{c}"] = squares_of_side(whole, c, self._side or 2)
                why["hist_left"] = {str(k): int(v) for k, v in
                                    Counter(int(v) for v in left.ravel()).items()
                                    if k in (self._avatar, self._marker)}
        if geom is not None:
            board_w = int(np.asarray(geom["board"]).shape[1])
            if self._avatar >= 0:
                start = self._at(geom["board"], self._avatar)
                goal = self._at(geom["board"], self._marker)
        print(json.dumps({
            "n": n, "level": lvl, "carry": list(getattr(self, "_carry", None) or []),
            "rare": list(self._rare), "avatar": int(self._avatar), "marker": int(self._marker),
            "board_w": board_w, "start": list(start) if start else None,
            "goal": list(goal) if goal else None,
            "dead": bool(self._dead), "retired": bool(self._retired),
            "kinds": {f"{k[0]},{k[1]}": v for k, v in sorted(self._kind.items())},
            "off": list(self._off), "drives": len(self._drives()),
            "groups": [[list(gr["click"]), gr.get("period")] for gr in self._groups],
            "warps": {f"{k[0][0]},{k[0][1]}|{k[1][0]},{k[1][1]}": str(v)
                      for k, v in self._warps.items()},
            "objects": len(self._objects), "visited": len(self._visited),
            "notfloor": sorted(self._not_floor), "planned": len(self._steps),
            "proposed": len(steps), "why": why,
            "portals": ([list(c) for c in sorted(self._portals(geom["board"]))]
                        if geom is not None else None),
            "warp_tested": len(self._warp_tested),
            "gate": {f"{k[0]},{k[1]}": len(v) for k, v in sorted(getattr(self, "_gate", {}).items())},
            "hidden": [list(c) for c in sorted(getattr(self, "_hidden", set()))],
            "aims": int(getattr(self, "_aims", 0)),
            "start_is_portal": (bool(start and start in self._portals(geom["board"])))
            if geom is not None else None,
            "panel": ([list(c) for c in self._panel_buttons(g, geom)]
                      if geom is not None else None),
        }), flush=True)
        return steps

    GantryCraneTool.propose = propose


def main():
    mask = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    gmask = int(sys.argv[3]) if len(sys.argv) > 3 else 0
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
    print(json.dumps({"mask": mask, "gmask": gmask, "levels_completed": res.get("levels_completed"),
                      "total_actions": res.get("total_actions"),
                      "game_score": res.get("game_score"),
                      "gantry_turns_on_last": STATE["n"]}), flush=True)
    from _dc22_gantryx import PRESSES
    seen = {}
    for click, pos, landed, key in PRESSES:
        seen.setdefault((click, pos), []).append((key, landed, landed != pos))
    print(json.dumps({"presses": len(PRESSES),
                      "moved": [[list(k[0]), list(k[1]), str(v)]
                                for k, v in sorted(seen.items()) if any(m for _, _, m in v)],
                      "pairs": [[list(k[0]), list(k[1]), len(v)] for k, v in sorted(seen.items())]}),
          flush=True)


if __name__ == "__main__":
    main()
