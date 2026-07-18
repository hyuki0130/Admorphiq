"""Dump L7 ground-truth geometry: mover track, refills, goal, changers, passable
maze. Used to compute disc visibility for a refill-chained observation post."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter

ar = Arcade(operation_mode=OperationMode.OFFLINE)
env = ar.make("ls20")
obs = env.observation_space
g = env._game
adapter = Adapter(giveup=9000)
steps = 0
while steps < 9000 and obs.levels_completed < 6:
    a = adapter.choose_action([], obs)
    obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    steps += 1
for _ in range(2):
    obs = env.step(GameAction.ACTION1)
print("reached L7 levels_completed", obs.levels_completed)

m = g.wsoslqeku[0]
trk = m.bfdcztirdu
print("mover sprite=(%d,%d) dir=%d" % (m._sprite.x, m._sprite.y, m._dir))
print("mover track sprite region: x=%d y=%d w=%d h=%d" % (trk.x, trk.y, trk.width, trk.height))
# enumerate on-track lattice cells (5px): cells whose top-left lies within region
tx0, ty0, tw, th = trk.x, trk.y, trk.width, trk.height
track_cells = []
for yy in range(ty0, ty0 + th, 5):
    for xx in range(tx0, tx0 + tw, 5):
        track_cells.append((xx, yy))
print("track_cells (5px lattice within region):", track_cells)

print("\npushwalls:", [(w.sprite.x, w.sprite.y, type(w).__name__) for w in g.hasivfwip])
print("goal:", [((gg.x, gg.y), (g.ldxlnycps[i], g.yjdexjsoa[i], g.ehwheiwsk[i])) for i, gg in enumerate(g.plrpelhym)])
print("avatar start:", (g.gudziatsk.x, g.gudziatsk.y), "token:", (g.fwckfzsyc, g.hiaauhahz, g.cklxociuu))
print("life current_steps:", g._step_counter_ui.current_steps)

# passable maze: the arena grid. Find changers + refills + walls by scanning
# engine sprite lists.
for a in dir(g):
    if a.startswith("__"): continue
    try:
        v = getattr(g, a)
    except Exception:
        continue
    if isinstance(v, list) and v and hasattr(v[0], "sprite"):
        try:
            pts = [(x.sprite.x, x.sprite.y) for x in v]
        except Exception:
            continue
        print(f"g.{a}: [{len(v)}] {type(v[0]).__name__} -> {pts[:12]}")
