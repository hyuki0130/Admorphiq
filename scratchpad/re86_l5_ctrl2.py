"""re86 L5 CLOSING controller (task #84): flood-robust sequential recolour + cover.

Design from the selection/flood probe (re86_l5_sel.py):
  - Selection cycles 12->11->14 in a fixed order; the colour-0 MARKER reliably
    identifies the selected piece EXCEPT during a single 1-frame recolour flood
    (marker returns next frame). So selection = cycle ACTION5 until the marker is
    on the piece I want.
  - The permanent stall was a piece RE-RECOLOURING by crossing multiple stations
    (12->8->10). Fix: the instant a piece reaches its target colour, STOP routing
    toward stations and drive it to its cover cluster (which sits away from every
    station), station-avoiding the whole way so it never re-recolours.

Sequential: work ONE piece at a time to 'done' (recolour -> cover), never
disturbing a placed piece. The win-check is a snapshot, so cover order is free;
the win fires when the last piece lands. Reuses parsing/assignment/routing from
re86_l5_ctrl.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _station_boxes
from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.kernels import max_coverage_offset, grid_shortest_path, find_regions
from re86_l5_ctrl import (
    parse_movables, scan_gate_cells, cluster, assign_pieces, marker_of, reach_l5,
)

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL = 3
BORDER, STA_BORDER, MARK = 4, 2, 0


def parse2(grid, gate_cells, station_boxes):
    """FIX (b): parse movables SUBTRACTING both gate cells AND station-box pixels.
    A recoloured colour-9 body abutting the colour-9 station-9 swatch merges under
    plain connected components (same colour); subtracting the station BOX region
    (by box, not colour) keeps the piece's true shape/centroid so tracking survives
    the merge. Mirrors the L4 gate-cell-subtraction pattern extended to stations."""
    bg = most_common_color(grid)
    exclude = {bg, BORDER, STA_BORDER, MARK}
    gc = set(gate_cells)
    def in_box(r, c):
        return any(r0 - 1 <= r <= r1 + 1 and c0 - 1 <= c <= c1 + 1 for r0, c0, r1, c1 in station_boxes)
    out = []
    for reg in find_regions(grid, background=bg, gap=1):
        if reg["color"] in exclude:
            continue
        cells = frozenset((r, c) for (r, c) in reg["cells"] if (r, c) not in gc and not in_box(r, c))
        if not (20 <= len(cells) <= 120):
            continue
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        if max(rs) - min(rs) < 3 or max(cs) - min(cs) < 3:
            continue
        cen = (sum(rs) // len(cells), sum(cs) // len(cells))
        out.append({"color": reg["color"], "cells": cells, "cen": cen})
    return out


def route_to(pos, goal_px, half, avoid_boxes, walls, dirmap, move_ids):
    """One action stepping the CENTRE from `pos` toward pixel `goal_px` via
    grid_shortest_path over a 3px-cell grid with `avoid_boxes` inflated by `half`
    and learned `walls` impassable. Returns action id or None."""
    n = 64 // CELL + 1
    passable = [[True] * n for _ in range(n)]
    for (r0, c0, r1, c1) in avoid_boxes:
        for i in range(max(0, (r0 - half) // CELL), min(n, (r1 + half) // CELL + 1)):
            for j in range(max(0, (c0 - half) // CELL), min(n, (c1 + half) // CELL + 1)):
                passable[i][j] = False
    for (wi, wj) in walls:
        if 0 <= wi < n and 0 <= wj < n:
            passable[wi][wj] = False
    start = (pos[0] // CELL, pos[1] // CELL)
    goal = (min(n - 1, max(0, goal_px[0] // CELL)), min(n - 1, max(0, goal_px[1] // CELL)))
    passable[start[0]][start[1]] = True
    passable[goal[0]][goal[1]] = True
    path = grid_shortest_path(passable, start, goal)
    if not path or len(path) < 2:
        return None
    want = (path[1][0] - start[0], path[1][1] - start[1])
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
        print("no L5"); return
    dirmap = dict(ad._dir_global)
    for _ in range(2):
        obs = env.step(A[5]); steps += 1
    grid = canonical_layer(obs)
    stations, station_boxes = _station_boxes(grid)
    sbox = {col: next(b for b in station_boxes if b[0] <= stations[col][0] <= b[2] and b[1] <= stations[col][1] <= b[3])
            for col in stations}
    print(f"stations={stations}")

    gate_acc = {8: set(), 9: set()}

    def refresh_gates(grid):
        gg = scan_gate_cells(grid, station_boxes, set())
        for tc in (8, 9):
            gate_acc[tc] |= gg[tc]

    from itertools import permutations
    all_gate = lambda: [c for tc in (8, 9) for c in gate_acc[tc]]
    # Two of the four colour-8 gate cells start OCCLUDED by the rightmost movable
    # body (colour-12 at col ~52). Reveal them with a SAFE left-nudge of the
    # rightmost piece (moving LEFT is away from the right-edge stations 10/8 and
    # far from the mid/bottom-left stations, so no accidental recolour), then do
    # the FULL 3-way feasibility assignment (all 3 clusters must be fully covered
    # — the colour-8 piece covers 4/4 only for the right movable; colour-11 covers
    # just 3/4, so elimination-only assignment silently loses the win).
    refresh_gates(canonical_layer(obs))
    for _ in range(14):
        if len(gate_acc[8]) >= 4 and len(gate_acc[9]) >= 6:
            break
        grid = canonical_layer(obs)
        movs = parse_movables(grid, all_gate(), station_boxes)
        if not movs:
            obs = env.step(A[5]); steps += 1; continue
        rightmost = max(range(len(movs)), key=lambda i: movs[i]["cen"][1])
        mk = marker_of(grid)
        selm = None
        if mk is not None:
            for i, m in enumerate(movs):
                rs = [r for r, _ in m["cells"]]; cs = [c for _, c in m["cells"]]
                if min(rs) - 2 <= mk[0] <= max(rs) + 2 and min(cs) - 2 <= mk[1] <= max(cs) + 2:
                    selm = i; break
        if selm != rightmost:
            obs = env.step(A[5]); steps += 1
        else:
            left = next((a for a, s in dirmap.items() if s == (0, -1)), 3)
            obs = env.step(A[left]); steps += 1
        refresh_gates(canonical_layer(obs))
    grid = canonical_layer(obs)
    movs0 = parse_movables(grid, all_gate(), station_boxes)
    if len(movs0) != 3:
        print(f"parse gave {len(movs0)} movables, need 3"); return
    clusters9 = [cl for cl in cluster(gate_acc[9])]
    cells8 = list(gate_acc[8])
    if len(clusters9) != 2:
        print(f"expected 2 colour-9 clusters, got {len(clusters9)}"); return
    print(f"reveal done: 9-clusters={[len(c) for c in clusters9]} 8-cells={len(cells8)}")

    def cov(mi, cells):
        best = max_coverage_offset(list(movs0[mi]["cells"]), cells)
        return len(best[1]) if best else 0
    # full 3-way: choose eight_mi and the 9-perm maximizing (all-full, total cover)
    best_rank, chosen = (-1, -1), None
    for eight_mi in range(3):
        rest = [i for i in range(3) if i != eight_mi]
        for m0, m1 in permutations(rest, 2):
            c8 = cov(eight_mi, cells8)
            c0, c1 = cov(m0, clusters9[0]), cov(m1, clusters9[1])
            full = (c8 == len(cells8)) and (c0 == len(clusters9[0])) and (c1 == len(clusters9[1]))
            rank = (1 if full else 0, c8 + c0 + c1)
            if rank > best_rank:
                best_rank, chosen = rank, (eight_mi, {m0: clusters9[0], m1: clusters9[1]})
    eight_mi, a9 = chosen
    pieces = []
    for mi, m in enumerate(movs0):
        if mi in a9:
            tcol, ccells = 9, a9[mi]
        else:
            tcol, ccells = 8, cells8
        rs = [r for r, _ in m["cells"]]; cs = [c for _, c in m["cells"]]
        pieces.append({"orig": m["color"], "color": m["color"], "target": tcol,
                       "cluster": list(ccells), "cen": m["cen"], "cells": m["cells"],
                       "half": max(max(rs) - min(rs), max(cs) - min(cs)) // 2 + 1,
                       "walls": set(), "shape_rel": None, "phase": "recolour",
                       "is8": mi == eight_mi})
    print("ASSIGN:", [(p["orig"], p["target"], len(p["cluster"])) for p in pieces], "full=", best_rank[0] == 1)
    # Processing order: the 8-piece first (its cover zone is the right side, clear
    # of the shared station-9), then the two colour-9 pieces TOP cluster BEFORE
    # BOTTOM — both recolour at the single bottom-left station-9, so send the
    # top-bound one UP and away first, leaving the bottom-left area free for the
    # bottom-bound one (measured: processing bottom-first collides the two colour-9
    # bodies at the shared station-9 and breaks same-colour tracking).
    def clu_row(p):
        return sum(r for r, _ in p["cluster"]) / max(1, len(p["cluster"]))
    order = sorted(range(3), key=lambda i: (pieces[i]["target"] != 8, clu_row(pieces[i])))
    print("ORDER:", [(pieces[i]["orig"], pieces[i]["target"], round(clu_row(pieces[i]))) for i in order])

    def track(grid):
        movs = parse2(grid, all_gate(), station_boxes)
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
            if best is not None and bd <= 22:
                used.add(best)
                p["cen"] = movs[best]["cen"]
                p["cells"] = movs[best]["cells"]
                if movs[best]["color"] in known:
                    p["color"] = movs[best]["color"]

    MAXS = 6000
    win = False
    last_move = None
    loop_i = 0
    any_recoloured = lambda: any(p["color"] in (8, 9) and p["color"] != p["orig"] for p in pieces)
    while steps < MAXS:
        grid = canonical_layer(obs)
        track(grid)
        # keep revealing the occluded colour-8 gate cells until the first recolour
        # (scan is clean while all bodies still hold their original colours).
        if not any_recoloured():
            refresh_gates(grid)
            for p in pieces:
                if p["is8"]:
                    p["cluster"] = list(gate_acc[8])
        marker = marker_of(grid)
        # wall-learning (marker-to-marker)
        if last_move is not None and marker is not None:
            pi, prev_pos, want = last_move
            adv = (marker[0] - prev_pos[0]) * want[0] + (marker[1] - prev_pos[1]) * want[1]
            if adv < 2:
                pieces[pi]["walls"].add((prev_pos[0] // CELL + want[0], prev_pos[1] // CELL + want[1]))
        last_move = None

        lv = int(getattr(obs, "levels_completed", 0) or 0)
        if lv >= 5 or str(obs.state).endswith("WIN"):
            win = True; break

        move_ids = [1, 2, 3, 4]
        active = next((i for i in order if pieces[i]["phase"] != "done"), None)
        if active is None:
            break
        p = pieces[active]

        # which piece is selected? NEAREST CENTROID to the marker (not first-bbox-
        # containing: a placed piece's large cover bbox can overlap another piece's
        # position and steal selection — measured, it trapped colour-12 forever).
        sel = None
        if marker is not None:
            sel = min(range(len(pieces)),
                      key=lambda i: abs(pieces[i]["cen"][0] - marker[0]) + abs(pieces[i]["cen"][1] - marker[1]))
        if loop_i < 40 or steps % 200 == 0:
            print(f"  @{steps} i{loop_i} active={active}({p['orig']}->{p['target']},{p['phase']}) "
                  f"sel={sel} marker={marker} colors={[q['color'] for q in pieces]} "
                  f"walls={[len(q['walls']) for q in pieces]} cens={[q['cen'] for q in pieces]}")
        loop_i += 1

        if marker is None:
            # 1-frame flood: wait WITHOUT cycling (a move no-ops on the frozen piece)
            obs = env.step(A[1]); steps += 1; continue
        if sel != active:
            obs = env.step(A[5]); steps += 1; continue  # cycle to the active piece

        if p["color"] != p["target"]:
            others = [b for c, b in sbox.items() if c != p["target"]]
            tb = sbox[p["target"]]
            # FIX (a): EDGE-ONLY approach. The recolour fires on FIRST body overlap
            # (L4 finding), so once the body bbox touches the target station box,
            # STOP pushing in (that is what wedges into the corner and stalls the
            # flood) — retreat toward the cover cluster instead; the 1-frame flip
            # completes and the piece is already leaving.
            body = (marker[0] - p["half"], marker[1] - p["half"], marker[0] + p["half"], marker[1] + p["half"])
            overlaps = not (body[2] < tb[0] or body[0] > tb[2] or body[3] < tb[1] or body[1] > tb[3])
            if overlaps:
                ccen = (sum(r for r, _ in p["cluster"]) // len(p["cluster"]),
                        sum(c for _, c in p["cluster"]) // len(p["cluster"]))
                act = route_to(marker, ccen, p["half"], others, p["walls"], dirmap, move_ids)
            else:
                act = route_to(marker, stations[p["target"]], p["half"], others, p["walls"], dirmap, move_ids)
            if act is None:
                obs = env.step(A[5]); steps += 1; continue
            last_move = (active, marker, dirmap[act])
            obs = env.step(A[act]); steps += 1
            continue

        # COVER: piece is recoloured; drive its shape to cover its cluster, avoiding
        # every station of a DIFFERENT colour (so it never re-recolours).
        if p["shape_rel"] is None:
            p["shape_rel"] = frozenset((r - marker[0], c - marker[1]) for r, c in p["cells"])
        cur = {(marker[0] + dr, marker[1] + dc) for dr, dc in p["shape_rel"]}
        need = p["cluster"]
        if sum(1 for gt in need if gt in cur) == len(need):
            p["phase"] = "done"
            print(f"  PLACED p{active}({p['orig']}->{p['color']}) covering {len(need)} cells @marker={marker}")
            continue
        best = max_coverage_offset(list(cur), need)
        if best is None:
            obs = env.step(A[5]); steps += 1; continue
        (odr, odc), _ = best
        goal_px = (marker[0] + odr, marker[1] + odc)
        others = [b for c, b in sbox.items() if c != p["color"]]
        act = route_to(marker, goal_px, p["half"], others, p["walls"], dirmap, move_ids)
        if act is None:
            obs = env.step(A[5]); steps += 1; continue
        last_move = (active, marker, dirmap[act])
        obs = env.step(A[act]); steps += 1

    print(f"\nRESULT win={win} steps={steps} levels={int(getattr(obs,'levels_completed',0) or 0)}")
    print("pieces:", [(p["orig"], p["color"], p["target"], p["phase"], p["cen"]) for p in pieces])


if __name__ == "__main__":
    main()
