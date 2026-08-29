"""Do railpeg's two new branches FIRE on lf52's level 6, or were they never reached?

⛔ Rule 7g. The previous attempt at `refuse_local_win` + the rail-reach travel bonus came back from
the gate at 0.2727 / 5 levels — IDENTICAL to the version without them — and its author's own note
was "before concluding inert, prove whether the new branches fire at all". A change that is never
executed and a change that is executed and does nothing want OPPOSITE repairs, and no score can
tell them apart.

So this runs the REAL harness (same giveup / stall / no_progress as the runner, LLM dead so routing
is by signature, exactly as the card ships) and reports, attributed to level 6 by DELTA against a
snapshot taken the instant level 6 starts:

  elsewhere:set            did the board ever get classified as extending past the screen
  plan:local-win-refused   did `refuse_local_win` ever actually refuse one
  travel:plans/boards      did the travel tier run, and did any plan put a piece ON a cart
  travel:reach-top         the best novelty ANY known track can carry a cart to. ⛔ Zero here means
                           the bonus is arithmetically incapable of changing a ranking — every rail
                           cell known sits where pieces have already stood — and no amount of
                           weighting it differently would matter.
  travel:field-top         the same number for a walking piece, so the two are comparable
  drive:with-passenger     drives that carried somebody, against drive:empty
  tools                    which tool the harness actually had active, per action

The instrument proves itself: `at6` is the action level 6 began at and `acted6` the actions spent
there. A run reporting acted6 = 0 measured nothing.

Expected feedback: `elsewhere:set` = 0 says the win-claim refutation never happened and BOTH
branches were gated off. `travel:boards` = 0 with `reach-top` = 0 says the bonus cannot see any
track worth boarding. `travel:boards` > 0 with the level still unfinished says boarding works and
the wall is further on.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

START = 5           # level 6 is levels_completed == 5
MAX_ACTIONS = 4000


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.railpeg import (
        DIRS,
        RailPegTool,
        _ground,
        _successors,
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

    # ⛔ CENSUS THE BARREN MOMENT ITSELF. A counter says how often every tier came back empty; it
    # cannot say what the board looked like when they did, and that is the whole question — a
    # region with no legal jump left and a region whose cart is out of reach want different work.
    barren: list[dict] = []
    raw_plan = RailPegTool._ensure_plan

    def wrapped_plan(self, m):
        score = raw_plan(self, m)
        if score == 0.0 and at6[0] is not None and len(barren) < 12:
            pieces = dict(m.pieces)
            solid = set(pieces) | set(m.obstacles) | set(m.cargo)
            legal = sum(1 for _ns, _mv, _c in _successors(
                m.state(), _ground(m), self._noncapture))
            barren.append({
                "pieces": len(pieces), "colours": sorted(Counter(pieces.values()).values()),
                "carts": len(m.carts), "cargo": len(m.cargo), "aboard":
                    len(set(m.carts) & set(pieces)),
                "legal_moves": legal,
                "jumps": sum(1 for p in pieces for d in DIRS
                             if (p[0] + d[0], p[1] + d[1]) in solid),
                "known": len(m.known()), "rails": len(m.rails), "window": len(m.window),
            })
        return score

    RailPegTool._ensure_plan = wrapped_plan
    agent = UnifiedAgent(tools, _no_llm, giveup=8000, stall=80, ctx_budget=6000)
    snap_why: Counter[str] = Counter()
    snap_tiers: Counter[str] = Counter()
    at6: list = [None]
    acted6 = 0
    active: Counter[str] = Counter()
    known: list[int] = []
    start_level = int(getattr(obs, "levels_completed", 0) or 0)
    lvl = start_level
    for i in range(MAX_ACTIONS):
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl >= START and at6[0] is None:
            at6[0] = i
            snap_why = Counter(peg._why)
            snap_tiers = Counter(peg._tiers)
        if lvl > START:
            break
        if agent.is_done([], obs):
            break
        # ⛔ The runner passes an EMPTY frame list (score_efficiency.py:381), so a probe that hands
        # over a history is measuring a different agent from the one the gate scores.
        act = agent.choose_action([], obs)
        if at6[0] is not None:
            acted6 += 1
            active[str(getattr(agent, "_current", "?"))] += 1
            m = getattr(peg, "_model", None)
            if m is not None and acted6 % 10 == 0:
                known.append(len(m.known()))
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)

    final = int(getattr(obs, "levels_completed", 0) or 0)
    why6 = Counter(peg._why)
    why6.subtract(snap_why)
    tiers6 = Counter(peg._tiers)
    tiers6.subtract(snap_tiers)
    # ⛔ reach-top / field-top are MAXIMA held in the same Counter, so a delta on them is
    # meaningless — report the absolute value and say so.
    for k in ("travel:reach-top", "travel:field-top"):
        why6[k] = peg._why[k]
    print(json.dumps({
        "seed": seed,
        "start_level": start_level,
        "at6": at6[0],
        "acted6": acted6,
        "final_level": final,
        "cleared6": final > START,
        "why6": {k: v for k, v in sorted(why6.items()) if v},
        "tiers6": {k: v for k, v in sorted(tiers6.items()) if v},
        "tools6": dict(active.most_common()),
        "known_trace": known[:40],
        "barren": barren,
        "elsewhere": bool(getattr(peg, "_elsewhere", False)),
        "noncapture": sorted(getattr(peg, "_noncapture", set())),
    }), flush=True)


if __name__ == "__main__":
    main()
