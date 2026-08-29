"""Is there CHEAP FRAME EVIDENCE that lf52's level-6 board runs past the screen?

⛔ THE GENERIC DEFECT, restated: a predicate over a camera is not a predicate over the state. The
only evidence railpeg currently has that a board is wider than its window is a REFUTATION — it
plans a win, plays it, the level does not end, and only then does `_elsewhere` become true. That
costs a whole win plan, and on a board needing six captures the tool can spend its no-progress
budget getting there.

If the lattice VISIBLY runs into the edge of the frame, the same fact is available on action one
and for every scrolling game, not just this one. That is what this measures, per action, on level
6, without changing any behaviour:

  edge_L/R/T/B   a known cell (socket, rail or bolted obstacle) sitting in the outermost cell
                 column or row the pitch admits — i.e. the structure is CUT by the window rather
                 than ending in background
  scrolled       the alignment offset `_align` returned this frame, accumulated. Non-zero at any
                 point is proof the world moved under the camera, which a board that fits cannot do
  spanW/spanH    how many cells wide/high the map has become, against the window

The instrument proves itself: `fired` counts the frames it inspected, and a run reporting fired = 0
inspected nothing.

Expected feedback: an edge flag that is TRUE from the first level-6 frame is a free, generic
replacement for the win-claim refutation. One that is true on EVERY board, level 1 included, is
useless — it would fire everywhere — so level 1 is measured the same way for contrast (rule 7b:
contrast with the level that clears).
"""
from __future__ import annotations

import json
import sys
from collections import Counter

MAX_ACTIONS = 4000
WATCH = (0, 5)          # level 1 (clears) and level 6 (stalls) — the contrast


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.railpeg import RailPegTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    peg = next((t for t in tools if isinstance(t, RailPegTool)), None)
    if peg is None:
        print(json.dumps({"seed": seed, "error": "railpeg not registered"}), flush=True)
        return

    fired = Counter()
    stats: dict[int, dict] = {}
    cur = [0]
    raw_sync = RailPegTool._sync

    def wrapped(self, g):
        prev_known = len(self._model.known()) if self._model is not None else 0
        prev_ox, prev_oy = (self._model.ox, self._model.oy) if self._model else (0, 0)
        res = raw_sync(self, g)
        lvl = cur[0]
        if lvl not in WATCH:
            return res
        fired[lvl] += 1
        board = self._read
        s = stats.setdefault(lvl, {
            "frames": 0, "board_none": 0, "edgeL": 0, "edgeR": 0, "edgeT": 0, "edgeB": 0,
            "shifted": 0, "spanW": 0, "spanH": 0, "known": 0, "winW": 0, "carts": 0,
            "rails": 0, "first_edge_frame": None, "elsewhere_frame": None})
        s["frames"] += 1
        if self._elsewhere and s["elsewhere_frame"] is None:
            s["elsewhere_frame"] = s["frames"]
        if board is None:
            s["board_none"] += 1
            return res
        h, w = g.shape
        p = board.pitch or 1
        fixed = board.sockets | board.rails | board.obstacles | board.carts
        if fixed:
            rows = [c[0] for c in fixed]
            cols = [c[1] for c in fixed]
            # A cell is at the window edge when the NEXT cell along would not fit on screen.
            if board.ox + (min(cols) - 1) * p < 0:
                s["edgeL"] += 1
            if board.ox + (max(cols) + 2) * p > w:
                s["edgeR"] += 1
            if board.oy + (min(rows) - 1) * p < 0:
                s["edgeT"] += 1
            if board.oy + (max(rows) + 2) * p > h:
                s["edgeB"] += 1
            if (s["edgeL"] or s["edgeR"]) and s["first_edge_frame"] is None:
                s["first_edge_frame"] = s["frames"]
            s["winW"] = max(s["winW"], max(cols) - min(cols) + 1)
        m = res[0] if res is not None else None
        if m is not None:
            k = m.known()
            if k:
                s["spanW"] = max(s["spanW"], max(c[1] for c in k) - min(c[1] for c in k) + 1)
                s["spanH"] = max(s["spanH"], max(c[0] for c in k) - min(c[0] for c in k) + 1)
            s["known"] = max(s["known"], len(k))
            s["carts"] = max(s["carts"], len(m.carts))
            s["rails"] = max(s["rails"], len(m.rails))
            if (m.ox, m.oy) != (prev_ox, prev_oy) and prev_known:
                s["shifted"] += 1
        return res

    RailPegTool._sync = wrapped
    try:
        agent = UnifiedAgent(tools, _no_llm, giveup=8000, stall=80, ctx_budget=6000)
        for _i in range(MAX_ACTIONS):
            cur[0] = int(getattr(obs, "levels_completed", 0) or 0)
            if agent.is_done([], obs):
                break
            act = agent.choose_action([], obs)
            data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
            obs = env.step(act, data=data) if data else env.step(act)
    finally:
        RailPegTool._sync = raw_sync

    print(json.dumps({
        "seed": seed,
        "fired": dict(fired),
        "final_level": int(getattr(obs, "levels_completed", 0) or 0),
        "levels": {str(k): v for k, v in sorted(stats.items())},
    }), flush=True)


if __name__ == "__main__":
    main()
