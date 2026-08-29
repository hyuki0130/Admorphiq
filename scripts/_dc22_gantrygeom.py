"""What `gantry` actually SEES on dc22 level 6.

Purpose: dc22's last level retires gantry through the EMPTY path (`gantry:501`, the route BFS
finds no path).  This plays the game with the generic tools until level 6 and then dumps the
tool's own perception of that frame: the board/panel split, the panel buttons, the marker and
avatar it resolves, and whether the goal cell falls inside the board it routes over.

Varying parameter FIRST = max actions.  Prints ONE JSON line.
"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from arcengine import GameAction  # noqa: E402
import score_efficiency as SE  # noqa: E402


class Peek:
    """Generic tools until level 6, then dump gantry's perception and stop."""

    def __init__(self):
        self.inner = SE._make_agent("unified", game_id="dc22")
        self.done = False
        self.report = {}

    def is_done(self, frames, obs):
        return self.done or self.inner.is_done(frames, obs)

    def choose_action(self, frames, obs):
        if obs.levels_completed >= 5 and not self.done:
            self.dump(obs)
            self.done = True
            return GameAction.ACTION5 if hasattr(GameAction, "ACTION5") else GameAction.RESET
        return self.inner.choose_action(frames, obs)

    def dump(self, obs):
        from admorphiq.tools.gantry import GantryCraneTool as GantryTool
        from admorphiq.tools import phase as P
        g = np.asarray(obs.frame[-1], dtype=int)
        top, bot = P._chrome_span(g)
        split = P._split_columns(g, top, bot)
        t = GantryTool()
        t.reset()
        geom = t._read(g)
        rep = {"frame_shape": list(g.shape), "chrome_span": [int(top), int(bot)],
               "split": list(split) if split else None,
               "geom": None}
        if geom:
            board = geom["board"]
            rep["geom"] = {"top": geom["top"], "bot": geom["bot"], "panel": geom["panel"],
                           "board_shape": list(np.asarray(board).shape),
                           "bg": geom["bg"], "side": geom["side"], "rare": list(geom["rare"])}
            rep["panel_buttons"] = [list(c) for c in t._panel_buttons(g, geom)]
            # where is every colour-11 (goal-coloured) block?
            cells = np.argwhere(g == 11)
            rep["colour11_cells"] = [[int(a), int(b)] for a, b in cells][:40]
            rep["colour11_in_board"] = int(sum(1 for a, b in cells if b < geom["panel"]))
            rep["colour11_in_panel"] = int(sum(1 for a, b in cells if b >= geom["panel"]))
        rep["detect"] = float(t.detect([], obs))
        self.report = rep
        print(json.dumps({"gantry_view": rep}), flush=True)


def main():
    max_actions = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments() if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"result": "NO_GAME"}), flush=True)
        return
    ei = envs[0]
    agent = Peek()
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="peek",
                      max_actions=max_actions, adapter_factory=lambda: agent)
    print(json.dumps({"levels_completed": res.get("levels_completed"),
                      "total_actions": res.get("total_actions")}), flush=True)


if __name__ == "__main__":
    main()
