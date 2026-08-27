"""Every level of every sample game, statically — no engine, no actions, no run.

Each game ships as ONE python file holding both its rules and its data: a `sprites = {...}`
table and a `levels = [...]` list of literals. Importing the module and walking those gives the
whole board — every sprite, its tags, its position, its size — for every level of all 25 games,
without stepping the environment once.

⛔ This replaces a habit, not a tool. The previous session measured boards by probing them live,
which costs actions on games that LOSE when an action budget runs out (six of them do) and cannot
see a level it has not yet reached. The data was on disk the whole time.

Same line as `read_sample_games.py`: DEV-TIME understanding of which mechanic a generic tool must
handle. Nothing here may be imported by a tool.

⛔ IT IS BLIND TO GAMES THAT BUILD THEIR BOARD AT RUNTIME, and it does not say so — it reports a
true fact about the wrong object. MEASURED 2026-08-27: bp35 comes back as one 1x1 sprite on an
8x8 grid for all nine levels, which reads as "there is nothing here". Its boards are actually in
a module-level dict, ten entries keyed `grid1`..`grid10`, each an object carrying `.width`,
`.height`, the board as a list of one-char-per-cell strings, a legend mapping char to sprite
name, a start cell and an exit. Two tool authors worked that game without them.

So when this script reports a level with almost nothing in it, the next step is to walk the
module for OTHER tables — a dict or list whose length matches the level count is the tell — not
to conclude the level is empty:

    for name, val in vars(module).items():
        if isinstance(val, (dict, list, tuple)) and len(val) >= len(module.levels):
            print(name, type(val).__name__, len(val))
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent / "environment_files"


def load(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"_game_{path.stem}", path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def sprite_rows(level) -> list[tuple[str, str, int, int, int, int]]:
    out = []
    for s in level.get_sprites():
        tags = ",".join(sorted(str(t) for t in (getattr(s, "tags", None) or [])))[:44]
        px = getattr(s, "pixels", None)
        h = len(px) if px is not None else 0
        w = len(px[0]) if h else 0
        out.append((str(getattr(s, "name", "?"))[:22], tags, int(getattr(s, "x", 0)),
                    int(getattr(s, "y", 0)), int(w), int(h)))
    return out


def main() -> None:
    only = set(sys.argv[1:]) or None
    for game_dir in sorted(ROOT.iterdir()):
        if not game_dir.is_dir() or (only and game_dir.name not in only):
            continue
        src = next(iter(sorted(game_dir.rglob("*.py"))), None)
        if src is None:
            continue
        try:
            mod = load(src)
        except Exception as exc:  # noqa: BLE001
            print(f"{game_dir.name}: could not import ({type(exc).__name__}: {exc})")
            continue
        levels = getattr(mod, "levels", None)
        if not levels:
            print(f"{game_dir.name}: no `levels` literal")
            continue
        print("=" * 78)
        print(f"{game_dir.name}   {len(levels)} levels")
        for i, level in enumerate(levels):
            try:
                rows = sprite_rows(level)
            except Exception as exc:  # noqa: BLE001
                print(f"  L{i}: unreadable ({type(exc).__name__})")
                continue
            tags = Counter(t for _, tg, *_ in rows for t in tg.split(",") if t)
            grid = getattr(level, "grid_size", None)
            data = getattr(level, "_data", None) or getattr(level, "data", None)
            print(f"  L{i}: {len(rows)} sprites  grid={grid}  data={data}")
            print(f"      tags: {dict(tags.most_common(10))}")
            if only:
                for r in rows[:40]:
                    print(f"        {r[0]:22s} [{r[1]:44s}] at ({r[2]:2d},{r[3]:2d}) {r[4]}x{r[5]}")


if __name__ == "__main__":
    main()
