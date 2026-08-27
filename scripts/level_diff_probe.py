"""What does the first UNCLEARED level contain that the last cleared one does not?

Applied to ls20 an hour ago it broke an eight-iteration loop: its level 7 carries five element
kinds level 6 never shows, so no amount of planning refinement was going to reach them. This runs
the same read for the remaining stuck games. Engine never started; the level data is static.
"""
import collections
import importlib.util
import pathlib
import sys

import numpy as np


def kinds(L):
    c = collections.Counter()
    for s in L.get_sprites():
        px = np.array(s.pixels)
        c[(s.width, s.height, tuple(sorted(set(px.ravel().tolist()))))] += 1
    return c
STUCK = {"wa30": 8, "dc22": 5, "ka59": 6, "g50t": 6, "s5i5": 6, "ls20": 6, "lf52": 5, "bp35": 5}
import sys as _s

_args = _s.argv[1:]
_pairs = ([(t, STUCK[t]) for t in _args] if _args else sorted(STUCK.items()))
for title, cleared in _pairs:
    p = next(pathlib.Path(f"environment_files/{title}").rglob(f"{title}.py"))
    spec = importlib.util.spec_from_file_location("m_"+title, p)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
    if cleared >= len(m.levels): print(f"{title}: no uncleared level"); continue
    a, b = kinds(m.levels[cleared-1]), kinds(m.levels[cleared])
    new = b - a
    print(f"\n{title}: L{cleared} ({sum(a.values())} sprites, {len(a)} kinds) -> "
          f"L{cleared+1} ({sum(b.values())} sprites, {len(b)} kinds)")
    if not new: print("   NOTHING new — the uncleared level uses only kinds already seen")
    for k, n in sorted(new.items(), key=lambda x: -x[1])[:6]:
        print(f"   new: {k[0]}x{k[1]} colours{k[2]} x{n}")
