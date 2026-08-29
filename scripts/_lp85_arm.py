"""lp85 arm bench — vary ONE cyclepress behaviour at a time and price it per level.

Mirrors ``scripts/score_efficiency.py:run_game`` (empty frames list, restart_on_game_over,
BREAK on WIN) and reports the per-level action counts, the RHAE game score computed the same
way the scorer does, and a PROBE/PLAN/NUDGE census per level.

Purpose: level 4 is the only loss on this game (19 actions against a human 16) and the census
says it is 1 nudge + 10 evidence presses + 8 solution presses. Each arm attacks one of those.
Expected feedback: an arm that takes level 4 to 16 or fewer WITHOUT adding an action to any
other level is a candidate; anything that costs an action on levels 1/2/3/5/6/7/8 is a loss,
because all seven are at the metric's cap with zero headroom.

Arms are selected by the fan's seed so every arm is measured concurrently.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402

ARMS = ["nudge0", "nudge0+invtwin", "nudge0+invtwin+joint", "nudge0+invtwin+streak4",
        "nudge0+invtwin+max7", "nudge0+joint", "nudge0+invtwin+joint+streak4",
        "nudge0+invtwin+streak3"]


class _Shim:
    """An observation whose visible frame is one chosen layer of the real one."""

    def __init__(self, obs, layer):
        self._obs = obs
        self.frame = layer

    def __getattr__(self, name):
        return getattr(self._obs, name)


def _solved(g, cp) -> bool | None:
    """True/False when this grid reads as a satisfied board, None when it reads as no board."""
    board = cp.read_board(g)
    if board is None:
        return None
    tiles, side, _pitch = board
    marks = cp.markers_on(g, tiles, side)
    if not marks:
        return None
    return all(tiles.get(slot) == colour for slot, colour in marks)


def main() -> None:
    arm = ARMS[(int(sys.argv[1]) - 1) % len(ARMS)]
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    from score_efficiency import _make_agent

    from admorphiq.tools import cyclepress as cp
    from admorphiq.tools.base import has_frame

    log: list[dict] = []
    layers: list[dict] = []
    state = {"tag": None, "level": 0}

    orig_probe = cp.CyclePressTool._next_probe
    orig_nudge = cp.CyclePressTool._nudge
    orig_propose = cp.CyclePressTool.propose

    if "max7" in arm:
        cp._MAX_PRESSES = 7
    enough = next((int(t[-1]) for t in arm.split("+") if t.startswith("streak")), 0)

    orig_twin = cp.CyclePressTool._twin

    def twin_wrap(self, control):
        out = orig_twin(self, control)
        if out is not None or "inv" not in arm:
            return out
        # A confirmed control's INVERSE is structure no single press can manufacture: these
        # controls come in opposed pairs, so the inverse of a permutation already fixed is a
        # candidate that was decided before this control was ever pressed.
        for other, perm in self._perm.items():
            if other == control or self._streak.get(other, 0) < cp._CONFIRM_STREAK:
                continue
            inv = {v: k for k, v in perm.items()}
            if all(cp._replays(inv, b, a) for b, a in self._pairs[control]):
                return inv
        return None

    cp.CyclePressTool._twin = twin_wrap

    orig_learn = cp.CyclePressTool._learn

    def learn_wrap(self, tiles):
        orig_learn(self, tiles)
        if "joint" not in arm:
            return
        # JOINT INVERSE RECOVERY. These controls come in opposed pairs, so a press of D is,
        # read backwards, a press of C. Merging D's REVERSED transitions into C's evidence
        # doubles what each press buys — and the pairing is a hypothesis, so it is accepted
        # only when exactly ONE partner yields a permutation that replays both sides.
        for c in sorted(self._pairs):
            if self._streak.get(c, 0) >= cp._CONFIRM_STREAK:
                continue
            found = []
            for d in sorted(self._pairs):
                if d == c:
                    continue
                merged = list(self._pairs[c]) + [(a, b) for (b, a) in self._pairs[d]]
                if len(merged) < 3:
                    continue
                perm = cp.recover_permutation(self._slots, merged, self._pitch)
                if perm is None:
                    continue
                inv = {v: k for k, v in perm.items()}
                if all(cp._replays(perm, b, a) for b, a in self._pairs[c]) and \
                        all(cp._replays(inv, b, a) for b, a in self._pairs[d]):
                    found.append((d, perm, inv))
            if len(found) == 1:
                d, perm, inv = found[0]
                self._perm[c] = perm
                self._streak[c] = cp._CONFIRM_STREAK
                self._perm[d] = inv
                self._streak[d] = cp._CONFIRM_STREAK

    cp.CyclePressTool._learn = learn_wrap

    def probe_wrap(self, controls, tiles, marks):
        if enough:
            # A permutation that has PREDICTED once and rests on this many presses is treated
            # as settled; the second prediction is what the extra press is buying.
            for c, pairs in self._pairs.items():
                if self._streak.get(c, 0) >= 1 and len(pairs) >= enough:
                    self._streak[c] = cp._CONFIRM_STREAK
        out = orig_probe(self, controls, tiles, marks)
        if out is not None:
            state["tag"] = "PROBE"
        # readyfresh: the FRESH-control branch never asked whether a plan already exists; the
        # confirmation branch does. A press that can only shorten an existing plan by less than
        # itself is not worth taking.
        if "readyfresh" in arm and out is not None and out not in self._pairs:
            if self._ready(tiles, marks):
                state["tag"] = None
                return None
        return out

    def nudge_wrap(self, controls):
        state["tag"] = "NUDGE"
        return orig_nudge(self, controls)

    def propose_wrap(self, frames, obs):
        state["tag"] = None
        # Diagnostic, every arm: what the layers say on a board nothing has been pressed on yet.
        if has_frame(obs) and not self._pairs and not self._plan:
            arr = np.asarray(getattr(obs, "frame", None))
            if arr.ndim >= 3 and len(arr) > 1:
                g0 = arr[0].astype(np.int64)
                gl = arr[-1].astype(np.int64)
                s0, sl = _solved(g0, cp), _solved(gl, cp)
                layers.append({"lvl": state["level"], "n": int(len(arr)),
                               "same": bool(np.array_equal(g0, gl)),
                               "solved0": s0, "solvedlast": sl})
                if "nudge0" in arm and s0 is True and sl is False:
                    obs = _Shim(obs, arr[-1])
        steps = orig_propose(self, frames, obs)
        tag = state["tag"] or ("PLAN" if steps else "EMPTY")
        log.append({"lvl": state["level"], "tag": tag, "step": steps[0] if steps else None,
                    "perms": len(self._perm), "pressed": len(self._pairs),
                    "replans": self._replans, "plan_left": len(self._plan),
                    "ctl": {str(c): [len(self._pairs[c]), self._streak.get(c, 0),
                                     hash(tuple(sorted(self._perm[c].items()))) % 100000
                                     if c in self._perm else None]
                            for c in sorted(self._pairs)}})
        return steps

    cp.CyclePressTool._next_probe = probe_wrap
    cp.CyclePressTool._nudge = nudge_wrap
    cp.CyclePressTool.propose = propose_wrap

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(e for e in arcade.get_environments()
                if "lp85" in f"{e.game_id} {e.title or ''}".lower())
    baseline = info.baseline_actions
    agent = _make_agent("unified", game_id=info.game_id)

    env = arcade.make(info.game_id)
    obs = env.observation_space
    win_levels = int(obs.win_levels)
    prev = int(obs.levels_completed)
    state["level"] = prev
    total = 0
    this_level = 0
    per_level: list[int] = []
    restart = bool(getattr(agent, "restart_on_game_over", False))

    while total < budget:
        if agent.is_done([], obs):
            break
        action = agent.choose_action([], obs)
        if not isinstance(action, GameAction):
            break
        obs = (env.step(action, data=action.action_data.model_dump())
               if action.is_complex() else env.step(action))
        if obs is None:
            break
        total += 1
        this_level += 1
        cur = int(obs.levels_completed)
        if cur > prev:                                   # ⛔ ">" — a collapse is not a clear
            for _ in range(cur - prev):
                per_level.append(this_level)
                this_level = 0
            prev = cur
            state["level"] = cur
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            this_level += 1
            if obs is None:
                break

    # RHAE, computed the way scripts/score_efficiency.py does it.
    num = 0.0
    den = float(sum(range(1, win_levels + 1)))
    per = []
    for i, acts in enumerate(per_level):
        human = baseline[i] if baseline and i < len(baseline) else None
        s = min(human / acts, 1.0) ** 2 if human and acts else 0.0
        per.append({"lvl": i + 1, "agent": acts, "human": human, "score": round(s, 4)})
        num += (i + 1) * s

    census: dict[str, dict[str, int]] = {}
    for row in log:
        census.setdefault(str(row["lvl"]), {}).setdefault(row["tag"], 0)
        census[str(row["lvl"])][row["tag"]] += 1

    detail = {
        "arm": arm,
        "levels_completed": int(prev),
        "total_actions": total,
        "per_level": per_level,
        "game_score": round(num / den, 4) if den else 0.0,
        "per": per,
        "census": census,
        "layers": layers,
        "l4": [r for r in log if r["lvl"] == 3],
    }
    # ⛔ ONE SHORT LINE to stdout. Concurrent >4KB appends from a fan interleave and every arm
    # but one reads as "produced nothing" — the fail-toward-nothing shape. Detail goes to a
    # per-arm file the fan cannot mix.
    Path(f"/tmp/lp85arm_{arm.replace('+', '_')}.json").write_text(json.dumps(detail))
    print(json.dumps({"arm": arm, "levels": int(prev), "total": total,
                      "per_level": per_level,
                      "score": round(num / den, 4) if den else 0.0,
                      "census": {k: v for k, v in sorted(census.items())}}))


if __name__ == "__main__":
    main()
