"""bp35 through the REAL harness, with every ATTEMPT at every level separated out.

⛔ Why attempts and not levels. bp35's levels 1-6 end the attempt at 64 actions (128 on 7-9, 192 on
10) — `render_interface` calls `lose()` the moment the counter reaches the level's cap — and a loss
RESTARTS the level rather than ending the game. `levels_completed` does not move across that
boundary, so a tool watching only that number cannot see it; on wa30 exactly this made six of eight
tries byte-identical replays of the first. bp35 also has a SECOND way to die (landing on a spike),
so the two are separated here by the counter's value at the death: at the cap it is the clock, below
it is a spike.

The scorer charges a cleared level with every action spent dying on it first, which is why the
baseline reads L2 = 87 actions against a 64 allowance: that is one death plus a 23-action clear, not
one slow attempt.

Reports, per attempt: the acting tool, the length, how it ended, and the ACTION SEQUENCE, so
"are the retries the same attempt" is answered by comparing bytes rather than by eye.

⛔ `levels_completed` is printed as a NUMBER and compared `> start`.
"""
from __future__ import annotations

import hashlib
import json
import sys

sys.path.insert(0, "src")


def main() -> None:
    import importlib.util
    from pathlib import Path

    from arc_agi import Arcade, OperationMode

    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    # ⛔ Build the agent with the SCORER'S OWN factory, not a hand-rolled UnifiedAgent. Measured:
    # a hand-rolled one (same tools, same giveup/stall/ctx) cleared FOUR levels where
    # `score_efficiency.py --agent unified` clears five — it omits `draw_llm` and the
    # `no_progress` default, and the difference is a whole level. A diagnostic that disagrees
    # with the instrument being explained is explaining something else.
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

    def counter() -> int:
        return int(getattr(game, "hbqwwgceeqp", -1))

    # ⛔ MIRROR `score_efficiency.run_game` EXACTLY. Two things in it are load-bearing and a
    # hand-rolled loop gets both wrong: it passes an EMPTY frames list to `is_done` /
    # `choose_action` (not the accumulated history), and unless the agent sets
    # `restart_on_game_over` it BREAKS on `GameState.GAME_OVER` instead of playing on. Measured:
    # the hand-rolled version cleared four levels and stopped at 683 actions where the scorer
    # clears five in 740. A diagnostic that disagrees with the instrument being explained is
    # explaining a different run.
    from arcengine import GameAction, GameState

    restart_on_game_over = bool(getattr(agent, "restart_on_game_over", False))
    start_done = int(getattr(obs, "levels_completed", 0) or 0)
    levels = start_done
    attempts: list[dict] = []
    cur = {"levels_completed": levels, "start_action": 1, "acts": [], "tools": {},
           "states": {}}
    prev_count = counter()
    step = 0
    stopped = "budget"

    for step in range(cap):
        if agent.is_done([], obs):
            stopped = "agent_is_done"
            break
        act = agent.choose_action([], obs)
        who = str(agent._current)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        aid = int(getattr(getattr(act, "id", None), "value", -1))
        tag = f"{aid}" if not data else f"{aid}:{data.get('x')},{data.get('y')}"
        obs = env.step(act, data=data) if data else env.step(act)
        if obs is None:
            stopped = "obs_none"
            break
        cur["acts"].append(tag)
        cur["tools"][who] = cur["tools"].get(who, 0) + 1
        st = str(getattr(obs, "state", ""))
        cur["states"][st] = cur["states"].get(st, 0) + 1

        now = int(getattr(obs, "levels_completed", levels) or 0)
        count = counter()
        advanced = now > levels
        restarted = count < prev_count
        if advanced or restarted:
            cur["end_action"] = step + 1
            cur["length"] = len(cur["acts"])
            cur["counter_at_end"] = prev_count
            cur["outcome"] = ("CLEARED" if advanced
                              else "CLOCK" if prev_count in (64, 128, 192) else "SPIKE")
            cur["seq_sha"] = hashlib.sha1(" ".join(cur["acts"]).encode()).hexdigest()[:12]
            attempts.append(cur)
            levels = now
            cur = {"levels_completed": levels, "start_action": step + 2,
                   "acts": [], "tools": {}, "states": {}}
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

    cur["end_action"] = step + 1
    cur["length"] = len(cur["acts"])
    cur["counter_at_end"] = prev_count
    cur.setdefault("outcome", "RUN_END")
    cur["seq_sha"] = hashlib.sha1(" ".join(cur["acts"]).encode()).hexdigest()[:12]
    attempts.append(cur)

    end_done = int(getattr(obs, "levels_completed", 0) or 0)
    rows = [{"n": i + 1, "done": a["levels_completed"],
             "len": a["length"], "out": a["outcome"], "cnt": a["counter_at_end"],
             "sha": a["seq_sha"], "tools": a["tools"], "states": a["states"]}
            for i, a in enumerate(attempts)]
    by_level: dict[int, list[str]] = {}
    for a in attempts:
        by_level.setdefault(a["levels_completed"], []).append(a["seq_sha"])
    print(json.dumps({
        "levels_completed_start": start_done,
        "levels_completed_end": end_done,
        "greater_than_start": end_done > start_done,
        "actions_total": step + 1,
        "why_stopped": stopped,
        "attempts": rows,
        "distinct_sequences_per_level": {str(k): [len(set(v)), len(v)]
                                         for k, v in by_level.items()},
        "wall_first_acts": attempts[-1]["acts"][:40],
    }))


if __name__ == "__main__":
    main()
