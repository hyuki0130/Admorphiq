"""Closed-loop LIVE winnability probe for su15 idx6 (verification-only, reads
engine internals for ground truth). Two-phase adaptive choreography:

  Phase A: cascade the four value-1s -> one value-3, deliver to goal1 (top),
           luring whichever enemy threatens a cascade fruit.
  Phase B: use enemy2 (below the value-5) to chase-downgrade the value-5 5->4->3
           (enemy NON-vacuumed at contact), then deliver to goal2; stop the 3rd
           contact by delivering out of reach.

Prints per click. Success = level_index advances past 6.
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

_VAL_BY_COLOR = {c: v for v, c in enumerate(su15._VAL_COLORS)}
R = su15._VACUUM_RADIUS
EW, EH = su15._ENEMY_W, su15._ENEMY_H
SZ = su15._SIZE


def snap(game):
    fr = []
    for f in game.lkujttxgs:
        px = f.pixels
        c = int(px[px >= 0].max()) if (px is not None and (px >= 0).any()) else -1
        fr.append([int(f.x), int(f.y), _VAL_BY_COLOR.get(c, -1)])
    en = [[int(e.x), int(e.y), game.yghzqxumz.get(e, 0)] for e in game.fezhhzhih]
    return fr, en


def goals(game):
    out = []
    for s in game.powykypsm:
        h, w = s.pixels.shape
        out.append((int(s.x) + w // 2, int(s.y) + h // 2, (int(s.x), int(s.y), int(s.x) + w - 1, int(s.y) + h - 1)))
    return out


def step(env, cx, cy):
    cx = max(0, min(63, int(round(cx))))
    cy = max(10, min(62, int(round(cy))))
    a = click_action(x=cx, y=cy)
    env.step(a, data=a.action_data.model_dump())
    return cx, cy


def center(f):
    s = SZ[f[2]]
    return (f[0] + s // 2, f[1] + s // 2)


def ecenter(e):
    return (e[0] + EW // 2, e[1] + EH // 2)


def dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def deliver_click(f, goalc):
    """Click from fruit center toward goal, grab-safe lead (near edge stays in R)."""
    cx0, cy0 = center(f)
    dx, dy = goalc[0] - cx0, goalc[1] - cy0
    d = (dx * dx + dy * dy) ** 0.5 or 1.0
    sz = SZ[f[2]]
    lead = max(1.0, min(d, R - sz / 2.0 - 0.5))
    return (cx0 + dx / d * lead, cy0 + dy / d * lead)


def merge_click(a, b):
    ca, cb = center(a), center(b)
    d = dist(ca, cb)
    if d <= su15._MERGE_DIST:
        return ((ca[0] + cb[0]) / 2.0, (ca[1] + cb[1]) / 2.0)
    ux, uy = (cb[0] - ca[0]) / d, (cb[1] - ca[1]) / d
    return (ca[0] + ux * 7.0, ca[1] + uy * 7.0)


def lure_away(e, fruits, corner):
    ec = ecenter(e)
    dx, dy = corner[0] - ec[0], corner[1] - ec[1]
    d = (dx * dx + dy * dy) ** 0.5 or 1.0
    return (ec[0] + dx / d * R, ec[1] + dy / d * R)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lure", type=float, default=12.0)
    ap.add_argument("--max", type=int, default=60)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("su15")
    env.step(reset_action())
    game = env._game
    game.set_level(6)
    gs = goals(game)
    g1 = min(gs, key=lambda g: g[1])   # top goal (lowest y) for the cascade value-3
    g2 = max(gs, key=lambda g: g[1])   # lower goal for the value-5 chain
    print(f"goals g1(cascade)={g1[:2]} g2(v5)={g2[:2]}")

    for k in range(args.max):
        fr, en = snap(game)
        state = game._state.name if hasattr(game._state, "name") else str(game._state)
        if game.level_index != 6:
            print(f"*** CLEARED at click {k} (state={state}) ***")
            return 0
        if not fr:
            print("board empty"); break

        # classify
        chain = [f for f in fr if f[2] >= 4]         # the value-5 downgrade chain (4 or 5)
        threes = [f for f in fr if f[2] == 3]
        cascade = [f for f in fr if 1 <= f[2] <= 2]  # value-1/2 building second three

        # in-goal test
        def in_goal(f, g):
            c = center(f)
            _, _, bb = g[0], g[1], g[2]
            return bb[0] <= c[0] <= bb[2] and bb[1] <= c[1] <= bb[3]

        threes_in_g1 = [f for f in threes if in_goal(f, g1)]
        threes_in_g2 = [f for f in threes if in_goal(f, g2)]

        click = None
        why = ""

        # ---- delivery of value-3s to separate goals ----
        undelivered_threes = [f for f in threes if not (in_goal(f, g1) or in_goal(f, g2))]
        if undelivered_threes:
            # deliver first undelivered three to whichever goal is empty (prefer g1 for the cascade one, g2 else)
            f = undelivered_threes[0]
            tgt = g1 if not threes_in_g1 else g2
            # if this three is the value-5-origin (came from chain), send to g2
            click = deliver_click(f, tgt[:2]); why = f"deliver3 -> {tgt[:2]}"

        # ---- cascade the value-1/2s ----
        if click is None and len(cascade) >= 2:
            # protect: if an enemy is close to a cascade fruit, lure it away first
            by_val = {}
            for f in cascade:
                by_val.setdefault(f[2], []).append(f)
            pv = sorted(v for v, fs in by_val.items() if len(fs) >= 2)
            if pv:
                grp = by_val[pv[0]]
                # nearest pair
                a, b = min(((grp[i], grp[j]) for i in range(len(grp)) for j in range(i + 1, len(grp))),
                           key=lambda p: dist(center(p[0]), center(p[1])))
                others = [f for f in fr if f is not a and f is not b]
                # threat check: enemy within lure of an idle fruit that ISN'T the value-5 chain
                threat = None
                for e in en:
                    if e[2] > 0:
                        continue
                    ec = ecenter(e)
                    idle_prot = [f for f in fr if f is not a and f is not b and f[2] <= 3]
                    if idle_prot and min(dist(ec, center(f)) for f in idle_prot) < args.lure:
                        threat = e; break
                if threat is not None:
                    # lure to the corner farthest from all fruits
                    corners = [(2, 12), (62, 12), (2, 60), (62, 60)]
                    corner = max(corners, key=lambda c: min(dist(c, center(f)) for f in fr))
                    click = lure_away(threat, fr, corner); why = "lureThreat(cascade)"
                else:
                    click = merge_click(a, b); why = f"merge v{pv[0]} pair"
            else:
                # single cascade fruit left of value 2 waiting: nothing to merge now
                pass

        # ---- downgrade the value-5 chain ----
        if click is None and chain:
            f5 = chain[0]
            # enemy2 = enemy nearest the chain fruit
            e2 = min(en, key=lambda e: dist(ecenter(e), center(f5)))
            # We want enemy2 to CHASE-contact f5: do NOT vacuum e2. If e2 is its nearest,
            # any click far from e2 lets it walk in. Nudge f5 gently toward e2 to speed it,
            # by clicking on the far side of f5 from e2 (pulls f5 toward e2)? No: click near f5
            # would vacuum e2 too (they get close). Instead: click on a neutral far spot to let
            # e2 chase. Use the OTHER goal direction as a harmless park click.
            # But we also must keep e2's nearest = f5. If cascade fruits are closer to e2, e2
            # targets them. Here chain is the only high fruit; ensure e2 targets it.
            ec = ecenter(e2)
            # neutral click: far from BOTH enemies and f5, e.g. top-center, lets chase proceed
            click = (32, 11); why = "let e2 chase v5 (neutral click)"
            # if e2 already adjacent (dist small) it will contact this click's chase anyway

        if click is None:
            click = (32, 11); why = "idle"

        cx, cy = step(env, click[0], click[1])
        fr2, en2 = snap(game)
        vals = sorted(f[2] for f in fr2)
        if args.verbose:
            print(f"[{k:02d}] ({cx},{cy}) {why:28s} vals={vals} en={[(e[0],e[1],e[2]) for e in en2]}")
    print(f"did NOT clear (final vals={sorted(f[2] for f in snap(game)[0])})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
