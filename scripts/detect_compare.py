"""Compare the shipped card, detection dispatch, and the adapter ceiling, per game.

Purpose: a port is only real if it gains a game WITHOUT costing another, so the three
columns have to be read together. The ceiling column says how much of the gap is still
locked behind game_id selection.

Expected feedback: one row per game with GAIN / REGRESSION marked. A game the detect run
has not finished is reported as "not measured yet" and NEVER as zero — reading missing as
zero printed three false regressions on a run that was 7/25 done, and an earlier partial
read claimed lp85 had dropped when the complete data showed it identical.
"""

from __future__ import annotations

import glob
import json
import os
import sys

CARD = "scripts/rounds/SUBCAND1/games"
CEIL = "scripts/rounds/CEILING1"


def load(directory: str) -> dict[str, tuple[float, int]]:
    """Per-game (score, levels) from a run's games/*.json."""
    out: dict[str, tuple[float, int]] = {}
    for path in sorted(glob.glob(f"{directory}/*.json")):
        try:
            payload = json.load(open(path))
        except (OSError, json.JSONDecodeError):
            continue
        for game in payload.get("games", []):
            title = (game.get("title") or "?").lower()
            out[title] = (game.get("game_score", 0.0), game.get("levels_completed", 0))
    return out


def load_ceiling() -> dict[str, tuple[float, int]]:
    """Per-game (score, levels) off each script25 adapter run's SUMMARY.txt."""
    out: dict[str, tuple[float, int]] = {}
    for name in sorted(os.listdir(CEIL)):
        path = os.path.join(CEIL, name, "SUMMARY.txt")
        if not os.path.isfile(path):
            continue
        for line in open(path):
            parts = line.split()
            if len(parts) >= 6 and "/" in parts[2] and parts[-1] in ("ok", "ERROR"):
                out[name] = (float(parts[4]), int(parts[2].split("/")[0]))
                break
    return out


def main() -> int:
    detect_dir = sys.argv[1] if len(sys.argv) > 1 else "scripts/rounds/DETECT1/games"
    card, detect, ceiling = load(CARD), load(detect_dir), load_ceiling()
    keys = sorted(set(card) | set(detect))
    missing = sorted(set(card) - set(detect))

    print(f"{'game':<7}{'card':>9}{'detect':>9}{'ceiling':>9}   delta")
    print("-" * 48)
    for game in keys:
        c = card.get(game, (0.0, 0))[0]
        x = ceiling.get(game, (0.0, 0))[0]
        if game in missing:
            print(f"{game:<7}{c:>9.4f}{'--':>9}{x:>9.4f}   (not measured yet)")
            continue
        d = detect[game][0]
        mark = "  <-- GAIN" if d - c > 0.005 else ("  ⛔ REGRESSION" if c - d > 0.005 else "")
        print(f"{game:<7}{c:>9.4f}{d:>9.4f}{x:>9.4f}{mark}")

    n = len(keys)
    print("-" * 48)
    print(f"{'MEAN':<7}{sum(card.get(g, (0.0, 0))[0] for g in keys) / n:>9.4f}"
          f"{sum(detect.get(g, (0.0, 0))[0] for g in keys) / n:>9.4f}"
          f"{sum(ceiling.get(g, (0.0, 0))[0] for g in keys) / n:>9.4f}   (n={n})")
    if missing:
        scored = [g for g in keys if g not in missing]
        print(f"\n⚠️ PARTIAL — {len(missing)} game(s) not measured yet: {' '.join(missing)}")
        print("   the detect MEAN above counts them as 0 and is NOT comparable to the card.")
        print(f"   scored-only detect mean = "
              f"{sum(detect[g][0] for g in scored) / max(1, len(scored)):.4f} "
              f"over {len(scored)} game(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
