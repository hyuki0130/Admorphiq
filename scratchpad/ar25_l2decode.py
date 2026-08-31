"""AR25 L2 characterization (2026-07-16).

Drives the REAL adapter through L0 (reflection) + L1 (geared) to L2, then
characterizes L2: regions, whether the first move relocates (as L1 does),
whether ACTION5 toggles control modes, the geared model both modes yield, the
static goal(s), and whether a covering drive exists (alignment + reachability
+ a plan/execute attempt). Answers: same geared mechanic / new gears / new
mechanic.
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
from admorphiq.kernels import learn_geared_operators, plan_geared_coverage  # noqa: E402
from admorphiq.kernels.motion import _shift_groups, frame_diff  # noqa: E402
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


def covering_offsets(piece, goal):
    piece = set(piece)
    g0 = next(iter(goal))
    cands = {(g0[0] - p[0], g0[1] - p[1]) for p in piece}
    return [o for o in cands if all((g[0] - o[0], g[1] - o[1]) in piece for g in goal)]


def reach_steps(shifts):
    rmags = [abs(dr) for dr, dc in shifts.values() if dr]
    cmags = [abs(dc) for dr, dc in shifts.values() if dc]
    r = 0
    for m in rmags:
        r = gcd(r, m)
    c = 0
    for m in cmags:
        c = gcd(c, m)
    return r, c


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env_info = next(e for e in arcade.get_environments() if "ar25" in f"{e.game_id} {e.title or ''}".lower())
    env = arcade.make(env_info.game_id)
    obs = env.observation_space
    adapter = Adapter()
    n = 0
    while n < 400 and obs.levels_completed < 2:
        act = adapter.choose_action([], obs)
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        n += 1
        if obs.state == GameState.GAME_OVER:
            obs = step(env, 0)
    print(f"reached levels_completed={obs.levels_completed} in {n} actions, state={state_name(obs)}")
    if obs.levels_completed < 2:
        print("FAILED to reach L2"); return

    pre = masked(obs)
    bg = most_common_color(pre)
    H, W = len(pre), len(pre[0])
    avail = sorted({a if isinstance(a, int) else getattr(a, "value", None) for a in (obs.available_actions or [])} - {None})
    print(f"L2 start {H}x{W} bg={bg} available={avail}")
    print("L2 start regions (non-bg, top 12 by size):")
    for r in sorted(find_regions(pre, background=bg), key=lambda x: -x["size"])[:12]:
        print(f"  color={r['color']} size={r['size']} bbox={r['bbox']}")

    # does the first move relocate (staging like L1)?
    obs = step(env, 4)
    d = len(frame_diff(pre, masked(obs))["cells"])
    print(f"\nfirst move (ACTION4) changed {d} cells (relocation if large)")
    ref = masked(obs)

    has_toggle = 5 in avail
    obs, obsA = probe_mode(env, obs, bg, "A")
    obsB = []
    if has_toggle:
        obs = step(env, 5)
        obs, obsB = probe_mode(env, obs, bg, "B")
        obs = step(env, 5)
    model = learn_geared_operators(obsA + obsB, background=bg)
    print(f"\ngeared model: base_step={model['base_step']} labels={model['labels']} "
          f"pieces={len(model['pieces'])} moving_colors={sorted(model['moving_colors'])}")
    moving = set()
    for p in sorted(model["pieces"], key=lambda x: -len(x["cells"])):
        moving |= p["cells"]
        if len(p["cells"]) >= 5:
            print(f"  piece colors={sorted(p['colors'])} cells={len(p['cells'])} shifts={p['shifts']}")
    for p in model["pieces"]:
        moving |= p["cells"]

    static = {(r, c) for r, row in enumerate(ref) for c, v in enumerate(row) if v != bg and (r, c) not in moving}
    goal_grid = tuple(tuple(ref[r][c] if (r, c) in static else bg for c in range(W)) for r in range(H))
    goals = [g for g in find_regions(goal_grid, background=bg) if g["size"] >= 20]
    print(f"\nstatic goal clusters (>=20): {[(g['color'], g['size'], g['bbox']) for g in goals]}")

    for g in goals:
        gc = frozenset(g["cells"])
        print(f"\n-- goal color={g['color']} size={g['size']} --")
        for p in sorted(model["pieces"], key=lambda x: -len(x["cells"])):
            if len(p["cells"]) < len(gc):
                continue
            offs = covering_offsets(p["cells"], gc)
            rs, cs = reach_steps(p["shifts"])
            reach = [o for o in offs if (not o[0] or (rs and o[0] % rs == 0)) and (not o[1] or (cs and o[1] % cs == 0))]
            print(f"   piece colors={sorted(p['colors'])} size={len(p['cells'])} rowstep={rs} colstep={cs}: "
                  f"{len(offs)} covering offsets, reachable={reach[:4]}")

    plan = plan_geared_coverage(model["pieces"], [frozenset(g["cells"]) for g in goals], model["labels"], max_count=25)
    print(f"\nplan_geared_coverage(all goals): {'len=' + str(len(plan)) if plan else 'None'}")
    print(f"final state={state_name(obs)} levels={obs.levels_completed}")


if __name__ == "__main__":
    main()
