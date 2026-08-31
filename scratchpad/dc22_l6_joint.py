"""dc22 level 6 — joint BFS over (bar phase, 'c' parity, mover cell).

'f' shifts the bar staircase (period 6); 'c' swaps every group-c form (period 2) AND
teleports the mover when it is standing on a tewfut tile.  Support is re-checked after
every click, so a click can drop the mover.  This enumerates the joint graph with the
REAL engine's predicates and reports which landmarks open up.
"""
import sys, collections, json
sys.path.insert(0, "scratchpad")
from dc22_l6_macro import load
from dc22_l6_phase import maps

DIRS = {1: (0, -2), 2: (0, 2), 3: (-2, 0), 4: (2, 0)}
F = (53, 5)
C = (48, 23)


def main():
    m = load()
    from arcengine.base_game import ActionInput
    from arcengine.sprites import InteractionMode as IM
    S = {}
    B = {}
    TP = {}
    LM = {}
    for q in range(2):
        g = m.Dc22()
        g.set_level(5)
        if q:
            g.perform_action(ActionInput(id=6, data=dict(x=C[0], y=C[1])))
        for p in range(6):
            s, b = maps(g)
            S[(p, q)] = s
            B[(p, q)] = b
            g.perform_action(ActionInput(id=6, data=dict(x=F[0], y=F[1])))
        # landmarks + teleport map for this parity
        g2 = m.Dc22(); g2.set_level(5)
        if q:
            g2.perform_action(ActionInput(id=6, data=dict(x=C[0], y=C[1])))
        for s2 in g2.current_level.get_sprites():
            if s2.interaction == IM.REMOVED:
                continue
            if set(s2.tags) & {"tewfut", "piyqze", "njvd-rolo", "goknoi"}:
                LM.setdefault((s2.x, s2.y), set()).add(s2.name)
        # teleport destinations: stand on each tewfut, click c, see where we land
        for s2 in list(g2.current_level.get_sprites_by_tag("tewfut")):
            if s2.interaction == IM.REMOVED:
                continue
            gg = m.Dc22(); gg.set_level(5)
            if q:
                gg.perform_action(ActionInput(id=6, data=dict(x=C[0], y=C[1])))
            gg.qnnpcoyzd.set_position(s2.x, s2.y)
            gg.perform_action(ActionInput(id=6, data=dict(x=C[0], y=C[1])))
            TP[(q, s2.x, s2.y)] = (gg.qnnpcoyzd.x, gg.qnnpcoyzd.y)
    print("teleports:", TP, flush=True)

    start = (0, 0, 28, 52)
    prev = {start: None}
    dq = collections.deque([start])
    while dq:
        cur = dq.popleft()
        p, q, x, y = cur
        succ = []
        for aid, (dx, dy) in DIRS.items():
            n = (p, q, x + dx, y + dy)
            if (n[2], n[3]) in S[(p, q)] and (n[2], n[3]) not in B[(p, q)]:
                succ.append((n, f"A{aid}"))
        np_ = ((p + 1) % 6, q)
        if (x, y) in S[np_] and (x, y) not in B[np_]:
            succ.append((np_[0], q, x, y), )
            succ[-1] = ((np_[0], q, x, y), "click_f")
        nq = q ^ 1
        tx, ty = TP.get((q, x, y), (x, y))
        if (tx, ty) in S[(p, nq)] and (tx, ty) not in B[(p, nq)]:
            succ.append(((p, nq, tx, ty), "click_c"))
        for n, lab in succ:
            if n in prev:
                continue
            prev[n] = (cur, lab)
            dq.append(n)
    cells = {(x, y) for (_, _, x, y) in prev}
    print(json.dumps({"joint_states": len(prev), "distinct_cells": len(cells)}), flush=True)
    import os
    tgt = os.environ.get("DC22_TARGET")
    if tgt:
        tx, ty = [int(v) for v in tgt.split(",")]
        for pp in range(6):
            for qq in range(2):
                node = (pp, qq, tx, ty)
                if node in prev:
                    path = []
                    n = node
                    while prev[n] is not None:
                        pr, lab = prev[n]
                        path.append(lab)
                        n = pr
                    print(json.dumps({"target": [tx, ty], "phase": pp, "parity": qq,
                                      "len": len(path), "path": path[::-1]}), flush=True)
                    break
            else:
                continue
            break
    for (lx, ly), nms in sorted(LM.items()):
        hit = [(p, q) for p in range(6) for q in range(2) if (p, q, lx, ly) in prev]
        print(f"  landmark {sorted(nms)} ({lx},{ly}) reachable at {hit[:6]}{'...' if len(hit)>6 else ''}", flush=True)


if __name__ == "__main__":
    main()
