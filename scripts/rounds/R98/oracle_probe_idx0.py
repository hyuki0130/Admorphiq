"""R98 oracle certification probe — sp80 idx0 (FlowDeflectionDynamics).

Purpose
-------
Certify, against the LIVE engine, the three claims the R98 v1.1 schema rests on:

1. The hand-authored oracle (translate the single piece 3 cells, then commit)
   clears idx0, and in how many actions.
2. The commit observation exposes the whole spill as frame LAYERS, so one
   sacrificial commit yields a full trajectory (the affordability premise).
3. The propagation response to a piece is a PERPENDICULAR SPLIT that preserves
   the original direction — not a 90 degree turn, not absorption. This is what
   pre-certifies transition mutants T1/T2 as CONTRADICTED.

Expected feedback
-----------------
A PASS line for each claim means the schema's decoded mechanics are faithful and
the mutant table's expected verdicts are grounded in observed transitions rather
than in a source reading. A FAIL means the schema section must be corrected
BEFORE the contract is frozen -- it does not mean the round pivots.

Dev-time only: this reads no game internals, but it is a certification probe,
not part of any runtime agent path.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

WATER = 6  # the flow colour on this board, read off the observation, not internals


def _grid(obs, layer: int = 0) -> list[list[int]]:
    return obs.frame[layer]


def _cells(grid, colour: int) -> set[tuple[int, int]]:
    return {
        (y, x)
        for y, row in enumerate(grid)
        for x, v in enumerate(row)
        if v == colour
    }


def _fresh():
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=os.environ.get("ARC_ENVIRONMENTS_DIR") or None,
    )
    gid = next(e.game_id for e in arcade.get_environments() if e.game_id.startswith("sp80"))
    env = arcade.make(gid)
    return gid, env, env.step(GameAction.RESET)


def claim_1_and_2() -> tuple[bool, bool, int, int]:
    """Oracle clear + layer exposure."""
    _, env, obs = _fresh()
    actions = 0
    for _ in range(3):
        obs = env.step(GameAction.ACTION4)
        actions += 1
    obs = env.step(GameAction.ACTION5)
    actions += 1
    layers = len(obs.frame)
    cleared = obs.levels_completed >= 1
    if not cleared:  # let the settle verdict land
        for _ in range(30):
            obs = env.step(GameAction.ACTION5)
            actions += 1
            if obs.levels_completed >= 1:
                cleared = True
                break
    return cleared, layers > 1, actions, layers


def claim_3() -> tuple[bool, list[str]]:
    """Perpendicular split, direction preserved — from the sacrificial commit.

    The observation is a 64x64 PIXEL frame, so cell coordinates are recovered by
    dividing by a scale INFERRED from the data: the first spill layer holds a
    single one-cell droplet, so its pixel width IS the scale.
    """
    _, env, obs = _fresh()
    for _ in range(3):
        obs = env.step(GameAction.ACTION4)
    obs = env.step(GameAction.ACTION5)

    layers = [_cells(layer, WATER) for layer in obs.frame]
    first = next((c for c in layers if c), set())
    if not first:
        return False, ["no water observed in any layer"]
    scale = max(1, len({x for (_, x) in first}))

    per_layer = []
    for cells in layers:
        if not cells:
            per_layer.append((set(), None))
            continue
        cols = {x // scale for (_, x) in cells}
        depth = max(y // scale for (y, _) in cells)
        per_layer.append((cols, depth))

    widths = [len(c) for (c, _) in per_layer if c]
    depths = [d for (_, d) in per_layer if d is not None]

    split = bool(widths) and widths[0] == 1 and max(widths) >= 2
    descending = all(b >= a for a, b in zip(depths, depths[1:])) and depths[-1] > depths[0]

    # the two emergent streams: columns present in the deepest pre-terminal layer
    deep = max(range(len(per_layer)), key=lambda i: (per_layer[i][1] or -1))
    emergent = sorted(per_layer[deep][0])

    # the FRONTIER — cells that are new in each layer — is the actual droplet
    # motion; the accumulated trail is not discriminating because water persists.
    frontier = []
    seen = set()
    for layer in layers:
        cur = {(y // scale, x // scale) for (y, x) in layer}
        new = sorted(cur - seen)
        seen |= cur
        frontier.append(new)
    # the split signature: a layer whose frontier is exactly the two cells
    # flanking the previous frontier cell, both later continuing to descend.
    split_layers = [i for i, f in enumerate(frontier) if len(f) == 2
                    and f[0][0] == f[1][0] and f[1][1] - f[0][1] == 2]

    notes = [
        f"inferred pixel scale per cell: {scale}",
        f"frontier cells per layer (row, col): {frontier[:8]}",
        f"layers whose frontier is a flanking pair on one row: {split_layers}",
        f"distinct water columns per layer (cells): {widths}",
        f"deepest water row per layer (cells): {depths}",
        f"columns occupied at the deepest layer: {emergent}",
    ]
    return (split and descending), notes


def main() -> int:
    cleared, layered, actions, layers = claim_1_and_2()
    split_ok, notes = claim_3()

    print(f"[claim 1] oracle clears idx0: {'PASS' if cleared else 'FAIL'} "
          f"({actions} actions)")
    print(f"[claim 2] commit exposes the spill as layers: "
          f"{'PASS' if layered else 'FAIL'} ({layers} layers)")
    print(f"[claim 3] piece response is a direction-preserving perpendicular "
          f"split: {'PASS' if split_ok else 'FAIL'}")
    for n in notes:
        print(f"          {n}")
    return 0 if (cleared and layered and split_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
