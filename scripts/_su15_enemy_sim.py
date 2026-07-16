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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=20)
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--lure", type=float, default=20.0)
    ap.add_argument("--level", type=int, default=3)
    args = ap.parse_args()
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    if args.search:
        search(arcade, args.level)
        return
    if args.live:
        run_live_openloop(arcade, args.lure, args.level)
        return
    for s in range(args.seeds):
        print(f"===== validation seed {s} (L{args.level}) =====")
        validate(arcade, args.frames, seed=s, idx=args.level)


if __name__ == "__main__":
    main()
