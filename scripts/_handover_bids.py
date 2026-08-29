"""Which tools bid, and what did they bid, AT THE HANDOVER FRAME — not at frame 0.

⛔ THE QUESTION `bid_matrix.py` CANNOT ANSWER. It reads every tool's `detect` on each game's FIRST
frame, which is the right check for selectivity-at-entry and silent about the moment that actually
decides a stuck game: the RE-DECIDE, when the incumbent has been retired and the board goes to
whoever bids highest. Measured by the ls20 agent, no tool that is SOLVING a board is more than 7%
inert (0, 0, 1, 1, 2, 7) while `graph` is never below 41% (41, 49, 71) — cited, not re-derived. So
`graph` is what a stuck game LOOKS like: it is the fallback that inherits every board no specialist
claims, and the question is not its hit rate but why the board fell through to it.

THREE OUTCOMES, needing three different kinds of work — and the third is why a single-frame snapshot
is not enough:

  NOTHING BID      every specialist reports 0.00 here and has NEVER bid on this game -> the board
                   needs a TOOL, and no routing change will conjure one.
  SOMETHING BID    a specialist bids above zero at the handover and loses anyway -> a ROUTING
                   defect, costing us on a board we already believe we can solve.
  CONFIDENCE DECAYED  a specialist bid nonzero EARLIER in this game and bids 0.00 now. Invisible in
                   a snapshot, and it is neither of the above: the tool knows the mechanic and has
                   stopped recognising it, which is a detector problem inside a tool that exists.

⚠️ AND THE BID ALONE MAKES A DEAD TOOL LOOK LIKE A ROUTING WIN. On dc22 a specialist bids, wins, and
latches dead within a handful of actions; another lasts twelve. A table recording only the bid
cannot tell "won and worked" from "won and contributed nothing", so every tenure carries how many
`propose` calls it made and how many returned a move. A winner with `proposed 0` did not route
badly — it routed fine and then did nothing.

METHOD. Each tool's `detect` is wrapped to record its value, so the bid vector is read from the
calls the HARNESS makes rather than recomputed; recomputing would double the planning cost on
exactly the expensive tools and could disagree with what the harness saw. `_decide` is wrapped to
snapshot that vector at the instant it is used, with the winner, the retirement reason, and the
outgoing tenure's productivity.

⛔ THE LOOP MIRRORS `score_efficiency.py` EXACTLY (rule 7x): empty frames list into `is_done` and
`choose_action`, break on WIN, honour `restart_on_game_over` with `arcengine.GameAction.RESET` —
the enum member, not `admorphiq.types`' `.reset()`, which raises only on a death and so leaves a
game that never dies looking perfectly healthy. A hand-rolled loop measured four bp35 boards where
the scorer clears five, and a census counted 143 deaths on a game that scores 1.0000 by playing on
past the win.

The instrument proves itself: `handovers` counts the re-decides captured and `bid_calls` the detect
calls wrapped. A run reporting either as 0 measured nothing, whatever else it printed.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

MAX_ACTIONS = 4000
# The six boards below the cap on the R101WA30 baseline, worst first. `pfan.sh` feeds an index, so
# one fan covers every stuck game and the arm number IS the game.
STUCK = ["bp35", "lf52", "s5i5", "dc22", "ls20", "lp85"]


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "1"
    title = STUCK[(int(arg) - 1) % len(STUCK)] if arg.isdigit() else arg
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else MAX_ACTIONS
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()

    now_bid: dict[str, float] = {}
    best_bid: dict[str, float] = {}
    bid_calls = [0]
    proposed: Counter[str] = Counter()
    propose_calls: Counter[str] = Counter()

    def instrument(tool):
        nm = tool.name
        raw_detect, raw_propose = tool.detect, tool.propose

        def detect(frames, o):
            bid_calls[0] += 1
            try:
                v = float(raw_detect(frames, o))
            except Exception:                       # noqa: BLE001
                v = 0.0
            now_bid[nm] = v
            best_bid[nm] = max(best_bid.get(nm, 0.0), v)
            return v

        def propose(frames, o):
            propose_calls[nm] += 1
            out = raw_propose(frames, o)
            if out:
                proposed[nm] += 1
            return out

        tool.detect, tool.propose = detect, propose

    for t in tools:
        instrument(t)

    agent = UnifiedAgent(tools, _no_llm, giveup=8000, stall=80, ctx_budget=6000)
    handovers: list[dict] = []
    act = [0]
    tenure = {"name": None, "act": 0, "pc": 0, "ok": 0}
    raw_decide = UnifiedAgent._decide

    def decide(self, sig):
        prev = tenure["name"]
        out_calls = propose_calls.get(prev, 0) - tenure["pc"] if prev else 0
        out_ok = proposed.get(prev, 0) - tenure["ok"] if prev else 0
        now_bid.clear()
        mode, name = raw_decide(self, sig)
        specialists = {k: round(v, 3) for k, v in now_bid.items() if v > 0 and k != "graph"}
        decayed = sorted(k for k, v in best_bid.items()
                         if v > 0 and now_bid.get(k, 0.0) <= 0 and k != "graph")
        handovers.append({
            "act": act[0],
            "level": int(getattr(obs, "levels_completed", 0) or 0),
            "retired": prev,
            "its_propose_calls": out_calls,
            "it_proposed": out_ok,
            "lasted": act[0] - tenure["act"] if prev else 0,
            "winner": name,
            "mode": mode,
            "bids_now": {k: round(v, 3) for k, v in sorted(now_bid.items()) if v > 0},
            "specialists_bidding_now": specialists,
            "specialists_decayed_to_zero": decayed,
            "zero_now": sum(1 for v in now_bid.values() if v <= 0),
            "failed": sorted(self._failed),
            "why": (self._feedback or "")[:100],
        })
        tenure.update(name=name, act=act[0],
                      pc=propose_calls.get(name, 0), ok=proposed.get(name, 0))
        return mode, name

    UnifiedAgent._decide = decide
    restart = bool(getattr(agent, "restart_on_game_over", False))
    try:
        while act[0] < budget:
            if agent.is_done([], obs):
                break
            a = agent.choose_action([], obs)
            if not isinstance(a, GameAction):
                break
            obs = (env.step(a, data=a.action_data.model_dump()) if a.is_complex()
                   else env.step(a))
            if obs is None:
                break
            act[0] += 1
            if obs.state == GameState.WIN:
                break
            if obs.state == GameState.GAME_OVER:
                if not restart:
                    break
                obs = env.step(GameAction.RESET)
                act[0] += 1
                if obs is None:
                    break
    finally:
        UnifiedAgent._decide = raw_decide

    print(json.dumps({
        "game": title,
        "handovers": len(handovers),
        "bid_calls": bid_calls[0],
        "actions": act[0],
        "final_level": int(getattr(obs, "levels_completed", 0) or 0) if obs else -1,
        "best_bid_ever": {k: round(v, 3) for k, v in sorted(best_bid.items()) if v > 0},
        "tenures": {k: {"calls": propose_calls[k], "proposed": proposed[k]}
                    for k in sorted(set(propose_calls) | set(proposed))},
        "rows": handovers[:24],
    }), flush=True)


if __name__ == "__main__":
    main()
