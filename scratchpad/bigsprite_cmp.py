import importlib.util, pathlib, sys
import numpy as np
for title, cleared in [("dc22",5),("g50t",6),("ka59",6),("s5i5",6),("ls20",6)]:
    p = next(pathlib.Path(f"environment_files/{title}").rglob(f"{title}.py"))
    spec = importlib.util.spec_from_file_location("m_"+title, p)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
    for tag, idx in (("cleared", cleared-1), ("stuck", cleared)):
        big = sorted(m.levels[idx].get_sprites(), key=lambda s:-(s.width*s.height))[:2]
        d = "  ".join(f"{s.width}x{s.height}@{(s.x,s.y)} {(np.array(s.pixels)>=0).mean():.2f}op"
                      for s in big)
        print(f"{title:5} {tag:8} {d}")
