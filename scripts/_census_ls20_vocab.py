"""ls20: how much of fogscout's tenure is VOCABULARY ACQUISITION an observe-channel could remove?

fogscout owns level 7 (index 6) and never plays levels 1-6 — the one case in the 25 where a
late-arriving tool actually CLEARS its level. This snapshots its own `census` (it labels every
action with the planner clause that produced it) at every level boundary and at the end, so the
`press`/`mark`/`look` vocabulary excursions can be separated from the walking.

Mirrors score_efficiency.run_game via adapter_factory; the score must reproduce 0.9121/645.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))
for _v in ("GF_GIVEUP", "HARNESS_STALL", "HARNESS_CTX"):
    os.environ.pop(_v, None)


class Spy:
    def __init__(self, inner):
        object.__setattr__(self, "inner", inner)
        object.__setattr__(self, "snaps", [])
        object.__setattr__(self, "_lv", 0)

    def is_done(self, frames, obs):
        return self.inner.is_done(frames, obs)

    def choose_action(self, frames, obs):
        from admorphiq.harness.loop import levels_completed
        lv = int(levels_completed(obs))
        fog = self.inner.tools.get("fogscout")
        # snapshot BEFORE the harness resets every tool on a level-up
        if lv != self._lv:
            self.snaps.append({"leaving_level": self._lv,
                               "census": dict(getattr(fog, "census", {}) or {}),
                               "kinds": len(getattr(fog, "kind", {}) or {}),
                               "inert": len(getattr(fog, "inert", set()) or set())})
            object.__setattr__(self, "_lv", lv)
        act = self.inner.choose_action(frames, obs)
        self.snaps and None
        return act

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "inner"), name)


def main() -> None:
    from arc_agi import Arcade, OperationMode

    import score_efficiency as SE

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env_info = next(e for e in arcade.get_environments()
                    if "ls20" in f"{e.game_id} {e.title or ''}".lower())
    box = {}

    def factory():
        s = Spy(SE._make_agent("unified", game_id=env_info.game_id))
        box["s"] = s
        return s

    res = SE.run_game(arcade, env_info.game_id, env_info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)
    s = box["s"]
    fog = s.inner.tools.get("fogscout")
    s.snaps.append({"leaving_level": s._lv, "final": True,
                    "census": dict(getattr(fog, "census", {}) or {}),
                    "kinds": len(getattr(fog, "kind", {}) or {}),
                    "inert": len(getattr(fog, "inert", set()) or set())})
    print(json.dumps({
        "score": res.get("game_score"),
        "levels_completed": res.get("levels_completed"),
        "total_actions": res.get("total_actions"),
        "per_level": res.get("per_level"),
        "snaps": s.snaps,
    }))


if __name__ == "__main__":
    main()
