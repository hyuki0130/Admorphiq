"""Dump dc22 level 6's frame and every perception candidate a tool could key on.

Purpose: the named work is (1) a whole-frame board with a LEARNED floor palette, (2) a drive
gated on where the avatar stands, (3) a warp aimed by another control's phase.  All three need
the actual frame, and every previous read of it was partial.  This plays to level 6 with the
generic tools and prints the frame plus:

  * the chrome span, the split, and what `_pieces` returns on the LEFT board and on the WHOLE frame
  * every solid block of every colour, with its size and position, so the goal's four twins are
    visible as data rather than as a claim
  * the panel's own ground colour (the candidate non-floor colour for a whole-frame board)
  * the panel buttons at the arrival cell

Expected feedback: a perception design that is checked against the board before it is written.
Varying parameter FIRST = repetition index (this dump is deterministic); second = max actions.  Prints ONE JSON line.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402
from arcengine import GameAction  # noqa: E402


def blocks(grid, colour):
    """Every maximal filled square of `colour`, as (y, x, side)."""
    out = []
    cells = np.argwhere(grid == colour)
    for y, x in cells:
        y, x = int(y), int(x)
        best = 0
        for side in range(2, 8):
            if y + side > grid.shape[0] or x + side > grid.shape[1]:
                break
            if bool((grid[y:y + side, x:x + side] == colour).all()):
                best = side
        if best < 2:
            continue
        if y and bool((grid[y - 1, x:x + best] == colour).all()):
            continue
        if x and bool((grid[y:y + best, x - 1] == colour).all()):
            continue
        out.append([y, x, best])
    return out


class Peek:
    def __init__(self):
        self.inner = SE._make_agent("unified", game_id="dc22")
        self.done = False

    def is_done(self, frames, obs):
        return self.done or self.inner.is_done(frames, obs)

    def choose_action(self, frames, obs):
        if obs.levels_completed >= 5 and not self.done:
            self.dump(obs)
            self.done = True
            return GameAction.ACTION1
        return self.inner.choose_action(frames, obs)

    def dump(self, obs):
        from collections import Counter

        from admorphiq.tools import phase as P
        from admorphiq.tools.base import frame_2d
        from admorphiq.tools.gantry import GantryCraneTool

        layers = np.asarray(obs.frame, dtype=int)
        g = np.asarray(obs.frame[-1], dtype=int)
        f2 = np.asarray(frame_2d(obs), dtype=int)
        top, bot = P._chrome_span(g)
        split = P._split_columns(g, top, bot)
        rep = {
            "levels_completed": int(obs.levels_completed),
            "n_layers": int(layers.shape[0]),
            "frame_2d_equals_last": bool(np.array_equal(f2, g)),
            "chrome_span": [int(top), int(bot)],
            "split": list(split) if split else None,
        }
        left = g[top:bot + 1, 0:split[0]] if split else None
        whole = g[top:bot + 1, :]
        rep["pieces_left"] = list(P._pieces(left)) if left is not None and P._pieces(left) else None
        rep["pieces_whole"] = list(P._pieces(whole)) if P._pieces(whole) else None
        rep["hist_whole"] = {str(k): int(v) for k, v in
                             sorted(Counter(int(v) for v in whole.ravel()).items())}
        rep["hist_left"] = ({str(k): int(v) for k, v in
                             sorted(Counter(int(v) for v in left.ravel()).items())}
                            if left is not None else None)
        rep["blocks"] = {str(c): blocks(whole, c)
                         for c in sorted({int(v) for v in whole.ravel()})
                         if 0 < len(blocks(whole, c)) <= 12}
        if split:
            strip = g[top:bot + 1, split[0]:]
            rep["panel_ground"] = int(Counter(int(v) for v in strip.ravel()).most_common(1)[0][0])
            rep["board_ground"] = int(Counter(int(v) for v in left.ravel()).most_common(1)[0][0])
        t = GantryCraneTool()
        t.reset()
        geom = t._read(g)
        if geom is not None:
            rep["geom_rare"] = list(geom["rare"])
            rep["geom_side"] = int(geom["side"])
            rep["geom_bg"] = int(geom["bg"])
            rep["panel_buttons"] = [list(c) for c in t._panel_buttons(g, geom)]
        rep["frame"] = [[int(v) for v in row] for row in whole]
        print(json.dumps(rep), flush=True)


def main():
    max_actions = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"result": "NO_GAME"}), flush=True)
        return
    ei = envs[0]
    agent = Peek()
    SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="peek",
                max_actions=max_actions, adapter_factory=lambda: agent)


if __name__ == "__main__":
    main()
