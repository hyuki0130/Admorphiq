"""Census: does a tool that OWNS a later level sit idle through the earlier levels?

Runs one game (index 1..25) through the EXACT score_efficiency.run_game loop, with the
UnifiedAgent wrapped in a transparent spy that records, per action, the level being played
and the tool the harness had chosen. Prints one JSON line.

Rule 7e: entrypoint at the bottom. The score MUST reproduce the banked per-game number or
the tenure record is of no configuration.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

# The runner's own env contract (R101BASE/run.sh): these must not be set.
for _v in ("GF_GIVEUP", "HARNESS_STALL", "HARNESS_CTX"):
    os.environ.pop(_v, None)

GAMES = ("ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 "
         "sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30").split()


class Spy:
    """Transparent proxy over UnifiedAgent recording (level, current tool) per action."""

    def __init__(self, inner):
        object.__setattr__(self, "inner", inner)
        object.__setattr__(self, "trace", [])

    def is_done(self, frames, obs):
        return self.inner.is_done(frames, obs)

    def choose_action(self, frames, obs):
        from admorphiq.harness.loop import levels_completed
        lv = levels_completed(obs)
        act = self.inner.choose_action(frames, obs)
        # _current is set INSIDE choose_action, so read it after.
        self.trace.append((int(lv), self.inner._current))
        return act

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "inner"), name)


def main() -> None:
    idx = int(sys.argv[1])
    title = GAMES[(idx - 1) % len(GAMES)]

    from arc_agi import Arcade, OperationMode

    import score_efficiency as SE

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = arcade.get_environments()
    env_info = None
    for e in envs:
        if title in f"{e.game_id} {e.title or ''}".lower():
            env_info = e
            break
    if env_info is None:
        print(json.dumps({"title": title, "error": "no env"}))
        return

    spy_box = {}

    def factory():
        agent = SE._make_agent("unified", game_id=env_info.game_id)
        s = Spy(agent)
        spy_box["s"] = s
        return s

    res = SE.run_game(arcade, env_info.game_id, env_info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)

    trace = spy_box["s"].trace
    # per level being played -> {tool: action count}, in first-seen order
    by_level: dict[str, dict[str, int]] = {}
    for lv, tool in trace:
        k = str(lv)
        d = by_level.setdefault(k, {})
        t = tool if tool is not None else "_none"
        d[t] = d.get(t, 0) + 1

    from admorphiq.harness.registry import default_tools
    roster = sorted(t.name for t in default_tools())

    print(json.dumps({
        "title": title,
        "game_id": env_info.game_id,
        "score": res.get("game_score"),
        "levels_completed": res.get("levels_completed"),
        "win_levels": res.get("win_levels"),
        "total_actions": res.get("total_actions"),
        "by_level": by_level,
        "n_tools": len(roster),
        "roster": roster,
    }))


if __name__ == "__main__":
    main()
