import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
sys.path.insert(0, str(Path("scripts").resolve()))
from arc_agi import Arcade, OperationMode
from admorphiq.adapters25.lp85 import Adapter
from admorphiq.adapters25.base import canonical_layer
from arcengine import GameAction

arcade = Arcade(operation_mode=OperationMode.OFFLINE)
env = arcade.make("lp85")
obs = env.observation_space
adapter = Adapter()
steps = 0
while steps < 6000 and obs.levels_completed < 5:
    if adapter.is_done([], obs):
        break
    a = adapter.choose_action([], obs)
    obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
    if obs is None: break
    steps += 1
grid = canonical_layer(obs)
print(f"levels={obs.levels_completed} dims={len(grid)}x{len(grid[0])}")
# color legend counts
from collections import Counter
cnt = Counter(v for row in grid for v in row)
print("color counts:", dict(sorted(cnt.items())))
# print grid with single-char per cell (hex-ish)
sym = {v:('.' if v in (3,4) else format(v,'x')) for v in cnt}
for r,row in enumerate(grid):
    print(f"{r:2d} " + "".join(sym[v] for v in row))
