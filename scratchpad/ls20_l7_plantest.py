"""Does a death-free L7 plan EXIST from a clean full-life anchor? Build the maze
from GT (walls/refills/goal/changers/pushwalls/mover-track), then sim_bfs from
(19,15),(1,0,0),life=21,mover=(54,10,0) with escalating caps."""
from __future__ import annotations
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.ls20 import Adapter, _detect_pushwalls_pixel, _find_refill_sprites, _snap_to_lattice
from admorphiq.adapters25.base import canonical_layer
from ls20_l7_v2 import sim_bfs, _CELL, _STEP_FULL

ar = Arcade(operation_mode=OperationMode.OFFLINE)
env = ar.make("ls20"); obs = env.observation_space; g = env._game
ad = Adapter(giveup=9000); s = 0
while s < 9000 and obs.levels_completed < 6:
    a = ad.choose_action([], obs)
    obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a); s += 1
lvl = g.current_level
OX, OY = 4, 0
walls = frozenset((sp.x, sp.y) for sp in lvl.get_sprites_by_tag("ihdgageizm"))
refills = frozenset(_snap_to_lattice(sp.x, sp.y, OX, OY) for sp in lvl.get_sprites_by_tag("npxgalaybz"))
goal = (29, 50); req = (0, 3, 2)
static_changers = {(19, 40): "shape", (9, 40): "color"}
track = frozenset((54, y) for y in (5, 10, 15, 20, 25, 30))
# pushwalls from the frame (settled): use the pixel detector on GT grid
grid = tuple(tuple(r) for r in canonical_layer(env.step(__import__("arcengine", fromlist=["GameAction"]).GameAction.ACTION1)))
pw = {(34,31):(0,-1),(39,19):(0,1),(40,30):(-1,0)}
print("GT pushwalls sprites:", [(w.sprite.x, w.sprite.y, type(w).__name__) for w in g.hasivfwip])
print("frame-detected pushwalls:", pw)
m = {"goal": goal, "req": req, "walls": walls, "refills": refills,
     "static_changers": static_changers, "mover_kind": "rot", "track": track,
     "pushwalls": pw, "fj": frozenset(set(walls) | {goal}), "step_full": _STEP_FULL // 2}
# mover current at this frame (after 1 settle move from (54,10) it advanced)
mv = g.wsoslqeku[0]
start = (g.gudziatsk.x, g.gudziatsk.y, g.fwckfzsyc, g.hiaauhahz, g.cklxociuu, 21,
         frozenset(), (mv._sprite.x, mv._sprite.y, mv._dir))
print("start:", start, "GT avatar/token/mover")
for cap in (2_000_000, 8_000_000, 30_000_000):
    t0 = time.time()
    plan = sim_bfs(m, start, cap=cap)
    print(f"cap={cap}: plan_len={len(plan) if plan else None} ({time.time()-t0:.1f}s)", flush=True)
    if plan:
        # replay open-loop
        from arcengine import GameAction
        A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4}
        won = False
        for i, act in enumerate(plan):
            obs = env.step(A[act])
            if obs is None: break
            if str(obs.state).endswith("WIN") or obs.levels_completed >= 7:
                print(f"*** sim plan REPLAYS to LIVE WIN at {i+1}/{len(plan)} ***"); won = True; break
        if not won:
            print("sim plan did NOT replay to a win; ended levels", obs.levels_completed, "state", obs.state)
        break
