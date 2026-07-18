"""re86 L7 FULL 3-leg run, frame-only: place all three movables so the snapshot
win fires (levels 6 -> 7). Consolidates the three verified legs behind ONE
cycle-index identity calibration:
  - colour-12 (13x13 outline) -> recolour 9 -> vertical reshape 13x13->19x7 ->
    place rect corners (18,57),(24,39)  [re86_l7_ctrl.py]
  - colour-10 (19x19 cross)  -> recolour 11 -> bar-shift -> place plus
    (30,45),(48,39),(48,51)             [re86_l7_cross.py]
  - colour-7  (37x19 cross)  -> recolour 8  -> BFS bar-shift+place plus
    (9,9),(15,3),(15,36),(27,9)         [re86_l7_c7.py, BFS over re86_l7_sim]
Movables do NOT collide with each other (the engine's collision handler checks
only the obstacle + stations), so a placed piece stays put while another is
worked, and leg order is free. This is the blueprint for Adapter._decide_l7.
"""
from __future__ import annotations
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import (
    Adapter, _station_boxes, _target_boxes, _l6_obstacle_box, _l6_cross_state, _l5_route,
)
from admorphiq.adapters25.base import canonical_layer
from re86_l7_ctrl import marker, l7_regions, region_at  # type: ignore
from re86_l7_sim import bfs_plan  # type: ignore

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
DIRMAP = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
MOVE_IDS = [1, 2, 3, 4]


_NSTEP = [0]
_GO_AT = [None]


def step(env, a):
    r = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    _NSTEP[0] += 1
    if _GO_AT[0] is None and str(getattr(r, "state", "")) == "GameState.GAME_OVER":
        _GO_AT[0] = _NSTEP[0]
        print(f"    !! GAME_OVER at global step {_NSTEP[0]}")
    return r


class Ctx:
    def __init__(self, env, obs, stations, sboxes, sbox, ob, tby, idx_color):
        self.env = env; self.obs = obs
        self.stations = stations; self.sboxes = sboxes; self.sbox = sbox
        self.ob = ob; self.tby = tby; self.idx_color = idx_color
        self.sel = 0
        self.obc = (ob[1] + ob[3]) // 2

    def cur_marker(self):
        return marker(canonical_layer(self.obs))


def _cross_place_target(tgt):
    """plus/T target -> (goal_state, tgt_cells) for a CROSS. vbar col = col shared
    by >=2 tips (or the odd-one-out for a 3-cell T); hbar row = row shared by >=2
    tips. Frame x = min tip col, y = min tip row."""
    tr = [r for r, _c in tgt]; tc = [c for _r, c in tgt]
    rc, cc = Counter(tr), Counter(tc)
    hbar_row = rc.most_common(1)[0][0]
    vbar_col = cc.most_common(1)[0][0]
    return vbar_col, hbar_row


def leg_cross_bfs(ctx, color, tgt_color, w, h, verbose=True):
    """colour-7-style leg: recolour (right-detour around the obstacle) then BFS
    bar-shift+place. Works for any wide cross; the outline of the recolour route
    keeps the piece on-board."""
    env = ctx.env; ob = ctx.ob
    tgt = sorted(ctx.tby[tgt_color])
    st_col = ctx.stations[tgt_color][1]
    vbar_col, hbar_row = _cross_place_target(tgt)
    place_x = min(c for _r, c in tgt); place_y = min(r for r, _c in tgt)
    goal = (place_x, place_y, vbar_col - place_x, hbar_row - place_y)
    ob_right = ob[3]; half_w = w // 2
    phase = "reco_right"; last_act = 4; plan: list[int] = []
    for it in range(500):
        g = canonical_layer(ctx.obs)
        mk = marker(g)
        if mk is None:
            ctx.obs = step(env, A[last_act]); continue
        if ctx.idx_color[ctx.sel] != color:
            ctx.obs = step(env, A[5]); ctx.sel = (ctx.sel + 1) % 3; continue
        reg = region_at(g, mk, ctx.sboxes)
        cur = reg["color"] if reg else None
        if verbose and it % 40 == 0:
            print(f"      c{color} it{it} phase={phase} mk={mk} cur={cur} sel={ctx.sel}")
        if phase == "reco_right":
            if cur == tgt_color:
                phase = "settle"; continue
            # move right until the whole frame clears the obstacle on the right
            # (so the rise is collision-free): marker col = frame x + half_w.
            if mk[1] < ob_right + half_w + 2:
                last_act = 4; ctx.obs = step(env, A[4]); continue
            phase = "reco_up1"
        if phase == "reco_up1":
            if cur == tgt_color:
                phase = "settle"; continue
            if mk[0] > 18:
                last_act = 1; ctx.obs = step(env, A[1]); continue
            phase = "reco_left"
        if phase == "reco_left":
            if cur == tgt_color:
                phase = "settle"; continue
            # align the vbar (= marker col during recolour) to the station column
            # WITHIN its box, so ONLY the 1-wide vbar tip rises into that one
            # station (a mis-aligned col lets the wide hbar clip a neighbour and
            # recolour to the wrong colour — the colour-10 GAME_OVER bug).
            if mk[1] > st_col + 1:
                last_act = 3; ctx.obs = step(env, A[3]); continue
            if mk[1] < st_col - 1:
                last_act = 4; ctx.obs = step(env, A[4]); continue
            phase = "reco_up2"
        if phase == "reco_up2":
            if cur == tgt_color:
                phase = "settle"
                if verbose:
                    print(f"    [it{it}] {color}->recoloured {tgt_color} mk={mk}")
                continue
            last_act = 1; ctx.obs = step(env, A[1]); continue
        if phase == "settle":
            if reg is None or reg["bbox"][0] < 7:
                last_act = 2; ctx.obs = step(env, A[2]); continue
            phase = "plan"
        if phase == "plan":
            if reg is None:
                ctx.obs = step(env, A[last_act]); continue
            s = _l6_cross_state(reg["cells"])
            st = (s["c0"], s["r0"], s["va"] - s["c0"], s["ha"] - s["r0"])
            plan = bfs_plan(st, goal, w, h, ob, valid=lambda z: z[1] >= 7) or []
            if verbose:
                print(f"    [it{it}] {color} place plan from {st} len={len(plan)}")
            if not plan and not all(t in reg["cells"] for t in tgt):
                last_act = 2; ctx.obs = step(env, A[2]); continue
            phase = "exec"
        if phase == "exec":
            if reg is None:
                ctx.obs = step(env, A[last_act]); continue
            if all(t in reg["cells"] for t in tgt):
                if verbose:
                    print(f"    [it{it}] {color} PLACED bbox={reg['bbox']}")
                return True
            if not plan:
                phase = "plan"; continue
            a = plan.pop(0); last_act = a; ctx.obs = step(env, A[a]); continue
    return False


def leg_outline(ctx, verbose=True):
    """colour-12 outline -> recolour 9 -> vertical reshape -> place rect corners.
    Ported from re86_l7_ctrl.py (the DONE outline leg)."""
    env = ctx.env; ob = ctx.ob; sboxes = ctx.sboxes; sbox = ctx.sbox
    OUT = 12
    rect_color = next(k for k, v in ctx.tby.items() if len(v) == 2)
    tgt9 = sorted(ctx.tby[rect_color])
    tr = [r for r, _c in tgt9]; tc = [c for _r, c in tgt9]
    rect = (min(tr), max(tr), min(tc), max(tc))
    th, tw = rect[1] - rect[0] + 1, rect[3] - rect[2] + 1
    phase = "recolour"; walls: set = set(); last_act = 1
    for it in range(900):
        g = canonical_layer(ctx.obs); mk = marker(g)
        if mk is None:
            ctx.obs = step(env, A[last_act]); continue
        if ctx.idx_color[ctx.sel] != OUT:
            ctx.obs = step(env, A[5]); ctx.sel = (ctx.sel + 1) % 3; continue
        reg = region_at(g, mk, sboxes); cur = reg["color"] if reg else None
        if phase == "recolour":
            if cur == rect_color:
                phase = "reshape"; continue
            scen = ctx.stations[rect_color]
            if mk[0] > 36:
                want = (-1, 0)
            elif abs(mk[1] - scen[1]) > 2:
                want = (0, 1 if mk[1] < scen[1] else -1)
            else:
                want = (-1, 0)
            act = next((a for a, v in DIRMAP.items() if v == want), 1)
            last_act = act; ctx.obs = step(env, A[act]); continue
        if phase == "reshape":
            if reg is not None:
                r0, r1, c0, c1 = reg["bbox"]; hh = r1 - r0 + 1
                if hh <= th:
                    phase = "place"; continue
                col_overlap = c0 <= ob[3] and c1 >= ob[1]; below_needed = r1 < ob[0]
            else:
                col_overlap = ob[1] - 7 <= mk[1] <= ob[3] + 7; below_needed = mk[0] < ob[0] - 6
            if not col_overlap or below_needed:
                goal = (max(ob[0] - 7, 14), ctx.obc)
                act = _l5_route(mk, goal, 7, list(sbox.values()), walls, DIRMAP, MOVE_IDS) or 2
                last_act = act; ctx.obs = step(env, A[act]); continue
            last_act = 2; ctx.obs = step(env, A[2]); continue
        if phase == "place":
            if reg is None:
                ctx.obs = step(env, A[last_act]); continue
            if all(t in reg["cells"] for t in tgt9):
                if verbose:
                    print(f"    [it{it}] outline PLACED bbox={reg['bbox']}")
                return True
            tgt_cen = ((rect[0] + rect[1]) // 2, (rect[2] + rect[3]) // 2)
            avoid = (ob[0] - th, ob[1] - tw, ob[2] + th, ob[3] + tw)
            act = _l5_route(mk, tgt_cen, 0, list(sbox.values()) + [avoid], walls, DIRMAP, MOVE_IDS) or 1
            last_act = act; ctx.obs = step(env, A[act]); continue
    return False


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    s = 0
    while s < 4000 and int(getattr(obs, "levels_completed", 0) or 0) < 6 and not ad.is_done([], obs):
        obs = step(env, ad.choose_action([], obs)); s += 1
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
    spawn = {m["color"]: m["cen"] for m in regs}

    def nearest_spawn(mk):
        return min(spawn, key=lambda k: abs(spawn[k][0] - mk[0]) + abs(spawn[k][1] - mk[1]))
    idx_color = []
    for _k in range(3):
        idx_color.append(nearest_spawn(marker(canonical_layer(obs))))
        obs = step(env, A[5])
    print(f"stations={stations} obstacle={ob} idx_color={idx_color}")
    print(f"targets={ {k: sorted(v) for k, v in tby.items()} }")

    ctx = Ctx(env, obs, stations, sboxes, sbox, ob, tby, idx_color)

    def lv():
        return int(getattr(ctx.obs, "levels_completed", 0) or 0)

    def state():
        return getattr(ctx.obs, "state", None)

    legs = [
        ("colour-7 cross", lambda: leg_cross_bfs(ctx, 7, 8, 37, 19)),
        ("colour-10 cross", lambda: leg_cross_bfs(ctx, 10, 11, 19, 19)),
        ("colour-12 outline", lambda: leg_outline(ctx)),
    ]
    for name, fn in legs:
        print(f"--- leg: {name} (level={lv()} state={state()}) ---")
        ok = fn()
        print(f"    -> {'placed' if ok else 'FAILED'} (level now {lv()} state={state()})")
        if lv() >= 7:
            print(f"*** L7 CLEARED after {name} ***"); break
    print(f"FINAL levels_completed={lv()} state={state()}")


if __name__ == "__main__":
    main()
