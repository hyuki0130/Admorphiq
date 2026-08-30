"""What does dc22's FINAL level actually require? Read off the game's own source, engine unstarted.

dc22 scores 0.7143 with all FIVE reached levels at the metric's cap — pure depth, one level from
completion. Nobody has written down what that level IS. Rule 0: read the source and the level data
before probing the board as a black box.

This reconstructs level index 5 exactly as `Dc22.on_set_level` does (the variant-clone expansion,
the per-tag interaction assignment, and the level-5-only `tewfut-color-cycle` tagging of the
sprite at (18,48)), then reports the decoded control scheme and an exact reachability answer:

  * who the avatar and the goal are, and where;
  * the SUPPORT map — `sxnzvaqltp` returns a sprite only where a pixel of an INTANGIBLE sprite
    lies under the query point, so INTANGIBLE is floor and everything else is hole or wall;
  * the letter groups — `njvd-rolo` pads gate `buezna` sprites of the same single-letter tag, so a
    crane plate exists only while the avatar stands on its pad;
  * whether the goal is reachable by MOVEMENT ALONE (ACTION1-4 step two cells and are refused both
    on collision and on landing unsupported).

Expected feedback: if plain movement reaches the goal the level is a routing problem and the tool
set's failure is a perception or planning defect. If it does not, the printed frontier names the
mechanic that must be operated to open the way, which is what any tool would have to express.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
from collections import deque
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "environment_files/dc22/fdcac232/dc22.py"


def load():
    spec = importlib.util.spec_from_file_location("dc22mod", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(mod, idx: int):
    """Reproduce `on_set_level`'s sprite expansion for one level, engine never started."""
    from arcengine import InteractionMode

    sps = copy.deepcopy(mod.levels[idx]._sprites)
    if idx == 5:
        for s in sps:
            if s.tags and "tewfut" in s.tags and s.x == 18 and s.y == 48:
                s.tags.append(mod.qiukbrokfa)
                s.tags.append("d")
                break

    tovemc = [s for s in sps if s.tags and "tovemc" in s.tags]
    prefixes = {s.name[:-1] for s in tovemc if s.name[-1].isdigit()}
    counts = {}
    for pre in prefixes:
        n = 1
        for k in range(2, 9):
            if pre + str(k) in mod.sprites:
                n += 1
            else:
                break
        counts[pre] = n

    added = []
    for s in list(tovemc):
        if not s.name[-1].isdigit():
            continue
        pre = s.name[:-1]
        if pre not in counts:
            continue
        if "omvz" in s.tags:
            s.set_interaction(InteractionMode.INTANGIBLE)
        elif "inzejtible" in s.tags:
            s.set_interaction(InteractionMode.INVISIBLE)
        elif "buezna" in s.tags:
            s.set_interaction(InteractionMode.INTANGIBLE)
        else:
            s.set_interaction(InteractionMode.TANGIBLE)
        for k in range(1, counts[pre] + 1):
            if k == int(s.name[-1]):
                continue
            nm = pre + str(k)
            if nm not in mod.sprites:
                continue
            c = mod.sprites[nm].clone()
            c.set_position(s.x, s.y)
            c.set_interaction(InteractionMode.REMOVED)
            for t in s.tags:
                if t not in c.tags:
                    c.tags.append(t)
            added.append(c)
    sps.extend(added)
    return sps, counts


def main() -> None:
    idx = int(sys.argv[1]) - 1 if len(sys.argv) > 1 else 5
    import numpy as np
    from arcengine import InteractionMode

    mod = load()
    sps, counts = build(mod, idx)
    lvl = mod.levels[idx]
    grid = lvl.grid_size
    step = mod.ndiyvmxxey

    avatar = next(s for s in sps if s.tags and "jfva" in s.tags)
    goal = next(s for s in sps if s.tags and "goknoi" in s.tags)
    layered = sorted(sps, key=lambda s: s.layer, reverse=True)

    def supported(x: int, y: int) -> str | None:
        for s in layered:
            if s is avatar or "ignore" in s.tags or "crzsjq" in s.tags or "vcha" in s.tags:
                continue
            if not (s.x <= x < s.x + s.width and s.y <= y < s.y + s.height):
                continue
            if s.render()[y - s.y][x - s.x] < 0:
                continue
            if s._interaction == InteractionMode.INTANGIBLE:
                return s.name
        return None

    av = avatar.render()
    ah, aw = av.shape
    NB = mod.BlockingMode.NOT_BLOCKED

    def blocked(x: int, y: int) -> str | None:
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
                return o.name
        return None

    start = (avatar.x, avatar.y)
    target = (goal.x, goal.y)
    seen = {start: None}
    q = deque([start])
    order = []
    while q:
        cur = q.popleft()
        order.append(cur)
        if cur == target:
            break
        for dx, dy in ((0, -step), (0, step), (-step, 0), (step, 0)):
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in seen:
                continue
            if blocked(*nxt) is not None:
                continue
            if supported(*nxt) is None:
                continue
            seen[nxt] = cur
            q.append(nxt)

    path = None
    if target in seen:
        path, c = [], target
        while c is not None:
            path.append(c)
            c = seen[c]
        path.reverse()

    pads = [{"name": s.name, "xy": [s.x, s.y],
             "letter": next((t for t in s.tags if len(t) == 1), None)}
            for s in sps if s.tags and "njvd-rolo" in s.tags]
    buez = [{"name": s.name, "xy": [s.x, s.y], "tags": list(s.tags),
             "letter": next((t for t in s.tags if len(t) == 1), None)}
            for s in sps if s.tags and "buezna" in s.tags and s.interaction != InteractionMode.REMOVED]
    piy = [{"name": s.name, "xy": [s.x, s.y],
            "letter": next((t for t in s.tags if len(t) == 1), None)}
           for s in sps if s.tags and "piyqze" in s.tags]
    tew = [{"name": s.name, "xy": [s.x, s.y], "inter": str(s.interaction),
            "cycle": mod.qiukbrokfa in s.tags}
           for s in sps if s.tags and "tewfut" in s.tags and s.interaction != InteractionMode.REMOVED]

    # Which single square of the frontier is adjacent to an UNSUPPORTED or BLOCKED cell that the
    # goal needs — reported as the reachable cells nearest the goal.
    def d(c):
        return abs(c[0] - target[0]) + abs(c[1] - target[1])

    near = sorted(seen, key=d)[:8]

    print(json.dumps({
        "level": idx + 1,
        "grid": list(grid) if grid else None,
        "step_counter": lvl.get_data("StepCounter"),
        "move_step": step,
        "avatar": {"name": avatar.name, "xy": list(start), "size": [aw, ah]},
        "goal": {"name": goal.name, "xy": list(target)},
        "goal_supported": supported(*target),
        "goal_blocked_by": blocked(*target),
        "reachable_cells": len(seen),
        "goal_reachable_by_movement_alone": target in seen,
        "path_len": None if path is None else len(path) - 1,
        "path": path,
        "nearest_reachable_to_goal": [{"xy": list(c), "manhattan": d(c)} for c in near],
        "njvd_rolo_pads": pads,
        "buezna": buez,
        "piyqze": piy,
        "tewfut": tew,
        "variant_counts": counts,
        "tewfut_colour_cycle": mod.awhuyiogsr,
    }, default=str))


if __name__ == "__main__":
    main()
