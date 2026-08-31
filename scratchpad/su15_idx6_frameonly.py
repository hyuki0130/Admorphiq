"""FRAME-ONLY reactive winnability port for idx6: drives the live env from
level 6 using ONLY the frame (canonical_layer + su15._classify) — no engine
internal reads for perception (set_level(6) is the only internal call, to reach
the level). Logic: deliver value-3s to separate goals; merge value-1/2 cascade
pairs; else a neutral idle click letting the enemies auto-downgrade the value-5.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from admorphiq.adapters25 import su15  # noqa: E402
from admorphiq.adapters25.base import (  # noqa: E402
    reset_action, click_action, canonical_layer, state_name,
)

R = su15._VACUUM_RADIUS


def frame_grid(latest):
    return canonical_layer(latest)


def deliver_click(fruit, goalc, val):
    cr, cc = fruit["centroid"]  # (row, col)
    dr, dc = goalc[0] - cr, goalc[1] - cc
    d = (dr * dr + dc * dc) ** 0.5 or 1.0
    sz = su15._SIZE[val]
    lead = max(1.0, min(d, R - sz / 2.0 - 0.5))
    return (cr + dr / d * lead, cc + dc / d * lead)  # (row, col)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=60)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("su15")
    latest = env.step(reset_action())
    game = env._game
    game.set_level(6)

    def step(row, col):
        r = max(10, min(62, int(round(row))))
        c = max(0, min(63, int(round(col))))
        a = click_action(x=c, y=r)
        return env.step(a, data=a.action_data.model_dump())

    latest = step(10, 32)  # render the level-6 frame (top-center, grabs nothing)

    # Capture goal anchors ONCE from the opening frame (colour-9 disks drop out of
    # detection once fruits/enemies occlude them — anchor to their start positions).
    g0, _f0, _e0 = su15._classify(frame_grid(latest))
    anchors = sorted((g["centroid"] for g in g0), key=lambda c: c[0])
    print(f"anchors={[tuple(round(x) for x in a) for a in anchors]}")

    for k in range(args.max):
        if game.level_index != 6:
            print(f"*** CLEARED frame-only at click {k} ***")
            return 0
        grid = frame_grid(latest)
        goals, fruits, enemies = su15._classify(grid)
        if not fruits:
            latest = step(11, 32); continue

        def val(f):
            return su15._COLOR_VAL.get(f["color"], -1)

        threes = [f for f in fruits if val(f) == 3]
        cascade = [f for f in fruits if 1 <= val(f) <= 2]

        # goal centroids (row, col) from the level-start ANCHORS (robust to dropout)
        if len(anchors) >= 2:
            g1, g2 = anchors[0], anchors[-1]
        elif len(anchors) == 1:
            g1 = g2 = anchors[0]
        else:
            g1 = g2 = (17, 23)

        def in_goal(f, gc):
            cr, cc = f["centroid"]
            return abs(cr - gc[0]) <= 5 and abs(cc - gc[1]) <= 5

        undelivered_threes = [f for f in threes if not (in_goal(f, g1) or in_goal(f, g2))]
        threes_in_g1 = [f for f in threes if in_goal(f, g1)]

        click = None
        why = ""
        if undelivered_threes:
            f = undelivered_threes[0]
            tgt = g1 if not threes_in_g1 else g2
            click = deliver_click(f, tgt, 3); why = f"deliver3->{tuple(round(x) for x in tgt)}"
        elif len(cascade) >= 2:
            by_val = {}
            for f in cascade:
                by_val.setdefault(val(f), []).append(f)
            pv = sorted(v for v, fs in by_val.items() if len(fs) >= 2)
            if pv:
                grp = by_val[pv[0]]

                def cdist(a, b):
                    return ((a["centroid"][0] - b["centroid"][0]) ** 2 + (a["centroid"][1] - b["centroid"][1]) ** 2) ** 0.5

                a, b = min(((grp[i], grp[j]) for i in range(len(grp)) for j in range(i + 1, len(grp))), key=lambda p: cdist(*p))
                ac, bc = a["centroid"], b["centroid"]
                d = cdist(a, b)
                if d <= su15._MERGE_DIST:
                    click = ((ac[0] + bc[0]) / 2.0, (ac[1] + bc[1]) / 2.0)
                else:
                    ur, uc = (bc[0] - ac[0]) / d, (bc[1] - ac[1]) / d
                    click = (ac[0] + ur * 7.0, ac[1] + uc * 7.0)
                why = f"merge v{pv[0]}"
        if click is None:
            click = (11, 32); why = "idle(let enemy downgrade)"

        latest = step(*click)
        if args.verbose:
            g2, f2, e2 = su15._classify(frame_grid(latest))
            vals = sorted(val(f) for f in f2)
            print(f"[{k:02d}] {why:26s} vals={vals} enemies={len(e2)} goals={len(g2)}")
    print(f"did NOT clear frame-only (final level_index={game.level_index})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
