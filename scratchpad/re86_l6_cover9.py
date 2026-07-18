"""re86 L6: can movable-9 (the cross) cover its 4 target tips by pure TRANSLATION
(no reshape)? The feasibility probe returned on-board covering_offsets for it, so
test live: select movable-9, drive it marker-anchored by max_coverage_offset over
its 4 colour-9 target cells (routing around the inflated obstacle), and report how
many of the 4 cells its body covers at the best reachable offset.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _l5_movables, _station_boxes, _target_boxes, _l5_route
from admorphiq.adapters25.base import canonical_layer
from admorphiq.kernels import max_coverage_offset

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
OBST = (26, 37, 26, 37)  # obstacle bbox padded a touch


def marker(g):
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == 0:
                return (r, c)
    return None


def get(g, sb, color):
    for m in _l5_movables(g, set(), sb, subtract_boxes=False):
        if m["color"] == color:
            return m
    return None


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    steps = 0
    while steps < 2500 and int(getattr(obs, "levels_completed", 0) or 0) < 5 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a); steps += 1
    for _ in range(3):
        obs = env.step(A[5])
    g = canonical_layer(obs); _st, sb = _station_boxes(g)
    tb = _target_boxes(g)
    tgt9 = [(r, c) for r, c in tb if g[r][c] == 9]
    print(f"target-9 cells = {sorted(tgt9)}")
    dirmap = dict(ad._dir_global)
    move_ids = [1, 2, 3, 4]
    walls: set = set()
    shape_rel = None
    last = None
    for it in range(400):
        g = canonical_layer(obs); mk = marker(g); m = get(g, sb, 9)
        if m is None or mk is None:
            obs = env.step(A[5]); continue
        # select movable-9
        if abs(m["cen"][0] - mk[0]) > 15 or abs(m["cen"][1] - mk[1]) > 15:
            obs = env.step(A[5]); continue
        # wall learning
        if last is not None:
            pm, want = last
            adv = (mk[0] - pm[0]) * want[0] + (mk[1] - pm[1]) * want[1]
            if adv < 2:
                walls.add((pm[0] // 3 + want[0], pm[1] // 3 + want[1]))
        last = None
        if shape_rel is None:
            shape_rel = frozenset((r - mk[0], c - mk[1]) for r, c in m["cells"])
        cur = {(mk[0] + dr, mk[1] + dc) for dr, dc in shape_rel}
        covered = sum(1 for t in tgt9 if t in cur)
        if covered == len(tgt9):
            print(f"  it{it}: COVERED all {len(tgt9)}/4 at marker={mk}")
            break
        best = max_coverage_offset(list(cur), tgt9)
        if best is None:
            obs = env.step(A[5]); continue
        (odr, odc), cov = best
        goal = (mk[0] + odr, mk[1] + odc)
        half = 13
        act = _l5_route(mk, goal, half, [OBST], walls, dirmap, move_ids)
        if act is None:
            if it % 20 == 0:
                print(f"  it{it}: no route; cover={covered} best_cov={len(cov)} goal={goal} mk={mk}")
            obs = env.step(A[5]); continue
        last = (mk, dirmap[act])
        obs = env.step(A[act])
        if it % 25 == 0:
            print(f"  it{it}: mk={mk} covered={covered}/4 best_off={(odr,odc)} act={act}")
    g = canonical_layer(obs); mk = marker(g); m = get(g, sb, 9)
    cur = {(mk[0] + dr, mk[1] + dc) for dr, dc in shape_rel} if (mk and shape_rel) else set()
    print(f"FINAL covered {sum(1 for t in tgt9 if t in cur)}/4  movable-9 now {m['cen'] if m else None} bbox px={len(m['cells']) if m else 0}")


if __name__ == "__main__":
    main()
