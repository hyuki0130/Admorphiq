"""Why does `cover_targets` spend a level's whole allowance without winning it?

A level that is lost to an overrun and a level that is lost to a bad search read the same from
outside: the engine restores the board and the score keeps the actions. This runs the real
harness and records, for every action the tool proposes, WHAT IT THOUGHT it was doing — which
piece it believes it holds, whether a covering plan exists at all, and what the remaining offsets
were. The counts at the end are the reason the level costs what it costs.

    uv run python scripts/covertargets_probe.py <title> [cap] [level]
"""

from __future__ import annotations

import sys
from collections import Counter

sys.path.insert(0, "src")


def main() -> None:
    title = sys.argv[1] if len(sys.argv) > 1 else "re86"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    watch = int(sys.argv[3]) if len(sys.argv) > 3 else -1

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools import cover_targets as CT

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]

    state = {"level": 0, "attempt": 1, "step": 0}
    log: list[dict] = []
    original = CT.CoverTargetsTool.propose

    def traced(self, fr, ob):
        out = original(self, fr, ob)
        rec = {
            "level": state["level"], "attempt": state["attempt"], "step": state["step"],
            "wheel": self._wheel, "parts": len(self._parts),
            "sizes": [len(p["shape"]) for p in self._parts],
            "colours": [p["colour"] for p in self._parts],
            "anchors": [p["anchor"] for p in self._parts],
            "pairing": dict(self._pairing), "effect": dict(self._effect),
            "act": out[0][0] if out else None,
            "legs": len(self._legs[1]),
        }
        spec = self._spec
        if spec is not None:
            blobs = self._blobs_of(CT.frame_2d(ob), spec)
            pips = spec[1]
            rec["gap"] = [(r, c, v) for r, c, v in pips if not self._covered(r, c, v)]
            rec["npips"] = len(pips)
            plan = self._assign(pips, blobs)
            rec["plan"] = plan
            rec["source"] = "assign" if plan is not None else "scheme/none"
        log.append(rec)
        return out

    CT.CoverTargetsTool.propose = traced

    done = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        state["step"] += 1
        act = agent.choose_action(frames, obs)
        cur = str(agent._current)
        if log and log[-1]["step"] == state["step"]:
            log[-1]["tool"] = cur
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", done) or 0)
        if now != done:
            print(f"[level {state['level']} attempt {state['attempt']}] CLEARED at step {state['step']}")
            done = now
            state.update(level=now, attempt=1, step=0)
        elif str(getattr(obs, "state", "")).endswith("GAME_OVER"):
            print(f"[level {state['level']} attempt {state['attempt']}] BINNED at step {state['step']}")
            state["attempt"] += 1
            state["step"] = 0
    print(f"cleared={done} actions={step + 1}")

    if watch < 0:
        return
    rows = [r for r in log if r["level"] == watch]
    print(f"\n=== level {watch}: {len(rows)} cover_targets proposals ===")
    for att in sorted({r["attempt"] for r in rows}):
        mine = [r for r in rows if r["attempt"] == att]
        print(f"\n-- attempt {att}: {len(mine)} proposals --")
        print("   plan source:", Counter(r.get("source") for r in mine))
        print("   actions    :", Counter(r["act"] for r in mine))
        print("   wheel      :", Counter(r["wheel"] for r in mine))
        print("   gap size   :", Counter(len(r.get("gap", [])) for r in mine))
        print("   part sizes :", Counter(tuple(r["sizes"]) for r in mine).most_common(4))
        print("   anchors    :", Counter(tuple(r["anchors"]) for r in mine).most_common(4))
        print("   pairing    :", Counter(tuple(sorted(r["pairing"].items())) for r in mine))
        for r in mine[:6] + mine[len(mine) // 2: len(mine) // 2 + 4] + mine[-4:]:
            print(f"    s{r['step']:>4} act={r['act']} wheel={r['wheel']} legs={r['legs']} "
                  f"src={r.get('source')} plan={r.get('plan')} anchors={r['anchors']} "
                  f"cols={r['colours']} gap={r.get('gap')}")


if __name__ == "__main__":
    main()
