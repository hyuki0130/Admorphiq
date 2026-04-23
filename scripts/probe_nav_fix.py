"""Verify R22 nav fix restores AR25/M0R0 to 2/2 baseline."""

from __future__ import annotations

import time

from admorphiq.strategies.inferential import strat_inferential_agent


TARGETS = ["AR25", "M0R0", "DC22"]
BASELINE = {"AR25": 2, "M0R0": 2, "DC22": 1}


def main() -> None:
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    title_gid = {}
    for info in arcade.get_environments():
        t = (info.title or "").upper()
        if t in TARGETS:
            title_gid[t] = info.game_id

    for title in TARGETS:
        gid = title_gid.get(title)
        if not gid:
            print(f"{title}: env not served")
            continue
        env = arcade.make(gid)
        if env is None:
            print(f"{title}: make failed")
            continue
        t0 = time.time()
        best, label, used = strat_inferential_agent(env, 50000)
        print(
            f"{title:<5} {gid:<22} levels={best}/{BASELINE[title]}  "
            f"actions={used:>6d}  label={label:<40s}  "
            f"elapsed={time.time()-t0:>5.1f}s"
        )


if __name__ == "__main__":
    main()
