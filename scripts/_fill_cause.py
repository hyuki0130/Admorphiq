"""When the harness probe fills a turn, did the tool have NO PLAN — or a plan it could not EXPRESS?

`UnifiedAgent._fill_from_current` ends with `self._queue = legal or self._probe(...)`, and `legal`
is `[s for s in steps if self._legal(s, simple_ids, action6)]`. So a filled turn has exactly two
possible causes and they want opposite fixes:

  NOPLAN   `propose` returned nothing. The tool cannot read this board. The fix is the tool, or
           handing the board to one that can.
  ILLEGAL  `propose` returned steps and every one of them was REJECTED — the tool asked for an
           action the engine is not offering on this frame (a click where ACTION6 is unavailable,
           a key not in `simple_ids`). The fix is the tool's action vocabulary, or the harness
           telling it what is available. Nothing about the board is unreadable.

Measured across the set, filled turns are 43 of 5937 actions, but they concentrate: dc22 16,
lf52 13, bp35 8, ls20 8 — and on ls20, a FUEL game where actions are the resource, all 8 are
inert. Which cause they have has never been measured.

    uv run python scripts/_fill_cause.py <index 1..25> [cap]

⛔ Level changes are tested as `> previous` (rule 7f). Progress prints from the first action
(rule 7e). One json line on stdout.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _log(*a):
    print(*a, file=sys.stderr, flush=True)


def main() -> None:
    idx = int(sys.argv[1]) - 1
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    import numpy as np
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.base import availability
    from admorphiq.tools.segment import board_changed

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    infos = sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id).lower())
    if idx >= len(infos):
        print(json.dumps({"skip": idx}))
        return
    info = infos[idx]
    title = (info.title or info.game_id).lower()
    _log(f"[fill] {title} cap={cap}")
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)

    # Every tool's propose is wrapped so the LAST return value is visible after choose_action.
    # ⛔ The harness swallows a propose that throws, and a swallowed exception is a third cause
    # that reads exactly like NOPLAN — so it is counted separately rather than folded in.
    seen: dict = {"steps": None, "threw": False}

    def wrap(tool):
        real = tool.propose

        def inner(*a, **k):
            try:
                out = real(*a, **k)
            except Exception:
                seen["threw"] = True
                raise
            seen["steps"] = out
            return out
        return inner

    for t in agent.tools.values():
        t.propose = wrap(t)                       # type: ignore[method-assign]

    filled = {"n": 0}
    real_probe = agent._probe

    def _probe(simple_ids, action6):
        filled["n"] += 1
        return real_probe(simple_ids, action6)

    agent._probe = _probe                          # type: ignore[method-assign]

    frames = [obs]
    done = 0
    noplan = illegal = threw = 0
    asked: Counter = Counter()
    offered: Counter = Counter()
    inert_by: Counter = Counter()
    n = 0
    for n in range(cap):
        if agent.is_done(frames, obs):
            break
        seen["steps"], seen["threw"] = None, False
        before = filled["n"]
        simple_ids, action6 = availability(obs)
        act = agent.choose_action(frames, obs)
        was_fill = filled["n"] > before
        board = np.asarray(obs.frame[0] if isinstance(obs.frame, list) else obs.frame)
        cause = ""
        if was_fill:
            if seen["threw"]:
                threw += 1
                cause = "THREW"
            elif not seen["steps"]:
                noplan += 1
                cause = "NOPLAN"
            else:
                illegal += 1
                cause = "ILLEGAL"
                for s in seen["steps"]:
                    asked[str(s[0])] += 1
                offered[",".join(map(str, sorted(simple_ids))) + ("+6" if action6 else "")] += 1
            _log(f"  {title} fill#{filled['n']} at {n} {cause} "
                 f"tool={agent._current} steps={seen['steps']} avail={simple_ids} a6={action6}")
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        after = np.asarray(obs.frame[0] if isinstance(obs.frame, list) else obs.frame)
        if was_fill and board.shape == after.shape and not board_changed(board, after):
            inert_by[cause] += 1
        now = int(getattr(obs, "levels_completed", done) or 0)
        if now > done:
            _log(f"  {title} level {now} at action {n + 1}")
            done = now
        if n % 200 == 0:
            _log(f"  {title} step={n} level={done} fills={filled['n']}")
    print(json.dumps({
        "game": title, "actions": n + 1, "levels": done, "fills": filled["n"],
        "noplan": noplan, "illegal": illegal, "threw": threw,
        "asked": dict(asked), "offered": dict(offered), "inert_by": dict(inert_by),
    }))


if __name__ == "__main__":
    main()
