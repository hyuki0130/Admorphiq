"""Does a round's SUMMARY.txt agree with its own games/*.json?

Purpose: a live aggregator writes SUMMARY.txt as the run progresses, and nothing re-writes it
if the final pass does not fire. The stale file then reports a PARTIAL run as if it were the
answer — measured today on scripts/rounds/SUBCAND1, whose summary read "LIVE 21/25, mean
0.0650" while the complete data read 25/25 and 0.0566. Understating coverage while
overstating the mean is the direction that flatters a card, so it will not announce itself.

Expected feedback: per round directory, the summary's own claim beside the data's, and a
verdict. AGREES means the file may be quoted. STALE means quote the data, not the file.

Usage: summary_agrees.py [round-dir …]   (default: every dir under scripts/rounds with both)
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROUNDS = Path("scripts/rounds")


def from_data(games_dir: Path) -> tuple[int, float]:
    """(games scored, mean game_score) straight from the run's own JSON."""
    scores: dict[str, float] = {}
    for path in sorted(games_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for game in payload.get("games", []):
            if "error" in game:
                continue
            scores[(game.get("title") or path.stem).lower()] = game.get("game_score", 0.0)
    if not scores:
        return (0, 0.0)
    return (len(scores), sum(scores.values()) / len(scores))


def from_summary(path: Path) -> tuple[int | None, float | None]:
    """(games claimed, mean claimed) as the summary file states them."""
    text = path.read_text()
    n = re.search(r"(\d+)\s*/\s*25", text)
    mean = re.search(r"mean game_score\s*=\s*([0-9.]+)", text)
    return (int(n.group(1)) if n else None,
            float(mean.group(1)) if mean else None)


def main() -> int:
    targets = [Path(a) for a in sys.argv[1:]] or [
        Path(d).parent for d in sorted(glob.glob(str(ROUNDS / "*" / "SUMMARY.txt")))
        if (Path(d).parent / "games").is_dir()
    ]
    stale = 0
    for round_dir in targets:
        summary, games = round_dir / "SUMMARY.txt", round_dir / "games"
        if not (summary.is_file() and games.is_dir()):
            continue
        d_n, d_mean = from_data(games)
        s_n, s_mean = from_summary(summary)
        if s_n is None or s_mean is None:
            # Not a full-25 aggregator summary — single-game and per-adapter runs use other
            # formats and have no claim to contradict. Reporting those as STALE was this
            # checker's own first failure: 351 of them, every one a false alarm.
            continue
        agree = s_n == d_n and abs(s_mean - d_mean) < 0.0005
        stale += not agree
        verdict = "AGREES" if agree else "⛔ STALE — quote the DATA, not the file"
        print(f"{round_dir.name:14s} summary {s_n:>3}/25 {s_mean:>8.4f} "
              f"| data {d_n:>3}/25 {d_mean:>8.4f}  {verdict}")
    if stale:
        print(f"\n{stale} round(s) with a summary its own data contradicts")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
