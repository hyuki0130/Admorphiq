"""re86 L7 colour-7 leg (the 37x19 RECTANGULAR cross), frame-only.

colour-7 -> recolour 8 -> bar-shift + place onto the colour-8 plus
[(9,9),(15,3),(15,36),(27,9)]. The recolour goes around the RIGHT of the
obstacle (the 37-wide hbar pins on the obstacle if risen through it, so detour:
right past the obstacle, rise above it, left to the station-8 column, up so ONLY
the 1-wide vbar tip touches station-8). The bar-shift+place is planned by BFS
over the faithful offline cross simulator (re86_l7_sim), not a hand FSM.

dir 1=up 2=down 3=left 4=right. Reuses the proven cycle-index identity +
occlusion-safe drive from re86_l7_ctrl.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import (
    Adapter, _station_boxes, _target_boxes, _l6_obstacle_box, _l6_cross_state,
)
from admorphiq.adapters25.base import canonical_layer
from re86_l7_ctrl import marker, l7_regions, region_at  # type: ignore
from re86_l7_sim import bfs_plan, sim_move  # type: ignore

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
C7 = 7
TGT = 8
W, H = 37, 19


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def parse_state(reg):
    """(x, y, vrel, hrel) from a parsed cross region (frame-only)."""
    s = _l6_cross_state(reg["cells"])
    return (s["c0"], s["r0"], s["va"] - s["c0"], s["ha"] - s["r0"])


def run(env, obs, ad, verbose=True):
    for _ in range(3):
        obs = step(env, A[5])
    g = canonical_layer(obs)
    stations, sboxes = _station_boxes(g)
    ob = _l6_obstacle_box(g)
    tby = {}
    for r, c in _target_boxes(g):
        tby.setdefault(g[r][c], []).append((r, c))
    tgt8 = sorted(tby[TGT])
    st8 = stations[TGT]                      # (4, 37)
    obc = (ob[1] + ob[3]) // 2
    regs = l7_regions(g, sboxes)
    spawn = {m["color"]: m["cen"] for m in regs}
    if verbose:
        print(f"obstacle={ob} station8={st8} tgt8={tgt8} spawn7={spawn.get(C7)}")

    # place target: vbar abs col 9, hbar abs row 15, frame x=3 y=9 -> vrel=6 hrel=6
    tr = [r for r, _c in tgt8]; tc = [c for _r, c in tgt8]
    vbar_col = min(tc)                       # 3? no: plus vbar col shared by 2 tips
    # vbar col = the col shared by the two vertical tips (9); hbar row = row shared
    # by the two horizontal tips (15).
    from collections import Counter
    vbar_col = Counter(tc).most_common(1)[0][0]
    hbar_row = Counter(tr).most_common(1)[0][0]
    place_x = min(tc)                        # hbar leftmost tip col = frame x
    place_y = min(tr)                        # vbar topmost tip row = frame y
    goal = (place_x, place_y, vbar_col - place_x, hbar_row - place_y)
    if verbose:
        print(f"vbar_col={vbar_col} hbar_row={hbar_row} -> goal={goal}")

    # cycle-index identity calibration
    def nearest_spawn(mk):
        return min(spawn, key=lambda k: abs(spawn[k][0] - mk[0]) + abs(spawn[k][1] - mk[1]))
    idx_color = []
    for _k in range(3):
        idx_color.append(nearest_spawn(marker(canonical_layer(obs))))
        obs = step(env, A[5])
    sel = 0
    if verbose:
        print(f"idx_color={idx_color}")

    st8_col = st8[1]                         # 37
    phase = "reco_right"
    last_act = 4
    plan: list[int] = []
    for it in range(900):
        g = canonical_layer(obs)
        mk = marker(g)
        if mk is None:
            obs = step(env, A[last_act]); continue        # occluded/flood: hold drive
        if idx_color[sel] != C7:
            obs = step(env, A[5]); sel = (sel + 1) % 3; continue
        reg = region_at(g, mk, sboxes)
        cur = reg["color"] if reg else None

        # ---- recolour phases (marker-driven waypoints around the obstacle) ----
        if phase == "reco_right":
            if cur == TGT:
                phase = "settle"; continue
            if mk[1] < st8_col + 18:                       # marker col < ~55 (x=36)
                last_act = 4; obs = step(env, A[4]); continue
            phase = "reco_up1"; continue
        if phase == "reco_up1":
            if cur == TGT:
                phase = "settle"; continue
            if mk[0] > 18:                                 # rise to y~9 (marker row ~18)
                last_act = 1; obs = step(env, A[1]); continue
            phase = "reco_left"; continue
        if phase == "reco_left":
            if cur == TGT:
                phase = "settle"; continue
            if mk[1] > st8_col - 1:                         # marker col -> station-8 col (37)
                last_act = 3; obs = step(env, A[3]); continue
            phase = "reco_up2"; continue
        if phase == "reco_up2":
            if cur == TGT:
                phase = "settle"; print(f"  [it{it}] recoloured -> 8 mk={mk}"); continue
            last_act = 1; obs = step(env, A[1]); continue   # rise vbar tip into station-8

        if phase == "settle":
            # flood resolves under ACTION5 (no piece moves); then pull DOWN to
            # separate from the station so the region re-acquires cleanly.
            if reg is None:
                last_act = 2; obs = step(env, A[2]); continue
            if reg["bbox"][0] < 7:                          # frame top still in station band
                last_act = 2; obs = step(env, A[2]); continue
            phase = "plan"; continue

        if phase == "plan":
            if reg is None:
                obs = step(env, A[last_act]); continue
            st = parse_state(reg)
            plan = bfs_plan(st, goal, W, H, ob, valid=lambda s: s[1] >= 7) or []
            if verbose:
                print(f"  [it{it}] place plan from {st} len={len(plan)}")
            if not plan:
                # already placed?
                if all(t in reg["cells"] for t in tgt8):
                    phase = "done"; continue
                # nudge and re-plan
                last_act = 2; obs = step(env, A[2]); continue
            phase = "exec"; continue

        if phase == "exec":
            if reg is None:
                obs = step(env, A[last_act]); continue
            if all(t in reg["cells"] for t in tgt8):
                print(f"  [it{it}] COLOUR-7 PLACED bbox={reg['bbox']} covers {tgt8}")
                phase = "done"; break
            if not plan:
                phase = "plan"; continue
            a = plan.pop(0)
            last_act = a
            obs = step(env, A[a]); continue

        if phase == "done":
            break
    else:
        g = canonical_layer(obs)
        mk2 = marker(g) or (0, 0)
        r = region_at(g, mk2, sboxes)
        print(f"  colour-7 leg UNFINISHED phase={phase} state={parse_state(r) if r else None}")
    return obs, phase == "done"


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    s = 0
    while s < 4000 and int(getattr(obs, "levels_completed", 0) or 0) < 6 and not ad.is_done([], obs):
        obs = step(env, ad.choose_action([], obs)); s += 1
    run(env, obs, ad)


if __name__ == "__main__":
    main()
