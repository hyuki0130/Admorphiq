"""WHO spends s5i5's actions, level by level, on the live board and on its archived re-render.

⛔ WHY THIS EXISTS. `scripts/_s5i5_xfer.py` established that the live arm reproduces the banked
[13, 30, 47, 39, 32, 31] three times out of three and that the swivel tool never even sees level 4
— it begins at level 5. So the 39 -> 61 that `xfergate.sh` measures on level 4 belongs to some
OTHER tool, and naming the defect requires naming the owner first (rule 7b: a property of the
level is not a cause until it is measured on the level that costs the same).

This records, for both boards:

  * the OPENING FRAME of every level, hashed — if the two boards open level 4 pixel-identically,
    then nothing perceptual differs there and the divergence was carried in from an earlier level;
    if they differ, the difference is on the board and can be read off it;
  * which tool the harness had selected for each of the game's actions, tallied per level — the
    owner, and whether the arms disagree about it;
  * the harness's own re-decision count per level.

⛔ ATTRIBUTION IS FROM INSIDE THE LOOP, never by proximity (rule 7b): the level and the tool are
both read off the agent at the moment the action is chosen, not matched up afterwards.

  bash scripts/pfan.sh s5i5own scripts/_s5i5_owner.py 2 "" 2
      seed 1 -> the LIVE board, seed 2 -> the ARCHIVED re-render.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from collections import Counter
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

    import numpy as np
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness import loop as hloop
    from admorphiq.tools.base import levels_completed

    # ⛔ DUMP THE LAYER THE TOOL ACTUALLY READS. `frame_2d` returns layer 0 and every tool in this
    # family reads `_layers(obs)[-1]`; a dump of the wrong layer is an instrument answering a
    # different question than the one the finding rests on (rule 7z), and the first version of
    # this probe dumped layer 0 and disagreed with the tool's own marker counts because of it.
    from admorphiq.tools.telescope import _layers

    owners: Counter = Counter()
    opening: dict[int, str] = {}
    opening_grid: dict[int, list] = {}

    original = hloop.UnifiedAgent.choose_action

    def traced(self, frames, latest_frame):  # noqa: ANN001, ANN202
        act = original(self, frames, latest_frame)
        try:
            lvl = levels_completed(latest_frame)
            stack = _layers(latest_frame)
            if lvl not in opening and stack:
                arr = np.asarray(stack[-1], dtype=np.int16)
                opening[lvl] = hashlib.md5(arr.tobytes()).hexdigest()[:12]
                opening_grid[lvl] = arr.tolist()
            owners[(lvl, str(self._current))] += 1
        except Exception:  # noqa: BLE001
            owners[(-1, "instrument_failed")] += 1
        return act

    hloop.UnifiedAgent.choose_action = traced

    from score_efficiency import run_game

    arcade = Arcade(operation_mode=OperationMode.OFFLINE,
                    environments_dir=_env_dir(arm))
    envs = arcade.get_environments()
    info = envs[0]
    res = run_game(arcade, info.game_id, info.baseline_actions,
                   agent_name="unified", max_actions=BUDGET)

    # The full opening boards go to a file, not to stdout: they are 64x64 each and the fan's
    # stdout is a single JSON line.
    dump = Path(f"/tmp/s5i5_open_{arm}.json")
    dump.write_text(json.dumps({str(k): v for k, v in opening_grid.items()}))

    print(json.dumps({
        "seed": seed,
        "arm": arm,
        "game_score": res.get("game_score"),
        "actions": [lv["agent_actions"] for lv in res.get("per_level", [])],
        "opening_hash": {str(k): v for k, v in sorted(opening.items())},
        "owners": {f"lvl{k[0]}:{k[1]}": v for k, v in sorted(owners.items())},
        "dump": str(dump),
    }))


if __name__ == "__main__":
    main()
