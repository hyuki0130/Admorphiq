"""What does railpeg SEE at the moment it refuses every capture on lf52 level 6?

⛔ THE STOPPER IS `plan:all-candidates-fatal`, 11-18 times a level, and the last-resort experiment
already proved the veto CORRECT — relaxing it took a capture and reached a position with zero legal
jumps thereafter. So the veto stays and the question is about the MAP it is asked over. Two
readings, needing different work:

  a  THE MAP IS STILL TOO SMALL. The follow-up capture that would make a candidate survivable lies
     in board the tool has not uncovered yet, so "no capture is reachable" is a statement about the
     camera, not the position. Then the work is exploration, and the frontier term should optimise
     for reaching board that could HOLD a capture.
  b  THE VETO IS ASKED TOO EARLY. The refusals cluster in the first actions while the map is still
     growing fast, and stop once it settles. Then the work is ordering — explore first, ask later.

The discriminator is exact and needs no new search: this board holds EIGHT pieces, and the model
knows how many it has actually seen. A refusal taken while fewer than eight are known is a refusal
over a partial board by construction. Recorded with it: the action index inside the level (early
vs late separates reading b), the column span the model has against the board's 28, and the open
ends, so the frontier redesign has the numbers it needs in the same run.

⚠️ It also records the refusals' POSITION IN TIME as a list, because "eleven refusals" spread evenly
and "eleven refusals in the first thirty actions" are different findings and a total cannot tell
them apart.

The instrument proves itself by counting the `plan_level` calls it wrapped: a run reporting `calls`
0 wrapped nothing. It detects the veto by watching railpeg's OWN counter move across the call
rather than by re-deriving the verdict, so it cannot disagree with the tool about what happened.

Expected feedback: refusals concentrated where pieces_known < 8 is reading (a) and says the map is
the lever. Refusals continuing at pieces_known == 8 with the columns saturated is a genuine dead
end, and lf52 level 6 needs a different mechanic entirely.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

START = 5
MAX_ACTIONS = 4000
PIECES_ON_THE_BOARD = 8      # measured in R101LF52: the level holds eight pads


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
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
        print(json.dumps({"seed": seed, "error": "railpeg not registered"}), flush=True)
        return

    act_now = [0]
    at6: list = [None]
    calls = [0]
    vetoes: list[dict] = []
    nofollow: list[dict] = []
    raw_plan_level = rp.plan_level

    def wrapped(m, noncapture, *a, **kw):
        why = kw.get("why")
        before = why["plan:all-candidates-fatal"] if why is not None else 0
        beforenc = why["plan:no-capture-reachable"] if why is not None else 0
        res = raw_plan_level(m, noncapture, *a, **kw)
        if at6[0] is None or why is None:
            return res
        calls[0] += 1
        vetoed = why["plan:all-candidates-fatal"] > before
        nofoll = why["plan:no-capture-reachable"] > beforenc
        if not (vetoed or nofoll):
            return res
        known = m.known()
        cols = [c[1] for c in known] or [0]
        rails = m.rails | m.carts
        row = {
            "act": act_now[0] - (at6[0] or 0),
            "pieces_known": len(m.pieces),
            "colours": sorted(Counter(m.pieces.values()).values()),
            "known": len(known),
            "cols": [min(cols), max(cols)],
            "carts": len(m.carts),
            "aboard": len(set(m.carts) & set(m.pieces)),
            "open_ends": sum(1 for c in rails for d in rp.DIRS
                             if rp._offscreen(m, rails, c, d)),
        }
        (vetoes if vetoed else nofollow).append(row)
        return res

    rp.plan_level = wrapped
    try:
        agent = UnifiedAgent(tools, _no_llm, giveup=8000, stall=80, ctx_budget=6000)
        for i in range(MAX_ACTIONS):
            act_now[0] = i
            lvl = int(getattr(obs, "levels_completed", 0) or 0)
            if lvl >= START and at6[0] is None:
                at6[0] = i
            if lvl > START or agent.is_done([], obs):
                break
            a = agent.choose_action([], obs)
            data = a.action_data.model_dump() if getattr(a, "action_data", None) else None
            obs = env.step(a, data=data) if data else env.step(a)
    finally:
        rp.plan_level = raw_plan_level

    partial = [v for v in vetoes if v["pieces_known"] < PIECES_ON_THE_BOARD]
    print(json.dumps({
        "seed": seed, "at6": at6[0], "plan_level_calls": calls[0],
        "final_level": int(getattr(obs, "levels_completed", 0) or 0),
        "vetoes": len(vetoes),
        "vetoes_over_a_partial_board": len(partial),
        "ever_vetoed_with_all_8_known": len(vetoes) - len(partial),
        "veto_acts": [v["act"] for v in vetoes],
        "veto_rows": vetoes[:12],
        "no_capture_reachable": len(nofollow),
        "nofollow_rows": nofollow[:6],
        "best_map_seen": max((v["known"] for v in vetoes), default=0),
        "most_pieces_seen": max((v["pieces_known"] for v in vetoes), default=0),
    }), flush=True)


if __name__ == "__main__":
    main()
