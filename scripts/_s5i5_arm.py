"""s5i5 — the candidate repairs for level 7, measured END TO END on the whole game.

WHAT THE DIAGNOSIS ACTUALLY SAYS (`scripts/_s5i5_run7.py`, `scripts/_s5i5_die.py`,
`scripts/_s5i5_gap.py`, all on the harness itself):

  * `swivel` reads level 7 EXACTLY — six bars with the source's own colours, the chain
    c11 -> c14 -> c9 -> c12, both riders, both destinations, the wall as 417 static cells;
  * `_agrees` never once disagrees, so the model tracks the board perfectly;
  * it plans 25 clicks, executes SIXTEEN cleanly, is refused, replans to 20, executes two, is
    refused again — and then `plan()` finds NOTHING and the tool sets `_dead` at action 224;
  * `linkage` inherits 463 actions and clears nothing;
  * the engine's own step allowance (readable on frame row 63) drains 64 -> 5 and REFILLS at
    action 401 and again at 601. The level is lost and restarted TWICE, and `levels_completed`
    never moves, so the restart is invisible to anything watching the level number (rule 7f).

MEASURED SEPARATELY, on `swivel`'s own model taken from the live board: a joint search from the
post-probe configuration DOES find a 24-28 click win, but needs **324k to 1.8M pops**. The shipped
`_MAX_OPEN` is **120,000**, so the search is cut off just short of the answer. That is the one
lever with direct evidence behind it.

⚠️ Two other candidates were tested and are NOT the cause, which is why they are not varied here:
recovering the missing `turn c8` control changes nothing (the plan it produces is no better), and
`_settle` never returns False, so there is no model/frame disagreement to survive.

Arms (`job`):
  1 as shipped — the control
  2 escalate: when `plan()` comes back empty, retry the JOINT search once at 400k pops
  3 escalate to 1.5M pops
  4 escalate to 400k, and cap bar length at 21 units (a bar longer than the 64-cell board is
    never useful, so this prunes without excluding an answer)
  5 escalate to 400k with the search leaning harder on the distance estimate (weight 4)
  6 escalate to 400k, and a level RESTART re-arms the tool: `_dead` is cleared when the board
    returns to the configuration `_begin` first read, because the engine hands back a fresh
    solvable board and nothing downstream notices
  7 arms 4 and 6 together
  8 raise `_MAX_OPEN` to 400k globally (no escalation) — measures what the escalation buys

Reports levels, per-level actions against the game's own human baselines, the RHAE game score, and
WALL CLOCK, because a search that finds the answer in ten minutes is not a repair.

Run:  bash scripts/pfan.sh s5i5arm scripts/_s5i5_arm.py 8 "" 8
"""
from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, "src")

TITLE = "s5i5"
HUMAN = [20, 89, 106, 54, 162, 38, 86, 83]      # environment_files/s5i5/*/metadata.json
WIN_LEVELS = 8


def install(escalate: int, cap_units: int, weight: int, rearm: bool, globally: int) -> list:
    import admorphiq.tools.swivel as sv

    log: list = []
    if globally:
        sv._MAX_OPEN = globally

    if escalate:
        orig_plan = sv.plan

        def plan(model, start, moves, banned=None):
            got = orig_plan(model, start, moves, banned)
            if got is not None:
                return got
            # ⛔ Conceding here is what kills the tool. The board is not unsolvable; the search
            # was cut off. Pay for one deep attempt before giving the level away.
            keep_open, keep_w = sv._MAX_OPEN, sv._WEIGHT
            sv._MAX_OPEN, sv._WEIGHT = escalate, weight or keep_w
            t0 = time.time()
            try:
                deep = sv._joint(model, start, moves, banned) if model.pairing else None
            finally:
                sv._MAX_OPEN, sv._WEIGHT = keep_open, keep_w
            log.append({"ev": "escalated", "found": deep is not None,
                        "len": len(deep) if deep else 0, "s": round(time.time() - t0, 1)})
            return deep

        sv.plan = plan

    if cap_units:
        orig_legal = sv.legal
        lim = cap_units * sv._UNIT

        def legal(model, cfg):
            for box, edge in cfg.bars:
                if sv._length(box, edge) > lim:
                    return False
            return orig_legal(model, cfg)

        sv.legal = legal

    if rearm:
        orig_propose = sv.SwivelArmTool.propose

        def propose(self, frames, obs):
            if self._dead and self._first is not None:
                layers = sv._layers(obs)
                if layers is not None and len(layers) > 0:
                    seen, _m = sv.solid_cells(layers[-1], self._marker or 0,
                                              [w.box for w in self._widgets])
                    if seen == self._first:
                        # ⛔ The engine restarted the level. The level number did not move, so
                        # nothing else can see it; the board is the one this tool read at the
                        # start and it is solvable again.
                        keep = self._level
                        self.reset()
                        self._level = keep
                        log.append({"ev": "rearmed"})
            out = orig_propose(self, frames, obs)
            if self._first is None and self._model is not None and self._widgets:
                layers = sv._layers(obs)
                if layers:
                    seen, _m = sv.solid_cells(layers[-1], self._marker or 0,
                                              [w.box for w in self._widgets])
                    self._first = seen
            return out

        sv.SwivelArmTool.propose = propose
        orig_reset = sv.SwivelArmTool.reset

        def reset(self):
            first = getattr(self, "_first", None)
            orig_reset(self)
            self._first = first

        sv.SwivelArmTool.reset = reset
        sv.SwivelArmTool._first = None

    return log


ARMS = {
    1: dict(escalate=0, cap_units=0, weight=0, rearm=False, globally=0),
    2: dict(escalate=400_000, cap_units=0, weight=0, rearm=False, globally=0),
    3: dict(escalate=1_500_000, cap_units=0, weight=0, rearm=False, globally=0),
    4: dict(escalate=400_000, cap_units=21, weight=0, rearm=False, globally=0),
    5: dict(escalate=400_000, cap_units=0, weight=4, rearm=False, globally=0),
    6: dict(escalate=400_000, cap_units=0, weight=0, rearm=True, globally=0),
    7: dict(escalate=400_000, cap_units=21, weight=0, rearm=True, globally=0),
    8: dict(escalate=0, cap_units=0, weight=0, rearm=False, globally=400_000),
}


def main() -> None:
    job = int(sys.argv[1])
    arm = ARMS[((job - 1) % len(ARMS)) + 1]
    log = install(**arm)

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(TITLE))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=8000, stall=80, ctx_budget=6000)
    frames = [obs]
    who: dict[str, int] = {}
    per_level: list[list[int]] = []
    lvl = 0
    last_up = 0
    t0 = time.time()
    step = 0
    for step in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        who[str(agent._current)] = who.get(str(agent._current), 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", lvl) or 0)
        if now > lvl:                       # ⛔ `>` — a fall back is not a clear (rule 7f)
            per_level.append([now, step + 1 - last_up])
            last_up = step + 1
            lvl = now
        elif now < lvl:
            per_level.append([now, -(step + 1 - last_up)])
            last_up = step + 1
            lvl = now
    scores = []
    for n, acts in per_level:
        if acts <= 0 or n > len(HUMAN):
            continue
        scores.append(min(HUMAN[n - 1] / acts, 1.0) ** 2)
    weights = list(range(1, WIN_LEVELS + 1))
    game_score = sum(w * s for w, s in zip(weights, scores)) / sum(weights)
    print(json.dumps({
        "job": job, **{k: v for k, v in arm.items()},
        "levels": lvl, "game_score": round(game_score, 4),
        "actions": step + 1, "wall_s": round(time.time() - t0, 1),
        "per_level_actions": per_level, "who_acted": who,
        "events": log[:20], "n_events": len(log),
    }))


if __name__ == "__main__":
    main()
