"""ls20 through the REAL harness with the shipped tool set — per level, no subclass anywhere.

⛔ Every measurement in this round was taken through a probe SUBCLASS of `FogScoutTool`. A subclass
is not the shipped code, and the whole point of the change is that it lands in `_search`. This runs
`default_tools()` untouched and prints the per-level action counts and the RHAE score the runner
would compute, so the tool's own file is what is being measured.

Expected feedback: levels 1-6 unchanged at 17/101/63/66/67/100 (all at the 1.0 cap) and level 7 at
231 rather than 237. Any movement on levels 1-6 means the change reached a board it must not touch —
`detect` returns 0.00 on every unfogged frame, so there should be none.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# ⛔ Resolve `src` against THIS FILE, never against the cwd. A private snapshot is run with the
# cwd on the SHARED tree (that is where `environment_files` lives), and `sys.path.insert(0, "src")`
# would then select the shared tree's code — the exact shadowing `ptest.sh` was found doing in
# rule 7n, silently measuring the wrong bytes.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    human = list(getattr(info, "baseline_actions", []) or [])
    lvl = 0
    per: Counter[int] = Counter()
    n = 0
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        n += 1
        per[lvl] += 1
        now = int(getattr(obs, "levels_completed", 0) or 0)
        # ⛔ `> lvl`, never `!=` — a collapse and a clear are the same boolean (rule 7f).
        if now > lvl:
            lvl = now
    weight = sum(range(1, len(human) + 1))
    got = 0.0
    rows = []
    for i, h in enumerate(human, start=1):
        mine = per[i - 1]
        s = min(h / mine, 1.0) ** 2 if mine else 0.0
        got += i * s
        rows.append({"level": i, "agent": mine, "human": h, "score": round(s, 6)})
    print(json.dumps({"levels_completed": lvl, "total": n, "per_level": rows,
                      "game_score": round(got / weight, 6)}, indent=1), flush=True)


if __name__ == "__main__":
    main()
