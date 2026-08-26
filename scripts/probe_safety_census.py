"""How expensive is it to LOOK? One short probe walk per sample game.

Two games are now measured to punish a wrong action — ft09 charges a level, tn36 ends the game
after about three wrong submissions — so "explore first, decide later" is not free and cannot be
assumed. A generic tool has to know, per game, whether probing costs anything.

Per game this takes a handful of actions and reports:

  responsive  probes that changed the board (the HUD is subtracted, see below)
  lost        probes after which `levels_completed` went DOWN
  died        the run hit an empty frame or a terminal state
  hud         cells that change under almost every probe — a counter or timer, not the board
  avail       the actions the ENGINE declares legal — the authoritative answer
  moves       simple actions (1-5) that changed the board

⛔ `moves` alone is a LIE and was reported as one first: ft09 declares `available_actions == [6]`
yet all five simple actions "changed the board", because an illegal action draws a refusal
screen. A visible change is not evidence that an action is accepted. Read `avail`.

⛔ The HUD subtraction is load-bearing, not cosmetic: ft09 marches an action counter one pixel
per action, so without it EVERY probe scores as responsive and the census says nothing.
"""

from __future__ import annotations

import sys
from collections import Counter

sys.path.insert(0, "src")

from admorphiq.adapters25.base import canonical_layer  # noqa: E402

PROBES = 12


def _grid(obs) -> list[list[int]] | None:
    if not (getattr(obs, "frame", None) or []):
        return None
    return canonical_layer(obs)


def walk(env, spots: list[tuple[int, int]]) -> dict[str, object]:
    from arcengine import GameAction

    obs = env.reset()
    start = _grid(obs)
    if start is None:
        return {"died": True, "responsive": 0, "lost": 0, "hud": 0, "acted": 0, "moves": 0, "avail": []}
    size = len(start)
    deltas: list[set[tuple[int, int]]] = []
    lost = 0
    moved = 0
    died = False
    acted = 0
    level = int(getattr(obs, "levels_completed", 0) or 0)
    for y, x in spots:
        before = _grid(obs)
        if before is None:
            died = True
            break
        obs = env.step(GameAction.ACTION6, data={"x": x, "y": y})
        acted += 1
        after = _grid(obs)
        if after is None:
            died = True
            break
        deltas.append({(r, c) for r in range(size) for c in range(size) if before[r][c] != after[r][c]})
        now = int(getattr(obs, "levels_completed", level) or 0)
        if now < level:
            lost += 1
        level = now
    for act in (GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3,
                GameAction.ACTION4, GameAction.ACTION5):
        before = _grid(obs)
        if before is None or died:
            break
        obs = env.step(act)
        acted += 1
        after = _grid(obs)
        if after is None:
            died = True
            break
        if any(before[r][c] != after[r][c] for r in range(size) for c in range(size)):
            moved += 1
    avail = sorted(int(a) for a in (getattr(obs, "available_actions", None) or []))
    seen: Counter[tuple[int, int]] = Counter()
    for d in deltas:
        seen.update(d)
    hud = {c for c, n in seen.items() if deltas and n >= 0.8 * len(deltas)}
    responsive = sum(1 for d in deltas if d - hud)
    return {"died": died, "responsive": responsive, "lost": lost, "hud": len(hud),
            "acted": acted, "moves": moved, "avail": avail}


def main() -> None:
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    seen: set[str] = set()
    print(f"{'game':6s} {'acts':>5s} {'resp':>5s} {'moves':>5s} {'lost':>5s} {'avail':>12s}  verdict")
    for info in arcade.get_environments():
        title = (info.title or info.game_id).split("-")[0].lower()
        if title in seen:
            continue
        seen.add(title)
        env = arcade.make(info.game_id)
        g0 = _grid(env.reset())
        size = len(g0) if g0 else 64
        step = max(4, size // 5)
        spots = [(y, x) for y in range(step, size - step + 1, step) for x in range(step, size - step + 1, step)]
        r = walk(env, spots[:PROBES])
        verdict = (
            "DEADLY — probing ends the game" if r["died"]
            else "COSTLY — probing loses levels" if r["lost"]
            else "click + move" if 6 in r["avail"] and set(r["avail"]) - {6, 7}
            else "click-only" if 6 in r["avail"]
            else "MOVE-only" if r["avail"]
            else "no legal action declared"
        )
        print(f"{title:6s} {r['acted']:5d} {r['responsive']:5d} {r['moves']:5d} {r['lost']:5d} "
              f"{str(r['avail']):>12s}  {verdict}")


if __name__ == "__main__":
    main()
