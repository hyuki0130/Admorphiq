"""wa30 through the REAL harness, with level 9 instrumented attempt by attempt.

⛔ Runs the whole game from level 1, not `set_level(8)`. Two reasons, both paid for elsewhere in
this repo: the tool's own bookkeeping (`_friendly`, `_removable`, `_walkers`) is carried ACROSS
levels by design, so a tool dropped straight onto level 9 is a different tool; and levels 1-8 are
all at score 1.0 with zero headroom, so their action counts have to be readable in the same run
that reads level 9 or a change cannot be judged.

What it reports, per attempt at level 9 (the level restarts when its 70-action counter runs out,
so the harness gets several):

  * the ENGINE's own count of pieces resting in a bay, and which piece is left over;
  * who delivered each piece — the carrier or one of the two helpers — credited by who last held
    it, because a piece can be delivered twice if a thief takes it back out;
  * the tool's own `alone` number for every piece at the attempt's first decision: the straight
    line to the nearest thing it believes walks. That is the quantity `_start_haul` ranks on, and
    the sealed second helper is the reason to look at it;
  * whether the attempts DIFFER. A deterministic tool spends every retry the same way.

⛔ `levels_completed` is printed as a NUMBER and compared with `> start`. Level 9 is the last, so
a real clear never increments `level_index`, and a collapse to level 0 looks exactly like a clear
to anything that tests `!=`.
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")

C = 4


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.shepherd import ShepherdRelayTool

    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 1400

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what the harness scores")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("wa30"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    game = getattr(env, "_game", None) or getattr(env, "game", None)

    tools = default_tools()
    shep = next((t for t in tools if isinstance(t, ShepherdRelayTool)), None)
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)

    def cell(s):
        return (s.y // C, s.x // C)

    def pieces():
        return game.current_level.get_sprites_by_tag("geezpjgiyd")

    def covered():
        return sum(1 for s in pieces()
                   if (s.x, s.y) in game.wyzquhjerd and s not in game.zmqreragji)

    def role(holder):
        if holder is None:
            return None
        tags = set(getattr(holder, "tags", ()))
        if "wbmdvjhthc" in tags:
            return "carrier"
        if "kdweefinfi" in tags:
            return "helper"
        if "ysysltqlke" in tags:
            return "thief"
        return "?"

    start_done = int(getattr(obs, "levels_completed", 0) or 0)
    frames = [obs]
    levels = start_done
    per_level: list[tuple[int, int]] = []      # (level number reached, action index)
    last_mark = 0
    attempts: list[dict] = []
    cur: dict | None = None
    prev_steps = None
    held_by: dict[int, str] = {}               # id(piece) -> role of last holder
    step = 0
    cleared = False

    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        who = str(agent._current)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now > levels:
            per_level.append((now, step + 1 - last_mark))
            last_mark = step + 1
            levels = now
        if levels != 8:
            continue

        steps_left = game.kuncbnslnm.current_steps
        if prev_steps is None or steps_left > prev_steps:
            # The counter only ever falls within an attempt, so a rise IS the restart.
            if cur is not None:
                attempts.append(cur)
            movers = [cell(s) for s in game.current_level.get_sprites_by_tag("kdweefinfi")]
            alone = {}
            if shep is not None and shep._actors:
                seen = sorted(shep._actors)
                for s in pieces():
                    pc = cell(s)
                    alone[str(pc)] = min(
                        [abs(pc[0] - m[0]) + abs(pc[1] - m[1]) for m in seen], default=-1)
            cur = {"attempt": len(attempts) + 1, "start_action": step + 1,
                   "movers_engine": [str(m) for m in movers],
                   "tool_actors": {str(k): v for k, v in (shep._actors or {}).items()}
                   if shep is not None else {},
                   "tool_alone_span": alone,
                   "deliveries": [], "who": {}, "final_covered": None, "left_over": []}
            held_by = {}
        prev_steps = steps_left

        for s in pieces():
            h = role(game.zmqreragji.get(s))
            if h is not None:
                held_by[id(s)] = h
        assert cur is not None
        cur["who"][who] = cur["who"].get(who, 0) + 1
        cov = covered()
        if not cur["deliveries"] or cur["deliveries"][-1][1] != cov:
            cur["deliveries"].append([step + 1 - cur["start_action"] + 1, cov])

        if cov == len(pieces()):
            cleared = True

    if cur is not None:
        cur["final_covered"] = covered()
        cur["left_over"] = [str(cell(s)) for s in pieces()
                            if (s.x, s.y) not in game.wyzquhjerd or s in game.zmqreragji]
        cur["credit"] = {}
        for s in pieces():
            if (s.x, s.y) in game.wyzquhjerd and s not in game.zmqreragji:
                r = held_by.get(id(s), "none")
                cur["credit"][r] = cur["credit"].get(r, 0) + 1
        attempts.append(cur)

    end_done = int(getattr(obs, "levels_completed", 0) or 0)
    sig = [(a["final_covered"], tuple(tuple(d) for d in a["deliveries"])) for a in attempts]
    print(json.dumps({
        "levels_completed_start": start_done,
        "levels_completed_end": end_done,
        "greater_than_start": end_done > start_done,
        "engine_win_seen": cleared,
        "actions_total": step + 1,
        "per_level_actions": per_level,
        "attempts_at_level9": len(attempts),
        "attempts_identical": len(set(map(str, sig))) <= 1,
        "attempt_signatures": [str(s) for s in sig],
        "detail": attempts[:4],
    }))


if __name__ == "__main__":
    main()
