"""ls20 level 7: the shortest route is 10 actions and the tool spends 237 — where do the rest go?

Purpose. The fuel axis is closed (`scripts/_ls20_fuelfan{,2,3}.py`): slack in `_refuel` takes
level 7 from 303 to 237, every slack from 2 to 6 lands on the same plateau, and a
fuel-constrained BFS over the map the tool FINISHES with puts the start ten steps from the
goal. So ~227 of the 237 are not travel. This probe finds out what they are, and tests the
cheap policies that would remove them.

Variant 0 is the instrument and changes no decision. Each tick it records whether a WINNING
ROUTE EXISTS at all — the same joint (cell, token) search `_plan` runs — and how long that
route is, alongside the learning state (marks seen, changer tables closed, cells stood, goal
and target known). That answers the question directly: the actions before the first tick a win
route exists are the price of DISCOVERY, and the ones after are the price of EXECUTION.

  0  instrument only (expect 237)
  1  cap `map` at 40 actions — does the frontier sweep need all 59?
  2  cap `tread` at 30 actions — the defended clause, bounded rather than gated
  3  stop treading once 60 cells have been stood on
  4  stop treading once 45 cells have been stood on
  5  explore only where the tank can still reach a known refill (safe exploration)
  6  once the goal is known, break frontier ties toward it
  7  cap `look` — never patrol while a winning route exists
  8  3 + 6      9  4 + 6      10  6 + 7      11  2 + 6 + 7

Expected feedback. 237 is the control and 186 the human baseline at which ls20 scores 1.0000.
A variant below 237 with `levels`=7 is a real gain. The instrument's `win@` — the first tick a
winning route exists — is the number that decides where any further work belongs: if it is
late, the cost is discovery and the exploration clauses are the target; if it is early, the
cost is execution and the fuel/token machinery is.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, deque
from typing import Any

NVAR = 12
# map_cap, tread_action_cap, tread_stood_cap, safe_explore, goal_bias, no_look_on_win
CFG: dict[int, tuple[int, int, int, bool, bool, bool]] = {
    0:  (0, 0, 0, False, False, False),
    1:  (40, 0, 0, False, False, False),
    2:  (0, 30, 0, False, False, False),
    3:  (0, 0, 60, False, False, False),
    4:  (0, 0, 45, False, False, False),
    5:  (0, 0, 0, True, False, False),
    6:  (0, 0, 0, False, True, False),
    7:  (0, 0, 0, False, False, True),
    8:  (0, 0, 60, False, True, False),
    9:  (0, 0, 45, False, True, False),
    10: (0, 0, 0, False, True, True),
    11: (0, 30, 0, False, True, True),
}


def _mk(variant: int):
    from admorphiq.tools.fogscout import _MOVE_IDS, FogScoutTool

    map_cap, tread_cap_a, tread_cap, safe, goal_bias, no_look = CFG[variant]

    class V(FogScoutTool):
        """FogScoutTool instrumented for where-the-actions-go, with one policy swapped in."""

        def __init__(self) -> None:
            self.trace: list[dict[str, Any]] = []
            self.win_at: int | None = None
            self.dry = 0
            self._was_zero = False
            super().__init__()

        def _win_route(self, shape) -> int | None:
            """Length of the winning route in (cell, token) space, or None if there is none.

            A copy of `_search`'s traversal carrying a depth, so the instrument reports the
            same availability the planner acts on and cannot disagree with it.
            """
            if self.pos is None or self.tok is None or self.goal is None or self.target is None:
                return None
            q: deque[tuple[Any, Any, int]] = deque([(self.pos, self.tok, 0)])
            seen = {(self.pos, self.tok)}
            acts = [a for a in self.dirs if a in _MOVE_IDS]
            while q:
                c, t, d = q.popleft()
                for a in acts:
                    nb = self._step_to(c, a)
                    if nb == self.goal:
                        if t == self.target:
                            return d + 1
                        continue
                    if not self._passable(nb, shape):
                        continue
                    nt = self._tok_after(nb, t)
                    if nt is None or (nb, nt) in seen:
                        continue
                    seen.add((nb, nt))
                    q.append((nb, nt, d + 1))
            return None

        def _refill_d(self, shape) -> int | None:
            live = {c for c, sig in self.mark.items() if sig in self.refill_marks}
            if not live:
                return None
            keep = self._aim_cell
            step, d = self._walk_far(shape, lambda c: c in live)
            self._aim_cell = keep
            return d if step is not None else None

        def _plan(self, shape):
            step = super()._plan(shape)
            tag = self.reason.split("[")[0]
            if (map_cap and tag == "map" and self.census["map"] > map_cap) or \
                    (tread_cap_a and tag == "tread" and self.census["tread"] > tread_cap_a):
                self.census[tag] -= 1
                self._say(f"{tag}-budgeted")
                alt = self._patrol(shape)
                return alt if alt is not None else step
            if tread_cap and tag == "tread" and len(self.stood) >= tread_cap:
                self.census["tread"] -= 1
                self._say("tread-capped")
                alt = self._patrol(shape)
                return alt if alt is not None else step
            if safe and tag in ("map", "tread"):
                rd = self._refill_d(shape)
                if rd is not None and self._plan_dist is not None \
                        and self._plan_dist + rd > self.moves_left():
                    self.census[tag] -= 1
                    self._say("unsafe-skip")
                    fuel = self._refuel(shape)
                    if fuel is not None:
                        return fuel
            if goal_bias and tag == "map" and self.goal is not None:
                g = self.goal
                keep = self._aim_cell
                near = self._walk(shape, lambda c: c not in self.stood and c not in self.give_up
                                  and abs(c[0] - g[0]) + abs(c[1] - g[1]) <= 3)
                self._aim_cell = keep
                if near is not None:
                    self._say("map-goalward")
                    return near
            if no_look and tag.startswith("look") and self._win_route(shape) is not None:
                self.census[tag] -= 1
                self._say("look-skipped")
                return step
            return step

        def propose(self, frames, obs):
            out = super().propose(frames, obs)
            if self.bar_drop:
                z = self.moves_left() == 0
                if z and not self._was_zero:
                    self.dry += 1
                self._was_zero = z
            if variant == 0 and self.pos is not None:
                wl = self._win_route((64, 64))
                if wl is not None and self.win_at is None:
                    self.win_at = self.tick
                self.trace.append({
                    "t": self.tick, "why": self.reason.split("[")[0], "win": wl,
                    "left": self.moves_left(), "stood": len(self.stood), "seen": len(self.seen),
                    "marks": len(self.mark), "kinds": len(self.kind), "inert": len(self.inert),
                    "refills": len(self.refill_marks), "goal": self.goal is not None,
                    "tgt": self.target is not None,
                })
            return out

    return V()


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    arg = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    variant = (arg - 1) % NVAR

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    fog = _mk(variant)
    tools = [fog if t.name == "fogscout" else t for t in default_tools()]

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(tools, _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    lvl = 0
    per_level: Counter[int] = Counter()
    census7: Counter[str] = Counter()
    banked: dict[str, Any] = {}
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
        per_level[lvl] += 1
        if lvl == 6:
            census7[str(fog.reason).split("[")[0]] += 1
        if now > lvl:
            if lvl == 6:
                banked = {"dry": fog.dry, "winat": fog.win_at,
                          "why": dict(census7.most_common(8))}
            lvl = now
        if n % 60 == 0:
            print(f"v{variant} n={n} lvl={lvl + 1} l7={per_level[6]}", flush=True)
    if lvl == 6 and not banked:
        banked = {"dry": fog.dry, "winat": fog.win_at, "why": dict(census7.most_common(8))}
    if variant == 0:
        with open(f"/tmp/ls20w227_trace_{arg}.json", "w") as fh:
            json.dump(fog.trace, fh, default=str)
    out = {"arg": arg, "v": variant, "cfg4": list(CFG[variant]), "levels": lvl,
           "total": n, "lvl7": per_level[6], **banked}
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
