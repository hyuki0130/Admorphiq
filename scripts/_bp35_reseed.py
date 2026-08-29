"""bp35 — does RE-SEEDING a lost map beat surrendering the board?

MEASURED FIRST, so the fix is aimed at a named cause and not at a symptom:

  * crag clears boards 1-5 outright and then quits EIGHT times in a row on board 6 with one
    reason, `window does not belong to this board`, its body position frozen at (6,8). It is not
    `_refuted` and its `_mute` is 0 — the harness simply retires it for handing the turn back, and
    `graph` inherits ~450 actions and dies on the 64-action clock seven times.
  * The three causes hiding behind that one word were separated (`scripts/_bp35_lost.py`):
    physics refuses NOTHING once `allow` goes None, and the best alignment achieved is **0.60
    against a 0.82 threshold** — stable, eight events running. So it is neither the admissibility
    window nor the threshold (both of which R101SILENT already tried blind and reverted). The
    window genuinely does not match the map any more.
  * ⛔ And lowering the threshold to admit 0.60 is the one thing that must NOT be done: `_stitch`'s
    own docstring records that a window laid fifteen rows off its home still agrees nine cells in
    ten, and accepting one such false fit taught the tool that a block reverses gravity and cost
    every later board.

So the candidate is the wa30 lesson in its general form: **positional state that no longer matches
the board is worse than no positional state.** After N consecutive losses, throw the MAP away and
re-seed it from the current window — keeping the vocabulary (`_lethal`, `_open`, `_solid`, `_swap`,
`_flip`), which is about the GAME's glyphs and stays true, and dropping only what is about WHERE.

Variants, so the effect is attributable:
  control     the shipped tool
  reseed3     re-seed after 3 consecutive losses
  reseed1     re-seed on the first loss (is the patience doing anything?)
  thresh      lower `_ALIGN_FIT` to 0.55 instead — the thing that must NOT work, run so the claim
              "the threshold is not the fix" is measured rather than asserted

⛔ Scorer's own agent factory and its exact loop; `levels_completed` printed as a NUMBER and
compared `> start`.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

VARIANTS = ["control", "reseed3", "reseed1", "thresh"]


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.tools import crag as cragmod

    job = int(sys.argv[1])
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    kind = VARIANTS[(job - 1) % len(VARIANTS)]

    spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(se)

    if kind == "thresh":
        cragmod._ALIGN_FIT = 0.55

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = se._make_agent("unified", info.game_id)
    crag = agent.tools.get("crag")

    fired = {"reseeds": 0, "lost": 0, "max_run": 0}
    run = {"n": 0}
    if kind in ("reseed3", "reseed1"):
        patience = 3 if kind == "reseed3" else 1
        raw_stitch = crag._stitch

        def stitch_reseed(readings, allow):
            out = raw_stitch(readings, allow)
            if out[0] != "lost":
                run["n"] = 0
                return out
            fired["lost"] += 1
            run["n"] += 1
            fired["max_run"] = max(fired["max_run"], run["n"])
            if run["n"] < patience:
                return out
            # ⛔ Drop only what is about WHERE. `_world`/`_opening`/`_home` and the body's own
            # position are the map; `_lethal`, `_open`, `_solid`, `_swap`, `_flip` are the
            # game's glyph vocabulary and are as true on this window as on the last one.
            run["n"] = 0
            fired["reseeds"] += 1
            crag._world = {}
            crag._opening = None
            crag._home = None
            crag._at = None
            crag._last = None
            crag._expect = None
            crag._plan = []
            crag._idle = 0
            return raw_stitch(readings, allow)

        crag._stitch = stitch_reseed

    restart_on_game_over = bool(getattr(agent, "restart_on_game_over", False))
    levels = int(getattr(obs, "levels_completed", 0) or 0)
    start = levels
    attempts: list[dict] = []
    cur = {"done": levels, "acts": [], "tools": {}}
    prev_count = int(getattr(env._game, "hbqwwgceeqp", -1))
    step = 0
    for step in range(cap):
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        who = str(agent._current)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        aid = int(getattr(getattr(act, "id", None), "value", -1))
        obs = env.step(act, data=data) if data else env.step(act)
        if obs is None:
            break
        cur["acts"].append(f"{aid}" if not data else f"{aid}:{data.get('x')},{data.get('y')}")
        cur["tools"][who] = cur["tools"].get(who, 0) + 1
        now = int(getattr(obs, "levels_completed", levels) or 0)
        count = int(getattr(env._game, "hbqwwgceeqp", -1))
        if now > levels or count < prev_count:
            cur["len"] = len(cur["acts"])
            cur["out"] = ("CLEARED" if now > levels
                          else "CLOCK" if prev_count in (64, 128, 192) else "SPIKE")
            cur["sha"] = hashlib.sha1(" ".join(cur["acts"]).encode()).hexdigest()[:10]
            cur.pop("acts")
            attempts.append(cur)
            levels = now
            cur = {"done": levels, "acts": [], "tools": {}}
        prev_count = count
        if getattr(obs, "state", None) == GameState.WIN:
            break
        if getattr(obs, "state", None) == GameState.GAME_OVER:
            if not restart_on_game_over:
                break
            obs = env.step(GameAction.RESET)
            if obs is None:
                break
    cur["len"] = len(cur["acts"])
    cur["out"] = "RUN_END"
    cur["sha"] = hashlib.sha1(" ".join(cur["acts"]).encode()).hexdigest()[:10]
    cur.pop("acts")
    attempts.append(cur)

    print(json.dumps({
        "job": job, "variant": kind,
        "levels_completed_start": start, "levels_completed_end": levels,
        "greater_than_start": levels > start, "actions": step + 1,
        "fired": fired, "align_fit": cragmod._ALIGN_FIT,
        "attempts": attempts,
    }))


if __name__ == "__main__":
    main()
