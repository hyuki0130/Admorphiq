"""ls20: sweep the harness's empty-proposal EVIDENCE threshold and read level 7 off the curve.

Purpose. The handover census (scripts/_ls20_handover.py) measured the defect exactly: on level 7
`keymaze` bids 0.00 and proposes nothing from the level's third action while `fogscout` bids 0.80
from its second, and the loop spends EIGHT probe actions (ACTION1 into a wall, every one refused)
before retiring it. Retiring on the evidence at 2 hands `fogscout` the board six actions earlier and
with 34 of 42 fuel units instead of 22 — and MEASURED, that LOSES the level (0 clears, 0.7500).

So the ten actions are not obviously waste: the tank `fogscout` inherits is an input to its own
plan. This probe reads the whole curve rather than two points — one arm per threshold 1..8, where 8
reproduces the shipped behaviour exactly (the evidence branch and the tolerance branch fire on the
same proposal) — so "231 at a 22-unit tank" can be told apart from "231 is a knife-edge".

The agent is the shipped `UnifiedAgent`; only the module-level threshold is patched, and the loop
mirrors `score_efficiency.run_game` (empty frames list, honour `restart_on_game_over`, break on WIN).

Expected feedback. Arm 8 MUST return [17,101,63,66,67,100,231] and 0.912085 or the harness is not
the shipped one and no other arm means anything. Any arm beating 231 on level 7 without touching
levels 1-6 is the win; every arm at or below it says the handover cost is load-bearing and the axis
closes with a measured negative.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    # argv[1] = arm index; argv[2] = which side of the shipped constant to sweep. "ev" walks the
    # EVIDENCE threshold 1..8 (handover EARLIER than shipped, 8 == shipped exactly); "tol" walks
    # `_EMPTY_TOLERANCE` to 8+arm, i.e. the handover LATER, so the surface is read on both sides of
    # the tank `fogscout` inherits rather than only below it.
    arm = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    side = sys.argv[2] if len(sys.argv) > 2 else "ev"
    ev = arm

    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.harness import loop as loop_mod
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    if side == "tol":
        loop_mod._EMPTY_TOLERANCE = 8 + arm
        ev = 8 + arm            # keep the evidence branch from firing first
    elif not hasattr(loop_mod, "_EMPTY_EVIDENCE"):
        # ⛔ RULE 7g. The evidence side needs the early-retirement patch IN the loop; the patch was
        # REVERTED when this sweep measured it a regression (see rounds/r101_ls20-fog-cost). Setting
        # a module attribute nothing reads would make every arm silently reproduce the shipped
        # number and read as a clean plateau. Refuse instead.
        raise SystemExit(
            "the 'ev' side needs loop._EMPTY_EVIDENCE, which is NOT in the shipped loop — "
            "re-apply the early-retirement patch before sweeping it; 'tol' works as shipped")
    loop_mod._EMPTY_EVIDENCE = ev

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)

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
    deaths = 0
    handover = None
    fuel_at_handover = None
    restart = bool(getattr(agent, "restart_on_game_over", False))
    t0 = time.time()
    reason = "action_cap"

    while total < 4000:
        if agent.is_done([], obs):
            reason = "agent.is_done"
            break
        act = agent.choose_action([], obs)
        if not isinstance(act, GameAction):
            break
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        if obs is None:
            break
        total += 1
        this += 1
        if prev_levels == 6 and handover is None and agent._current == "fogscout":
            handover = this
            fuel_at_handover = g._step_counter_ui.current_steps
        cur = int(obs.levels_completed)
        if cur > prev_levels:
            for _ in range(cur - prev_levels):
                per.append(this)
                this = 0
            prev_levels = cur
        if obs.state == GameState.WIN:
            reason = "WIN"
            break
        if obs.state == GameState.GAME_OVER:
            deaths += 1
            if not restart:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            this += 1
            if obs is None:
                break

    weight = sum(range(1, len(human) + 1))
    got = 0.0
    for i, h in enumerate(human, start=1):
        mine = per[i - 1] if i - 1 < len(per) else 0
        got += i * (min(h / mine, 1.0) ** 2 if mine else 0.0)
    print(json.dumps({
        "side": side, "arm": arm, "evidence": ev,
        "tolerance": loop_mod._EMPTY_TOLERANCE, "levels": prev_levels, "total": total,
        "per_level": per, "game_score": round(got / weight, 6),
        "deaths": deaths, "handover_tick": handover, "fuel_at_handover": fuel_at_handover,
        "elapsed_s": round(time.time() - t0, 1), "stop": reason,
    }), flush=True)


if __name__ == "__main__":
    main()
