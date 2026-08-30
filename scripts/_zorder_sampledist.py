"""How violent is a RANDOM re-serialisation, next to a reversal and next to a real one?

⛔ THE QUESTION RULE 7ck LEAVES OPEN. That rule's arms REVERSE the sprite list, which is
the maximum possible perturbation of paint order, so "14 of 25 games depend on paint order"
is a worst-case statement. A real re-render is not a reversal: the competition's own
re-render of s5i5 changed the picture by ONE CELL on level 4. This probe puts the three on
one axis, per game and per level, on the authored boards:

  * ``reversal``   — the arm rule 7ck used
  * ``uniform``    — N uniformly random orderings, the expected case
  * ``archive``    — for s5i5 ONLY, the ordering the competition actually shipped, which
                     `scripts/_s5i5_srcdiff.py` proved differs from the live file in list
                     ORDER ALONE (same art, same positions, same `Children`, all 8 levels)

⭐ THE CALIBRATION IS THE POINT. If the archive's real ordering sits at a typical percentile
of the uniform draws, uniform is a fair model of a re-render and the sampled gate measures
the expected case. If it sits at the extreme low end, uniform is too violent and even the
sampled gate is still a pessimistic bound — which would have to be said.

⛔ IT PAINTS THE WAY EACH GAME PAINTS. s5i5, tu93 and wa30 override ``Camera._raw_render``
with a version that never sorts, and two of those read ``sprite.pixels`` RAW where the base
engine calls ``sprite.render()`` (rotation, mirroring, scale). Painting all 25 the same way
answers a question about a different game — the error that cost rule 7ck's first arm its
positive control.

⚠️ IT IS STATIC and sees only the AUTHORED boards, so it is blind to a game that builds its
board at runtime (bp35) and to sprites that move into overlap during play (g50t). The live
sampled gate is the authority; this probe is the cheap calibration that says what the gate's
distribution should be compared against.

    bash scripts/pfan.sh zdist scripts/_zorder_sampledist.py 25 "" 8
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import pathlib
import random
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAMES = ROOT / "environment_files"
DRAWS = 200


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
    """(sorts by layer, reads raw `.pixels`) — read off the game's own camera override.

    ⛔ ``value is not Camera`` is load-bearing: ``vars(mod)`` holds the imported base class
    and ``Camera.__dict__`` naturally contains ``_raw_render``, so without it the test
    matches in every game that imports Camera and answers "no sort" for all 25 — a detector
    firing on its own reference class.
    """
    from arcengine import Camera

    for value in vars(mod).values():
        if (isinstance(value, type) and value is not Camera
                and issubclass(value, Camera) and "_raw_render" in value.__dict__):
            try:
                src = inspect.getsource(value.__dict__["_raw_render"])
            except OSError:  # pragma: no cover
                src = ""
            return False, "sprite.pixels" in src
    return True, False


def paint(sprites, w: int, h: int, sorts: bool, raw: bool) -> np.ndarray:
    order = sorted(sprites, key=lambda s: s.layer) if sorts else list(sprites)
    out = np.zeros((h, w), dtype=np.int16)
    for sprite in order:
        px = np.asarray(sprite.pixels if raw else sprite.render())
        sh, sw = px.shape
        x0, y0 = int(sprite.x), int(sprite.y)
        dx0, dy0 = max(0, x0), max(0, y0)
        dx1, dy1 = min(w, x0 + sw), min(h, y0 + sh)
        if dx1 <= dx0 or dy1 <= dy0:
            continue
        region = px[dy0 - y0:dy1 - y0, dx0 - x0:dx1 - x0]
        mask = region >= 0
        out[dy0:dy1, dx0:dx1][mask] = region[mask]
    return out


def _levels(mod):
    return getattr(mod, "levels", None) or []


def _sprites(level, sorts: bool):
    # The base camera filters `is_visible` before painting; the three overriding cameras
    # do not, so applying the engine's filter to a game that has none drops content.
    return [s for s in level.get_sprites() if not sorts or getattr(s, "is_visible", True)]


def main() -> None:
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    dirs = sorted(d for d in GAMES.iterdir() if d.is_dir())
    game_dir = dirs[idx - 1]
    row: dict = {"game": game_dir.name, "draws": DRAWS}
    try:
        mod = _load(_game_source(game_dir))
    except Exception as exc:  # noqa: BLE001
        row["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(row))
        return
    sorts, raw = camera_rules(mod)
    row["camera_sorts_by_layer"], row["camera_reads_raw_pixels"] = sorts, raw

    per_level = []
    for i, level in enumerate(_levels(mod)):
        sprites = _sprites(level, sorts)
        gw, gh = level.grid_size or (64, 64)
        base = paint(sprites, gw, gh, sorts, raw)
        rev = int((base != paint(list(sprites)[::-1], gw, gh, sorts, raw)).sum())
        counts = []
        for seed in range(1, DRAWS + 1):
            shuffled = list(sprites)
            random.Random(seed).shuffle(shuffled)
            counts.append(int((base != paint(shuffled, gw, gh, sorts, raw)).sum()))
        counts.sort()
        per_level.append({
            "level": i + 1,
            "sprites": len(sprites),
            "reversal": rev,
            "uniform_zero_fraction": round(sum(1 for c in counts if c == 0) / len(counts), 4),
            "uniform_min": counts[0],
            "uniform_p25": counts[len(counts) // 4],
            "uniform_median": counts[len(counts) // 2],
            "uniform_p75": counts[3 * len(counts) // 4],
            "uniform_max": counts[-1],
        })
    row["levels"] = per_level
    row["levels_any_uniform_change"] = sum(1 for r in per_level if r["uniform_max"])
    row["levels_reversal_changes"] = sum(1 for r in per_level if r["reversal"])

    # ⭐ s5i5 alone has a re-render proved to differ in LIST ORDER ONLY, so it is the only
    # game where the competition's real ordering can be placed against the uniform draws.
    if game_dir.name == "s5i5":
        arch_dir = ROOT / "environment_files_archive/s5i5"
        if not arch_dir.exists():
            arch_dir = pathlib.Path.home() / "admorphiq/environment_files_archive/s5i5"
        if arch_dir.exists():
            arch = _load(_game_source(arch_dir))
            marks = []
            for i, (live_lv, arch_lv) in enumerate(zip(_levels(mod), _levels(arch))):
                gw, gh = live_lv.grid_size or (64, 64)
                a = paint(_sprites(live_lv, sorts), gw, gh, sorts, raw)
                b = paint(_sprites(arch_lv, sorts), gw, gh, sorts, raw)
                real = int((a != b).sum())
                lv = per_level[i]
                marks.append({"level": i + 1, "archive_cells": real,
                              "uniform_median": lv["uniform_median"],
                              "uniform_max": lv["uniform_max"],
                              "reversal": lv["reversal"]})
            row["archive_vs_uniform"] = marks
    print(json.dumps(row))


if __name__ == "__main__":
    main()
