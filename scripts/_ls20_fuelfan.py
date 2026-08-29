"""ls20 level 7 costs 302 actions against a human 186 — every hypothesis for the gap, at once.

Purpose. fogscout clears ls20 7/7 but runs dry TWICE on the fogged level 7, and the second
attempt discovers nothing yet still costs 146 actions. This probe runs ONE full ls20 per
process, each with a different candidate mechanism swapped into a FogScoutTool subclass, so
every hypothesis about the gap is measured in the same fan-out instead of one per session.

The hypotheses, and the variant that tests each:

  0  baseline + FULL TRACE of level 7 (mode, tank, distance to the nearest known refill,
     distance to the goal, deaths) + a fuel-constrained shortest-route lower bound computed
     from the map the tool itself finished with.
  1  `_refuel`'s "only when the tank is genuinely low" gate (left > max(3, full//3) refuses)
     is what makes a death unavoidable: by the time it is willing to divert, the refill is
     out of range. Variant drops that gate.
  2  the margin is too tight: it goes only when `left <= dist + 1`, i.e. with zero slack.
  3  1 and 2 together.
  4  a softer version of 1: divert below half a tank, slack 2.
  5  the last units of fuel are spent TREADING. Divert instead when a tread would leave the
     tank unable to reach a refill.
  6  the win walk is committed to WITHOUT checking it is affordable — `_search` never sets
     `_plan_dist`, so the tank is never compared against the route that is actually being
     executed. Variant refuels first when the goal is further than the tank.
  7  3 + 6.
  8  3 + 5 + 6 — everything.
  9  top up when it is nearly free: a refill one step away and the tank not full.
 10  9 + 3 + 6.
 11  NULL TEST: refuelling removed entirely. If level 7 costs the same, the refuel clause is
     not where the actions are going and every variant above is aimed at the wrong stage.

Expected feedback. `lvl7` is the whole metric: 302 today, 186 is the human baseline and worth
+0.1558 on ls20 (+0.0062 on the 25-game mean). A variant that lowers `lvl7` while keeping
`levels=7` is a real gain; one that raises it, or loses the level, refutes its hypothesis. A
flat row of twelve identical numbers says the fuel clause is not the lever at all.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, deque
from typing import Any

import numpy as np

NVAR = 12


def _mk(variant: int):
    from admorphiq.tools.fogscout import FogScoutTool

    class V(FogScoutTool):
        """FogScoutTool with ONE candidate fuel mechanism swapped in."""

        def __init__(self) -> None:
            self.v = variant
            self.trace: list[dict[str, Any]] = []
            self.snap: dict[str, Any] | None = None
            super().__init__()

        # -- shared measurements, none of which mutate the plan ------------
        def _keep(self, fn):
            keep = self._aim_cell
            out = fn()
            self._aim_cell = keep
            return out

        def _refill_reach(self, shape):
            live = {c for c, sig in self.mark.items() if sig in self.refill_marks}
            if not live:
                return None, None
            step, d = self._keep(lambda: self._walk_far(shape, lambda c: c in live))
            return (step, d) if step is not None else (None, None)

        def _goal_reach(self, shape):
            g = self.goal
            if g is None:
                return None
            step, d = self._keep(
                lambda: self._walk_far(shape, lambda c: abs(c[0] - g[0]) + abs(c[1] - g[1]) == 1))
            return None if step is None else d + 1

        def _tank_full(self) -> int:
            return self.bar_full // self.bar_drop if self.bar_drop else 0

        # -- the variants ---------------------------------------------------
        def _refuel(self, shape):
            v = self.v
            if v == 11:
                return None
            if v in (0, 5, 6):
                return super()._refuel(shape)
            step, d = self._refill_reach(shape)
            if step is None:
                return None
            left = self.moves_left()
            full = self._tank_full()
            if v in (9, 10) and d <= 1 and full and left < full:
                return step
            if v in (2, 4) and full and left > (max(3, full // 3) if v == 2 else max(3, full // 2)):
                return None
            slack = 3 if v in (2, 3, 7, 8, 10) else (2 if v == 4 else 1)
            return step if left <= d + slack else None

        def _plan(self, shape):
            step = super()._plan(shape)
            v = self.v
            tag = self.reason.split("[")[0]
            if v in (5, 8) and tag == "tread":
                rstep, rd = self._refill_reach(shape)
                if rstep is not None and self.moves_left() <= rd + 2:
                    self.census["tread"] -= 1
                    self._say("refuel-tread")
                    return rstep
            if v in (6, 7, 8, 10) and tag == "win":
                gd = self._goal_reach(shape)
                if gd is not None and gd > self.moves_left():
                    rstep, rd = self._refill_reach(shape)
                    if rstep is not None and rd < self.moves_left():
                        self.census["win"] -= 1
                        self._say("refuel-win")
                        return rstep
            return step

        # -- variant 0's instrument, which changes no decision --------------
        def propose(self, frames, obs):
            out = super().propose(frames, obs)
            if self.v == 0 and self.pos is not None:
                shape = (64, 64)
                _s, rd = self._refill_reach(shape)
                self.trace.append({
                    "tick": self.tick, "why": self.reason.split("[")[0],
                    "left": self.moves_left(), "rd": rd, "gd": self._goal_reach(shape),
                    "pos": self.pos, "stood": len(self.stood),
                    "nrefill": len({c for c, s in self.mark.items() if s in self.refill_marks}),
                    "goal": self.goal is not None, "tgt": self.target is not None,
                })
                self.snap = {
                    "stood": set(self.stood), "seen": dict(self.seen), "walls": set(self.walls),
                    "goal": self.goal, "start": self.start, "pitch": self.pitch,
                    "full": self._tank_full(),
                    "refills": {c for c, s in self.mark.items() if s in self.refill_marks},
                }
            return out

    return V()


def _lower_bound(snap: dict[str, Any], tool) -> dict[str, Any]:
    """Shortest fuel-feasible start->goal route on the map the tool finished with.

    Tokens are ignored, so this is a LOWER BOUND on what any route could cost, not a plan.
    """
    if not snap or snap.get("goal") is None or snap.get("start") is None:
        return {"lb": None}
    goal, start, full = snap["goal"], snap["start"], snap["full"] or 21
    open_cells = (set(snap["stood"]) | set(snap["seen"])) - set(snap["walls"])
    refills = set(snap["refills"])
    plain = len(open_cells)
    q = deque([(start, full, 0)])
    best: dict[tuple[Any, int], int] = {(start, full): 0}
    ans = None
    while q:
        c, f, d = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (c[0] + dy, c[1] + dx)
            if nb == goal:
                ans = d + 1 if ans is None else min(ans, d + 1)
                continue
            if nb not in open_cells or f <= 1:
                continue
            nf = full if nb in refills else f - 1
            if best.get((nb, nf), 1 << 30) <= d + 1:
                continue
            best[(nb, nf)] = d + 1
            q.append((nb, nf, d + 1))
    return {"lb": ans, "open": plain, "refills": len(refills), "full": full}


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    arg = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    variant = (arg - 1) % NVAR

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    tools = default_tools()
    fog = _mk(variant)
    tools = [fog if t.name == "fogscout" else t for t in tools]

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(tools, _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    lvl = 0
    prev = None
    per_level: Counter[int] = Counter()
    deaths: Counter[int] = Counter()
    death_ticks: list[int] = []
    census7: Counter[str] = Counter()
    banked_trace: list[dict[str, Any]] = []
    banked_snap: dict[str, Any] | None = None
    banked_census: Counter[str] = Counter()
    n = 0
    print(f"v{variant} start", flush=True)
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        n += 1
        now = int(getattr(obs, "levels_completed", 0) or 0)
        g = np.array(obs.frame[-1], dtype=np.int16)
        if prev is not None and now == lvl and int((g != prev).sum()) > 2048:
            deaths[lvl] += 1
            if lvl == 6:
                death_ticks.append(per_level[6])
        prev = g
        per_level[lvl] += 1
        if lvl == 6:
            census7[str(getattr(fog, "reason", "?")).split("[")[0]] += 1
        if now > lvl:
            # ⛔ bank BEFORE the level-up wipes the tool's state (rule: a counter
            # reset by the very event being measured reads as "it never happened").
            if lvl == 6:
                banked_trace = list(fog.trace)
                banked_snap = fog.snap
                banked_census = Counter(census7)
            lvl = now
        if n % 60 == 0:
            print(f"v{variant} n={n} lvl={lvl + 1} l7={per_level[6]}", flush=True)
    if lvl == 6 and not banked_census:
        banked_trace, banked_snap, banked_census = list(fog.trace), fog.snap, Counter(census7)
    out: dict[str, Any] = {
        "arg": arg, "v": variant, "levels": lvl, "total": n, "lvl7": per_level[6],
        "deaths7": deaths[6], "deathat": death_ticks,
        "why": dict(banked_census.most_common(8)),
    }
    if variant == 0:
        out.update(_lower_bound(banked_snap or {}, fog))
        with open(f"/tmp/ls20fan_trace_{arg}.json", "w") as fh:
            json.dump(banked_trace, fh, default=str)
    print("RESULT " + json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
