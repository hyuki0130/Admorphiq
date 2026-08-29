"""Change the ONE render fact and watch s5i5 level 4 go back to 39 actions.

⛔ WHAT IS ALREADY MEASURED (`scripts/_s5i5_tele.py`, both arms, and `_s5i5_xfer.py` 3/3 each way,
so neither number is a draw):

    live  [13, 30, 47, 39, 32, 31]   drawn rider markers per level: 2 1 2 1 2   fellback NEVER
    arch  [13, 30, 47, 61, 32, 31]   drawn rider markers per level: 0 0 0 0 0   fellback ALWAYS
                                     candidate bars when it falls back: 2 4 4 9 5
                                     plans / pairings refuted:          1/0 2/1 1/0 9/4 2/0

`TelescopeArmTool._begin` decides which bars carry riders from whether the rider's MARKER CELLS
survive into the frame, and the archived serialization lists every rider before the bar it rides,
so every one of them is painted over. The tool then guesses among ALL bars and pays for the wrong
guesses in clicks it has already spent. Four levels fall back and cost nothing; the fifth has NINE
candidate bars for one destination and costs twenty-two actions.

⛔ THAT IS A CORRELATION UNTIL THE FACT IS CHANGED. This probe changes exactly it and nothing else:
on the archived board the rider cells the LIVE board draws are put back into `read_markers`'s
`movers` FOR THE DURATION OF `_begin` ONLY — the same boards, the same geometry, the same planner,
the same budget, with the rider evidence restored and nothing else touched. The restriction to
`_begin` is deliberate: `_agrees` checks drawn movers against the model's predictions every action,
so injecting there would be feeding the verifier its own answer.

Three runs in ONE process, so the arms cannot disagree about anything but the injection:

    1. live,  recording where the drawn riders sit at each level's first frame
    2. arch,  untouched          -> the control, must reproduce 61
    3. arch,  riders injected    -> if the defect is named right, level 4 returns to 39

  bash scripts/pfan.sh s5i5oracle scripts/_s5i5_oracle.py 1 "" 1
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

    state = {"level": -1, "mode": "off"}
    recorded: dict[int, list] = {}
    inject: dict = {"cells": None}
    trace: list[dict] = []

    orig_rm = te.read_markers

    def read_markers(g, colour):  # noqa: ANN001, ANN202
        m = orig_rm(g, colour)
        if inject["cells"] and m is not None:
            return te.Markers(m.colour,
                              tuple(sorted(set(m.movers) | {tuple(c) for c in inject["cells"]})),
                              m.places)
        return m

    te.read_markers = read_markers

    orig_begin = te.TelescopeArmTool._begin

    def begin(self, g):  # noqa: ANN001, ANN202
        lvl = state["level"]
        inject["cells"] = recorded.get(lvl) if state["mode"] == "oracle" else None
        try:
            ok = orig_begin(self, g)
        finally:
            cells = inject["cells"]
            inject["cells"] = None
        if ok and self._model is not None:
            tips = [list(te.tip_centre(self._pieces[h].box, e)) for h, e in self._model.riders]
            if state["mode"] == "record":
                recorded[lvl] = tips
            trace.append({"mode": state["mode"], "level": lvl,
                          "riders": len(self._model.riders),
                          "injected": len(cells or []), "tips": tips})
        return ok

    te.TelescopeArmTool._begin = begin

    orig_choose = hloop.UnifiedAgent.choose_action

    def choose(self, frames, latest_frame):  # noqa: ANN001, ANN202
        state["level"] = levels_completed(latest_frame)
        return orig_choose(self, frames, latest_frame)

    hloop.UnifiedAgent.choose_action = choose

    from score_efficiency import run_game

    out: dict = {"runs": []}
    for arm, mode in (("live", "record"), ("arch", "off"), ("arch", "oracle")):
        state["mode"] = mode
        state["level"] = -1
        arcade = Arcade(operation_mode=OperationMode.OFFLINE,
                        environments_dir=_env_dir(arm))
        info = arcade.get_environments()[0]
        res = run_game(arcade, info.game_id, info.baseline_actions,
                       agent_name="unified", max_actions=BUDGET)
        out["runs"].append({
            "arm": arm, "mode": mode,
            "game_score": res.get("game_score"),
            "actions": [lv["agent_actions"] for lv in res.get("per_level", [])],
        })
    out["trace"] = trace
    print(json.dumps(out))


if __name__ == "__main__":
    main()
