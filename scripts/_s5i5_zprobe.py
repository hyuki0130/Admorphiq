"""Why a SAME-LAYER reversal does not reproduce s5i5's known paint-order answer.

Rule 7cd's positive control is s5i5 L4: the archived re-render lists the rider BEFORE the
bar it rides, the bar covers one cell, and the level costs 39 -> 61 actions. The first
`zrev` arm — reverse each LAYER's sprites among themselves — left s5i5 identical action
for action, so either the rider and the bar are not on the same layer or the reversal does
not reach them. This says which.

⛔ IT PAINTS THE WAY s5i5 ITSELF PAINTS, not the way the base engine does. s5i5 overrides
`Camera._raw_render` with a version that does NOT sort by layer and reads `sprite.pixels`
directly, so for this game the LIST ORDER alone decides the picture and `layer` is not a
rendering property at all. Painting it with the base engine's rules would answer a
question about a different game.

Both permutations are compared against the unmutated paint, per level:
  * same-layer reversal  — the conservative arm, layers keep their list slots
  * whole-list reversal  — what the archived re-render's difference actually IS

    bash scripts/pfan.sh s5i5z scripts/_s5i5_zprobe.py 1 "" 1
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _game_source(game_dir: pathlib.Path) -> pathlib.Path:
    """The game's own module, skipping ceph-build's `._<game>.py` AppleDouble artefacts —
    they sort first, are binary, and import as "source code string cannot contain null
    bytes", which reads as "the game cannot be read"."""
    return next(p for p in sorted(game_dir.rglob("*.py")) if not p.name.startswith("._"))


def _load(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"_game_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def paint(sprites, w: int, h: int, background: int = 0) -> np.ndarray:
    """s5i5's own painter: list order, `sprite.pixels`, no layer sort, no visibility test."""
    out = np.full((h, w), background, dtype=np.int16)
    for s in sprites:
        px = np.asarray(s.pixels)
        sh, sw = px.shape
        x0, y0 = int(s.x), int(s.y)
        dx0, dy0 = max(0, x0), max(0, y0)
        dx1, dy1 = min(w, x0 + sw), min(h, y0 + sh)
        if dx1 <= dx0 or dy1 <= dy0:
            continue
        region = px[dy0 - y0:dy1 - y0, dx0 - x0:dx1 - x0]
        mask = region >= 0
        out[dy0:dy1, dx0:dx1][mask] = region[mask]
    return out


def same_layer_reverse(sprites):
    slots: dict[int, list[int]] = {}
    for i, s in enumerate(sprites):
        slots.setdefault(int(s.layer), []).append(i)
    out = list(sprites)
    for idxs in slots.values():
        for i, s in zip(idxs, [sprites[j] for j in idxs][::-1]):
            out[i] = s
    return out


def main() -> None:
    live = _load(_game_source(ROOT / "environment_files/s5i5"))
    # ⚠️ `pfan.sh` links only .venv / environment_files / data / ARC-AGI-3-Agents into the
    # snapshot, so the archive has to be reached in the shared tree beside it.
    arch_dir = ROOT / "environment_files_archive/s5i5"
    if not arch_dir.exists():
        arch_dir = pathlib.Path.home() / "admorphiq/environment_files_archive/s5i5"
    arch = _load(_game_source(arch_dir)) if arch_dir.exists() else None

    rows = []
    for idx, level in enumerate(live.levels):
        sprites = level.get_sprites()
        gw, gh = level.grid_size or (64, 64)
        base = paint(sprites, gw, gh)
        sl = paint(same_layer_reverse(sprites), gw, gh)
        whole = paint(list(sprites)[::-1], gw, gh)
        layers = [int(s.layer) for s in sprites]
        rows.append({
            "level": idx + 1,
            "n": len(sprites),
            "layers": sorted(set(layers)),
            "per_layer_counts": {str(v): layers.count(v) for v in sorted(set(layers))},
            "same_layer_cells_changed": int((base != sl).sum()),
            "whole_list_cells_changed": int((base != whole).sum()),
        })

    out = {"probe": "s5i5_zorder", "levels": rows}

    if arch is not None:
        diffs = []
        for idx, (lv_live, lv_arch) in enumerate(zip(live.levels, arch.levels)):
            gw, gh = lv_live.grid_size or (64, 64)
            a = paint(lv_live.get_sprites(), gw, gh)
            b = paint(lv_arch.get_sprites(), gw, gh)
            cells = np.argwhere(a != b)
            diffs.append({
                "level": idx + 1,
                "cells_differing": int(len(cells)),
                "where": [[int(y), int(x), int(a[y, x]), int(b[y, x])]
                          for y, x in cells[:6]],
            })
        out["live_vs_archived"] = diffs

    print(json.dumps(out))


if __name__ == "__main__":
    main()
