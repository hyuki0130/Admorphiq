"""R52 arm1 analysis: per-game synthesis fit vs the accept gate, and score deltas.

Reads games1/*.log for the [GF-EWM] synthesized-fit lines and both arms' game
JSONs; prints the fit distribution (the R53 design input: is the gate the
binding constraint, or is runtime-observation quality the wall?) and per-game
score/level deltas.
"""

from __future__ import annotations

import json
import re
from glob import glob
from pathlib import Path

D = Path(__file__).resolve().parent
FIT = re.compile(r"\[GF-EWM\] synthesized fit=([0-9.]+) kept=(\w+)")


def scores(arm: int) -> dict[str, tuple[float, int]]:
    out: dict[str, tuple[float, int]] = {}
    for f in sorted(glob(str(D / f"games{arm}" / "*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for g in d.get("games", []):
            out[(g.get("title") or "?").upper()] = (
                g.get("game_score", 0), g.get("levels_completed", 0)
            )
    return out


def main() -> None:
    fits: dict[str, tuple[float, bool]] = {}
    for logf in sorted(glob(str(D / "games1" / "*.log"))):
        m = FIT.search(open(logf, errors="replace").read())
        if m:
            fits[Path(logf).stem.upper()] = (float(m.group(1)), m.group(2) == "True")

    base, ewm = scores(0), scores(1)
    print(f"{'game':<6}{'fit':>7}{'kept':>6}{'base':>9}{'ewm':>9}{'lvl b/e':>9}")
    for t in sorted(set(base) | set(ewm) | set(fits)):
        fit, kept = fits.get(t, (None, None))
        fs = "   --" if fit is None else f"{fit:.2f}"
        b, e = base.get(t), ewm.get(t)
        bs = "   --" if b is None else f"{b[0]:.4f}"
        es = "   --" if e is None else f"{e[0]:.4f}"
        lv = f"{b[1] if b else '-'}/{e[1] if e else '-'}"
        print(f"{t:<6}{fs:>7}{str(kept):>6}{bs:>9}{es:>9}{lv:>9}")
    if fits:
        vals = [v[0] for v in fits.values()]
        kept = sum(1 for v in fits.values() if v[1])
        print(f"\nfits: n={len(vals)} mean={sum(vals)/len(vals):.3f} "
              f"max={max(vals):.2f} kept={kept} (gate 0.8)")
    both = {t for t in base if t in ewm}
    if both:
        db = sum(ewm[t][0] - base[t][0] for t in both)
        print(f"score delta (ewm-base) over {len(both)} games: {db:+.4f}")


if __name__ == "__main__":
    main()
