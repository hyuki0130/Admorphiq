"""AR25 L1 coverage-reachability analysis (2026-07-16).

The BFS coverage planner is too shallow for L1's real solution depth. But the
geared dynamics are LINEAR, so 'can piece P cover goal G' reduces to: is there
a translation offset o with G subseteq (P + o), and is o reachable as an
integer combination of P's per-control shift vectors? This computes exactly
that for every learned moving piece against the color-11 goal — the decisive
solvability test.
"""

from __future__ import annotations

import sys
from math import gcd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameState  # noqa: E402

from admorphiq.adapters25.ar25 import Adapter, _mask_hud  # noqa: E402
from admorphiq.adapters25.base import canonical_layer, most_common_color, simple_action, state_name  # noqa: E402
from admorphiq.kernels import learn_geared_operators  # noqa: E402
from admorphiq.kernels.motion import frame_diff  # noqa: E402
from admorphiq.kernels.regions import find_regions  # noqa: E402

INV = {1: 2, 2: 1, 3: 4, 4: 3}


def masked(obs):
    return _mask_hud(canonical_layer(obs))


def step(env, a):
    return env.step(simple_action(a))


def probe_mode(env, obs, bg, tag):
    out = []
    base = masked(obs)
    for a in (1, 2, 3, 4):
        obs = step(env, a)
        out.append({"before": base, "after": masked(obs), "label": f"{tag}{a}"})
        obs = step(env, INV[a])
        if frame_diff(base, masked(obs))["cells"]:
            base = masked(obs)
    return obs, out


def reachable_lattice(shifts):
    """The set {(dr%g_r step), ...} — here: dr must be a multiple of gcd of all
    row-shift magnitudes, dc a multiple of gcd of all col-shift magnitudes,
    AND independently achievable. Returns (row_step, col_step): 0 means that
    axis is immovable."""
    row_mags = [abs(dr) for dr, dc in shifts.values() if dr]
    col_mags = [abs(dc) for dr, dc in shifts.values() if dc]
    rstep = 0
    for m in row_mags:
        rstep = gcd(rstep, m)
    cstep = 0
    for m in col_mags:
        cstep = gcd(cstep, m)
    return rstep, cstep


def covering_offsets(piece, goal):
    """All offsets o with goal subseteq (piece + o)."""
    piece = set(piece)
    goal = list(goal)
    g0 = goal[0]
    cands = {(g0[0] - p[0], g0[1] - p[1]) for p in piece}
    good = []
    for o in cands:
        if all((g[0] - o[0], g[1] - o[1]) in piece for g in goal):
            good.append(o)
    return good


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env_info = next(e for e in arcade.get_environments() if "ar25" in f"{e.game_id} {e.title or ''}".lower())
    env = arcade.make(env_info.game_id)
    obs = env.observation_space
    adapter = Adapter()
    n = 0
    while n < 400 and obs.levels_completed < 1:
        act = adapter.choose_action([], obs)
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        n += 1
        if obs.state == GameState.GAME_OVER:
            obs = step(env, 0)
    obs = step(env, 4)
    ref = masked(obs)
    bg = most_common_color(ref)
    H, W = len(ref), len(ref[0])

    obs, obsA = probe_mode(env, obs, bg, "A")
    obs = step(env, 5)
    obs, obsB = probe_mode(env, obs, bg, "B")
    obs = step(env, 5)
    model = learn_geared_operators(obsA + obsB, background=bg)

    moving_cells = set()
    for p in model["pieces"]:
        moving_cells |= p["cells"]
    static = {(r, c) for r, row in enumerate(ref) for c, v in enumerate(row) if v != bg and (r, c) not in moving_cells}
    goal_grid = tuple(tuple(ref[r][c] if (r, c) in static else bg for c in range(W)) for r in range(H))
    goals = [g for g in find_regions(goal_grid, background=bg) if g["size"] >= 20]
    print(f"goals: {[(g['color'], g['size'], g['bbox']) for g in goals]}")

    for goal in goals:
        gcells = frozenset(goal["cells"])
        print(f"\n=== goal color={goal['color']} size={goal['size']} ===")
        for p in sorted(model["pieces"], key=lambda x: -len(x["cells"])):
            if len(p["cells"]) < len(gcells):
                continue  # too small to cover
            offs = covering_offsets(p["cells"], gcells)
            rstep, cstep = reachable_lattice(p["shifts"])
            reach = [
                o for o in offs
                if (rstep and o[0] % rstep == 0 or o[0] == 0) and (cstep and o[1] % cstep == 0 or o[1] == 0)
            ]
            tag = f"colors={sorted(p['colors'])} size={len(p['cells'])} rowstep={rstep} colstep={cstep}"
            if offs:
                print(f"  piece {tag}: {len(offs)} covering offset(s) e.g. {offs[:3]}; reachable={reach[:5]}")
            else:
                print(f"  piece {tag}: shape does NOT translate-cover the goal (0 offsets)")
    print(f"\nstate={state_name(obs)} levels={obs.levels_completed}")


if __name__ == "__main__":
    main()
