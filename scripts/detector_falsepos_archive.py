"""Do the detectors misfire on boards they were never tuned against?

Purpose: the 0/24 gate measured false positives on the SAME 25 public boards the detectors were
written on, which cannot show what happens on an unfamiliar one. The submission's hidden score
came in below the card it replaced, and "detectors misfiring on private games" is one of the
remaining explanations. `environment_files_archive/` holds an older version hash for fifteen
games — boards nobody tuned any detector against — so every detector can be asked about every
one of them.

Expected feedback: per archived board, which detectors fire. A detector firing on a board that
is not its own game is a MISFIRE on unfamiliar input, which is the failure mode the hidden score
would show as a drop. Silence everywhere is evidence the detectors stay quiet off their mechanic.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

ARCHIVE = Path("environment_files_archive")
LIVE = Path("environment_files")


def main() -> int:
    from arc_agi import Arcade, OperationMode

    from admorphiq.adapters25 import discover_adapters
    from admorphiq.adapters25.base import GameAdapter

    adapters = discover_adapters()
    ported = {
        name: cls for name, cls in adapters.items()
        if cls._detect_mechanic.__func__ is not GameAdapter._detect_mechanic.__func__
    }
    print(f"ported detectors: {' '.join(sorted(ported))}\n")

    staging = Path(tempfile.mkdtemp())
    misfires = 0
    for game_dir in sorted(ARCHIVE.iterdir()):
        if not game_dir.is_dir():
            continue
        name = game_dir.name
        backup = staging / name
        shutil.move(str(LIVE / name), str(backup))
        shutil.copytree(game_dir, LIVE / name)
        try:
            arcade = Arcade(operation_mode=OperationMode.OFFLINE)
            for env_info in arcade.get_environments():
                if name not in (env_info.title or env_info.game_id).lower():
                    continue
                env = arcade.make(env_info.game_id)
                if env is None or env.observation_space is None:
                    break
                frame = env.observation_space
                fired = sorted(n for n, cls in ported.items() if cls.detect(frame))
                wrong = [n for n in fired if n != name]
                misfires += len(wrong)
                mark = f"  ⛔ MISFIRE {wrong}" if wrong else ""
                print(f"archived {name:6s} fires: {fired or '(none)'}{mark}")
                break
        finally:
            shutil.rmtree(LIVE / name, ignore_errors=True)
            shutil.move(str(backup), str(LIVE / name))
    shutil.rmtree(staging, ignore_errors=True)

    print(f"\n{misfires} misfire(s) across {len(list(ARCHIVE.iterdir()))} unfamiliar boards")
    return 1 if misfires else 0


if __name__ == "__main__":
    raise SystemExit(main())
