"""AR25 L1 linearity-across-toggles check (2026-07-16).

Directly answers the precondition: does a mode-B press produce the SAME shift
after an A->B->A->B toggle round-trip as it did before? If toggles reset or
perturb piece positions, the 3-integer lattice framing breaks. Measures a
mode-B ACTION2 (down) shift, does a full mode round-trip, re-measures, and
compares.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameState  # noqa: E402

from admorphiq.adapters25.ar25 import Adapter, _mask_hud  # noqa: E402
from admorphiq.adapters25.base import canonical_layer, most_common_color, simple_action  # noqa: E402
from admorphiq.kernels.motion import _shift_groups  # noqa: E402


def masked(obs):
    return _mask_hud(canonical_layer(obs))


def step(env, a):
    return env.step(simple_action(a))


def measure_b2(env, obs, bg):
    """Shift of the color-4 piece under one mode-B ACTION2, restored after."""
    before = masked(obs)
    obs = step(env, 2)
    groups = {s: g for s, g in _shift_groups(before, masked(obs), bg).items() if s != (0, 0)}
    shift = next((s for s, g in groups.items() if 4 in g["colors"]), None)
    obs = step(env, 1)  # inverse (up) restores
    return shift, obs


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
    obs = step(env, 4)  # relocate -> mode A ref
    bg = most_common_color(masked(obs))

    obs = step(env, 5)  # -> mode B
    shift_before, obs = measure_b2(env, obs, bg)
    print(f"mode-B color-4 ACTION2 shift (first): {shift_before}")

    # full round-trip: B -> A -> B (and a horizontal excursion in A, undone)
    obs = step(env, 5)  # -> A
    obs = step(env, 3)  # A horizontal excursion
    obs = step(env, 4)  # undo it
    obs = step(env, 5)  # -> B again
    shift_after, obs = measure_b2(env, obs, bg)
    print(f"mode-B color-4 ACTION2 shift (after A<->B round-trip + A excursion): {shift_after}")

    print(f"LINEAR ACROSS TOGGLES: {shift_before == shift_after and shift_before is not None}")


if __name__ == "__main__":
    main()
