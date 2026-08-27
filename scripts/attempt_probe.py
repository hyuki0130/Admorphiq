"""Where did a game's actions actually GO — into solving it, or into attempts that were binned?

A per-game score says a game is expensive. It does not say WHICH KIND of expensive, and the two
kinds want opposite work:

  * the winning run is slow — the route is bad, and the search is what to improve;
  * the winning run is FAST and the game is expensive because the attempts before it were thrown
    away — the route is already right, and what to improve is not dying.

Nothing in the harness separates those, because a restart is invisible in the level counter: the
engine restores the board, hands back a fresh allowance, and the score simply carries the actions
already spent. So a level cleared on the third try reads exactly like a level cleared slowly.

This splits a real harness run into LEVELS and, inside each, ATTEMPTS, and prices them. On the
game it was written for, the answer inverted the plan: the winning attempts were 56, 42 and 37
actions against human baselines of 48, 44 and 33 -- one of them BETTER than the human -- and every
bit of the game's shortfall was in four earlier attempts that were binned. No amount of route
improvement was going to pay for that, and two days could have gone into it.

    uv run python scripts/attempt_probe.py where <title> [cap]
    uv run python scripts/attempt_probe.py all [cap]

The last column of ``where`` is the one to read: what the game would score if only its winning
attempts were paid for. A game whose ceiling is near its score is a SEARCH problem; a game whose
ceiling is far above it is an ATTEMPT problem, and they are not fixed by the same change.
"""

from __future__ import annotations

import sys
from collections import Counter

sys.path.insert(0, "src")


def _arcade():
    from arc_agi import Arcade, OperationMode
    return Arcade(operation_mode=OperationMode.OFFLINE)


def _agent(cap: int):
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    return UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)


def _rhae(costs: list[int], human: list[int], levels_total: int) -> float:
    """The metric, as the scorer computes it: squared action ratio, weighted by level index."""
    weight = sum(range(1, levels_total + 1))
    if not weight:
        return 0.0
    got = 0.0
    for i, (mine, theirs) in enumerate(zip(costs, human), start=1):
        if mine <= 0:
            continue
        got += i * min(theirs / mine, 1.0) ** 2
    return got / weight


def run(title: str, cap: int) -> dict:
    """Play the game and record, action by action, which level and which attempt it belonged to."""
    arcade = _arcade()
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = _agent(cap)
    frames = [obs]
    human = list(getattr(info, "baseline_actions", []) or [])
    # level -> list of attempts; an attempt is [clicks, moves, outcome]
    levels: list[list[list]] = [[[0, 0, "running"]]]
    picks: Counter = Counter()
    done = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        picks[str(agent._current)] += 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        # ⛔ A click is told from a move by the ACTION, not by whether a payload came back: the
        # simple actions carry an (empty) data object too, and reading that counted every move
        # on a lateral-only board as a click.
        click = str(getattr(act, "name", act)).endswith("6")
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        cur = levels[-1][-1]
        cur[0 if click else 1] += 1
        now = int(getattr(obs, "levels_completed", done) or 0)
        if now != done:
            cur[2] = "CLEARED"
            done = now
            levels.append([[0, 0, "running"]])
        elif str(getattr(obs, "state", "")).endswith("GAME_OVER"):
            cur[2] = "binned"
            levels[-1].append([0, 0, "running"])
    if levels and levels[-1][-1][2] == "running" and sum(levels[-1][-1][:2]) == 0:
        levels[-1].pop()
    return {"title": (info.title or info.game_id).lower(), "human": human,
            "levels": levels, "picks": picks, "actions": step + 1, "cleared": done}


def _summarise(r: dict) -> tuple[float, float, list[str]]:
    """Score as played, score if only the winning attempts were paid for, and the per-level lines."""
    human, out = r["human"], []
    paid: list[int] = []
    won: list[int] = []
    for idx, attempts in enumerate(r["levels"]):
        if not attempts:
            continue
        if not any(a[2] == "CLEARED" for a in attempts):
            continue
        total = sum(a[0] + a[1] for a in attempts)
        winner = next(a for a in attempts if a[2] == "CLEARED")
        paid.append(total)
        won.append(winner[0] + winner[1])
        h = human[idx] if idx < len(human) else 0
        binned = total - (winner[0] + winner[1])
        detail = " ".join(f"{a[0] + a[1]}{'c' if a[2] == 'CLEARED' else 'x'}" for a in attempts)
        out.append(f"   L{idx + 1}: paid {total:4d}  won in {winner[0] + winner[1]:3d} "
                   f"({winner[0]} clicks, {winner[1]} moves)  binned {binned:3d}  "
                   f"human {h:4d}   [{detail}]")
    n = max(len(human), len(paid))
    return _rhae(paid, human, n), _rhae(won, human, n), out


def where(title: str, cap: int) -> None:
    r = run(title, cap)
    now, ceiling, lines = _summarise(r)
    print(f"{r['title']}: {r['cleared']} levels in {r['actions']} actions   "
          f"acted {dict(r['picks'].most_common(3))}")
    for ln in lines:
        print(ln)
    kind = "ATTEMPTS" if ceiling - now > 0.02 else "SEARCH"
    print(f"   scored {now:.4f}   ceiling if no attempt were binned {ceiling:.4f}   "
          f"-> the cost is {kind}")


def every(cap: int) -> None:
    arcade = _arcade()
    rows = []
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        name = (info.title or info.game_id).lower()
        try:
            r = run(name, cap)
        except Exception as exc:  # noqa: BLE001 - a game that will not run is still a report
            print(f"{name:8s} ERROR {exc}", flush=True)
            continue
        now, ceiling, _ = _summarise(r)
        binned = sum(sum(a[0] + a[1] for a in att if a[2] != "CLEARED") for att in r["levels"])
        rows.append((ceiling - now, name, r["cleared"], now, ceiling, binned))
        print(f"{name:8s} {r['cleared']} levels  scored {now:.4f}  ceiling {ceiling:.4f}  "
              f"binned {binned:5d} actions", flush=True)
    print("\nmost recoverable by not binning attempts:")
    for gain, name, lv, now, ceiling, binned in sorted(rows, reverse=True)[:8]:
        print(f"   {name:8s} +{gain:.4f}  ({now:.4f} -> {ceiling:.4f}, {lv} levels, {binned} binned)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "all":
        every(int(sys.argv[2]) if len(sys.argv) > 2 else 1500)
    else:
        where(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1500)
