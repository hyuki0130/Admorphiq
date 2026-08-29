"""ls20 level 7: `_refuel` picks the NEAREST ring; the cheap one is the one on the way.

Purpose. An oracle BFS over the level's own geometry (walls, changers, refills, the mover's lane,
the 42-unit tank at 2 per action) puts the full-knowledge solve at **61 actions with fuel and 55
without** — so fuel costs an optimal plan about SIX actions. The tool's own knowledge-complete solve
(the census's game ticks 157-231) is **75**, and 14 of those are refuel diversions: it reaches the
first win route at length 33 and spends 47 actions on it.

`_refuel` walks to the NEAREST refill. Nearest is not cheapest when the level is about to end
somewhere specific: a ring behind you costs the walk twice. This fan re-ranks ONLY the refill
choice — it does not rebuild the win search over the tank, which was measured WORSE (241) and is
closed.

  0 control                                   2 arm 1, but only while a win route exists
  1 minimise d(pos->ring) + d(ring->goal)     3 arm 1, and also when the goal is not yet known,
                                                 ranking against the current aim cell instead

Expected feedback. Arm 0 must return [17,101,63,66,67,100,231]. `detour` counts the ticks where the
re-ranked choice DIFFERS from nearest — an arm at 231 with `detour` 0 never fired and says nothing.
"""
from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

NVAR = 4


def _mk(v: int):
    from admorphiq.tools.fogscout import _MOVE_IDS, FogScoutTool

    on = v in (1, 2, 3)
    win_only = v == 2
    use_aim = v == 3

    class V(FogScoutTool):
        """FogScoutTool whose refuel target is ranked by the DETOUR it costs."""

        def __init__(self) -> None:
            self.fired = {"detour": 0, "calls": 0}
            super().__init__()

        def _dists(self, shape, src):
            out = {src: 0}
            q = deque([(src, 0)])
            acts = [a for a in self.dirs if a in _MOVE_IDS]
            while q:
                c, d = q.popleft()
                for a in acts:
                    nb = self._step_to(c, a)
                    if nb in out or nb == self.goal or not self._passable(nb, shape):
                        continue
                    out[nb] = d + 1
                    q.append((nb, d + 1))
            return out

        def _refuel(self, shape):
            step = super()._refuel(shape)
            if not on or step is None:
                return step
            self.fired["calls"] += 1
            anchor = self.goal
            if anchor is None:
                if not use_aim:
                    return step
                anchor = self._aim_cell
            if anchor is None:
                return step
            if win_only and self._search(
                    shape, lambda c, t: c == self.goal and t == self.target, False) is None:
                return step
            live = {c for c, sig in self.mark.items() if sig in self.refill_marks}
            if len(live) < 2:
                return step
            here = self._dists(shape, self.pos)
            back = self._dists(shape, anchor)
            cand = [(here[c] + back[c], c) for c in live if c in here and c in back]
            if not cand:
                return step
            _cost, best = min(cand)
            keep = self._aim_cell
            alt = self._walk(shape, lambda c: c == best)
            if alt is None:
                self._aim_cell = keep
                return step
            if alt != step:
                self.fired["detour"] += 1
            return alt

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
                      "census": dict(fog.census.most_common(10))}), flush=True)


if __name__ == "__main__":
    main()
