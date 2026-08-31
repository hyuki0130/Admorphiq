"""g50t L1 SLAM stage 1: per-move SCROLL VECTOR estimator (dead-reckoning foundation).

Under camera-lock the player is pinned at screen cell (3,4); a SUCCESSFUL move
scrolls the whole world 6px opposite the move direction, a wall-blocked move
leaves the interior unchanged. Rather than the noisy binary floor_symdiff, this
measures the FULL interior CONTENT shift by cross-correlation: for each pair of
consecutive frames find the integer pixel offset (dr,dc) that best aligns the
interior (minimizes mismatch of the overlap). That offset IS the scroll; ÷6 =
the confirmed move in cells (opposite sign = the player's world displacement).

Goal: validate that (a) each real move produces a clean ±6px axis-aligned shift,
(b) a blocked move produces (0,0), and (c) the lag between issuing a move and
seeing its shift is uniform, so dead-reckoning world_pos = spawn + Σ moves works.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}
CELL = 6
# interior play area (border fixed at pixel bbox (7,7,55,55)); crop inside it and
# drop the bottom HUD-flicker rows.
R0, R1, C0, C1 = 8, 54, 8, 55


def reach_l1(env, obs):
    ad = Adapter(giveup=2000)
    s = 0
    while s < 2000 and int(getattr(obs, "levels_completed", 0) or 0) < 1 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def interior(grid):
    return [row[C0:C1] for row in grid[R0:R1]]


def best_shift(g0, g1, rng=8):
    """Integer (dr,dc) shift applied to g1 that best matches g0 over the overlap.
    Returns (dr, dc, mismatch_fraction). Small mismatch => a clean rigid scroll."""
    h = len(g0)
    w = len(g0[0])
    best = (0, 0, 1.0)
    for dr in range(-rng, rng + 1):
        for dc in range(-rng, rng + 1):
            miss = 0
            tot = 0
            for r in range(h):
                r1 = r + dr
                if r1 < 0 or r1 >= h:
                    continue
                row0 = g0[r]
                row1 = g1[r1]
                for c in range(w):
                    c1 = c + dc
                    if c1 < 0 or c1 >= w:
                        continue
                    tot += 1
                    if row0[c] != row1[c1]:
                        miss += 1
            if tot < h * w * 0.4:
                continue
            frac = miss / tot
            if frac < best[2]:
                best = (dr, dc, frac)
    return best


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1")
        return
    g_prev = interior(canonical_layer(obs))
    # DOWN,DOWN,DOWN, RIGHT,RIGHT,RIGHT, UP,UP,UP, LEFT,LEFT,LEFT, mix
    seq = [2, 2, 2, 4, 4, 4, 1, 1, 1, 3, 3, 3, 2, 4, 1, 3]
    names = {1: "UP", 2: "DN", 3: "LF", 4: "RT"}
    print("move  -> shift(dr,dc) mismatch  (shift/6 = scroll cells)")
    for k, a in enumerate(seq):
        obs = env.step(A[a])
        g = interior(canonical_layer(obs))
        dr, dc, frac = best_shift(g_prev, g)
        cell = (dr // CELL if dr % CELL == 0 else dr / CELL,
                dc // CELL if dc % CELL == 0 else dc / CELL)
        print(f"  step{k:2d} {names[a]} -> shift=({dr:+d},{dc:+d}) miss={frac:.3f} cells={cell}")
        g_prev = g


if __name__ == "__main__":
    main()
