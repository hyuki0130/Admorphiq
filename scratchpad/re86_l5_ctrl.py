"""re86 L5 live controller prototype (task #84): 3-piece recolour-route-cover.

Validates the full L5 chain live BEFORE porting to the adapter (the L4 build did
the same). Plan:
  1. Reach L5 via the adapter; borrow its measured move map (_dir_global).
  2. Frame-parse 3 movables + 5 stations + gate cells (colour-9/8, accumulated
     across frames since 2 eight-cells start occluded by a movable body).
  3. Assign 1:1 (offline max_coverage_offset): each movable -> (target colour,
     gate cluster) it FULLY covers.  colour-11->9/top, colour-12->9/bottom,
     colour-14->8/right (feasibility probe proved this is the unique 1:1 plan).
  4. RECOLOUR: route each movable into its target station via grid_shortest_path
     over a passability grid with NON-target station boxes inflated by the
     movable half-extent (station-14 mid-left breaks L4's edge-row avoidance).
  5. COVER: marker-anchored shape, drive each to cover its cluster; win when all
     three stamp simultaneously.

Instrumented: prints phase + per-piece state so the first real divergence is
visible for banking.
"""
from __future__ import annotations
import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _station_boxes
from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.kernels import find_regions, max_coverage_offset, grid_shortest_path

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL = 3
BORDER, STA_BORDER, MARK = 4, 2, 0


def reach_l5(env, ad):
    obs = env.observation_space
    s = 0
    while s < 6000 and int(getattr(obs, "levels_completed", 0) or 0) < 4 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs, s


def marker_of(grid):
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v == MARK:
                return (r, c)
    return None


def parse_movables(grid, gate_cells, station_boxes):
    bg = most_common_color(grid)
    exclude = {bg, BORDER, STA_BORDER, MARK}
    gc = set(gate_cells)
    out = []
    for reg in find_regions(grid, background=bg, gap=1):
        if reg["color"] in exclude:
            continue
        cells = frozenset(reg["cells"]) - gc
        if not (20 <= len(cells) <= 120):
            continue
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        if max(rs) - min(rs) < 3 or max(cs) - min(cs) < 3:
            continue
        cen = (sum(rs) // len(cells), sum(cs) // len(cells))
        if any(r0 - 1 <= cen[0] <= r1 + 1 and c0 - 1 <= cen[1] <= c1 + 1 for r0, c0, r1, c1 in station_boxes):
            continue
        out.append({"color": reg["color"], "cells": cells, "cen": cen})
    return out


def scan_gate_cells(grid, station_boxes, mov_colors):
    """Colour-9/8 pixels that are NOT inside a station box (the gate canvas cells).
    Movable bodies are colours 12/11/14 so they don't collide with 9/8 scans until
    recoloured; once recoloured a movable's own cells read as 9/8 — but those are
    dense blobs, whereas gate cells are ISOLATED. Keep only isolated (small
    connected-component) 9/8 marks."""
    found = {8: set(), 9: set()}
    for tc in (8, 9):
        for reg in find_regions(grid, background=None, gap=0):
            if reg["color"] != tc:
                continue
            cells = reg["cells"]
            if len(cells) > 4:
                continue  # a recoloured movable body, not a gate mark
            r, c = next(iter(cells))
            if any(r0 <= r <= r1 and c0 <= c <= c1 for r0, c0, r1, c1 in station_boxes):
                continue
            for cell in cells:
                found[tc].add(cell)
    return found


def cluster(cells, radius=20):
    cells = list(cells); clusters = []
    for cell in cells:
        for cl in clusters:
            if any(abs(cell[0] - x) + abs(cell[1] - y) <= radius for x, y in cl):
                cl.append(cell); break
        else:
            clusters.append([cell])
    return clusters


def assign_pieces(movs, clusters):
    """1:1 movable->cluster maximizing total coverage (prefer fully-covering).
    Returns {mov_index: (target_color, cluster_cells)}. Always returns a mapping
    when #movs == #clusters (best-effort — frame-parsed shapes may not hit the
    exact full count every frame; the cover phase converges from the best perm)."""
    nC = len(clusters)
    if len(movs) != nC:
        return None
    cov = {}
    for mi, m in enumerate(movs):
        for ci, cl in enumerate(clusters):
            best = max_coverage_offset(list(m["cells"]), cl["cells"])
            cov[(mi, ci)] = len(best[1]) if best else 0
    best_perm, best_rank = None, (-1, -1)
    for perm in product(range(len(movs)), repeat=nC):
        if len(set(perm)) != nC:
            continue
        score = sum(cov[(perm[ci], ci)] for ci in range(nC))
        full = all(cov[(perm[ci], ci)] == len(clusters[ci]["cells"]) for ci in range(nC))
        rank = (1 if full else 0, score)
        if rank > best_rank:
            best_rank, best_perm = rank, perm
    if best_perm is None:
        return None
    return {best_perm[ci]: (clusters[ci]["color"], clusters[ci]["cells"]) for ci in range(nC)}


def route_move(cen, half, target_box, other_boxes, dirmap, move_ids, walls=frozenset()):
    """One action toward target_box centre via grid_shortest_path over a 3px-cell
    passability grid with other_boxes inflated by `half` AND learned `walls`
    (interior-wall centre-cells discovered from failed moves). Returns action id
    or None."""
    n = 64 // CELL + 1
    passable = [[True] * n for _ in range(n)]
    for (r0, c0, r1, c1) in other_boxes:
        for i in range(max(0, (r0 - half) // CELL), min(n, (r1 + half) // CELL + 1)):
            for j in range(max(0, (c0 - half) // CELL), min(n, (c1 + half) // CELL + 1)):
                passable[i][j] = False
    for (wi, wj) in walls:
        if 0 <= wi < n and 0 <= wj < n:
            passable[wi][wj] = False
    start = (cen[0] // CELL, cen[1] // CELL)
    tr = (target_box[0] + target_box[2]) // 2
    tc = (target_box[1] + target_box[3]) // 2
    goal = (tr // CELL, tc // CELL)
    passable[start[0]][start[1]] = True
    passable[goal[0]][goal[1]] = True
    path = grid_shortest_path(passable, start, goal)
    if not path or len(path) < 2:
        return None
    dr = path[1][0] - start[0]; dc = path[1][1] - start[1]
    want = (dr, dc)
    for a, sign in dirmap.items():
        if a in move_ids and sign == want:
            return a
    return None


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=6000)
    obs, steps = reach_l5(env, ad)
    if int(getattr(obs, "levels_completed", 0) or 0) != 4:
        print("did NOT reach L5"); return
    dirmap = dict(ad._dir_global)
    print(f"reached L5 @ {steps}; dirmap={dirmap}")
    # settle
    for _ in range(2):
        obs = env.step(A[5]); steps += 1
    grid = canonical_layer(obs)
    stations, station_boxes = _station_boxes(grid)
    print(f"stations={stations}")

    gate_acc = {8: set(), 9: set()}
    mov_colors = set()

    def refresh_gates(grid):
        g = scan_gate_cells(grid, station_boxes, mov_colors)
        for tc in (8, 9):
            gate_acc[tc] |= g[tc]

    refresh_gates(grid)
    all_gate = lambda: [c for tc in (8, 9) for c in gate_acc[tc]]

    # initial movable parse + assignment (recompute once all gate cells known)
    movs0 = parse_movables(grid, all_gate(), station_boxes)
    mov_colors = {m["color"] for m in movs0}
    print(f"movables@entry: {[(m['color'], m['cen'], len(m['cells'])) for m in movs0]}")
    print(f"gates@entry: 9={sorted(gate_acc[9])} 8={sorted(gate_acc[8])}")

    # track pieces by identity (index into a stable list keyed on entry centroid)
    pieces = [{"orig": m["color"], "cen": m["cen"], "cells": m["cells"],
               "color": m["color"], "target": None, "cluster": None,
               "shape_rel": None, "placed": False, "walls": set(),
               "half": (max(max(r for r,_ in m['cells'])-min(r for r,_ in m['cells']), max(c for _,c in m['cells'])-min(c for _,c in m['cells'])))//2 + 1}
              for m in movs0]
    assign = None
    last_move = None  # (piece_index, pixel_centroid, want_dir) for wall-learning

    def try_assign():
        nonlocal assign
        # LOCK only when all gate cells look complete (6 nine + 4 eight) so the
        # full-coverage permutation is found — an early 2-cell 8-cluster picks the
        # WRONG perm (measured: c14->9/c11->8 instead of the feasible c14->8/c11->9).
        if len(gate_acc[9]) < 6 or len(gate_acc[8]) < 4:
            return
        clusters = []
        for tc in (9, 8):
            for cl in cluster(gate_acc[tc]):
                clusters.append({"color": tc, "cells": cl})
        if len(clusters) != len(pieces):
            return
        a = assign_pieces([{"cells": p["cells"]} for p in pieces], clusters)
        if a is None:
            return
        for mi, (tcol, ccells) in a.items():
            pieces[mi]["target"] = tcol
            pieces[mi]["cluster"] = ccells
        assign = a
        print(f"ASSIGNED: " + ", ".join(f"p{mi}(c{pieces[mi]['orig']})->{tcol}/{len(ccells)}cells" for mi, (tcol, ccells) in a.items()))

    try_assign()

    def track(grid):
        refresh_gates(grid)
        movs = parse_movables(grid, all_gate(), station_boxes)
        known = {8, 9} | {p["orig"] for p in pieces}
        used = set()
        for p in pieces:
            best, bd = None, None
            for mi, m in enumerate(movs):
                if mi in used:
                    continue
                d = abs(m["cen"][0] - p["cen"][0]) + abs(m["cen"][1] - p["cen"][1])
                if bd is None or d < bd:
                    bd, best = d, mi
            if best is not None and bd <= 20:
                used.add(best)
                p["cen"] = movs[best]["cen"]
                p["cells"] = movs[best]["cells"]
                if movs[best]["color"] in known:
                    p["color"] = movs[best]["color"]

    # ── main control loop ──
    MAXS = 4000
    win = False
    loop_i = 0
    while steps < MAXS:
        grid = canonical_layer(obs)
        track(grid)
        marker = marker_of(grid)
        # WALL-LEARNING (ported from L4 _l4_blocked): the driven move recorded the
        # marker position it started from; if the marker did not advance toward
        # `want`, an interior wall sits at the cell the centre would have entered —
        # fold it into that piece's passability. Marker-to-marker (both exact 3px).
        if last_move is not None:
            pi, prev_pos, want = last_move
            if marker is not None:
                adv = (marker[0] - prev_pos[0]) * want[0] + (marker[1] - prev_pos[1]) * want[1]
                if adv < 2:  # did not advance a full 3px cell in the intended dir
                    wcell = (prev_pos[0] // CELL + want[0], prev_pos[1] // CELL + want[1])
                    pieces[pi]["walls"].add(wcell)
            last_move = None

        if assign is None:
            try_assign()
        lv = int(getattr(obs, "levels_completed", 0) or 0)
        if lv >= 5 or str(obs.state).endswith("WIN"):
            win = True; break
        move_ids = [1, 2, 3, 4]
        # selected piece = the one whose bbox contains the marker
        sel = None
        if marker is not None:
            for i, p in enumerate(pieces):
                rs = [r for r, _ in p["cells"]]; cs = [c for _, c in p["cells"]]
                if rs and min(rs) - 1 <= marker[0] <= max(rs) + 1 and min(cs) - 1 <= marker[1] <= max(cs) + 1:
                    sel = i; break
        _trace = (loop_i < 50) or (steps % 200 == 0)
        if _trace:
            print(f"  @{steps} i{loop_i} assign={'set' if assign else 'None'} marker={marker} sel={sel} "
                  f"colors={[p['color'] for p in pieces]} targets={[p['target'] for p in pieces]} "
                  f"walls={[len(p['walls']) for p in pieces]} cens={[p['cen'] for p in pieces]}")
        loop_i += 1
        if sel is None:
            obs = env.step(A[5]); steps += 1; continue

        p = pieces[sel]
        if assign is None:
            # reveal occluded gate cells: nudge the selected piece, alternate cycle
            if steps % 3 == 0:
                obs = env.step(A[5])
            else:
                obs = env.step(A[1] if steps % 2 else A[2])
            steps += 1; continue

        recolour_done = all(pp["color"] == pp["target"] for pp in pieces)
        if not recolour_done:
            if p["color"] == p["target"]:
                obs = env.step(A[5]); steps += 1; continue  # done; select another
            # MARKER-ANCHOR the driven piece: the parse centroid jitters +-4px
            # (marker exclusion + gate subtraction shift the region) and confounds
            # wall-learning; the colour-0 marker is the sprite's exact centre and
            # moves in clean 3px steps (L4 lesson). Fall back to parse only if the
            # marker is momentarily hidden (recolour flood).
            pos = marker if marker is not None else p["cen"]
            tcol = p["target"]
            tbox = next((b for b in station_boxes if b[0] <= stations[tcol][0] <= b[2] and b[1] <= stations[tcol][1] <= b[3]), None)
            others = [b for b in station_boxes if b is not tbox]
            a = route_move(pos, p["half"], tbox, others, dirmap, move_ids, p["walls"])
            if steps % 100 == 0:
                print(f"    recolour p{sel}(c{p['color']}->{tcol}) pos={pos} half={p['half']} "
                      f"walls={len(p['walls'])} route_action={a}")
            if a is None:
                obs = env.step(A[5]); steps += 1; continue
            last_move = (sel, pos, dirmap[a])
            obs = env.step(A[a]); steps += 1
            continue

        # COVER phase
        need = list(p["cluster"])
        if marker is None:
            obs = env.step(A[5]); steps += 1; continue
        if p["shape_rel"] is None:
            p["shape_rel"] = frozenset((r - marker[0], c - marker[1]) for r, c in p["cells"])
        cur = {(marker[0] + dr, marker[1] + dc) for dr, dc in p["shape_rel"]}
        if sum(1 for gt in need if gt in cur) == len(need):
            p["placed"] = True
            obs = env.step(A[5]); steps += 1; continue
        best = max_coverage_offset(list(cur), need)
        if best is None:
            obs = env.step(A[5]); steps += 1; continue
        (odr, odc), _ = best
        if abs(odr) >= abs(odc) and odr != 0:
            want = (1 if odr > 0 else -1, 0)
        elif odc != 0:
            want = (0, 1 if odc > 0 else -1)
        else:
            want = (1 if odr > 0 else -1, 0)
        a = next((aa for aa, sign in dirmap.items() if aa in move_ids and sign == want), None)
        if a is None:
            obs = env.step(A[5]); steps += 1; continue
        obs = env.step(A[a]); steps += 1

    print(f"\nRESULT: win={win} steps={steps} levels={int(getattr(obs,'levels_completed',0) or 0)}")
    print("final pieces:", [(p["orig"], p["color"], p["target"], p["cen"], p["placed"]) for p in pieces])
    print("final gates: 9=", sorted(gate_acc[9]), "8=", sorted(gate_acc[8]))


if __name__ == "__main__":
    main()
