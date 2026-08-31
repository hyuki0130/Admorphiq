"""AR25 L1 piece-switch probe (2026-07-16).

The geared horizontal drive of the ACTIVE piece cannot cover either static
goal, and vertical moves are inert on it. This checks the missing DOF: does
ACTION5 (cycle active piece) or ACTION6 (click-select) activate a DIFFERENT
piece whose motion (horizontal or vertical) could reach a goal? Also dumps the
moving groups' full bboxes so we can see whether any drive could ever align
rows with a goal.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameState  # noqa: E402

from admorphiq.adapters25.ar25 import Adapter, _mask_hud  # noqa: E402
from admorphiq.adapters25.base import canonical_layer, most_common_color, simple_action, state_name  # noqa: E402
from admorphiq.kernels.motion import _shift_groups, frame_diff  # noqa: E402


def masked(obs):
    return _mask_hud(canonical_layer(obs))


def step(env, a):
    return env.step(simple_action(a))


def probe_moves(env, obs, bg, tag):
    """Report which groups move under each of ACTION1-4 from the CURRENT board,
    returning to it via the opposite action so the board is preserved."""
    base = masked(obs)
    inv = {1: 2, 2: 1, 3: 4, 4: 3}
    for a in (1, 2, 3, 4):
        obs = step(env, a)
        after = masked(obs)
        groups = {s: g for s, g in _shift_groups(base, after, bg).items() if s != (0, 0)}
        desc = ", ".join(f"{sorted(g['colors'])}x{len(g['cells'])}@{s}" for s, g in sorted(groups.items()))
        print(f"  [{tag}] ACTION{a}: {len(groups)} moving -> {desc or 'none'}")
        obs = step(env, inv[a])
        if frame_diff(base, masked(obs))["cells"]:
            print(f"     [warn] ACTION{inv[a]} did not restore; resyncing base")
            base = masked(obs)
    return obs


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
    obs = step(env, 4)  # relocate
    bg = most_common_color(masked(obs))
    print(f"post-reloc, levels={obs.levels_completed} state={state_name(obs)} bg={bg}")

    print("\n== moves with piece #0 active ==")
    obs = probe_moves(env, obs, bg, "p0")

    # cycle active piece with ACTION5, re-probe
    for cyc in range(1, 5):
        before5 = masked(obs)
        obs = step(env, 5)
        d5 = len(frame_diff(before5, masked(obs))["cells"])
        print(f"\n== after {cyc}x ACTION5 (cycle) diff={d5} ==")
        obs = probe_moves(env, obs, bg, f"p{cyc}")

    print(f"\nfinal state={state_name(obs)} levels={obs.levels_completed}")


if __name__ == "__main__":
    main()
