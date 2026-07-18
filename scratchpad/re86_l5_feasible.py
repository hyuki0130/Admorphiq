"""re86 L5 FEASIBILITY probe (task #84): the decisive de-risk BEFORE building the
tracking/routing machinery. Question: can the 3 movable SHAPES cover the gate-cell
clusters via a single translation each (max_coverage_offset)? The win-check
(`jeiavrvavi`) stamps each movable's pixels at its (x,y) onto a canvas and requires
every non-4 gate cell to equal the stamp. So the FINAL config must have recoloured
movables whose stamped pixels land exactly on their assigned gate cells.

We enumerate 3-way assignments of {movable shape} -> {gate-cell cluster} and report,
per assignment, whether each movable can FULLY cover its cluster (offset exists with
coverage == cluster size) and whether the colour partition is consistent (each
movable recolours to a single colour in {8,9}). GT is used ONLY to get the exact
gate cells + movable shapes for planning; the runtime parse feasibility is a
separate question flagged at the end.
"""
from __future__ import annotations
import sys
from collections import Counter
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter
from admorphiq.adapters25.base import canonical_layer
from admorphiq.kernels import max_coverage_offset

MOV_TAG, STA_TAG, GATE_TAG = "0031cppcuvqlbi", "0007dtbisvazhv", "0054xnsuqceejm"


def reach_l5(env, ad):
    obs = env.observation_space
    s = 0
    while s < 6000 and int(getattr(obs, "levels_completed", 0) or 0) < 4 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def sprite_cells(s):
    """World (row,col) cells of a sprite's non-(-1) pixels, keyed by colour."""
    out = {}
    for j, row in enumerate(s.pixels):        # j = local y
        for i, v in enumerate(row):           # i = local x
            iv = int(v)
            if iv == -1:
                continue
            out.setdefault(iv, []).append((s.y + j, s.x + i))
    return out


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    g = env._game
    ad = Adapter(giveup=6000)
    obs = reach_l5(env, ad)
    if int(getattr(obs, "levels_completed", 0) or 0) != 4:
        print("did NOT reach L5"); return
    for _ in range(2):
        obs = env.step(GameAction.ACTION5)
    lvl = g.current_level

    # --- exact gate cells (win canvas) ---
    gate_sprites = lvl.get_sprites_by_tag(GATE_TAG)
    gate_cells = {}
    for s in gate_sprites:
        for col, cells in sprite_cells(s).items():
            if col == 4:
                continue
            gate_cells.setdefault(col, []).extend(cells)
    print("=== GATE CELLS (exact, from win canvas) ===")
    for col, cells in sorted(gate_cells.items()):
        print(f"  colour-{col}: {len(cells)} cells {sorted(cells)}")

    # --- movable shapes (relative to centroid) ---
    movs = []
    for s in lvl.get_sprites_by_tag(MOV_TAG):
        sc = sprite_cells(s)
        # dominant colour = the movable colour (ignore the 0 marker)
        col = max((c for c in sc if c != 0), key=lambda c: len(sc[c]))
        cells = [cell for c, cl in sc.items() if c != 0 for cell in cl]
        cen = (sum(r for r, _ in cells) // len(cells), sum(c for _, c in cells) // len(cells))
        movs.append({"color": col, "cells": cells, "cen": cen, "n": len(cells)})
    print("\n=== MOVABLE SHAPES ===")
    for m in movs:
        print(f"  colour-{m['color']} n={m['n']} centroid={m['cen']} "
              f"bbox_span={(max(r for r,_ in m['cells'])-min(r for r,_ in m['cells']), max(c for _,c in m['cells'])-min(c for _,c in m['cells']))}")

    # --- cluster the gate cells spatially per colour (a movable covers one cluster) ---
    def cluster(cells, radius=20):
        cells = list(cells)
        clusters = []
        for cell in cells:
            for cl in clusters:
                if any(abs(cell[0]-x)+abs(cell[1]-y) <= radius for x, y in cl):
                    cl.append(cell); break
            else:
                clusters.append([cell])
        return clusters

    clusters = []
    for col, cells in sorted(gate_cells.items()):
        for cl in cluster(cells):
            clusters.append({"color": col, "cells": cl})
    print(f"\n=== GATE CLUSTERS ({len(clusters)}) ===")
    for k, cl in enumerate(clusters):
        print(f"  cluster{k}: colour-{cl['color']} {len(cl['cells'])} cells {sorted(cl['cells'])}")

    # --- feasibility: which movable can FULLY cover which cluster? ---
    print("\n=== COVERAGE MATRIX (movable x cluster: covered/total) ===")
    cov = {}
    for mi, m in enumerate(movs):
        row = []
        for ci, cl in enumerate(clusters):
            best = max_coverage_offset(list(m["cells"]), cl["cells"])
            n = len(best[1]) if best else 0
            cov[(mi, ci)] = n
            row.append(f"{n}/{len(cl['cells'])}")
        print(f"  mov{mi}(c{m['color']}): " + "  ".join(f"cl{ci}:{row[ci]}" for ci in range(len(clusters))))

    # --- enumerate assignments movable->cluster (each movable to >=0 clusters, but
    #     each cluster needs exactly one fully-covering movable; a movable may cover
    #     multiple clusters only if same colour) ---
    print("\n=== FEASIBLE ASSIGNMENTS (each cluster fully covered) ===")
    nC = len(clusters)
    found = 0
    for assign in product(range(len(movs)), repeat=nC):
        # assign[ci] = movable index for cluster ci
        ok = all(cov[(assign[ci], ci)] == len(clusters[ci]["cells"]) for ci in range(nC))
        if not ok:
            continue
        # colour consistency: a movable assigned to multiple clusters -> same colour
        mov_colours = {}
        consistent = True
        for ci in range(nC):
            mi = assign[ci]
            want = clusters[ci]["color"]
            if mi in mov_colours and mov_colours[mi] != want:
                consistent = False; break
            mov_colours[mi] = want
        if not consistent:
            continue
        found += 1
        if found <= 10:
            desc = ", ".join(f"cl{ci}->mov{assign[ci]}(recolour c{clusters[ci]['color']})" for ci in range(nC))
            print(f"  FEASIBLE: {desc}")
    print(f"total feasible assignments: {found}")


if __name__ == "__main__":
    main()
