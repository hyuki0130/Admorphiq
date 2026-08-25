"""Firing is necessary; SOLVING is the point. Score the card on ARCHIVED game versions.

Purpose: `detector_transfer.py` shows the detectors fire on version hashes they were never
written against. That is not yet good news — a detector that fires and then FAILS is worse
than one that never fires, because it takes the game away from the fallback that would
otherwise have played it. This scores both agents on the archived version and compares.

Expected feedback: per game, (fallback score, dispatch score) on a board neither was tuned
on. Dispatch >= fallback means the port carries to unseen variants. Dispatch < fallback
means the detector is claiming games it cannot solve, and the port is HARMFUL on the hidden
set however well it scores on the proxy.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ARCHIVE = Path("environment_files_archive")
LIVE = Path("environment_files")


def score(agent: str, title: str, budget: int) -> tuple[float, int]:
    """Run one game and return (game_score, levels)."""
    import json

    out = Path(tempfile.mkstemp(suffix=".json")[1])
    subprocess.run(
        [sys.executable, "scripts/score_efficiency.py", "--agent", agent,
         "--titles", title, "--max-actions", str(budget), "--out", str(out)],
        capture_output=True, text=True, timeout=3600,
    )
    try:
        payload = json.loads(out.read_text())
    except (OSError, json.JSONDecodeError):
        return (0.0, 0)
    for game in payload.get("games", []):
        if "error" in game:
            return (0.0, 0)
        return (game.get("game_score", 0.0), game.get("levels_completed", 0))
    return (0.0, 0)


def main() -> int:
    games = sys.argv[1:] or ["m0r0", "r11l", "re86", "sk48", "su15"]
    budget = 5000
    staging = Path(tempfile.mkdtemp())
    rows = []
    for name in games:
        if not (ARCHIVE / name).is_dir():
            print(f"{name}: no archived version")
            continue
        backup = staging / name
        shutil.move(str(LIVE / name), str(backup))
        shutil.copytree(ARCHIVE / name, LIVE / name)
        try:
            base = score("chained", name, budget)
            port = score("kaggle_detect", name, budget)
            rows.append((name, base, port))
            flag = ("  <-- GAIN" if port[0] - base[0] > 0.005
                    else "  ⛔ HARMFUL" if base[0] - port[0] > 0.005 else "")
            print(f"{name:6s} fallback {base[0]:.4f} ({base[1]} lvl)   "
                  f"dispatch {port[0]:.4f} ({port[1]} lvl){flag}", flush=True)
        finally:
            shutil.rmtree(LIVE / name, ignore_errors=True)
            shutil.move(str(backup), str(LIVE / name))
    shutil.rmtree(staging, ignore_errors=True)

    if rows:
        b = sum(r[1][0] for r in rows) / len(rows)
        p = sum(r[2][0] for r in rows) / len(rows)
        print(f"\nmean over {len(rows)} archived version(s): fallback {b:.4f} -> dispatch {p:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
