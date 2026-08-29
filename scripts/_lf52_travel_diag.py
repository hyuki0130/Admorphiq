"""Did the boarding objective and the refused local win actually FIRE on lf52 level 6?

⛔ Rule 7b: verify an intervention took effect before calling it inert. The full-game score came
back byte-identical (5 levels, 0.2727, 823 actions against a baseline 820), which is consistent
with three different things and the score cannot separate them: the new code never runs, it runs
and changes no argmax, or it changes the plan and the plan dies on execution.

So this wraps both entry points on level 6 and logs what each one actually saw:

  plan_level   — was `refuse_local_win` set, and did it suppress a `solved` it would have returned?
  travel_moves — the novelty of the start, the novelty of the chosen state, whether `_rail_reach`
                 gave any cart a bonus at all, and whether the returned plan lands on a cart.

Expected feedback: `bonus_max` 0 means the rail component is worth no more than the ground already
worked and the objective is correct to ignore it — the fix is aimed at the wrong thing. `bonus_max`
high with `boarded` false means the argmax is elsewhere and the term is too weak. `boarded` true
with the level still stuck means the plan is right and dies in execution.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

START_LEVEL = 5


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools import railpeg as R

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    peg = next(t for t in tools if isinstance(t, R.RailPegTool))

    at6 = [False]
    tlog: list[dict] = []
    plog = Counter()
    raw_travel = R.travel_moves
    raw_plan = R.plan_level

    def travel(m, noncapture, touched, visited, **kw):
        moves = raw_travel(m, noncapture, touched, visited, **kw)
        if at6[0] and len(tlog) < 40:
            field = R._novelty_field(m, touched)
            reach = R._rail_reach(m, field)
            bonus = [reach.get(c, 0) - field.get(c, 0) for c in m.carts]
            landings = [(c[0] + 2 * d[0], c[1] + 2 * d[1])
                        for kind, c, d in moves if kind == "jump"]
            tlog.append({
                "carts": len(m.carts), "rails": len(m.rails), "sockets": len(m.sockets),
                "pieces": len(m.pieces),
                "cart_field": [field.get(c, 0) for c in sorted(m.carts)],
                "cart_reach": [reach.get(c, 0) for c in sorted(m.carts)],
                "bonus_max": max(bonus) if bonus else 0,
                "field_max": max(field.values()) if field else 0,
                "moves": len(moves),
                "kinds": [k for k, _c, _d in moves][:8],
                "boarded": any(land in m.carts for land in landings),
            })
        return moves

    def plan(m, noncapture, **kw):
        got = raw_plan(m, noncapture, **kw)
        if at6[0]:
            plog[f"refuse={kw.get('refuse_local_win')} solved={got[1] if got else None}"] += 1
        return got

    R.travel_moves = travel
    R.plan_level = plan
    try:
        agent = UnifiedAgent(tools, _no_llm, giveup=4000, stall=80, ctx_budget=6000)
        frames = [obs]
        start_i = 0
        for i in range(2000):
            lvl = int(getattr(obs, "levels_completed", 0) or 0)
            if lvl >= START_LEVEL and not at6[0]:
                at6[0] = True
                start_i = i
                print(f"# level 6 at action {i}", file=sys.stderr, flush=True)
            if lvl > START_LEVEL:
                break
            if at6[0] and i - start_i > 400:
                break
            act = agent.choose_action(frames, obs)
            data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
            obs = env.step(act, data=data) if data else env.step(act)
            frames.append(obs)
    finally:
        R.travel_moves = raw_travel
        R.plan_level = raw_plan

    print(json.dumps({
        "seed": seed, "level": int(getattr(obs, "levels_completed", 0) or 0),
        "plan_calls": dict(plog), "travel_calls": len(tlog),
        "any_boarded": any(t["boarded"] for t in tlog),
        "max_bonus_seen": max((t["bonus_max"] for t in tlog), default=None),
        "travel": tlog[:14],
        "tiers": dict(getattr(peg, "_tiers", {})),
        "elsewhere": getattr(peg, "_elsewhere", None),
    }), flush=True)


if __name__ == "__main__":
    main()
