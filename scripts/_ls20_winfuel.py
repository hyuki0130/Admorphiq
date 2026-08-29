"""ls20 level 7: the tool walks AWAY from a three-step win to top up a tank it does not need.

Found by pricing the execution phase tick by tick (`_ls20_gap32.py`'s trace, ticks 168-222). The
winning route's remaining length is printed beside the tank on every tick, and three times it turns
the wrong way:

    t=214  refuel   win=3  left=7      <- three steps from the end, seven moves in the tank
    t=215  refuel   win=4  left=6
    t=216  refuel   win=5  left=5
    t=217  win      win=6  left=21     <- refilled, now SIX steps out instead of three

The cause is one missing number rather than a bad rule. `propose` skips the tank only when
"the plan's target distance is KNOWN and within reach"; `_walk` sets that distance and `_search`
does not, so on every tick the winning route is being executed `_plan_dist` is None and the
cautious branch runs. `_refuel` then fires on its own terms — tank below a third, refill closer
than the tank is deep — with no idea that the level is about to end.

Two ways to give it the number, and one deeper change that subsumes both:

  0  control (expect 237)
  1  the win branch reports its ROUTE LENGTH as the plan distance, so the existing skip applies
  2  a hard skip: never divert while a winning route exists that the tank already covers
  3  the win search itself becomes FUEL-AWARE — (cell, token, tank) with a known refill cell
     resetting the tank — so the route returned is one the tank can actually complete, and its
     length is reported as the plan distance. Falls back to the plain search when no fuelled
     route exists, so a level can never be lost to it.
  4  1 + 3        5  control repeated (determinism)

Expected feedback: 237 is the control and 186 the human baseline at which ls20 scores 1.0000. A
variant below 237 with `levels` = 7 is a real gain. ⛔ `levels` must stay 7: running dry costs a
life AND resets the token to the level's start, so a refuel rule that is too brave loses far more
than it saves.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, deque
from typing import Any

NVAR = 6
# report_win_dist, hard_skip, fuel_aware
CFG: dict[int, tuple[bool, bool, bool]] = {
    0: (False, False, False),
    1: (True,  False, False),
    2: (False, True,  False),
    3: (False, False, True),
    4: (True,  False, True),
    5: (False, False, False),
}


def _mk(variant: int):
    from admorphiq.tools.fogscout import _MOVE_IDS, FogScoutTool

    report, hard, fuelled = CFG[variant]

    class V(FogScoutTool):
        """FogScoutTool whose winning route knows how long it is, and optionally how it is fuelled."""

        def __init__(self) -> None:
            self.dry = 0
            self._was_zero = False
            self._win_len: int | None = None
            super().__init__()

        def _route(self, shape) -> tuple[int | None, int | None]:
            """(first action, length) of the winning route in (cell, token) space."""
            if self.pos is None or self.tok is None or self.goal is None or self.target is None:
                return None, None
            q: deque[tuple[Any, Any, int | None, int]] = deque([(self.pos, self.tok, None, 0)])
            seen = {(self.pos, self.tok)}
            acts = [a for a in self.dirs if a in _MOVE_IDS]
            while q:
                c, t, first, d = q.popleft()
                for a in acts:
                    nb = self._step_to(c, a)
                    head = a if first is None else first
                    if nb == self.goal:
                        if t == self.target:
                            return head, d + 1
                        continue
                    if not self._passable(nb, shape):
                        continue
                    nt = self._tok_after(nb, t)
                    if nt is None or (nb, nt) in seen:
                        continue
                    seen.add((nb, nt))
                    q.append((nb, nt, head, d + 1))
            return None, None

        def _fuel_route(self, shape) -> tuple[int | None, int | None]:
            """The same route, carrying the tank: a known refill cell fills it back up."""
            if self.pos is None or self.tok is None or self.goal is None or self.target is None:
                return None, None
            full = self.bar_full // self.bar_drop if self.bar_drop else 0
            if not full:
                return None, None
            fills = {c for c, sig in self.mark.items() if sig in self.refill_marks}
            start = min(self.moves_left(), full)
            q: deque[tuple[Any, Any, int, int | None, int]] = deque(
                [(self.pos, self.tok, start, None, 0)])
            seen = {(self.pos, self.tok, start)}
            acts = [a for a in self.dirs if a in _MOVE_IDS]
            while q:
                c, t, f, first, d = q.popleft()
                for a in acts:
                    nb = self._step_to(c, a)
                    head = a if first is None else first
                    if nb == self.goal:
                        if t == self.target and f >= 1:
                            return head, d + 1
                        continue
                    if not self._passable(nb, shape):
                        continue
                    nf = full if nb in fills else f - 1
                    if nf < 0:
                        continue
                    nt = self._tok_after(nb, t)
                    if nt is None:
                        continue
                    key = (nb, nt, nf)
                    if key in seen:
                        continue
                    seen.add(key)
                    q.append((nb, nt, nf, head, d + 1))
            return None, None

        def _plan(self, shape):
            self._win_len = None
            if (report or hard or fuelled) and self.goal is not None and self.target is not None:
                step, dist = (self._fuel_route(shape) if fuelled else (None, None))
                if step is None:
                    step, dist = self._route(shape)
                if step is not None:
                    self._win_len = dist
                    self._say("win")
                    if report or fuelled:
                        self._plan_dist = dist
                    return step
            return super()._plan(shape)

        def propose(self, frames, obs):
            keep = None
            if hard:
                keep = self._refuel

                def _guard(shape):
                    if self._win_len is not None and self._win_len <= self.moves_left():
                        return None
                    return keep(shape)

                self._refuel = _guard  # type: ignore[method-assign]
            try:
                out = super().propose(frames, obs)
            finally:
                if hard:
                    self._refuel = keep  # type: ignore[method-assign]
            if self.bar_drop:
                z = self.moves_left() == 0
                if z and not self._was_zero:
                    self.dry += 1
                self._was_zero = z
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
        # ⛔ `> lvl`, never `!=` — a collapse and a clear are the same boolean (rule 7f).
        if now > lvl:
            lvl = now
        if n % 120 == 0:
            print(f"v{variant} n={n} lvl={lvl + 1} l7={per_level[6]}", flush=True)
    out = {"arg": arg, "v": variant, "cfg": list(CFG[variant]), "levels": lvl, "total": n,
           "lvl7": per_level[6], "dry": fog.dry, "why": dict(fog.census.most_common(8))}
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
