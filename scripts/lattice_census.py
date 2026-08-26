"""Which sample games are built on a lattice of equal tiles? One frame each, zero actions.

The stencil tool (r101) recovers its rule from a tile lattice. Before writing a second tool it
is worth knowing how many games even HAVE that substrate — a cheap census beats picking the
next game by intuition, and picking by intuition is what put four ports on the dispatch axis.

⛔ Read the ZEROS as a fact about this DETECTOR, not about the games. `tiles()` wants a solid,
square, single-block region, so a sokoban grid whose walls run together is one component and
scores 0 here while obviously being a lattice. The census is trustworthy only in the positive
direction: a game it marks really does present equal tiles on frame 1.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")
sys.path.insert(0, "scripts")

from arc_agi import Arcade, OperationMode  # noqa: E402

from admorphiq.adapters25.base import canonical_layer  # noqa: E402
from glyph_stencil_probe import _pitch, all_tiles, tiles  # noqa: E402


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    seen: set[str] = set()
    rows: list[tuple[str, int, int, int, int, int]] = []
    for info in arcade.get_environments():
        title = (info.title or info.game_id).split("-")[0].lower()
        if title in seen:
            continue
        seen.add(title)
        env = arcade.make(info.game_id)
        g = canonical_layer(env.reset())
        every = all_tiles(g)
        live = tiles(g)
        side = next(iter(every.values()))["size"] if every else 0
        rows.append((
            title, len(every), len(live), side,
            _pitch(list(every), side) if every else 0,
            sum(1 for t in every.values() if len(t["colours"]) > 1),
        ))
    rows.sort(key=lambda r: (-r[1], r[0]))
    print(f"{'game':6s} {'tiles':>5s} {'live':>5s} {'side':>4s} {'pitch':>5s} {'marked':>6s}")
    for r in rows:
        flag = "  <- lattice" if r[1] >= 6 and r[4] >= r[3] > 0 else ""
        print(f"{r[0]:6s} {r[1]:5d} {r[2]:5d} {r[3]:4d} {r[4]:5d} {r[5]:6d}{flag}")


if __name__ == "__main__":
    main()
