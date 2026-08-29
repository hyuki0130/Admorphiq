"""Does a candidate frontier term actually RANK anything, or is it another constant?

⛔ RULE 7v, APPLIED TO MY OWN REDESIGN BEFORE I WRITE IT. The term I shipped is inert for a reason
that is invisible in the source: `_rail_reach` gives a component `max(field)+1` whenever it has an
open end, and on this board EVERY component has one, so every component scores the same and the
term ranks nothing. A term identical across every candidate looks exactly like a working term. So
the next one gets measured for SPREAD first — the number of DISTINCT values it assigns across the
components competing in a single decision — and a candidate whose spread is 1 is rejected before it
costs a run.

Three terms are scored side by side on the same live boards, per planning turn:

  cur       what ships: component max novelty, raised to max(field)+1 if the component has ANY
            open end.
  outward   the same, but an open end only counts when the cell beyond it lies OUTSIDE the model's
            own bounding box. An open end pointing into the interior is a hole in the map, not a
            way off it — the board is simply not filled in there, and going to look costs a journey
            to reach territory the tool is standing next to.
  reachable the outward test, weighted by how far past the bounding box the open end points along
            its own axis, so two ways off the map are separated by how much they open.

⚠️ Spread is measured ACROSS COMPONENTS WITHIN A TURN, never across turns. A term that varies from
turn to turn while being flat inside each one still cannot choose, and averaging over turns would
hide exactly that.

The instrument proves itself with `turns` and `multi_component_turns`: spread is undefined where
only one component exists, so a run whose boards never offer a choice measures nothing about
ranking, and that count says whether the question was even askable.

Expected feedback: `cur` flat at spread 1 confirms the shipped defect on live boards. A candidate
with spread > 1 on a decent share of the multi-component turns is worth building; one that is also
flat is the same mistake in a new coat and must not be shipped on the strength of its docstring.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, deque

START = 5
MAX_ACTIONS = 4000


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools import railpeg as rp

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    def components(m):
        rails = m.rails | m.carts
        seen, out = set(), []
        for origin in rails:
            if origin in seen:
                continue
            comp, q = [origin], deque([origin])
            seen.add(origin)
            while q:
                c = q.popleft()
                for d in rp.DIRS:
                    n = (c[0] + d[0], c[1] + d[1])
                    if n in rails and n not in seen:
                        seen.add(n)
                        comp.append(n)
                        q.append(n)
            out.append(comp)
        return out, rails

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

    at6: list = [None]
    turns = [0]
    multi = [0]
    spread = {"cur": Counter(), "outward": Counter(), "reachable": Counter()}
    open_kinds = Counter()
    rows: list[dict] = []
    raw_plan = rp.RailPegTool._ensure_plan

    def wrapped(self, m):
        if at6[0] is not None and m.known():
            turns[0] += 1
            field = rp._novelty_field(m, self._touched)
            comps, rails = components(m)
            known = m.known()
            rs = [c[0] for c in known]
            cs = [c[1] for c in known]
            box = (min(rs), max(rs), min(cs), max(cs))
            horizon = max(field.values(), default=0) + 1
            vals = {"cur": [], "outward": [], "reachable": []}
            for comp in comps:
                top = max((field.get(c, 0) for c in comp), default=0)
                any_open = False
                any_out = False
                best_depth = 0
                for c in comp:
                    for d in rp.DIRS:
                        if not rp._offscreen(m, rails, c, d):
                            continue
                        any_open = True
                        n = (c[0] + d[0], c[1] + d[1])
                        outside = not (box[0] <= n[0] <= box[1] and box[2] <= n[1] <= box[3])
                        open_kinds["outward" if outside else "interior"] += 1
                        if outside:
                            any_out = True
                            # how far past the box this points, along its own axis
                            depth = (max(0, n[0] - box[1]) + max(0, box[0] - n[0])
                                     + max(0, n[1] - box[3]) + max(0, box[2] - n[1]))
                            best_depth = max(best_depth, depth)
                vals["cur"].append(max(top, horizon) if any_open else top)
                vals["outward"].append(max(top, horizon) if any_out else top)
                vals["reachable"].append(top + best_depth * horizon if any_out else top)
            if len(comps) > 1:
                multi[0] += 1
                for k, v in vals.items():
                    spread[k][len(set(v))] += 1
                if len(rows) < 10:
                    rows.append({"comps": len(comps), "field_top": max(field.values(), default=0),
                                 **{k: v for k, v in vals.items()}})
        return raw_plan(self, m)

    rp.RailPegTool._ensure_plan = wrapped
    try:
        agent = UnifiedAgent(tools, _no_llm, giveup=8000, stall=80, ctx_budget=6000)
        for i in range(MAX_ACTIONS):
            lvl = int(getattr(obs, "levels_completed", 0) or 0)
            if lvl >= START and at6[0] is None:
                at6[0] = i
            if lvl > START or agent.is_done([], obs):
                break
            a = agent.choose_action([], obs)
            data = a.action_data.model_dump() if getattr(a, "action_data", None) else None
            obs = env.step(a, data=data) if data else env.step(a)
    finally:
        rp.RailPegTool._ensure_plan = raw_plan

    def pct(c):
        tot = sum(c.values()) or 1
        return {f"spread{k}": f"{v} ({100*v//tot}%)" for k, v in sorted(c.items())}

    print(json.dumps({
        "seed": seed, "at6": at6[0], "turns": turns[0],
        "multi_component_turns": multi[0],
        "open_ends_by_kind": dict(open_kinds),
        "cur": pct(spread["cur"]),
        "outward": pct(spread["outward"]),
        "reachable": pct(spread["reachable"]),
        "rows": rows,
        "final_level": int(getattr(obs, "levels_completed", 0) or 0),
    }), flush=True)


if __name__ == "__main__":
    main()
