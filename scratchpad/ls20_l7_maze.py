"""Find the L7 passable maze + refills + changers from the engine (GT)."""
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

# dump every attribute: lists of sprites, dicts, and any grid-like structure
for a in sorted(dir(g)):
    if a.startswith("_"): continue
    try:
        v = getattr(g, a)
    except Exception:
        continue
    t = type(v).__name__
    if isinstance(v, list):
        if v and hasattr(v[0], "x") and hasattr(v[0], "y"):
            print(f"g.{a}: list[{len(v)}] {type(v[0]).__name__} xy -> {[(o.x,o.y) for o in v][:12]}")
        elif v and hasattr(v[0], "sprite"):
            print(f"g.{a}: list[{len(v)}] {type(v[0]).__name__} sprite -> {[(o.sprite.x,o.sprite.y) for o in v][:12]}")
        elif v and isinstance(v[0], (int, float, str)):
            print(f"g.{a}: list[{len(v)}] scalar -> {v[:12]}")
        else:
            print(f"g.{a}: list[{len(v)}] of {type(v[0]).__name__ if v else '?'}")
    elif isinstance(v, dict):
        print(f"g.{a}: dict[{len(v)}] keys={list(v)[:8]}")
