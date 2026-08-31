"""re86 L4 end-to-end: recolour-routing controller. Drive L1-L3 with the
adapter, then at L4: parse movables/gates/stations, assign each movable a gate
colour, route it through the matching-colour changer to recolour, then
colour-aware cover its gates. Reuses covering_offsets. Target: live L4 win.
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
from admorphiq.kernels import covering_offsets, find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
SEL = 0
BORDER_GATE = 4
BORDER_STATION = 2


def marker(grid):
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] == SEL:
                return (r, c)
    return None


def parse_stations(grid):
    """colour-2-bordered 6x6 boxes -> {swatch_color: (center_r, center_c)}."""
    H, W = len(grid), len(grid[0])
    seen = [[False] * W for _ in range(H)]
    out = {}
    for r in range(H):
        for c in range(W):
            if grid[r][c] == BORDER_STATION and not seen[r][c]:
                # flood the colour-2 border component, get bbox
                comp = []
                q = deque([(r, c)]); seen[r][c] = True
                while q:
                    y, x = q.popleft(); comp.append((y, x))
                    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < H and 0 <= nx < W and not seen[ny][nx] and grid[ny][nx] == BORDER_STATION:
                            seen[ny][nx] = True; q.append((ny, nx))
                ys = [p[0] for p in comp]; xs = [p[1] for p in comp]
                cy, cx = (min(ys) + max(ys)) // 2, (min(xs) + max(xs)) // 2
                # interior color = dominant non-(2,5) inside bbox
                inside = Counter()
                for y in range(min(ys), max(ys) + 1):
                    for x in range(min(xs), max(xs) + 1):
                        v = grid[y][x]
                        if v not in (BORDER_STATION, 5):
                            inside[v] += 1
                if inside:
                    out[inside.most_common(1)[0][0]] = (cy, cx)
    return out


def parse_movables(grid):
    """The 2 movable sprites: interior shaped regions (size 30-70), NOT touching
    the frame edge (stations/HUD are edge-pinned), NOT colour-2. The SELECTED
    movable's bbox contains the marker (marker at its centre)."""
    H, W = len(grid), len(grid[0])
    bg = most_common_color(grid)
    regions = find_regions(grid, background=bg, gap=1)
    mk = marker(grid)
    out = []
    for reg in regions:
        cells = reg["cells"]
        cols = Counter(grid[r][c] for r, c in cells if grid[r][c] not in (SEL, bg, 5))
        if not cols:
            continue
        color = cols.most_common(1)[0][0]
        if color == BORDER_STATION:
            continue
        size = len(cells)
        if not (30 <= size <= 90):
            continue
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        if min(rs) <= 1 or max(rs) >= H - 2 or min(cs) <= 1 or max(cs) >= W - 2:
            continue  # edge-pinned (station / HUD)
        contains_mk = mk is not None and min(rs) <= mk[0] <= max(rs) and min(cs) <= mk[1] <= max(cs)
        out.append({"color": color, "cells": frozenset(cells),
                    "contains_mk": contains_mk, "bbox": (min(rs), min(cs), max(rs), max(cs)),
                    "centroid": (sum(rs) // size, sum(cs) // size)})
    # mark the single selected movable = the marker-containing one nearest the marker
    if mk is not None:
        cands = [m for m in out if m["contains_mk"]]
        if cands:
            best = min(cands, key=lambda m: abs(m["centroid"][0] - mk[0]) + abs(m["centroid"][1] - mk[1]))
            for m in out:
                m["selected"] = m is best
        else:
            for m in out:
                m["selected"] = False
    else:
        for m in out:
            m["selected"] = False
    return out


def measure_dirs(env, obs, holder):
    """Probe each of ACTION1-4 once, learn marker displacement -> {action:(dr,dc)}."""
    dirs = {}
    for a in (1, 2, 3, 4):
        grid = canonical_layer(holder[0])
        m0 = marker(grid)
        holder[0] = env.step(A[a])
        grid1 = canonical_layer(holder[0])
        m1 = marker(grid1)
        if m0 and m1 and (m1 != m0):
            dirs[a] = (_sign(m1[0] - m0[0]), _sign(m1[1] - m0[1]))
    return dirs


def move_toward(dirs, dr, dc):
    """Pick an action reducing the larger axis of (dr,dc)."""
    cand = []
    if dr:
        cand.append((abs(dr), (_sign(dr), 0)))
    if dc:
        cand.append((abs(dc), (0, _sign(dc))))
    cand.sort(reverse=True)
    for _m, want in cand:
        for a, s in dirs.items():
            if s == want:
                return a
    return None


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
    holder = [obs]
    # settle
    holder[0] = env.step(A[5]); steps += 1
    grid = canonical_layer(holder[0])
    stations = parse_stations(grid)
    gates_by_color = {}
    for (r, c) in _target_boxes(grid):
        gates_by_color.setdefault(grid[r][c], []).append((r, c))
    gate_colors = sorted(gates_by_color)
    print("stations:", stations)
    print("gates_by_color:", {k: len(v) for k, v in gates_by_color.items()}, "gate_colors", gate_colors)
    # engine dir map is source-fixed (ACTION1=up,2=down,3=left,4=right); the
    # adapter measures the same at runtime. Use it directly in the prototype.
    dirs = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
    print("dirs:", dirs)

    # assignment: each un-recoloured movable -> a gate color not on a movable.
    ea = 0
    for _ in range(2500):
        grid = canonical_layer(holder[0])
        movs = parse_movables(grid)
        if not movs:
            holder[0] = env.step(A[5]); ea += 1; continue
        cur_colors = {m["color"] for m in movs}
        recoloured = cur_colors & set(gate_colors)
        sel = next((m for m in movs if m["selected"]), None)
        st = str(holder[0].state)
        if st.endswith("WIN") or holder[0].levels_completed >= 4:
            print(f"*** LIVE L4 WIN (ea={ea}) ***"); return
        if sel is None:
            holder[0] = env.step(A[5]); ea += 1; continue
        color = sel["color"]
        if color in gate_colors:
            # recoloured -> cover its gates
            gts = gates_by_color[color]
            offs = covering_offsets(list(sel["cells"]), gts)
            # covering_offsets works on absolute cells+points -> offset to apply
            if not offs:
                holder[0] = env.step(A[5]); ea += 1; continue
            dr, dc = min(offs, key=lambda o: abs(o[0]) + abs(o[1]))
            if dr == 0 and dc == 0:
                holder[0] = env.step(A[5]); ea += 1; continue  # placed; cycle
            mv = move_toward(dirs, dr, dc)
            holder[0] = env.step(A[mv if mv else 5]); ea += 1
        else:
            # needs recolour: target = a gate color not on any movable
            avail = [gc for gc in gate_colors if gc not in recoloured]
            if not avail:
                holder[0] = env.step(A[5]); ea += 1; continue
            target = avail[0]
            if target not in stations:
                holder[0] = env.step(A[5]); ea += 1; continue
            scy, scx = stations[target]
            cy, cx = sel["centroid"]
            mv = move_toward(dirs, scy - cy, scx - cx)
            holder[0] = env.step(A[mv if mv else 5]); ea += 1
        if ea < 50 or ea % 100 == 0:
            allm = [(m["color"], m["centroid"], m["selected"]) for m in movs]
            print(f"  ea={ea} sel={sel['color']}@{sel['centroid']} target_phase={'cover' if color in gate_colors else 'recolour'} movs={allm}", flush=True)
    print("no win; ea", ea, "final movs", [(m['color'], m['selected']) for m in parse_movables(canonical_layer(holder[0]))])


if __name__ == "__main__":
    main()
