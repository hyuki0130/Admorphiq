"""AR25 L1 direct execution test: drive color-4 by the reachable covering
offset (24,-18) = A3x3 (mode A, -18 cols) + B2x8 (mode B, +24 rows). If the
geared coverage reading is right, this fires the level-complete WIN."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameState  # noqa: E402

from admorphiq.adapters25.ar25 import Adapter, _mask_hud  # noqa: E402
from admorphiq.adapters25.base import canonical_layer, simple_action, state_name  # noqa: E402


def masked(obs):
    return _mask_hud(canonical_layer(obs))


def step(env, a):
    return env.step(simple_action(a))


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
    print(f"L1 reached in {n} actions")
    obs = step(env, 4)  # relocate -> ref
    print(f"relocated. levels={obs.levels_completed} state={state_name(obs)}")

    # A3 x3 (mode A, -18 cols)
    for i in range(3):
        obs = step(env, 3)
        if obs.levels_completed >= 2 or obs.state == GameState.WIN:
            print(f"WIN during A3 #{i+1}"); print(f"levels={obs.levels_completed} state={state_name(obs)}"); return
    # toggle to mode B
    obs = step(env, 5)
    # B2 x8 (mode B, +24 rows)
    for i in range(8):
        obs = step(env, 2)
        print(f"  B2 #{i+1}: levels={obs.levels_completed} state={state_name(obs)}")
        if obs.levels_completed >= 2 or obs.state == GameState.WIN:
            print(f"*** WIN / level-up after B2 #{i+1} ***"); return
    print(f"final: levels={obs.levels_completed} state={state_name(obs)}")


if __name__ == "__main__":
    main()
