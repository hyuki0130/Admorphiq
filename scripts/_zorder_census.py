"""How many of the 25 games can exhibit a PAINT-ORDER dependence at all?

⭐ THE POPULATION QUESTION, AND WHY IT COMES FIRST. Rule 7cd's defect needs two sprites
drawn over the same cell at the same layer: swap their order and one cell changes colour.
A game whose sprites never do that CANNOT exhibit it, and that count bounds the exposure
before a single full-25 run is spent. "Only s5i5 has overlapping same-layer pairs" would
be a complete result — it would say the public 25 cannot measure this class and the
private 110 must be assumed to.

WHAT IT COUNTS. Per level, the number of SAME-LAYER sprite pairs that are Z-SENSITIVE: they
have overlapping opaque pixels AND differ in colour somewhere in that overlap. Colour
matters — two identical sprites stacked on each other render the same either way, so a
footprint overlap alone is an INPUT count, and rule 7by's lesson is to count effects.

⛔ IT IS STATIC AND THEREFORE A LOWER BOUND, AND THAT IS NOT A DETAIL. It reads
`module.levels`, so it sees the board as AUTHORED. Two things escape it: a game that builds
its board at runtime (`dump_sample_levels.py`'s docstring records bp35 coming back as one
1x1 sprite for all nine levels), and a level whose sprites MOVE into overlap during play.
The authoritative count is the dynamic one — `zordergate_run.py` renders both orders on
every observation frame and reports `frames_changed` / `cells_changed` for the levels the
agent actually reaches. Read the two together; neither alone is the answer.

⛔ BOTH CONTROLS TRAVEL WITH EVERY RUN, because an all-zero census and a broken counter are
the same output. The positive control is two same-layer sprites overlapping in different
colours (must report 1 pair); the negative is the SAME two sprites on different layers
(must report 0, since a same-layer permutation cannot reorder them). A run whose controls
disagree with those prints CONTROLFAIL and its counts mean nothing.

    bash scripts/pfan.sh zcensus scripts/_zorder_census.py 25 "" 8
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent / "environment_files"


def _load(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"_game_{path.stem}", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _placed(sprite) -> tuple[int, int, np.ndarray]:
    """(x, y, rendered pixels) — ``render()`` applies rotation, mirroring and scale."""
    return int(sprite.x), int(sprite.y), np.asarray(sprite.render())


def z_sensitive(a, b) -> int:
    """1 when swapping ``a`` and ``b`` changes the picture, else 0.

    Purpose: the census's whole definition. The two sprites must overlap where BOTH are
    opaque (pixel >= 0; -1 is the engine's transparency) and must disagree on the colour
    of at least one such cell — otherwise the order between them is invisible.

    Expected feedback: used by both the census and its controls. If this returns 1 for a
    pair on different layers, the caller has grouped wrongly and every count is inflated.
    """
    ax, ay, ap = _placed(a)
    bx, by, bp = _placed(b)
    x0, y0 = max(ax, bx), max(ay, by)
    x1 = min(ax + ap.shape[1], bx + bp.shape[1])
    y1 = min(ay + ap.shape[0], by + bp.shape[0])
    if x1 <= x0 or y1 <= y0:
        return 0
    sub_a = ap[y0 - ay:y1 - ay, x0 - ax:x1 - ax]
    sub_b = bp[y0 - by:y1 - by, x0 - bx:x1 - bx]
    both = (sub_a >= 0) & (sub_b >= 0)
    if not both.any():
        return 0
    return 1 if bool((sub_a[both] != sub_b[both]).any()) else 0


def count_level(sprites) -> tuple[int, int]:
    """(z-sensitive same-layer pairs, z-sensitive pairs ignoring layer entirely).

    The second number is not decoration: s5i5, tu93 and wa30 override
    ``Camera._raw_render`` with a version that does NOT sort by layer, so for those three
    the list order alone decides the picture and every pair is a same-order pair. The
    mutation is still same-layer-only there — that is the conservative choice — but the
    gap between the two numbers says how much of those boards the arm deliberately leaves
    alone.
    """
    same, any_layer = 0, 0
    n = len(sprites)
    for i in range(n):
        for j in range(i + 1, n):
            hit = z_sensitive(sprites[i], sprites[j])
            if not hit:
                continue
            any_layer += 1
            if int(sprites[i].layer) == int(sprites[j].layer):
                same += 1
    return same, any_layer


def _controls() -> tuple[bool, str]:
    from arcengine import Sprite

    art_a = [[1, 1], [1, 1]]
    art_b = [[2, 2], [2, 2]]
    same = [Sprite(pixels=art_a, x=0, y=0, layer=3),
            Sprite(pixels=art_b, x=1, y=1, layer=3)]
    cross = [Sprite(pixels=art_a, x=0, y=0, layer=3),
             Sprite(pixels=art_b, x=1, y=1, layer=4)]
    pos, _ = count_level(same)
    neg, _ = count_level(cross)
    ok = pos == 1 and neg == 0
    return ok, f"positive={pos} (want 1) negative={neg} (want 0)"


def main() -> None:
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    games = sorted(d for d in ROOT.iterdir() if d.is_dir())
    if not 1 <= idx <= len(games):
        print(json.dumps({"error": f"index {idx} outside 1..{len(games)}"}))
        return
    game_dir = games[idx - 1]
    ok, detail = _controls()
    row: dict = {"game": game_dir.name, "controls_ok": ok, "controls": detail}
    if not ok:
        row["verdict"] = "CONTROLFAIL"
        print(json.dumps(row))
        return

    src = next(iter(sorted(game_dir.rglob("*.py"))), None)
    if src is None:
        row["error"] = "no game source"
        print(json.dumps(row))
        return
    try:
        mod = _load(src)
    except Exception as exc:  # noqa: BLE001
        row["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(row))
        return

    levels = getattr(mod, "levels", None) or []
    per_level, per_level_any, sprite_counts = [], [], []
    for level in levels:
        try:
            sprites = [s for s in level.get_sprites() if getattr(s, "is_visible", True)]
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"level read failed: {type(exc).__name__}: {exc}"
            print(json.dumps(row))
            return
        same, any_layer = count_level(sprites)
        per_level.append(same)
        per_level_any.append(any_layer)
        sprite_counts.append(len(sprites))

    row.update({
        "n_levels": len(levels),
        "sprites_per_level": sprite_counts,
        "zpairs_same_layer": per_level,
        "zpairs_any_layer": per_level_any,
        "levels_with_zpairs": sum(1 for v in per_level if v),
        "total_zpairs": sum(per_level),
        "max_zpairs": max(per_level) if per_level else 0,
        "verdict": "CAN_EXHIBIT" if sum(per_level) else "STATICALLY_CLEAN",
    })
    print(json.dumps(row))


if __name__ == "__main__":
    main()
