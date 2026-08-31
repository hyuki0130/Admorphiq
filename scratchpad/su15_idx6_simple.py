"""Decisive test: the SIMPLE choreography that won LIVE (su15_idx6_live.py),
driven OPEN-LOOP on the faithful downgrade sim (seed once) and executed live.
No two-phase, no protect: deliver any value-3 to an empty goal, merge the
cascade, else neutral idle letting enemies downgrade the value-5 (knockback
drifts it up near the goals). Tests both SIM-win and LIVE clear.
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
from su15_idx6_openloop import snap, goals_xy, center, dist, in_goal, deliver_click  # noqa: E402

R = su15._VACUUM_RADIUS
SZ = su15._SIZE


def simple(fruits, enemies, g1, g2, idle_xy):
    threes = [f for f in fruits if f[2] == 3]
    cascade = [f for f in fruits if 1 <= f[2] <= 2]
    in_g1 = [f for f in threes if in_goal(f, g1)]
    in_g2 = [f for f in threes if in_goal(f, g2)]
    undelivered = [f for f in threes if not in_goal(f, g1) and not in_goal(f, g2)]
    if undelivered:
        f = undelivered[0]
        tgt = g1 if not in_g1 else g2
        return deliver_click(f, tgt), "deliver3"
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
    return idle_xy, "idle"


def run(arcade, idle_xy, execute, verbose):
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
    for k in range(60):
        if execute and game.level_index != 6:
            print(f"*** CLEARED live at click {k} (idle={idle_xy}) ***")
            return True
        d = sum(1 for f in model if f[2] == 3 and (in_goal(f, g1) or in_goal(f, g2)))
        if not execute and d >= 2:
            print(f"SIM win at click {k} (idle={idle_xy})")
            return True
        if not model:
            break
        click, why = simple(model, emodel, g1, g2, idle_xy)
        cx = max(0, min(63, int(round(click[0]))))
        cy = max(10, min(62, int(round(click[1]))))
        model, emodel = sim_click_downgrade(model, emodel, cx, cy)
        if execute:
            a = click_action(x=cx, y=cy)
            env.step(a, data=a.action_data.model_dump())
        if verbose:
            print(f"[{k:02d}] ({cx},{cy}) {why:9s} simVals={sorted(f[2] for f in model)} d={d}")
    if not execute:
        d = sum(1 for f in model if f[2] == 3 and (in_goal(f, g1) or in_goal(f, g2)))
        print(f"SIM no win (idle={idle_xy}, {d}/2, final={sorted(f[2] for f in model)})")
    else:
        print(f"{'CLEARED' if game.level_index != 6 else 'did NOT clear'} live (idle={idle_xy})")
    return game.level_index != 6 if execute else False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--ix", type=int, default=32)
    ap.add_argument("--iy", type=int, default=11)
    args = ap.parse_args()
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    run(arcade, (args.ix, args.iy), args.live, args.verbose)


if __name__ == "__main__":
    main()
