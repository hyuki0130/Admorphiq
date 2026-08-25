"""Do the detectors fire on a DIFFERENT VERSION of the same game?

Purpose: a detector measured at 0/24 false positives fires on exactly one public board, and
that leaves the question a submission actually turns on — will it fire on a board it was
never written against? `environment_files_archive/` holds an older version hash for fifteen
games, i.e. the same mechanic with different internals, which the project has recorded as a
proxy for the private set's obfuscation.

Expected feedback: per ported adapter, whether its detector fires on its own game's ARCHIVED
version. A fire is evidence the detector reads the MECHANIC; a miss means it reads this
board, and the port earns nothing on the hidden set however well it scores on the proxy.
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
    ported = [a for a in sys.argv[1:]] or ["m0r0", "r11l", "re86", "sk48", "su15"]
    available = sorted(n for n in ported if (ARCHIVE / n).is_dir())
    missing = [n for n in ported if n not in available]
    if missing:
        print(f"no archived version for: {' '.join(missing)}")
    if not available:
        return 1

    # The engine loads whatever sits under environment_files/, so the archived version is
    # swapped IN for the run and the live tree restored afterwards.
    staging = Path(tempfile.mkdtemp())
    fired: list[str] = []
    for name in available:
        backup = staging / name
        shutil.move(str(LIVE / name), str(backup))
        shutil.copytree(ARCHIVE / name, LIVE / name)
        served = sorted(x.name for x in (LIVE / name).iterdir() if x.is_dir())
        print(f"{name:6s} environment_files/{name} now holds: {served}")
        try:
            fired += _probe_one(name)
        finally:
            shutil.rmtree(LIVE / name, ignore_errors=True)
            shutil.move(str(backup), str(LIVE / name))
    shutil.rmtree(staging, ignore_errors=True)

    print(f"\nfired on the archived version: {len(fired)}/{len(available)} "
          f"{sorted(fired) or '(none)'}")
    print("a fire = the detector reads the MECHANIC; a miss = it reads this board")
    return 0


def _probe_one(name: str) -> list[str]:
    """Boot the archived version and ask that adapter's detector about it."""
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    from admorphiq.adapters25 import discover_adapters
    from admorphiq.adapters25.base import GameAdapter, available_action_ids

    cls = discover_adapters()[name]
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    for env_info in arcade.get_environments():
        if name not in (env_info.title or env_info.game_id).lower():
            continue
        env = arcade.make(env_info.game_id)
        if env is None or env.observation_space is None:
            continue
        frame = env.observation_space
        hit = cls.detect(frame)
        if not hit and cls._detect_mechanic_probed.__func__ is not (
            GameAdapter._detect_mechanic_probed.__func__
        ):
            simple_ids, _ = available_action_ids(frame)
            if 3 in simple_ids:
                hit = cls.detect_probed(frame, env.step(GameAction.ACTION3))
        print(f"{name:6s} archived {env_info.game_id:20s} detector fires: {hit}")
        return [name] if hit else []
    print(f"{name:6s} archived version did not load")
    return []


if __name__ == "__main__":
    raise SystemExit(main())
