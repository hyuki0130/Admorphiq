"""Compare the two s5i5 boards' opening frames, level by level, in the marker colour.

The two serializations place identical sprites at identical positions on all eight levels
(`scripts/_s5i5_srcdiff.py`), yet every opening frame hashes differently and the tool reads TWO
drawn rider markers on the live board and ZERO on the archived one. This prints what actually
differs in the frame, so the claim rests on pixels rather than on a reading of the level lists.

    .venv/bin/python scripts/_s5i5_framecmp.py /tmp/s5i5_open_live.json /tmp/s5i5_open_arch.json
"""

from __future__ import annotations

import json
import sys

import numpy as np

MARKER = 13


def main() -> None:
    a = json.loads(open(sys.argv[1]).read())
    b = json.loads(open(sys.argv[2]).read())
    for k in sorted(set(a) & set(b), key=int):
        x = np.array(a[k], dtype=np.int16)
        y = np.array(b[k], dtype=np.int16)
        diff = np.argwhere(x != y)
        mx = {(int(i), int(j)) for i, j in np.argwhere(x == MARKER)}
        my = {(int(i), int(j)) for i, j in np.argwhere(y == MARKER)}
        print(f"level {k}: cells differing={len(diff)}  marker cells live={len(mx)} arch={len(my)}")
        only_live = sorted(mx - my)
        only_arch = sorted(my - mx)
        if only_live:
            print(f"   marker only on LIVE {only_live} -> live shows {[int(y[c]) for c in only_live]} there")
        if only_arch:
            print(f"   marker only on ARCH {only_arch} -> arch shows {[int(x[c]) for c in only_arch]} there")
        if len(diff) and not only_live and not only_arch:
            vals = {(int(x[i, j]), int(y[i, j])) for i, j in diff}
            print(f"   non-marker differences, (live,arch) value pairs: {sorted(vals)[:8]}")


if __name__ == "__main__":
    main()
