"""What perception returns on EVERY dc22 level, read on the left board and on the whole frame.

Purpose: the level-6 goal sits at column 46, inside what `phase_grid`'s split calls the control
panel, so the board the route searches has no goal in it.  Widening the board to the whole frame
was measured to LOSE two levels, and the recorded cause is the panel's own ground being read as
floor.  Before any of that is written, this reads — on the first settled frame of each level —
what the piece rule returns on the left board and on the whole frame, every maximal filled square
of the two candidate colours, and the two grounds.

Expected feedback: if `_pieces` on the whole frame returns the same pair as on the left board for
levels 1-5, a whole-frame board is safe for the pair; if it does not, the pair must be carried.

Varying parameter FIRST = repetition index (deterministic); second = max actions.
Prints ONE JSON line per level.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402


def squares(grid, colour):
    """Every maximal filled square of `colour`, as [y, x, side]."""
    out = []
    for y, x in np.argwhere(grid == colour):
        y, x = int(y), int(x)
        best = 0
        for side in range(2, 9):
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
        self.seen: set[int] = set()
        self.age = 0

    def is_done(self, frames, obs):
        return self.inner.is_done(frames, obs)

    def choose_action(self, frames, obs):
        lvl = int(obs.levels_completed)
        if lvl not in self.seen:
            self.age += 1
            if self.age > 2:          # let the level-up frame turn the page first
                self.seen.add(lvl)
                self.age = 0
                self.dump(obs, lvl)
        return self.inner.choose_action(frames, obs)

    def dump(self, obs, lvl):
        from admorphiq.tools import phase as P
        from admorphiq.tools.base import frame_2d

        g = np.asarray(frame_2d(obs), dtype=int)
        top, bot = P._chrome_span(g)
        split = P._split_columns(g, top, bot)
        rep = {"level": lvl, "chrome": [int(top), int(bot)],
               "split": list(split) if split else None}
        if split is None:
            print(json.dumps(rep), flush=True)
            return
        left = g[top:bot + 1, 0:split[0]]
        whole = g[top:bot + 1, :]
        strip = g[top:bot + 1, split[0]:]
        pl, pw = P._pieces(left), P._pieces(whole)
        rep["pieces_left"] = list(pl) if pl else None
        rep["pieces_whole"] = list(pw) if pw else None
        rep["board_ground"] = int(Counter(int(v) for v in left.ravel()).most_common(1)[0][0])
        rep["panel_ground"] = int(Counter(int(v) for v in strip.ravel()).most_common(1)[0][0])
        cand = sorted({c for p in (pl, pw) if p for c in p[:2]} | {11, 14})
        rep["squares_whole"] = {str(c): squares(whole, c) for c in cand}
        rep["counts_whole"] = {str(c): int((whole == c).sum()) for c in cand}
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
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="peek",
                      max_actions=max_actions, adapter_factory=lambda: agent)
    print(json.dumps({"done": True, "levels_completed": res.get("levels_completed"),
                      "total_actions": res.get("total_actions")}), flush=True)


if __name__ == "__main__":
    main()
