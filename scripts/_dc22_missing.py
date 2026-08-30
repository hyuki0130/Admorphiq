"""Why six of dc22 level 6's sprites vanish from a straight `on_set_level` rebuild.

The five crane plates and the colour-cycle button are declared in the level and absent from the
reconstruction. Their interaction, visibility and blocking are printed from the live objects, both
as the `sprites` dict defines them and as the level holds them, so the reason is read rather than
guessed. Expected feedback: names the state that hides them, which is the level's gating rule.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "environment_files/dc22/fdcac232/dc22.py"


def main() -> None:
    spec = importlib.util.spec_from_file_location("dc22mod", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    want = ["renrjo-buezna", "crzsjq-lersnf-1", "crzsjq-riidpd-1", "crzsjq-up-1",
            "crzsjq-grawwq-1", "crzsjq-lersnf-2", "brixtocrzsjq-1", "brixto-orckhi1",
            "brixto-orckhi2", "buezna-matkhq", "sprite-6"]
    out = []
    for n in want:
        s = mod.sprites.get(n)
        out.append({"name": n, "in_dict": s is not None,
                    "tags": list(s.tags) if s else None,
                    "inter": str(s.interaction).split(".")[-1] if s else None,
                    "vis": bool(s.is_visible) if s else None,
                    "coll": bool(s.is_collidable) if s else None,
                    "wh": [s.width, s.height] if s else None})
    lv = copy.deepcopy(mod.levels[5]._sprites)
    lvl = [{"name": s.name, "xy": [s.x, s.y],
            "inter": str(s.interaction).split(".")[-1],
            "vis": bool(s.is_visible), "tags": list(s.tags)}
           for s in lv if s.name in want]
    print(json.dumps({"from_sprite_dict": out, "from_level": lvl,
                      "level_sprite_count": len(lv)}, default=str))


if __name__ == "__main__":
    main()
