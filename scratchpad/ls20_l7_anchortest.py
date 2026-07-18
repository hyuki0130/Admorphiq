"""Which post-loiter anchor yields a replayable plan? Test (49,5) full-life and
(19,15) full-life (death-reset), both with correct pushwalls + mover read fresh."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter, _snap_to_lattice
from ls20_l7_v2 import sim_bfs, _CELL, _STEP_FULL

ar = Arcade(operation_mode=OperationMode.OFFLINE)
env = ar.make("ls20"); obs = env.observation_space; g = env._game
ad = Adapter(giveup=9000); s = 0
while s < 9000 and obs.levels_completed < 6:
    a = ad.choose_action([], obs)
    obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a); s += 1
lvl = g.current_level
walls = frozenset((sp.x, sp.y) for sp in lvl.get_sprites_by_tag("ihdgageizm"))
refills = frozenset(_snap_to_lattice(sp.x, sp.y, 4, 0) for sp in lvl.get_sprites_by_tag("npxgalaybz"))
m = {"goal": (29,50), "req": (0,3,2), "walls": walls, "refills": refills,
     "static_changers": {(19,40):"shape",(9,40):"color"}, "mover_kind": "rot",
     "track": frozenset((54,y) for y in (5,10,15,20,25,30)),
     "pushwalls": {(34,31):(0,-1),(39,19):(0,1),(40,30):(-1,0)},
     "fj": frozenset(set(walls)|{(29,50)}), "step_full": _STEP_FULL//2}
mv = g.wsoslqeku[0]; mcur = (mv._sprite.x, mv._sprite.y, mv._dir)
for name, anchor in [
    ("(49,5) full life, taken={(49,5)}", (49,5,1,0,0,21,frozenset({(49,5)}),mcur)),
    ("(49,10) full life", (49,10,1,0,0,21,frozenset(),mcur)),
    ("(19,15) full life (death-reset)", (19,15,1,0,0,21,frozenset(),mcur)),
]:
    plan = sim_bfs(m, anchor, cap=8_000_000)
    print(f"{name}: plan_len={len(plan) if plan else None}", flush=True)

print("--- extra: current-state anchors with FULL refill set ---")
for name, anchor in [
    ("(49,20) band6 mover(54,25,2) taken={}", (49,20,1,0,0,6,frozenset(),(54,25,2))),
    ("(49,20) band12 taken={}", (49,20,1,0,0,12,frozenset(),(54,25,2))),
    ("(49,15) band17 taken={(49,5)}", (49,15,1,0,0,17,frozenset({(49,5)}),(54,25,2))),
]:
    plan = sim_bfs(m, anchor, cap=12_000_000)
    print(f"{name}: plan_len={len(plan) if plan else None}", flush=True)

print("--- (49,20) with (49,5) legitimately consumed (taken) ---")
for b in (6, 12, 18, 21):
    plan = sim_bfs(m, (49,20,1,0,0,b,frozenset({(49,5)}),(54,25,2)), cap=12_000_000)
    print(f"(49,20) band{b} taken={{(49,5)}}: plan_len={len(plan) if plan else None}", flush=True)

print("--- (49,20) taken={(49,5)} band threshold ---")
for b in (7, 8, 9, 10, 11):
    plan = sim_bfs(m, (49,20,1,0,0,b,frozenset({(49,5)}),(54,25,2)), cap=12_000_000)
    print(f"(49,20) band{b} taken={{(49,5)}}: plan_len={len(plan) if plan else None}", flush=True)

print("--- exact v6 anchor (49,20) band18 taken={} mover(54,25,0) ---")
for cap in (8_000_000, 16_000_000, 30_000_000):
    for d in (0, 2):
        plan = sim_bfs(m, (49,20,1,0,0,18,frozenset(),(54,25,d)), cap=cap)
        print(f"cap={cap} mover_dir={d}: plan_len={len(plan) if plan else None}", flush=True)
