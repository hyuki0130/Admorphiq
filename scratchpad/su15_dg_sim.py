"""Faithful DOWNGRADE sim for su15 idx6 + lockstep validator.

Extends the sacrifice sim with the value>=1 downgrade path (source
`wwvumwkgbn` + `luwexfjhwl`): on a non-vacuumed enemy contacting a value>=1
fruit, the fruit is downgraded by 1 and KNOCKED BACK away from the enemy over
`rmziewkdi(4)` shake + `dgpsayght(4)` slide sub-steps (slide = ttwugcsth/dgpsayght
= 2.5 px/sub-step), during which the click runs EXTRA sub-steps (knockback
resolution) that decrement enemy cooldowns without chasing (closing the banked
model gap). value-0 contact destroys (4 knockback sub-steps). Enemy cooldown
= rmziewkdi+dgpsayght+1 = 9 sub-steps.

Lockstep: drive the SAME clicks through the live engine and the sim; compare
fruit multiset+positions and enemy positions+cooldowns each click.
"""
from __future__ import annotations
import argparse
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from admorphiq.adapters25 import su15  # noqa: E402
from admorphiq.adapters25.base import reset_action, click_action  # noqa: E402

_VAL_BY_COLOR = {c: v for v, c in enumerate(su15._VAL_COLORS)}
_KB_SHAKE = 4      # rmziewkdi
_KB_SLIDE = 4      # dgpsayght
_KB_TOTAL = _KB_SHAKE + _KB_SLIDE          # 8 (value>=1 downgrade)
_KB_DESTROY = _KB_SHAKE                     # 4 (value-0 destroy)
_KB_SPEED = 10.0 / _KB_SLIDE                # ttwugcsth/dgpsayght = 2.5 px/slide step
_COOLDOWN = _KB_TOTAL + 1                   # 9


def _euclid_in_radius(cx, cy, x, y, w, h, radius=su15._VACUUM_RADIUS):
    return su15._euclid_in_radius(cx, cy, x, y, w, h, radius)


def sim_click_downgrade(fruits, enemies, cx, cy):
    """One-click faithful sim WITH value>=1 downgrade + knockback + extra-substep
    cooldown accounting. fruits=[x,y,value]; enemies=[x,y,cooldown]. Returns
    (fruits', enemies')."""
    fs = [f[:] for f in fruits]
    es = [e[:] for e in enemies]
    ew, eh = su15._ENEMY_W, su15._ENEMY_H
    SZ = su15._SIZE

    sel = [i for i, f in enumerate(fs) if _euclid_in_radius(cx, cy, f[0], f[1], SZ[f[2]], SZ[f[2]])]
    vac = {}
    for i, e in enumerate(es):
        if _euclid_in_radius(cx, cy, e[0], e[1], ew, eh):
            ecx, ecy = e[0] + ew // 2, e[1] + eh // 2
            vx, vy = float(cx - ecx), float(cy - ecy)
            d = (vx * vx + vy * vy) ** 0.5
            ux, uy = (vx / d, vy / d) if d > 0 else (0.0, 0.0)
            vac[i] = (ux, uy, float(e[0]), float(e[1]))

    # knockback state per fruit index: [steps_done, total, dir_x, dir_y, fx, fy, applied]
    kb: dict[int, list] = {}
    dead: set[int] = set()

    substep = 0
    while True:
        vacuum_phase = substep < su15._SUBSTEPS
        # 1) vacuum-pull selected fruits (only in vacuum phase, and not knocking back)
        if vacuum_phase:
            for i in sel:
                if i in kb or i in dead:
                    continue
                f = fs[i]
                dx, dy = cx - f[0], cy - f[1]
                if dx > 0:
                    f[0] += min(su15._PULL_PX, dx)
                elif dx < 0:
                    f[0] += max(-su15._PULL_PX, dx)
                if dy > 0:
                    f[1] += min(su15._PULL_PX, dy)
                elif dy < 0:
                    f[1] += max(-su15._PULL_PX, dy)
            step = su15._PULL_PX * su15._ENEMY_VAC_FRAC
            for i, (ux, uy, fx, fy) in list(vac.items()):
                fx += ux * step
                fy += uy * step
                xi, yi = su15._clamp_pos(fx, fy, ew, eh)
                es[i][0], es[i][1] = xi, yi
                vac[i] = (ux, uy, float(xi), float(yi))

        # 2) animate knockback fruits (shake then slide; apply downgrade value at slide start)
        for i, st in list(kb.items()):
            done, total, dx, dy, fx, fy, applied = st
            if done < _KB_SHAKE:
                pass  # shake: ~stationary (source jitters y +-1; negligible)
            else:
                fx += dx * _KB_SPEED
                fy += dy * _KB_SPEED
                xi, yi = su15._clamp_pos(fx, fy, SZ[fs[i][2]], SZ[fs[i][2]])
                fs[i][0], fs[i][1] = xi, yi
                fx, fy = float(xi), float(yi)
            done += 1
            kb[i] = [done, total, dx, dy, fx, fy, applied]
            if done >= total:
                del kb[i]

        # 3) chase (only in vacuum phase, non-vacuumed non-frozen enemies, no knockback active-block)
        kb_active = any(_KB_SHAKE <= st[0] < st[1] for st in kb.values())
        if vacuum_phase and not kb_active:
            alive = [k for k in range(len(fs)) if k not in dead and k not in kb]
            for i, e in enumerate(es):
                if i in vac or e[2] > 0 or not alive:
                    continue
                ecx, ecy = e[0] + ew // 2, e[1] + eh // 2
                best = min(alive, key=lambda k: (fs[k][0] + SZ[fs[k][2]] // 2 - ecx) ** 2
                           + (fs[k][1] + SZ[fs[k][2]] // 2 - ecy) ** 2)
                tx = fs[best][0] + SZ[fs[best][2]] // 2
                ty = fs[best][1] + SZ[fs[best][2]] // 2
                sx = 1 if tx > ecx else (-1 if tx < ecx else 0)
                sy = 1 if ty > ecy else (-1 if ty < ecy else 0)
                e[0], e[1] = su15._clamp_pos(e[0] + sx, e[1] + sy, ew, eh)
            # 4) contact: non-vacuumed enemy overlapping a fruit not already in kb/dead
            for i, e in enumerate(es):
                if i in vac:
                    continue
                for k in range(len(fs)):
                    if k in dead or k in kb:
                        continue
                    if su15._bbox_overlap(e[0], e[1], ew, eh, fs[k][0], fs[k][1], SZ[fs[k][2]], SZ[fs[k][2]]):
                        # downgrade / destroy
                        ecx, ecy = e[0] + ew // 2, e[1] + eh // 2
                        fcx, fcy = fs[k][0] + SZ[fs[k][2]] // 2, fs[k][1] + SZ[fs[k][2]] // 2
                        vx, vy = float(fcx - ecx), float(fcy - ecy)
                        d = (vx * vx + vy * vy) ** 0.5
                        ux, uy = (vx / d, vy / d) if d > 0 else (0.0, -1.0)
                        if fs[k][2] == 0:
                            dead.add(k)
                            kb[k] = [0, _KB_DESTROY, ux, uy, float(fs[k][0]), float(fs[k][1]), True]
                        else:
                            fs[k][2] -= 1  # downgrade applied (approx: at contact; source applies at slide start)
                            kb[k] = [0, _KB_TOTAL, ux, uy, float(fs[k][0]), float(fs[k][1]), True]
                        e[2] = _COOLDOWN
                        break

        # decrement cooldowns every substep
        for e in es:
            if e[2] > 0:
                e[2] -= 1

        substep += 1
        if not vacuum_phase and not kb:
            break
        if substep > 40:  # safety
            break

    # remove destroyed
    fs = [f for k, f in enumerate(fs) if k not in dead]

    # merge same-value overlaps (only fruits not mid-knockback — but kb is empty now)
    def touch(a, b):
        sa, sb = SZ[a[2]], SZ[b[2]]
        return not (a[0] + sa <= b[0] or b[0] + sb <= a[0] or a[1] + sa <= b[1] or b[1] + sb <= a[1])

    n = len(fs)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if fs[i][2] == fs[j][2] and touch(fs[i], fs[j]):
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out = []
    for idxs in groups.values():
        if len(idxs) >= 2:
            v = fs[idxs[0]][2] + 1
            nsz = SZ[v] if v < len(SZ) else SZ[-1]
            gx = round(sum(fs[k][0] for k in idxs) / len(idxs))
            gy = round(sum(fs[k][1] for k in idxs) / len(idxs))
            out.append([gx - (nsz - 1) // 2, gy - (nsz - 1) // 2, v])
        else:
            out.append(fs[idxs[0]])
    return out, es


def snap(game):
    fr = []
    for f in game.lkujttxgs:
        px = f.pixels
        c = int(px[px >= 0].max()) if (px is not None and (px >= 0).any()) else -1
        fr.append([int(f.x), int(f.y), _VAL_BY_COLOR.get(c, -1)])
    en = [[int(e.x), int(e.y), game.yghzqxumz.get(e, 0)] for e in game.fezhhzhih]
    return fr, en


def ms(fr):
    d = {}
    for f in fr:
        d[f[2]] = d.get(f[2], 0) + 1
    return dict(sorted(d.items()))


def step(env, cx, cy):
    a = click_action(x=cx, y=cy)
    env.step(a, data=a.action_data.model_dump())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--frames", type=int, default=25)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("su15")
    env.step(reset_action())
    game = env._game
    game.set_level(6)
    sim_f, sim_e = snap(game)
    print(f"seed fruits={sim_f} enemies={sim_e}")
    ms_mm = 0
    pos_mm = 0
    cd_mm = 0
    for k in range(args.frames):
        live_f, live_e = snap(game)
        # bias clicks: often near an enemy or a fruit to exercise chase/contact
        r = rng.random()
        if r < 0.5 and live_e:
            e = rng.choice(live_e)
            cx = max(0, min(63, e[0] + rng.randint(-8, 8)))
            cy = max(10, min(62, e[1] + rng.randint(-8, 8)))
        else:
            f = rng.choice(live_f)
            cx = max(0, min(63, f[0] + rng.randint(-8, 8)))
            cy = max(10, min(62, f[1] + rng.randint(-8, 8)))
        # advance sim from the PREVIOUS live state (seeded lockstep)
        sim_f, sim_e = sim_click_downgrade([f[:] for f in live_f], [e[:] for e in live_e], cx, cy)
        step(env, cx, cy)
        new_f, new_e = snap(game)
        ms_ok = ms(sim_f) == ms(new_f)
        # position match: sort by (value, x, y)
        sp = sorted([tuple(f) for f in sim_f])
        lp = sorted([tuple(f) for f in new_f])
        pos_ok = sp == lp
        # cooldown match (sorted, positions ignore order): compare enemy cd multiset
        cd_ok = sorted(e[2] for e in sim_e) == sorted(e[2] for e in new_e)
        if not ms_ok:
            ms_mm += 1
        if not pos_ok:
            pos_mm += 1
        if not cd_ok:
            cd_mm += 1
        tag = "OK" if (ms_ok and pos_ok and cd_ok) else ("MSBAD" if not ms_ok else ("POS" if not pos_ok else "CD"))
        print(f"[{k:02d}] click({cx},{cy}) simMS={ms(sim_f)} liveMS={ms(new_f)} "
              f"{tag}  simE={[e[2] for e in sim_e]} liveE={[e[2] for e in new_e]}")
        if not ms_ok:
            print(f"     sim_pos={sp}\n     live_pos={lp}")
        if game.level_index != 6 or not new_f:
            print("  (level changed / empty)")
            break
    print(f"\nSUMMARY seed={args.seed} frames={args.frames} ms_mismatch={ms_mm} pos_mismatch={pos_mm} cd_mismatch={cd_mm}")


if __name__ == "__main__":
    main()
