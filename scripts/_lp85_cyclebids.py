"""cyclepress's bid on every sample game's opening frame — the selectivity check.

Purpose: a change to a tool is only safe once it is known which boards that tool takes.
Expected feedback: a bid of 0.00 everywhere but lp85 means this tool's edits cannot reach
another game; anything else names the games a full-25 gate must watch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools.cyclepress import CyclePressTool

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    out = {}
    for info in arcade.get_environments():
        title = (info.title or info.game_id).split("-")[0].lower()
        if title in out:
            continue
        env = arcade.make(info.game_id)
        obs = env.observation_space
        tool = CyclePressTool()
        try:
            out[title] = round(float(tool.detect([], obs)), 3)
        except Exception as exc:                        # a throw is a bid of nothing, loudly
            out[title] = f"ERR {exc}"
    print(json.dumps({"bids": {k: v for k, v in sorted(out.items()) }}))


if __name__ == "__main__":
    main()
