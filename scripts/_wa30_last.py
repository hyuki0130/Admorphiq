"""wa30 level 9 stops ONE piece short — this asks which piece, and why it never lands.

The 30-way policy sweep put the shipped harness at 8 of 9 pieces delivered inside a single
70-action attempt, nine attempts running, never 9.  Two very different things produce that:
the attempt RUNS OUT with a piece still walking, or the count reaches 8 early and then sits
there because the last piece cannot be delivered at all.  They want opposite repairs.

Per attempt this records the action at which each delivery happened, the state at the moment
the step counter kills the attempt, and for every undelivered piece: where it is, who holds it,
whether it stands in the den, and whether the engine's OWN passability rule
(`fuykgiiwit`, the rule the game uses to decide whether a carrier may drag it) admits a route
from it to a bay cell nobody is standing on.

One attempt index per process.
"""
from __future__ import annotations

import json
import sys
from collections import deque

C = 4
DIRS = ((0, -C), (0, C), (-C, 0), (C, 0))


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.types import GameAction

    job = int(sys.argv[1])
    attempts_wanted = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    conv = AdmorphiqAdapter._convert_action

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("wa30"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    game = env._game
    game.set_level(8)
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]

    def pieces():
        return game.current_level.get_sprites_by_tag("geezpjgiyd")

    def covered():
        return sum(1 for s in pieces()
                   if (s.x, s.y) in game.wyzquhjerd and s not in game.zmqreragji)

    def deliverable(piece):
        """Is there a route for SOME carrier to drag this piece onto an empty bay cell?

        Uses the engine's own two-sprite passability rule with the carrier standing on the
        cell the piece would be dragged from, i.e. exactly what `cyjrduhzmz` walks.
        """
        occupied = {(s.x, s.y) for s in pieces() if s is not piece}
        openbay = [b for b in game.wyzquhjerd if b not in occupied]
        if not openbay:
            return "no_open_bay"
        if (piece.x, piece.y) in openbay:
            return "already_on_bay"
        start = (piece.x, piece.y)
        seen = {start}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur in openbay:
                return "reachable"
            for dx, dy in DIRS:
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt in seen:
                    continue
                # the piece itself is in pkbufziase; treat its own cell as free
                blocked = (nxt in game.pkbufziase and nxt != start) or nxt in game.qthdiggudy
                if not blocked:
                    seen.add(nxt)
                    q.append(nxt)
        return "walled_off"

    report = []
    for attempt in range(attempts_wanted):
        deliveries = []
        last = covered()
        used = 0
        while True:
            state = str(getattr(game, "_state", ""))
            if "GAME_OVER" in state or "WIN" in state:
                break
            action = agent.choose_action(frames, obs)
            obs = env.step(action)
            frames.append(obs)
            frames[:] = frames[-16:]
            used += 1
            c = covered()
            if c != last:
                deliveries.append((used, c))
                last = c
            if game.level_index > 8:
                print(json.dumps({"job": job, "CLEARED": True, "level_index": game.level_index,
                                  "attempt": attempt, "actions": used}))
                return
            if used > 200:
                break
        missing = []
        for s in pieces():
            if (s.x, s.y) in game.wyzquhjerd and s not in game.zmqreragji:
                continue
            holder = game.zmqreragji.get(s)
            missing.append({
                "at": [s.x, s.y],
                "held_by": (list(holder.tags) or [holder.name]) if holder else None,
                "in_den": (s.x, s.y) in game.lqctaojiby,
                "route": deliverable(s),
            })
        rec = {"attempt": attempt, "actions_used": used,
               "steps_left": game.kuncbnslnm.current_steps,
               "state": str(getattr(game, "_state", "")),
               "covered_at_end": covered(), "deliveries": deliveries,
               "missing": missing,
               "thieves_left": len(game.current_level.get_sprites_by_tag("ysysltqlke"))}
        report.append(rec)
        print(f"[{job}] attempt {attempt}: {used} actions, covered {covered()}/9, "
              f"missing {[m['route'] for m in missing]}", file=sys.stderr, flush=True)
        obs = env.step(conv(GameAction.reset()))
        frames.append(obs)
        if game.level_index != 8:
            game.set_level(8)

    print(json.dumps({"job": job, "CLEARED": False, "report": report}))


if __name__ == "__main__":
    main()
