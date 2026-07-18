"""Verify the fog signature (colour-5 pixel count) cleanly separates L7 from
L1-L6, so an L7 gate can never mis-fire on an earlier level."""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.ls20 import Adapter
from admorphiq.adapters25.base import canonical_layer

ar = Arcade(operation_mode=OperationMode.OFFLINE)
env = ar.make("ls20"); obs = env.observation_space
ad = Adapter(giveup=9000); s = 0
seen = {}
while s < 9000 and obs.levels_completed < 7:
    lvl = obs.levels_completed
    grid = canonical_layer(obs)
    if grid and len(grid) >= 64:
        c5 = sum(1 for row in grid for v in row if v == 5)
        seen.setdefault(lvl, []).append(c5)
    a = ad.choose_action([], obs)
    obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    s += 1
for lvl in sorted(seen):
    xs = seen[lvl]
    print(f"L{lvl+1}: colour-5 px  min={min(xs)} max={max(xs)} median={sorted(xs)[len(xs)//2]} nframes={len(xs)}")
