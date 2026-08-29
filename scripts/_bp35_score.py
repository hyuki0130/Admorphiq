"""Score bp35 with `score_efficiency.py`'s OWN `run_game`, and say whether the mirror rule fired.

⛔ Two things a per-level number alone cannot tell you, and both have cost a round on this game.
The first is rule 7g: a branch that CAN fire is not a branch that DOES. So `_mirror_lethal` is
wrapped and every join it makes is recorded with the two signatures it joined — a run that gains
nothing because the rule never ran reads identically to a run where the rule ran and was useless,
and they want opposite work. The second is that bp35's game total hides which board moved: a level
lost and retried is charged to the level it eventually clears, so the per-level column is printed
in full and compared against the gate baseline board by board.

Baseline (scripts/rounds/R101WA30/games/bp35.json, `--agent unified` @4000):
    L1 18/21 = 1.0   L2 87/48 = 0.3044   L3 45/44 = 0.9560   L4 23/38 = 1.0   L5 60/33 = 0.3025
    game 0.221988

Expected feedback: the joins list is non-empty and names the two spike histograms, AND no level's
agent_actions rises. A join that fires on some OTHER pair is the false-positive this rule is most
exposed to and is the thing to look at first.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import crag as cragmod

    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    # ⛔ One title per SEED, so a fan measures a different game per slot instead of the same one
    # N times. Repeating a title in the list is how determinism is checked.
    titles = (sys.argv[3] if len(sys.argv) > 3 else "bp35").split(",")
    title = titles[(seed - 1) % len(titles)]

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    _se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_se)

    joins: list[dict] = []
    faces: dict = {}
    mirror = cragmod.CragTool._mirror_join

    def spy(self):
        before = set(self._lethal)
        mirror(self)
        for added in self._lethal - before:
            joins.append({"joined": [list(t) for t in added],
                          "lethal_now": len(self._lethal)})
        # rule 7c: prove the table the rule reads is actually being filled.
        faces.clear()
        faces.update({str([list(t) for t in k]): len(v) for k, v in self._face.items()})

    cragmod.CragTool._mirror_join = spy

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    res = _se.run_game(arcade, info.game_id, info.baseline_actions,
                       agent_name="unified", max_actions=cap)
    print(json.dumps({
        "game": info.game_id,
        "levels_completed": res["levels_completed"],
        "greater_than_start": int(res["levels_completed"]) > 0,
        "total_actions": res["total_actions"],
        "game_score": res["game_score"],
        "per_level": res["per_level"],
        "mirror_joins": joins,
        "faces_per_signature": faces,
    }))


if __name__ == "__main__":
    main()
