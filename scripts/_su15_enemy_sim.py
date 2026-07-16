"""Verification-only dev-probe (DISPOSABLE): lockstep-validate su15's full
fruits+enemy sim (:func:`admorphiq.adapters25.su15._sim_click_full`) against the
LIVE engine at L3, then run the margin search.

Nothing in the runtime adapter reads engine internals — this probe does
(``env._game``) ONLY to obtain ground-truth positions for validation, the
established repo pattern (see ``scripts/_tr87_capture_l1.py``). L3 is reached
by ``next_level()`` ×3. Fruit value is read from sprite colour (hash-agnostic),
so the probe works whichever su15 hash the offline engine loads.

Usage: uv run python scripts/_su15_enemy_sim.py [--frames 20] [--search]
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


def _make_level(arcade, idx: int):
    """su15 env at level ``idx`` (source ``set_level``); returns (env, game)."""
    env = arcade.make("su15")
    env.step(reset_action())
    game = env._game  # noqa: SLF001 — verification-only
    game.set_level(idx)
    assert game.level_index == idx, f"expected L{idx}, got {game.level_index}"
    return env, game


def _goal(game) -> tuple[tuple[int, int], tuple[int, int, int, int]]:
    """(centre (x,y), bbox (x0,y0,x1,y1)) of the level's goal disk, from
    internals — the win target, read per level rather than hardcoded."""
    for s in game.powykypsm:
        h, w = s.pixels.shape
        x, y = int(s.x), int(s.y)
        return (x + w // 2, y + h // 2), (x, y, x + w - 1, y + h - 1)
    return (32, 32), (28, 28, 36, 36)


def _fruits(game) -> list[list[int]]:
    """Ground-truth fruit models [x, y, value] from engine internals."""
    out = []
    for f in game.lkujttxgs:
        px = f.pixels
        color = int(px[px >= 0].max()) if (px is not None and (px >= 0).any()) else -1
        out.append([int(f.x), int(f.y), _VAL_BY_COLOR.get(color, -1)])
    return out


def _enemies(game) -> list[list[int]]:
    return [[int(e.x), int(e.y)] for e in game.fezhhzhih]


def _ms(fruits: list[list[int]]) -> dict[int, int]:
    d: dict[int, int] = {}
    for f in fruits:
        d[f[2]] = d.get(f[2], 0) + 1
    return d


def _step_click(env, cx: int, cy: int):
    """Step an ACTION6 click, passing the x/y as the engine expects (a bare
    ``env.step(action)`` drops the coords → the engine clicks (0,0), out of
    play). Mirrors ``score_efficiency.run_game``'s complex-action path."""
    action = click_action(x=cx, y=cy)
    return env.step(action, data=action.action_data.model_dump())


def _apply_live(env, game, cx: int, cy: int):
    _step_click(env, cx, cy)
    return _fruits(game), _enemies(game)


def _enemy_err(sim_e: list[list[int]], live_e: list[list[int]]) -> float:
    """Max over enemies of the top-left L-inf position error (px). Index-matched
    when counts are equal (sim preserves input order and the engine keeps the
    enemy list stable when no merge fires); nearest-match otherwise."""
    if not sim_e or not live_e:
        return 0.0
    err = 0.0
    if len(sim_e) == len(live_e):
        for s, lv in zip(sim_e, live_e):
            err = max(err, max(abs(s[0] - lv[0]), abs(s[1] - lv[1])))
        return err
    for s in sim_e:
        d = min(max(abs(s[0] - le[0]), abs(s[1] - le[1])) for le in live_e)
        err = max(err, d)
    return err


def validate(arcade, n_frames: int, seed: int = 0, idx: int = 3) -> None:
    """Drive random legal clicks; after each, compare _sim_click_full's
    prediction (advanced from the PREVIOUS live state) against the live engine.
    Prints per-click fruit-multiset match, enemy position error, contact flag."""
    rng = random.Random(seed)
    env, game = _make_level(arcade, idx)
    lf, le = _fruits(game), _enemies(game)
    print(f"L{idx} seed: {len(lf)} fruits {_ms(lf)}, {len(le)} enemies at {le}")
    ms_mismatch = 0
    enemy_err_max = 0.0
    cf_mismatch = 0  # contact-FREE fruit-multiset mismatches (must be 0)
    cf_enemy_err = 0.0  # enemy error on contact-free frames
    for k in range(n_frames):
        # Bias clicks near a fruit or the enemy so the sim's interesting paths
        # (vacuum-pull + chase) are actually exercised, not just no-ops.
        if le and rng.random() < 0.5:
            en = rng.choice(le)
            cx = max(0, min(63, en[0] + rng.randint(-6, 6)))
            cy = max(10, min(62, en[1] + rng.randint(-6, 6)))
        elif lf:
            f = rng.choice(lf)
            cx = max(0, min(63, f[0] + rng.randint(-6, 6)))
            cy = max(10, min(62, f[1] + rng.randint(-6, 6)))
        else:
            cx, cy = rng.randint(0, 63), rng.randint(10, 62)
        sim_f, sim_e, contact = su15._sim_click_full(lf, le, cx, cy)
        lf, le = _apply_live(env, game, cx, cy)
        ms_ok = _ms(sim_f) == _ms(lf)
        eerr = _enemy_err(sim_e, le)
        if not ms_ok:
            ms_mismatch += 1
        if not contact:
            if not ms_ok:
                cf_mismatch += 1
            cf_enemy_err = max(cf_enemy_err, eerr)
        enemy_err_max = max(enemy_err_max, eerr)
        flag = "OK" if (ms_ok and eerr <= 1) else "!!"
        print(
            f"[{k:02d}] click({cx},{cy}) simMS={_ms(sim_f)} liveMS={_ms(lf)} "
            f"ms={'ok' if ms_ok else 'MISMATCH'} enemyErr={eerr:.0f} contact={contact} {flag}"
        )
        if game.level_index != idx or not lf:
            print("  (level changed / board empty — stopping)")
            break
    print(
        f"\nSUMMARY frames={n_frames} ms_mismatches={ms_mismatch} "
        f"(contact-FREE mismatches={cf_mismatch}) max_enemy_err={enemy_err_max:.0f}px "
        f"(contact-free enemy_err={cf_enemy_err:.0f}px)"
    )


# ── margin search ────────────────────────────────────────────────────────


def _delivered(fruits: list[list[int]], goal_bbox: tuple[int, int, int, int], target: int = 3) -> bool:
    """Win (spec [``target``,1]): exactly one ``target``-value fruit whose centre
    is inside the goal bbox, and no fruit of value > ``target`` (over-merge)."""
    x0, y0, x1, y1 = goal_bbox
    hit = 0
    for f in fruits:
        if f[2] > target:
            return False
        if f[2] == target:
            cx = f[0] + su15._SIZE[target] // 2
            cy = f[1] + su15._SIZE[target] // 2
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                hit += 1
    return hit == 1


def _choreograph(model, enemies_xy, goal_xy, lure_base, corners):
    """Multi-enemy mirror of the adapter's proven L3 choreography, parametrised
    by lure aggression ``lure_base`` and the lure ``corners``. ``enemies_xy`` is
    a LIST of enemy centres. Deliver the top fruit once it reaches value ≥3; else
    merge the nearest lowest-value pair — but if ANY enemy threatens an idle
    (non-merging) fruit, first LURE the MOST urgent enemy (closest to an idle
    fruit) to the fruit-farthest corner. Returns a click ``(x, y)`` or None."""
    R = su15._VACUUM_RADIUS

    def dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    top = max(model, key=lambda f: f[2])
    if top[2] >= 3:
        dx, dy = goal_xy[0] - top[0], goal_xy[1] - top[1]
        d = (dx * dx + dy * dy) ** 0.5
        if d < 3.5:
            return None
        return (top[0] + dx / d * R, top[1] + dy / d * R)
    best = None
    for i in range(len(model)):
        for j in range(i + 1, len(model)):
            if model[i][2] == model[j][2]:
                d = dist((model[i][0], model[i][1]), (model[j][0], model[j][1]))
                if best is None or d < best[0]:
                    best = (d, i, j)
    if best is None:
        return None
    d, i, j = best
    a, b = model[i], model[j]
    others = [f for k, f in enumerate(model) if k not in (i, j)]
    max_val = max(f[2] for f in model)
    danger = lure_base + 4.0 * max_val + max(0, 5 - len(model)) * 3.0
    if others and enemies_xy:
        urgency = [(min(dist(e, (f[0], f[1])) for f in others), e) for e in enemies_xy]
        gap, e = min(urgency, key=lambda t: t[0])
        if gap < danger:
            park = max(corners, key=lambda c: min((dist(c, (f[0], f[1])) for f in model), default=0.0))
            dx, dy = park[0] - e[0], park[1] - e[1]
            dd = (dx * dx + dy * dy) ** 0.5 or 1.0
            return (e[0] + dx / dd * R, e[1] + dy / dd * R)
    if d <= su15._MERGE_DIST:
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    return (a[0] + ux * 7.0, a[1] + uy * 7.0)


def _enemies_xy(enemies):
    return [(e[0] + su15._ENEMY_W // 2, e[1] + su15._ENEMY_H // 2) for e in enemies]


def _run_plan(fruits, enemy, goal_c, goal_bbox, lure_base, corners, max_clicks=64):
    """Drive ``_choreograph`` open-loop over the FAITHFUL full sim from a given
    seed. Returns (outcome, clicks) where outcome in {win, contact, stuck,
    budget}. ``contact`` = an enemy downgraded a fruit OR two enemies merged
    (both unsafe/unmodelled → the plan is rejected)."""
    model = [f[:] for f in fruits]
    enemies = [e[:] for e in enemy]
    for k in range(max_clicks):
        if _delivered(model, goal_bbox):
            return "win", k
        if not model:
            return "stuck", k
        click = _choreograph(model, _enemies_xy(enemies), goal_c, lure_base, corners)
        if click is None:
            return "stuck", k
        cx = max(0, min(63, int(round(click[0]))))
        cy = max(10, min(62, int(round(click[1]))))
        model, enemies, contact = su15._sim_click_full(model, enemies, cx, cy)
        if contact:
            return "contact", k
    return "budget", max_clicks


def _perturb(fruits, enemy, dx, dy):
    f2 = [[max(0, min(63, f[0] + dx)), max(10, min(62, f[1] + dy)), f[2]] for f in fruits]
    e2 = [[max(0, min(59, e[0] + dx)), max(10, min(60, e[1] + dy))] for e in enemy]
    return f2, e2


def search(arcade, idx: int = 3) -> None:
    """Enumerate (lure_base × corner-set) choreography variants; for each, run
    the faithful sim from the PARSED seed and from ±1px perturbations. Accept a
    plan only if it WINS under ALL perturbations (drift-robust margin)."""
    _env, game = _make_level(arcade, idx)
    fruits = _fruits(game)
    enemy = _enemies(game)
    goal_c, goal_bbox = _goal(game)
    print(f"L{idx} seed: fruits={fruits} enemies={enemy} goal_c={goal_c} bbox={goal_bbox}")

    corner_sets = {
        "adapter8": su15.Adapter._MODEL_CORNERS,
        "far4": ((2, 12), (2, 60), (60, 60), (60, 12)),
        "corners6": ((2, 12), (2, 60), (60, 12), (60, 60), (2, 36), (60, 36)),
    }
    lure_bases = [12.0, 15.0, 18.0, 20.0, 24.0, 28.0, 32.0, 36.0]
    # ±1px perturbations of EVERY object (the frame-parse rounding drift).
    perturbs = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]

    results = []
    for cname, corners in corner_sets.items():
        for lb in lure_bases:
            outcomes = []
            for dx, dy in perturbs:
                pf, pe = _perturb(fruits, enemy, dx, dy)
                out, k = _run_plan(pf, pe, goal_c, goal_bbox, lb, corners)
                outcomes.append((out, k))
            wins = sum(1 for o, _ in outcomes if o == "win")
            base_out, base_k = outcomes[0]
            robust = wins == len(perturbs)
            results.append((cname, lb, wins, len(perturbs), base_out, base_k, robust))
            tag = "  ROBUST-WIN" if robust else ""
            print(
                f"corners={cname:9s} lure_base={lb:4.0f}  wins={wins}/{len(perturbs)}  "
                f"base={base_out}@{base_k}{tag}"
            )
    robust = [r for r in results if r[6]]
    print(f"\nSEARCH SUMMARY L{idx}: {len(robust)} drift-robust winning plan(s) of {len(results)} configs")
    if robust:
        for r in sorted(robust, key=lambda r: r[5]):
            print(f"  ROBUST: corners={r[0]} lure_base={r[1]:.0f} base_clicks={r[5]}")
    else:
        best = max(results, key=lambda r: (r[2], -r[5]))
        print(
            f"  best (non-robust): corners={best[0]} lure_base={best[1]:.0f} "
            f"wins={best[2]}/{best[3]} base={best[4]}@{best[5]}"
        )


def run_live_openloop(arcade, lure_base: float = 20.0, idx: int = 3) -> None:
    """Decisive transfer test: seed the sim ONCE from the parsed level state, run
    the margin-robust choreography OPEN-LOOP through the faithful sim, and execute
    each click on the LIVE engine. Reports whether the level clears live."""
    env, game = _make_level(arcade, idx)
    model = _fruits(game)
    enemies = _enemies(game)
    goal_c, _goal_bbox = _goal(game)
    corners = su15.Adapter._MODEL_CORNERS
    print(f"LIVE open-loop L{idx}: seed fruits={len(model)} enemies={enemies} lure_base={lure_base}")
    for k in range(64):
        state = game._state.name if hasattr(game._state, "name") else str(game._state)
        if game.level_index != idx or state == "WIN":
            print(f"  cleared at click {k} (state={state}, level_index={game.level_index})")
            return
        if not model:
            print("  board empty — stopping")
            break
        click = _choreograph(model, _enemies_xy(enemies), goal_c, lure_base, corners)
        if click is None:
            print(f"  plan exhausted at click {k}")
            break
        cx = max(0, min(63, int(round(click[0]))))
        cy = max(10, min(62, int(round(click[1]))))
        _step_click(env, cx, cy)
        model, enemies, _c = su15._sim_click_full(model, enemies, cx, cy)
    fin = game.level_index
    print(f"  FINAL level_index={fin} ({'CLEARED L%d' % idx if fin > idx else 'did NOT clear'})")


# ── joint (side-parallel merge + timed cross-merge) plan class ─────────────
# For TWO independent chasers (L4): merge each side's pair on its own side while
# luring THAT side's enemy to a fruit-free PARK, then combine the two value-2s in
# a window when both enemies are clear of the merge midpoint. Strict contact=reject
# so an accepted plan provably never downgrades ANY fruit.


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _joint_choreograph(model, enemies_xy, goal_xy, lure_base, park_l, park_r, cross_gate):
    """Side-parallel joint choreography. ``park_l``/``park_r`` are the lure
    targets for the left/right (by x<32) enemy; ``cross_gate`` is the enemy
    clearance required before a FAR (cross-side) merge. Returns a click or None."""
    R = su15._VACUUM_RADIUS
    top = max(model, key=lambda f: f[2])
    if top[2] >= 3:
        dx, dy = goal_xy[0] - top[0], goal_xy[1] - top[1]
        d = (dx * dx + dy * dy) ** 0.5
        if d < 3.5:
            return None
        return (top[0] + dx / d * R, top[1] + dy / d * R)

    by_val: dict[int, list] = {}
    for f in model:
        by_val.setdefault(f[2], []).append(f)
    pair_vals = sorted(v for v, fs in by_val.items() if len(fs) >= 2)
    if not pair_vals:
        # No pair to merge — deliver the top fruit toward the goal.
        dx, dy = goal_xy[0] - top[0], goal_xy[1] - top[1]
        d = (dx * dx + dy * dy) ** 0.5 or 1.0
        return (top[0] + dx / d * R, top[1] + dy / d * R)
    v = pair_vals[0]
    grp = by_val[v]
    # Among candidate same-value pairs, pick the SAFEST merge (midpoint farthest
    # from both enemies) — this defers the exposed cross-merge until enemies clear.
    cand = []
    for i in range(len(grp)):
        for j in range(i + 1, len(grp)):
            a, b = grp[i], grp[j]
            mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            safety = min((_dist(mid, e) for e in enemies_xy), default=1e9)
            cand.append((safety, a, b, mid))
    cand.sort(key=lambda t: -t[0])
    _safety, a, b, mid = cand[0]
    pair_ids = {id(a), id(b)}
    others = [f for f in model if id(f) not in pair_ids]
    far = _dist((a[0], a[1]), (b[0], b[1])) > su15._MERGE_DIST
    max_val = max(f[2] for f in model)
    danger = lure_base + 4.0 * max_val + max(0, 5 - len(model)) * 3.0

    # Which enemy (if any) must be lured before we act? An enemy threatens if it
    # is within `danger` of an idle fruit; for a FAR merge, also if it is within
    # `cross_gate` of the merge midpoint (it would reach the exposed transit).
    urgent = None
    best = 1e9
    for e in enemies_xy:
        urg = min((_dist(e, (f[0], f[1])) for f in others), default=1e9)
        thr = danger
        if far:
            urg = min(urg, _dist(e, mid))
            thr = max(danger, cross_gate)
        if urg < thr and urg < best:
            best = urg
            urgent = e
    if urgent is not None:
        park = park_l if urgent[0] < 32 else park_r
        dx, dy = park[0] - urgent[0], park[1] - urgent[1]
        d = (dx * dx + dy * dy) ** 0.5 or 1.0
        return (urgent[0] + dx / d * R, urgent[1] + dy / d * R)
    if _dist((a[0], a[1]), (b[0], b[1])) <= su15._MERGE_DIST:
        return mid
    d = _dist((a[0], a[1]), (b[0], b[1]))
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    return (a[0] + ux * 7.0, a[1] + uy * 7.0)


def _run_plan_joint(fruits, enemy, goal_c, goal_bbox, lure_base, park_l, park_r, cross_gate, max_clicks=80):
    model = [f[:] for f in fruits]
    enemies = [e[:] for e in enemy]
    for k in range(max_clicks):
        if _delivered(model, goal_bbox):
            return "win", k
        if not model:
            return "stuck", k
        click = _joint_choreograph(model, _enemies_xy(enemies), goal_c, lure_base, park_l, park_r, cross_gate)
        if click is None:
            return "stuck", k
        cx = max(0, min(63, int(round(click[0]))))
        cy = max(10, min(62, int(round(click[1]))))
        model, enemies, contact = su15._sim_click_full(model, enemies, cx, cy)
        if contact:
            return "contact", k
    return "budget", max_clicks


# Park-pair candidates (x=col, y=row). Mid-height side edges sit BETWEEN the top
# value-1 fruits (rows ~25) and the bottom value-0 fruits (rows ~55), so a lured
# enemy there is clear of every fruit; the bottom/split options are also tried.
_PARK_PAIRS = {
    "midedge": ((1, 40), (62, 40)),
    "midhi": ((1, 33), (62, 33)),
    "midlo": ((1, 46), (62, 46)),
    "topcorner": ((1, 12), (62, 12)),
    "splitout": ((1, 37), (62, 37)),
}


def search_joint(arcade, idx: int = 4) -> None:
    """Search the side-parallel joint plan (park-pair × lure_base × cross_gate);
    accept only plans that WIN under ALL ±1px perturbations."""
    _env, game = _make_level(arcade, idx)
    fruits = _fruits(game)
    enemy = _enemies(game)
    goal_c, goal_bbox = _goal(game)
    print(f"L{idx} JOINT search: fruits={fruits} enemies={enemy} goal_c={goal_c}")
    lure_bases = [14.0, 18.0, 22.0, 26.0]
    cross_gates = [14.0, 20.0, 26.0]
    perturbs = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]
    results = []
    for pname, (pl, pr) in _PARK_PAIRS.items():
        for lb in lure_bases:
            for cg in cross_gates:
                outs = []
                for dx, dy in perturbs:
                    pf, pe = _perturb(fruits, enemy, dx, dy)
                    outs.append(_run_plan_joint(pf, pe, goal_c, goal_bbox, lb, pl, pr, cg))
                wins = sum(1 for o, _ in outs if o == "win")
                base_out, base_k = outs[0]
                robust = wins == len(perturbs)
                results.append((pname, lb, cg, wins, len(perturbs), base_out, base_k, robust))
                if robust or wins >= len(perturbs) - 2:
                    tag = "  ROBUST-WIN" if robust else ""
                    print(
                        f"park={pname:9s} lure={lb:4.0f} cross_gate={cg:4.0f}  "
                        f"wins={wins}/{len(perturbs)} base={base_out}@{base_k}{tag}"
                    )
    robust = [r for r in results if r[7]]
    print(f"\nJOINT SEARCH SUMMARY L{idx}: {len(robust)} drift-robust winner(s) of {len(results)} configs")
    if robust:
        for r in sorted(robust, key=lambda r: r[6]):
            print(f"  ROBUST: park={r[0]} lure={r[1]:.0f} cross_gate={r[2]:.0f} base_clicks={r[6]}")
    else:
        best = max(results, key=lambda r: (r[3], -r[6]))
        print(
            f"  best (non-robust): park={best[0]} lure={best[1]:.0f} cross_gate={best[2]:.0f} "
            f"wins={best[3]}/{best[4]} base={best[5]}@{best[6]}"
        )


def run_live_joint(arcade, park="midedge", lure_base=18.0, cross_gate=20.0, idx=4) -> None:
    """Execute the joint plan OPEN-LOOP on the LIVE engine (transfer test for a
    robust winner). Pure open-loop, settled checkpoints (one obs per action)."""
    env, game = _make_level(arcade, idx)
    model = _fruits(game)
    enemies = _enemies(game)
    goal_c, _bbox = _goal(game)
    pl, pr = _PARK_PAIRS[park]
    print(f"LIVE joint L{idx}: fruits={len(model)} enemies={enemies} park={park} lure={lure_base} cg={cross_gate}")
    for k in range(80):
        state = game._state.name if hasattr(game._state, "name") else str(game._state)
        if game.level_index != idx or state == "WIN":
            print(f"  cleared at click {k} (state={state}, level_index={game.level_index})")
            return
        if not model:
            print("  board empty — stopping")
            break
        click = _joint_choreograph(model, _enemies_xy(enemies), goal_c, lure_base, pl, pr, cross_gate)
        if click is None:
            print(f"  plan exhausted at click {k}")
            break
        cx = max(0, min(63, int(round(click[0]))))
        cy = max(10, min(62, int(round(click[1]))))
        _step_click(env, cx, cy)
        model, enemies, _c = su15._sim_click_full(model, enemies, cx, cy)
    fin = game.level_index
    print(f"  FINAL level_index={fin} ({'CLEARED L%d' % idx if fin > idx else 'did NOT clear'})")


# ── spare-sacrifice plan class (3rd) ───────────────────────────────────────
# The spec is [3,1]: only the four value-1s are needed (4->2->1). The four
# value-0s are SPARE — deliberately let the enemies EAT them (source: a value-0
# contact `rzdkhogqmi` destroys the fruit after ~4 knockback sub-steps AND gives
# the enemy a `tfaferyux+djoqfdlzu+1 = 9` sub-step cooldown, freezing its chase
# ~2 clicks). So a `_sim_click_sacrifice` models value-0 DESTRUCTION + cooldown
# (allowed) and value>=1 DOWNGRADE (a cascade-fruit hit → REJECT). Enemies carry
# a 3rd field = cooldown (sub-steps). Kept in the probe only — su15.py (the
# shipped adapter, floor 4/9) is untouched unless a robust winner is found.
_COOLDOWN = 9  # tfaferyux + djoqfdlzu + 1


def _sim_click_sacrifice(fruits, enemies, cx, cy):
    """Like `su15._sim_click_full` but: value-0 enemy contact DESTROYS the fruit
    (removed) and sets that enemy's cooldown to `_COOLDOWN` sub-steps (frozen
    chase); value>=1 contact sets ``bad`` (a cascade-fruit downgrade → reject).
    ``enemies`` are ``[x, y, cooldown]``. Returns ``(fruits', enemies', bad)``."""
    fs = [f[:] for f in fruits]
    es = [e[:] for e in enemies]
    ew, eh = su15._ENEMY_W, su15._ENEMY_H
    sel_fruit = [f for f in fs if su15._euclid_in_radius(cx, cy, f[0], f[1], su15._SIZE[f[2]], su15._SIZE[f[2]])]
    vac = {}
    for i, e in enumerate(es):
        if su15._euclid_in_radius(cx, cy, e[0], e[1], ew, eh):
            ecx, ecy = e[0] + ew // 2, e[1] + eh // 2
            vx, vy = float(cx - ecx), float(cy - ecy)
            d = (vx * vx + vy * vy) ** 0.5
            ux, uy = (vx / d, vy / d) if d > 0 else (0.0, 0.0)
            vac[i] = (ux, uy, float(e[0]), float(e[1]))
    bad = False
    dead = set()  # indices of destroyed value-0 fruits
    for _ in range(su15._SUBSTEPS):
        for f in sel_fruit:
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
        alive = [k for k in range(len(fs)) if k not in dead]
        for i, e in enumerate(es):
            if i in vac or e[2] > 0 or not alive:
                continue
            ecx, ecy = e[0] + ew // 2, e[1] + eh // 2
            best = min(alive, key=lambda k: (fs[k][0] + su15._SIZE[fs[k][2]] // 2 - ecx) ** 2
                       + (fs[k][1] + su15._SIZE[fs[k][2]] // 2 - ecy) ** 2)
            tx = fs[best][0] + su15._SIZE[fs[best][2]] // 2
            ty = fs[best][1] + su15._SIZE[fs[best][2]] // 2
            sx = 1 if tx > ecx else (-1 if tx < ecx else 0)
            sy = 1 if ty > ecy else (-1 if ty < ecy else 0)
            e[0], e[1] = su15._clamp_pos(e[0] + sx, e[1] + sy, ew, eh)
        for i, e in enumerate(es):
            if i in vac:
                continue
            for k in range(len(fs)):
                if k in dead:
                    continue
                if su15._bbox_overlap(e[0], e[1], ew, eh, fs[k][0], fs[k][1],
                                      su15._SIZE[fs[k][2]], su15._SIZE[fs[k][2]]):
                    if fs[k][2] == 0:
                        dead.add(k)
                        e[2] = _COOLDOWN
                    else:
                        bad = True
        for e in es:
            if e[2] > 0:
                e[2] -= 1
    fs = [f for k, f in enumerate(fs) if k not in dead]
    # same-value overlap merge (identical to the full sim)
    n = len(fs)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def touch(a, b):
        sa, sb = su15._SIZE[a[2]], su15._SIZE[b[2]]
        return not (a[0] + sa <= b[0] or b[0] + sb <= a[0] or a[1] + sa <= b[1] or b[1] + sb <= a[1])

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
            nsz = su15._SIZE[v] if v < len(su15._SIZE) else su15._SIZE[-1]
            gx = round(sum(fs[k][0] for k in idxs) / len(idxs))
            gy = round(sum(fs[k][1] for k in idxs) / len(idxs))
            out.append([gx - (nsz - 1) // 2, gy - (nsz - 1) // 2, v])
        else:
            out.append(fs[idxs[0]])
    return out, es, bad


def _sacrifice_choreograph(model, enemies, goal_xy, lure_base, sink):
    """Sacrifice choreography: lure any enemy that threatens a value-1 (a cascade
    fruit) DOWN toward its side of the value-0 field (``sink`` rows), where it
    eats spares and freezes; meanwhile merge the value-1 pairs and deliver.
    ``enemies`` = ``[x,y,cd]``. Returns a click or None."""
    R = su15._VACUUM_RADIUS
    exy = [(e[0] + su15._ENEMY_W // 2, e[1] + su15._ENEMY_H // 2) for e in enemies]
    top = max(model, key=lambda f: f[2])
    if top[2] >= 3:
        # Deliver from the fruit CENTRE with a grab-safe lead: a size-`sz` fruit's
        # near edge must stay within the vacuum radius, so the click sits at most
        # `R - sz/2` px from the centre (aiming top-left + R overshoots on a
        # diagonal for a size-4 fruit and stalls delivery — measured).
        sz = su15._SIZE[top[2]]
        cx0, cy0 = top[0] + sz // 2, top[1] + sz // 2
        dx, dy = goal_xy[0] - cx0, goal_xy[1] - cy0
        d = (dx * dx + dy * dy) ** 0.5 or 1.0
        lead = max(1.0, min(d, R - sz / 2.0 - 0.5))
        return (cx0 + dx / d * lead, cy0 + dy / d * lead)
    cascade = [f for f in model if f[2] >= 1]  # the fruits we must protect
    # If a NON-frozen enemy is within danger of a cascade fruit, lure it down.
    danger = lure_base
    threat = None
    best = 1e9
    for e, c in zip(exy, enemies):
        if c[2] > 0:  # already frozen/eating — safe
            continue
        if not cascade:
            continue
        g = min(((e[0] - f[0]) ** 2 + (e[1] - f[1]) ** 2) ** 0.5 for f in cascade)
        if g < danger and g < best:
            best = g
            threat = e
    if threat is not None:
        # sink target on the threat's own side (x kept, driven to the low rows)
        tx = 2 if threat[0] < 32 else 61
        ty = sink
        dx, dy = tx - threat[0], ty - threat[1]
        d = (dx * dx + dy * dy) ** 0.5 or 1.0
        return (threat[0] + dx / d * R, threat[1] + dy / d * R)
    # No threat — merge the lowest-value pair (cascade first).
    by_val = {}
    for f in model:
        by_val.setdefault(f[2], []).append(f)
    pv = sorted(v for v, fs in by_val.items() if len(fs) >= 2 and v >= 1)
    if not pv:
        pv = sorted(v for v, fs in by_val.items() if len(fs) >= 2)
    if not pv:
        return None
    grp = by_val[pv[0]]
    a, b = min(((grp[i], grp[j]) for i in range(len(grp)) for j in range(i + 1, len(grp))),
               key=lambda p: (p[0][0] - p[1][0]) ** 2 + (p[0][1] - p[1][1]) ** 2)
    d = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
    if d <= su15._MERGE_DIST:
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    return (a[0] + ux * 7.0, a[1] + uy * 7.0)


def _run_plan_sacrifice(fruits, enemy, goal_c, goal_bbox, lure_base, sink, max_clicks=90):
    model = [f[:] for f in fruits]
    enemies = [[e[0], e[1], 0] for e in enemy]
    for k in range(max_clicks):
        if _delivered(model, goal_bbox):
            return "win", k
        if not [f for f in model if f[2] >= 1]:
            return "lostcascade", k  # all value-1s gone → can't build a 3
        click = _sacrifice_choreograph(model, enemies, goal_c, lure_base, sink)
        if click is None:
            return "stuck", k
        cx = max(0, min(63, int(round(click[0]))))
        cy = max(10, min(62, int(round(click[1]))))
        model, enemies, bad = _sim_click_sacrifice(model, enemies, cx, cy)
        if bad:
            return "downgrade", k
    return "budget", max_clicks


def validate_sacrifice(arcade, lure_base=24.0, sink=56.0, idx=4) -> None:
    """Lockstep the destruction path: drive the SAME sacrifice-choreography clicks
    through BOTH the live engine and `_sim_click_sacrifice`, comparing the fruit
    multiset each click. Verifies value-0 destroys (multiset shrinks identically)
    and flags where a value>=1 downgrade appears (the sim's `bad`, which it does
    not model past)."""
    env, game = _make_level(arcade, idx)
    goal_c, goal_bbox = _goal(game)
    model = [list(f) for f in _fruits(game)]
    enemies = [[e[0], e[1], 0] for e in _enemies(game)]
    print(f"L{idx} SACRIFICE lockstep: seed ms={_ms(_fruits(game))} lure={lure_base} sink={sink}")
    mism = 0
    for k in range(60):
        click = _sacrifice_choreograph(model, enemies, goal_c, lure_base, sink)
        if click is None:
            print(f"  plan done at {k}")
            break
        cx = max(0, min(63, int(round(click[0]))))
        cy = max(10, min(62, int(round(click[1]))))
        model, enemies, bad = _sim_click_sacrifice(model, enemies, cx, cy)
        _step_click(env, cx, cy)
        live = _fruits(game)
        sim_ms = _ms([[f[0], f[1], f[2]] for f in model])
        live_ms = _ms(live)
        ok = sim_ms == live_ms
        if not ok:
            mism += 1
        print(f"[{k:02d}] click({cx},{cy}) simMS={sim_ms} liveMS={live_ms} {'ok' if ok else 'MISMATCH'} bad={bad}")
        if bad or not ok:
            print("  (sim flagged downgrade / diverged — destruction-path check ends here)")
            break
        if game.level_index != idx:
            print(f"  cleared L{idx}")
            break
    print(f"SACRIFICE lockstep: multiset mismatches (pre-downgrade) = {mism}")


def run_live_sacrifice(arcade, lure_base=16.0, sink=56.0, idx=4, reparse=False) -> None:
    """Execute the sacrifice plan on the LIVE engine. Default pure open-loop
    (advance the sim, emit its clicks); ``reparse`` re-seeds fruit positions +
    values from the live frame each click (enemy cooldown kept from the sim,
    since it is not frame-observable) to correct the sim's ~1-spare destruction-
    timing drift while trusting the sim only for cooldown book-keeping."""
    env, game = _make_level(arcade, idx)
    goal_c, _bbox = _goal(game)
    model = [list(f) for f in _fruits(game)]
    enemies = [[e[0], e[1], 0] for e in _enemies(game)]
    print(f"LIVE sacrifice L{idx}: seed ms={_ms(_fruits(game))} lure={lure_base} sink={sink} reparse={reparse}")
    for k in range(80):
        state = game._state.name if hasattr(game._state, "name") else str(game._state)
        if game.level_index != idx or state == "WIN":
            print(f"  CLEARED at click {k} (state={state}, level_index={game.level_index})")
            return
        if not [f for f in model if f[2] >= 1]:
            print(f"  cascade lost at click {k} (no value-1 left)")
            break
        click = _sacrifice_choreograph(model, enemies, goal_c, lure_base, sink)
        if click is None:
            print(f"  plan done at click {k}")
            break
        cx = max(0, min(63, int(round(click[0]))))
        cy = max(10, min(62, int(round(click[1]))))
        model, enemies, _bad = _sim_click_sacrifice(model, enemies, cx, cy)
        _step_click(env, cx, cy)
        if reparse:
            live = _fruits(game)
            live_enemies = _enemies(game)
            model = [list(f) for f in live]
            # keep sim cooldowns, refresh enemy positions from live (index-matched)
            new_e = []
            for i, le in enumerate(live_enemies):
                cd = enemies[i][2] if i < len(enemies) else 0
                new_e.append([le[0], le[1], cd])
            enemies = new_e
    fin = game.level_index
    print(f"  FINAL level_index={fin} ({'CLEARED L%d' % idx if fin > idx else 'did NOT clear'})")


def search_sacrifice(arcade, idx: int = 4) -> None:
    """Search the spare-sacrifice plan (lure_base × sink-row); accept only plans
    that WIN under ALL ±1px perturbations, allowing value-0 kills but rejecting
    any value>=1 downgrade."""
    _env, game = _make_level(arcade, idx)
    fruits = _fruits(game)
    enemy = _enemies(game)
    goal_c, goal_bbox = _goal(game)
    print(f"L{idx} SACRIFICE search: fruits={fruits} enemies={enemy} goal_c={goal_c}")
    lure_bases = [16.0, 20.0, 24.0, 28.0, 32.0]
    sinks = [52.0, 56.0, 60.0]
    perturbs = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]
    results = []
    for lb in lure_bases:
        for sk in sinks:
            outs = []
            for dx, dy in perturbs:
                pf, pe = _perturb(fruits, enemy, dx, dy)
                outs.append(_run_plan_sacrifice(pf, pe, goal_c, goal_bbox, lb, sk))
            wins = sum(1 for o, _ in outs if o == "win")
            base_out, base_k = outs[0]
            robust = wins == len(perturbs)
            results.append((lb, sk, wins, len(perturbs), base_out, base_k, robust))
            tag = "  ROBUST-WIN" if robust else ""
            print(f"lure={lb:4.0f} sink={sk:4.0f}  wins={wins}/{len(perturbs)} base={base_out}@{base_k}{tag}")
    robust = [r for r in results if r[6]]
    print(f"\nSACRIFICE SEARCH SUMMARY L{idx}: {len(robust)} drift-robust winner(s) of {len(results)} configs")
    if not robust:
        best = max(results, key=lambda r: (r[2], -r[5]))
        print(
            f"  best (non-robust): lure={best[0]:.0f} sink={best[1]:.0f} "
            f"wins={best[2]}/{best[3]} base={best[4]}@{best[5]}"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=20)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--joint", action="store_true")
    ap.add_argument("--sacrifice", action="store_true")
    ap.add_argument("--val-sac", dest="val_sac", action="store_true")
    ap.add_argument("--live-sac", dest="live_sac", action="store_true")
    ap.add_argument("--reparse", action="store_true")
    ap.add_argument("--sink", type=float, default=56.0)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--live-joint", action="store_true")
    ap.add_argument("--lure", type=float, default=20.0)
    ap.add_argument("--park", default="midedge")
    ap.add_argument("--cross-gate", type=float, default=20.0)
    ap.add_argument("--level", type=int, default=3)
    args = ap.parse_args()
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    if args.sacrifice:
        search_sacrifice(arcade, args.level)
        return
    if args.val_sac:
        validate_sacrifice(arcade, args.lure, args.sink, args.level)
        return
    if args.live_sac:
        run_live_sacrifice(arcade, args.lure, args.sink, args.level, args.reparse)
        return
    if args.joint:
        search_joint(arcade, args.level)
        return
    if args.search:
        search(arcade, args.level)
        return
    if args.live_joint:
        run_live_joint(arcade, args.park, args.lure, args.cross_gate, args.level)
        return
    if args.live:
        run_live_openloop(arcade, args.lure, args.level)
        return
    for s in range(args.seeds):
        print(f"===== validation seed {s} (L{args.level}) =====")
        validate(arcade, args.frames, seed=s, idx=args.level)


if __name__ == "__main__":
    main()
