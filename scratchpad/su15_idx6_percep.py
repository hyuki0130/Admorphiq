"""Perception-fidelity diagnostic along the WINNING oracle trajectory.

Drives idx6 with the oracle's internal-read DECISIONS (so it wins in 8 clicks),
and each click compares FRAME perception (su15._classify on canonical_layer +
goal ANCHORS captured once) against internal ground truth. Shows whether a
frame-only closed-loop port can win, or exactly where perception diverges.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from admorphiq.adapters25 import su15  # noqa: E402
from admorphiq.adapters25.base import reset_action, click_action, canonical_layer  # noqa: E402

_VAL_BY_COLOR = {c: v for v, c in enumerate(su15._VAL_COLORS)}
R = su15._VACUUM_RADIUS
SZ = su15._SIZE


def truth(game):
    fr = []
    for f in game.lkujttxgs:
        px = f.pixels
        c = int(px[px >= 0].max()) if (px is not None and (px >= 0).any()) else -1
        fr.append([int(f.x), int(f.y), _VAL_BY_COLOR.get(c, -1)])
    return fr


def goals_xy(game):
    out = []
    for s in game.powykypsm:
        h, w = s.pixels.shape
        out.append((int(s.x) + w // 2, int(s.y) + h // 2))
    return out


def frame_fruits(grid):
    """Frame-only fruit read (x=col, y=row, value) via su15._classify."""
    _g, fr, _e = su15._classify(grid)
    out = []
    for f in fr:
        r, c = f["centroid"]
        v = su15._COLOR_VAL.get(f["color"], -1)
        out.append([int(round(c)), int(round(r)), v])
    return out


def frame_goals(grid):
    g, _f, _e = su15._classify(grid)
    return [(int(round(gg["centroid"][1])), int(round(gg["centroid"][0]))) for gg in g]  # (x,y)


def ms(fr):
    d = {}
    for f in fr:
        d[f[2]] = d.get(f[2], 0) + 1
    return dict(sorted(d.items()))


def center(f):
    s = SZ[f[2]]
    return (f[0] + s // 2, f[1] + s // 2)


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def main():
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("su15")
    latest = env.step(reset_action())
    game = env._game
    game.set_level(6)
    latest = env.step(click_action(x=32, y=10), data=click_action(x=32, y=10).action_data.model_dump())
    gs = goals_xy(game)
    g1 = min(gs, key=lambda g: g[1])
    g2 = max(gs, key=lambda g: g[1])
    anchors = sorted(frame_goals(canonical_layer(latest)), key=lambda g: g[1])
    print(f"truth goals={gs} frame-anchors={anchors}")

    def in_goal(f, g):
        c = center(f)
        return abs(c[0] - g[0]) <= 5 and abs(c[1] - g[1]) <= 5

    for k in range(40):
        if game.level_index != 6:
            print(f"*** oracle CLEARED at click {k} ***")
            break
        # perception compare
        tf = truth(game)
        ff = frame_fruits(canonical_layer(latest))
        match = ms(tf) == ms(ff)
        print(f"[{k:02d}] truthMS={ms(tf)} frameMS={ms(ff)} {'OK' if match else 'PERCEP-DIVERGE'}")
        if not match:
            print(f"     truth={sorted(map(tuple, tf))}\n     frame={sorted(map(tuple, ff))}")
        # oracle decision (internal truth)
        threes = [f for f in tf if f[2] == 3]
        cascade = [f for f in tf if 1 <= f[2] <= 2]
        in_g1 = [f for f in threes if in_goal(f, g1)]
        undelivered = [f for f in threes if not in_goal(f, g1) and not in_goal(f, g2)]
        click = None
        if undelivered:
            f = undelivered[0]
            tgt = g1 if not in_g1 else g2
            c = center(f)
            dx, dy = tgt[0] - c[0], tgt[1] - c[1]
            d = (dx * dx + dy * dy) ** 0.5 or 1.0
            lead = max(1.0, min(d, R - SZ[f[2]] / 2.0 - 0.5))
            click = (c[0] + dx / d * lead, c[1] + dy / d * lead)
        elif len(cascade) >= 2:
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
                    click = ((ca[0] + cb[0]) / 2.0, (ca[1] + cb[1]) / 2.0)
                else:
                    ux, uy = (cb[0] - ca[0]) / d, (cb[1] - ca[1]) / d
                    click = (ca[0] + ux * 7.0, ca[1] + uy * 7.0)
        if click is None:
            click = (32, 11)
        cx = max(0, min(63, int(round(click[0]))))
        cy = max(10, min(62, int(round(click[1]))))
        a = click_action(x=cx, y=cy)
        latest = env.step(a, data=a.action_data.model_dump())


if __name__ == "__main__":
    main()
