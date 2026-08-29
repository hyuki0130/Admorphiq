"""What the TELESCOPE reader sees on s5i5's level 4, live board versus archived re-render.

⛔ WHY TELESCOPE AND NOT SWIVEL. `scripts/_s5i5_owner.py` measured the owner from inside the loop:
every one of s5i5's first six levels is played by `swivel`, and `swivel.propose` hands the board
straight to a `TelescopeArmTool` delegate on any level with no one-way control. So the tool whose
action count moves 39 -> 61 on level 4 is the DELEGATE, and instrumenting `SwivelArmTool._begin`
(which the first probe did) sees nothing on that level at all.

⛔ WHAT IS BEING SEPARATED. `TelescopeArmTool._begin` decides which bars carry riders:

    pinned = [b for b in bars if tip_centre(...) in drawn]      # drawn = the rider MARKER CELLS
    riders = pinned if len(pinned) >= len(m.places) else bars   # else: EVERY bar is a candidate

and `_replan` then treats the rider->destination pairing as a hypothesis the board must knock
down, "so a wrong guess costs the clicks it asked for". Whether a rider is DRAWN is a z-order
fact — a rider painted under its bar is simply not in the frame. This probe records, per level and
per arm: how many rider markers were visible, how many bars got pinned, whether the fallback fired,
how many plans were spent and how many pairings the board refuted.

⭐ It records EVERY level, not level 4 alone, because the fallback also fires on a level whose
action count is IDENTICAL in both arms (rule 7b: contrast with the level that costs the same).

  bash scripts/pfan.sh s5i5tele scripts/_s5i5_tele.py 2 "" 2
      seed 1 -> the LIVE board, seed 2 -> the ARCHIVED re-render.
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
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    arm = "live" if seed == 1 else "arch"

    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import telescope as te
    from admorphiq.tools.base import levels_completed

    rows: list[dict] = []
    state: dict = {"level": -1}

    orig_begin = te.TelescopeArmTool._begin

    def begin(self, g):  # noqa: ANN001, ANN202
        widgets = te.read_widgets(g)
        ok = orig_begin(self, g)
        row = {"level": state["level"], "began": bool(ok), "widgets": len(widgets)}
        if ok and self._model is not None:
            marker = self._marker or 0
            m = te.read_markers(g, marker)
            boxes = [wd.box for wd in widgets]
            bars = te.anchored_bars(g, marker, boxes, self._pieces)
            drawn = set(m.movers) if m else set()
            pinned = [b for b in bars
                      if te.tip_centre(self._pieces[b[0]].box, b[1]) in drawn]
            row.update(
                pieces=len(self._pieces),
                bars=len(bars),
                places=len(m.places) if m else -1,
                # ⭐ movers = the rider markers the FRAME actually shows. A rider painted under
                # its bar is not here, and that is the whole render-dependence.
                movers=len(drawn),
                pinned=len(pinned),
                riders=len(self._model.riders),
                fellback=len(pinned) < (len(m.places) if m else 0),
                marker=int(marker),
                controls=len(self._controls),
            )
        rows.append(row)
        return ok

    te.TelescopeArmTool._begin = begin

    orig_replan = te.TelescopeArmTool._replan

    def replan(self):  # noqa: ANN001, ANN202
        out = orig_replan(self)
        rows.append({"level": state["level"], "replan": bool(out),
                     "plans": self._plans,
                     "refuted": len(self._model.refuted) if self._model else -1})
        return out

    te.TelescopeArmTool._replan = replan

    from admorphiq.harness import loop as hloop
    orig_choose = hloop.UnifiedAgent.choose_action

    def choose(self, frames, latest_frame):  # noqa: ANN001, ANN202
        state["level"] = levels_completed(latest_frame)
        return orig_choose(self, frames, latest_frame)

    hloop.UnifiedAgent.choose_action = choose

    from score_efficiency import run_game

    arcade = Arcade(operation_mode=OperationMode.OFFLINE,
                    environments_dir=_env_dir(arm))
    info = arcade.get_environments()[0]
    res = run_game(arcade, info.game_id, info.baseline_actions,
                   agent_name="unified", max_actions=BUDGET)

    # Collapse the replan stream to its last row per level: the running totals are cumulative.
    last: dict[int, dict] = {}
    begins = [r for r in rows if "began" in r]
    for r in rows:
        if "replan" in r:
            last[r["level"]] = r
    print(json.dumps({
        "seed": seed, "arm": arm,
        "game_score": res.get("game_score"),
        "actions": [lv["agent_actions"] for lv in res.get("per_level", [])],
        "begins": begins,
        "replans": [last[k] for k in sorted(last)],
    }))


if __name__ == "__main__":
    main()
