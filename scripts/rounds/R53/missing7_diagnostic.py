"""Why the 7 graph-blocked games resist executable-WM synthesis (R53 ceiling evidence).

A deterministic predict_next_frame(frame, action) cannot exceed (1 - nondet_frac)
exact-frame accuracy when identical (state, action) inputs map to different next
frames in the data. This measures that ceiling per game from the collected
transitions — the mechanistic reason the EWM lever is inert on these games,
independent of model scale.
"""
from __future__ import annotations

import hashlib

import numpy as np

MISSING = ["dc22", "g50t", "re86", "s5i5", "su15", "wa30", "sc25"]
CLEARED = ["ar25", "lf52", "tu93"]  # cleared control games with collected data


def stats(game: str):
    import os
    path = f"data/transitions/train/{game}.npz"
    if not os.path.exists(path):
        return None
    d = np.load(path, allow_pickle=True)
    fr, ac, nf = d["frames"], d["actions"], d["next_frames"]
    n = len(ac)
    changed = [int((fr[i] != nf[i]).sum()) for i in range(n)]
    nz = [c for c in changed if c > 0]
    seen: dict = {}
    nondet = pairs = 0
    for i in range(n):
        k = (hashlib.md5(fr[i].tobytes()).hexdigest()[:8], int(ac[i]))
        h = hashlib.md5(nf[i].tobytes()).hexdigest()[:8]
        if k in seen:
            pairs += 1
            nondet += seen[k] != h
        else:
            seen[k] = h
    return {
        "n": n,
        "changed_frac": len(nz) / max(1, n),
        "avg_changed_cells": sum(nz) / max(1, len(nz)),
        "nondet_frac": nondet / max(1, pairs),
        "det_exact_ceiling": 1 - nondet / max(1, pairs),
    }


def main() -> None:
    for label, grp in (("MISSING-7", MISSING), ("CLEARED", CLEARED)):
        print(f"== {label}")
        for g in grp:
            s = stats(g)
            if s is None:
                print(f"  {g}: (no transition data)")
                continue
            print(f"  {g}: nondet={s['nondet_frac']*100:.0f}% "
                  f"det-ceiling={s['det_exact_ceiling']*100:.0f}% "
                  f"avgcells={s['avg_changed_cells']:.1f}")


if __name__ == "__main__":
    main()
