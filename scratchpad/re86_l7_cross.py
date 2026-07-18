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
    TGT = 11
    tby = {}
    for r, c in _target_boxes(g):
        tby.setdefault(g[r][c], []).append((r, c))
    tgt = sorted(tby[TGT])                 # [(30,45),(48,39),(48,51)]
    hbar_row = max(set(r for r, _c in tgt), key=lambda r: sum(1 for rr, _c in tgt if rr == r))
    vbar_col = next(c for r, c in tgt if r != hbar_row)   # 45
    top_row = min(r for r, _c in tgt)      # 30
    # frame: 19 tall/wide. vbar natural frame-rel col 9 -> c0 = vbar_col-9. hbar at
    # abs hbar_row = bottom (frame-rel 18) -> hrel_t=18; r0 = hbar_row-18.
    c0_t = vbar_col - 9
    r0_t = hbar_row - 18
    hrel_t = 18
    print(f"  cross->{TGT}: hbar_row={hbar_row} vbar_col={vbar_col} -> r0_t={r0_t} c0_t={c0_t} hrel_t={hrel_t}")
    obc = (ob[1] + ob[3]) // 2
    scen11 = stations[TGT]
    last_act = 2
    phase = "recolour"
    for it in range(500):
        g = canonical_layer(obs)
        mk = marker(g)
        if mk is None:
            obs = step(env, A[last_act]); continue
        if idx_color[sel] != CROSS:
            obs = step(env, A[5]); sel = (sel + 1) % 3; continue
        reg = region_at(g, mk, sboxes)
        cur_color = reg["color"] if reg else None

        if phase == "recolour":
            if cur_color == TGT:
                phase = "sethrel"; print(f"  [it{it}] recoloured -> {TGT}"); continue
            # Rise to a CLEAR ZONE above the obstacle (centre row <= ob[0]-11 so
            # the 19-tall body clears the obstacle rows), THEN horizontal-align to
            # the station column, THEN up into it. Aligning lower would col-collide
            # the obstacle (bar-shift) or, in the bottom cluster, occlude the marker.
            clear = ob[0] - 11
            if abs(mk[1] - scen11[1]) > 2:
                want = (-1, 0) if mk[0] > clear else (0, 1 if mk[1] < scen11[1] else -1)
            else:
                want = (-1, 0)
            act = {(-1, 0): 1, (1, 0): 2, (0, -1): 3, (0, 1): 4}[want]
            last_act = act; obs = step(env, A[act]); continue

        if reg is None:
            # recoloured piece abuts its top station -> parse-merged/occluded; pull
            # DOWN off the station until the region re-acquires.
            if phase in ("sethrel",) and it % 20 == 0:
                print(f"  it{it} {phase} reg=None mk={mk} regs={[(m['color'],m['bbox']) for m in l7_regions(g,sboxes)]}")
            last_act = 2; obs = step(env, A[2]); continue
        st = _l6_cross_state(reg["cells"])
        if phase == "sethrel" and it % 15 == 0:
            print(f"  it{it} sethrel st r0={st['r0']} c0={st['c0']} c1={st['c1']} vrel={st['vrel']} hrel={st['hrel']} mk={mk}")

        if phase == "sethrel":
            if st["hrel"] >= hrel_t:
                phase = "carry_right"; print(f"  [it{it}] hrel set = {st['hrel']} @r0={st['r0']} c0={st['c0']}"); continue
            # must col-overlap the obstacle and sit ABOVE it, then push DOWN.
            if not (st["c0"] <= ob[3] and st["c1"] >= ob[1]):
                act = 4 if (st["c0"] + st["c1"]) // 2 < obc else 3
                last_act = act; obs = step(env, A[act]); continue
            if st["r1"] >= ob[0] - 1 and st["hrel"] == 9:
                # need to be above so a down-push pins the hbar at the obstacle top
                last_act = 1; obs = step(env, A[1]); continue
            last_act = 2; obs = step(env, A[2]); continue  # push DOWN -> hrel+3

        if phase == "carry_right":
            # clear obstacle rows (up) then move right out of the obstacle columns
            if st["c0"] < ob[3] + 1 and st["r1"] >= ob[0] - 1:
                last_act = 1; obs = step(env, A[1]); continue  # rise clear of obstacle rows
            if st["c0"] < c0_t:
                last_act = 4; obs = step(env, A[4]); continue  # right, out of obstacle cols
            phase = "carry_place"; continue

        if phase == "carry_place":
            if all(t in reg["cells"] for t in tgt):
                print(f"  [it{it}] CROSS PLACED bbox={reg['bbox']} covers {tgt}"); break
            # at cols right of the obstacle -> free vertical + horizontal to r0_t,c0_t
            if st["c0"] != c0_t:
                act = 4 if st["c0"] < c0_t else 3
            elif st["r0"] != r0_t:
                act = 2 if st["r0"] < r0_t else 1
            else:
                act = 5
            last_act = act if act != 5 else last_act
            obs = step(env, A[act]); continue
    else:
        g = canonical_layer(obs)
        mk2 = marker(g) or (0, 0)
        r = region_at(g, mk2, sboxes)
        print(f"  cross leg UNFINISHED phase={phase} state={_l6_cross_state(r['cells']) if r else None}")


if __name__ == "__main__":
    main()
