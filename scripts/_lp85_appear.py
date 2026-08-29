"""Is a lp85 button's APPEARANCE a sound proxy for its permutation?

lp85 level 4 draws SIXTEEN button sprites over only FOUR distinct controls, and cyclepress presses
every one of them once before it plans — sixteen actions against a human budget of sixteen. If two
buttons that look the same always drive the same ring+direction, one press per appearance class
replaces one press per button.

This checks the claim against the game's own sprite table, per level: group each level's buttons by
(pixels, rotation) and report any group that mixes tags. A mixed group is a level where appearance
adoption would install a WRONG permutation.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "environment_files/lp85/305b61c3/lp85.py"


def main() -> None:
    idx = int(sys.argv[1]) - 1 if len(sys.argv) > 1 else 3
    spec = importlib.util.spec_from_file_location("lp85mod", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    lv = mod.levels[idx]
    buttons = [s for s in lv._sprites if s.tags and s.tags[0].startswith("button_")]
    groups: dict[tuple, set[str]] = {}
    for s in buttons:
        key = (repr(s.pixels), getattr(s, "rotation", 0))
        groups.setdefault(key, set()).add(s.tags[0])
    mixed = [sorted(v) for v in groups.values() if len(v) > 1]
    print(json.dumps({
        "level": idx + 1, "name": lv.get_data("level_name"),
        "buttons": len(buttons), "distinct_tags": len({s.tags[0] for s in buttons}),
        "appearance_classes": len(groups),
        "mixed_classes": len(mixed), "mixed": mixed[:6],
    }))


if __name__ == "__main__":
    main()
