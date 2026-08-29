"""ls20 level 7, third wave: what is left after the refuel slack, and does the prior pay if bounded.

Purpose. Wave two measured the slack axis to a PLATEAU — slack 2/3/4/5/6 all land at 237-239
actions against the baseline's 303, all cutting the dry-tank count 5 -> 4 — so the lever is
"more than zero slack", not a tuned number. It also measured two things that do NOT pay as
written: the gauge-colour prior finds a refill at tick 4 instead of tick 72 and cuts deaths to
3, yet COSTS actions (265 vs 239) because it then diverts all game (refuel 43 vs 18); and
topping up whenever a refill is adjacent is far worse (382).

What is left at 237, by clause: map 59, tread 56, win 38, mark 22, press 17, refuel 17, and
about 28 in `look`. `win` is tried FIRST in `_plan`, so map and tread only ever run because no
winning route exists yet — they are not waste by construction, which is why this wave attacks
the three tunables around them instead of the clauses themselves.

  0  control, slack 4                     10  slack = max(3, full//5), the generic form of 4
  1  _STALE_LOOK 120 (re-look half as often)     2  _STALE_LOOK 30 (twice as often)
  3  _PURSUIT_CAP 15                             4  _PURSUIT_CAP 60
  5  _SIGHT_RETRY 100
  6  do not START a map/tread walk on fumes: below 4 moves, refuel instead
  7  BOUNDED PRIOR: the gauge-colour guess is used only while no refill has been CONFIRMED,
     so it buys the early deaths without paying the all-game diversion that sank wave two's 6
  8  7 at slack 5                               9  7 + _STALE_LOOK 120
 11  7 + 6 — the bounded prior and the fumes rule together

Expected feedback. 303 baseline, 237 the wave-two best, 186 the human baseline and the point
at which ls20 scores 1.0000. Anything at or below 237 with `levels`=7 is a real gain; a
variant that raises `dry` while lowering `lvl7` is trading lives for time and must be read
against the fact that the level clears with one life in hand.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any

NVAR = 12
# slack, prior-until-confirmed, fumes rule, stale_look, pursuit_cap, sight_retry, generic-slack
CFG: dict[int, tuple[int, bool, bool, int, int, int, bool]] = {
    0:  (4, False, False, 60, 30, 50, False),
    1:  (4, False, False, 120, 30, 50, False),
    2:  (4, False, False, 30, 30, 50, False),
    3:  (4, False, False, 60, 15, 50, False),
    4:  (4, False, False, 60, 60, 50, False),
    5:  (4, False, False, 60, 30, 100, False),
    6:  (4, False, True, 60, 30, 50, False),
    7:  (4, True, False, 60, 30, 50, False),
    8:  (5, True, False, 60, 30, 50, False),
    9:  (4, True, False, 120, 30, 50, False),
    10: (4, False, False, 60, 30, 50, True),
    11: (4, True, True, 60, 30, 50, False),
}


def _mk(variant: int):
    from admorphiq.tools import fogscout as F

    slack, prior, fumes, stale, pursuit, sight, generic = CFG[variant]
    F._STALE_LOOK = stale
    F._PURSUIT_CAP = pursuit
    F._SIGHT_RETRY = sight

    class V(F.FogScoutTool):
        """FogScoutTool with one post-slack policy swapped in."""

        def __init__(self) -> None:
            self.dry = 0
            self._was_zero = False
            super().__init__()

        def _tank_full(self) -> int:
            return self.bar_full // self.bar_drop if self.bar_drop else 0

        def _live(self) -> set:
            live = {c for c, sig in self.mark.items() if sig in self.refill_marks}
            if prior and not live and self.bar_color is not None:
                live |= {c for c, sig in self.mark.items()
                         if sig and {p[2] for p in sig} == {self.bar_color}}
            return live

        def _refuel(self, shape):
            live = self._live()
            if not live:
                return None
            keep = self._aim_cell
            step, d = self._walk_far(shape, lambda c: c in live)
            self._aim_cell = keep
            if step is None:
                return None
            left, full = self.moves_left(), self._tank_full()
            if fumes and left <= 3 and d < left:
                return step
            if full and left > max(3, full // 3):
                return None
            s = max(3, full // 5) if (generic and full) else slack
            return step if left <= d + s else None

        def propose(self, frames, obs):
            out = super().propose(frames, obs)
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
                banked = {"dry": fog.dry, "why": dict(census7.most_common(7))}
            lvl = now
        if n % 60 == 0:
            print(f"v{variant} n={n} lvl={lvl + 1} l7={per_level[6]} dry={fog.dry}", flush=True)
    if lvl == 6 and not banked:
        banked = {"dry": fog.dry, "why": dict(census7.most_common(7))}
    out = {"arg": arg, "v": variant, "cfg3": list(CFG[variant]), "levels": lvl,
           "total": n, "lvl7": per_level[6], **banked}
    print("RESULT " + json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
