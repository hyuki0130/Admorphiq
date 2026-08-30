"""What the paint-order mutation actually DESTROYS, per game and per level.

⛔ THE QUESTION THIS ANSWERS IS THE ONE THE SCORE CANNOT. A game that scores lower under
the z-order arm is either a tool reading PAINT ORDER where the mechanic was available
another way (a transfer failure, and the tool's problem) or a board whose evidence the
mutation removed outright (a harder board, and nobody's problem) — rule 7ce's shift1
lesson: "a broken mutation and a brittle tool produce the same lower number, and only the
accounting separates them".

WHAT IT COUNTS, per level's opening board: how many sprites go from having at least one
visible cell to having NONE. A sprite that vanishes entirely is evidence deleted; a sprite
that merely swaps a few cells with a neighbour is evidence relocated. s5i5's L4 is the
calibration point — rule 7cd's own reading is that ONE cell of the rider is covered there,
so the arm's smallest real effect is a single cell and anything much larger is a different
kind of change.

⛔ ORDER IS TAKEN FROM THE GAME'S OWN CAMERA, NOT ASSUMED. s5i5, tu93 and wa30 override
`Camera._raw_render` with a version that never sorts, so their paint order is the raw list
order; the other 22 paint `sorted(key=layer)`, stable. Painting all 25 the same way would
answer a question about a different game — that error is exactly what cost the first
mutation arm its positive control.

⛔ AND IT READS THE PIXELS THE GAME'S OWN CAMERA READS. `render()` applies rotation,
mirroring and scale; s5i5's and wa30's overrides take `sprite.pixels` RAW. An earlier
version refused any game where the two differ, which knocked out 15 of the 25 including
four of the five movers — the accessor is detected from the override's source instead.

⚠️ IT IS STATIC AND SEES ONLY THE AUTHORED BOARDS. `ZOrderPatch`'s own `buried_max`
measures the same quantity DURING PLAY, with the camera itself deciding visibility, and
that is the authority: g50t's authored level 1 shows nothing moving while 586 of its 2,852
live frames change.

    bash scripts/pfan.sh zoccl scripts/_zorder_occlude.py 25 "" 8
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent / "environment_files"


def _game_source(game_dir: pathlib.Path) -> pathlib.Path | None:
    for path in sorted(game_dir.rglob("*.py")):
        if not path.name.startswith("._"):
            return path
    return None


def _load(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"_game_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def camera_rules(mod) -> tuple[bool, bool]:
    """(does the game's camera sort by layer, does it read `sprite.pixels` raw).

    ⛔ THE FIRST VERSION OF THIS ANSWERED "no sort" FOR ALL 25 GAMES and the probe happily
    printed occlusion counts for every one of them. Cause: `vars(mod)` contains the
    imported `Camera` ITSELF, and `Camera.__dict__` naturally holds `_raw_render`, so the
    test "is there a Camera subclass overriding _raw_render" matched the base class in
    every game that imports it. A detector that fires on its own reference class is rule
    7z's family — a plausible answer to a question it was not asking — and here it would
    have painted 22 boards in an order their engine never uses.

    The accessor matters for the same reason: s5i5's and wa30's overrides read
    `sprite.pixels` RAW while tu93's and the base engine's call `sprite.render()`, which
    applies rotation, mirroring and scale. Reading the wrong one paints a different board.
    """
    from arcengine import Camera

    for value in vars(mod).values():
        if (isinstance(value, type) and value is not Camera
                and issubclass(value, Camera) and "_raw_render" in value.__dict__):
            try:
                src = inspect.getsource(value.__dict__["_raw_render"])
            except OSError:  # pragma: no cover - source always available here
                src = ""
            return False, "sprite.pixels" in src
    return True, False


def visible_cells(sprites, order, w: int, h: int, raw: bool) -> dict[int, int]:
    """id(sprite) -> how many cells of it survive to the final picture under ``order``.

    Paints an OWNER map rather than a colour map: each cell records which sprite last wrote
    it, so a sprite completely covered by later ones ends with a count of zero. Counting
    owners rather than colours is deliberate — two sprites of the same colour overlapping
    change no pixel, and a colour map would report them as still visible when one of them
    has in fact been buried.
    """
    owner = np.full((h, w), -1, dtype=np.int64)
    for slot, sprite in enumerate(order):
        px = np.asarray(sprite.pixels if raw else sprite.render())
        sh, sw = px.shape
        x0, y0 = int(sprite.x), int(sprite.y)
        dx0, dy0 = max(0, x0), max(0, y0)
        dx1, dy1 = min(w, x0 + sw), min(h, y0 + sh)
        if dx1 <= dx0 or dy1 <= dy0:
            continue
        region = px[dy0 - y0:dy1 - y0, dx0 - x0:dx1 - x0]
        mask = region >= 0
        owner[dy0:dy1, dx0:dx1][mask] = slot
    counts = {id(s): 0 for s in order}
    slots = {slot: id(s) for slot, s in enumerate(order)}
    for slot, n in zip(*np.unique(owner, return_counts=True)):
        if int(slot) >= 0:
            counts[slots[int(slot)]] = int(n)
    return counts


def paint_order(sprites, sorts: bool):
    return sorted(sprites, key=lambda s: s.layer) if sorts else list(sprites)


def main() -> None:
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    games = sorted(d for d in ROOT.iterdir() if d.is_dir())
    game_dir = games[idx - 1]
    row: dict = {"game": game_dir.name}
    src = _game_source(game_dir)
    try:
        mod = _load(src)
    except Exception as exc:  # noqa: BLE001
        row["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(row))
        return

    sorts, raw = camera_rules(mod)
    row["camera_sorts_by_layer"] = sorts
    row["camera_reads_raw_pixels"] = raw
    levels = getattr(mod, "levels", None) or []
    out = []
    for i, level in enumerate(levels):
        # ⛔ The base camera filters `is_visible` before painting; the three overriding
        # cameras do not. Applying the engine's filter to a game that has none would drop
        # sprites the picture actually contains.
        sprites = [s for s in level.get_sprites()
                   if not sorts or getattr(s, "is_visible", True)]
        gw, gh = level.grid_size or (64, 64)
        base = paint_order(sprites, sorts)
        rev = paint_order(list(sprites)[::-1], sorts)
        before = visible_cells(sprites, base, gw, gh, raw)
        after = visible_cells(sprites, rev, gw, gh, raw)
        buried = [k for k in before if before[k] > 0 and after[k] == 0]
        raised = [k for k in before if before[k] == 0 and after[k] > 0]
        out.append({
            "level": i + 1,
            "sprites": len(sprites),
            "cells_moved": sum(abs(before[k] - after[k]) for k in before) // 2,
            "sprites_buried": len(buried),
            "sprites_raised": len(raised),
            "buried_sizes": sorted(before[k] for k in buried),
            "already_buried": sum(1 for k in before if before[k] == 0),
        })
    row["levels"] = out
    row["total_buried"] = sum(r["sprites_buried"] for r in out)
    row["total_cells_moved"] = sum(r["cells_moved"] for r in out)
    print(json.dumps(row))


if __name__ == "__main__":
    main()
