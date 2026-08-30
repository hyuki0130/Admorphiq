"""Does the rider evidence telescope needs ever appear LATER in the level on the archived board?

Why this probe exists
---------------------
Rule 7cl measured WHEN each visibility-identity site reads:

    telescope.py:1183   5 evaluations, ALL FIVE at in-level action 0
    swivel.py:734       2 evaluations, BOTH at in-level action 0
    lattice_maze.py:484 187 evaluations, 178 of them mid-level      <- why its repair works

`lattice_maze`'s repair is dead reckoning — identity from a tracked position plus the known
displacement of the action just spent — and it works because 95% of its reads happen after an
action has been spent. telescope and swivel commit the rider set on the level's OPENING FRAME,
where no action has been spent and there is nothing to reckon from.

⛔ THAT IS NOT YET A PROOF THAT THE REPAIR IS IMPOSSIBLE. The read could be DEFERRED: telescope
probes every control anyway, spending actions it has already budgeted, so if the rider markers
become visible at any point during the level the commitment could simply wait for them. Whether
they do is a question about the BOARD, not about the tool, and only a run answers it (rule 7g).

What it measures
----------------
`read_markers` is wrapped for a whole s5i5 run on each board, recording per call the level, the
in-level action index, and how many movers / places the frame shows. The question is one number:
on the ARCHIVED board, does `movers` ever become non-empty within a level — above all within
level 4, the level that costs 22 extra actions?

Both controls
-------------
POSITIVE — the LIVE board must show movers non-empty at every level's opening frame (2 1 2 1 2,
per `scripts/_s5i5_tele.py`). An instrument reporting the live board empty has measured nothing.
NEGATIVE — the ARCHIVED board must show movers EMPTY at every level's opening frame, reproducing
the same banked reading from the other direction.

⚠️ `read_markers` is called by the DETECTOR as well as by the tool, and on frames from levels the
tool is not playing. Every call is recorded with its level and action index so the two can be told
apart rather than averaged.

    bash scripts/pfan.sh s5i5reveal scripts/_s5i5_reveal.py 1 "" 1
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

BUDGET = 4000
LIVE = _ROOT / "environment_files" / "s5i5"
ARCH = Path.home() / "admorphiq" / "environment_files_archive" / "s5i5"


def _env_dir(arm: str) -> str:
    src = LIVE if arm == "live" else ARCH
    tmp = Path(tempfile.mkdtemp(prefix=f"s5i5_{arm}_"))
    shutil.copytree(src, tmp / "s5i5")
    return str(tmp)


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness import loop as hloop
    from admorphiq.tools import telescope as te
    from admorphiq.tools.base import levels_completed

    ctx = {"level": -1, "act": 0}
    calls: list[tuple[int, int, int, int]] = []   # level, act, n_movers, n_places

    orig_rm = te.read_markers

    def read_markers(g, colour):  # noqa: ANN001, ANN202
        m = orig_rm(g, colour)
        calls.append((ctx["level"], ctx["act"],
                      0 if m is None else len(m.movers),
                      0 if m is None else len(m.places)))
        return m

    te.read_markers = read_markers

    orig_choose = hloop.UnifiedAgent.choose_action

    def choose(self, frames, latest_frame):  # noqa: ANN001, ANN202
        lvl = levels_completed(latest_frame)
        if lvl != ctx["level"]:
            ctx["level"], ctx["act"] = lvl, 0
        out = orig_choose(self, frames, latest_frame)
        ctx["act"] += 1
        return out

    hloop.UnifiedAgent.choose_action = choose

    from score_efficiency import run_game

    out: dict = {"arms": []}
    for arm in ("live", "arch"):
        calls.clear()
        ctx["level"], ctx["act"] = -1, 0
        arcade = Arcade(operation_mode=OperationMode.OFFLINE,
                        environments_dir=_env_dir(arm))
        info = arcade.get_environments()[0]
        res = run_game(arcade, info.game_id, info.baseline_actions,
                       agent_name="unified", max_actions=BUDGET)
        per: dict[int, dict] = {}
        for lvl, act, nm, np_ in calls:
            d = per.setdefault(lvl, {"calls": 0, "opening_movers": None,
                                     "max_movers": 0, "acts_with_movers": [],
                                     "max_places": 0})
            d["calls"] += 1
            if act == 0 and d["opening_movers"] is None:
                d["opening_movers"] = nm
            d["max_movers"] = max(d["max_movers"], nm)
            d["max_places"] = max(d["max_places"], np_)
            if nm and act not in d["acts_with_movers"]:
                d["acts_with_movers"].append(act)
        for d in per.values():
            d["acts_with_movers"] = sorted(d["acts_with_movers"])[:12]
        out["arms"].append({
            "arm": arm,
            "game_score": res.get("game_score"),
            "actions": [lv["agent_actions"] for lv in res.get("per_level", [])],
            "total_read_markers_calls": len(calls),
            "per_level": {str(k): v for k, v in sorted(per.items())},
        })
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
