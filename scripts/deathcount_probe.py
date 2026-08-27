"""Count a game's deaths, and name WHO was acting and WHAT permitted the fatal action.

A death is the most informative event a run produces and the harness throws it away: the engine
restores the board, hands back a fresh allowance, and the level counter does not move. So a level
cleared on the third try is indistinguishable from a level cleared slowly, and the actions that
went into the two binned attempts are invisible.

⛔ FOUR WAYS TO MEASURE THIS THAT DO NOT WORK, each of which returns a plausible number:

  * driving the env with ``env.step(action)`` — the runner passes ``data=action_data.model_dump()``,
    so every click arrives without its coordinates and the GAME appears to crash;
  * building the agent yourself through a factory — the runner supplies giveup/stall/ctx_budget and
    a hand-built one loses them, which on one game scored 0.0338 against a real 0.1648;
  * reading the state off the frame the AGENT is given — a restart the runner absorbs is never
    shown to the agent, so the count is zero;
  * substituting the agent class in the runner's namespace — the runner imports it inside the
    function, so the substitution is inert while the score still matches perfectly.

That last one is the dangerous one, and the rule this file is built on: **a number that reproduces
the real score is not evidence the instrument is attached.** So this drives the loop itself with
the runner's own argument shapes, and prints the score it reproduced next to the count, and the
count is only believable when a deliberately WRONG probe would have shown something different.

What it reports per death: which tool held the board, the action it proposed, and — for a tool
that keeps a plan of legs — the PREDICATE that permitted it, which is the tool's own prediction of
where the body would come to rest. Counting those over one run is what separates "the tool walked
into something it could not see" from "the tool walked into something it had already classified".

    uv run python scripts/deathcount_probe.py <title> [cap] [tool]
"""

from __future__ import annotations

import sys
from collections import Counter

sys.path.insert(0, "src")


def main(title: str, cap: int, watch: str | None) -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    target = next((t for t in tools if t.name == watch), None) if watch else None

    # The tool's own reading of the action it is about to take, captured BEFORE it is taken --
    # after a death the tool has already been reset and cannot be asked.
    def _reading(who: str) -> str:
        # ⛔ Only ever the ACTING tool's own reading. Printing the watched tool's note while a
        # different tool holds the board attributes one tool's state to another's action, and it
        # is convincing: every death on the sixth board carried the watched tool's stale note
        # even though sixteen of them were taken by another tool entirely.
        if target is None or who != target.name:
            return "-"
        plan = getattr(target, "_plan", None)
        if plan:
            leg = plan[0]
            return f"planned:{leg[3]}" if len(leg) > 3 else "planned"
        note = str(getattr(target, "_note", ""))
        return f"unplanned:{note.split(';')[0][:28]}" if note else "unplanned"

    frames = [obs]
    marks: list[tuple[int, int]] = []
    deaths: list[tuple[int, int, str, str, str]] = []
    picks: Counter = Counter()
    levels = step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        who = str(agent._current)
        picks[who] += 1
        reading = _reading(who)
        # ⛔ The runner's own call shape. Passing the action alone strips a click's coordinates.
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step + 1))
            levels = now
        elif str(getattr(obs, "state", "")).endswith("GAME_OVER"):
            deaths.append((levels + 1, step + 1, who, str(getattr(act, "name", act)), reading))

    print(f"{title}: {levels} levels in {step + 1} actions   clears at {marks}")
    print(f"   acted {dict(picks.most_common(4))}")
    print(f"   {len(deaths)} deaths")
    after_last = sum(1 for d in deaths if d[0] > levels)
    print(f"      {len(deaths) - after_last} on levels that were later cleared -- these cost score")
    print(f"      {after_last} after the last clear -- these cost nothing")
    for lvl, at, who, action, reading in deaths:
        tag = "COSTS" if lvl <= levels else "free "
        print(f"      [{tag}] L{lvl} action {at:4d}  tool {who:14s} {action:8s} {reading}")
    if target is not None:
        scoring = [d for d in deaths if d[0] <= levels]
        print(f"   what permitted the fatal action, {target.name} only:")
        for reading, n in Counter(d[4] for d in scoring if d[2] == target.name).most_common():
            print(f"      {n} x {reading}")
    by_tool = Counter(d[2] for d in deaths if d[0] <= levels)
    print(f"   who took the deaths that cost score: {dict(by_tool)}")
    gaps = [b[1] - a[1] for a, b in zip(deaths, deaths[1:]) if a[0] > levels and b[0] > levels]
    if gaps and max(gaps) - min(gaps) <= 1:
        print(f"   the free deaths are PERIODIC at {gaps[0]} actions -- that is a clock, "
              f"not a hazard")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1600,
         sys.argv[3] if len(sys.argv) > 3 else None)
