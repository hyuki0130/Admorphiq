"""Faithful AR25 L1 probe (2026-07-16).

Drives to L1 with the REAL adapter (clears L0), then interposes ACTION1-4 each
followed by ACTION7 (undo) and dumps the measured shift groups + what
learn_reflection_operators recovers. Faithful path: uses the same env-stepping
the runner uses (simple actions, env.step(action) with no data payload -- AR25
never issues ACTION6), and reads env internals only passively.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameState  # noqa: E402

from admorphiq.adapters25.ar25 import Adapter, _mask_hud  # noqa: E402
from admorphiq.adapters25.base import (  # noqa: E402
    canonical_layer,
    most_common_color,
    simple_action,
    state_name,
)
from admorphiq.kernels.motion import _shift_groups, learn_reflection_operators  # noqa: E402

GAME = "ar25"


def masked(obs):
    return _mask_hud(canonical_layer(obs))


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = arcade.get_environments()
    env_info = next(e for e in envs if GAME in f"{e.game_id} {e.title or ''}".lower())
    print(f"env: {env_info.game_id}  baseline0={env_info.baseline_actions}")
    env = arcade.make(env_info.game_id)
    obs = env.observation_space

    adapter = Adapter()
    # 1) Drive to L1 with the real adapter.
    steps = 0
    while steps < 400:
        if obs.levels_completed >= 1:
            break
        action = adapter.choose_action([], obs)
        if action.is_complex():
            obs = env.step(action, data=action.action_data.model_dump())
        else:
            obs = env.step(action)
        steps += 1
        if obs is None:
            print("obs None during drive"); return
        if obs.state == GameState.GAME_OVER:
            obs = env.step(simple_action(0))  # RESET
    print(f"reached levels_completed={obs.levels_completed} after {steps} adapter actions, state={state_name(obs)}")
    if obs.levels_completed < 1:
        print("FAILED to reach L1"); return

    # 2) Settle: capture L1 start board.
    start = masked(obs)
    bg = most_common_color(start)
    h, w = len(start), len(start[0])
    print(f"L1 board {h}x{w} bg={bg}")

    # region census on start
    from admorphiq.kernels.regions import find_regions
    regs = find_regions(start, background=bg)
    print(f"L1 start regions (non-bg): {len(regs)}")
    for r in sorted(regs, key=lambda x: -x["size"])[:12]:
        print(f"  color={r['color']} size={r['size']} bbox={r['bbox']}")

    # 3) Probe ACTION1-4 each with an undo restore.
    avail = [a if isinstance(a, int) else getattr(a, "value", None) for a in (obs.available_actions or [])]
    print(f"available_actions ids: {sorted(x for x in avail if x is not None)}")
    observations = []
    # Horizontal moves (3,4) first — they carry the load-bearing dynamics and
    # must be measured from the PRISTINE L1 start; 1/2 last (ACTION1 triggers a
    # large re-layout whose undo does not cleanly restore).
    for a in (3, 4, 1, 2):
        before = masked(obs)
        obs = env.step(simple_action(a))
        after = masked(obs)
        groups = _shift_groups(before, after, bg)
        moving = {s: g for s, g in groups.items() if s != (0, 0)}
        from admorphiq.kernels.motion import frame_diff
        n_before_start = len(frame_diff(start, before)["cells"])
        print(f"\nACTION{a} (before-vs-L1start diff={n_before_start} cells): "
              f"{len(moving)} moving group(s), state={state_name(obs)}, levels={obs.levels_completed}")
        for shift in sorted(moving):
            g = moving[shift]
            print(f"   shift={shift} cells={len(g['cells'])} colors={sorted(g['colors'])}")
        observations.append({"before": before, "after": after, "label": a})
        # undo to restore start board for the next probe
        obs = env.step(simple_action(7))
        restored = masked(obs)
        n_restore = len(frame_diff(before, restored)["cells"])
        if n_restore:
            print(f"   [warn] undo left {n_restore} cells un-restored")

    # 4) What does the kernel learn?
    model = learn_reflection_operators(observations, background=bg)
    print("\n=== learn_reflection_operators ===")
    print(f"axes={model['axes']}")
    print(f"piece_colors={sorted(model['piece_colors'])}")
    print(f"piece_cells={len(model['piece_cells'])}")
    print(f"delta_map={model['delta_map']}")
    print(f"moving_colors={sorted(model['moving_colors'])}")
    print(f"correspondences={len(model['correspondences'])}")


if __name__ == "__main__":
    main()
