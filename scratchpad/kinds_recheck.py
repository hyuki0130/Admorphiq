"""Re-read the 'new kinds' finding with a key that does NOT include size.

level_diff_probe keys a kind on (w,h,colours), so a structure that merely RESIZES between
levels registers as new. Compare three keys to see what survives.
"""
import collections, importlib.util, pathlib, sys
import numpy as np
STUCK = {"wa30":8,"dc22":5,"ka59":6,"g50t":6,"s5i5":6,"ls20":6}
def counts(L, key):
    c = collections.Counter()
    for s in L.get_sprites():
        px = np.array(s.pixels); cols = tuple(sorted(set(px.ravel().tolist())))
        c[key(s, cols)] += 1
    return c
KEYS = {
    "size+colours": lambda s, c: (s.width, s.height, c),
    "colours only": lambda s, c: c,
}
for title, cleared in STUCK.items():
    p = next(pathlib.Path(f"environment_files/{title}").rglob(f"{title}.py"))
    spec = importlib.util.spec_from_file_location("m_"+title, p)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
    a_, b_ = m.levels[cleared-1], m.levels[cleared]
    row = []
    for name, k in KEYS.items():
        new = counts(b_, k) - counts(a_, k)
        row.append(f"{name}: {len(new)} new kinds ({sum(new.values())} sprites)")
    print(f"{title:5} L{cleared}->L{cleared+1}   " + " | ".join(row))
