"""ls20 level 7: WHY does no winning route exist between tick 138 and tick 170?

The prior round measured 237 = 12 handover + 170 discovery + 55 execution, and named the open
gap precisely: the three changer tables close at ticks 67, 69 and 138, yet the joint (cell, token)
search does not return a route until 170. "Everything the route needs is known at 138" is the
CLAIM; it has never been checked, and there are two independent things a route needs.

This instrument checks both, every tick, separately:

  reach   can the avatar walk to a cell one step from the target, ignoring the token entirely?
  clos    is the demanded token in the CLOSURE of the rules the tool currently believes,
          starting from the token it is currently holding, ignoring geometry entirely?

A route exists iff both hold (plus their interaction). So the tick at which each becomes true
says which of the two is the critical path, and the answer selects the fix. If `clos` turns true
only at ~170, the gap is token learning and the rule machinery is the target. If `clos` is true
at 138 and `reach` is late, the gap is the MAP and exploration is the target. If both are true
well before 170, the search itself is refusing a route it could return, and that is a defect.

Expected feedback: the first tick of `reach`, of `clos` and of `win`, on the same clock.

Variants 1-9 are candidate fixes, all inside the tool's rule/plan layer, measured on level-7
action count with `levels` held at 7:

  0  instrument only (control; expect 237, win@170)
  1  motion-conjugated mask tables, VERIFIED (a mask permutation commutes with a known rigid
     motion, so m[M(x)] = M(m[x]) — accepted only where an overlapping case already agrees)
  2  the same, UNVERIFIED (no overlapping case required)
  3  the existing mask x mask commutation loop run 16 times instead of 4
  4  press-first: once the goal and the demanded token are known but the token is NOT in the
     closure, take the nearest unmeasured press ahead of frontier/mark/tread
  5  2 + 4        6  2 + 3        7  2 + 3 + 4        9  1 + 4
  8  control repeated (determinism check — two arms of the fan must agree exactly)
"""
from __future__ import annotations

import json
import sys
from collections import Counter, deque
from typing import Any

NVAR = 10
# conj_verified, conj_unverified, deep_commute, press_first
CFG: dict[int, tuple[bool, bool, bool, bool]] = {
    0: (False, False, False, False),
    1: (True,  False, False, False),
    2: (False, True,  False, False),
    3: (False, False, True,  False),
    4: (False, False, False, True),
    5: (False, True,  False, True),
    6: (False, True,  True,  False),
    7: (False, True,  True,  True),
    8: (False, False, False, False),
    9: (True,  False, False, True),
}


def _mk(variant: int):
    from admorphiq.tools.fogscout import _MOTIONS, _MOVE_IDS, FogScoutTool, _norm

    conj_ver, conj_unver, deep, press_first = CFG[variant]

    class V(FogScoutTool):
        """FogScoutTool with the instrument, and at most one rule/plan policy swapped in."""

        def __init__(self) -> None:
            self.trace: list[dict[str, Any]] = []
            self.win_at: int | None = None
            self.reach_at: int | None = None
            self.clos_at: int | None = None
            self.dry = 0
            self._was_zero = False
            super().__init__()

        # -- instrument -----------------------------------------------------

        def _win_route(self, shape) -> int | None:
            """Length of the winning route, by the same traversal `_search` runs."""
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

        def _goal_reachable(self, shape) -> bool:
            """Can the avatar stand one step from the target, token ignored?"""
            if self.pos is None or self.goal is None:
                return False
            acts = [a for a in self.dirs if a in _MOVE_IDS]
            cells = set(self._reach(shape))
            cells.add(self.pos)
            return any(self._step_to(c, a) == self.goal for c in cells for a in acts)

        def _closure(self, cap: int = 3000) -> set:
            """Every token the believed rules can reach from the one held, geometry ignored."""
            if self.tok is None:
                return set()
            seen = {self.tok}
            q = [self.tok]
            while q and len(seen) < cap:
                t = q.pop()
                for sig in list(self.kind):
                    nt = self._factored(sig, t)
                    if nt is None:
                        nt = self.kind[sig].get(t)
                    if nt is not None and nt not in seen:
                        seen.add(nt)
                        q.append(nt)
            return seen

        # -- candidate fixes ------------------------------------------------

        def _rules(self):
            base = super()._rules()
            if not (conj_ver or conj_unver or deep):
                return base
            ver = sum(len(v) for v in self.kind.values())
            if getattr(self, "_xver", None) == ver:
                return self._xcache
            out = {sig: (axis, dict(tab) if isinstance(tab, dict) else tab)
                   for sig, (axis, tab) in base.items()}
            if deep:
                movers = [s for s, (ax, _) in out.items() if ax == "mask"]
                for _ in range(16):
                    grew = False
                    for a_sig in movers:
                        for b_sig in movers:
                            if a_sig == b_sig:
                                continue
                            a, b = out[a_sig][1], out[b_sig][1]
                            if not self._commutes(a, b):
                                continue
                            for m in list(b):
                                ab = a.get(b[m])
                                if ab is None or a.get(m) is None or a[m] in b:
                                    continue
                                b[a[m]] = ab
                                grew = True
                    if not grew:
                        break
            if conj_ver or conj_unver:
                names = [tab for ax, tab in out.values() if ax == "motion"]
                for _sig, (ax, tab) in out.items():
                    if ax != "mask":
                        continue
                    for mname in names:
                        fn = _MOTIONS[mname]
                        ok, agree = True, 0
                        for x in list(tab):
                            mx = _norm(fn(x))
                            if mx in tab:
                                agree += 1
                                if tab[mx] != _norm(fn(tab[x])):
                                    ok = False
                                    break
                        if not ok or (conj_ver and agree == 0):
                            continue
                        for _ in range(4):
                            for x in list(tab):
                                mx = _norm(fn(x))
                                if mx not in tab:
                                    tab[mx] = _norm(fn(tab[x]))
            self._xver, self._xcache = ver, out
            return out

        def _plan(self, shape):
            if press_first and self.goal is not None and self.target is not None and self.kind:
                if self._search(shape, lambda c, t: c == self.goal and t == self.target, False) is None \
                        and self.target not in self._closure():
                    press = self._search(shape, lambda c, t: False, True)
                    if press is not None:
                        self._say("press-first")
                        return press
            return super()._plan(shape)

        def propose(self, frames, obs):
            out = super().propose(frames, obs)
            if self.bar_drop:
                z = self.moves_left() == 0
                if z and not self._was_zero:
                    self.dry += 1
                self._was_zero = z
            if self.pos is not None:
                wl = self._win_route((64, 64))
                if wl is not None and self.win_at is None:
                    self.win_at = self.tick
                rc = self._goal_reachable((64, 64))
                if rc and self.reach_at is None:
                    self.reach_at = self.tick
                ct = self.target is not None and self.target in self._closure()
                if ct and self.clos_at is None:
                    self.clos_at = self.tick
                if variant == 0:
                    self.trace.append({
                        "t": self.tick, "why": self.reason.split("[")[0], "win": wl,
                        "reach": int(rc), "clos": int(ct),
                        "nclos": len(self._closure()), "left": self.moves_left(),
                        "stood": len(self.stood), "seen": len(self.seen),
                        "kinds": {str(sorted(s)[:1]): len(v) for s, v in self.kind.items()},
                        "axes": {str(sorted(s)[:1]): a for s, (a, _) in self._rules().items()},
                        "goal": int(self.goal is not None), "tgt": int(self.target is not None),
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
    holder: Counter[str] = Counter()
    banked: dict[str, Any] = {}
    n = 0
    print(f"v{variant} start", flush=True)
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        if lvl == 6:
            holder[str(agent._current)] += 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        n += 1
        # ⛔ `> lvl`, never `!=` — a collapse and a clear look identical to a boolean (rule 7f).
        now = int(getattr(obs, "levels_completed", 0) or 0)
        per_level[lvl] += 1
        if now > lvl:
            if lvl == 6:
                banked = {"dry": fog.dry, "winat": fog.win_at, "reachat": fog.reach_at,
                          "closat": fog.clos_at, "held": dict(holder.most_common(4))}
            lvl = now
        if n % 120 == 0:
            print(f"v{variant} n={n} lvl={lvl + 1} l7={per_level[6]}", flush=True)
    if lvl == 6 and not banked:
        banked = {"dry": fog.dry, "winat": fog.win_at, "reachat": fog.reach_at,
                  "closat": fog.clos_at, "held": dict(holder.most_common(4))}
    if variant == 0:
        with open(f"/tmp/ls20gap32_trace_{arg}.json", "w") as fh:
            json.dump(fog.trace, fh, default=str)
    out = {"arg": arg, "v": variant, "levels": lvl, "total": n, "lvl7": per_level[6], **banked}
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
