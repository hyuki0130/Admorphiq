"""Open-loop idx6 clear: seed fruit+enemy model once, run the merge/deliver
choreography on the SIM model (advancing sim_click_downgrade), execute each
click LIVE. The sim's exact multiset gives precise fruit tracking (the frame-
only reactive version failed on goal dropout + tracking noise). Goal targets
from the level-start anchors (col,row). Verifies live clear.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from admorphiq.adapters25 import su15  # noqa: E402
from admorphiq.adapters25.base import reset_action, click_action  # noqa: E402
from su15_dg_sim import sim_click_downgrade  # noqa: E402

_VAL_BY_COLOR = {c: v for v, c in enumerate(su15._VAL_COLORS)}
R = su15._VACUUM_RADIUS
SZ = su15._SIZE


def snap(game):
    fr = []
    for f in game.lkujttxgs:
        px = f.pixels
        c = int(px[px >= 0].max()) if (px is not None and (px >= 0).any()) else -1
        fr.append([int(f.x), int(f.y), _VAL_BY_COLOR.get(c, -1)])
    en = [[int(e.x), int(e.y), game.yghzqxumz.get(e, 0)] for e in game.fezhhzhih]
    return fr, en


def goals_xy(game):
    out = []
    for s in game.powykypsm:
        h, w = s.pixels.shape
        out.append((int(s.x) + w // 2, int(s.y) + h // 2))  # (col,row) center
    return out


def center(f):
    s = SZ[f[2]]
    return (f[0] + s // 2, f[1] + s // 2)


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def in_goal(f, g, m=5):
    c = center(f)
    return abs(c[0] - g[0]) <= m and abs(c[1] - g[1]) <= m


def deliver_click(f, g):
    c = center(f)
    dx, dy = g[0] - c[0], g[1] - c[1]
    d = (dx * dx + dy * dy) ** 0.5 or 1.0
    sz = SZ[f[2]]
    lead = max(1.0, min(d, R - sz / 2.0 - 0.5))
    return (c[0] + dx / d * lead, c[1] + dy / d * lead)


def _lure_corner_away(e, fruits, avoid, R):
    """Lure enemy e toward the bottom corner farthest from all fruits AND from the
    goals (avoid), so vacuuming it there does not grab a fruit nor push it at a goal."""
    ec = (e[0] + su15._ENEMY_W // 2, e[1] + su15._ENEMY_H // 2)
    corners = [(2, 60), (61, 60), (2, 52), (61, 52), (32, 61)]
    corner = max(corners, key=lambda c: min([dist(c, center(f)) for f in fruits] + [dist(c, a) for a in avoid]))
    dx, dy = corner[0] - ec[0], corner[1] - ec[1]
    dd = (dx * dx + dy * dy) ** 0.5 or 1.0
    return (ec[0] + dx / dd * R, ec[1] + dy / dd * R)


def choreograph2(fruits, enemies, g1, g2, lure, phase):
    """Two-phase plan. Returns (click, why, new_phase).

    Phase 1 (cascade): merge the four value-1s -> one value-3 and deliver it to g1,
    while LURING any enemy that comes within `lure` of ANY fruit (keeps the value-5
    intact as bait AND protects the cascade). Transition to phase 2 once a value-3
    sits in g1.
    Phase 2 (chain): the cascade-3 is safe in g1 (enemies are bottom). Release the
    enemies onto the value-5 (neutral bottom clicks let them chase+downgrade it);
    deliver the chain value-3 to g2 the instant it forms -> win. Protect g1 by
    luring any enemy that drifts toward it."""
    threes = [f for f in fruits if f[2] == 3]
    cascade = [f for f in fruits if 1 <= f[2] <= 2]
    chain = [f for f in fruits if f[2] >= 4]
    in_g1 = [f for f in threes if in_goal(f, g1)]
    in_g2 = [f for f in threes if in_goal(f, g2)]

    if phase == 1:
        if in_g1:
            return None, "P1 done", 2  # a three sits in g1 -> phase 2 (deliver the chain three)
        # cascade three ready but not yet in g1 -> deliver the one NEAREST g1 (the
        # cascade three, formed top; never the bottom chain three)
        undelivered3 = [f for f in threes]
        if undelivered3:
            f = min(undelivered3, key=lambda f: dist(center(f), g1))
            return deliver_click(f, g1), "P1 deliver->g1", 1
        # protect EVERYTHING (value-5 stays intact as bait): lure a threatening enemy
        for e in enemies:
            if e[2] > 0:
                continue
            ec = (e[0] + su15._ENEMY_W // 2, e[1] + su15._ENEMY_H // 2)
            if fruits and min(dist(ec, center(f)) for f in fruits) < lure:
                return _lure_corner_away(e, fruits, [g1, g2], R), "P1 lure", 1
        # merge the lowest cascade pair
        if len(cascade) >= 2:
            by = {}
            for f in cascade:
                by.setdefault(f[2], []).append(f)
            pv = sorted(v for v, fs in by.items() if len(fs) >= 2)
            if pv:
                grp = by[pv[0]]
                a, b = min(((grp[i], grp[j]) for i in range(len(grp)) for j in range(i + 1, len(grp))),
                           key=lambda p: dist(center(p[0]), center(p[1])))
                ca, cb = center(a), center(b)
                d = dist(ca, cb)
                if d <= su15._MERGE_DIST:
                    return ((ca[0] + cb[0]) / 2.0, (ca[1] + cb[1]) / 2.0), "P1 merge", 1
                ux, uy = (cb[0] - ca[0]) / d, (cb[1] - ca[1]) / d
                return (ca[0] + ux * 7.0, ca[1] + uy * 7.0), "P1 gather", 1
        return (32, 61), "P1 idle", 1

    # phase 2
    # protect the cascade-3 in g1: if an enemy is near g1, lure it away
    for e in enemies:
        if e[2] > 0:
            continue
        ec = (e[0] + su15._ENEMY_W // 2, e[1] + su15._ENEMY_H // 2)
        if dist(ec, g1) < lure + 4:
            return _lure_corner_away(e, fruits, [g1, g2], R), "P2 protect-g1", 2
    # deliver the chain three the instant it exists
    undelivered_chain3 = [f for f in threes if not in_goal(f, g2) and not in_goal(f, g1)]
    if undelivered_chain3:
        f = min(undelivered_chain3, key=lambda f: dist(center(f), g2))
        return deliver_click(f, g2), "P2 deliver->g2", 2
    # let the enemies chase+downgrade the value-5: neutral bottom click near it
    if chain:
        f5 = chain[0]
        return (center(f5)[0], 61), "P2 downgrade-v5", 2
    return (32, 61), "P2 idle", 2


def choreograph(fruits, enemies, g1, g2, lure):
    threes = [f for f in fruits if f[2] == 3]
    cascade = [f for f in fruits if 1 <= f[2] <= 2]   # protect these
    chain = [f for f in fruits if f[2] >= 4]           # WANT the enemy to downgrade this
    in_g1 = [f for f in threes if in_goal(f, g1)]
    in_g2 = [f for f in threes if in_goal(f, g2)]
    undelivered = [f for f in threes if not in_goal(f, g1) and not in_goal(f, g2)]

    # 1) deliver any value-3 the moment it exists (removes it from enemy reach; the
    #    chain three -> nearest goal, cascade three -> the other). Deliver the fruit
    #    NEAREST its target goal first (shorter haul lands before a 3rd downgrade).
    if undelivered:
        def target_for(f):
            # if a three already sits in a goal, the new one goes to the OTHER goal
            if in_g1 and not in_g2:
                return g2
            if in_g2 and not in_g1:
                return g1
            return g1 if dist(center(f), g1) <= dist(center(f), g2) else g2
        f = min(undelivered, key=lambda f: dist(center(f), target_for(f)))
        return deliver_click(f, target_for(f)), "deliver3"

    # 2) protect cascade fruits: lure ONLY an enemy whose NEAREST fruit is a cascade
    #    fruit (value<=2) within `lure` — never lure the enemy assigned to the chain.
    all_targets = cascade + threes + chain
    for e in enemies:
        if e[2] > 0 or not all_targets:
            continue
        ec = (e[0] + su15._ENEMY_W // 2, e[1] + su15._ENEMY_H // 2)
        nearest = min(all_targets, key=lambda f: dist(ec, center(f)))
        if nearest[2] <= 2 and dist(ec, center(nearest)) < lure:
            corners = [(2, 12), (61, 12), (2, 60), (61, 60)]
            corner = max(corners, key=lambda c: min(dist(c, center(f)) for f in fruits))
            dx, dy = corner[0] - ec[0], corner[1] - ec[1]
            dd = (dx * dx + dy * dy) ** 0.5 or 1.0
            return (ec[0] + dx / dd * R, ec[1] + dy / dd * R), "lure"

    # 3) merge the cascade (lowest value with a pair)
    if len(cascade) >= 2:
        by = {}
        for f in cascade:
            by.setdefault(f[2], []).append(f)
        pv = sorted(v for v, fs in by.items() if len(fs) >= 2)
        if pv:
            grp = by[pv[0]]
            a, b = min(((grp[i], grp[j]) for i in range(len(grp)) for j in range(i + 1, len(grp))),
                       key=lambda p: dist(center(p[0]), center(p[1])))
            ca, cb = center(a), center(b)
            d = dist(ca, cb)
            if d <= su15._MERGE_DIST:
                return ((ca[0] + cb[0]) / 2.0, (ca[1] + cb[1]) / 2.0), "merge"
            ux, uy = (cb[0] - ca[0]) / d, (cb[1] - ca[1]) / d
            return (ca[0] + ux * 7.0, ca[1] + uy * 7.0), "gather"
    return (32, 11), "idle"


def run(arcade, lure, verbose, execute):
    env = arcade.make("su15")
    env.step(reset_action())
    game = env._game
    game.set_level(6)
    fruits, enemies = snap(game)
    gs = goals_xy(game)
    g1 = min(gs, key=lambda g: g[1])
    g2 = max(gs, key=lambda g: g[1])
    model = [f[:] for f in fruits]
    emodel = [[e[0], e[1], 0] for e in enemies]
    phase = 1
    for k in range(60):
        if execute and game.level_index != 6:
            print(f"*** CLEARED at click {k} (lure={lure}) ***")
            return True
        threes_delivered = sum(1 for f in model if f[2] == 3 and (in_goal(f, g1) or in_goal(f, g2)))
        if not execute and threes_delivered >= 2:
            print(f"SIM win at click {k} (lure={lure})")
            return True
        if not model:
            break
        click, why, phase = choreograph2(model, emodel, g1, g2, lure, phase)
        if click is None:  # phase transition, re-plan same click
            click, why, phase = choreograph2(model, emodel, g1, g2, lure, phase)
        cx = max(0, min(63, int(round(click[0]))))
        cy = max(10, min(62, int(round(click[1]))))
        model, emodel = sim_click_downgrade(model, emodel, cx, cy)
        if execute:
            a = click_action(x=cx, y=cy)
            env.step(a, data=a.action_data.model_dump())
        if verbose:
            vals = sorted(f[2] for f in model)
            print(f"[{k:02d}] ({cx},{cy}) {why:9s} simVals={vals} deliv={threes_delivered}")
    ok = execute and game.level_index != 6
    if not execute:
        d = sum(1 for f in model if f[2] == 3 and (in_goal(f, g1) or in_goal(f, g2)))
        print(f"SIM did NOT reach win (lure={lure}, delivered {d}/2, final={sorted(f[2] for f in model)})")
    else:
        print(f"{'CLEARED' if ok else 'did NOT clear'} live (lure={lure})")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lure", type=float, default=10.0)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    args = ap.parse_args()
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    if args.sweep:
        for lure in [0.0, 8.0, 10.0, 12.0, 16.0, 20.0]:
            run(arcade, lure, False, False)
        return
    run(arcade, args.lure, args.verbose, args.live)


if __name__ == "__main__":
    main()
