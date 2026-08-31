"""Is the maze swallowed as background on the levels g50t CLEARS too?

If yes, the swallow cannot be what stops L7 -- the same test that killed the overlay premise.
"""
import importlib.util, pathlib, sys, collections
import numpy as np
sys.path.insert(0, "src")
from admorphiq.tools.base import color_histogram
p = next(pathlib.Path("environment_files/g50t").rglob("g50t.py"))
spec = importlib.util.spec_from_file_location("mg", p)
m = importlib.util.module_from_spec(spec); sys.modules["mg"] = m; spec.loader.exec_module(m)
for i, L in enumerate(m.levels):
    sprites = list(L.get_sprites())
    grid = np.zeros((64, 64), dtype=int)
    for s in sorted(sprites, key=lambda s: getattr(s, "layer", 0)):
        px = np.array(s.pixels)
        for yy in range(px.shape[0]):
            for xx in range(px.shape[1]):
                v = int(px[yy, xx])
                if v < 0: continue
                Y, X = s.y + yy, s.x + xx
                if 0 <= Y < 64 and 0 <= X < 64: grid[Y, X] = v
    bg = int(color_histogram(grid).argmax())
    big = [s for s in sprites if s.width * s.height >= 2000]
    sw = []
    for s in big:
        gpx = np.array(s.pixels); gc = collections.Counter(gpx[gpx >= 0].ravel().tolist())
        gm = gc.most_common(1)[0][0] if gc else None
        if gm == bg: sw.append(f"{s.width}x{s.height}")
    tag = "CLEARS" if i <= 5 else "STUCK "
    print(f"L{i+1} {tag} bg=c{bg}  geometry sprites {len(big)}  swallowed: {sw or '-'}")
