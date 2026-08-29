"""bp35: the SECOND spike death on each board arrives with `blind=None`. What did crag think?

Measured by `_bp35_deaths.py`: bp35's four spike deaths split two ways.

    L2 a25  blind={5:4,15:12}           NAMES ubhhgljbnpu   (first spike kind ever seen)
    L2 a59  blind=None                  names NOTHING
    L5 a184 blind={0:1,5:4,11:2,15:9}   NAMES hzusueifitk   (the SAME art flipped = a 2nd kind)
    L5 a198 blind=None                  names NOTHING

`_take` sets `blind` only when the emitted leg's own verdict was "blind" — the searcher knew it was
stepping onto something unexplained. A `blind=None` death is therefore a leg the searcher believed
was SAFE, and the tool cannot learn from it because it has nothing to blame.

This probe records, for every emitted leg, the verdict the searcher assigned, where it expected the
body to come to rest, and where the body actually is at the next turn — then prints the legs
immediately before each death.

Expected feedback: if the leg's `rest` matches the body's real landing, the model is right and the
death is a rule the tool does not have. If `rest` disagrees, the world map placed the fall wrong and
the fix is in the map, not in lethality.

⛔ `levels_completed` is printed as a NUMBER and compared `> start`.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.tools import crag as cragmod

    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 800

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    _se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_se)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    game = getattr(env, "_game", None) or getattr(env, "game", None)
    agent = _se._make_agent("unified", info.game_id)

    legs: list[dict] = []
    state = {"step": 0, "level": 0}

    take = cragmod.CragTool._take

    def spy_take(self):
        peek = self._plan[0] if self._plan else None
        at, gdir = self._at, self._gdir
        step = take(self)
        if peek is not None:
            _s, rest, g, verdict, under = peek
            legs.append({"at_action": state["step"], "level": state["level"],
                         "from": list(at) if at else None, "gdir": gdir,
                         "action": list(step[0:1]) + ([list(step[1])] if step[1] else []),
                         "verdict": verdict, "expect_rest": list(rest) if rest else None,
                         "leg_gdir": g,
                         "under": None if under is None else [list(t) for t in under]})
        return step

    cragmod.CragTool._take = spy_take

    restart_on_game_over = bool(getattr(agent, "restart_on_game_over", False))
    start_done = int(getattr(obs, "levels_completed", 0) or 0)
    prev_count = int(getattr(game, "hbqwwgceeqp", -1))
    prev_lvl = int(getattr(obs, "levels_completed", 0) or 0)
    ends: list[dict] = []
    stopped, step = "budget", 0
    for step in range(cap):
        state["step"] = step
        scene = game.oztjzzyqoek
        state["level"] = int(scene.qswcochjodb)
        body_before = tuple(scene.twdpowducb.qumspquyus)
        grav_before = bool(scene.vivnprldht)
        if agent.is_done([], obs):
            stopped = "agent_is_done"
            break
        nlegs = len(legs)
        act = agent.choose_action([], obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        if obs is None:
            stopped = "obs_none"
            break
        if len(legs) > nlegs:
            legs[-1]["body_before"] = list(body_before)
            legs[-1]["grav_before"] = grav_before
            sc = game.oztjzzyqoek
            legs[-1]["body_after"] = list(sc.twdpowducb.qumspquyus)
            legs[-1]["grav_after"] = bool(sc.vivnprldht)
        count = int(getattr(game, "hbqwwgceeqp", -1))
        now_lvl = int(getattr(obs, "levels_completed", prev_lvl) or 0)
        if count < prev_count:
            ends.append({"at_action": step, "level": state["level"], "counter": prev_count,
                         "kind": "CLEARED" if now_lvl > prev_lvl
                                 else ("CLOCK" if prev_count in (64, 128, 192) else "SPIKE"),
                         "recent_legs": legs[-4:]})
        prev_count, prev_lvl = count, now_lvl
        if getattr(obs, "state", None) == GameState.WIN:
            stopped = "WIN"
            break
        if getattr(obs, "state", None) == GameState.GAME_OVER:
            if not restart_on_game_over:
                stopped = "GAME_OVER_break"
                break
            obs = env.step(GameAction.RESET)
            if obs is None:
                stopped = "obs_none_after_reset"
                break

    end_done = int(getattr(obs, "levels_completed", 0) or 0)
    spikes = [e for e in ends if e["kind"] == "SPIKE"]
    print(json.dumps({
        "levels_completed_start": start_done,
        "levels_completed_end": end_done,
        "greater_than_start": end_done > start_done,
        "actions_total": step + 1,
        "why_stopped": stopped,
        "attempt_ends": [{k: v for k, v in e.items() if k != "recent_legs"} for e in ends],
        "spike_deaths": spikes,
        "legs_emitted": len(legs),
        "verdict_histogram": {v: sum(1 for x in legs if x["verdict"] == v)
                              for v in {x["verdict"] for x in legs}},
    }))


if __name__ == "__main__":
    main()
