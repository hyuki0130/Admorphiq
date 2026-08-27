"""What does the first UNCLEARED level contain that the last cleared one does not?

⛔ BLIND TO GAMES THAT BUILD THEIR BOARD AT RUNTIME, and it says so rather than reporting a false
negative. bp35 and lf52 come back as "1 sprite, 1 kind, nothing new" on every level because their
boards live in a module-level tile table, not in `levels` — the same limitation
`dump_sample_levels.py` carries. For those two, sweep the module for a dict or list whose length
matches the level count.

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
# ⛔ REFRESH THIS FROM A CURRENT FULL-25, NEVER FROM MEMORY. On 2026-08-27 g50t sat here while
# it was scoring 1.0000 -- an agent was directed at a level that clears in 42 actions, three
# times, because this dict was written from a baseline the TREE had already moved past.
#   uv run python -c "import json,glob,os; [print(os.path.basename(f)[:-5]) for f in
#     glob.glob('scripts/rounds/<LATEST>/games/*.json') if json.load(open(f))['total_score']<0.999]"
# Last refreshed: R101NOW, 2026-08-27, mean 0.8702, 16/25 at the cap.
STUCK = {"wa30": 8, "dc22": 5, "ka59": 6, "s5i5": 6, "ls20": 6, "lf52": 5, "bp35": 5,
         "lp85": 7, "re86": 7}

_args = sys.argv[1:]
_pairs = [(t, STUCK[t]) for t in _args] if _args else sorted(STUCK.items())
for title, cleared in _pairs:
    p = next(pathlib.Path(f"environment_files/{title}").rglob(f"{title}.py"))
    spec = importlib.util.spec_from_file_location("m_"+title, p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    if cleared >= len(m.levels):
        print(f"{title}: no uncleared level")
        continue
    a, b = kinds(m.levels[cleared-1]), kinds(m.levels[cleared])
    new = b - a
    print(f"\n{title}: L{cleared} ({sum(a.values())} sprites, {len(a)} kinds) -> "
          f"L{cleared+1} ({sum(b.values())} sprites, {len(b)} kinds)")
    if not new:
        print("   NOTHING new by this reading — but see the caveat above: a board built at"
              " RUNTIME shows as one sprite and this probe is blind to it")
    for k, n in sorted(new.items(), key=lambda x: -x[1])[:6]:
        print(f"   new: {k[0]}x{k[1]} colours{k[2]} x{n}")
