"""`induce.discover_lattice` across every sample game — where does a CLICK do something?

64 probes per game on a stride-8 grid, counter cells filtered. Two columns carry the finding:
the response FOOTPRINT (how many cells one click moves) and its KIND.

⛔ Three limits, all about this instrument rather than the games, all measured:

  * **it is click-only, so it is silent about movement.** Twelve games report nothing here and
    every one of them is driven by the simple actions. cn04 reports a clean uniform footprint
    and is a NAVIGATION game — its clicks blink a 15x15 body that moves under actions 1-5;
  * it reads ONE layer (`canonical_layer`), so a response drawn elsewhere reads as inert — sp80
    scores 0 and is known to answer a placement with a twenty-layer spill;
  * it probes stride 8, so controls finer or offset from that grid are invisible.

A zero is "no click response found by THIS sweep", never "this game ignores clicks".
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.adapters25.base import canonical_layer  # noqa: E402
from admorphiq.tools.induce import discover_lattice  # noqa: E402

Cell = tuple[int, int]


def blobs(cells: set[Cell]) -> list[list[Cell]]:
    seen: set[Cell] = set()
    out: list[list[Cell]] = []
    for cell in cells:
        if cell in seen:
            continue
        stack = [cell]
        seen.add(cell)
        group: list[Cell] = []
        while stack:
            y, x = stack.pop()
            group.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (y + dy, x + dx)
                if nxt in cells and nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        out.append(group)
    return out


def kind(delta: list[Cell]) -> str:
    """MOVE or EDIT? A uniform footprint means one operator OR one object translating.

    A move leaves two disjoint congruent blobs — the cells vacated and the cells occupied —
    where an edit leaves one. Measured on cn04, whose footprint column alone read as "a single
    135-cell operator" and whose 135 cells are a 15x15 body.
    """
    parts = blobs(set(delta))
    if len(parts) == 2 and abs(len(parts[0]) - len(parts[1])) <= max(2, len(delta) // 10):
        return "move"
    return "edit"


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    seen: set[str] = set()
    print(f"{'game':6s} {'resp':>4s} {'pitch':>5s} {'hud':>4s}  footprints / kind")
    for info in arcade.get_environments():
        title = (info.title or info.game_id).split("-")[0].lower()
        if title in seen:
            continue
        seen.add(title)
        env = arcade.make(info.game_id)
        box = [env.reset()]

        def probe(cell: Cell, _env=env, _box=box) -> tuple[list[list[int]], list[list[int]]]:
            before = canonical_layer(_box[0])
            _box[0] = _env.step(GameAction.ACTION6, data={"x": cell[1], "y": cell[0]})
            return before, canonical_layer(_box[0])

        report = discover_lattice(probe, 64, coarse=8, budget=64)
        sizes = sorted({len(v) for v in report["live"].values()})
        kinds = sorted({kind(v) for v in report["live"].values()})
        print(f"{title:6s} {len(report['live']):4d} {str(report['stride']):>5s} "
              f"{report['hud_cells']:4d}  {sizes[:6]} {kinds}")


if __name__ == "__main__":
    main()
