"""At the moment lf52 level 6 stalls, is there ANY single action that would grow the map?

⛔ THE QUESTION IS ORACULAR, SO IT IS ANSWERED BY DOING, NOT BY INSPECTING. Exploration stops at 98
cells, columns [0,25] of 28, with 6 of 8 pads seen; `travel` reports no-gain and `railhead` finds
nobody aboard. The tempting next step is a tier that boards a cart and drives it outward — and the
LAST plausible-sounding tier built on that intuition (`ferry_moves`) fired zero times. So before
anything is built, the board is asked directly.

METHOD. Each run takes an ARM. At the first stall on level 6 — the moment railpeg's own
`_ensure_plan` returns 0.0, so the stall is the tool's verdict and not mine — the arm forces ONE
action of its own choosing instead of the harness's, then hands control back and watches whether
the model's known-cell count ever exceeds what it had at the stall.

    arm -1   force nothing; the control, and the number every other arm is read against
    arm  k   force the k-th move railpeg's own successor function offers at that instant
             (its legal jumps first, then the four cart drives), played exactly as `propose`
             would play it — two clicks for a jump, the learned direction id for a drive

A move is only interesting if the tool COULD have made it, so the arms come from the tool's own
model rather than from a raw action enumeration; an arm that the engine refuses is a real answer
(the model believed a move the board does not allow) and is reported as such.

⚠️ The stall is detected on railpeg's return value, so an arm that never sees a stall reports
`stalled_at: null` — that is a measurement failure, not a finding of "no stall", and it is printed
rather than silently counted as zero growth.

The instrument proves itself: `arms_available` says how many moves existed at the stall, so an arm
index beyond it is reported as skipped rather than as a null result, and `known_at_stall` against
`known_after` is a comparison of the same quantity at two times rather than of two quantities.

Expected feedback: any arm whose `grew` is positive means a single action DOES open the board from
the stall, and the missing capability is a tier that finds it — the hypothesis survives and gains a
worked example. Every arm at zero, including the drives, means the stall is genuine on this board:
no single move opens it, and the two-step plan is not merely unexpressed but insufficient.
"""
from __future__ import annotations

import json
import sys

START = 5
MAX_ACTIONS = 4000
WATCH = 80          # actions to keep watching after the forced move


def main() -> None:
    # pfan feeds 1..N, so seed 1 is the CONTROL (arm -1) and seed k forces move k-2.
    arm = (int(sys.argv[1]) if len(sys.argv) > 1 else 1) - 2
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools import railpeg as rp

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    peg = next((t for t in tools if isinstance(t, rp.RailPegTool)), None)
    if peg is None:
        print(json.dumps({"arm": arm, "error": "railpeg not registered"}), flush=True)
        return

    at6: list = [None]
    stalled = {"at": None, "known": 0, "arms": 0, "forced": None, "note": None}
    raw_plan = rp.RailPegTool._ensure_plan

    def wrapped(self, m):
        score = raw_plan(self, m)
        if score == 0.0 and at6[0] is not None and stalled["at"] is None:
            moves = [mv for _ns, mv, _c in rp._successors(
                m.state(), rp._ground(m), self._noncapture)]
            # jumps first, then drives — the order `_successors` already yields
            stalled["arms"] = len(moves)
            stalled["known"] = len(m.known())
            stalled["pieces"] = len(m.pieces)
            stalled["carts"] = len(m.carts)
            stalled["aboard"] = len(set(m.carts) & set(m.pieces))
            stalled["at"] = -1                      # filled with the action index by the caller
            stalled["moves"] = [f"{k}:{c}:{d}" for k, c, d in moves[:12]]
            stalled["pick"] = moves[arm] if 0 <= arm < len(moves) else None
        return score

    rp.RailPegTool._ensure_plan = wrapped
    best_after = 0
    forced_at = None
    try:
        agent = UnifiedAgent(tools, _no_llm, giveup=8000, stall=80, ctx_budget=6000)
        for i in range(MAX_ACTIONS):
            lvl = int(getattr(obs, "levels_completed", 0) or 0)
            if lvl >= START and at6[0] is None:
                at6[0] = i
            if lvl > START or agent.is_done([], obs):
                break
            step = None
            if stalled["at"] == -1:
                stalled["at"] = i - at6[0]
                if stalled["pick"] is not None:
                    m = peg._model
                    kind, cell, d = stalled["pick"]
                    if kind == "jump":
                        land = (cell[0] + 2 * d[0], cell[1] + 2 * d[1])
                        step = [(6, m.pixel(cell)), (6, m.pixel(land))]
                    else:
                        aid = peg._dirmap.get(d)
                        step = [(aid, None)] if aid is not None else None
                        if step is None:
                            stalled["note"] = "no learned action id for that direction"
                    stalled["forced"] = f"{kind}:{cell}:{d}"
                    forced_at = i
            if step is not None:
                # ⛔ Built through the harness's OWN converter, so a forced move is played exactly
                # as the tool would have played it; a hand-rolled action would be measuring a
                # different thing from the one the tier would emit.
                from admorphiq.adapter import AdmorphiqAdapter
                from admorphiq.types import ActionType, GameAction
                convert = AdmorphiqAdapter._convert_action
                for aid, xy in step:
                    g = (GameAction.coordinate(int(xy[0]), int(xy[1])) if aid == 6
                         else GameAction.simple(ActionType(aid)))
                    a = convert(g)
                    data = a.action_data.model_dump() if getattr(a, "action_data", None) else None
                    obs = env.step(a, data=data) if data else env.step(a)
                continue
            a = agent.choose_action([], obs)
            data = a.action_data.model_dump() if getattr(a, "action_data", None) else None
            obs = env.step(a, data=data) if data else env.step(a)
            if forced_at is not None:
                if peg._model is not None:
                    best_after = max(best_after, len(peg._model.known()))
                if i - forced_at > WATCH:
                    break
    finally:
        rp.RailPegTool._ensure_plan = raw_plan

    print(json.dumps({
        "arm": arm,
        "arms_available": stalled["arms"],
        "skipped": stalled["arms"] > 0 and not (arm < 0 or arm < stalled["arms"]),
        "stalled_at": stalled["at"],
        "known_at_stall": stalled["known"],
        "pieces_at_stall": stalled.get("pieces"),
        "carts_at_stall": stalled.get("carts"),
        "aboard_at_stall": stalled.get("aboard"),
        "moves_on_offer": stalled.get("moves"),
        "forced": stalled["forced"],
        "note": stalled["note"],
        "known_after": best_after,
        "grew": max(0, best_after - stalled["known"]),
        "final_level": int(getattr(obs, "levels_completed", 0) or 0),
    }), flush=True)


if __name__ == "__main__":
    main()
