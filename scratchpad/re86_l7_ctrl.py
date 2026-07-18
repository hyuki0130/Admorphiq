"""re86 L7 scratch controller (R66): CYCLE-INDEX identity + per-piece
recolour->reshape->place FSM, frame-only.

The three movables SPAWN OVERLAPPING, so colour/centroid parse loses a piece.
KEY: a piece's SELECTION-CYCLE POSITION (sprite index) never changes, even after
recolour — so cycle-index is bulletproof identity. Calibrate index->spawn-colour
once (the engine cycle order is fixed), then track the selected index by counting
confirmed ACTION5 advances (a flood-wait ACTION5 does NOT advance selection — the
flood branch returns early @2103), and drive the selected piece by its marker.

This build validates the OUTLINE leg (colour-12 -> recolour 9 -> vertical reshape
13x13->19x7 -> place rows18-24 cols39-57) end-to-end frame-only. dir 1=up 2=down
3=left 4=right.
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


def _in_boxes(cell, boxes, pad=1):
    r, c = cell
    return any(b[0] - pad <= r <= b[2] + pad and b[1] - pad <= c <= b[3] + pad for b in boxes)


def l7_regions(grid, station_boxes):
    bg = most_common_color(grid)
    exclude = {bg, 4, 2, 0, _OBST}
    out = []
    for reg in find_regions(grid, background=bg, gap=1):
        if reg["color"] in exclude:
            continue
        # Subtract station-box pixels so a RECOLOURED piece abutting its same-
        # colour station swatch keeps its true shape/centroid (the L5 discipline).
        cells = frozenset(c for c in reg["cells"] if not _in_boxes(c, station_boxes, pad=1))
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


def region_at(grid, mk, sboxes):
    """Tightest region whose bbox contains the marker (the selected piece's live
    shape once it has separated from the cluster)."""
    best = None
    for m in l7_regions(grid, sboxes):
        r0, r1, c0, c1 = m["bbox"]
        if r0 - 1 <= mk[0] <= r1 + 1 and c0 - 1 <= mk[1] <= c1 + 1:
            area = (r1 - r0) * (c1 - c0)
            if best is None or area < best[1]:
                best = (m, area)
    return best[0] if best else None


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
    spawn_cen = {m["color"]: m["cen"] for m in regs}
    print(f"L7 stations={stations} obstacle={ob} targets={ {k: sorted(v) for k,v in tby.items()} }")

    # ---- calibrate cycle-index -> spawn-colour (fixed identity) ----
    def nearest_spawn(mk):
        return min(spawn_cen, key=lambda k: abs(spawn_cen[k][0] - mk[0]) + abs(spawn_cen[k][1] - mk[1]))

    idx_color = []
    for _k in range(3):
        idx_color.append(nearest_spawn(marker(canonical_layer(obs))))
        obs = step(env, A[5])
    sel = 0
    print(f"cycle idx_color = {idx_color} (sel=0)")

    def do_cycle():
        """Issue ACTION5. If a flood is active (marker None) the engine does NOT
        advance selection; otherwise sel advances by one."""
        nonlocal obs, sel
        flooding = marker(canonical_layer(obs)) is None
        obs = step(env, A[5])
        if not flooding:
            sel = (sel + 1) % 3

    rect_color = next(k for k, v in tby.items() if len(v) == 2)
    tgt9 = sorted(tby[rect_color])
    tr = [r for r, _c in tgt9]; tc = [c for _r, c in tgt9]
    rect = (min(tr), max(tr), min(tc), max(tc))
    th, tw = rect[1] - rect[0] + 1, rect[3] - rect[2] + 1
    OUT = 12
    print(f"outline colour={OUT} -> recolour {rect_color}, rect {rect} ({th}x{tw})")

    phase = "recolour"
    walls = set()
    obc = (ob[1] + ob[3]) // 2
    # NEVER press ACTION5 when the marker is invisible: mk=None means the selected
    # piece's centre marker is OCCLUDED by another piece's body (measured:
    # colour-10's hbar renders over colour-12's centre), NOT necessarily a flood.
    # A5 on an occluded frame cycles the engine and desyncs selection. Instead,
    # re-issue the current drive move (a move never cycles; a flood harmlessly
    # ignores it and advances; occlusion keeps the piece moving until the marker
    # re-emerges). A5 fires ONLY on a visible marker, so the count stays synced.
    last_act = 1  # default nudge (up) before the first real move
    for it in range(700):
        g = canonical_layer(obs)
        mk = marker(g)
        if mk is None:
            obs = step(env, A[last_act]); continue  # occluded/flood: hold the drive
        if idx_color[sel] != OUT:
            obs = step(env, A[5]); sel = (sel + 1) % 3; continue  # visible -> real cycle
        reg = region_at(g, mk, sboxes)
        cur_color = reg["color"] if reg else None

        if phase == "recolour":
            if cur_color == rect_color:
                phase = "reshape"
                print(f"  [it{it}] recoloured -> {rect_color} bbox={reg['bbox']}")
                continue
            scen = stations[rect_color]
            # UP-FIRST separation, then column-align, then up into the station.
            if mk[0] > 36:
                want = (-1, 0)
            elif abs(mk[1] - scen[1]) > 2:
                want = (0, 1 if mk[1] < scen[1] else -1)
            else:
                want = (-1, 0)
            act = next((a for a, v in DIRMAP.items() if v == want), 1)
            last_act = act
            obs = step(env, A[act]); continue

        if phase == "reshape":
            # Route by MARKER (reg may vanish under occlusion/station-merge); use
            # reg only to read the reshaped height + col-overlap when available.
            if reg is not None:
                r0, r1, c0, c1 = reg["bbox"]
                h, w = r1 - r0 + 1, c1 - c0 + 1
                if h <= th:
                    phase = "place"
                    print(f"  [it{it}] reshaped to {h}x{w} @({r0},{c0})")
                    continue
                col_overlap = c0 <= ob[3] and c1 >= ob[1]
                below_needed = r1 < ob[0]
            else:
                # approx from the marker (outline half-width ~6, half-height ~6)
                col_overlap = ob[1] - 7 <= mk[1] <= ob[3] + 7
                below_needed = mk[0] < ob[0] - 6
            if not col_overlap or below_needed:
                # route the centre to just above the obstacle, col-aligned to it
                goal = (max(ob[0] - 7, 14), obc)
                act = _l5_route(mk, goal, 7, list(sbox.values()), walls, DIRMAP, MOVE_IDS) or 2
                last_act = act
                obs = step(env, A[act]); continue
            last_act = 2
            obs = step(env, A[2]); continue  # push DOWN -> vertical reshape

        if phase == "place":
            if reg is None:
                obs = step(env, A[last_act]); continue
            if all(t in reg["cells"] for t in tgt9):
                print(f"  [it{it}] OUTLINE PLACED bbox={reg['bbox']} covers {tgt9}")
                break
            tgt_cen = ((rect[0] + rect[1]) // 2, (rect[2] + rect[3]) // 2)
            avoid = (ob[0] - th, ob[1] - tw, ob[2] + th, ob[3] + tw)
            act = _l5_route(mk, tgt_cen, 0, list(sbox.values()) + [avoid], walls, DIRMAP, MOVE_IDS) or 1
            last_act = act
            obs = step(env, A[act]); continue
    else:
        g = canonical_layer(obs)
        mk2 = marker(g) or (0, 0)
        print(f"  outline leg UNFINISHED phase={phase} sel={sel} reg={region_at(g, mk2, sboxes)}")


if __name__ == "__main__":
    main()
