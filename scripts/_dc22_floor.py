"""dc22: the floor rule condemns the very tiles the crane's plates are drawn on.

The chain, each link measured or read off the level's own data:

  1. `_learn_refusal` condemns COLOURS: at the plate cluster `_not_floor` holds `[0, 5]`.
  2. every `njvd-rolo` plate on level 6 is a 2x2 sprite drawn `[[1,0],[0,C]]` (C = 12/15/14/10) —
     it CONTAINS colour 0.
  3. `_standable` refuses any avatar-sized window carrying one condemned pixel, so every window
     overlapping a plate is "not floor".
  4. MEASURED (`_dc22_plateverify.py`): standing at (57,34), in the middle of the plate cluster,
     the tool believes NONE of its four one-step neighbours is standable — `nbrs_in_grid` all
     false — and `_plan_full` returns a plan of length 0 to every one of the four plates, from
     every one of the five cells, while a raw two-move walk between exactly those cells succeeds
     every time and each plate then enables exactly its own drive.
  5. so the crane's four drives are unreachable BY PLAN, and the crane is never learned.

The repair under test is the repo's own "observation trumps inference": a cell the avatar HAS
STOOD IN is floor, whatever colour it is drawn in.  `_grid` unions `self._visited`, `_blocked`
still subtracts.

  arg 1 = repetition.  arg 2 = 1 to apply the repair, 0 for the control arm.
  arg 3 = `_dc22_percep` mask, arg 4 = `_dc22_gantryx` mask.
Rule 7x: the scorer's own `run_game` drives it.  Rule 7f: the level count prints as a number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import score_efficiency as SE  # noqa: E402


def apply_repair():
    from admorphiq.tools.gantry import GantryCraneTool

    orig = GantryCraneTool._grid

    def _grid(self, cache, board, pcfg, off):
        got = orig(self, cache, board, pcfg, off)
        key = ("visited", pcfg, off, len(self._visited))
        cached = cache.get(key)
        if cached is not None:
            return cached
        h, w = board.shape
        extra = {c for c in self._visited if 0 <= c[0] < h and 0 <= c[1] < w}
        out = set(got) | extra
        for cell, _sig in self._blocked:
            out.discard(cell) if cell in extra and cell not in got else None
        cache[key] = out
        return out

    GantryCraneTool._grid = _grid


def main():
    rep = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    repair = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    pmask = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    gmask = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    if pmask:
        from _dc22_percep import apply as apply_percep
        apply_percep(pmask)
    if gmask:
        from _dc22_gantryx import apply as apply_gantryx
        apply_gantryx(gmask)
    if repair:
        apply_repair()
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
    print(json.dumps({"rep": rep, "repair": repair, "pmask": pmask, "gmask": gmask,
                      "levels_completed": int(res.get("levels_completed") or 0),
                      "total_actions": res.get("total_actions"),
                      "game_score": res.get("game_score"),
                      "per_level": res.get("per_level")}), flush=True)


if __name__ == "__main__":
    main()
