"""Drive the ACTUAL adapter on re86 and trace its L4 controller state."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.re86 import Adapter

ar = Arcade(operation_mode=OperationMode.OFFLINE)
env = ar.make("re86")
obs = env.observation_space
ad = Adapter(giveup=2000)
steps = 0
last = -1
while steps < 2000 and not ad.is_done([], obs):
    a = ad.choose_action([], obs)
    obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    steps += 1
    lv = int(getattr(obs, "levels_completed", 0) or 0)
    if lv != last:
        print(f"step={steps} levels={lv} state={str(obs.state)[-12:]}", flush=True)
        last = lv
    if lv == 3 and steps % 30 == 0:
        pcs = ad._l4_pieces
        info = [(p["color"], p["centroid"]) for p in pcs] if pcs else None
        print(f"  step={steps} sel={ad._l4_sel} dir={sorted(ad._dir)} stations={bool(ad._l4_stations)} "
              f"assign={ad._l4_assign} pieces={info} blocked={len(ad._l4_blocked)}", flush=True)
print("FINAL levels", int(getattr(obs, "levels_completed", 0) or 0), "steps", steps, "state", str(obs.state)[-12:])
