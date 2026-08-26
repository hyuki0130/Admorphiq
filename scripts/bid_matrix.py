"""Every registered tool's `detect` on every sample game's first frame.

⛔ This is the integrator's check and nobody else can run it. Selectivity is a property of the
tool SET: a tool that bids on a board it cannot solve takes the turn from the tool that can, and
measured 2026-08-27 that cost one game 0.4286 while the offender gained nothing. A tool's author
sees only their own game.

Reads: one row per tool. `own` is the highest bid it makes anywhere; `elsewhere` is the highest bid
it makes on a game that is not its best. A healthy rule-recovery tool has a high `own` and an
`elsewhere` of 0.00.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.registry import default_tools

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    titles: list[str] = []
    seen: set[str] = set()
    ids: dict[str, str] = {}
    for info in arcade.get_environments():
        title = (info.title or info.game_id).split("-")[0].lower()
        if title in seen:
            continue
        seen.add(title)
        titles.append(title)
        ids[title] = info.game_id

    rows: list[tuple[float, str, str, float, list[str]]] = []
    for tool in default_tools():
        bids: dict[str, float] = {}
        for title in titles:
            # ⛔ A FRESH env and a FRESH tool per cell. The first version built all 25
            # observations up front and reused them across every tool: a stateful tool then read a
            # frame whose env had moved on, and one that scores 0.62 on its own game was reported
            # as bidding 0.00 everywhere. The instrument was wrong, not the tool.
            obs = arcade.make(ids[title]).reset()
            probe = type(tool)()
            try:
                bids[title] = float(probe.detect([], obs))
            except Exception:  # noqa: BLE001
                bids[title] = 0.0
        best_game = max(bids, key=lambda g: bids[g])
        own = bids[best_game]
        others = {g: b for g, b in bids.items() if g != best_game and b > 0}
        elsewhere = max(others.values(), default=0.0)
        rows.append((own, tool.name, best_game, elsewhere, sorted(others)))

    rows.sort(key=lambda r: (-r[3], -r[0]))
    print(f"{'tool':16s} {'best game':10s} {'own':>5s} {'elsewhere':>9s}  bids on")
    for own, name, game, elsewhere, others in rows:
        flag = "  <- BIDS ON OTHER GAMES" if elsewhere > 0 else ""
        print(f"{name:16s} {game:10s} {own:5.2f} {elsewhere:9.2f}  "
              f"{','.join(others[:6]) if others else '-'}{flag}")


if __name__ == "__main__":
    main()
