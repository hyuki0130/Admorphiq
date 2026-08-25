"""Measure a ported adapter detector's FALSE POSITIVE rate across all 25 public games.

Purpose: detection dispatch is only safe if a detector fires on its own mechanic and on
nothing else. Porting an adapter without this number ships a solver that can hijack an
unrelated private game and burn its action budget.

Expected feedback: one line per adapter under test, listing every game whose FIRST frame
the detector accepts. The adapter's own game must appear; anything else is a false
positive and blocks the port until the signature is tightened.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402

from admorphiq.adapters25 import discover_adapters  # noqa: E402


def main() -> int:
    under_test = sys.argv[1:] or ["ft09"]
    adapters = discover_adapters()
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)

    first_frames: dict[str, object] = {}
    for env_info in arcade.get_environments():
        title = (env_info.title or env_info.game_id).lower()
        key = title.split("-")[0][:4]
        if key in first_frames:
            continue
        env = arcade.make(env_info.game_id)
        if env is None or env.observation_space is None:
            continue
        first_frames[key] = env.observation_space

    print(f"booted {len(first_frames)} games: {' '.join(sorted(first_frames))}\n")

    failed = 0
    for name in under_test:
        cls = adapters.get(name)
        if cls is None:
            print(f"{name}: NO SUCH ADAPTER")
            failed += 1
            continue
        fires = sorted(g for g, frame in first_frames.items() if cls.detect(frame))
        own = "yes" if name in fires else "NO"
        others = [g for g in fires if g != name]
        print(f"{name}: fires on own game = {own} | false positives = "
              f"{len(others)}/{len(first_frames) - 1} {others}")
        if own == "NO" or others:
            failed += 1

    print("\n" + ("PASS — every detector fires on its own mechanic and nothing else"
                  if not failed else f"⛔ {failed} adapter(s) not portable as-is"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
