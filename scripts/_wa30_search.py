"""Hill-climb the CARRIER'S SCHEDULE for wa30 level 9, each candidate scored by the real engine.

Two searches saturate at 8 of 9: a primitive beam over key presses (width 1000) and a beam over
whole deliveries (width 500).  Both are myopic in the same way — they rank a partial schedule by
what it has banked so far, and the delivery that decides this board pays off late (the piece on
the far side of the split wall costs about sixteen actions and returns one).

So rank whole schedules instead.  A candidate is: which pieces the carrier takes, in what order,
into which bay, with how long it stands still first — standing still is a real move here because
the working mover retargets to the nearest free piece and delivers more when the carrier is not
competing for it.  Each candidate is replayed in the real `Wa30` object for the level's full
70-action allowance, and scored on pieces RESTING in a bay when the counter runs out, then on
actions to spare.

One seed per process.  Prints the winning action string when a candidate clears.
"""
from __future__ import annotations

import copy
import json
import sys
import time
from collections import deque

C = 4
DIRS = {1: (0, -C), 2: (0, C), 3: (-C, 0), 4: (C, 0)}


def main() -> None:
    import numpy as np
    from arc_agi import Arcade, OperationMode
    from arcengine import ActionInput
    from arcengine import GameAction as EGA
    from arcengine.enums import GameState

    seed = int(sys.argv[1])
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 900
    rng = np.random.default_rng(seed)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("wa30"))
    env = arcade.make(info.game_id)
    env.reset()
    root = env._game
    root.set_level(8)

    def clone(gm):
        memo = {id(gm._clean_levels): gm._clean_levels}
        for i, lv in enumerate(gm._levels):
            if i != gm.level_index:
                memo[id(lv)] = lv
        return copy.deepcopy(gm, memo)

    START = clone(root)
    P0 = [(s.x, s.y) for s in root.current_level.get_sprites_by_tag("geezpjgiyd")]
    BAYS = sorted(b for b in root.wyzquhjerd if b[0] % C == 0 and b[1] % C == 0)
    N = len(P0)

    def pieces(gm):
        return gm.current_level.get_sprites_by_tag("geezpjgiyd")

    def player(gm):
        return gm.current_level.get_sprites_by_tag("wbmdvjhthc")[0]

    def covered(gm):
        return sum(1 for s in pieces(gm)
                   if (s.x, s.y) in gm.wyzquhjerd and s not in gm.zmqreragji)

    def bfs(gm, start, goal, passable):
        seen = {start}
        q = deque([[start]])
        while q:
            path = q.popleft()
            if goal(path[-1]):
                return path
            for dx, dy in DIRS.values():
                nxt = (path[-1][0] + dx, path[-1][1] + dy)
                if nxt not in seen and passable(nxt):
                    seen.add(nxt)
                    q.append(path + [nxt])
        return None

    def dir_to(a, b):
        for k, (dx, dy) in DIRS.items():
            if (a[0] + dx, a[1] + dy) == b:
                return k
        return None

    def facing(p, t):
        r = p.rotation
        return ((p.x, p.y - C) == t if r == 0 else
                (p.x, p.y + C) == t if r == 180 else
                (p.x + C, p.y) == t if r == 90 else (p.x - C, p.y) == t)

    def pass_dir(gm):
        p = player(gm)
        for k, (dx, dy) in DIRS.items():
            if not gm.kblzhbvysd((p.x + dx, p.y + dy)):
                return k
        return 1

    def rollout(genome, want_log=False):
        """order: list of piece-slot indices; bay: bay index per slot; wait: pause before each."""
        order, baysel, waits, kill = genome
        gm = clone(START)
        log = []
        qi = 0
        pause = 0
        cleared = None
        for _ in range(70):
            if gm._state in (GameState.GAME_OVER, GameState.WIN):
                break
            p = player(gm)
            here = (p.x, p.y)
            a = None
            if kill:
                tl = gm.current_level.get_sprites_by_tag("ysysltqlke")
                if tl and p not in gm.nsevyuople:
                    t = tl[0]
                    if (abs(t.x - p.x) + abs(t.y - p.y)) // C <= kill:
                        tp = (t.x, t.y)
                        adj = {(tp[0] + dx, tp[1] + dy) for dx, dy in DIRS.values()}
                        if here in adj:
                            a = 5 if facing(p, tp) else dir_to(here, tp)
                        else:
                            pa = bfs(gm, here, lambda v: v in adj, gm.kblzhbvysd)
                            if pa and len(pa) > 1:
                                a = dir_to(pa[0], pa[1])
            if a is None and p in gm.nsevyuople:
                held = gm.nsevyuople[p]
                occ = {(s.x, s.y) for s in pieces(gm) if s is not held}
                want = BAYS[baysel[qi % len(baysel)] % len(BAYS)]
                if want in occ:
                    want = None
                if (held.x, held.y) in gm.wyzquhjerd:
                    a = 5
                else:
                    dx, dy = held.x - p.x, held.y - p.y
                    goals = ({want} if want else {b for b in BAYS if b not in occ})
                    pa = bfs(gm, here, lambda v: (v[0] + dx, v[1] + dy) in goals,
                             lambda v: gm.fuykgiiwit(p, held, v))
                    a = dir_to(pa[0], pa[1]) if pa and len(pa) > 1 else 5
            elif a is None:
                live = {(s.x, s.y) for s in pieces(gm)}
                while qi < len(order):
                    tgt = P0[order[qi]]
                    if tgt in live and tgt not in gm.wyzquhjerd:
                        break
                    qi += 1
                    pause = 0
                if qi >= len(order):
                    a = pass_dir(gm)
                else:
                    if pause < waits[qi]:
                        pause += 1
                        a = pass_dir(gm)
                    else:
                        tgt = P0[order[qi]]
                        adj = {(tgt[0] + dx, tgt[1] + dy) for dx, dy in DIRS.values()}
                        if here in adj:
                            a = 5 if facing(p, tgt) else dir_to(here, tgt)
                        else:
                            pa = bfs(gm, here, lambda v: v in adj, gm.kblzhbvysd)
                            a = dir_to(pa[0], pa[1]) if pa and len(pa) > 1 else pass_dir(gm)
            a = a or pass_dir(gm)
            log.append(a)
            gm._set_action(ActionInput(id=EGA.from_id(a)))
            gm.step()
            if gm._state == GameState.WIN or gm.level_index > 8:
                cleared = len(log)
                break
        return covered(gm), gm.kuncbnslnm.current_steps, cleared, (log if want_log else None)

    def fresh():
        order = list(rng.permutation(N))
        return (order,
                [int(rng.integers(0, len(BAYS))) for _ in range(N)],
                [int(rng.integers(0, 3)) * int(rng.integers(0, 6)) for _ in range(N)],
                int(rng.choice([0, 0, 2, 4])))

    def mutate(g):
        order, baysel, waits, kill = list(g[0]), list(g[1]), list(g[2]), g[3]
        r = rng.random()
        if r < 0.4:
            i, j = int(rng.integers(0, N)), int(rng.integers(0, N))
            order[i], order[j] = order[j], order[i]
        elif r < 0.6:
            i = int(rng.integers(0, N))
            j = int(rng.integers(0, N))
            v = order.pop(i)
            order.insert(j, v)
        elif r < 0.8:
            baysel[int(rng.integers(0, N))] = int(rng.integers(0, len(BAYS)))
        elif r < 0.95:
            waits[int(rng.integers(0, N))] = int(rng.integers(0, 8))
        else:
            kill = int(rng.choice([0, 2, 4, 6]))
        return (order, baysel, waits, kill)

    best = None
    best_fit = (-1, -1)
    tries = 0
    t0 = time.time()
    cur = fresh()
    cur_fit = rollout(cur)[:2]
    since = 0
    while time.time() - t0 < seconds:
        cand = mutate(cur)
        cov, left, cleared, _ = rollout(cand)
        tries += 1
        if cleared:
            _, _, _, log = rollout(cand, want_log=True)
            order, baysel, waits, kill = cand
            print(json.dumps({"seed": seed, "CLEARED": True, "actions": cleared,
                              "tries": tries,
                              "carrier_order": [list(P0[i]) for i in order],
                              "bays": [list(BAYS[baysel[i] % len(BAYS)]) for i in range(N)],
                              "waits": list(waits), "kill_radius": kill,
                              "witness": log}))
            return
        fit = (cov, left)
        if fit >= cur_fit:
            cur, cur_fit = cand, fit
            since = 0
        else:
            since += 1
            if since > 120:
                cur = fresh()
                cur_fit = rollout(cur)[:2]
                since = 0
        if fit > best_fit:
            best_fit, best = fit, cand
            print(f"[{seed}] try {tries}: covered {fit[0]}/9, {fit[1]} actions to spare",
                  file=sys.stderr, flush=True)
    print(json.dumps({"seed": seed, "CLEARED": False, "best_covered": best_fit[0],
                      "spare": best_fit[1], "tries": tries,
                      "order": [P0[i] for i in best[0]] if best else None}))


if __name__ == "__main__":
    main()
