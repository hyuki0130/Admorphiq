"""ls20 level 7 HANDOVER census: who holds the board for the first ticks of the level, and why.

Purpose. Level 7 costs 231 actions against a human 186. A peer measured that the first ten belong
to `keymaze` and that eight of them push into a wall. This probe establishes, from the engine's own
state beside the harness's own bookkeeping, WHICH mechanism spends those actions: keymaze's own
plan, or the harness's `_probe` fallback fired because keymaze proposed NOTHING (`_EMPTY_TOLERANCE`
is 8, and `_probe` returns `simple_ids[0]` every time, so eight empty proposals are eight identical
actions).

It changes NO decision — the agent is the shipped `UnifiedAgent` with recorders bolted on, and the
loop mirrors `score_efficiency.run_game` (empty frames list, honour `restart_on_game_over`, break on
WIN), so the banked per-level [17,101,63,66,67,100,231] and 0.912085 must come back or nothing below
describes the shipped agent.

Per tick on level 7 it records: the harness's current tool, its `_empty_runs` counter, what the
active tool's `propose` actually returned, the action finally taken, the avatar cell before and
after (equal = the move was REFUSED by the engine), the fuel counter, lives, and the live `detect`
of keymaze and fogscout on that exact frame.

Expected feedback. `per_level` must read [17,101,63,66,67,100,231]. Then: if the level-7 opening
actions carry `src="probe"`, the ten actions are a HARNESS defect (a tool bidding nothing while the
harness spends the budget anyway) and not a keymaze one; if they carry `src="plan"`, keymaze is
actively choosing them and the defect is the tool's. The fogscout detect column says when the swap
signal becomes true, which bounds how early any fix could act.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    tools = default_tools()
    rec: dict[str, Any] = {"last_plan": None, "last_tool": None}

    for t in tools:
        orig = t.propose

        def wrapped(frames, obs, _o=orig, _n=t.name):
            out = _o(frames, obs)
            rec["last_plan"] = [list(s) if not isinstance(s, tuple) else [s[0], list(s[1]) if s[1] else None]
                                for s in out]
            rec["last_tool"] = _n
            return out
        t.propose = wrapped  # type: ignore[method-assign]

    agent = UnifiedAgent(tools, _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    by_name = {t.name: t for t in tools}

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.observation_space
    g = env._game
    human = list(getattr(info, "baseline_actions", []) or [])

    prev_levels = int(obs.levels_completed)
    total = 0
    this = 0
    per: list[int] = []
    rows: list[dict[str, Any]] = []
    restart = bool(getattr(agent, "restart_on_game_over", False))

    while total < 4000:
        if agent.is_done([], obs):
            break
        rec["last_plan"] = None
        rec["last_tool"] = None
        cur_before = agent._current
        empty_before = getattr(agent, "_empty_runs", 0)
        qlen = len(agent._queue)
        watch = prev_levels >= 5
        if watch:
            dets = {}
            for nm in ("keymaze", "fogscout"):
                if nm in by_name:
                    try:
                        dets[nm] = round(float(by_name[nm].detect(agent._recent_frames, obs)), 3)
                    except Exception as e:  # noqa: BLE001
                        dets[nm] = f"ERR:{e}"
            px, py = g.gudziatsk.x, g.gudziatsk.y
            fuel0 = g._step_counter_ui.current_steps
        act = agent.choose_action([], obs)
        if not isinstance(act, GameAction):
            break
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        if obs is None:
            break
        total += 1
        this += 1
        if watch:
            rows.append({
                "lv": prev_levels, "n": this,
                "cur0": cur_before, "cur1": agent._current,
                "empty0": empty_before, "empty1": getattr(agent, "_empty_runs", 0),
                "q": qlen,
                "src": "queue" if qlen else ("plan" if rec["last_plan"] else "probe/none"),
                "proposer": rec["last_tool"], "plan": rec["last_plan"],
                "act": str(getattr(act, "name", act)),
                "p0": [px, py], "p1": [g.gudziatsk.x, g.gudziatsk.y],
                "moved": [px, py] != [g.gudziatsk.x, g.gudziatsk.y],
                "fuel": [fuel0, g._step_counter_ui.current_steps,
                         g._step_counter_ui.osgviligwp],
                "lives": g.aqygnziho,
                "det": dets,
                "failed": sorted(agent._failed),
            })
        cur = int(obs.levels_completed)
        if cur > prev_levels:
            for _ in range(cur - prev_levels):
                per.append(this)
                this = 0
            prev_levels = cur
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            this += 1
            if obs is None:
                break

    weight = sum(range(1, len(human) + 1))
    got = 0.0
    out_levels = []
    for i, h in enumerate(human, start=1):
        mine = per[i - 1] if i - 1 < len(per) else 0
        s = min(h / mine, 1.0) ** 2 if mine else 0.0
        got += i * s
        out_levels.append([i, mine, h, round(s, 4)])
    print(json.dumps({
        "seed": sys.argv[1] if len(sys.argv) > 1 else None,
        "levels": prev_levels, "total": total,
        "per_level": out_levels, "game_score": round(got / weight, 6),
        "rows": rows,
    }, default=str), flush=True)


if __name__ == "__main__":
    main()
