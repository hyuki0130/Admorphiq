"""dc22 level 6: does the PANEL change with the avatar's cell?  (the pressure-plate signal)

Where this comes from — three measurements that only fit together one way:

  * `_dc22_rail.py`: from avatar cell (49,28), each of the four crane drives (32,50) (36,46)
    (36,54) (40,50) is pressed 23 times and the board does not move ONE pixel, while (8,56) and
    (25,51) answer from that same cell.  The instrument is attached; the drives are refused.
  * `/tmp/pfan_dc22pt17.jsonl`: the same (32,50) slides a 28-pixel body from cell (55,34).
  * the panel ISLANDS are identical at both cells, so the button is drawn either way.

The game's `yuonzbouxb()` runs every step and, for every `njvd-rolo` plate the avatar overlaps,
makes the `buezna` controls carrying that plate's key VISIBLE + INTANGIBLE and hides all the
others.  `xodizggcom` skips invisible sprites, so a hidden control is a dead click at a cell that
still draws its housing.  If that is what is happening here, the panel's PIXELS must change when
the avatar steps onto a plate even though its island set does not.

This logs, for every turn of the last level, the avatar cell and the panel strip's pixels, and
reports which cells produce which panel.  A tool can only learn a plate if the frame shows one.

  arg 1 = repetition (fan slot).   arg 2 = max actions (default 4000).
  arg 3 = `_dc22_percep` mask, arg 4 = `_dc22_gantryx` mask — the previous agent's arms, needed
  because ONLY they take the avatar as far as the plate cluster at frame (55..61, 32..37).  The
  baseline tool never leaves rows 17-35, so a run without them cannot see a plate at all and its
  "the panel never changes" is a statement about where the avatar went, not about the mechanic.
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

SEEN: dict = {}
ORDER: list = []


def instrument():
    from admorphiq.tools.base import frame_2d
    from admorphiq.tools.gantry import GantryCraneTool

    orig = GantryCraneTool.propose

    def propose(self, frames, obs):
        out = orig(self, frames, obs)
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl < 5:
            return out
        g = np.asarray(frame_2d(obs), dtype=int)
        geom = self._read(g)
        if geom is None or self._avatar < 0:
            return out
        here = self._at(geom["board"], self._avatar)
        strip = g[geom["top"]:geom["bot"] + 1, geom["panel"]:]
        h = hashlib.md5(strip.tobytes()).hexdigest()[:8]
        rec = SEEN.setdefault(h, {"cells": set(), "n": 0,
                                  "nonbg": int((strip != geom["bg"]).sum())})
        rec["n"] += 1
        rec["cells"].add(tuple(here) if here else None)
        if not ORDER or ORDER[-1][0] != h:
            ORDER.append((h, tuple(here) if here else None))
        return out

    GantryCraneTool.propose = propose


def main():
    rep = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    max_actions = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    pmask = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    gmask = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    if pmask:
        from _dc22_percep import apply as apply_percep
        apply_percep(pmask)
    if gmask:
        from _dc22_gantryx import apply as apply_gantryx
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
    print(json.dumps({"rep": rep, "levels_completed": int(res.get("levels_completed") or 0),
                      "total_actions": res.get("total_actions"),
                      "game_score": res.get("game_score"),
                      "pmask": pmask, "gmask": gmask,
                      "distinct_panels": len(SEEN), "switches": len(ORDER),
                      "panels": {k: {"n": v["n"], "nonbg": v["nonbg"],
                                     "cells": sorted(str(c) for c in v["cells"])[:12],
                                     "ncells": len(v["cells"])}
                                 for k, v in SEEN.items()}}), flush=True)
    for h, c in ORDER[:80]:
        print(json.dumps({"panel": h, "at": list(c) if c else None}), flush=True)


if __name__ == "__main__":
    main()
