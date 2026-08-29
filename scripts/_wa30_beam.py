"""Does a 70-action clear of wa30 level 9 EXIST? Beam search in the real engine.

The level declares a StepCounter of 70 and the branch that spends it is `elif not
current_steps: self.lose()` — MEASURED firing (the raw engine reaches GameState.GAME_OVER on
action 70 under a constant press), so an attempt is 70 actions and no more.  Nine pieces have
to be standing on a bay cell, held by nobody, before that.

This searches the real `Wa30` object rather than a model of it: each node is the engine itself,
copied with the untouched levels shared into the memo (3.5ms a copy against 14.5ms naive), and
advanced by `_set_action` + `step()` — the same two calls `perform_action` makes, minus the
render.  So a witness it returns is a witness the engine accepts.

One (width, heuristic, seed) per process.  Reports the best coverage any beam reached, the
depth it reached it at, and the action string when a clear is found.
"""
from __future__ import annotations

import copy
import json
import sys

C = 4
ACTS = (1, 2, 3, 4, 5)


def main() -> None:
    import numpy as np
    from arc_agi import Arcade, OperationMode
    from arcengine import ActionInput
    from arcengine import GameAction as EGA
    from arcengine.enums import GameState

    job = int(sys.argv[1])
    depth_cap = int(sys.argv[2]) if len(sys.argv) > 2 else 70
    widths = (150, 400, 1000)
    width = widths[(job - 1) % 3]
    heur = ((job - 1) // 3) % 4
    seed = (job - 1) // 12
    rng = np.random.default_rng(seed + 1)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("wa30"))
    env = arcade.make(info.game_id)
    env.reset()
    root = env._game
    root.set_level(8)
    if len(root.current_level.get_sprites_by_tag("geezpjgiyd")) != 9:
        print(json.dumps({"job": job, "error": "not level 9"}))
        return

    def clone(gm):
        memo = {id(gm._clean_levels): gm._clean_levels}
        for i, lv in enumerate(gm._levels):
            if i != gm.level_index:
                memo[id(lv)] = lv
        return copy.deepcopy(gm, memo)

    def advance(gm, a):
        gm._set_action(ActionInput(id=EGA.from_id(a)))
        gm.step()

    def parts(gm):
        lv = gm.current_level
        ps = lv.get_sprites_by_tag("geezpjgiyd")
        bay, den = gm.wyzquhjerd, gm.lqctaojiby
        held = gm.zmqreragji
        cov = free_cells = 0
        onbay_held = thief_held = 0
        loose = []
        for s in ps:
            on = (s.x, s.y) in bay
            if s in held:
                if on:
                    onbay_held += 1
                if "ysysltqlke" in held[s].tags:
                    thief_held += 1
                loose.append(s)
            elif on:
                cov += 1
            else:
                loose.append(s)
        del free_cells
        return cov, onbay_held, thief_held, loose, bay, den

    def score(gm):
        cov, onbay_held, thief_held, loose, bay, den = parts(gm)
        occupied = {(s.x, s.y) for s in gm.current_level.get_sprites_by_tag("geezpjgiyd")}
        openbay = [b for b in bay if b not in occupied]
        dist = 0
        for s in loose:
            if openbay:
                dist += min(abs(s.x - b[0]) + abs(s.y - b[1]) for b in openbay) // C
            if (s.x, s.y) in den:
                dist += 10
        v = 1000 * cov - dist
        if heur >= 1:
            v += 100 * onbay_held - 200 * thief_held
        if heur == 2:
            p = gm.current_level.get_sprites_by_tag("wbmdvjhthc")[0]
            if loose:
                v -= 5 * min(abs(s.x - p.x) + abs(s.y - p.y) for s in loose) // C
        if heur == 3:
            # potential: the drag work still owed, each loose piece assigned a DISTINCT open bay
            # nearest-first, plus the walk owed by whichever agent is closest to it.
            agents = [(a.x, a.y) for a in
                      gm.current_level.get_sprites_by_tag("wbmdvjhthc")
                      + gm.current_level.get_sprites_by_tag("kdweefinfi")]
            pool = list(openbay)
            work = 0
            for s in sorted(loose, key=lambda q: -(q.x + q.y)):
                if not pool:
                    break
                b = min(pool, key=lambda q: abs(s.x - q[0]) + abs(s.y - q[1]))
                pool.remove(b)
                work += (abs(s.x - b[0]) + abs(s.y - b[1])) // C
                if agents:
                    work += min(abs(s.x - a[0]) + abs(s.y - a[1]) for a in agents) // (C * 3)
            v = 1000 * cov - 3 * work + 100 * onbay_held - 200 * thief_held
        return v, cov

    def key(gm):
        lv = gm.current_level
        bits = [(s.x, s.y) for s in lv.get_sprites_by_tag("geezpjgiyd")]
        bits += [(s.x, s.y) for s in lv.get_sprites_by_tag("kdweefinfi")]
        bits += [(s.x, s.y) for s in lv.get_sprites_by_tag("ysysltqlke")]
        p = lv.get_sprites_by_tag("wbmdvjhthc")[0]
        bits.append((p.x, p.y, p.rotation, len(gm.nsevyuople)))
        return (tuple(bits), gm.kuncbnslnm.current_steps)

    beam = [(root, [])]
    best_cov = parts(root)[0]
    best_at = 0
    for d in range(1, depth_cap + 1):
        cand = []
        seen = set()
        for gm, hist in beam:
            for a in ACTS:
                nxt = clone(gm)
                advance(nxt, a)
                st = nxt._state
                if st == GameState.WIN:
                    print(json.dumps({"job": job, "width": width, "heur": heur, "seed": seed,
                                      "CLEARED": True, "actions": d,
                                      "witness": hist + [a]}))
                    return
                if st == GameState.GAME_OVER:
                    continue
                k = key(nxt)
                if k in seen:
                    continue
                seen.add(k)
                v, cov = score(nxt)
                if cov > best_cov:
                    best_cov = cov
                    best_at = d
                    print(f"[{job}] depth {d}: covered {cov}/9 steps="
                          f"{nxt.kuncbnslnm.current_steps}", file=sys.stderr, flush=True)
                cand.append((v + float(rng.random()), nxt, hist + [a]))
        if not cand:
            break
        cand.sort(key=lambda t: -t[0])
        beam = [(g, h) for _, g, h in cand[:width]]
        if d % 10 == 0:
            print(f"[{job}] depth {d}: beam {len(beam)} best_cov {best_cov}",
                  file=sys.stderr, flush=True)

    print(json.dumps({"job": job, "width": width, "heur": heur, "seed": seed,
                      "CLEARED": False, "best_covered": best_cov, "best_at_depth": best_at,
                      "depth_cap": depth_cap}))


if __name__ == "__main__":
    main()
