"""s5i5 level 7 — take the engine's free retry, with the comparator that actually sees it.

MEASURED (`scripts/_s5i5_restart.py`): the level dies at action **392, 593, 794, 995, 1196, 1397,
1598** — every 201 actions, seven times in one run — and at 393, 594, ... the board returns to a
fingerprint **identical** to the one at action 192, with the outer band excluded. `levels_completed`
never moves. So the retry is real, periodic, and detectable.

⛔ AND THE EARLIER DETECTOR WAS THE DEFECT, NOT THE MECHANISM. Both previous attempts compared
`solid_cells(frame)` against the first reading and never matched once in 2202 actions. `solid_cells`
returns the WHOLE frame's solid cells including the allowance bar the game paints along row 63 —
full at the first reading, three pixels short one action after the restart, so the two can never
compare equal. `_chrome` covers that row and is subtracted inside `_agrees`, but not in a raw
comparison. A band-excluded fingerprint matches on the exact action the bar refills.

⚠️ WHAT THIS IS WORTH, BEFORE MEASURING IT. The scorer charges a level with every action since the
previous clear, deaths included (`action_count_this_level` is reset on a level-up and never on a
GAME_OVER), and level 7's human baseline is 86:

    cleared on attempt 1 (~60 actions)    -> 1.0000   s5i5 0.5833 -> 0.7778   +0.1944
    cleared on attempt 2 (~260 actions)   -> 0.1094   s5i5          0.6046   +0.0213
    cleared on attempt 3 (~460 actions)   -> 0.0349   s5i5          0.5901   +0.0068

So the retry route is worth a fiftieth of an early clear, and it is only worth anything at all
because clearing level 7 also opens level 8 (weight 8 of 36). This arm measures whether it converges
and on which attempt, so the trade is a number rather than a hope.

  1 control
  2 hold the board, re-arm on the band-excluded fingerprint, carry the learned off-grid geometry
  3 arm 2 without carrying the geometry — is it load-bearing?
  4 arm 2 + escalate the search to 400k when no plan is found
  5 arm 2, no-progress 2000   — DIAGNOSTIC: nine retries. Does it converge AT ALL?
  6 arm 3, no-progress 2000
  7 control, no-progress 2000
  8 arm 4, no-progress 2000

Run:  bash scripts/pfan.sh s5i5arm5 scripts/_s5i5_arm5.py 8 "" 8
"""
from __future__ import annotations

import hashlib
import json
import sys
import time

sys.path.insert(0, "src")

TITLE = "s5i5"
HUMAN = [20, 89, 106, 54, 162, 38, 86, 83]
WIN_LEVELS = 8
_BAND = 1


def _board_key(g) -> str:
    """The board, with the outer band left out — where the allowance bar and the counters live."""
    import numpy as np
    a = np.asarray(g)
    inner = a[_BAND:a.shape[0] - _BAND, _BAND:a.shape[1] - _BAND]
    return hashlib.md5(inner.tobytes()).hexdigest()[:16]


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
        first = getattr(self, "_firstkey", None)
        waits = getattr(self, "_waits", 0)
        orig_reset(self)
        self._firstkey = first
        self._waits = waits

    def nxt(self):
        out = orig_next(self)
        if out or not self._dead:
            return out
        # ⛔ CONCEDING IS THE EXPENSIVE MOVE. The level restarts on its own clock; a tool that
        # stops proposing is retired and is never called again, so it cannot use the retry.
        self._dead = False
        self._waits = getattr(self, "_waits", 0) + 1
        if self._model is not None:
            saved["off"] |= set(self._model.offblocked)
            saved["ill"] |= set(self._model.illegal)
        n = len(self._controls) or 1
        return [self._click(self._waits % n, 1 if (self._waits // n) % 2 == 0 else -1)]

    def propose(self, frames, obs):
        layers = sv._layers(obs)
        if layers and getattr(self, "_firstkey", None) is not None and getattr(self, "_waits", 0):
            if _board_key(layers[-1]) == self._firstkey:
                if self._model is not None:
                    saved["off"] |= set(self._model.offblocked)
                    saved["ill"] |= set(self._model.illegal)
                keep_lvl, keep_key = self._level, self._firstkey
                self.reset()
                self._level, self._firstkey, self._waits = keep_lvl, keep_key, 0
                log.append({"ev": "rearmed", "off": len(saved["off"]), "ill": len(saved["ill"])})
        out = orig_propose(self, frames, obs)
        if layers and getattr(self, "_firstkey", None) is None and self._model is not None:
            self._firstkey = _board_key(layers[-1])
            log.append({"ev": "first_key", "key": self._firstkey})
        return out

    sv.SwivelArmTool._next = nxt
    sv.SwivelArmTool.propose = propose
    sv.SwivelArmTool._begin = begin
    sv.SwivelArmTool.reset = reset
    sv.SwivelArmTool._firstkey = None
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
        if now > lvl:                        # rule 7f — `>`, and the level is a number
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
        "FIRED": kinds, "events": [e for e in log if e["ev"] != "held"][:14],
    }))


if __name__ == "__main__":
    main()
