"""Everything dc22's final level contains, read off the live sprite objects — not off the source text.

⛔ Written because a regex read of the `sprites` dict mis-assigned tags: it reported
`tacugo-plelvb-1` as carrying "buezna"/"goknoi" and the crane plates as carrying single letters,
and the constructed level disagrees with both. A tag table is only trustworthy from the objects the
game builds.

Reconstructs level index 5 the way `Dc22.on_set_level` does and prints, for every sprite, its name,
position, size, tags, interaction and layer; then the SUPPORT map (`sxnzvaqltp`: a pixel of an
INTANGIBLE sprite under the point) and the BLOCKED map (`collides_with` against the 2x2 avatar) as
ASCII at the game's own two-cell move granularity.

Expected feedback: the ASCII maps say in one look what the avatar can stand on and where it cannot
go, and the tag table says which sprites are the controls. Together they are the level's statement.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
SRC = Path(__file__).resolve().parent.parent / "environment_files/dc22/fdcac232/dc22.py"


def main() -> None:
    idx = int(sys.argv[1]) - 1 if len(sys.argv) > 1 else 5
    import numpy as np
    from arcengine import InteractionMode

    spec = importlib.util.spec_from_file_location("dc22mod", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    oracle = importlib.util.spec_from_file_location(
        "dc22orac", Path(__file__).resolve().parent / "_dc22_l6_oracle.py")
    om = importlib.util.module_from_spec(oracle)
    oracle.loader.exec_module(om)

    sps, counts = om.build(mod, idx)
    lvl = mod.levels[idx]
    w, h = lvl.grid_size
    avatar = next(s for s in sps if "jfva" in s.tags)
    goal = next(s for s in sps if "goknoi" in s.tags)
    layered = sorted(sps, key=lambda s: s.layer, reverse=True)
    NB = mod.BlockingMode.NOT_BLOCKED
    av = avatar.render()
    ah, aw = av.shape

    def supported(x, y):
        for s in layered:
            if s is avatar or "ignore" in s.tags or "crzsjq" in s.tags or "vcha" in s.tags:
                continue
            if not (s.x <= x < s.x + s.width and s.y <= y < s.y + s.height):
                continue
            if s.render()[y - s.y][x - s.x] < 0:
                continue
            if s._interaction == InteractionMode.INTANGIBLE:
                return s
        return None

    def blocker(x, y):
        for o in sps:
            if o is avatar or "ignore" in o.tags:
                continue
            if not (avatar.is_collidable and o.is_collidable):
                continue
            if avatar._blocking == NB or o._blocking == NB:
                continue
            ob = o.render()
            oh, ow = ob.shape
            if x >= o.x + ow or x + aw <= o.x or y >= o.y + oh or y + ah <= o.y:
                continue
            x0, x1 = max(x, o.x), min(x + aw, o.x + ow)
            y0, y1 = max(y, o.y), min(y + ah, o.y + oh)
            a = av[y0 - y:y1 - y, x0 - x:x1 - x]
            b = ob[y0 - o.y:y1 - o.y, x0 - o.x:x1 - o.x]
            if bool(np.any((a >= 0) & (b >= 0))):
                return o
        return None

    rows = []
    for s in sps:
        if s.interaction == InteractionMode.REMOVED:
            continue
        rows.append({
            "name": s.name, "xy": [s.x, s.y], "wh": [s.width, s.height],
            "tags": list(s.tags), "inter": str(s.interaction).split(".")[-1],
            "layer": s.layer, "coll": bool(s.is_collidable), "vis": bool(s.is_visible),
        })

    art_sup, art_blk = [], []
    for y in range(0, h, 2):
        rs, rb = [], []
        for x in range(0, w, 2):
            sup = supported(x, y)
            blk = blocker(x, y)
            if (x, y) == (avatar.x, avatar.y):
                rs.append("A")
            elif (x, y) == (goal.x, goal.y):
                rs.append("G")
            else:
                rs.append("." if sup is None else "#")
            rb.append("." if blk is None else "X")
        art_sup.append("".join(rs))
        art_blk.append("".join(rb))

    print(json.dumps({
        "level": idx + 1, "grid": [w, h],
        "avatar": [avatar.x, avatar.y], "goal": [goal.x, goal.y, goal.name],
        "variant_counts": counts,
        "sprites": rows,
        "support_map": art_sup,
        "blocked_map": art_blk,
    }, default=str))


if __name__ == "__main__":
    main()
