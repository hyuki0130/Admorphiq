"""re86 L7 scratch controller (R65): per-piece recolour -> reshape -> place FSM,
frame-only. The three movables SPAWN OVERLAPPING, so colour-based frame tracking
loses a piece behind another; identity is tracked by nearest-centroid-to-marker
(the selection marker = the selected piece's exact centre), the L5 discipline.

Assignment (frame-derived, feasibility-proven):
  outline colour-12 -> recolour 9 -> vertical reshape 13x13->7x19 -> place
     rows 18-24 cols 39-57 (corners cover target-9 (18,57),(24,39))
  cross colour-7  -> recolour 8 -> bar-shift -> cover target-8 plus
  cross colour-10 -> recolour 11 -> bar-shift -> cover target-11 plus
Recolour leg = column-align in the interior then drive UP the target column
(only that station is in the column). dir 1=up 2=down 3=left 4=right.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import (
    Adapter, _station_boxes, _target_boxes, _l6_obstacle_box, _l5_route,
)
from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.kernels import find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
DIRMAP = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
MOVE_IDS = [1, 2, 3, 4]
_OBST = 1


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def marker(grid):
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            if grid[r][c] == 0:
                return (r, c)
    return None


def l7_regions(grid, station_boxes):
    """All movable-ish colour regions (excluding bg/border/station/obstacle),
    with bbox + centroid. Under overlap a piece may be missing/merged."""
    bg = most_common_color(grid)
    exclude = {bg, 4, 2, 0, _OBST}
    out = []
    for reg in find_regions(grid, background=bg, gap=1):
        if reg["color"] in exclude:
            continue
        cells = frozenset(reg["cells"])
        if len(cells) < 12:
            continue
        rs = [r for r, _c in cells]; cs = [c for _r, c in cells]
        if max(rs) - min(rs) < 3 or max(cs) - min(cs) < 3:
            continue
        cen = (sum(rs) // len(cells), sum(cs) // len(cells))
        if any(b[0] - 1 <= cen[0] <= b[2] + 1 and b[1] - 1 <= cen[1] <= b[3] + 1 for b in station_boxes):
            continue
        out.append({"color": reg["color"], "cells": cells, "cen": cen,
                    "bbox": (min(rs), max(rs), min(cs), max(cs))})
    return out


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    steps = 0
    while steps < 4000 and int(getattr(obs, "levels_completed", 0) or 0) < 6 and not ad.is_done([], obs):
        obs = step(env, ad.choose_action([], obs)); steps += 1
    for _ in range(3):
        obs = step(env, A[5])
    g = canonical_layer(obs)
    stations, sboxes = _station_boxes(g)
    sbox = {}
    for col, cen in stations.items():
        for b in sboxes:
            if b[0] <= cen[0] <= b[2] and b[1] <= cen[1] <= b[3]:
                sbox[col] = b; break
    ob = _l6_obstacle_box(g)
    tby = {}
    for r, c in _target_boxes(g):
        tby.setdefault(g[r][c], []).append((r, c))
    regs = l7_regions(g, sboxes)
    print(f"L7 stations={stations} obstacle={ob}")
    print(f"targets={ {k: sorted(v) for k, v in tby.items()} }")
    for m in regs:
        print(f"  spawn colour={m['color']} bbox={m['bbox']} cen={m['cen']}")

    # rectangle target colour = the one with 2 cells not sharing row/col (outline)
    rect_color = next(k for k, v in tby.items() if len(v) == 2)
    tgt9 = sorted(tby[rect_color])
    tr = [r for r, _c in tgt9]; tc = [c for _r, c in tgt9]
    rect = (min(tr), max(tr), min(tc), max(tc))
    th, tw = rect[1] - rect[0] + 1, rect[3] - rect[2] + 1
    outline_spawn_color = 12  # frame-parseable at spawn (hollow); assignment: 12->rect
    print(f"outline colour=12 -> recolour {rect_color}, rect {rect} ({th}x{tw})")

    # ---- pure marker-based identity: track each piece's centre ONLY from the
    # marker (the selection marker = the selected piece's exact centre; parse
    # centroids are noisy under overlap). Init from the clean spawn parse. ----
    pcen = {m["color"]: m["cen"] for m in regs}  # {spawn-colour: centre}
    OUT = 12  # outline piece identity = its spawn colour

    def sel_color(mk):
        return min(pcen, key=lambda k: abs(pcen[k][0] - mk[0]) + abs(pcen[k][1] - mk[1]))

    def region_at(grid, mk):
        """The isolated region whose bbox tightly contains the marker (valid once
        the piece has separated from the bottom cluster)."""
        best = None
        for m in l7_regions(grid, sboxes):
            r0, r1, c0, c1 = m["bbox"]
            if r0 - 1 <= mk[0] <= r1 + 1 and c0 - 1 <= mk[1] <= c1 + 1:
                # prefer the tighter bbox (an overlapping neighbour has a looser fit)
                area = (r1 - r0) * (c1 - c0)
                if best is None or area < best[1]:
                    best = (m, area)
        return best[0] if best else None

    phase = "recolour"
    walls = set()
    half = 7
    for it in range(500):
        g = canonical_layer(obs)
        mk = marker(g)
        if mk is None:
            obs = step(env, A[5]); continue  # flood wait
        sel = sel_color(mk)
        pcen[sel] = mk  # the marker is the selected piece's exact centre
        if it < 40:
            print(f"  it{it} mk={mk} sel={sel} phase={phase} pcen={pcen}")
        if sel != OUT:
            obs = step(env, A[5]); continue  # cycle to our piece
        reg = region_at(g, mk)
        cur_color = reg["color"] if reg else None

        if phase == "recolour":
            if cur_color == rect_color:
                phase = "reshape"
                print(f"  [it{it}] recoloured -> {rect_color} bbox={reg['bbox']}")
                continue
            scen = stations[rect_color]
            want = (0, 1 if mk[1] < scen[1] else -1) if abs(mk[1] - scen[1]) > 2 else (-1, 0)
            act = next((a for a, v in DIRMAP.items() if v == want), None)
            if it < 80:
                print(f"  it{it} REC mk={mk} col={cur_color} want={want}")
            obs = step(env, A[act] if act else A[5]); continue

        if phase == "reshape":
            if reg is None:
                obs = step(env, A[5]); continue
            r0, r1, c0, c1 = reg["bbox"]
            h, w = r1 - r0 + 1, c1 - c0 + 1
            if h <= th:
                phase = "place"
                print(f"  [it{it}] reshaped to {h}x{w} @({r0},{c0})")
                continue
            obc = (ob[1] + ob[3]) // 2
            if not (c0 <= ob[3] and c1 >= ob[1]):
                goal = (max(ob[0] - 6, 12), obc)  # above obstacle, col-aligned
                act = _l5_route(mk, goal, half, list(sbox.values()), walls, DIRMAP, MOVE_IDS)
                obs = step(env, A[act] if act else A[5]); continue
            obs = step(env, A[2]); continue  # push DOWN = vertical reshape

        if phase == "place":
            if reg is None:
                obs = step(env, A[5]); continue
            if all(t in reg["cells"] for t in tgt9):
                print(f"  [it{it}] OUTLINE PLACED bbox={reg['bbox']} covers {tgt9}")
                break
            tgt_cen = ((rect[0] + rect[1]) // 2, (rect[2] + rect[3]) // 2)
            avoid = (ob[0] - th, ob[1] - tw, ob[2] + th, ob[3] + tw)
            act = _l5_route(mk, tgt_cen, 0, list(sbox.values()) + [avoid], walls, DIRMAP, MOVE_IDS)
            obs = step(env, A[act] if act else A[5]); continue
    else:
        print(f"  outline leg unfinished phase={phase} pcen={pcen}")


if __name__ == "__main__":
    main()
