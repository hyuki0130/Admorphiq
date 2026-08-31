"""g50t L2 bounded PROBE (no build): reach L2 with the shipped adapter (clears
L0+L1), then dump the L2 scene and classify — colour-9 blob inventory
(players/goal), colour-8 circuit cells (plates+barriers), autonomous movers
(enemies react to steps), available actions. Bank the classification in G50T.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.g50t import Adapter
from admorphiq.adapters25.base import canonical_layer, state_name, available_action_ids
from admorphiq.kernels import find_regions

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
     4: GameAction.ACTION4, 5: GameAction.ACTION5}


def reach_level(env, obs, target):
    ad = Adapter(giveup=4000)
    s = 0
    while s < 4000 and int(getattr(obs, "levels_completed", 0) or 0) < target and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs, s


def inv(grid):
    hist = {}
    for row in grid:
        for v in row:
            hist[v] = hist.get(v, 0) + 1
    regs = {}
    for r in find_regions(grid, background=None):
        c = r["color"]
        regs.setdefault(c, []).append((round(r["centroid"][0], 1), round(r["centroid"][1], 1), r["size"]))
    return hist, regs


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs, steps = reach_level(env, env.observation_space, 2)
    lvl = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"reached levels_completed={lvl} in {steps} adapter steps, state={state_name(obs)}")
    if lvl < 2:
        print("did NOT reach L2"); return
    grid = canonical_layer(obs)
    simple, a6 = available_action_ids(obs)
    print(f"available_actions simple={simple} a6={a6}")
    hist, regs = inv(grid)
    print(f"colour histogram: {dict(sorted(hist.items()))}")
    print(f"colour-9 blobs (player/goal): {regs.get(9, [])}")
    print(f"colour-8 cells (plates+barriers) count: {hist.get(8,0)}px; regions: {regs.get(8, [])}")
    # detect autonomous movers (enemies): issue a wall-blocked move and see what shifts
    g0 = grid
    obs2 = env.step(A[2]); g1 = canonical_layer(obs2)
    obs3 = env.step(A[2]); g2 = canonical_layer(obs3)
    def nine_cells(g):
        return sorted((round(r['centroid'][0],1), round(r['centroid'][1],1), r['size'])
                      for r in find_regions(g, background=None) if r['color']==9)
    print(f"nine blobs t0: {nine_cells(g0)}")
    print(f"nine blobs t1: {nine_cells(g1)}")
    print(f"nine blobs t2: {nine_cells(g2)}")
    # count distinct colour-8 connected regions (circuit elements)
    c8 = [r for r in find_regions(grid, background=None) if r['color']==8]
    print(f"colour-8 connected regions: {len(c8)} -> {[(round(r['centroid'][0],1),round(r['centroid'][1],1),r['size']) for r in c8]}")
    # track candidate enemy/hazard colours 1,2 across the same steps
    def cregs(g, col):
        return sorted((round(r['centroid'][0],1), round(r['centroid'][1],1), r['size'])
                      for r in find_regions(g, background=None) if r['color']==col)
    for col in (1, 2):
        print(f"colour-{col} t0={cregs(g0,col)} t1={cregs(g1,col)} t2={cregs(g2,col)}")
    # issue a few MORE moves and watch if colour-1/2 shift independent of the player
    gg = g2
    for k in range(4):
        gg = canonical_layer(env.step(A[4 if k % 2 == 0 else 3]))  # RIGHT/LEFT bounce
        print(f"  extra{k}: c1={cregs(gg,1)} c2={cregs(gg,2)} player9={[b for b in cregs(gg,9) if b[2]>=20]}")


if __name__ == "__main__":
    main()
