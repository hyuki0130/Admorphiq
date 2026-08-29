"""Does lf52's level-6 track TERMINATE IN VIEW, or is railpeg's open-end test wrong?

⛔ MEASURE THIS, DO NOT BUILD ON IT. At the barren moment `travel` reports no-gain while a cart is
boardable, which means no rail component has an OPEN END — the model believes it has seen all of
its track, inside a 90-cell window on a 28-column board. Two readings, cheaply distinguishable,
leading to completely different work:

  A  the track really does stop where the tool can see it stop, and the far side of the board is
     reached by some mechanic that is not "ride a cart" at all;
  B  `_offscreen` is wrong — there IS track running out of the picture and the test cannot see it.

The discriminator is the neighbour of every rail cell at the edge of the known track, taken ALONG
the track's own direction (the cell behind must be track, or every rail touching the window edge
counts as leaving it in all four directions). Exactly three things that neighbour can be:

  term_floor      in the window, and not track — the track visibly ends on plain floor. Reading A.
  term_furniture  a known socket or obstacle — the track ends against something. Reading A.
  open            outside the window — the board cannot say. Reading B, and what `_offscreen` flags.

⚠️ AND IT IS SAMPLED OVER TIME, because the map only started growing at all this round (61 -> 99
cells, from one retracted rail cell). "No open end" being TRUE FOREVER and "no open end for the
first two hundred actions and then not" are different states with different repairs, and a single
reading at the barren moment cannot tell them apart.

The instrument proves itself: `samples` is how many planning turns it inspected, and a run
reporting 0 measured nothing. It also prints the model's rail extent against the window's, so a
claim that the track stops in view can be checked against where the track actually is.

Expected feedback: `open` > 0 at any sample with `travel:no-gain` at the same moment means the test
sees an open end and travel still declines it — reading B, and the bug is in the ranking, not the
test. `open` == 0 at every sample, with the rail extent ending well inside the known map, is
reading A, and riding carts is not the route to the rest of that board.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

START = 5
MAX_ACTIONS = 4000


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.railpeg import (
        DIRS,
        RailPegTool,
        _novelty_field,
        _offscreen,
        _rail_reach,
    )

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

    at6: list = [None]
    samples: list[dict] = []
    ever_open = Counter()
    # ⚠️ RULE 7s. A level that RESTARTS reads identically to one that continues — `levels_completed`
    # does not move — so a census over "the barren moments" can silently be averaging several
    # ATTEMPTS at the same board as though they were one. On a capture game the tell is exact:
    # pieces only ever leave the board within an attempt, so a piece count that goes UP is a
    # restart and nothing else.
    attempt = [0, -1]

    def census(self, m):
        rails = m.rails | m.carts
        field = _novelty_field(m, self._touched)
        reach = _rail_reach(m, field) if field else {}
        ends = Counter()
        for c in rails:
            for d in DIRS:
                back = (c[0] - d[0], c[1] - d[1])
                n = (c[0] + d[0], c[1] + d[1])
                if back not in rails or n in rails:
                    continue                       # not a track end in this direction
                if n not in m.known() and n not in m.window:
                    ends["open"] += 1
                elif n in m.known():
                    ends["term_furniture"] += 1
                else:
                    ends["term_floor"] += 1
        if len(m.pieces) > attempt[1] >= 0:
            attempt[0] += 1
        attempt[1] = len(m.pieces)
        cols = [c[1] for c in m.known()] or [0]
        wcols = [c[1] for c in m.window] or [0]
        rcols = [c[1] for c in rails] or [0]
        return {
            "open": ends["open"], "term_floor": ends["term_floor"],
            "term_furniture": ends["term_furniture"],
            "offscreen_flag": sum(1 for c in rails for d in DIRS
                                  if _offscreen(m, rails, c, d)),
            "known": len(m.known()), "rails": len(rails), "carts": len(m.carts),
            "aboard": len(set(m.carts) & set(m.pieces)), "pieces": len(m.pieces),
            "known_cols": [min(cols), max(cols)], "win_cols": [min(wcols), max(wcols)],
            "rail_cols": [min(rcols), max(rcols)],
            "attempt": attempt[0],
            "field_top": max(field.values(), default=0),
            "reach_top": max(reach.values(), default=0),
        }

    raw_plan = RailPegTool._ensure_plan

    def wrapped(self, m):
        if at6[0] is not None and self._model is not None and len(samples) < 600:
            row = census(self, m)
            row["act"] = len(samples)
            samples.append(row)
            if row["open"]:
                ever_open["open"] += 1
        return raw_plan(self, m)

    RailPegTool._ensure_plan = wrapped
    try:
        agent = UnifiedAgent(tools, _no_llm, giveup=8000, stall=80, ctx_budget=6000)
        for i in range(MAX_ACTIONS):
            lvl = int(getattr(obs, "levels_completed", 0) or 0)
            if lvl >= START and at6[0] is None:
                at6[0] = i
            if lvl > START or agent.is_done([], obs):
                break
            act = agent.choose_action([], obs)
            data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
            obs = env.step(act, data=data) if data else env.step(act)
    finally:
        RailPegTool._ensure_plan = raw_plan

    # Compress the series: the distinct census rows in order of first appearance, so a state that
    # persists for two hundred actions is ONE line carrying how long it lasted.
    runs: list[dict] = []
    for row in samples:
        key = {k: v for k, v in row.items() if k != "act"}
        if runs and runs[-1]["state"] == key:
            runs[-1]["n"] += 1
            runs[-1]["last"] = row["act"]
        else:
            runs.append({"state": key, "n": 1, "first": row["act"], "last": row["act"]})
    print(json.dumps({
        "seed": seed, "at6": at6[0], "samples": len(samples),
        "attempts_on_level_6": attempt[0] + 1,
        "final_level": int(getattr(obs, "levels_completed", 0) or 0),
        "turns_with_an_open_end": ever_open["open"],
        "distinct_states": len(runs),
        "series": runs[:40],
        "why": {k: v for k, v in sorted(peg._why.items()) if v},
    }), flush=True)


if __name__ == "__main__":
    main()
