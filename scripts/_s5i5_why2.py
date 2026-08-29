"""s5i5 level 7 — why the restart detector does not fire, logged at the restart itself.

`scripts/_s5i5_restart.py` proved the restart: GAME_OVER at 392/593/794/995/1196/1397/1598 and the
band-excluded board fingerprint returns to its level-start value at 393/594/... exactly. But a
detector inside `swivel.propose` built on that same fingerprint (`scripts/_s5i5_arm5.py`) fired
ZERO times while the tool was holding the board through the 392 death.

Two possibilities and they want different repairs, so this logs the raw evidence at the moment:

  A `propose` is not CALLED at the restart — the harness queues steps, or `_ledger_observe`
    re-decides on the GAME_OVER and the board changes hands for those actions;
  B `propose` IS called and the fingerprint DIFFERS — the frame the tool is handed at that instant
    is not the settled board (`_layers(obs)[-1]` mid-revival), or the first reading was taken one
    action later than the level-start frame.

Every `propose` between actions 370 and 420 is recorded with its own action number, the key it
computes, the stored first key, and who the harness thinks is acting.

Run:  bash scripts/pfan.sh s5i5why2 scripts/_s5i5_why2.py 1 "" 2
"""
from __future__ import annotations

import hashlib
import json
import sys

sys.path.insert(0, "src")

TITLE = "s5i5"
STUCK = 6
_BAND = 1


def main() -> None:
    _job = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    import numpy as np
    from arc_agi import Arcade, OperationMode

    import admorphiq.tools.swivel as sv
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def key_of(g) -> str:
        a = np.asarray(g)
        inner = a[_BAND:a.shape[0] - _BAND, _BAND:a.shape[1] - _BAND]
        return hashlib.md5(inner.tobytes()).hexdigest()[:12]

    clock = {"a": 0}
    seen_log: list = []
    state = {"firstkey": None}

    orig_next = sv.SwivelArmTool._next
    orig_propose = sv.SwivelArmTool.propose

    def nxt(self):
        out = orig_next(self)
        if out or not self._dead:
            return out
        self._dead = False
        self._waits = getattr(self, "_waits", 0) + 1
        n = len(self._controls) or 1
        return [self._click(self._waits % n, 1 if (self._waits // n) % 2 == 0 else -1)]

    def propose(self, frames, obs):
        layers = sv._layers(obs)
        k = key_of(layers[-1]) if layers else "none"
        a = clock["a"]
        if state["firstkey"] is None and self._model is not None:
            state["firstkey"] = k
            seen_log.append({"a": a, "ev": "first", "key": k})
        if 370 <= a <= 420 or (state["firstkey"] and k == state["firstkey"] and a > 200):
            if len(seen_log) < 90:
                seen_log.append({"a": a, "key": k, "match": k == state["firstkey"],
                                 "layers": len(layers) if layers else 0,
                                 "waits": getattr(self, "_waits", 0),
                                 "dead": bool(self._dead)})
        return orig_propose(self, frames, obs)

    sv.SwivelArmTool._next = nxt
    sv.SwivelArmTool.propose = propose
    sv.SwivelArmTool._waits = 0

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(TITLE))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=8000, stall=80,
                         no_progress=2000, ctx_budget=6000)
    frames = [obs]
    who: dict[str, int] = {}
    outside: list = []
    lvl = 0
    step = 0
    for step in range(900):
        if agent.is_done(frames, obs):
            break
        clock["a"] = step + 1
        act = agent.choose_action(frames, obs)
        cur = str(agent._current)
        who[cur] = who.get(cur, 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        lvl = int(getattr(obs, "levels_completed", lvl) or 0)
        if 386 <= step + 1 <= 400 and len(outside) < 30:
            layers = sv._layers(obs)
            outside.append([step + 1, cur, key_of(layers[-1]) if layers else "none",
                            len(layers) if layers else 0,
                            str(getattr(obs, "state", ""))[-12:]])
    print(json.dumps({"job": 1, "levels": lvl, "actions": step + 1, "who": who,
                      "firstkey": state["firstkey"],
                      "propose_log": seen_log[:60],
                      "loop_frames_386_400": outside}))


if __name__ == "__main__":
    main()
