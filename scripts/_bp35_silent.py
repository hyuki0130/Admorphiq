"""WHY `crag` goes silent on bp35's sixth board — the EMPTY path, named rather than assumed.

Measured first (`scripts/_bp35_diag.py`, scorer-faithful loop): crag clears boards 1-5 outright,
acts for THIRTEEN actions on board 6, and is never heard from again; `graph` inherits the remaining
~450 actions and dies on the 64-action clock seven times, every attempt a DIFFERENT sequence. So
bp35 is not wa30 — its retries are not replays — and the question is the other one CLAUDE.md names:
does the specialist propose nothing, and if so, what does it say the reason is?

crag has a permanent kill switch: `_quit` counts idle turns, sixteen of them make a `_mute`, three
mutes set `_refuted`, and `detect` returns 0.0 for the rest of the GAME once refuted (`reset` clears
`_mute` per level but never `_refuted`). This probe wraps `_quit`, `detect` and `propose` and reports
the reason string every time crag hands the turn back, plus its own `trace()` at that moment.

⛔ Reports `levels_completed` as a NUMBER. Runs the scorer's own agent factory and its exact loop —
a hand-rolled loop clears FOUR boards where the scorer clears five.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState


    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(se)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = se._make_agent("unified", info.game_id)
    crag = agent.tools.get("crag")
    if crag is None:
        print(json.dumps({"error": "crag not in the agent's tool list"}))
        return

    log: list[dict] = []
    quits: Counter[str] = Counter()
    state = {"level": 0}

    raw_quit, raw_detect, raw_propose = crag._quit, crag.detect, crag.propose

    def quit_spy(why: str):
        quits[f"L{state['level']}:{why}"] += 1
        if state["level"] >= 5 and len(log) < 60:
            log.append({"lvl": state["level"], "why": why, "idle": crag._idle,
                        "mute": crag._mute, "refuted": crag._refuted,
                        "trace": crag.trace()[:200]})
        return raw_quit(why)

    def detect_spy(frames, o):
        v = raw_detect(frames, o)
        state["last_detect"] = v
        return v

    def propose_spy(frames, o):
        out = raw_propose(frames, o)
        state["last_len"] = len(out)
        return out

    crag._quit, crag.detect, crag.propose = quit_spy, detect_spy, propose_spy

    restart_on_game_over = bool(getattr(agent, "restart_on_game_over", False))
    levels = int(getattr(obs, "levels_completed", 0) or 0)
    start = levels
    first_refuted_at = None
    detect_after: list[float] = []
    step = 0
    for step in range(cap):
        state["level"] = levels
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        if obs is None:
            break
        if crag._refuted and first_refuted_at is None:
            first_refuted_at = {"action": step + 1, "levels_completed": levels,
                                "trace": crag.trace()[:300]}
        if first_refuted_at is not None and len(detect_after) < 5:
            detect_after.append(raw_detect([], obs))
        levels = int(getattr(obs, "levels_completed", levels) or 0)
        if getattr(obs, "state", None) == GameState.WIN:
            break
        if getattr(obs, "state", None) == GameState.GAME_OVER:
            if not restart_on_game_over:
                break
            obs = env.step(GameAction.RESET)
            if obs is None:
                break

    print(json.dumps({
        "levels_completed_start": start,
        "levels_completed_end": levels,
        "greater_than_start": levels > start,
        "actions": step + 1,
        "crag_refuted": crag._refuted,
        "first_refuted_at": first_refuted_at,
        "detect_after_refuted": detect_after,
        "quit_reasons": dict(quits.most_common(20)),
        "wall_quits": log[:25],
    }))


if __name__ == "__main__":
    main()
