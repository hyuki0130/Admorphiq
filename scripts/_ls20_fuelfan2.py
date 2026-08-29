"""ls20 level 7, second wave: the slack optimum, and recognising a refill WITHOUT touching it.

Purpose. Wave one (`_ls20_fuelfan.py`) established, deterministically over 24 runs, that
`_refuel`'s zero-slack rule (`left <= dist + 1`) is the single biggest lever: slack 3 takes
level 7 from 303 to 239 actions. Its variant-0 trace then showed where the rest goes:

  the tank reaches ZERO at ticks 10, 32, 54, 143, 225 — FIVE dry deaths, not the one the
  full-screen-overlay detector could see — and the FIRST KNOWN REFILL CELL appears at tick 73.
  So three of the five deaths happen before the tool has any idea what a refill looks like,
  and `_refuel`'s `live` set is empty for them no matter what its thresholds are.

  attempt 1 (155 actions) is all exploration: map 59, tread 56, mark 21, stood 1 -> 65.
  attempt 2 (136 actions) discovers NOTHING: win 87, refuel 30, press 11, stood 65 -> 65.

The hypotheses this wave tests:

  0  control — slack 3, low gate full//3 (wave one's winner, expected 239)
  1  slack 2          2  slack 4          3  slack 5          4  slack 6
  5  slack 3, low gate at half a tank rather than a third
  6  THE GAUGE-COLOUR PRIOR: the fuel pickup is drawn in the SAME colour as the fuel gauge
     (both colour 11 here), which is a game-design convention and not an ls20 fact. A mark
     whose every drawn pixel is the gauge's own colour is treated as a refill on SIGHT, so
     the tool can divert to one before it has ever stepped on one. Baseline thresholds.
  7  6 + slack 3      8  6 + slack 5      10  6 + slack 3 + no low gate
  9  slack 3 + top up whenever a refill is one step away and the tank is not full
 11  slack 3 + an ABSOLUTE feasibility rule: when the plan's own distance exceeds the tank
     and a refill is reachable within it, refuel regardless of every threshold.

Expected feedback. `lvl7` is the metric (303 baseline, 239 wave-one best, 186 = human). `dry`
counts the ticks the tank sat at zero, i.e. the real death count, which the overlay detector
undercounts 5-to-1; a variant that lowers `lvl7` without lowering `dry` is buying time some
other way, and one that loses the level (`levels` < 7) refutes its threshold outright.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any


NVAR = 12
# (slack, low-gate divisor or 0 for none, gauge-colour prior, top-up-when-adjacent, absolute)
CFG: dict[int, tuple[int, int, bool, bool, bool]] = {
    0: (3, 3, False, False, False),
    1: (2, 3, False, False, False),
    2: (4, 3, False, False, False),
    3: (5, 3, False, False, False),
    4: (6, 3, False, False, False),
    5: (3, 2, False, False, False),
    6: (1, 3, True, False, False),
    7: (3, 3, True, False, False),
    8: (5, 3, True, False, False),
    9: (3, 3, False, True, False),
    10: (3, 0, True, False, False),
    11: (3, 3, False, False, True),
}


def _mk(variant: int):
    from admorphiq.tools.fogscout import FogScoutTool

    slack, gate, prior, topup, absolute = CFG[variant]

    class V(FogScoutTool):
        """FogScoutTool with one refuelling policy swapped in."""

        def __init__(self) -> None:
            self.dry = 0
            self.first_refill_tick: int | None = None
            self._was_zero = False
            super().__init__()

        def _tank_full(self) -> int:
            return self.bar_full // self.bar_drop if self.bar_drop else 0

        def _live(self) -> set:
            """Cells worth diverting to for fuel.

            ⛔ The prior is kept OUT of ``refill_marks`` deliberately: that set also
            suppresses a mark from the learn-this-mark worklist, so seeding it with a guess
            would stop the tool ever confirming the guess by standing on one.
            """
            live = {c for c, sig in self.mark.items() if sig in self.refill_marks}
            if prior and self.bar_color is not None:
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
            if topup and d <= 1 and full and left < full:
                return step
            if absolute and self._plan_dist is not None and self._plan_dist > left and d < left:
                return step
            if gate and full and left > max(3, full // gate):
                return None
            return step if left <= d + slack else None

        def propose(self, frames, obs):
            out = super().propose(frames, obs)
            if self.bar_drop:
                z = self.moves_left() == 0
                if z and not self._was_zero:
                    self.dry += 1
                self._was_zero = z
            if self.first_refill_tick is None and self._live():
                self.first_refill_tick = self.tick
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
            # ⛔ bank BEFORE the level-up resets the tool, or the counters read zero.
            if lvl == 6:
                banked = {"dry": fog.dry, "first": fog.first_refill_tick,
                          "why": dict(census7.most_common(7))}
            lvl = now
        if n % 60 == 0:
            print(f"v{variant} n={n} lvl={lvl + 1} l7={per_level[6]} dry={fog.dry}", flush=True)
    if lvl == 6 and not banked:
        banked = {"dry": fog.dry, "first": fog.first_refill_tick,
                  "why": dict(census7.most_common(7))}
    out = {"arg": arg, "v": variant, "cfg": list(CFG[variant]), "levels": lvl,
           "total": n, "lvl7": per_level[6], **banked}
    print("RESULT " + json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
