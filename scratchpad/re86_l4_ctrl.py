"""re86 L4 multi-piece FSM controller — end-to-end live test.

Reach L4 via the adapter, then run the frame-only controller:
  - lock gates (colour-4 boxes by colour) + stations (colour-2 boxes by centre)
  - parse BOTH movables (interior regions, gate/station-excluded), track by
    centroid continuity, identify the selected one by the colour-0 marker
  - assignment: max_coverage_offset full-cover test picks movable->gate-colour
  - per-piece 2-phase FSM: RECOLOUR (column-align then vertical into the target
    station, which avoids every other edge-row station) -> COVER (drive to the
    max_coverage_offset over its gate colour, then freeze) -> cycle ACTION5.
Target: live L4 win.
"""
from __future__ import annotations
import sys
from collections import Counter, deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _target_boxes, _sign
from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.kernels import find_regions, max_coverage_offset

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
SEL, B_GATE, B_STATION, HUD = 0, 4, 2, 15
# source-fixed move map (ACTION1=up,2=down,3=left,4=right); measured live too.
DIRS = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}


def marker(grid):
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] == SEL:
                return (r, c)
    return None


def parse_stations(grid):
    H, W = len(grid), len(grid[0])
    seen = [[False] * W for _ in range(H)]
    out, boxes = {}, []
    for r in range(H):
        for c in range(W):
            if grid[r][c] == B_STATION and not seen[r][c]:
                comp = []
                q = deque([(r, c)]); seen[r][c] = True
                while q:
                    y, x = q.popleft(); comp.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < H and 0 <= nx < W and not seen[ny][nx] and grid[ny][nx] == B_STATION:
                                seen[ny][nx] = True; q.append((ny, nx))
                ys = [p[0] for p in comp]; xs = [p[1] for p in comp]
                bb = (min(ys), min(xs), max(ys), max(xs))
                cy, cx = (bb[0] + bb[2]) // 2, (bb[1] + bb[3]) // 2
                inside = Counter()
                for y in range(bb[0], bb[2] + 1):
                    for x in range(bb[1], bb[3] + 1):
                        v = grid[y][x]
                        if v not in (B_STATION, 5):
                            inside[v] += 1
                if inside:
                    out[inside.most_common(1)[0][0]] = (cy, cx)
                    boxes.append(bb)
    return out, boxes


def in_boxes(cell, boxes, pad=0):
    r, c = cell
    for r0, c0, r1, c1 in boxes:
        if r0 - pad <= r <= r1 + pad and c0 - pad <= c <= c1 + pad:
            return True
    return False


def parse_gates(grid):
    by = {}
    for (r, c) in _target_boxes(grid):
        by.setdefault(grid[r][c], []).append((r, c))
    return by


def parse_movables(grid, gate_cells, station_boxes):
    H, W = len(grid), len(grid[0])
    bg = most_common_color(grid)
    regions = find_regions(grid, background=bg, gap=1)
    gc = set(gate_cells)
    out = []
    for reg in regions:
        color = reg["color"]
        if color in (bg, B_GATE, B_STATION, HUD, 1, SEL):
            continue
        cells = frozenset(reg["cells"]) - gc
        if len(cells) < 20:
            continue
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        cen = (sum(rs) // len(cells), sum(cs) // len(cells))
        if in_boxes(cen, station_boxes, pad=1):  # a station swatch, not a movable
            continue
        out.append({"color": color, "cells": cells, "centroid": cen, "size": len(cells)})
    return out


def move_toward(dr, dc):
    cand = []
    if dr:
        cand.append((abs(dr), (_sign(dr), 0)))
    if dc:
        cand.append((abs(dc), (0, _sign(dc))))
    cand.sort(reverse=True)
    for _m, want in cand:
        for a, s in DIRS.items():
            if s == want:
                return a
    return None


def recolour_move(cen, station_cen):
    """Column-align first (horizontal, in the interior — no stations there),
    then vertical into the target station along its column (the only station on
    that column on the movable's side). Provably avoids all other edge-row
    stations."""
    sr, sc = station_cen
    cr, cc = cen
    if abs(cc - sc) > 3:  # box only needs to overlap the station's column range
        return move_toward(0, sc - cc)
    return move_toward(sr - cr, 0)


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=9000)
    steps = 0
    while steps < 9000 and obs.levels_completed < 3:
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    print("reached L4 @", steps)
    obs = env.step(A[5]); steps += 1  # settle
    grid = canonical_layer(obs)
    stations, station_boxes = parse_stations(grid)
    gates = parse_gates(grid)
    gate_cells = [c for v in gates.values() for c in v]
    gate_colors = sorted(gates)
    print("stations", stations)
    print("gates", gates)
    movs = parse_movables(grid, gate_cells, station_boxes)
    print("movables", [(m["color"], m["centroid"], m["size"]) for m in movs])

    # assignment: pick the permutation where BOTH movables fully cover.
    orig = {m["color"]: m for m in movs}
    assign = {}
    if len(orig) == 2 and len(gate_colors) == 2:
        (ca, ma), (cb, mb) = list(orig.items())
        g0, g1 = gate_colors

        def full(m, g):
            best = max_coverage_offset(list(m["cells"]), gates[g])
            return best is not None and len(best[1]) == len(gates[g])
        opt1 = full(ma, g0) and full(mb, g1)
        opt2 = full(ma, g1) and full(mb, g0)
        if opt1 and not opt2:
            assign = {ca: g0, cb: g1}
        elif opt2 and not opt1:
            assign = {ca: g1, cb: g0}
        elif opt1:
            assign = {ca: g0, cb: g1}
        else:  # neither full: assign by best coverage
            def cov(m, g):
                b = max_coverage_offset(list(m["cells"]), gates[g])
                return len(b[1]) if b else 0
            if cov(ma, g0) + cov(mb, g1) >= cov(ma, g1) + cov(mb, g0):
                assign = {ca: g0, cb: g1}
            else:
                assign = {ca: g1, cb: g0}
    print("assign", assign)

    # ── robust piece tracking (identity by centroid continuity; selection by
    # count + motion, NOT the marker, which is occluded when pieces overlap) ──
    known_colors = set(gate_colors) | set(assign)

    def track(pieces, movs):
        """Persistently match parsed movs to the tracked pieces by OPTIMAL
        (min-total-distance) centroid assignment — greedy per-piece matching
        swaps identities when pieces pass close. Colour is updated only to a
        KNOWN colour (a gate colour or an original assign colour); mid-flood
        transient/mixed colours keep the piece's last stable colour so identity
        survives a recolour. Missing (flood-merged) pieces keep last state."""
        if len(pieces) == 2 and len(movs) == 2:
            def cost(pi, mi):
                a, b = pieces[pi]["centroid"], movs[mi]["centroid"]
                return abs(a[0] - b[0]) + abs(a[1] - b[1])
            if cost(0, 0) + cost(1, 1) <= cost(0, 1) + cost(1, 0):
                pairs = [(0, 0), (1, 1)]
            else:
                pairs = [(0, 1), (1, 0)]
        else:
            pairs = []
            used = set()
            for pi, p in enumerate(pieces):
                best, bd = None, None
                for mi, m in enumerate(movs):
                    if mi in used:
                        continue
                    d = abs(m["centroid"][0] - p["centroid"][0]) + abs(m["centroid"][1] - p["centroid"][1])
                    if bd is None or d < bd:
                        bd, best = d, mi
                if best is not None and bd <= 16:
                    used.add(best); pairs.append((pi, best))
        for pi, mi in pairs:
            m = movs[mi]
            pieces[pi]["centroid"] = m["centroid"]
            pieces[pi]["cells"] = m["cells"]
            if m["color"] in known_colors:
                pieces[pi]["color"] = m["color"]

    grid = canonical_layer(obs)
    movs0 = parse_movables(grid, gate_cells, station_boxes)
    pieces = [{"id": i, "color": m["color"], "cells": m["cells"], "centroid": m["centroid"],
               "shape_rel": None} for i, m in enumerate(movs0)]
    mk0 = marker(grid)
    sel = 0
    if mk0 is not None:
        sel = min(range(len(pieces)),
                  key=lambda i: abs(pieces[i]["centroid"][0] - mk0[0]) + abs(pieces[i]["centroid"][1] - mk0[1]))
    blocked = set()
    ea = 0

    def do(a):
        nonlocal obs, ea, sel
        obs = env.step(A[a]); ea += 1
        if a == 5 and len(pieces) == 2:
            sel = 1 - sel  # ACTION5 cycles selection (fixed engine order)

    def issue(cen, odr, odc):
        cands = []
        if odr:
            cands.append((abs(odr), (_sign(odr), 0)))
        if odc:
            cands.append((abs(odc), (0, _sign(odc))))
        cands.sort(reverse=True)
        key = (round(cen[0] / 3), round(cen[1] / 3))
        for _m, want in cands:
            for a, s in DIRS.items():
                if s == want and (key, a) not in blocked:
                    return a
        return None

    while ea < 4000:
        st = str(obs.state)
        if st.endswith("WIN") or obs.levels_completed >= 4:
            print(f"*** LIVE L4 WIN ea={ea} ***"); return
        grid = canonical_layer(obs)
        movs = parse_movables(grid, gate_cells, station_boxes)
        track(pieces, movs)
        # marker-authoritative selection (pieces are kept SEPARATED by phase
        # order, so the marker is visible; occluded only mid-flood -> keep sel).
        mk = marker(grid)
        if mk is not None:
            inside = []
            for i, pp in enumerate(pieces):
                rs = [r for r, _ in pp["cells"]]; cs = [c for _, c in pp["cells"]]
                if rs and min(rs) - 1 <= mk[0] <= max(rs) + 1 and min(cs) - 1 <= mk[1] <= max(cs) + 1:
                    inside.append((abs(pp["centroid"][0] - mk[0]) + abs(pp["centroid"][1] - mk[1]), i))
            if inside:
                sel = min(inside)[1]

        all_recol = all(pp["color"] in gate_colors for pp in pieces)
        p = pieces[sel]
        color, cen, cells = p["color"], p["centroid"], p["cells"]
        if ea % 50 == 0:
            info = [(pp["color"], pp["centroid"]) for pp in pieces]
            print(f"  ea={ea} sel{sel} recol_all={all_recol} pieces={info}", flush=True)

        if not all_recol:
            # RECOLOUR PHASE — recolour BOTH pieces first (they end at opposite-
            # edge stations, separated), so the later cover phase never overlaps.
            if color in gate_colors:
                do(5); continue  # this one done; select the other to recolour
            if color in assign:
                scen = stations.get(assign[color])
                mv = recolour_move(cen, scen) if scen else None
                do(mv if mv else 5)
            else:
                do(5)  # transient flood colour: advance
            continue

        # COVER PHASE — both recoloured & separated; MARKER-anchor the shape
        # once (the marker is the sprite's exact centre, so cur has no centroid
        # quantization), drive the locked shape to cover ALL its gates.
        need = gates[color]
        anchor = mk if mk is not None else cen
        if p["shape_rel"] is None:
            if mk is None:
                do(5); continue  # wait for the marker to lock a clean shape
            p["shape_rel"] = frozenset((r - mk[0], c - mk[1]) for r, c in cells)
        cur = set((anchor[0] + dr, anchor[1] + dc) for dr, dc in p["shape_rel"])
        covered_now = sum(1 for gt in need if gt in cur)
        best = max_coverage_offset(list(cur), need)
        if best is None:
            do(5); continue
        (odr, odc), cov = best
        if ea % 20 == 0:
            print(f"    COVER ea={ea} sel{sel} c={color}@{cen} off=({odr},{odc}) now={covered_now}/{len(need)} blk={len(blocked)}", flush=True)
        if covered_now == len(need):
            do(5); continue  # already covering all its gates: hold, work the other
        mv = issue(cen, odr, odc)
        if mv is None:
            do(5); continue
        key = (round(cen[0] / 3), round(cen[1] / 3))
        do(mv)
        post = parse_movables(canonical_layer(obs), gate_cells, station_boxes)
        if post:
            near = min(post, key=lambda m: abs(m["centroid"][0] - cen[0]) + abs(m["centroid"][1] - cen[1]))
            if near["centroid"] == cen:
                blocked.add((key, mv))  # selected piece did not move: walled
    print("NO WIN ea", ea)


if __name__ == "__main__":
    main()
