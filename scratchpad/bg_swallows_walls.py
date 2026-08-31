"""Does the shared segmentation DISCARD the level geometry as background?

connected_components(background=None) treats the most common colour as background and skips it.
If the walls/lattice are the most common colour on the board, every tool that calls it sees a
board with NO WALLS -- and plans straight through them. Checked on the stuck level of each
stuck game, against the geometry sprite's own colour.
"""
import importlib.util, pathlib, sys, collections
import numpy as np
sys.path.insert(0, "src")
from admorphiq.tools.base import color_histogram

STUCK = {"ka59":6,"g50t":6,"s5i5":6,"ls20":6,"dc22":5,"wa30":8}
for title, cleared in STUCK.items():
    p = next(pathlib.Path(f"environment_files/{title}").rglob(f"{title}.py"))
    spec = importlib.util.spec_from_file_location("m_"+title, p)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
    L = m.levels[cleared]
    sprites = list(L.get_sprites())
    # composite the level the way the engine does: -1 is alpha
    grid = np.full((64, 64), 0, dtype=int)
    for s in sorted(sprites, key=lambda s: getattr(s, "layer", 0)):
        px = np.array(s.pixels)
        for yy in range(px.shape[0]):
            for xx in range(px.shape[1]):
                v = int(px[yy, xx])
                if v < 0: continue
                Y, X = s.y + yy, s.x + xx
                if 0 <= Y < 64 and 0 <= X < 64: grid[Y, X] = v
    hist = color_histogram(grid)
    bg = int(hist.argmax())
    # EVERY board-sized sprite, not just the largest -- checking one representative is how the
    # first version of this probe missed g50t entirely.
    big = [s_ for s_ in sprites if s_.width * s_.height >= 2000]
    hits = []
    for s_ in big:
        gpx = np.array(s_.pixels); gc = collections.Counter(gpx[gpx >= 0].ravel().tolist())
        gmain = gc.most_common(1)[0][0] if gc else None
        hits.append((f"{s_.width}x{s_.height}", gmain, gmain == bg))
    swallowed = [h for h in hits if h[2]]
    desc = ", ".join(f"{d}:c{c}{'  <== SWALLOWED' if k else ''}" for d, c, k in hits)
    print(f"{title:5} L{cleared+1}  bg=c{bg} ({hist[bg]:4d}/4096)  geometry[{len(big)}] {desc}")
