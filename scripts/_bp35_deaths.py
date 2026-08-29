"""bp35: what does crag actually LEARN from each spike death, and what did the frame already say?

The census (`_bp35_glyphcensus.py`) settles the perception half: over 730 actions on levels 1-6 the
two spike orientations occupy TWO signatures, `ubhhgljbnpu` = {5:4, 15:12} and `hzusueifitk` =
{0:1, 5:4, 11:2, 15:9}, and ZERO signatures cover both a lethal cell and a safe one. So a lethal
glyph IS distinguishable in the frame before contact.

That is not the same as being IDENTIFIABLE. `_learn_death` names a kind lethal only when the leg it
emitted carried `verdict == "blind"` — the searcher knew it was stepping onto something unexplained.
A death arriving any other way names nothing, and the tool repeats it. This probe separates the two:

  * every death, with the counter at death (at the cap = the clock, below it = a spike),
  * what `_learn_death` was handed (`blind`, `brink`, `key`) and what it did with it,
  * whether the killing signature was ALREADY in `_lethal` when the body walked into it,
  * and the signature the ENGINE had at the body's landing cell, so a death that named nothing can
    still be attributed.

Expected feedback: if every spike death arrives with `blind` set and the kind is learned first time,
perception buys nothing and the two deaths per board are two DIFFERENT kinds being paid for once
each. If deaths arrive with `blind=None`, or on a signature already known lethal, the deaths are
avoidable and the census says with what.

⛔ `levels_completed` is printed as a NUMBER and compared `> start`.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

PITCH = 6
GRID_W, GRID_H = 11, 39


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

    events: list[dict] = []
    state = {"step": 0}

    orig = cragmod.CragTool._learn_death

    def spy(self, last):
        before = len(self._lethal)
        blind = None if not last else last.get("blind")
        rec = {"at_action": state["step"],
               "level": state["level"], "counter_before": state["counter_before"],
               "last_kind": None if not last else last.get("kind"),
               "blind": None if blind is None else [list(t) for t in blind],
               "blind_already_lethal": bool(blind is not None and blind in self._lethal),
               "blind_in_safe": bool(blind is not None and blind in self._safe),
               "blind_is_open": bool(blind is not None and self._is_open(blind)),
               "brink": None if not last else (None if last.get("brink") is None
                                               else str(last["brink"])),
               "lethal_before": before}
        orig(self, last)
        rec["lethal_after"] = len(self._lethal)
        rec["named_a_kind"] = rec["lethal_after"] > before
        rec["lethal_vocab"] = [[list(t) for t in s] for s in self._lethal]
        events.append(rec)

    cragmod.CragTool._learn_death = spy

    restart_on_game_over = bool(getattr(agent, "restart_on_game_over", False))
    start_done = int(getattr(obs, "levels_completed", 0) or 0)
    prev_count = int(getattr(game, "hbqwwgceeqp", -1))
    deaths: list[dict] = []
    stopped, step = "budget", 0
    for step in range(cap):
        state["step"] = step
        scene = game.oztjzzyqoek
        state["level"] = int(scene.qswcochjodb)
        state["counter_before"] = prev_count
        body_before = tuple(scene.twdpowducb.qumspquyus)
        if agent.is_done([], obs):
            stopped = "agent_is_done"
            break
        act = agent.choose_action([], obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        if obs is None:
            stopped = "obs_none"
            break
        count = int(getattr(game, "hbqwwgceeqp", -1))
        if count < prev_count:
            # The attempt ended. At the cap it is the clock; below it, a spike.
            scene2 = game.oztjzzyqoek
            gdir = -1 if scene2.vivnprldht else 1
            killer = None
            if prev_count not in (64, 128, 192):
                # the cell the body was heading into when it died
                cellnames = [i.name for i in scene2.hdnrlfmyrj.jhzcxkveiw(
                    body_before[0], body_before[1] + gdir)]
                killer = sorted(cellnames)
            deaths.append({"at_action": step, "level": state["level"],
                           "counter_at_death": prev_count,
                           "kind": "CLOCK" if prev_count in (64, 128, 192) else "SPIKE",
                           "body_before": list(body_before),
                           "cell_under_body": killer})
        prev_count = count
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
    spike = [d for d in deaths if d["kind"] == "SPIKE"]
    print(json.dumps({
        "levels_completed_start": start_done,
        "levels_completed_end": end_done,
        "greater_than_start": end_done > start_done,
        "actions_total": step + 1,
        "why_stopped": stopped,
        "deaths": deaths,
        "spike_deaths": len(spike),
        "learn_death_calls": len(events),
        "learn_death_named_a_kind": sum(1 for e in events if e["named_a_kind"]),
        "learn_death_blind_none": sum(1 for e in events if e["blind"] is None),
        "learn_death_blind_already_lethal": sum(1 for e in events if e["blind_already_lethal"]),
        "events": events,
    }))


if __name__ == "__main__":
    main()
