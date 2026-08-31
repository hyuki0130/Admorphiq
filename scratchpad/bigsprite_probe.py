"""Is the near-full-screen element on a stuck level an OVERLAY that covers the board?

Three games add an element at or beyond the 64x64 board exactly where their tool stops
(ka59 65x61, g50t 56x61, s5i5 70x51). If it covers, every planner iteration on those games
is aimed at a board that is not visible. Read-only; engine never started.
"""
import collections, importlib.util, pathlib, sys
import numpy as np

STUCK = {"ka59": 6, "g50t": 6, "s5i5": 6, "ls20": 6, "wa30": 8, "dc22": 5}

for title, cleared in [(t, STUCK[t]) for t in (sys.argv[1:] or STUCK)]:
    p = next(pathlib.Path(f"environment_files/{title}").rglob(f"{title}.py"))
    spec = importlib.util.spec_from_file_location("m_" + title, p)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    L = m.levels[cleared]
    sprites = list(L.get_sprites())
    print(f"\n=== {title} L{cleared+1}: {len(sprites)} sprites ===")
    s0 = sprites[0]
    print("   sprite attrs:", [a for a in dir(s0) if not a.startswith('_')][:18])
    big = sorted(sprites, key=lambda s: -(s.width * s.height))[:3]
    for s in big:
        px = np.array(s.pixels)
        opaque = int((px >= 0).sum())
        frac = opaque / px.size
        pos = tuple(getattr(s, k, None) for k in ("x", "y"))
        print(f"   {s.width}x{s.height} at {pos} colours{tuple(sorted(set(px.ravel().tolist())))} "
              f"opaque {opaque}/{px.size} = {frac:.3f}")
