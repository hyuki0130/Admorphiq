"""Drive the ACTUAL adapter through L5 and log its internal L5 state each step,
to find where the port diverges from the proven ctrl2 controller."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.re86 import Adapter

ar = Arcade(operation_mode=OperationMode.OFFLINE)
env = ar.make("re86")
ad = Adapter(giveup=6000)
obs = env.observation_space
steps = 0
last_phase = None
printed = 0
while steps < 1500 and not ad.is_done([], obs):
    lv = int(getattr(obs, "levels_completed", 0) or 0)
    a = ad.choose_action([], obs)
    if lv == 4:  # L5
        ph = ad._l5_phase
        gc = {c: len(v) for c, v in ad._l5_gate_acc.items()}
        pcs = None
        if ad._l5_pieces is not None:
            pcs = [(p["orig"], p["color"], p["target"], p["phase"], p["cen"], p.get("is_single")) for p in ad._l5_pieces]
        if ph != last_phase or printed < 60 or steps % 100 == 0:
            print(f"s{steps} lv{lv} phase={ph} settle={ad._l5_settle} reveal_steps={ad._l5_reveal_steps} "
                  f"stable={ad._l5_stable} gates={gc} order={ad._l5_order} act={a.name if hasattr(a,'name') else a}")
            if pcs and (ph != last_phase or printed < 60):
                print(f"    pieces={pcs}")
            printed += 1
        last_phase = ph
    obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    steps += 1
print(f"FINAL steps={steps} levels={int(getattr(obs,'levels_completed',0) or 0)}")
