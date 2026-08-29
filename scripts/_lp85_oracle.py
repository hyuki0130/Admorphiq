"""lp85 ORACLE — the shortest press sequence each level actually admits.

Reads the game's own cycle data (`izutyjcpih`) and level sprite lists, builds the exact
permutation behind every `button_<ring>_<L|R>` and BFSes the positions of the sprites the win
predicate names. Prints one JSON line so it can be fanned out one level per process.

Purpose: separate lp85's efficiency loss into "the plan is long" and "the discovery is long".
The human baseline for level 4 is 16 actions and cyclepress spends 33; if the oracle minimum is
far under 16 the loss is discovery, not planning.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import deque
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "environment_files/lp85/305b61c3/lp85.py"


def load():
    spec = importlib.util.spec_from_file_location("lp85mod", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def perms_for(mod, level_name):
    """(ring, dir) -> {from_pos: to_pos} in SPRITE coordinates (grid cell * 3)."""
    out = {}
    maps = mod.izutyjcpih[level_name]
    for ring in maps:
        for is_r in (True, False):
            pairs = mod.chmfaflqhy(level_name, ring, is_r, mod.uopmnplcnv)
            if not pairs:
                continue
            out[(ring, "R" if is_r else "L")] = {
                (a.x * 3, a.y * 3): (b.x * 3, b.y * 3) for a, b in pairs
            }
    return out


def main() -> None:
    idx = int(sys.argv[1]) - 1 if len(sys.argv) > 1 else 3
    mod = load()
    mod.uopmnplcnv = mod.qfvvosdkqr(mod.izutyjcpih)
    lv = mod.levels[idx]
    name = lv.get_data("level_name")
    budget = lv.get_data("StepCounter")
    sprites = list(lv._sprites)

    def tagged(t):
        return [s for s in sprites if s.tags and t in s.tags]

    buttons = [s for s in sprites if s.tags and s.tags[0].startswith("button_")]
    ctrl_tags = sorted({s.tags[0] for s in buttons})
    perms = perms_for(mod, name)

    marks = [(s.x + 1, s.y + 1) for s in tagged("bghvgbtwcb")]
    marks_o = [(s.x + 1, s.y + 1) for s in tagged("goal-o") and tagged("fdgmtkfrxl")]
    goals = tuple(sorted((s.x, s.y) for s in tagged("goal")))
    goals_o = tuple(sorted((s.x, s.y) for s in tagged("goal-o")))

    gens = []
    for key, mapping in perms.items():
        tag = f"button_{key[0]}_{key[1]}"
        if tag in ctrl_tags:
            gens.append((tag, mapping))

    def step(state, mapping):
        g, go = state
        return (tuple(sorted(mapping.get(p, p) for p in g)),
                tuple(sorted(mapping.get(p, p) for p in go)))

    def won(state):
        g, go = state
        return all(m in g for m in marks) and all(m in go for m in marks_o)

    start = (goals, goals_o)
    depth = None
    seq = None
    if won(start):
        depth, seq = 0, []
    else:
        seen = {start: None}
        q = deque([start])
        while q and depth is None:
            st = q.popleft()
            for tag, mapping in gens:
                nxt = step(st, mapping)
                if nxt in seen:
                    continue
                seen[nxt] = (st, tag)
                if won(nxt):
                    depth, seq, cur = 0, [], nxt
                    while seen[cur] is not None:
                        prev, t = seen[cur]
                        seq.append(t)
                        cur = prev
                    seq.reverse()
                    depth = len(seq)
                    break
                q.append(nxt)
            if len(seen) > 3_000_000:
                break
    print(json.dumps({
        "level": idx + 1, "name": name, "budget": budget,
        "button_sprites": len(buttons), "distinct_controls": len(ctrl_tags),
        "controls": ctrl_tags, "rings": sorted(mod.izutyjcpih[name]),
        "marks": len(marks), "marks_o": len(marks_o),
        "oracle_presses": depth, "oracle_seq": seq,
    }))


if __name__ == "__main__":
    main()
