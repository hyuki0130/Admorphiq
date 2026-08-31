"""AR25 L1 decode + coverage-drive test (2026-07-16).

Decisive build-vs-bank probe. Drives to L1 with the REAL adapter, relocates
the pieces into the play field with one move (the staging->play relocation
banked 2026-07-16), then:
  1) characterises the post-relocation board (regions, static vs moving),
  2) measures the geared per-group displacement under horizontal moves,
  3) lockstep-validates the learned linear model against a fresh probe,
  4) searches a net horizontal drive whose union footprint covers the largest
     static cluster (goal candidate), executes it, and reports whether WIN /
     levels_completed fires.

If (4) clears L1 -> the mechanic is drive-to-cover and the geared kernel build
is worthwhile. If not -> the goal needs more than driving images onto targets;
bank.
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
from admorphiq.kernels.motion import _shift_groups, frame_diff  # noqa: E402
from admorphiq.kernels.regions import find_regions  # noqa: E402

GAME = "ar25"


def masked(obs):
    return _mask_hud(canonical_layer(obs))


def step(env, a):
    return env.step(simple_action(a))


def moving_of(before, after, bg):
    groups = _shift_groups(before, after, bg)
    return {s: g for s, g in groups.items() if s != (0, 0)}


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = arcade.get_environments()
    env_info = next(e for e in envs if GAME in f"{e.game_id} {e.title or ''}".lower())
    env = arcade.make(env_info.game_id)
    obs = env.observation_space
    adapter = Adapter()
    print(f"env={env_info.game_id} baseline={env_info.baseline_actions}")

    # 1) drive to L1
    n = 0
    while n < 400 and obs.levels_completed < 1:
        act = adapter.choose_action([], obs)
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        n += 1
        if obs.state == GameState.GAME_OVER:
            obs = step(env, 0)
    print(f"reached L1 in {n} actions, state={state_name(obs)}")

    # 2) relocate with one move, capture post-reloc board B0
    obs = step(env, 4)
    B0 = masked(obs)
    bg = most_common_color(B0)
    print(f"\npost-reloc board bg={bg}, state={state_name(obs)}, levels={obs.levels_completed}")

    # 3) probe ACTION4 -> shifts, ACTION3 -> return
    a4 = masked(obs := step(env, 4))
    mv4 = moving_of(B0, a4, bg)
    obs = step(env, 3)  # opposite, should return toward B0
    back = masked(obs)
    print(f"ACTION4 from B0: {len(mv4)} moving groups; ACTION3-return diff-vs-B0={len(frame_diff(B0, back)['cells'])} cells")
    for s in sorted(mv4):
        g = mv4[s]
        print(f"   shift={s} cells={len(g['cells'])} colors={sorted(g['colors'])}")

    moving_colors = set()
    for g in mv4.values():
        moving_colors |= set(g["colors"])
    print(f"moving_colors={sorted(moving_colors)}")

    # 4) characterise regions on B0; goal = largest static (non-moving-color) cluster
    regs = find_regions(B0, background=bg)
    static = [r for r in regs if r["color"] not in moving_colors]
    static.sort(key=lambda r: -r["size"])
    print(f"\nB0 regions: {len(regs)} total, {len(static)} static (non-moving-color)")
    for r in static[:8]:
        print(f"   static color={r['color']} size={r['size']} bbox={r['bbox']}")
    if not static:
        print("NO static cluster -> goal is not a static glyph here. BANK."); return
    goal = frozenset(static[0]["cells"])
    print(f"goal candidate: color={static[0]['color']} size={len(goal)} bbox={static[0]['bbox']}")

    # 5) learn per-group per-press displacement (from the ACTION4 probe), build
    #    reference footprints by color membership in B0, search net horizontal n.
    #    disp per group under one ACTION4 press:
    group_disp = []  # (ref_cells, per_press_shift)
    for s, g in mv4.items():
        colors = g["colors"]
        ref_cells = frozenset(
            (r, c) for r, row in enumerate(B0) for cc, v in enumerate(row) for c in [cc] if v in colors
        )
        group_disp.append((ref_cells, s))
    # dedupe by color to avoid double count already handled by color-membership union
    def render(net_presses: int) -> frozenset:
        u = set()
        for ref_cells, (dr, dc) in group_disp:
            u |= {(r + dr * net_presses, c + dc * net_presses) for (r, c) in ref_cells}
        return frozenset(u)

    # lockstep: does render(1) match the actual ACTION4 board's moving footprint?
    # Compare predicted moved cells to a4's foreground of moving colors.
    a4_moving_fg = frozenset(
        (r, c) for r, row in enumerate(a4) for c, v in enumerate(row) if v in moving_colors
    )
    pred1 = render(1) & frozenset((r, c) for r in range(len(B0)) for c in range(len(B0[0])))
    iou = len(pred1 & a4_moving_fg) / max(1, len(pred1 | a4_moving_fg))
    print(f"\nlockstep render(1) vs actual ACTION4 moving-fg: IoU={iou:.3f} "
          f"(pred={len(pred1)} actual={len(a4_moving_fg)})")

    # search net horizontal presses for coverage of goal
    H, W = len(B0), len(B0[0])
    best = None
    for net in range(-25, 26):
        u = render(net)
        if goal <= u:
            best = net
            break
    print(f"coverage search: best net presses = {best}")
    if best is None:
        print("NO reachable horizontal drive covers the goal. Likely needs more. Candidate BANK.")
        # still try a raw sweep as a fallback sanity check
    else:
        # execute best: sign -> action, |best| presses (we are currently at net 0 = B0)
        act = 4 if best > 0 else 3
        for _ in range(abs(best)):
            obs = step(env, act)
            if obs.levels_completed >= 2 or obs.state == GameState.WIN:
                break
        print(f"executed {abs(best)}x ACTION{act}: state={state_name(obs)} levels={obs.levels_completed}")
        return

    # fallback: brute horizontal sweeps both directions, watch for level up
    print("\n-- fallback raw sweep --")
    for act in (4, 3):
        for k in range(1, 20):
            obs = step(env, act)
            if obs.levels_completed >= 2 or obs.state == GameState.WIN:
                print(f"  RAW: ACTION{act} x{k} -> levels={obs.levels_completed} state={state_name(obs)}")
                return
        # return to B0-ish
        for _ in range(19):
            obs = step(env, 3 if act == 4 else 4)
    print("  raw sweep did not clear L1")


if __name__ == "__main__":
    main()
