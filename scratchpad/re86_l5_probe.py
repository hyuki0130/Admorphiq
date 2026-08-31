"""re86 L5 characterization: drive the adapter to L5 (levels_completed==4),
settle, dump frame-only perception (gates/stations/movables) + a GT tag
cross-check (dev-time read only)."""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _target_boxes, _station_boxes
from admorphiq.adapters25.base import canonical_layer, most_common_color
from admorphiq.kernels import find_regions

MOV_TAG, STA_TAG, GATE_TAG = "0031cppcuvqlbi", "0007dtbisvazhv", "0054xnsuqceejm"


def frame_movables(grid, gate_cells, station_boxes):
    bg = most_common_color(grid)
    exclude = {bg, 4, 2, 0}
    gc = set(gate_cells)
    out = []
    for reg in find_regions(grid, background=bg, gap=1):
        if reg["color"] in exclude:
            continue
        cells = frozenset(reg["cells"]) - gc
        if not (20 <= len(cells) <= 120):
            continue
        rs = [r for r, _ in cells]; cs = [c for _, c in cells]
        if max(rs) - min(rs) < 3 or max(cs) - min(cs) < 3:
            continue
        cen = (sum(rs) // len(cells), sum(cs) // len(cells))
        # skip station swatches
        if any(r0 - 1 <= cen[0] <= r1 + 1 and c0 - 1 <= cen[1] <= c1 + 1 for r0, c0, r1, c1 in station_boxes):
            continue
        out.append((reg["color"], cen, len(cells)))
    return out


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    obs = env.observation_space
    g = env._game
    ad = Adapter(giveup=6000)
    steps = 0
    while steps < 6000 and int(getattr(obs, "levels_completed", 0) or 0) < 4 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    lv = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"reached levels_completed={lv} @ {steps} state={str(obs.state)[-12:]}")
    if lv != 4:
        print("did NOT reach L5"); return
    # settle a couple frames
    for _ in range(2):
        obs = env.step(GameAction.ACTION5); steps += 1
    grid = canonical_layer(obs)
    gates = {}
    for (r, c) in _target_boxes(grid):
        gates.setdefault(grid[r][c], []).append((r, c))
    stations, station_boxes = _station_boxes(grid)
    gate_cells = [c for v in gates.values() for c in v]
    movs = frame_movables(grid, gate_cells, station_boxes)
    print("=== FRAME-ONLY PARSE (L5) ===")
    print("gates:", {k: len(v) for k, v in gates.items()}, gates)
    print("stations:", stations)
    print("movables:", movs)
    print("=== GT CROSS-CHECK ===")
    lvl = g.current_level
    for tag, name in [(MOV_TAG, "movable"), (STA_TAG, "station"), (GATE_TAG, "gate")]:
        sp = lvl.get_sprites_by_tag(tag)
        info = []
        for s in sp:
            cols = Counter(int(v) for row in s.pixels for v in row if v != -1)
            info.append((s.x, s.y, s.width, s.height, dict(cols)))
        print(f"  {name} ({len(sp)}):", info)


if __name__ == "__main__":
    main()
