"""Full dc22 game under each combination of the three perception repairs, PER LEVEL.

Purpose: dc22's five cleared levels are all at per-level 1.0 with no headroom, so a repair that
costs an action there loses more than the sixth level could gain.  The only honest test of a
perception change on this game is the per-level action count of the whole game, not the total.

Varying parameter FIRST = the repair mask (0..7): bit0=S unique-square tracker, bit1=C carried
pair, bit2=W whole-frame board with the panel's ground non-floor.
Prints ONE JSON line.  Rule 7f: `levels_completed` is printed as a number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import score_efficiency as SE  # noqa: E402
from _dc22_percep import apply as apply_percep  # noqa: E402


def main():
    mask = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    max_actions = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    if mask:
        apply_percep(mask)
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
    print(json.dumps({"mask": mask, "levels_completed": res.get("levels_completed"),
                      "win_levels": res.get("win_levels"),
                      "total_actions": res.get("total_actions"),
                      "game_score": res.get("game_score"),
                      "per_level": res.get("per_level")}), flush=True)


if __name__ == "__main__":
    main()
