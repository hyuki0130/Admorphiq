"""WHICH object does the paint-order mutation bury? Name it, per game and per level.

Why this probe exists
---------------------
Rule 7ck measured that burial COUNT does not predict cost — r11l loses 7 sprites of 27 and
scores identically, g50t loses 1 of 18 and falls to 0.0000 — and concluded, correctly, that
*"what matters is WHICH object, not how many"*. `scripts/_zorder_occlude.py` counts the
buried sprites and reports their SIZES. It does not say what they are.

⭐ AND THE PREREQUISITE IS SETTLED. `scripts/_zorder_tape.py` replayed each game's own
296- / 187- / 692- / 83-action tape under the mutation: g50t, tu93, s5i5 and r11l all reach
the SAME levels in the SAME per-level action counts, so on these boards the mutation is
RENDER-ONLY by measurement and a score loss is the tool's, not a broken board's.

What it reports
---------------
Per level, for every sprite that goes from visible to invisible under the whole-list
reversal: its class name, its declared `name`/tag if it has one, its layer, its position,
its size in cells, and the distinct colours it is painted in. That is enough to match it
against the game's own source (`uv run python scripts/read_sample_games.py <game>`) and say
what it IS to the game — an avatar, a goal, a wall, a counter.

⛔ It also reports what BURIES it, because "a sprite vanished" is only half an attribution:
the sprite that now owns those cells is the one whose paint order changed the answer.

⚠️ STATIC, and says so. It paints each level's AUTHORED opening board with the game's own
camera rules. `ZOrderPatch.buried_max` measures the same quantity during play and is the
authority for what happens after the first action.

Both controls
-------------
POSITIVE — r11l must report 7 buried sprites across its levels (7ck's banked count), and
g50t exactly 1. A probe that finds nothing has measured nothing.
NEGATIVE — re86 must report ZERO buried on every level (7ck: *"0 of 19, nothing ever
hidden"*), and it still loses 0.0539 of score. A game with no burial must come back clean.

    bash scripts/pfan.sh zwho scripts/_zorder_who.py 4 "" 4
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "src"))

# g50t and tu93 are the two that fall to zero; r11l is the positive control (7 buried, no
# cost); re86 is the negative (0 buried, real cost).
GAMES = ["g50t", "tu93", "r11l", "re86"]


def _describe(sprite, owner_of: dict, buriers: dict) -> dict:
    import numpy as np

    px = np.asarray(getattr(sprite, "pixels", []))
    cols = sorted({int(c) for c in np.unique(px) if int(c) >= 0}) if px.size else []
    return {
        "class": type(sprite).__name__,
        "name": str(getattr(sprite, "name", "") or ""),
        "layer": int(getattr(sprite, "layer", -1)),
        "at": [int(getattr(sprite, "x", -1)), int(getattr(sprite, "y", -1))],
        "shape": list(px.shape) if px.size else [],
        "cells_before": owner_of.get(id(sprite), 0),
        "colours": cols,
        "buried_by": buriers.get(id(sprite), []),
    }


def main() -> None:
    import _zorder_occlude as zo
    import numpy as np

    arm = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    pick = sys.argv[2].strip().lower() if len(sys.argv) > 2 and sys.argv[2].strip() else ""
    name = pick if pick else GAMES[(arm - 1) % len(GAMES)]

    game_dir = zo.ROOT / name
    row: dict = {"game": name}
    mod = zo._load(zo._game_source(game_dir))
    sorts, raw = zo.camera_rules(mod)
    row["camera_sorts_by_layer"] = sorts

    out = []
    for i, level in enumerate(getattr(mod, "levels", None) or []):
        sprites = [s for s in level.get_sprites()
                   if not sorts or getattr(s, "is_visible", True)]
        gw, gh = level.grid_size or (64, 64)
        base = zo.paint_order(sprites, sorts)
        rev = zo.paint_order(list(sprites)[::-1], sorts)
        before = zo.visible_cells(sprites, base, gw, gh, raw)
        after = zo.visible_cells(sprites, rev, gw, gh, raw)
        buried = [s for s in sprites if before.get(id(s), 0) > 0 and after.get(id(s), 0) == 0]
        if not buried:
            out.append({"level": i + 1, "sprites": len(sprites), "buried": []})
            continue

        # WHO covers it now: repaint under the reversed order and read the owner of the
        # cells the buried sprite used to own.
        owner = np.full((gh, gw), -1, dtype=np.int64)
        for slot, sp in enumerate(rev):
            px = np.asarray(sp.pixels if raw else sp.render())
            sh, sw = px.shape
            x0, y0 = int(sp.x), int(sp.y)
            dx0, dy0, dx1, dy1 = max(0, x0), max(0, y0), min(gw, x0 + sw), min(gh, y0 + sh)
            if dx1 <= dx0 or dy1 <= dy0:
                continue
            reg = px[dy0 - y0:dy1 - y0, dx0 - x0:dx1 - x0]
            owner[dy0:dy1, dx0:dx1][reg >= 0] = slot
        buriers: dict[int, list] = {}
        for sp in buried:
            px = np.asarray(sp.pixels if raw else sp.render())
            sh, sw = px.shape
            x0, y0 = int(sp.x), int(sp.y)
            names: set[str] = set()
            for yy in range(max(0, y0), min(gh, y0 + sh)):
                for xx in range(max(0, x0), min(gw, x0 + sw)):
                    if px[yy - y0][xx - x0] < 0:
                        continue
                    o = int(owner[yy][xx])
                    if o >= 0 and rev[o] is not sp:
                        names.add(f"{type(rev[o]).__name__}"
                                  f"{'/' + str(rev[o].name) if getattr(rev[o], 'name', None) else ''}")
            buriers[id(sp)] = sorted(names)[:4]

        out.append({
            "level": i + 1,
            "sprites": len(sprites),
            "buried": [_describe(s, before, buriers) for s in buried],
        })
    row["levels"] = out
    row["total_buried"] = sum(len(r["buried"]) for r in out)
    print(json.dumps(row, sort_keys=True))


if __name__ == "__main__":
    main()
