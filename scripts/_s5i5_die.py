"""s5i5 level 7 — WHY swivel dies at action 224, and what happens if it does not.

Measured by `scripts/_s5i5_run7.py` job 1 (`/tmp/pfan_s5i5run7.jsonl`), and it moved the target:

    who_acted {"swivel": 230, "linkage": 463}   swivel_dead_at 224   best_level 6
    level_timeline [[13,1],[43,2],[90,3],[129,4],[161,5],[192,6]]  — and NOTHING after it

So the level is NOT lost to the engine's step counter inside a harness run: the state reads
NOT_FINISHED for all 695 actions and the level never falls back. `swivel` reads the board exactly,
finds a 25-click plan, and then goes DEAD 32 actions into the level; `linkage` inherits the rest and
never clears it. Everything about reachability and budget is downstream of that.

`_dead` is set in five places in `propose`/`_next`, and they mean different things:

    A `_begin` returned False                      — the board could not be read at all
    B `_settle` returned False                     — `nxt is None`, or the frame DISAGREED
    C `_assemble` returned False                   — no control was ever characterised
    D `_replan` found nothing and no control left to retry
    E the delegate path

This probe names which, prints the action it happened on and the click that caused it, and then
runs four variants that each remove one candidate cause. It also reads the engine's remaining step
allowance straight off the frame — `render_interface` paints row 63 with colour 3 up to
`64 * steps_left / budget` and colour 4 after it, so the budget is observable, not inferred.

  job 1  as shipped, full trace + death reason
  job 2  + `turn c8` recovered for the loose bar (the one move the engine's own A* needs twice)
  job 3  + a disagreement does not kill the tool: re-read the board and carry on
  job 4  both
  job 5  both, and the joint search forced with a larger open budget
  job 6  as shipped but swivel is the ONLY tool, so nothing inherits the board (isolates the
         463 actions `linkage` spends)

⛔ Levels are numbers and compared with `>` (rule 7f).

Run:  bash scripts/pfan.sh s5i5die scripts/_s5i5_die.py 6 "" 6
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")

TITLE = "s5i5"
STUCK = 6


def install(add_turn: bool, survive: bool, force_joint: bool, log: list) -> None:
    import admorphiq.tools.swivel as sv

    if force_joint:
        sv._MAX_OPEN = 1_500_000
        sv.plan = lambda model, start, moves, banned=None: (
            [] if sv.solved(model, start) else
            (sv._joint(model, start, moves, banned) if model.pairing else None))

    if add_turn:
        orig_assemble = sv.SwivelArmTool._assemble

        def assemble(self):
            ok = orig_assemble(self)
            if not ok:
                return ok
            model = self._model
            have = set(self._move_ctrl)
            for ctrl, (kind, _wd) in enumerate(self._controls):
                if kind != "turn" or ctrl in have:
                    continue
                colour = self._named[ctrl] if ctrl < len(self._named) else None
                if colour is None:
                    continue
                owns = [i for i, c in enumerate(model.colours) if c == colour]
                if len(owns) != 1:
                    continue
                bar = owns[0]
                if model.kids[bar] or any(bar in k for k in model.kids):
                    continue
                self._moves.append(("turn", colour, 0))
                self._move_ctrl.append(ctrl)
                log.append({"ev": "recovered_turn", "ctrl": ctrl, "colour": colour, "bar": bar})
            return ok

        sv.SwivelArmTool._assemble = assemble

    orig_settle = sv.SwivelArmTool._settle

    def settle(self, g, refused):
        pend = self._pending
        ok = orig_settle(self, g, refused)
        if not ok:
            log.append({"ev": "settle_false", "pending": list(pend) if pend else None,
                        "refused": bool(refused)})
            if survive:
                # ⛔ A disagreement means the MODEL is stale, not that the board is unplayable.
                # Rebuilding it from the frame costs nothing the level has not already spent.
                self.reset()
                self._level = None
                return True
        return ok

    sv.SwivelArmTool._settle = settle

    orig_begin = sv.SwivelArmTool._begin

    def begin(self, g):
        ok = orig_begin(self, g)
        if not ok:
            log.append({"ev": "begin_false"})
        return ok

    sv.SwivelArmTool._begin = begin

    orig_replan = sv.SwivelArmTool._replan

    def replan(self):
        ok = orig_replan(self)
        log.append({"ev": "replan", "ok": bool(ok), "len": len(self._plan)})
        return ok

    sv.SwivelArmTool._replan = replan


def budget_bar(obs) -> int:
    """Engine step allowance left, read off row 63 of the frame — colour 3 fills the fraction."""
    import numpy as np

    from admorphiq.tools.telescope import _layers
    layers = _layers(obs)
    if not layers:
        return -1
    row = np.asarray(layers[-1])[63]
    return int((row == 3).sum())


def main() -> None:
    job = int(sys.argv[1])
    add_turn = job in (2, 4, 5)
    survive = job in (3, 4, 5)
    force_joint = job == 5
    solo = job == 6
    log: list = []
    install(add_turn, survive, force_joint, log)

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
    tools = default_tools()
    if solo:
        tools = [t for t in tools if getattr(t, "name", "") == "swivel"]
    agent = UnifiedAgent(tools, _no_llm, giveup=900, stall=80, ctx_budget=6000)
    sw = agent.tools.get("swivel")
    frames = [obs]
    who: dict[str, int] = {}
    timeline: list[list[int]] = []
    lvl = best = 0
    dead_at = None
    steps_seen: list[list[int]] = []
    clicks: list[list] = []
    step = 0
    for step in range(900):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        cur = str(agent._current)
        who[cur] = who.get(cur, 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        if lvl >= STUCK and len(clicks) < 260:
            clicks.append([step + 1, cur, (data or {}).get("x"), (data or {}).get("y"),
                           len(sw._plan) if sw else -1, bool(sw._dead) if sw else None])
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", lvl) or 0)
        if now != lvl:
            timeline.append([step + 1, now])
            lvl = now
            best = max(best, now)
        if lvl >= STUCK and (step % 25 == 0 or len(steps_seen) < 4):
            steps_seen.append([step + 1, budget_bar(obs)])
        if sw is not None and sw._dead and dead_at is None:
            dead_at = step + 1
    print(json.dumps({
        "job": job, "add_turn": add_turn, "survive": survive, "force_joint": force_joint,
        "solo": solo,
        "CLEARED_LEVEL7": best > STUCK, "best_level": best, "level_at_end": lvl,
        "actions": step + 1, "level_timeline": timeline, "who_acted": who,
        "swivel_dead_at": dead_at,
        "events": log[:40], "n_events": len(log),
        "budget_bar_samples": steps_seen[:24],
        "clicks_on_level7": clicks[:80],
    }))


if __name__ == "__main__":
    main()
