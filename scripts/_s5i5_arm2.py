"""s5i5 — second arm set. The engine RESTARTS level 7 for free; the tool is dead for every retry.

WHAT THE FIRST ARM SET MEASURED (`scripts/_s5i5_arm.py`, all eight arms, whole game):

    control                                    6 levels  0.5833  695a  248s
    escalate the search to 400k pops on failure 6 levels  0.5833  695a  444s
      -> the escalation FIRES TWICE (88s, 99s) and finds NOTHING both times

So a bigger search from the state swivel has walked into does not exist within 400k pops, and the
+190 s buys nothing. ⛔ That kills the "the search is cut off just short" reading FROM THAT STATE —
the 324k-pop win measured earlier was from the POST-PROBE board, sixteen clicks earlier.

WHAT IS LEFT, and it is the finding the round already turned up: **the engine hands the tool a
fresh solvable board twice and nothing notices.** The 200-step allowance drains and level 7 restarts
at action ~392 and again at ~592, `levels_completed` never moves, and `_dead` is only cleared by
`reset()`, which `propose` calls on a LEVEL CHANGE. So swivel is dead through both retries.

And there is something worth carrying across a retry. The refusals are not noise: this board is
framed by a wall placed at (-3,-3), so part of it is OUTSIDE the visible grid and no frame-only tool
can see it. `_settle` learns it by refusal — 45 off-grid cells and 2 banned configurations by the
time the tool dies. On a fresh board that knowledge is exactly what would keep the next plan out of
the same trap; `reset()` throws it away.

Arms:
  1 control
  2 re-arm on restart only — does the restarted board match the first reading AT ALL?
  3 re-arm + carry the learned off-grid furniture and banned configurations across it
  4 arm 3 + escalate the search to 400k on failure
  5 escalate + allow longer plans (`_MAX_PLAN` 60 -> 150): from a walked-into state the way out
    may be longer than the way in
  6 escalate, but CLEAR the learned off-grid cells first — they are banked as a superset (every
    off-grid cell the refused move would have touched), so they may be over-constraining the search
  7 arm 3 + longer plans
  8 arm 3 + escalate + longer plans

⚠️ Every arm logs whether its mechanism FIRED, not just its outcome: a matrix that comes back
identical across arms is the signature of a branch that never executed.

Run:  bash scripts/pfan.sh s5i5arm2 scripts/_s5i5_arm2.py 8 "" 8
"""
from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, "src")

TITLE = "s5i5"
HUMAN = [20, 89, 106, 54, 162, 38, 86, 83]
WIN_LEVELS = 8


def install(escalate: int, rearm: bool, carry: bool, maxplan: int, drop_off: bool) -> list:
    import admorphiq.tools.swivel as sv

    log: list = []
    saved: dict = {"off": set(), "ill": set()}

    if maxplan:
        sv._MAX_PLAN = maxplan

    if escalate:
        orig_plan = sv.plan

        def plan(model, start, moves, banned=None):
            got = orig_plan(model, start, moves, banned)
            if got is not None:
                return got
            keep_open = sv._MAX_OPEN
            sv._MAX_OPEN = escalate
            dropped = None
            if drop_off and model.offblocked:
                dropped = set(model.offblocked)
                model.offblocked = set()
            t0 = time.time()
            try:
                deep = sv._joint(model, start, moves, banned) if model.pairing else None
            finally:
                sv._MAX_OPEN = keep_open
                if dropped is not None:
                    model.offblocked = dropped
            log.append({"ev": "escalated", "found": deep is not None,
                        "len": len(deep) if deep else 0, "s": round(time.time() - t0, 1),
                        "dropped_off": len(dropped) if dropped else 0})
            return deep

        sv.plan = plan

    if rearm:
        orig_propose = sv.SwivelArmTool.propose
        orig_begin = sv.SwivelArmTool._begin

        def begin(self, g):
            ok = orig_begin(self, g)
            if ok and carry and self._model is not None:
                self._model.offblocked |= saved["off"]
                self._model.illegal |= saved["ill"]
                if saved["off"] or saved["ill"]:
                    log.append({"ev": "carried", "off": len(saved["off"]),
                                "ill": len(saved["ill"])})
            return ok

        sv.SwivelArmTool._begin = begin

        def propose(self, frames, obs):
            if self._dead and getattr(self, "_first", None) is not None and self._widgets:
                layers = sv._layers(obs)
                if layers:
                    seen, _m = sv.solid_cells(layers[-1], self._marker or 0,
                                              [w.box for w in self._widgets])
                    diff = len(seen ^ self._first)
                    if diff == 0:
                        # ⛔ The engine restarted the level. Nothing downstream can see that: the
                        # level number did not move. The board is the one this tool first read and
                        # it is solvable again.
                        if self._model is not None:
                            saved["off"] |= set(self._model.offblocked)
                            saved["ill"] |= set(self._model.illegal)
                        keep_lvl, keep_first = self._level, self._first
                        self.reset()
                        self._level, self._first = keep_lvl, keep_first
                        log.append({"ev": "rearmed"})
                    elif len(log) < 30:
                        log.append({"ev": "restart_check", "diff_cells": diff})
            out = orig_propose(self, frames, obs)
            if getattr(self, "_first", None) is None and self._model is not None and self._widgets:
                layers = sv._layers(obs)
                if layers:
                    seen, _m = sv.solid_cells(layers[-1], self._marker or 0,
                                              [w.box for w in self._widgets])
                    self._first = seen
                    log.append({"ev": "first_reading", "cells": len(seen)})
            return out

        sv.SwivelArmTool.propose = propose
        orig_reset = sv.SwivelArmTool.reset

        def reset(self):
            first = getattr(self, "_first", None)
            orig_reset(self)
            self._first = first

        sv.SwivelArmTool.reset = reset
        sv.SwivelArmTool._first = None

    return log


ARMS = {
    1: dict(escalate=0, rearm=False, carry=False, maxplan=0, drop_off=False),
    2: dict(escalate=0, rearm=True, carry=False, maxplan=0, drop_off=False),
    3: dict(escalate=0, rearm=True, carry=True, maxplan=0, drop_off=False),
    4: dict(escalate=400_000, rearm=True, carry=True, maxplan=0, drop_off=False),
    5: dict(escalate=400_000, rearm=False, carry=False, maxplan=150, drop_off=False),
    6: dict(escalate=400_000, rearm=False, carry=False, maxplan=0, drop_off=True),
    7: dict(escalate=0, rearm=True, carry=True, maxplan=150, drop_off=False),
    8: dict(escalate=400_000, rearm=True, carry=True, maxplan=150, drop_off=False),
}


def main() -> None:
    job = int(sys.argv[1])
    arm = ARMS[((job - 1) % len(ARMS)) + 1]
    log = install(**arm)

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(TITLE))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=8000, stall=80, ctx_budget=6000)
    frames = [obs]
    who: dict[str, int] = {}
    per_level: list[list[int]] = []
    lvl = 0
    last_up = 0
    t0 = time.time()
    step = 0
    for step in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        who[str(agent._current)] = who.get(str(agent._current), 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", lvl) or 0)
        if now > lvl:                       # rule 7f — a fall back is not a clear
            per_level.append([now, step + 1 - last_up])
            last_up = step + 1
            lvl = now
        elif now < lvl:
            per_level.append([-now, -(step + 1 - last_up)])
            last_up = step + 1
            lvl = now
    scores = []
    for n, acts in per_level:
        if acts <= 0 or n > len(HUMAN):
            continue
        scores.append(min(HUMAN[n - 1] / acts, 1.0) ** 2)
    weights = list(range(1, WIN_LEVELS + 1))
    game_score = sum(w * s for w, s in zip(weights, scores)) / sum(weights)
    kinds: dict[str, int] = {}
    for e in log:
        kinds[e["ev"]] = kinds.get(e["ev"], 0) + 1
    print(json.dumps({
        "job": job, **arm,
        "levels": lvl, "game_score": round(game_score, 4),
        "actions": step + 1, "wall_s": round(time.time() - t0, 1),
        "per_level_actions": per_level, "who_acted": who,
        "fired": kinds, "events": log[:24], "n_events": len(log),
    }))


if __name__ == "__main__":
    main()
