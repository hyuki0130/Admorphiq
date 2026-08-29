"""Why does s5i5 level 4 cost 39 actions on the live board and 61 on its archived re-render?

⛔ WHAT THIS IS FOR. `scripts/xfergate.sh` (rule 7by) substitutes every archived re-render for its
live game and scores the full 25: twenty-four of twenty-five are action-for-action identical, and
exactly one level of one game moves — s5i5 L4, 39 -> 61. This probe runs THAT ONE GAME on both
boards, several times each, with the swivel tool's board-reading instrumented, so the three
candidate explanations are separated in one fan instead of one at a time (rule 7h):

  H1  nondeterminism — the count varies run to run on EITHER board, and there is no defect.
  H2  the rider set — `SwivelArmTool._begin` decides which bars carry riders from whether the
      rider MARKER IS DRAWN, and a rider painted under its bar is invisible. When fewer riders
      are visible than there are destinations it falls back to "every bar might be a rider" and
      pays for the wrong guesses.
  H3  something else in the reading — bar count, destination count, marker colour, widget order.

Every arm reports the readings for EVERY level, not only level 4, because a property of the level
that costs more is not a cause until the levels that cost the same lack it (rule 7b: contrast with
the level that clears).

⛔ It runs `run_game` from `scripts/score_efficiency.py` ITSELF rather than a hand-rolled loop, so
the action counts are the gate's own (rule 7aj #1), and it reproduces the banked numbers before
anything is concluded from it (rule 7aj #2).

  bash scripts/pfan.sh s5i5xfer scripts/_s5i5_xfer.py 6 "" 6
      seeds 1-3 -> the LIVE board, seeds 4-6 -> the ARCHIVED re-render.
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
# ⚠️ The archive is NOT in the repo and NOT linked into a pfan snapshot; it lives beside the
# shared tree on the box, which is where xfergate.sh reads it from too.
ARCH = Path.home() / "admorphiq" / "environment_files_archive" / "s5i5"


def _env_dir(arm: str) -> str:
    """A directory holding ONE s5i5 version, so the loader cannot pick the other.

    ⛔ Two version dirs under one game share a `game_id` and the loader keeps whichever `rglob`
    yields first (rule 7bu) — the artefact then cannot say which board it scored. Isolating the
    version in its own tree is the only thing that can.
    """
    src = LIVE if arm == "live" else ARCH
    tmp = Path(tempfile.mkdtemp(prefix=f"s5i5_{arm}_"))
    shutil.copytree(src, tmp / "s5i5")
    return str(tmp)


def _instrument(readings: list[dict]) -> None:
    """Record what `_begin` read off each level's opening frame, without changing it."""
    from admorphiq.tools import swivel as sw

    original = sw.SwivelArmTool._begin

    def traced(self, g):  # noqa: ANN001, ANN202
        ok = original(self, g)
        row: dict = {"level": self._level, "began": bool(ok)}
        if ok and self._model is not None and self._cfg is not None:
            marks = sw.read_markers(g, self._marker or 0)
            drawn = set(marks.movers) if marks else set()
            pinned = [i for i in range(len(self._cfg.bars))
                      if sw.rider_at(self._cfg, i) in drawn]
            row.update(
                bars=len(self._cfg.bars),
                places=len(self._model.places),
                # movers = marker cells NOT part of a destination ring: the drawn riders.
                movers=len(drawn),
                pinned=len(pinned),
                riders=len(self._model.riders),
                # ⭐ THE FIELD THE WHOLE QUESTION TURNS ON. False = the rider set is the measured
                # one; True = the reader fell back to "every bar is a candidate".
                fellback=len(pinned) < len(self._model.places),
                marker=int(self._marker or -1),
                controls=len(self._controls),
                freight=len(self._cfg.freight),
            )
        readings.append(row)
        return ok

    sw.SwivelArmTool._begin = traced

    # How many rider->destination pairings the board refuted before one planned. A refuted
    # pairing is not free: its plan was EXECUTED first.
    orig_replan = sw.SwivelArmTool._replan

    def traced_replan(self):  # noqa: ANN001, ANN202
        before = len(self._model.refuted) if self._model is not None else 0
        out = orig_replan(self)
        after = len(self._model.refuted) if self._model is not None else 0
        readings.append({"level": self._level, "replan": bool(out),
                         "refuted_before": before, "refuted_after": after})
        return out

    sw.SwivelArmTool._replan = traced_replan


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    arm = "live" if seed <= 3 else "arch"

    from arc_agi import Arcade, OperationMode

    readings: list[dict] = []
    _instrument(readings)
    from score_efficiency import run_game

    arcade = Arcade(operation_mode=OperationMode.OFFLINE,
                    environments_dir=_env_dir(arm))
    envs = arcade.get_environments()
    if len(envs) != 1:
        print(json.dumps({"seed": seed, "arm": arm,
                          "error": f"{len(envs)} environments, expected 1"}))
        return
    info = envs[0]
    res = run_game(arcade, info.game_id, info.baseline_actions,
                   agent_name="unified", max_actions=BUDGET)
    print(json.dumps({
        "seed": seed,
        "arm": arm,
        "game_score": res.get("game_score"),
        "levels": res.get("levels_completed"),
        "actions": [lv["agent_actions"] for lv in res.get("per_level", [])],
        "readings": readings,
    }))


if __name__ == "__main__":
    main()
