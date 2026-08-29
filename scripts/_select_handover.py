"""SELECTIVITY probe — what every tool bids AT THE HANDOVER FRAME, and what the winner then did.

Owned by the selectivity agent (2026-08-30). Namespaced `_select_*` so it cannot collide with a
peer's scratch probe.

WHY. `scripts/bid_matrix.py` reads FIRST frames only, so it cannot say why a board FALLS THROUGH to
the general searcher part-way into a game. The question is not graph's hit rate; it is why the board
was ever handed to graph. That is decided at `UnifiedAgent._redecide`, the harness's own re-decide
point, and nowhere else.

WHAT IS RECORDED, per handover, per game:
  * every registered tool's `detect()` at THAT EXACT FRAME (not frame 0, not the winner alone) —
    "nothing bid" and "something bid and lost" need completely different work;
  * WHY the incumbent was retired (stall / empty-propose / death-clock / level-start);
  * whether the WINNER SURVIVED — actions until the next handover, and how many propose() calls
    after winning actually returned a legal plan;
  * every tool's BEST bid so far this game, alongside its bid now (a tool whose confidence DECAYS
    is invisible in a single-frame snapshot).

INSTRUMENTATION IS SUBCLASS-ONLY. `loop.py` is shared by ~40 concurrent agents and is not touched.
The agent object is built by score_efficiency's own `_make_agent("unified")` and then re-classed, so
the configuration is identical by construction rather than by copying.

VALIDITY CHECK BUILT IN (rule: prove the instrument is attached, and that it did not perturb): the
run reports `game_score`, which must equal the gate baseline for that game. A score that moved means
the extra detect() calls changed behaviour and the table is void.

Usage (via pfan; seed selects the game):
    bash scripts/pfan.sh selho scripts/_select_handover.py 9 "" 6
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402
from score_efficiency import _make_agent, run_game  # noqa: E402

from admorphiq.harness.loop import UnifiedAgent  # noqa: E402

# 4 stuck + 5 controls. Controls clear and a specialist is meant to hold them throughout, so a
# handover on a control is as informative as one on a stuck board.
GAMES = ["lf52", "bp35", "s5i5", "dc22", "lp85", "m0r0", "vc33", "g50t", "ls20"]
STUCK = {"lf52", "bp35", "s5i5", "dc22"}

_BEST_EVERY = 50   # steps between best-bid samples (decay resolution vs perturbation)


class HandoverAgent(UnifiedAgent):
    """UnifiedAgent + a recorder at the re-decide point. Adds no branch that changes behaviour."""

    def _ho_init(self) -> None:
        self._ho_records: list[dict] = []
        self._ho_reason = "game_start"
        self._ho_best: dict[str, float] = {}
        self._ho_open: dict | None = None
        self._ho_proposed = 0
        self._ho_last_best_step = -10**9

    # -- bid sampling ---------------------------------------------------------

    def _ho_bids(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for name, t in self.tools.items():
            try:
                out[name] = round(float(t.detect(self._recent_frames, self._last_obs)), 4)
            except Exception:  # noqa: BLE001
                out[name] = -1.0          # detect threw — distinct from a real 0.00 bid
        for n, v in out.items():
            if v > self._ho_best.get(n, 0.0):
                self._ho_best[n] = v
        return out

    # -- retirement-reason latches (each is the ONLY site that nulls _current) --

    def _fill_from_current(self, frames, obs) -> None:
        before = self._current
        super()._fill_from_current(frames, obs)
        if before is not None and self._current is None:
            self._ho_reason = "empty_propose"
        elif before is not None and self._current == before and getattr(self, "_empty_runs", 0) == 0:
            self._ho_proposed += 1

    def _ledger_observe(self, levels, state) -> None:
        before = self._current
        super()._ledger_observe(levels, state)
        if before is not None and self._current is None:
            self._ho_reason = "death_clock"

    # -- the handover itself --------------------------------------------------

    def _redecide(self, frames, obs, sig) -> None:
        prev = self._current
        reason = "stall_swap" if prev is not None else self._ho_reason
        bids = self._ho_bids()
        failed_now = sorted(self._failed)
        banned_now = sorted(self._banned_now())
        if self._ho_open is not None:
            self._ho_open["survived_actions"] = self._steps - self._ho_open["step"]
            self._ho_open["proposed_after_win"] = self._ho_proposed
        super()._redecide(frames, obs, sig)
        winner = self._current
        live = {n: v for n, v in bids.items() if n not in failed_now and n not in banned_now}
        ranked = sorted(live.items(), key=lambda kv: -kv[1])
        top = ranked[0][1] if ranked else 0.0
        rec = {
            "step": self._steps,
            "level": self._last_levels,
            "attempt_level": self._attempt_level,
            "retired": prev,
            "reason": reason,
            "winner": winner,
            "primary_owns": bool(self._primary_owns),
            "top_bid": top,
            # every tool that bid ANYTHING at this frame, with its best-so-far alongside
            "bids": {n: [v, self._ho_best.get(n, 0.0)] for n, v in sorted(bids.items()) if v != 0.0},
            "n_zero": sum(1 for v in bids.values() if v == 0.0),
            # a specialist that bid and LOST: live, non-winner, non-graph, bid > 0
            "losers": sorted(
                (n for n, v in live.items() if v > 0.0 and n != winner), key=lambda n: -live[n]
            )[:6],
            "tied_at_top": sorted(n for n, v in live.items() if v == top and top > 0.0),
            "failed_before": failed_now,
            "banned_before": banned_now,
            "survived_actions": None,
            "proposed_after_win": None,
        }
        self._ho_records.append(rec)
        self._ho_open = rec
        self._ho_proposed = 0
        self._ho_reason = "unknown"

    def choose_action(self, frames, latest_frame):
        act = super().choose_action(frames, latest_frame)
        if self._steps - self._ho_last_best_step >= _BEST_EVERY:
            self._ho_last_best_step = self._steps
            self._ho_bids()          # best-so-far sampling between handovers
        return act

    def _ho_close(self) -> None:
        if self._ho_open is not None and self._ho_open["survived_actions"] is None:
            self._ho_open["survived_actions"] = self._steps - self._ho_open["step"]
            self._ho_open["proposed_after_win"] = self._ho_proposed


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if seed > len(GAMES):
        return
    want = GAMES[seed - 1]
    budget = 4000

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if want in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"game": want, "error": "no env"}), flush=True)
        return
    env_info = envs[0]

    holder: dict = {}

    def factory():
        a = _make_agent("unified")
        a.__class__ = HandoverAgent
        a._ho_init()
        holder["agent"] = a
        return a

    t0 = time.time()
    res = run_game(arcade, env_info.game_id, env_info.baseline_actions,
                   agent_name="unified", max_actions=budget, adapter_factory=factory)
    agent = holder.get("agent")
    if agent is not None:
        agent._ho_close()
        records = agent._ho_records
        best = {n: v for n, v in sorted(agent._ho_best.items()) if v > 0.0}
    else:
        records, best = [], {}

    print(json.dumps({
        "game": want,
        "stuck": want in STUCK,
        "game_score": res.get("game_score"),
        "levels": res.get("levels_completed"),
        "win_levels": res.get("win_levels"),
        "total_actions": res.get("total_actions"),
        "elapsed_s": round(time.time() - t0, 1),
        "n_handovers": len(records),
        "best_bid_any_frame": best,
        "handovers": records,
        "error": res.get("error"),
    }), flush=True)


if __name__ == "__main__":
    main()
