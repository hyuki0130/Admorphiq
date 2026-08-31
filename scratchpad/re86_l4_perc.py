"""re86 L4 frame-only perception probe. Reach L4 via the adapter, settle, then
dump my frame-only reads: gates (colour-4 boxes by colour), stations (colour-2
boxes by centre colour), both movables (gate-excluded regions), and the
assignment feasibility (max_coverage_offset full-cover test per movable x gate
colour). No sprite-tag reads in the perception path."""
from __future__ import annotations
import sys
from collections import Counter, deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _target_boxes
from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.kernels import find_regions, max_coverage_offset

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
SEL, BG_GATE, BG_STATION = 0, 4, 2


def marker(grid):
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] == SEL:
                return (r, c)
    return None


def parse_stations(grid):
    H, W = len(grid), len(grid[0])
    seen = [[False] * W for _ in range(H)]
    out = {}
    for r in range(H):
        for c in range(W):
            if grid[r][c] == BG_STATION and not seen[r][c]:
                comp = []
                q = deque([(r, c)]); seen[r][c] = True
                while q:
                    y, x = q.popleft(); comp.append((y, x))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < H and 0 <= nx < W and not seen[ny][nx] and grid[ny][nx] == BG_STATION:
                                seen[ny][nx] = True; q.append((ny, nx))
                ys = [p[0] for p in comp]; xs = [p[1] for p in comp]
                cy, cx = (min(ys) + max(ys)) // 2, (min(xs) + max(xs)) // 2
                inside = Counter()
                for y in range(min(ys), max(ys) + 1):
                    for x in range(min(xs), max(xs) + 1):
                        v = grid[y][x]
                        if v not in (BG_STATION, 5):
                            inside[v] += 1
                if inside:
                    out[inside.most_common(1)[0][0]] = (cy, cx)
    return out


def parse_gates(grid):
    by = {}
    for (r, c) in _target_boxes(grid):
        by.setdefault(grid[r][c], []).append((r, c))
    return by


def parse_movables(grid, gate_cells, station_cells):
    """Regions that are NOT gates/stations/HUD: connected components (gap=1)
    excluding known gate + station + border cells; size 20-90, not edge-pinned."""
    H, W = len(grid), len(grid[0])
    bg = most_common_color(grid)
    exclude = set(gate_cells) | set(station_cells)
    regions = find_regions(grid, background=(bg, BG_GATE, BG_STATION, SEL), gap=1)
    out = []
    for reg in regions:
        cells = frozenset(reg["cells"]) - exclude
        if not (20 <= len(cells) <= 90):
            continue
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        if min(rs) <= 1 or max(rs) >= H - 2 or min(cs) <= 1 or max(cs) >= W - 2:
            continue
        cols = Counter(grid[r][c] for r, c in cells if grid[r][c] not in (SEL, bg))
        if not cols:
            continue
        out.append({"color": cols.most_common(1)[0][0], "cells": cells,
                    "centroid": (sum(rs) // len(cells), sum(cs) // len(cells)),
                    "size": len(cells)})
    return out


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    obs = env.observation_space
    adapter = Adapter(giveup=9000)
    steps = 0
    while steps < 9000 and obs.levels_completed < 3:
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    print("reached L4 @", steps, "levels", obs.levels_completed)
    for _ in range(2):
        obs = env.step(A[5]); steps += 1
    grid = canonical_layer(obs)
    stations = parse_stations(grid)
    gates = parse_gates(grid)
    gate_cells = [c for v in gates.values() for c in v]
    station_cells = []
    movs = parse_movables(grid, gate_cells, station_cells)
    print("stations:", stations)
    print("gates:", {k: v for k, v in gates.items()})
    print("movables:", [(m["color"], m["centroid"], m["size"]) for m in movs])
    gate_colors = sorted(gates)
    print("=== assignment feasibility (max_coverage_offset full-cover) ===")
    for m in movs:
        for g in gate_colors:
            best = max_coverage_offset(list(m["cells"]), gates[g])
            n = len(best[1]) if best else 0
            print(f"  mov colour {m['color']} size {m['size']} -> gates {g} ({len(gates[g])}): offset {best[0] if best else None} covers {n}/{len(gates[g])}")


if __name__ == "__main__":
    main()
