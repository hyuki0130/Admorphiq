"""ls20 level 7: can the tool INFER a changer's rule instead of pressing it out?

Purpose. The census (`scripts/_ls20_census.py`) decomposed the 231 with engine ground truth:
10 keymaze handover, ~146 discovery, 75 execution, against a human 186 and an oracle execution of
~61. It also showed WHERE the discovery goes — the tool presses the three changers over and over to
fill LOOKUP TABLES, and one of those presses (seven in a row on the mover's lane) is what empties
the tank and costs the level its fourth life.

So this fan asks whether the same tables can be INFERRED from fewer presses, by two rules that are
checked before they are used, exactly as `_motion_of` and `_commutes` already are:

  * CYCLE CLOSURE — an axis map that is injective and whose observed pairs form one chain over the
    values the tool has ever seen must close that chain: a permutation of a finite set has no other
    completion. Costs the tool the press that only re-learns the wrap-around.
  * MOTION CONJUGATION — `_rules` already conjugates two mask-axis marks that commute, but it
    EXCLUDES the mark that reduced to a rigid motion, which is the one whose table is cheap to
    apply. If B commutes with a believed motion M then B(M(m)) = M(B(m)), so one observation of B
    covers all four rotations of the glyph.

  0 control                       4 1 + 3
  1 colour-cycle closure          5 fuel-safe press (never press beyond the tank's reach of a
  2 motion conjugation, strict      known refill — the measured cause of the fourth death)
  3 motion conjugation, permissive  6 1 + 3 + 5           7 mask-cycle closure as well

Expected feedback. Arm 0 must return 7 levels and [17,101,63,66,67,100,231]; anything else means the
harness is not the shipped one and no other arm is readable. An arm below 231 with levels=7 is a
real gain and must then be landed in the tool file and re-verified with `scripts/_ls20_verify.py` —
a subclass is not the shipped code. An arm at exactly 231 is INERT, which for an inference rule
means it never fired, and the firing counter says which.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

NVAR = 8


def _mk(v: int):
    from admorphiq.tools.fogscout import _MOTIONS, FogScoutTool, _norm

    close_colour = v in (1, 4, 6, 7)
    close_mask = v == 7
    conj = 2 if v == 2 else (1 if v in (3, 4, 6) else 0)
    safe_press = v in (5, 6)

    class V(FogScoutTool):
        """FogScoutTool with one inference rule swapped in; everything else shipped."""

        def __init__(self) -> None:
            self.fired = {"colour": 0, "mask": 0, "conj": 0, "safepress": 0}
            super().__init__()

        @staticmethod
        def _close(m: dict[Any, Any]) -> bool:
            if len(m) < 2 or len(set(m.values())) != len(m):
                return False
            vals = set(m) | set(m.values())
            src = vals - set(m)
            dst = vals - set(m.values())
            if len(src) != 1 or len(dst) != 1:
                return False
            m[next(iter(src))] = next(iter(dst))
            return True

        def _rules(self):
            rules = super()._rules()
            if close_colour or close_mask:
                for _sig, (axis, m) in rules.items():
                    if axis == "colour" and close_colour and self._close(m):
                        self.fired["colour"] += 1
                    elif axis == "mask" and close_mask and self._close(m):
                        self.fired["mask"] += 1
            if conj:
                motions = [t for a, t in rules.values() if a == "motion"]
                for _sig, (axis, m) in rules.items():
                    if axis != "mask":
                        continue
                    for name in motions:
                        f = _MOTIONS[name]
                        agree = 0
                        add: dict[Any, Any] = {}
                        bad = False
                        for k, val in list(m.items()):
                            fk, fv = _norm(f(k)), _norm(f(val))
                            if fk in m:
                                if m[fk] != fv:
                                    bad = True
                                    break
                                agree += 1
                            else:
                                add[fk] = fv
                        if bad or not add or (conj == 2 and agree < 1):
                            continue
                        m.update(add)
                        self.fired["conj"] += 1
            return rules

        def _plan(self, shape):
            step = super()._plan(shape)
            if safe_press and self.reason.split("[")[0] == "press":
                live = {c for c, sig in self.mark.items() if sig in self.refill_marks}
                if live:
                    keep = self._aim_cell
                    _s, d = self._walk_far(shape, lambda c: c in live)
                    self._aim_cell = keep
                    full = self.bar_full // self.bar_drop if self.bar_drop else 0
                    if _s is not None and self.moves_left() <= d + max(3, full // 5):
                        fuel = self._refuel(shape)
                        if fuel is not None:
                            self.census["press"] -= 1
                            self.fired["safepress"] += 1
                            self._say("refuel")
                            return fuel
            return step

    return V()


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    arg = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    v = (arg - 1) % NVAR

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    fog = _mk(v)
    tools = [fog if t.name == "fogscout" else t for t in default_tools()]
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.observation_space
    agent = UnifiedAgent(tools, _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    human = list(getattr(info, "baseline_actions", []) or [])
    prev, total, this = int(obs.levels_completed), 0, 0
    per: list[int] = []
    restart = bool(getattr(agent, "restart_on_game_over", False))
    while total < 4000:
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        if not isinstance(act, GameAction):
            break
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        if obs is None:
            break
        total += 1
        this += 1
        cur = int(obs.levels_completed)
        if cur > prev:
            for _ in range(cur - prev):
                per.append(this)
                this = 0
            prev = cur
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            this += 1
            if obs is None:
                break
    weight = sum(range(1, len(human) + 1))
    got = 0.0
    for i, h in enumerate(human, start=1):
        mine = per[i - 1] if i - 1 < len(per) else 0
        got += i * (min(h / mine, 1.0) ** 2 if mine else 0.0)
    print(json.dumps({"arg": arg, "v": v, "levels": prev, "total": total, "per": per,
                      "game_score": round(got / weight, 6), "fired": fog.fired,
                      "census": dict(fog.census.most_common(12))}), flush=True)


if __name__ == "__main__":
    main()
