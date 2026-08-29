"""dc22 FULL GAME with an oracle tail: generic tools for levels 1-5, the measured
level-6 plan for the last level.  Reports per-level actions and the RHAE game score.

Purpose: dc22 is the largest single target on the board (+0.0114 — its next level is its
last).  This measures what the game scores IF level 6 is cleared, and proves the level-6
plan executes through the SHIPPED harness path (Arcade -> FrameData -> GameAction), not
only against the game module.

Varying parameter FIRST = max actions.  Prints ONE JSON line.
Rule 7f: level changes are reported with DIRECTION and the resulting level number.
"""
import sys, json, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arcengine import GameAction  # noqa: E402
import score_efficiency as SE  # noqa: E402

PLAN_FILE = os.environ.get("DC22_PLAN", "scripts/_dc22_plan.json")


class OraclePlanAgent:
    """Generic tools until level 6, then the fixed measured plan."""

    def __init__(self, plan):
        self.inner = SE._make_agent("unified", game_id="dc22")
        self.plan = plan
        self.i = 0
        self.coords = None
        self.armed = False

    def is_done(self, frames, obs):
        if obs.levels_completed >= 5:
            return self.i >= len(self.plan)
        return self.inner.is_done(frames, obs)

    def choose_action(self, frames, obs):
        if obs.levels_completed >= 5:
            if not self.armed:
                self.armed = True
                print(f"  [oracle] armed at level {obs.levels_completed}", flush=True)
            lab = self.plan[self.i]
            self.i += 1
            if lab.startswith("A"):
                return getattr(GameAction, "ACTION" + lab[1])
            a = GameAction.ACTION6
            x, y = COORDS[lab]
            a.set_data({"x": x, "y": y})
            return a
        return self.inner.choose_action(frames, obs)


# Click coordinates are FIXED board positions of the level-6 buttons, read once from the
# level and recorded here so the runtime path uses no privileged access at play time.
COORDS = {
    "click_f": (53, 5),
    "click_c": (48, 23),
    "click_d": (49, 46),
    "crane_up": (49, 31),
    "crane_dowlja": (49, 39),
    "crane_lersnf": (45, 35),
    "crane_riidpd": (53, 35),
    "crane_grab": (47, 17),
}


def main():
    max_actions = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
    plan = json.load(open(PLAN_FILE))["plan"]
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments() if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"result": "NO_GAME", "hint": "set ENVIRONMENTS_DIR"}), flush=True)
        return
    ei = envs[0]
    gid, base = ei.game_id, ei.baseline_actions
    print(f"game {gid} baseline={base}", flush=True)
    res = SE.run_game(arcade, gid, base, agent_name="oracle",
                      max_actions=max_actions,
                      adapter_factory=lambda: OraclePlanAgent(plan))
    print(json.dumps(res), flush=True)


if __name__ == "__main__":
    main()
