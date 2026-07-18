"""re86 L7 cross-leg probe (R66): verify the bar-shift signs for a CROSS movable
on L7, reusing the proven cycle-index + occlusion-safe drive discipline. Drive
colour-10 to below the obstacle, col-overlap it, push UP, and measure hrel — is
up-push hrel+3 (as the L6 down-push symmetry predicts)? Also measure a LEFT push
vbar shift. dir 1=up 2=down 3=left 4=right.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _station_boxes, _target_boxes, _l6_obstacle_box, _l6_cross_state
from admorphiq.adapters25.base import canonical_layer
# reuse the proven helpers from the outline controller
from re86_l7_ctrl import marker, l7_regions, region_at  # type: ignore

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


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
    ob = _l6_obstacle_box(g)
    regs = l7_regions(g, sboxes)
    spawn_cen = {m["color"]: m["cen"] for m in regs}
    print(f"L7 obstacle={ob} spawn={ {c: v for c, v in spawn_cen.items()} }")

    def nearest_spawn(mk):
        return min(spawn_cen, key=lambda k: abs(spawn_cen[k][0] - mk[0]) + abs(spawn_cen[k][1] - mk[1]))
    idx_color = []
    for _k in range(3):
        idx_color.append(nearest_spawn(marker(canonical_layer(obs))))
        obs = step(env, A[5])
    sel = 0
    print(f"idx_color={idx_color}")

    CROSS = 10
    obr = (ob[0] + ob[2]) // 2
    obc = (ob[1] + ob[3]) // 2
    last_act = 2
    # Phase A: bring colour-10 BELOW the obstacle and col-overlapping it, then push
    # UP and log hrel/vrel. Route: drive down to rows > ob bottom, col-align to obc.
    phase = "approach"
    logged = []
    for it in range(200):
        g = canonical_layer(obs)
        mk = marker(g)
        if mk is None:
            obs = step(env, A[last_act]); continue
        if idx_color[sel] != CROSS:
            obs = step(env, A[5]); sel = (sel + 1) % 3; continue
        reg = region_at(g, mk, sboxes)
        if reg is None:
            obs = step(env, A[last_act]); continue
        st = _l6_cross_state(reg["cells"])
        if phase == "approach":
            # want the frame BELOW the obstacle (r0 > ob[2]) and col-overlapping
            if st["c0"] > obc - 2:
                last_act = 3; obs = step(env, A[3]); continue   # move left to col-align
            if st["c1"] < obc + 2:
                last_act = 4; obs = step(env, A[4]); continue
            if st["r0"] <= ob[2] + 1:
                last_act = 2; obs = step(env, A[2]); continue   # move down below obstacle
            phase = "pushup"
            print(f"  approach done: state r0={st['r0']} c0={st['c0']} vrel={st['vrel']} hrel={st['hrel']}")
            continue
        if phase == "pushup":
            logged.append((st["r0"], st["c0"], st["vrel"], st["hrel"]))
            if len(logged) >= 8:
                break
            last_act = 1; obs = step(env, A[1]); continue  # push UP into obstacle
    print("  pushup log (r0,c0,vrel,hrel):")
    for row in logged:
        print("   ", row)


if __name__ == "__main__":
    main()
