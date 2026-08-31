"""AR25 L1 geared-coverage live validation (2026-07-16).

Decisive ship-vs-bank measurement for the geared-copy kernel. Drives to L1,
relocates, probes BOTH control modes (ACTION5-toggled), learns the geared
model with learn_geared_operators, detects the static goal glyph(s) by
POSITION (colour-agnostic — colour 5 is both a moving piece and a static
goal), plans coverage with plan_geared_coverage, and EXECUTES the plan to see
whether WIN / levels_completed fires.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameState  # noqa: E402

from admorphiq.adapters25.ar25 import Adapter, _mask_hud  # noqa: E402
from admorphiq.adapters25.base import canonical_layer, most_common_color, simple_action, state_name  # noqa: E402
from admorphiq.kernels import learn_geared_operators, plan_geared_coverage, render_geared  # noqa: E402
from admorphiq.kernels.motion import frame_diff  # noqa: E402
from admorphiq.kernels.regions import find_regions  # noqa: E402

INV = {1: 2, 2: 1, 3: 4, 4: 3}


def masked(obs):
    return _mask_hud(canonical_layer(obs))


def step(env, a):
    return env.step(simple_action(a))


def probe_mode(env, obs, bg, mode_tag):
    """Probe ACTION1-4 from the current board, returning to it each time via
    the inverse move; yield observations labelled '<mode><action>'."""
    obs_list = []
    base = masked(obs)
    for a in (1, 2, 3, 4):
        obs = step(env, a)
        after = masked(obs)
        obs_list.append({"before": base, "after": after, "label": f"{mode_tag}{a}"})
        obs = step(env, INV[a])
        if frame_diff(base, masked(obs))["cells"]:
            base = masked(obs)  # resync if inverse didn't fully restore
    return obs, obs_list, base


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
    obs = step(env, 4)  # relocate into play field
    ref = masked(obs)
    bg = most_common_color(ref)
    H, W = len(ref), len(ref[0])
    print(f"L1 reached+relocated; ref {H}x{W} bg={bg} state={state_name(obs)}")

    # probe mode A, toggle to mode B, probe, toggle back
    obs, obsA, baseA = probe_mode(env, obs, bg, "A")
    obs = step(env, 5)  # toggle to mode B (pieces don't move; marker only)
    obs, obsB, baseB = probe_mode(env, obs, bg, "B")
    obs = step(env, 5)  # toggle back to mode A
    back = masked(obs)
    print(f"after full probe, board diff-vs-ref = {len(frame_diff(ref, back)['cells'])} cells")

    model = learn_geared_operators(obsA + obsB, background=bg)
    print(f"\ngeared model: base_step={model['base_step']} labels={model['labels']}")
    print(f"pieces={len(model['pieces'])} moving_colors={sorted(model['moving_colors'])}")
    moving_cells = set()
    for p in sorted(model["pieces"], key=lambda x: -len(x["cells"]))[:8]:
        moving_cells |= p["cells"]
        print(f"  piece colors={sorted(p['colors'])} cells={len(p['cells'])} shifts={p['shifts']}")
    for p in model["pieces"]:
        moving_cells |= p["cells"]

    # lockstep: render at one A4 press vs actual
    a4 = masked(step(env, 4))
    obs = step(env, 3)  # restore
    pred = render_geared(model["pieces"], {"A4": 1})
    pred_on = frozenset((r, c) for (r, c) in pred if 0 <= r < H and 0 <= c < W)
    actual_moving = frozenset(
        (r, c) for r, row in enumerate(a4) for c, v in enumerate(row)
        if v in model["moving_colors"] and (r, c) not in moving_cells or
        (v in model["moving_colors"])
    )
    # simpler: compare predicted moved cells to actual foreground of moving colors
    actual_fg = frozenset((r, c) for r, row in enumerate(a4) for c, v in enumerate(row) if v in model["moving_colors"])
    iou = len(pred_on & actual_fg) / max(1, len(pred_on | actual_fg))
    print(f"lockstep render(A4=1) vs actual moving-fg IoU={iou:.3f} (pred={len(pred_on)} actual={len(actual_fg)})")

    # goals = static clusters by POSITION (reference fg not in any moving piece)
    static_cells = {
        (r, c) for r, row in enumerate(ref) for c, v in enumerate(row)
        if v != bg and (r, c) not in moving_cells
    }
    # cluster static cells via find_regions on a masked copy
    goal_grid = tuple(
        tuple(ref[r][c] if (r, c) in static_cells else bg for c in range(W)) for r in range(H)
    )
    goals = sorted(find_regions(goal_grid, background=bg), key=lambda x: -x["size"])
    big = [frozenset(g["cells"]) for g in goals if g["size"] >= 20]
    print(f"\nstatic goal clusters (size>=20): {[(g['color'], g['size'], g['bbox']) for g in goals if g['size']>=20]}")

    bounds = (H, W)
    for label, tgts in (("both goals", big), ("largest goal", big[:1])):
        if not tgts:
            continue
        plan = plan_geared_coverage(model["pieces"], tgts, model["labels"], max_count=25, max_states=400000)
        print(f"plan_geared_coverage[{label}]: {'FOUND len=' + str(len(plan)) if plan is not None else 'None'}")
        if plan:
            counts = {}
            for lab, d in plan:
                counts[lab] = counts.get(lab, 0) + d
            print(f"   net counts = {counts}")
            # execute: group by mode. currently in mode A at ref.
            _execute(env, counts)
            obs2 = env.observation_space
            print(f"   after execute: state={state_name(obs2)} levels={obs2.levels_completed}")
            return
    print("\nNo covering configuration found under the geared model within bounds.")


def _execute(env, counts):
    """Do mode-A labelled presses, toggle to B, do mode-B presses. Net count
    n>0 -> action n times; n<0 -> inverse action |n| times."""
    def do(label, n):
        a = int(label[1])
        act = a if n > 0 else INV[a]
        for _ in range(abs(n)):
            step(env, act)
    for label, n in counts.items():
        if label.startswith("A") and n:
            do(label, n)
    if any(l.startswith("B") and n for l, n in counts.items()):
        step(env, 5)
        for label, n in counts.items():
            if label.startswith("B") and n:
                do(label, n)


if __name__ == "__main__":
    main()
