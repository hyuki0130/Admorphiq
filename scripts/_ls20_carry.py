"""ls20 level 7: is CROSS-LEVEL MECHANIC CARRY worth the 45 actions, or is it another inert axis?

Purpose. R101LS20FOG closed the handover and twelve arms across four axes, and left exactly one
item open: a first-time human arrives at level 7 having played six levels with the SAME three
changers, while `fogscout` arrives with nothing. Building that carry is a real build (fogscout
cannot perceive an unfogged board and the harness resets every tool at a level-up), so the value
must be measured BEFORE the build, not after.

Method — the upper bound, measured with a second pass over the SAME board. Pass 1 is the shipped
run; it must return the banked [17,101,63,66,67,100,231] or nothing below is about the shipped tool.
While it runs, the LAYOUT-INDEPENDENT half of what `fogscout` learns is snapshotted every tick:
`kind` (mark signature -> token permutation), `inert`, `refill_marks`, `dirs`. Those four are keyed
by the mark's own glyph and by the action id, so they are exactly what a player carries from one
level to the next -- and NOT the map, the goal cell, or the demanded token, which are per level.
Pass 2 replays the whole game with those tables re-installed on every `reset()`.

Pass 2 is therefore an OVER-estimate of cross-level carry (it carries knowledge learned on this very
board, which is at least as good as anything levels 1-6 could teach) and that is the point: if the
over-estimate does not move 231, the axis is dead and no build is warranted.

Arms (argv[1]):
  1 control -- carry NOTHING. Pass 2 must equal pass 1 exactly; this is the negative control, and
    without it a clean result cannot be told from an instrument that carries nothing at all.
  2 kind   3 inert   4 refill_marks   5 dirs
  6 kind+inert+refill_marks            7 all four
  8..13 the subsets that keep `dirs`, because `dirs` alone is the worst arm and `dirs` with the
  three mechanic facts is the best -- the interaction is not additive and the plateau has to be
  measured

Expected feedback. `p1_per_level` = [17,101,63,66,67,100,231]. Arm 1 must give p2 == p1. Any arm
whose p2 level 7 drops materially below 231 names the fact worth carrying; `p2_win_tick` says when
the win route first existed, which is the mechanism (the shipped run first sees one at tick 172 of
220).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

_ARMS = {
    1: (),
    2: ("kind",),
    3: ("inert",),
    4: ("refill_marks",),
    5: ("dirs",),
    6: ("kind", "inert", "refill_marks"),
    7: ("kind", "inert", "refill_marks", "dirs"),
    # Subsets that keep `dirs`. Arm 5 (dirs alone) is the worst arm measured and arm 7 (dirs with
    # the three mechanic facts) is the best, so the interaction is not additive and the size of
    # the plateau around arm 7 has to be measured, not assumed.
    8: ("kind", "dirs"),
    9: ("kind", "refill_marks", "dirs"),
    10: ("kind", "inert", "dirs"),
    11: ("inert", "refill_marks", "dirs"),
    12: ("refill_marks", "dirs"),
    13: ("inert", "dirs"),
}

_SNAP: dict[str, Any] = {}


def _mk(fields: tuple[str, ...], record: bool):
    from admorphiq.tools.fogscout import FogScoutTool

    class Carry(FogScoutTool):
        """Shipped decisions; the only change is what survives `reset()`."""

        def reset(self) -> None:
            super().reset()
            for f in fields:
                v = _SNAP.get(f)
                if v is None:
                    continue
                getattr(self, f).update(copy.deepcopy(v))

        def propose(self, frames, obs):
            out = super().propose(frames, obs)
            if record:
                for f in ("kind", "inert", "refill_marks", "dirs"):
                    _SNAP[f] = copy.deepcopy(getattr(self, f))
            return out

    return Carry


def _run(fields: tuple[str, ...], record: bool) -> dict[str, Any]:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    cls = _mk(fields, record)
    fog = cls()
    tools = [fog if t.name == "fogscout" else t for t in default_tools()]

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.observation_space
    agent = UnifiedAgent(tools, _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    human = list(getattr(info, "baseline_actions", []) or [])

    prev_levels = int(obs.levels_completed)
    total = this = 0
    per: list[int] = []
    # tick (fogscout-local) at which a win route first existed on level 7
    win_tick: int | None = None
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
        if prev_levels == 6 and win_tick is None and fog.reason.startswith("win"):
            win_tick = fog.tick
        cur = int(obs.levels_completed)
        if cur > prev_levels:
            for _ in range(cur - prev_levels):
                per.append(this)
                this = 0
            prev_levels = cur
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
    return {
        "levels": prev_levels,
        "per_level": per,
        "score": round(got / weight, 6),
        "win_tick": win_tick,
        "ticks": fog.tick,
        "kind": len(fog.kind),
        "inert": len(fog.inert),
        "refill": len(fog.refill_marks),
        "dirs": len(fog.dirs),
    }


def main() -> None:
    arm = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fields = _ARMS[arm]
    p1 = _run((), record=True)
    carried = {f: len(_SNAP.get(f) or ()) for f in ("kind", "inert", "refill_marks", "dirs")}
    p2 = _run(fields, record=False)
    print(json.dumps({
        "arm": arm, "carry": list(fields), "carried_sizes": carried,
        "p1": p1, "p2": p2,
    }, default=str), flush=True)


if __name__ == "__main__":
    main()
