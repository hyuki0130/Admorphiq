"""A schedule search for wa30 level 9, over DELIVERIES rather than key presses.

The primitive-action beam (`_wa30_macro`'s sibling `_wa30_beam.py`) reaches 8 of 9 at width 80
and stops there; 70 primitive actions with a branching factor of 5 is 5^70, and a myopic
heuristic cannot see a delivery that only pays off ten actions later.  This searches the space
the board is actually built from: the carrier's whole delivery of one piece into one bay, run
in the real engine, with the movers and the thief stepping alongside exactly as they will.

A branch is "carry piece P into bay B" or "stand still for k actions" (standing still is a real
choice here — the working mover delivers more when the carrier is not competing for its pieces).
Scored on pieces resting in a bay, then on actions left.

Existence is not in doubt: the human baseline for this level is 415 actions and an attempt is
70, so the human's clear happened inside one attempt.  What is in doubt is the SCHEDULE.
"""
from __future__ import annotations

import copy
import json
import sys
from collections import deque

C = 4
DIRS = {1: (0, -C), 2: (0, C), 3: (-C, 0), 4: (C, 0)}
WAITS = (2, 5, 10, 20)


def main() -> None:
    import numpy as np
    from arc_agi import Arcade, OperationMode
    from arcengine import ActionInput
    from arcengine import GameAction as EGA
    from arcengine.enums import GameState

    job = int(sys.argv[1])
    widths = (60, 120, 250, 500)
    width = widths[(job - 1) % 4]
    nbays = 1 + ((job - 1) // 4) % 3          # how many bay choices per piece
    seed = (job - 1) // 12
    rng = np.random.default_rng(seed + 1)

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

    def advance(gm, a):
        gm._set_action(ActionInput(id=EGA.from_id(a)))
        gm.step()
        return gm._state

    def pieces(gm):
        return gm.current_level.get_sprites_by_tag("geezpjgiyd")

    def player(gm):
        return gm.current_level.get_sprites_by_tag("wbmdvjhthc")[0]

    def covered(gm):
        return sum(1 for s in pieces(gm)
                   if (s.x, s.y) in gm.wyzquhjerd and s not in gm.zmqreragji)

    def bays(gm):
        occ = {(s.x, s.y) for s in pieces(gm)}
        return [b for b in gm.wyzquhjerd
                if b[0] % C == 0 and b[1] % C == 0 and b not in occ]

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

    def deliver(gm, piece_cell, bay_cell, log, cap=40):
        """Walk to the piece, grip it, tow it onto `bay_cell`, let go. In the real engine."""
        for _ in range(cap):
            st = gm._state
            if st in (GameState.GAME_OVER, GameState.WIN):
                return st
            p = player(gm)
            here = (p.x, p.y)
            if p in gm.nsevyuople:
                held = gm.nsevyuople[p]
                if (held.x, held.y) == bay_cell:
                    log.append(5)
                    st = advance(gm, 5)
                    return st
                dx, dy = held.x - p.x, held.y - p.y
                path = bfs(gm, here, lambda v: (v[0] + dx, v[1] + dy) == bay_cell,
                           lambda v: gm.fuykgiiwit(p, held, v))
                if not path or len(path) < 2:
                    return None
                a = dir_to(path[0], path[1])
            else:
                live = {(s.x, s.y) for s in pieces(gm)}
                if piece_cell not in live:
                    return gm._state          # somebody else moved it; the branch is over
                adj = {(piece_cell[0] + dx, piece_cell[1] + dy) for dx, dy in DIRS.values()}
                if here in adj:
                    a = 5 if facing(p, piece_cell) else dir_to(here, piece_cell)
                else:
                    path = bfs(gm, here, lambda v: v in adj, gm.kblzhbvysd)
                    if not path or len(path) < 2:
                        return None
                    a = dir_to(path[0], path[1])
            log.append(a)
            st = advance(gm, a)
            if st in (GameState.GAME_OVER, GameState.WIN):
                return st
        return None

    def wait(gm, k, log):
        for _ in range(k):
            a = pass_dir(gm)
            log.append(a)
            st = advance(gm, a)
            if st in (GameState.GAME_OVER, GameState.WIN):
                return st
        return gm._state

    beam = [(root, [], covered(root))]
    best = covered(root)
    for d in range(1, 12):
        cand = []
        for gm, log, _ in beam:
            live = [(s.x, s.y) for s in pieces(gm) if (s.x, s.y) not in gm.wyzquhjerd]
            openb = bays(gm)
            branches = []
            for pc in live:
                ranked = sorted(openb, key=lambda b: abs(b[0] - pc[0]) + abs(b[1] - pc[1]))
                for b in ranked[:nbays]:
                    branches.append(("go", pc, b))
            for k in WAITS:
                branches.append(("wait", k, None))
            for kind, x, y in branches:
                nxt = clone(gm)
                nlog = list(log)
                st = deliver(nxt, x, y, nlog) if kind == "go" else wait(nxt, x, nlog)
                if st == GameState.WIN or nxt.level_index > 8:
                    print(json.dumps({"job": job, "width": width, "nbays": nbays, "seed": seed,
                                      "CLEARED": True, "actions": len(nlog),
                                      "level_index": nxt.level_index, "witness": nlog}))
                    return
                if st is None or st == GameState.GAME_OVER:
                    continue
                cov = covered(nxt)
                if cov > best:
                    best = cov
                    print(f"[{job}] macro-depth {d}: covered {cov}/9 after {len(nlog)} actions",
                          file=sys.stderr, flush=True)
                left = nxt.kuncbnslnm.current_steps
                cand.append((1000 * cov + left + float(rng.random()), nxt, nlog, cov))
        if not cand:
            break
        cand.sort(key=lambda t: -t[0])
        beam = [(g, lg, c) for _, g, lg, c in cand[:width]]
        print(f"[{job}] macro-depth {d}: beam {len(beam)} best {best}",
              file=sys.stderr, flush=True)

    print(json.dumps({"job": job, "width": width, "nbays": nbays, "seed": seed,
                      "CLEARED": False, "best_covered": best}))


if __name__ == "__main__":
    main()
