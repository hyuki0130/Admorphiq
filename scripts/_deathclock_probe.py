"""Can a tool learn its own action allowance by DYING ONCE, without reading any pixels?

The pixel route was measured first and it mostly does not exist: of twenty-five games, exactly one
(bp35, row 63, scale 1) renders its action count as a readable bar. Twelve games nevertheless
DECLARE a per-level allowance in their level data, and on ten of them the human baseline exceeds
that allowance — so the metric's own baselines contain retries, and a tool that knew its remaining
allowance could stop gambling the last twenty actions.

⛔ So the reader does not have to be a reader. `obs.state` reports GAME_OVER directly, and the
action count at that moment IS the allowance whenever the game ends on overrun. If the death length
is CONSTANT for a level, one death teaches the tool the number for every later attempt at it — free,
frame-independent, and available on every game rather than on the one that draws a bar.

This measures exactly that, per game: split the run into attempts at GAME_OVER and at level
changes, record how long each attempt ran and how it ended, and report whether the deaths on a level
agree with each other.

Expected feedback: deaths of a constant length on a level mean the allowance is learnable in one
death and the mechanism is sound. Deaths of scattered lengths mean the game ends for a reason other
than an allowance — a hazard, a lost life — and the number learned would be a fiction. Zero deaths
on a game that declares an allowance means the allowance does not bite there (rule 7g), and nothing
should be built for it.

Usage: _deathclock_probe.py <index 1..25> [cap]   — one JSON line per game.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict


def main() -> None:
    idx = int(sys.argv[1])
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 1500

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    infos = sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id).lower())
    if idx < 1 or idx > len(infos):
        print(json.dumps({"index": idx, "error": f"only {len(infos)} environments"}))
        return
    info = infos[idx - 1]
    title = (info.title or info.game_id).lower()[:4]
    print(f"# {title}: starting", file=sys.stderr, flush=True)

    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]

    lvl = int(getattr(obs, "levels_completed", 0) or 0)
    start_lvl = lvl
    t = 0                      # actions in the current attempt
    steps = 0
    deaths: dict[int, list[int]] = defaultdict(list)   # level -> attempt lengths that DIED
    clears: dict[int, list[int]] = defaultdict(list)   # level -> attempt lengths that CLEARED
    was_over = False

    while steps < cap:
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        steps += 1
        t += 1
        state = str(getattr(obs, "state", ""))
        now = int(getattr(obs, "levels_completed", 0) or 0)
        over = "GAME_OVER" in state
        if now > lvl:
            # ⛔ tested `>`, never `!=` — a collapse and a clear are the same to a boolean (7f)
            clears[lvl].append(t)
            print(f"# {title}: level {lvl} -> {now} after {t} actions", file=sys.stderr, flush=True)
            lvl = now
            t = 0
            was_over = False
        elif now < lvl:
            deaths[lvl].append(t)
            print(f"# {title}: FELL BACK {lvl} -> {now} after {t}", file=sys.stderr, flush=True)
            lvl = now
            t = 0
            was_over = False
        elif over and not was_over:
            deaths[lvl].append(t)
            was_over = True
            t = 0
        elif not over:
            was_over = False
        if steps % 250 == 0:
            print(f"# {title}: {steps} actions, level {lvl}", file=sys.stderr, flush=True)

    def summarise(d):
        return {str(k): v[:12] for k, v in sorted(d.items())}

    consistent = {}
    for k, v in deaths.items():
        if len(v) >= 2:
            consistent[str(k)] = {"n": len(v), "min": min(v), "max": max(v),
                                  "constant": min(v) == max(v)}
    out = {"index": idx, "title": title, "actions": steps,
           "start_level": start_lvl, "end_level": lvl, "advanced": lvl > start_lvl,
           "deaths": summarise(deaths), "clears": summarise(clears),
           "death_total": sum(sum(v) for v in deaths.values()),
           "death_count": sum(len(v) for v in deaths.values()),
           "consistency": consistent}
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
