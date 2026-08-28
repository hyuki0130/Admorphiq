"""What per-level DATA changes at the level a tool stops — read from the game's own source.

⛔ WHY THIS EXISTS. ls20 was stuck at 6/7 and every frame-side investigation said the tool was
right to decline the board: it parsed cleanly, found the avatar, and found ZERO locks across all
13 attempts, while levels 1-6 always found one or two. The answer was one field in the level data:
level 7 is the ONLY level in that game with `Fog = True`, and every other setting matches level 5,
which clears at the cap in 67 actions. The board's locks were under fog. No amount of frame
instrumentation says "Fog"; the game's own `get_data` does, with the engine never started.

Usage:  uv run python scripts/level_data_diff.py <game> [<game> ...]
"""
import importlib.util
import pathlib
import sys

_KEYS_ALWAYS = ("StepCounter", "StepsDecrement")


def load(title: str):
    p = next(pathlib.Path(f"environment_files/{title}").rglob(f"{title}.py"))
    spec = importlib.util.spec_from_file_location(f"m_{title}", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def keys_of(module) -> list[str]:
    """Every data key any level in the game declares, in first-seen order."""
    out: list[str] = []
    for lv in module.levels:
        data = getattr(lv, "_data", None) or getattr(lv, "data", None) or {}
        for k in (data.keys() if hasattr(data, "keys") else []):
            if k not in out:
                out.append(str(k))
    for k in _KEYS_ALWAYS:
        if k not in out:
            out.append(k)
    return out


for title in sys.argv[1:]:
    m = load(title)
    keys = keys_of(m)
    rows = []
    for lv in m.levels:
        row = {}
        for k in keys:
            try:
                row[k] = lv.get_data(k)
            except Exception:
                row[k] = None
        rows.append(row)
    # only print the keys that DIFFER across levels — the rest is noise
    varying = [k for k in keys if len({str(r[k]) for r in rows}) > 1]
    print(f"\n== {title}: {len(m.levels)} levels, {len(varying)} varying keys of {len(keys)}")
    if not varying:
        print("   (no per-level data varies — the difference is in the sprites, not the settings)")
        continue
    print("  lvl " + " ".join(f"{k[:14]:>15}" for k in varying))
    for i, r in enumerate(rows):
        print(f"  {i+1:>3} " + " ".join(f"{str(r[k])[:14]:>15}" for k in varying))
