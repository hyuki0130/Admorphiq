"""What colours `gantry` calls avatar and marker on EVERY dc22 level.

Purpose: on level 6 the tool latches dead because neither rare colour can be located; the
question that decides the repair is whether the marker's colour is a property of the GAME
(carryable across levels) or of the level.  Plays the game with the generic tools and, on the
first frame of each level, asks a FRESH tool what it sees, then probes the four moves.

Varying parameter FIRST = unused.  Prints ONE JSON line per level.
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402
from arcengine import GameAction  # noqa: E402


class Watch:
    def __init__(self):
        self.inner = SE._make_agent("unified", game_id="dc22")
        self.seen = set()

    def is_done(self, frames, obs):
        return self.inner.is_done(frames, obs)

    def choose_action(self, frames, obs):
        lvl = int(obs.levels_completed)
        if lvl not in self.seen and hasattr(obs, "frame") and obs.frame:
            self.seen.add(lvl)
            self.dump(obs, lvl)
        return self.inner.choose_action(frames, obs)

    def dump(self, obs, lvl):
        from admorphiq.tools import phase as P
        from admorphiq.tools.gantry import GantryCraneTool
        g = np.asarray(obs.frame[-1], dtype=int)
        t = GantryCraneTool()
        t.reset()
        geom = t._read(g)
        rec = {"level_index_completed": lvl, "geom": geom is not None}
        if geom:
            b = geom["board"]
            rec["split"] = geom["panel"]
            rec["rare"] = list(geom["rare"])
            rec["side"] = geom["side"]
            rec["one_square"] = {int(c): P._one_square(b, int(c)) for c in geom["rare"]}
            rec["solid_block"] = {int(c): P._solid_block(b, int(c)) for c in geom["rare"]}
            from collections import Counter
            h = Counter(int(v) for row in b for v in row)
            rec["counts_of_rare"] = {int(c): h[int(c)] for c in geom["rare"]}
        print(json.dumps(rec, default=str), flush=True)


def main():
    _ = sys.argv[1] if len(sys.argv) > 1 else "0"
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments() if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    ei = envs[0]
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="watch",
                      max_actions=3000, adapter_factory=lambda: Watch())
    print(json.dumps({"levels_completed": res.get("levels_completed"),
                      "total_actions": res.get("total_actions")}), flush=True)


if __name__ == "__main__":
    main()
