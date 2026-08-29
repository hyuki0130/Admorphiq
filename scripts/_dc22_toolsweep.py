"""Every registered tool, alone, on dc22 level 6 — does ANY of them move it?

Purpose: rule 7b — sweep for an asset already present before building a new one. Plays to level 6
with the generic harness, then hands the board to ONE registered tool for a fixed budget and
reports whether the level went UP (rule 7f: direction named, number printed).

Varying parameter FIRST = 1-based tool index.  Prints ONE JSON line.
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402


class One:
    def __init__(self, idx, budget):
        self.inner = SE._make_agent("unified", game_id="dc22")
        self.idx = idx
        self.budget = budget
        self.used = 0
        self.tool = None
        self.name = "?"
        self.queue = []
        self.base = None
        self.best = None
        self.stopped = None

    def is_done(self, frames, obs):
        if obs.levels_completed >= 5:
            return self.used >= self.budget
        return self.inner.is_done(frames, obs)

    def choose_action(self, frames, obs):
        from admorphiq.types import ActionType, GameAction as AGA
        from admorphiq.adapter import AdmorphiqAdapter
        if obs.levels_completed < 5:
            return self.inner.choose_action(frames, obs)
        if self.tool is None:
            from admorphiq.harness.registry import default_tools
            tools = default_tools()
            if self.idx > len(tools):
                self.stopped = "index out of range"
                self.used = self.budget
                return AdmorphiqAdapter._convert_action(AGA.simple(ActionType(1)))
            self.tool = tools[self.idx - 1]
            self.name = getattr(self.tool, "name", type(self.tool).__name__)
            self.tool.reset()
            self.base = int(obs.levels_completed)
            self.best = self.base
        lvl = int(obs.levels_completed)
        if lvl > self.best:
            self.best = lvl
            print(json.dumps({"tool": self.name, "LEVEL_UP": True, "from": self.base,
                              "to": lvl, "after": self.used}), flush=True)
        self.used += 1
        if not self.queue:
            try:
                bid = float(self.tool.detect(frames, obs))
                steps = self.tool.propose(frames, obs) if bid > 0 else []
            except Exception as e:
                self.stopped = f"raised {type(e).__name__}: {e}"[:120]
                self.used = self.budget
                return AdmorphiqAdapter._convert_action(AGA.simple(ActionType(1)))
            self.queue = list(steps) if steps else []
            if not self.queue:
                self.stopped = f"empty at {self.used} (bid {bid:.2f})"
                self.used = self.budget
                return AdmorphiqAdapter._convert_action(AGA.simple(ActionType(1)))
        aid, xy = self.queue.pop(0)
        if xy is not None:
            return AdmorphiqAdapter._convert_action(AGA.coordinate(int(xy[0]), int(xy[1])))
        return AdmorphiqAdapter._convert_action(AGA.simple(ActionType(aid)))


def main():
    idx = int(sys.argv[1])
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments() if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    ei = envs[0]
    ag = One(idx, budget)
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="one",
                      max_actions=3000, adapter_factory=lambda: ag)
    print(json.dumps({"idx": idx, "tool": ag.name,
                      "level_from": ag.base, "level_to": ag.best,
                      "direction": ("UP" if (ag.best or 0) > (ag.base or 0) else "none"),
                      "actions_used": ag.used, "stopped": ag.stopped,
                      "levels_completed": res.get("levels_completed")}), flush=True)


if __name__ == "__main__":
    main()
