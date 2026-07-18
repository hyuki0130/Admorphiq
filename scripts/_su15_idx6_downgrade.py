"""Verification-only dev-probe (KEPT, non-regressing) for su15 idx6 (level index
6) — the CONSTRUCTIVE-DOWNGRADE mechanic. Banks the validated infra for the next
attempt. Nothing here runs in the shipped adapter (floor 6/9 untouched); it reads
engine internals (``env._game``) ONLY for ground-truth validation, the established
repo pattern (see ``scripts/_su15_enemy_sim.py``).

Contains:
  * :func:`sim_click_downgrade` — a FAITHFUL one-click sim that adds the value>=1
    DOWNGRADE path (source ``wwvumwkgbn`` + ``luwexfjhwl``) on top of the sacrifice
    sim: a non-vacuumed enemy contacting a value>=1 fruit downgrades it by 1 and
    KNOCKS IT BACK away from the enemy over rmziewkdi(4) shake + dgpsayght(4) slide
    sub-steps (slide = ttwugcsth/dgpsayght = 2.5 px/step), and the click runs EXTRA
    sub-steps until the knockback resolves — decrementing enemy cooldowns WITHOUT
    chasing (this closes the banked "destroy/knockback extends the click" model gap:
    a value>=1 downgrade ends the enemy cd at ~1, a value-0 destroy at ~5, matching
    live). Enemy cooldown = rmziewkdi+dgpsayght+1 = 9.
  * ``--val-dg`` — lockstep the sim vs the live engine at idx6 over random
    contact-biased clicks (MEASURED: fruit MULTISET 0 mismatches / 75 frames across
    3 seeds; positions/cooldowns drift ~1 sub-step, same order the sacrifice sim's
    margin-robustness absorbed).
  * ``--live`` — the DECISIVE winnability driver: a closed-loop choreography that
    reads live state each click (an ORACLE, not frame-only) and CLEARS idx6 in 8
    clicks (deterministic). Proves idx6 IS winnable; see SU15.md for why a robust
    FRAME-ONLY / open-loop port does not close in a bounded pass (delivered fruit is
    re-downgraded, so both value-3s must land near-simultaneously — a knife-edge the
    sim drift + goal-detection dropout both break).

Usage: uv run python scripts/_su15_idx6_downgrade.py --val-dg --seeds 3
       uv run python scripts/_su15_idx6_downgrade.py --live
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
from admorphiq.adapters25.base import click_action, reset_action  # noqa: E402

_VAL_BY_COLOR = {c: v for v, c in enumerate(su15._VAL_COLORS)}
_KB_SHAKE = 4                      # rmziewkdi (shake sub-steps)
_KB_SLIDE = 4                      # dgpsayght (knockback slide sub-steps)
_KB_TOTAL = _KB_SHAKE + _KB_SLIDE  # 8 — value>=1 downgrade
_KB_DESTROY = _KB_SHAKE            # 4 — value-0 destroy
_KB_SPEED = 10.0 / _KB_SLIDE       # ttwugcsth/dgpsayght = 2.5 px/slide step
_COOLDOWN = _KB_TOTAL + 1          # 9
_IDX = 6
R = su15._VACUUM_RADIUS
SZ = su15._SIZE
EW, EH = su15._ENEMY_W, su15._ENEMY_H


# ── faithful downgrade sim ──────────────────────────────────────────────────


def sim_click_downgrade(
    fruits: list[list[int]], enemies: list[list[int]], cx: int, cy: int
) -> tuple[list[list[int]], list[list[int]]]:
    """One-click faithful sim WITH the value>=1 downgrade + knockback + extra-
    sub-step cooldown accounting. ``fruits`` = ``[x, y, value]``; ``enemies`` =
    ``[x, y, cooldown]``. Returns ``(fruits', enemies')``."""
    fs = [f[:] for f in fruits]
    es = [e[:] for e in enemies]

    sel = [i for i, f in enumerate(fs) if su15._euclid_in_radius(cx, cy, f[0], f[1], SZ[f[2]], SZ[f[2]])]
    vac: dict[int, tuple[float, float, float, float]] = {}
    for i, e in enumerate(es):
        if su15._euclid_in_radius(cx, cy, e[0], e[1], EW, EH):
            ecx, ecy = e[0] + EW // 2, e[1] + EH // 2
            vx, vy = float(cx - ecx), float(cy - ecy)
            d = (vx * vx + vy * vy) ** 0.5
            ux, uy = (vx / d, vy / d) if d > 0 else (0.0, 0.0)
            vac[i] = (ux, uy, float(e[0]), float(e[1]))

    kb: dict[int, list] = {}  # fruit index -> [steps_done, total, dir_x, dir_y, fx, fy]
    dead: set[int] = set()
    substep = 0
    while True:
        vacuum_phase = substep < su15._SUBSTEPS
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
                xi, yi = su15._clamp_pos(fx, fy, EW, EH)
                es[i][0], es[i][1] = xi, yi
                vac[i] = (ux, uy, float(xi), float(yi))

        for i, st in list(kb.items()):
            done, total, dx, dy, fx, fy = st
            if done >= _KB_SHAKE:  # slide phase moves the fruit away from the enemy
                fx += dx * _KB_SPEED
                fy += dy * _KB_SPEED
                xi, yi = su15._clamp_pos(fx, fy, SZ[fs[i][2]], SZ[fs[i][2]])
                fs[i][0], fs[i][1] = xi, yi
                fx, fy = float(xi), float(yi)
            kb[i] = [done + 1, total, dx, dy, fx, fy]
            if done + 1 >= total:
                del kb[i]

        kb_sliding = any(_KB_SHAKE <= st[0] < st[1] for st in kb.values())
        if vacuum_phase and not kb_sliding:
            alive = [k for k in range(len(fs)) if k not in dead and k not in kb]
            for i, e in enumerate(es):
                if i in vac or e[2] > 0 or not alive:
                    continue
                ecx, ecy = e[0] + EW // 2, e[1] + EH // 2
                best = min(alive, key=lambda k: (fs[k][0] + SZ[fs[k][2]] // 2 - ecx) ** 2
                           + (fs[k][1] + SZ[fs[k][2]] // 2 - ecy) ** 2)
                tx = fs[best][0] + SZ[fs[best][2]] // 2
                ty = fs[best][1] + SZ[fs[best][2]] // 2
                sx = 1 if tx > ecx else (-1 if tx < ecx else 0)
                sy = 1 if ty > ecy else (-1 if ty < ecy else 0)
                e[0], e[1] = su15._clamp_pos(e[0] + sx, e[1] + sy, EW, EH)
            for i, e in enumerate(es):
                if i in vac:
                    continue
                for k in range(len(fs)):
                    if k in dead or k in kb:
                        continue
                    if su15._bbox_overlap(e[0], e[1], EW, EH, fs[k][0], fs[k][1], SZ[fs[k][2]], SZ[fs[k][2]]):
                        ecx, ecy = e[0] + EW // 2, e[1] + EH // 2
                        fcx, fcy = fs[k][0] + SZ[fs[k][2]] // 2, fs[k][1] + SZ[fs[k][2]] // 2
                        vx, vy = float(fcx - ecx), float(fcy - ecy)
                        d = (vx * vx + vy * vy) ** 0.5
                        ux, uy = (vx / d, vy / d) if d > 0 else (0.0, -1.0)
                        if fs[k][2] == 0:
                            dead.add(k)
                            kb[k] = [0, _KB_DESTROY, ux, uy, float(fs[k][0]), float(fs[k][1])]
                        else:
                            fs[k][2] -= 1  # downgrade
                            kb[k] = [0, _KB_TOTAL, ux, uy, float(fs[k][0]), float(fs[k][1])]
                        e[2] = _COOLDOWN
                        break

        for e in es:
            if e[2] > 0:
                e[2] -= 1

        substep += 1
        if not vacuum_phase and not kb:
            break
        if substep > 40:
            break

    fs = [f for k, f in enumerate(fs) if k not in dead]

    def touch(a: list[int], b: list[int]) -> bool:
        sa, sb = SZ[a[2]], SZ[b[2]]
        return not (a[0] + sa <= b[0] or b[0] + sb <= a[0] or a[1] + sa <= b[1] or b[1] + sb <= a[1])

    n = len(fs)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if fs[i][2] == fs[j][2] and touch(fs[i], fs[j]):
                parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out: list[list[int]] = []
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


# ── live helpers (ground truth) ─────────────────────────────────────────────


def _snap(game) -> tuple[list[list[int]], list[list[int]]]:
    fr = []
    for f in game.lkujttxgs:
        px = f.pixels
        c = int(px[px >= 0].max()) if (px is not None and (px >= 0).any()) else -1
        fr.append([int(f.x), int(f.y), _VAL_BY_COLOR.get(c, -1)])
    en = [[int(e.x), int(e.y), game.yghzqxumz.get(e, 0)] for e in game.fezhhzhih]
    return fr, en


def _goals_xy(game) -> list[tuple[int, int]]:
    out = []
    for s in game.powykypsm:
        h, w = s.pixels.shape
        out.append((int(s.x) + w // 2, int(s.y) + h // 2))
    return out


def _ms(fr):
    d: dict[int, int] = {}
    for f in fr:
        d[f[2]] = d.get(f[2], 0) + 1
    return dict(sorted(d.items()))


def _step(env, cx, cy):
    a = click_action(x=max(0, min(63, int(round(cx)))), y=max(10, min(62, int(round(cy)))))
    return env.step(a, data=a.action_data.model_dump())


def _make(arcade):
    env = arcade.make("su15")
    env.step(reset_action())
    game = env._game
    game.set_level(_IDX)
    return env, game


# ── lockstep validator ──────────────────────────────────────────────────────


def validate(arcade, n_frames: int, seed: int) -> tuple[int, int, int]:
    rng = random.Random(seed)
    env, game = _make(arcade)
    lf, le = _snap(game)
    ms_mm = pos_mm = cd_mm = 0
    for _k in range(n_frames):
        if rng.random() < 0.5 and le:
            e = rng.choice(le)
            cx = max(0, min(63, e[0] + rng.randint(-8, 8)))
            cy = max(10, min(62, e[1] + rng.randint(-8, 8)))
        else:
            f = rng.choice(lf)
            cx = max(0, min(63, f[0] + rng.randint(-8, 8)))
            cy = max(10, min(62, f[1] + rng.randint(-8, 8)))
        sim_f, sim_e = sim_click_downgrade([f[:] for f in lf], [e[:] for e in le], cx, cy)
        _step(env, cx, cy)
        lf, le = _snap(game)
        ms_mm += _ms(sim_f) != _ms(lf)
        pos_mm += sorted(tuple(f) for f in sim_f) != sorted(tuple(f) for f in lf)
        cd_mm += sorted(e[2] for e in sim_e) != sorted(e[2] for e in le)
        if game.level_index != _IDX or not lf:
            break
    print(f"seed={seed} frames={n_frames} MULTISET_mismatch={ms_mm} pos_mismatch={pos_mm} cd_mismatch={cd_mm}")
    return ms_mm, pos_mm, cd_mm


# ── closed-loop live winnability driver (ORACLE) ─────────────────────────────


def _center(f):
    s = SZ[f[2]]
    return (f[0] + s // 2, f[1] + s // 2)


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def run_live(arcade, max_clicks: int, verbose: bool) -> bool:
    """Closed-loop ORACLE: read live state each click, cascade the four value-1s,
    and deliver both value-3s (the cascade one + the enemy-downgraded value-5 one)
    to the two goals. Clears idx6 in 8 clicks — the winnability proof."""
    env, game = _make(arcade)
    gs = _goals_xy(game)
    g1 = min(gs, key=lambda g: g[1])
    g2 = max(gs, key=lambda g: g[1])

    def in_goal(f, g):
        c = _center(f)
        return abs(c[0] - g[0]) <= 5 and abs(c[1] - g[1]) <= 5

    for k in range(max_clicks):
        if game.level_index != _IDX:
            print(f"*** CLEARED idx6 at click {k} (winnable) ***")
            return True
        fr, _en = _snap(game)
        if not fr:
            break
        threes = [f for f in fr if f[2] == 3]
        cascade = [f for f in fr if 1 <= f[2] <= 2]
        in_g1 = [f for f in threes if in_goal(f, g1)]
        undelivered = [f for f in threes if not in_goal(f, g1) and not in_goal(f, g2)]
        click = None
        why = ""
        if undelivered:
            f = undelivered[0]
            tgt = g1 if not in_g1 else g2
            c = _center(f)
            dx, dy = tgt[0] - c[0], tgt[1] - c[1]
            d = (dx * dx + dy * dy) ** 0.5 or 1.0
            lead = max(1.0, min(d, R - SZ[f[2]] / 2.0 - 0.5))
            click, why = (c[0] + dx / d * lead, c[1] + dy / d * lead), "deliver3"
        elif len(cascade) >= 2:
            by: dict[int, list] = {}
            for f in cascade:
                by.setdefault(f[2], []).append(f)
            pv = sorted(v for v, fs in by.items() if len(fs) >= 2)
            if pv:
                grp = by[pv[0]]
                a, b = min(((grp[i], grp[j]) for i in range(len(grp)) for j in range(i + 1, len(grp))),
                           key=lambda p: _dist(_center(p[0]), _center(p[1])))
                ca, cb = _center(a), _center(b)
                d = _dist(ca, cb)
                if d <= su15._MERGE_DIST:
                    click, why = ((ca[0] + cb[0]) / 2.0, (ca[1] + cb[1]) / 2.0), "merge"
                else:
                    ux, uy = (cb[0] - ca[0]) / d, (cb[1] - ca[1]) / d
                    click, why = (ca[0] + ux * 7.0, ca[1] + uy * 7.0), "gather"
        if click is None:
            click, why = (32, 11), "idle"
        _step(env, *click)
        if verbose:
            f2, _ = _snap(game)
            print(f"[{k:02d}] {why:9s} vals={sorted(f[2] for f in f2)}")
    print(f"did NOT clear (final level_index={game.level_index})")
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-dg", dest="val_dg", action="store_true", help="lockstep sim vs live")
    ap.add_argument("--live", action="store_true", help="closed-loop winnability driver")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--frames", type=int, default=25)
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    if args.live:
        run_live(arcade, args.max, args.verbose)
        return
    if args.val_dg:
        tot = 0
        for s in range(args.seeds):
            ms, _p, _c = validate(arcade, args.frames, s)
            tot += ms
        print(f"\nTOTAL multiset mismatches across {args.seeds} seeds = {tot} (0 = faithful downgrade arithmetic)")
        return
    ap.print_help()


if __name__ == "__main__":
    main()
