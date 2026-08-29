"""wa30 level 9 — what the game's OWN win predicate does under six different policies.

The board: 9 pieces (tag geezpjgiyd), 2 movers (kdweefinfi) that carry pieces INTO the bay,
1 thief (ysysltqlke) that carries them out to a den, one 3x3 bay + two 2x1 bays, 50 walls,
6 no-go cells, and a declared StepCounter of 70.  The win predicate is the game's own
`ymzfopzgbq`: every piece stands on a bay cell AND is held by nobody.

Runs start ON level 9 via `set_level(8)` (the engine's own entry point, so `on_set_level`
re-arms the step counter exactly as arriving there would) and report, per action: the level
index, the step counter, the game state, and the predicate's parts.  Six policies, so six
DIFFERENT questions are asked at once rather than one after another:

  0 pass          press a refused direction every turn — do the two movers finish it alone?
  1 kill+pass     walk to the thief, remove it, then pass — is the thief what undoes the work?
  2 random        is a clear anywhere near random reach?
  3 incumbent     the shipped harness, for a like-for-like timeline
  4 haul          the carrier ferries pieces itself, nearest-first
  5 kill+haul     both

Reports max coverage ever seen, whether the count ever FELL (a piece taken back out), the
number of attempts the step counter forced, and — printed with the level number, never as
"the level changed" — whether it cleared.
"""
from __future__ import annotations

import json
import sys
from collections import deque

C = 4  # the game's own cell size (celomdfhbh)
DIRS = {1: (0, -C), 2: (0, C), 3: (-C, 0), 4: (C, 0)}


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.types import ActionType, GameAction

    job = int(sys.argv[1])
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 700
    mode = (job - 1) % 6
    seed = (job - 1) // 6
    conv = AdmorphiqAdapter._convert_action

    def act(n: int):
        return conv(GameAction.simple(ActionType(n)))

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("wa30"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    game = getattr(env, "_game", None) or getattr(env, "game", None)
    game.set_level(8)

    lvl = game.current_level
    census = {
        "pieces": len(lvl.get_sprites_by_tag("geezpjgiyd")),
        "movers": len(lvl.get_sprites_by_tag("kdweefinfi")),
        "thieves": len(lvl.get_sprites_by_tag("ysysltqlke")),
        "bay_cells": len(game.wyzquhjerd),
        "den_cells": len(game.lqctaojiby),
        "nogo": len(game.qthdiggudy),
        "steps": game.kuncbnslnm.dbdarsgrbj,
    }
    # the instrument must say something it could not say if it were not attached
    if census["pieces"] != 9 or census["thieves"] != 1 or census["movers"] != 2:
        print(json.dumps({"job": job, "error": "not level 9", "census": census}))
        return

    def player():
        return game.current_level.get_sprites_by_tag("wbmdvjhthc")[0]

    def pieces():
        return game.current_level.get_sprites_by_tag("geezpjgiyd")

    def thieves():
        return game.current_level.get_sprites_by_tag("ysysltqlke")

    def covered():
        return sum(1 for s in pieces()
                   if (s.x, s.y) in game.wyzquhjerd and s not in game.zmqreragji)

    def free(v):
        return game.kblzhbvysd(v)

    def bfs(start, goal_test, passable):
        seen = {start}
        q = deque([[start]])
        while q:
            path = q.popleft()
            cur = path[-1]
            if goal_test(cur):
                return path
            for dx, dy in DIRS.values():
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt not in seen and passable(nxt):
                    seen.add(nxt)
                    q.append(path + [nxt])
        return None

    def dir_to(a, b):
        for k, (dx, dy) in DIRS.items():
            if (a[0] + dx, a[1] + dy) == b:
                return k
        return None

    def pass_action():
        p = player()
        here = (p.x, p.y)
        for k, (dx, dy) in DIRS.items():
            if not free((here[0] + dx, here[1] + dy)):
                return k
        return 1

    def facing(p, target):
        r = p.rotation
        if r == 0:
            return (p.x, p.y - C) == target
        if r == 180:
            return (p.x, p.y + C) == target
        if r == 90:
            return (p.x + C, p.y) == target
        return (p.x - C, p.y) == target

    def kill_policy():
        tl = thieves()
        if not tl:
            return None
        p = player()
        here = (p.x, p.y)
        if p in game.nsevyuople:
            return 5
        t = min(tl, key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))
        tpos = (t.x, t.y)
        adj = {(tpos[0] + dx, tpos[1] + dy) for dx, dy in DIRS.values()}
        if here in adj:
            if facing(p, tpos):
                return 5
            return dir_to(here, tpos)
        path = bfs(here, lambda v: v in adj, free)
        if path and len(path) > 1:
            return dir_to(path[0], path[1])
        return None

    def haul_policy():
        p = player()
        here = (p.x, p.y)
        if p in game.nsevyuople:
            held = game.nsevyuople[p]
            dx, dy = held.x - p.x, held.y - p.y
            if (held.x, held.y) in game.wyzquhjerd:
                return 5                                  # arrived — put it down
            path = bfs(here,
                       lambda v: (v[0] + dx, v[1] + dy) in game.wyzquhjerd,
                       lambda v: game.fuykgiiwit(p, held, v))
            if path and len(path) > 1:
                return dir_to(path[0], path[1])
            return 5                                       # boxed in — release
        loose = [s for s in pieces()
                 if (s.x, s.y) not in game.wyzquhjerd and s not in game.zmqreragji]
        if not loose:
            return None
        tgt = min(loose, key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))
        tpos = (tgt.x, tgt.y)
        adj = {(tpos[0] + dx, tpos[1] + dy) for dx, dy in DIRS.values()}
        if here in adj:
            if facing(p, tpos):
                return 5
            return dir_to(here, tpos)
        path = bfs(here, lambda v: v in adj, free)
        if path and len(path) > 1:
            return dir_to(path[0], path[1])
        return None

    agent = None
    frames = [obs]
    if mode == 3:
        from admorphiq.harness.loop import UnifiedAgent
        from admorphiq.harness.registry import default_tools

        def _no_llm(*_a, **_k):
            raise RuntimeError("LLM-free")

        agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)

    import numpy as np
    rng = np.random.default_rng(seed + 1)

    best = covered()
    start_cov = best
    attempt_best = best
    best_attempt = best
    steals = []
    fell = 0
    attempts = 1
    losses = 0
    cleared_at = None
    timeline = [(0, best)]
    for step in range(1, budget + 1):
        state = str(getattr(game, "_state", ""))
        if "GAME_OVER" in state:
            losses += 1
            attempts += 1
            obs = env.step(conv(GameAction.reset()))
            frames.append(obs)
            if game.level_index != 8:
                game.set_level(8)
            timeline.append((step, covered()))   # resync: a reset is not a theft
            best_attempt = max(best_attempt, attempt_best)
            attempt_best = covered()
            continue
        if mode == 0:
            a = pass_action()
        elif mode == 1:
            a = kill_policy() or pass_action()
        elif mode == 2:
            a = int(rng.integers(1, 6))
        elif mode == 3:
            a = None
        elif mode == 4:
            a = haul_policy() or pass_action()
        else:
            a = (kill_policy() if thieves() else haul_policy()) or pass_action()

        if mode == 3:
            action = agent.choose_action(frames, obs)
            obs = env.step(action)
        else:
            obs = env.step(act(a))
        frames.append(obs)
        frames[:] = frames[-16:]

        c = covered()
        if c > best:
            best = c
            timeline.append((step, c))
            print(f"[{job}] action {step}: covered {c}/9 steps={game.kuncbnslnm.current_steps}",
                  file=sys.stderr, flush=True)
        elif c < timeline[-1][1]:
            fell += 1
            timeline.append((step, c))
            held_by_thief = sum(1 for s_ in pieces()
                                if s_ in game.zmqreragji
                                and "ysysltqlke" in game.zmqreragji[s_].tags)
            steals.append((step, timeline[-2][1], c, held_by_thief))
        if c > attempt_best:
            attempt_best = c
        if game.level_index > 8 or "WIN" in str(getattr(game, "_state", "")):
            cleared_at = step
            print(f"[{job}] CLEARED level 9 at action {step}; level_index now "
                  f"{game.level_index}", file=sys.stderr, flush=True)
            break
        if step % 100 == 0:
            print(f"[{job}] action {step}: covered {c}/9 best {best} losses {losses}",
                  file=sys.stderr, flush=True)

    print(json.dumps({
        "job": job, "mode": mode, "seed": seed, "census": census,
        "start_covered": start_cov, "best_covered": best, "final_covered": covered(),
        "count_fell": fell, "losses": losses, "attempts": attempts,
        "best_in_one_attempt": max(best_attempt, attempt_best), "steals": steals[:20],
        "cleared_at": cleared_at, "level_index": game.level_index,
        "thieves_left": len(thieves()), "timeline": timeline[:40],
    }))


if __name__ == "__main__":
    main()
