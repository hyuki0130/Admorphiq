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
from arcengine import GameAction  # noqa: E402

from admorphiq.adapters25 import discover_adapters  # noqa: E402
from admorphiq.adapters25.base import GameAdapter, available_action_ids  # noqa: E402

_PROBE_ACTION_ID = 3
_PROBE_ACTION = GameAction.ACTION3


def main() -> int:
    under_test = sys.argv[1:] or ["ft09"]
    adapters = discover_adapters()
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)

    # Each game is asked its question IMMEDIATELY after boot. Booting all 25 first and
    # reading them afterwards gave a WRONG answer — ls20's detector read as not firing on
    # its own game while `_parse` on a freshly booted ls20 frame plainly succeeded. The
    # observation object does not survive later `make()` calls, so the earlier version was
    # measuring stale frames for every game but the last.
    tested = [n for n in under_test if adapters.get(n) is not None]
    for missing in [n for n in under_test if adapters.get(n) is None]:
        print(f"{missing}: NO SUCH ADAPTER")

    hits: dict[str, list[str]] = {n: [] for n in tested}
    games: list[str] = []
    for env_info in arcade.get_environments():
        key = (env_info.title or env_info.game_id).lower().split("-")[0][:4]
        if key in games:
            continue
        env = arcade.make(env_info.game_id)
        if env is None or env.observation_space is None:
            continue
        games.append(key)
        frame = env.observation_space
        for name in tested:
            if adapters[name].detect(frame):
                hits[name].append(key)

        # PROBE detectors get one shared transition, which is the whole point of the
        # contract: the cost is one action however many adapters read it. The probe is
        # horizontal because a VERTICAL one does not separate m0r0 from ka59 — measured,
        # both move their pieces the same way under ACTION1.
        # __func__: a classmethod on a class is a fresh bound object every access, so an
        # identity test on the bound form calls every adapter probe-capable.
        probed = [n for n in tested
                  if adapters[n]._detect_mechanic_probed.__func__
                  is not GameAdapter._detect_mechanic_probed.__func__]
        if not probed:
            continue
        simple_ids, _has_click = available_action_ids(frame)
        if _PROBE_ACTION_ID not in simple_ids:
            continue
        after = env.step(_PROBE_ACTION)
        for name in probed:
            if adapters[name].detect_probed(frame, after) and key not in hits[name]:
                hits[name].append(key)

    print(f"booted {len(games)} games: {' '.join(sorted(games))}\n")

    failed = len(under_test) - len(tested)
    for name in tested:
        fires = sorted(hits[name])
        own = "yes" if name in fires else "NO"
        others = [g for g in fires if g != name]
        print(f"{name}: fires on own game = {own} | false positives = "
              f"{len(others)}/{len(games) - 1} {others}")
        if own == "NO" or others:
            failed += 1

    print("\n" + ("PASS — every detector fires on its own mechanic and nothing else"
                  if not failed else f"⛔ {failed} adapter(s) not portable as-is"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
