"""Trace the L6 covering decisions inside the adapter to see where it stalls."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.re86 import Adapter
from admorphiq.adapters25.base import canonical_layer
from admorphiq.kernels import covering_offsets

ar = Arcade(operation_mode=OperationMode.OFFLINE)
env = ar.make("re86")
ad = Adapter(giveup=8000)
obs = env.observation_space
steps = 0
n6 = 0
while steps < 2500 and not ad.is_done([], obs):
    lv = int(getattr(obs, "levels_completed", 0) or 0)
    a = ad.choose_action([], obs)
    if lv == 5:
        grid = canonical_layer(obs)
        mk = ad._marker(grid)
        act = ad._active_movable(grid, mk) if mk else None
        line = f"s{steps} L6 marker={mk} act_color={act[0] if act else None} act_size={len(act[1]) if act else 0}"
        if act:
            tg = ad._targets_by_color.get(act[0], [])
            offs = covering_offsets(list(act[1]), tg) if tg else []
            nearest = min(offs, key=lambda o: abs(o[0])+abs(o[1])) if offs else None
            line += f" targets={len(tg)} nearest_off={nearest} n_offs={len(offs)}"
        line += f" -> {a.name if hasattr(a,'name') else a}  targets_locked={ad._targets_locked} tbc={{k:len(v) for k,v in ad._targets_by_color.items()}}"
        if n6 < 60 or steps % 100 == 0:
            print(line)
        n6 += 1
        if n6 > 700:
            break
    obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    steps += 1
print(f"FINAL levels={int(getattr(obs,'levels_completed',0) or 0)} steps={steps}")
