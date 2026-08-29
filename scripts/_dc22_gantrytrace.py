"""Drive `gantry` ALONE on dc22 level 6 and log where it stops.

Purpose: the wiki records dc22 retiring gantry through the EMPTY path, but "the route BFS found
no path" and "the tool never had a goal" are different faults with different repairs.  This plays
to level 6 with the generic tools, then hands the board to a FRESH GantryCraneTool and logs its
own internals every step: rare pair, avatar/marker colours, start and goal cells, panel, drives,
and which exit it takes.

Varying parameter FIRST = actions to give gantry at level 6.  Prints ONE JSON line.
Rule 7f: level numbers are printed as numbers, and any change names its direction.
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from arcengine import GameAction  # noqa: E402
import score_efficiency as SE  # noqa: E402


class Trace:
    def __init__(self, budget):
        self.inner = SE._make_agent("unified", game_id="dc22")
        self.tool = None
        self.budget = budget
        self.used = 0
        self.log = []
        self.queue = []
        self.start_level = None

    def is_done(self, frames, obs):
        if obs.levels_completed >= 5:
            return self.used >= self.budget
        return self.inner.is_done(frames, obs)

    def choose_action(self, frames, obs):
        if obs.levels_completed < 5:
            return self.inner.choose_action(frames, obs)
        from admorphiq.tools.gantry import GantryCraneTool
        if self.tool is None:
            self.tool = GantryCraneTool()
            self.tool.reset()
            self.start_level = obs.levels_completed
            print(f"[trace] handing level {obs.levels_completed} to a fresh gantry", flush=True)
        if obs.levels_completed != self.start_level:
            print(f"[trace] LEVEL MOVED {self.start_level} -> {obs.levels_completed} "
                  f"({'UP' if obs.levels_completed > self.start_level else 'DOWN'})", flush=True)
            self.start_level = obs.levels_completed
        self.used += 1
        t = self.tool
        if not self.queue:
            steps = t.propose(frames, obs)
            self.queue = list(steps) if steps else []
            g = np.asarray(obs.frame[-1], dtype=int)
            geom = t._read(g)
            start = t._at(geom["board"], t._avatar) if geom and t._avatar >= 0 else None
            goal = t._at(geom["board"], t._marker) if geom and t._marker >= 0 else None
            rec = {"n": self.used, "level": int(obs.levels_completed),
                   "rare": list(t._rare), "avatar": int(t._avatar), "marker": int(t._marker),
                   "start": list(start) if start else None, "goal": list(goal) if goal else None,
                   "dead": bool(t._dead), "retired": bool(t._retired),
                   "kinds": {str(k): v for k, v in t._kind.items()},
                   "drives": [list(c) for c in t._drives()],
                   "groups": len(t._groups), "warps": len(t._warps),
                   "edges": {str(k): {str(kk): (list(vv) if vv else None) for kk, vv in v.items()}
                             for k, v in t._edges.items()},
                   "proposed": len(self.queue), "objects": len(t._objects)}
            self.log.append(rec)
            if self.used <= 12 or self.used % 20 == 0 or t._retired or t._dead or not self.queue:
                print(json.dumps(rec), flush=True)
            if t._dead or t._retired or not self.queue:
                print(json.dumps({"VERDICT": "gantry stopped", **rec}), flush=True)
                self.used = self.budget
                return GameAction.ACTION1
        step = self.queue.pop(0)
        aid, xy = step
        from admorphiq.types import ActionType, GameAction as AGA
        from admorphiq.adapter import AdmorphiqAdapter
        if xy is not None:
            return AdmorphiqAdapter._convert_action(AGA.coordinate(int(xy[0]), int(xy[1])))
        return AdmorphiqAdapter._convert_action(AGA.simple(ActionType(aid)))


def main():
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments() if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"result": "NO_GAME"}), flush=True)
        return
    ei = envs[0]
    ag = Trace(budget)
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="trace",
                      max_actions=3000, adapter_factory=lambda: ag)
    print(json.dumps({"levels_completed": res.get("levels_completed"),
                      "total_actions": res.get("total_actions"),
                      "gantry_steps_logged": len(ag.log)}), flush=True)


if __name__ == "__main__":
    main()
