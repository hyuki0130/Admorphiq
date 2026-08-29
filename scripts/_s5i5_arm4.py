"""s5i5 level 7 — the last route: HOLD the board, take the engine's free restart, re-plan.

Everything else is now measured and closed:

  ⛔ NO WIN KEEPS EVERY BAR INSIDE THE VISIBLE FRAME. Seven configurations (weight 2/4/8, length
     cap 12/21/none, 400k and 1.5M pops) all EXHAUST the in-grid space at 254k-334k pops with a
     residual gap of 6; the same search with the margin allowed finds a 28-click win. The board is
     framed by a wall placed at (-3,-3), so the answer is OUTSIDE what a frame-only tool can see.
  ⛔ Every search-budget arm is a negative: escalate-on-failure to 400k (+190 s), to 1.5M (+930 s),
     `_MAX_OPEN` 400k globally (900 s against a 248 s control), longer plans, tighter length caps —
     all sixteen arms end at 0.5833.
  ⛔ The missing `turn c8` control changes the run byte-identically; `_settle` never disagrees.
  ⛔ AND A DEAD TOOL HAS NO HOOK AT ALL. `propose` is called for the selected tool only, and
     `_decide` computes bids over `[n for n in self.tools if n not in self._failed]` — so once the
     harness retires a tool, neither `propose` NOR `detect` is ever called on it again. Both
     placements of a restart check were measured firing ZERO times.

What is left is the one asset nobody is using: the engine's 200-step allowance runs out and level 7
RESTARTS — at action ~392 and again at ~592, with `levels_completed` never moving. The board comes
back solvable and the tool is retired for both retries.

A tool that keeps PROPOSING is never retired. So: when the planner runs out of plans, do not
concede — keep the board, spend the remaining allowance on the controls (which is what the fallback
would do anyway, with no model), and when the board returns to the reading `_begin` first took,
re-read it and plan again, carrying the off-grid geometry the refusals taught. That geometry is the
only thing worth keeping: it is exactly what the next plan needs in order not to walk into the same
wall.

  1 control
  2 hold-and-retry, carrying the learned geometry          (the shippable shape)
  3 arm 2 without carrying it — is the carried geometry load-bearing?
  4 arm 2 + escalate the search to 400k when a plan is not found
  5 arm 2 with a 2000-action no-progress budget — DIAGNOSTIC: ~10 attempts. Does it EVER converge?
  6 arm 3 with 2000
  7 control with 2000                                      — the extra budget alone
  8 arm 4 with 2000

⚠️ Arms 5-8 are diagnostics: the shipped no-progress budget is 500 and raising it is a harness
change touching all 25 games. They bound the route — if ten attempts do not converge, no version of
this repair does, and that is the answer.

Run:  bash scripts/pfan.sh s5i5arm4 scripts/_s5i5_arm4.py 8 "" 8
"""
from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, "src")

TITLE = "s5i5"
HUMAN = [20, 89, 106, 54, 162, 38, 86, 83]
WIN_LEVELS = 8


def install(hold: bool, carry: bool, escalate: int) -> list:
    import admorphiq.tools.swivel as sv

    log: list = []
    saved: dict = {"off": set(), "ill": set()}

    if escalate:
        orig_plan = sv.plan

        def plan(model, start, moves, banned=None):
            got = orig_plan(model, start, moves, banned)
            if got is not None:
                return got
            keep = sv._MAX_OPEN
            sv._MAX_OPEN = escalate
            t0 = time.time()
            try:
                deep = sv._joint(model, start, moves, banned) if model.pairing else None
            finally:
                sv._MAX_OPEN = keep
            log.append({"ev": "escalated", "found": deep is not None,
                        "s": round(time.time() - t0, 1)})
            return deep

        sv.plan = plan

    if not hold:
        return log

    orig_next = sv.SwivelArmTool._next
    orig_propose = sv.SwivelArmTool.propose
    orig_begin = sv.SwivelArmTool._begin
    orig_reset = sv.SwivelArmTool.reset

    def begin(self, g):
        ok = orig_begin(self, g)
        if ok and carry and self._model is not None and (saved["off"] or saved["ill"]):
            self._model.offblocked |= saved["off"]
            self._model.illegal |= saved["ill"]
            log.append({"ev": "carried", "off": len(saved["off"]), "ill": len(saved["ill"])})
        return ok

    def reset(self):
        first = getattr(self, "_first", None)
        waits = getattr(self, "_waits", 0)
        orig_reset(self)
        self._first = first
        self._waits = waits

    def nxt(self):
        out = orig_next(self)
        if out or not self._dead:
            return out
        # ⛔ CONCEDING IS THE EXPENSIVE MOVE. The level restarts on its own clock and the board
        # comes back solvable; a tool that stops proposing is retired and never asked again.
        self._dead = False
        self._waits = getattr(self, "_waits", 0) + 1
        if self._model is not None:
            saved["off"] |= set(self._model.offblocked)
            saved["ill"] |= set(self._model.illegal)
        log.append({"ev": "held", "n": self._waits})
        ctrl = self._waits % max(1, len(self._controls))
        return [self._click(ctrl, 1 if (self._waits // max(1, len(self._controls))) % 2 == 0
                            else -1)]

    def propose(self, frames, obs):
        if getattr(self, "_first", None) is not None and self._widgets and self._model is not None:
            layers = sv._layers(obs)
            if layers:
                seen, _m = sv.solid_cells(layers[-1], self._marker or 0,
                                          [w.box for w in self._widgets])
                if seen == self._first and getattr(self, "_waits", 0):
                    # The engine restarted the level. Nothing else can see it — the level number
                    # did not move.
                    if self._model is not None:
                        saved["off"] |= set(self._model.offblocked)
                        saved["ill"] |= set(self._model.illegal)
                    keep_lvl, keep_first = self._level, self._first
                    self.reset()
                    self._level, self._first = keep_lvl, keep_first
                    self._waits = 0
                    log.append({"ev": "rearmed", "off": len(saved["off"]),
                                "ill": len(saved["ill"])})
        out = orig_propose(self, frames, obs)
        if getattr(self, "_first", None) is None and self._model is not None and self._widgets:
            layers = sv._layers(obs)
            if layers:
                seen, _m = sv.solid_cells(layers[-1], self._marker or 0,
                                          [w.box for w in self._widgets])
                self._first = seen
                log.append({"ev": "first_reading", "cells": len(seen)})
        return out

    sv.SwivelArmTool._next = nxt
    sv.SwivelArmTool.propose = propose
    sv.SwivelArmTool._begin = begin
    sv.SwivelArmTool.reset = reset
    sv.SwivelArmTool._first = None
    sv.SwivelArmTool._waits = 0
    return log


ARMS = {
    1: dict(hold=False, carry=False, escalate=0, nop=500),
    2: dict(hold=True, carry=True, escalate=0, nop=500),
    3: dict(hold=True, carry=False, escalate=0, nop=500),
    4: dict(hold=True, carry=True, escalate=400_000, nop=500),
    5: dict(hold=True, carry=True, escalate=0, nop=2000),
    6: dict(hold=True, carry=False, escalate=0, nop=2000),
    7: dict(hold=False, carry=False, escalate=0, nop=2000),
    8: dict(hold=True, carry=True, escalate=400_000, nop=2000),
}


def main() -> None:
    job = int(sys.argv[1])
    arm = dict(ARMS[((job - 1) % len(ARMS)) + 1])
    nop = arm.pop("nop")
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
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=8000, stall=80,
                         no_progress=nop, ctx_budget=6000)
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
        if now > lvl:                        # rule 7f
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
        "job": job, **arm, "no_progress": nop,
        "levels": lvl, "game_score": round(game_score, 4),
        "actions": step + 1, "wall_s": round(time.time() - t0, 1),
        "per_level_actions": per_level, "who_acted": who,
        "FIRED": kinds, "events": [e for e in log if e["ev"] != "held"][:16],
        "n_events": len(log),
    }))


if __name__ == "__main__":
    main()
