"""wa30 level 9 in ONE 70-action attempt: does a PARTITION of the pieces bank all nine?

Measured facts this stands on, all from this round:
  * the declared StepCounter of 70 IS enforced — the raw engine reaches GameState.GAME_OVER on
    action 70 and the level resets, nine times in a 700-action run, every policy;
  * the shipped harness banks 8 of 9 inside one attempt and the ninth is `reachable`;
  * the human baseline for this level is 415 actions, and since an attempt is 70 actions the
    human's clear happened inside ONE of them — so a <=70-action solution EXISTS.

The board (cells, 16x16): a wall column at col 9 rows 0-7 splits it. LEFT holds six pieces, the
one working mover, the den, and the 3x3 bay. RIGHT holds three pieces and a 2-cell bay; its mover
is sealed above a no-go band and moves zero cells. So the natural split is: the carrier takes the
RIGHT three (the mover can never reach them) and leaves the LEFT six to the mover.

Each process runs one (order, thief-policy) variant of that split and reports the count at the
moment the step counter kills the attempt, with the per-delivery action numbers.
"""
from __future__ import annotations

import json
import sys
from collections import deque

C = 4
DIRS = {1: (0, -C), 2: (0, C), 3: (-C, 0), 4: (C, 0)}


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.types import ActionType, GameAction

    job = int(sys.argv[1])
    order_idx = (job - 1) % 8
    thief_idx = ((job - 1) // 8) % 3
    conv = AdmorphiqAdapter._convert_action

    def act(n):
        return conv(GameAction.simple(ActionType(n)))

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("wa30"))
    env = arcade.make(info.game_id)
    env.reset()
    game = env._game
    game.set_level(8)



    def pieces():
        return game.current_level.get_sprites_by_tag("geezpjgiyd")

    def movers():
        return game.current_level.get_sprites_by_tag("kdweefinfi")

    def thieves():
        return game.current_level.get_sprites_by_tag("ysysltqlke")

    def player():
        return game.current_level.get_sprites_by_tag("wbmdvjhthc")[0]

    def covered():
        return sum(1 for s in pieces()
                   if (s.x, s.y) in game.wyzquhjerd and s not in game.zmqreragji)

    # --- which pieces can the working mover NEVER reach?  Walk the board from each mover with the
    #     engine's own free-cell rule; a piece on the far side of the split is ours.
    def walkfield(start):
        seen = {start: 0}
        q = deque([start])
        while q:
            cur = q.popleft()
            for dx, dy in DIRS.values():
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt in seen or not game.kblzhbvysd(nxt):
                    continue
                seen[nxt] = seen[cur] + 1
                q.append(nxt)
        return seen

    fields = [walkfield((m.x, m.y)) for m in movers()]

    def mover_reach(cell):
        best = None
        for f in fields:
            for dx, dy in DIRS.values():
                v = (cell[0] - dx, cell[1] - dy)
                if v in f and (best is None or f[v] < best):
                    best = f[v]
        return best

    mine = []
    for s in pieces():
        r = mover_reach((s.x, s.y))
        mine.append(((s.x, s.y), 10**6 if r is None else r))
    mine.sort(key=lambda t: -t[1])
    orphan = [c for c, r in mine if r >= 10**6]
    far = [c for c, r in mine if r < 10**6]
    p0 = player()

    def bays_now():
        occ = {(q.x, q.y) for q in pieces()}
        return [b for b in game.wyzquhjerd
                if b[0] % C == 0 and b[1] % C == 0 and b not in occ]

    allbays = bays_now()

    def drag(c):
        return min(abs(c[0] - b[0]) + abs(c[1] - b[1]) for b in allbays) // C

    def walk(c):
        return (abs(c[0] - p0.x) + abs(c[1] - p0.y)) // C

    cells = [c for c, _ in mine]
    if order_idx == 0:        # the pieces the mover reaches LAST, nearest to us first
        order = sorted(orphan + far[:3], key=walk)
    elif order_idx == 1:      # the same set, farthest from us first
        order = sorted(orphan + far[:3], key=lambda c: -walk(c))
    elif order_idx == 2:      # orphans only
        order = sorted(orphan, key=walk)
    elif order_idx == 3:      # orphans + everything the mover reaches after 8 steps
        order = sorted(orphan + [c for c, r in mine if 8 <= r < 10**6], key=walk)
    elif order_idx == 4:      # the DEAREST drags first — the mover cannot afford those
        order = sorted(cells, key=lambda c: -drag(c))
    elif order_idx == 5:      # dearest total job first (walk to it, then drag it)
        order = sorted(cells, key=lambda c: -(drag(c) + walk(c)))
    elif order_idx == 6:      # anything whose drag crosses the board, then cheapest-first
        far_drag = sorted([c for c in cells if drag(c) > 6], key=lambda c: -drag(c))
        order = far_drag + sorted([c for c in cells if drag(c) <= 6], key=walk)
    else:                     # our own half only (nearer to us than to any mover), dearest first
        ours = [c for c, r in mine if r is not None and walk(c) < r]
        order = sorted(ours or cells, key=lambda c: -(drag(c) + walk(c)))

    def bfs(start, goal, passable):
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

    def pass_action():
        p = player()
        for k, (dx, dy) in DIRS.items():
            if not game.kblzhbvysd((p.x + dx, p.y + dy)):
                return k
        return 1

    def free_bays():
        occ = {(s.x, s.y) for s in pieces()}
        return [b for b in game.wyzquhjerd if b not in occ and b[0] % C == 0 and b[1] % C == 0]

    target = None
    deliveries = []
    log = []
    for step in range(1, 71):
        if str(getattr(game, "_state", "")).find("GAME_OVER") >= 0:
            break
        p = player()
        here = (p.x, p.y)
        a = None

        # thief policy
        tl = thieves()
        if thief_idx and tl and p not in game.nsevyuople:
            t = min(tl, key=lambda s: abs(s.x - p.x) + abs(s.y - p.y))
            span = (abs(t.x - p.x) + abs(t.y - p.y)) // C
            if span <= (2 if thief_idx == 1 else 4):
                tp = (t.x, t.y)
                adj = {(tp[0] + dx, tp[1] + dy) for dx, dy in DIRS.values()}
                if here in adj:
                    a = 5 if facing(p, tp) else dir_to(here, tp)
                else:
                    path = bfs(here, lambda v: v in adj, game.kblzhbvysd)
                    if path and len(path) > 1:
                        a = dir_to(path[0], path[1])

        if a is None and p in game.nsevyuople:
            held = game.nsevyuople[p]
            if (held.x, held.y) in game.wyzquhjerd:
                a = 5
            else:
                dx, dy = held.x - p.x, held.y - p.y
                bays = set(free_bays())
                path = bfs(here, lambda v: (v[0] + dx, v[1] + dy) in bays,
                           lambda v: game.fuykgiiwit(p, held, v))
                a = dir_to(path[0], path[1]) if path and len(path) > 1 else 5
        elif a is None:
            while order and any((s.x, s.y) == order[0] and (s.x, s.y) in game.wyzquhjerd
                                for s in pieces()):
                order.pop(0)
            live = {(s.x, s.y) for s in pieces()}
            while order and order[0] not in live:
                order.pop(0)
            target = order[0] if order else None
            if target is None:
                a = pass_action()
            else:
                adj = {(target[0] + dx, target[1] + dy) for dx, dy in DIRS.values()}
                if here in adj:
                    a = 5 if facing(p, target) else dir_to(here, target)
                else:
                    path = bfs(here, lambda v: v in adj, game.kblzhbvysd)
                    a = dir_to(path[0], path[1]) if path and len(path) > 1 else pass_action()

        before = covered()
        env.step(act(a or pass_action()))
        after = covered()
        if after != before:
            deliveries.append((step, after))
            print(f"[{job}] action {step}: covered {after}/9", file=sys.stderr, flush=True)
        log.append(a)
        if game.level_index > 8 or "WIN" in str(getattr(game, "_state", "")):
            print(json.dumps({"job": job, "order_idx": order_idx, "thief_idx": thief_idx,
                              "CLEARED": True, "actions": step, "level_index": game.level_index,
                              "witness": log}))
            return

    print(json.dumps({"job": job, "order_idx": order_idx, "thief_idx": thief_idx,
                      "CLEARED": False, "covered": covered(),
                      "steps_left": game.kuncbnslnm.current_steps,
                      "orphans": orphan, "order": order, "deliveries": deliveries,
                      "thieves_left": len(thieves())}))


if __name__ == "__main__":
    main()
