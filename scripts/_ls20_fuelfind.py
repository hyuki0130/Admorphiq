"""ls20 level 7: the tool burns THREE LIVES before it owns a fuel model — can it find one sooner?

Purpose. The ground-truth census (`scripts/_ls20_census.py`) says the level's first 68 actions are
three whole lives and a game over, and that in all of them the tool never once stands on a refill:
the tank is 42 units at 2 per action, so a life is 21 moves, and `_plan` finishes the FRONTIER
before it will walk to any unlearned mark. `refill_marks` is empty until fogscout tick 72. Two of
the refills sat one cell off the path it walked.

The closed arms ranked marks ahead of the frontier UNCONDITIONALLY (6/7, ~503a) and again once
goal+target were known (6/7, 502a). This asks a narrower question that neither covers: when the tank
is nearly empty and NO refill is known at all, is the nearest unlearned mark worth more than the
next frontier cell? A mark is the only thing on this board that can be fuel, so the answer is not
obviously no — and treading stays ahead of nothing, so the load-bearing clause is untouched.

  0 control                     3 no-refill-known + tank <= 8, marks over frontier
  1 tank <= 8, marks over frontier (any time)      4 `_hold` removed — a refused move is a
  2 tank <= 12, marks over frontier (any time)       PROVEN no-op (18/18 blocked moves left the
  5 3 + 4                                            mover exactly where it was)

Expected feedback. Arm 0 must return [17,101,63,66,67,100,231]. An arm below 231 at levels=7 is a
gain; 231 exactly with a non-zero `fired` count is a decision that changed nothing; 231 with
`fired` 0 is a clause that never applied and says nothing about the idea.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

NVAR = 6
LOW = {1: 8, 2: 12, 3: 8, 5: 8}


def _mk(v: int):
    from admorphiq.tools.fogscout import FogScoutTool

    low = LOW.get(v, 0)
    only_unknown = v in (3, 5)
    no_hold = v in (4, 5)

    class V(FogScoutTool):
        """FogScoutTool with one fuel-discovery clause swapped in."""

        def __init__(self) -> None:
            self.fired = {"markfirst": 0, "hold": 0}
            super().__init__()

        def _hold(self, shape):
            if no_hold:
                self.fired["hold"] += 1
                return None
            return super()._hold(shape)

        def _plan(self, shape):
            if low and self.pos is not None and self.moves_left() <= low \
                    and not (only_unknown and self.refill_marks):
                if self.goal is None or self.target is None \
                        or self._search(shape, lambda c, t: c == self.goal and t == self.target,
                                        False) is None:
                    def unlearned(c):
                        sig = self.mark.get(c)
                        return (sig is not None and c != self.goal and sig not in self.kind
                                and sig not in self.inert and sig not in self.refill_marks)
                    step = self._walk(shape, unlearned)
                    if step is not None:
                        self.fired["markfirst"] += 1
                        self._say("markfuel")
                        return step
            return super()._plan(shape)

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
