"""s5i5 level 7 — the retry the engine already gives away, and whether taking it ever wins.

WHAT IS SETTLED (three fans, all on the harness or on swivel's own model of the live board):

  * ⛔ **NO WIN EXISTS THAT KEEPS EVERY BAR INSIDE THE VISIBLE FRAME.** Seven configurations —
    weight 2/4/8, length cap 12/21/none, 400k and 1.5M pops — all EXHAUST the in-grid space at
    254k-334k pops with a residual gap of 6. The SAME search with the margin allowed finds a
    28-click win. The board is framed by a wall placed at (-3,-3), so the answer lies OUTSIDE
    what a frame-only tool can observe: it must swing a bar past the edge and cannot verify that
    the move is legal until the engine refuses it.
  * ⛔ Every search-budget arm is a measured negative. Escalating on failure to 400k costs +190 s
    and finds nothing; to 1.5M costs +930 s and finds nothing; raising `_MAX_OPEN` globally to
    400k costs 900 s against a 248 s control and finds nothing. All eight end at 0.5833.
  * ⛔ Recovering the one control the tool drops (`turn c8`) changes the run byte-identically, and
    `_settle` never disagrees with the frame, so neither is the cause.

WHAT IS LEFT. The engine's 200-step allowance runs out at action ~392 and ~592 and RESTARTS level
7 — `levels_completed` never moves, so nothing downstream sees it. swivel is `_dead` from action
224 and cannot use either retry. ⚠️ And the obvious place to notice a restart does not work: a
dead tool's `propose` is NEVER CALLED AGAIN, because `detect` returns 0.0 and the harness only
drives the selected tool. MEASURED — the check fired 7 times, all in the seven actions before the
handover, and never once at either restart. `detect` is the only method a dead tool still gets.

So: put the restart check in `detect`, carry the learned off-grid geometry across the reset (it is
the only thing worth keeping — it is what the next plan needs to avoid), and measure whether more
attempts ever converge.

  1 control
  2 re-arm in `detect` + carry the learned geometry            (shippable shape, 500 no-progress)
  3 arm 2 + escalate the search to 400k on failure
  4 arm 2 + plan with the joint search from the start
  5 arm 2 with a 2000-action no-progress budget    — DIAGNOSTIC: does it EVER converge?
  6 arm 4 with 2000                                — same, with the joint planner
  7 no re-arm, 2000                                — control for the extra budget alone
  8 arm 3 with 2000

⚠️ Arms 5-8 are diagnostics, not candidates: the shipped no-progress budget is 500 and raising it
is a harness change that would touch all 25 games. They answer whether the retry route converges
at all, which decides whether the shippable arm is worth gating.

Run:  bash scripts/pfan.sh s5i5arm3 scripts/_s5i5_arm3.py 8 "" 8
"""
from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, "src")

TITLE = "s5i5"
HUMAN = [20, 89, 106, 54, 162, 38, 86, 83]
WIN_LEVELS = 8


def install(rearm: bool, carry: bool, escalate: int, joint: bool) -> list:
    import admorphiq.tools.swivel as sv

    log: list = []
    saved: dict = {"off": set(), "ill": set()}

    if joint:
        sv.plan = lambda model, start, moves, banned=None: (
            [] if sv.solved(model, start) else
            (sv._joint(model, start, moves, banned) if model.pairing else None))

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

    if rearm:
        orig_detect = sv.SwivelArmTool.detect
        orig_begin = sv.SwivelArmTool._begin
        orig_reset = sv.SwivelArmTool.reset

        def begin(self, g):
            ok = orig_begin(self, g)
            if ok and carry and self._model is not None and (saved["off"] or saved["ill"]):
                self._model.offblocked |= saved["off"]
                self._model.illegal |= saved["ill"]
                log.append({"ev": "carried", "off": len(saved["off"]),
                            "ill": len(saved["ill"])})
            return ok

        def reset(self):
            first = getattr(self, "_first", None)
            orig_reset(self)
            self._first = first

        def detect(self, frames, obs):
            # ⛔ THE ONLY METHOD A DEAD TOOL STILL GETS. `propose` is called for the selected
            # tool alone, so a check placed there can never see the board again — measured, it
            # fired seven times in the seven actions before the handover and never at either
            # restart.
            if self._dead and getattr(self, "_first", None) is not None and self._widgets:
                layers = sv._layers(obs)
                if layers:
                    seen, _m = sv.solid_cells(layers[-1], self._marker or 0,
                                              [w.box for w in self._widgets])
                    if seen == self._first:
                        if self._model is not None:
                            saved["off"] |= set(self._model.offblocked)
                            saved["ill"] |= set(self._model.illegal)
                        keep_lvl, keep_first = self._level, self._first
                        self.reset()
                        self._level, self._first = keep_lvl, keep_first
                        log.append({"ev": "rearmed", "off": len(saved["off"]),
                                    "ill": len(saved["ill"])})
            got = orig_detect(self, frames, obs)
            if getattr(self, "_first", None) is None and self._model is not None and self._widgets:
                layers = sv._layers(obs)
                if layers:
                    seen, _m = sv.solid_cells(layers[-1], self._marker or 0,
                                              [w.box for w in self._widgets])
                    self._first = seen
                    log.append({"ev": "first_reading", "cells": len(seen)})
            return got

        sv.SwivelArmTool.detect = detect
        sv.SwivelArmTool._begin = begin
        sv.SwivelArmTool.reset = reset
        sv.SwivelArmTool._first = None

    return log


ARMS = {
    1: dict(rearm=False, carry=False, escalate=0, joint=False, nop=500),
    2: dict(rearm=True, carry=True, escalate=0, joint=False, nop=500),
    3: dict(rearm=True, carry=True, escalate=400_000, joint=False, nop=500),
    4: dict(rearm=True, carry=True, escalate=0, joint=True, nop=500),
    5: dict(rearm=True, carry=True, escalate=0, joint=False, nop=2000),
    6: dict(rearm=True, carry=True, escalate=0, joint=True, nop=2000),
    7: dict(rearm=False, carry=False, escalate=0, joint=False, nop=2000),
    8: dict(rearm=True, carry=True, escalate=400_000, joint=False, nop=2000),
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
        "FIRED": kinds, "events": log[:18], "n_events": len(log),
    }))


if __name__ == "__main__":
    main()
