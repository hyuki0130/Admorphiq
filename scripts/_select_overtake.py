"""SELECTIVITY probe 2 — how often is a BETTER tool available at a frame where nobody asks?

Owned by the selectivity agent (2026-08-30). Follow-up to R101SELECT, which found that the loop
samples every tool exactly ONCE per handover, and that three tools reached a high bid between
decisions and were never consulted (`socketmerge` 0.95 and `hop` 0.88 on lf52, `telescope` 0.95 on
s5i5). That is the third outcome the single-frame view cannot see: not "nothing bid" and not "bid
and lost the tie", but BID AND WAS NEVER ASKED.

⛔ This measures a MECHANISM and licenses no change (rule 7o). What it can establish is whether a
re-decide trigger on "a non-incumbent strictly outbids the incumbent" would have anything to fire
on, and WHICH tools it would hand the board to — which is the difference between a routing lever
worth gating and a phantom.

Recorded every `_OVERTAKE_EVERY` steps: the incumbent's own bid, the best non-incumbent bid and its
owner, and whether a decision was taken at that step. Aggregated per game per level.

Instrumentation is subclass-only; `loop.py` is shared and untouched. Neutrality is checked the same
way R101SELECT checked it: the run must reproduce the gate baseline to the action.

    bash scripts/pfan.sh selov scripts/_select_overtake.py 9 "" 6
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402
from score_efficiency import _make_agent, run_game  # noqa: E402

from admorphiq.harness.loop import UnifiedAgent  # noqa: E402

GAMES = ["lf52", "bp35", "s5i5", "dc22", "lp85", "m0r0", "vc33", "g50t", "ls20"]
STUCK = {"lf52", "bp35", "s5i5", "dc22"}

_OVERTAKE_EVERY = 10   # steps between full-board bid sweeps


class OvertakeAgent(UnifiedAgent):
    def _ov_init(self) -> None:
        self._ov_samples = 0
        self._ov_tick = 0
        self._ov_last = -10**9
        # (level, incumbent, challenger) -> [n_samples, max_margin, cur_bid_at_max, chal_bid_at_max]
        self._ov_over: dict[tuple, list] = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
        self._ov_by_level: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # [samples, overtaken]
        self._ov_decisions = 0

    def _redecide(self, frames, obs, sig) -> None:
        self._ov_decisions += 1
        super()._redecide(frames, obs, sig)

    def choose_action(self, frames, latest_frame):
        act = super().choose_action(frames, latest_frame)
        # ⛔ NOT `self._steps` — it is LEVEL-LOCAL and resets on every level-up, so after the first
        # clear the gate `_steps - _ov_last >= N` stays false until the counter climbs back past the
        # old value. Measured in the first run of this probe: m0r0 got SIX samples over 188 actions,
        # concentrated on level 0. A monotonic tick of our own is the only correct clock here.
        self._ov_tick += 1
        if self._ov_tick - self._ov_last >= _OVERTAKE_EVERY and self._current not in (None, "code"):
            self._ov_last = self._ov_tick
            cur = self._current
            bids = {}
            for name, t in self.tools.items():
                try:
                    bids[name] = float(t.detect(self._recent_frames, self._last_obs))
                except Exception:  # noqa: BLE001
                    bids[name] = 0.0
            self._ov_samples += 1
            lvl = self._attempt_level
            self._ov_by_level[lvl][0] += 1
            mine = bids.get(cur, 0.0)
            others = [(v, n) for n, v in bids.items() if n != cur]
            if others:
                bv, bn = max(others)
                if bv > mine:
                    self._ov_by_level[lvl][1] += 1
                    slot = self._ov_over[(lvl, cur, bn)]
                    slot[0] += 1
                    if bv - mine > slot[1]:
                        slot[1], slot[2], slot[3] = round(bv - mine, 4), round(mine, 4), round(bv, 4)
        return act


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if seed > len(GAMES):
        return
    want = GAMES[seed - 1]

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
        a.__class__ = OvertakeAgent
        a._ov_init()
        holder["agent"] = a
        return a

    t0 = time.time()
    res = run_game(arcade, env_info.game_id, env_info.baseline_actions,
                   agent_name="unified", max_actions=4000, adapter_factory=factory)
    a = holder.get("agent")
    over = []
    by_level = {}
    if a is not None:
        for (lvl, cur, chal), (n, marg, cb, xb) in sorted(
                a._ov_over.items(), key=lambda kv: -kv[1][0]):
            over.append({"level": lvl, "incumbent": cur, "challenger": chal,
                         "samples": n, "max_margin": marg,
                         "inc_bid": cb, "chal_bid": xb})
        by_level = {str(k): v for k, v in sorted(a._ov_by_level.items())}

    print(json.dumps({
        "game": want,
        "stuck": want in STUCK,
        "game_score": res.get("game_score"),
        "levels": res.get("levels_completed"),
        "total_actions": res.get("total_actions"),
        "elapsed_s": round(time.time() - t0, 1),
        "samples": getattr(a, "_ov_samples", 0),
        "ticks": getattr(a, "_ov_tick", 0),
        "decisions": getattr(a, "_ov_decisions", 0),
        "by_level_samples_overtaken": by_level,
        "overtakes": over[:20],
        "error": res.get("error"),
    }), flush=True)


if __name__ == "__main__":
    main()
