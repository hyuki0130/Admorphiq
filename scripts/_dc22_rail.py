"""dc22 level 6: is a crane drive gated by the AVATAR's cell, or by the CRANE's own rail?

⛔ The brief this probe was written against says the four drives at (32,50) (36,46) (36,54)
(40,50) "act only while the avatar overlaps their own pressure plate".  The game's own `step()`
disagrees: the `sys_click` branch reads `self.sjixewahg` / `self.uxtzlxsiq` — the crane's grid
position — and `self.qnnpcoyzd` (the avatar) appears nowhere in the gate.  Either the crane
travels a TRACK (`qnlqkldrl` -> `tnedtgkguq` asks whether a `vcha` sprite is drawn at the target)
or it travels a hardcoded C: up/down only in column 0, left/right only in rows 0 and 3.

Rule 7g: the source says what is POSSIBLE.  This asks the board.

The arm holds the AVATAR STILL and round-robins the panel's own buttons, logging the rigid
translation of the body after every press.  If drives answer from a fixed avatar cell at some
rail positions and not others, the gate is the RAIL and the brief's premise is refuted.

  seed (arg 1) = repetition, and it rotates the press order so no single order is load-bearing.
  arg 2 = presses to spend on the last level (default 160).

Rule 7x: the scorer's own `run_game` drives this, so the game played is the game scored.
Rule 7f: `levels_completed` is printed as a number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402

LOG: list = []
S = {"n": 0, "warm": 0, "prev": None, "click": None, "before_pos": None, "level": -1}


def instrument(order_rot: int, budget: int):
    from admorphiq.tools.base import frame_2d
    from admorphiq.tools.gantry import GantryCraneTool, rigid_translation

    orig = GantryCraneTool.propose

    def propose(self, frames, obs):
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl < 5:
            S["level"] = lvl
            return orig(self, frames, obs)
        if S["level"] != lvl:
            S["level"] = lvl
            S["warm"] = 0
        # Let the tool's own opening turns run so its colours and geometry are initialised.
        if S["warm"] < 8:
            S["warm"] += 1
            return orig(self, frames, obs)
        g = np.asarray(frame_2d(obs), dtype=int)
        geom = self._read(g)
        if geom is None:
            LOG.append({"geom": None, "n": S["n"]})
            return []
        board = np.asarray(geom["board"], dtype=int)
        here = self._at(board, self._avatar) if self._avatar >= 0 else None
        if S["prev"] is not None and S["click"] is not None:
            prev = S["prev"]
            row = {"n": S["n"], "click": list(S["click"]), "avatar": list(here) if here else None,
                   "avatar_before": list(S["before_pos"]) if S["before_pos"] else None,
                   "still": bool(prev.shape == board.shape and np.array_equal(prev, board))}
            if prev.shape == board.shape:
                slide = rigid_translation(prev, board, {self._avatar, self._marker})
                if slide is not None:
                    delta, mask = slide
                    row["delta"] = [int(delta[0]), int(delta[1])]
                    row["body"] = int(mask.sum())
                    ys = [int(y) for y, _ in np.argwhere(mask)]
                    xs = [int(x) for _, x in np.argwhere(mask)]
                    row["bbox"] = [min(ys), min(xs), max(ys), max(xs)]
                else:
                    row["delta"] = None
                    row["changed"] = int((prev != board).sum())
            LOG.append(row)
        if S["n"] >= budget:
            return []
        panel = self._panel_buttons(g, geom)
        if not panel:
            LOG.append({"panel": 0, "n": S["n"]})
            return []
        pick = panel[(S["n"] + order_rot) % len(panel)]
        S["prev"] = board.copy()
        S["click"] = pick
        S["before_pos"] = here
        S["n"] += 1
        # Bypass the tool's own settle bookkeeping: this arm owns the turn.
        self._pending, self._kindof = None, ""
        return [(6, (pick[1], pick[0]))]

    GantryCraneTool.propose = propose


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 160
    instrument(seed % 4, budget)
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"result": "NO_GAME"}), flush=True)
        return
    ei = envs[0]
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="unified",
                      max_actions=4000)
    moved = [r for r in LOG if r.get("delta")]
    per: dict = {}
    for r in LOG:
        if "click" not in r:
            continue
        k = str(tuple(r["click"]))
        d = per.setdefault(k, {"n": 0, "moved": 0, "deltas": {}, "avatars": set()})
        d["n"] += 1
        d["avatars"].add(str(tuple(r["avatar_before"])) if r["avatar_before"] else "?")
        if r.get("delta"):
            d["moved"] += 1
            d["deltas"][str(r["delta"])] = d["deltas"].get(str(r["delta"]), 0) + 1
    print(json.dumps({"seed": seed, "levels_completed": int(res.get("levels_completed") or 0),
                      "total_actions": res.get("total_actions"),
                      "game_score": res.get("game_score"),
                      "logged": len(LOG), "moved": len(moved),
                      "per_button": {k: {"n": v["n"], "moved": v["moved"], "deltas": v["deltas"],
                                         "avatars": sorted(v["avatars"])}
                                     for k, v in sorted(per.items())}}), flush=True)
    for r in LOG[:200]:
        print(json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
