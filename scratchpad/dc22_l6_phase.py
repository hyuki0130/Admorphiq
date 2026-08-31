"""dc22 level 6 — BFS over (moxubw bar phase, mover cell).

The 'f' button shifts a 3-row staircase of bars by 2px per press and cycles with period 6.
Walking is only possible where a phase provides support; so the reachable set is a property
of (phase, position), not of position alone.  This enumerates that joint graph with the REAL
engine's own support/collision predicates and reports which landmarks become reachable.
"""
import sys, collections, json
sys.path.insert(0, "scratchpad")
from dc22_l6_macro import load

STEP = 2
DIRS = {1: (0, -STEP), 2: (0, STEP), 3: (-STEP, 0), 4: (STEP, 0)}


def maps(g):
    mv = g.qnnpcoyzd
    ox, oy = mv.x, mv.y
    sup = set()
    blk = set()
    for y in range(0, 64, 2):
        for x in range(0, 64, 2):
            if g.sxnzvaqltp(x, y, mv) is not None:
                sup.add((x, y))
            mv.set_position(x, y)
            for o in g.current_level.get_sprites():
                if g.collides_with(mv, o):
                    blk.add((x, y))
                    break
    mv.set_position(ox, oy)
    return sup, blk


def main():
    m = load()
    from arcengine.base_game import ActionInput
    from arcengine.sprites import InteractionMode as IM
    g = m.Dc22()
    g.set_level(5)
    S, B = [], []
    for p in range(6):
        s, b = maps(g)
        S.append(s)
        B.append(b)
        print(f"phase {p}: support {len(s)} blocked {len(b)}", flush=True)
        g.perform_action(ActionInput(id=6, data={"x": 53, "y": 5}))
    lm = {}
    for s in g.current_level.get_sprites():
        if s.interaction == IM.REMOVED:
            continue
        if set(s.tags) & {"tewfut", "piyqze", "njvd-rolo", "goknoi"}:
            lm[(s.x, s.y)] = s.name

    start = (0, 28, 52)
    prev = {start: None}
    q = collections.deque([start])
    while q:
        cur = q.popleft()
        p, x, y = cur
        cand = []
        for aid, (dx, dy) in DIRS.items():
            n = (p, x + dx, y + dy)
            if (n[1], n[2]) in S[p] and (n[1], n[2]) not in B[p]:
                cand.append((n, f"A{aid}"))
        np_ = (p + 1) % 6
        if (x, y) in S[np_] and (x, y) not in B[np_]:
            cand.append(((np_, x, y), "click_f"))
        for n, lab in cand:
            if n in prev:
                continue
            prev[n] = (cur, lab)
            q.append(n)
    byp = {}
    for (pp, x, y) in prev:
        byp.setdefault(pp, []).append((x, y))
    for pp in sorted(byp):
        cs = sorted(byp[pp])
        print(f"  phase {pp}: {len(cs)} cells  x{min(c[0] for c in cs)}-{max(c[0] for c in cs)} y{min(c[1] for c in cs)}-{max(c[1] for c in cs)}")
        rows = {}
        for (x, y) in cs:
            rows.setdefault(y, []).append(x)
        for y in sorted(rows):
            print(f"      y={y}: {sorted(rows[y])}")
    cells = {(x, y) for (p, x, y) in prev}
    print(json.dumps({"joint_states": len(prev), "distinct_cells": len(cells)}), flush=True)
    for (lx, ly), nm in sorted(lm.items()):
        hits = [p for p in range(6) if (p, lx, ly) in prev]
        print(f"  landmark {nm:26s} ({lx},{ly}) reachable in phases {hits}", flush=True)
    # print a path to the d-key if any
    for p in range(6):
        node = (p, 6, 18)
        if node in prev:
            path = []
            n = node
            while prev[n] is not None:
                pr, lab = prev[n]
                path.append(lab)
                n = pr
            print(json.dumps({"d_key_path_len": len(path), "path": path[::-1]}), flush=True)
            break


if __name__ == "__main__":
    main()
