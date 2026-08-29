"""s5i5 level 7 — the planner can never move the bar that is IN THE WAY. Arms + the firing record.

THREE FANS ALREADY RAN THIS SESSION AND ALL EIGHTEEN ARMS SCORED 0.5833, which is what says the
lever is none of the obvious ones:

  `_s5i5b_open`    open 120k/400k x weight 2/4          -> 0.5833. Plans are FOUND in seconds
                   (len 28 in 19.6s); only the post-refusal searches fail, at 386s and 416s.
  `_s5i5b_off`     off-grid ban union / none / one / intersection -> 0.5833. Removing the ban
                   makes it THRASH: 72 plans, 76 refusals, 70 banned configurations, dead at 392.
  `_s5i5b_margin`  bar may leave the frame by 0 / 3 / 6 / 9 cells, and unbounded -> 0.5833. It
                   cuts wall clock hard (219s -> 45s at margin 3) and clears nothing.

⭐ WHAT THE OLD ENGINE-SIDE MEASUREMENT SAYS, re-read (`/tmp/pfan_s5i5reach.jsonl`, jobs 5-28):
an A* over the REAL ENGINE with collisions ON is **exhausted, found=False, best gap 4-6**, at
every weight 2/4/8/20 and every length cap 8/12/16, up to 259,479 states. With collisions
DISABLED the same search wins in 20 clicks. And every one of those runs carries `ban: [10, 8]` —
it had BANNED two controls: `c10`, the slider of the other arm, and `c8`, the loose bar that
`_s5i5_solve`'s own docstring says "sits across one approach".

⭐ THE HYPOTHESIS. `plan()` decomposes the board when no control moves more than one rider, and
builds each subproblem's move set as `[n for n, t in enumerate(reach) if bar in t]`. A control
whose bar carries NO rider — an obstacle-mover, exactly what `c8` is — touches no rider, so `t`
is EMPTY and its moves are in NO subproblem. The planner therefore cannot move the thing that is
in the way, and the joint search that could is only reached when the decomposition FAILS, which
it does not: it returns a plan the engine then refuses.

This also explains a result the brief called mysterious: recovering `turn c8` in `_assemble`
changed the run BYTE-IDENTICALLY. Of course it did — the move was added to `moves` and then never
allowed into any subproblem.

⛔ THE CORRECTION IS SOUND BY THE DECOMPOSITION'S OWN ARGUMENT: a control that touches no rider
cannot disturb another rider's solution, which is the exact premise that licenses solving the
riders in sequence. So it belongs in EVERY subproblem, not in none.

    1  control (HEAD)                    2  allowed += the no-rider controls
    3  joint search only (no decompose)   4  joint only, open 400,000
    5  arm 2 + open 400,000               6  arm 2 + margin 3 (bounded off-grid, for wall clock)

Instrumented at the FIRING (rule 7g), because the whole hypothesis is about a branch that never
runs: which branch of `plan()` was taken, the per-move `touches` sizes, how many moves each
subproblem was allowed, every plan call with its wall clock, every refusal, and the action at
which `_dead` is set. `levels_completed` is printed as a NUMBER and tested `>` (rule 7f).

Run:  bash scripts/pfan.sh s5i5bfree scripts/_s5i5b_free.py 6 "" 6
"""
from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, "src")

TITLE = "s5i5"
HUMAN = [20, 89, 106, 54, 162, 38, 86, 83]
WIN_LEVELS = 8

ARMS = {
    1: dict(free=False, joint=False, open=120_000, margin=-1),
    2: dict(free=True, joint=False, open=120_000, margin=-1),
    3: dict(free=False, joint=True, open=120_000, margin=-1),
    4: dict(free=False, joint=True, open=400_000, margin=-1),
    5: dict(free=True, joint=False, open=400_000, margin=-1),
    6: dict(free=True, joint=False, open=120_000, margin=3),
}


def install(free: bool, joint_only: bool, open_: int, margin: int):
    from itertools import permutations

    import admorphiq.tools.swivel as sv

    sv._MAX_OPEN = open_
    log: list = []
    state = {"act": 0, "lvl": 0}

    orig_legal = sv.legal
    orig_settle = sv.SwivelArmTool._settle
    orig_propose = sv.SwivelArmTool.propose

    if margin >= 0:
        lo, hi = -margin, 63 + margin

        def legal(model, cfg):
            for box, _e in cfg.bars:
                if box[0] < lo or box[1] < lo or box[2] > hi or box[3] > hi:
                    return False
            for box in cfg.freight:
                if box[0] < lo or box[1] < lo or box[2] > hi or box[3] > hi:
                    return False
            return orig_legal(model, cfg)

        sv.legal = legal

    def plan(model, start, moves, banned=None):
        """A copy of `sv.plan` with the two arms spliced in and the branch taken recorded."""
        t0 = time.time()
        ev = {"ev": "plan", "a": state["act"], "lvl": state["lvl"], "branch": None}
        got = None
        if sv.solved(model, start):
            ev.update(branch="already", found=True, len=0)
            log.append(ev)
            return []
        if not model.pairing:
            ev.update(branch="no_pairing", found=False, len=0)
            log.append(ev)
            return None
        reach = [sv.touches(model, colour) for _k, colour, _s in moves]
        ev["touches"] = [len(t) for t in reach]
        ev["n_free"] = sum(1 for t in reach if not t)
        if not joint_only and len(model.pairing) > 1 and all(len(t) <= 1 for t in reach):
            ev["branch"] = "decomposed"
            for order in permutations(model.pairing):
                cfg = start
                out: list[int] = []
                for place_i, bar in order:
                    allowed = [n for n, t in enumerate(reach)
                               if bar in t or (free and not t)]
                    ev["allowed"] = len(allowed)
                    seek = sv._seek(model, cfg, moves, allowed, place_i, bar, banned)
                    if seek is None:
                        break
                    out += seek[0]
                    cfg = seek[1]
                else:
                    if sv.solved(model, cfg):
                        got = out
                        break
        if got is None and not joint_only:
            allowed_all = list(range(len(moves)))
            for place_i, bar in model.pairing:
                seek = sv._seek(model, start, moves, allowed_all, place_i, bar, banned)
                if seek is not None and sv.solved(model, seek[1]):
                    ev["branch"] = "single"
                    got = seek[0]
                    break
        if got is None:
            ev["branch"] = "joint"
            got = sv._joint(model, start, moves, banned)
        ev.update(s=round(time.time() - t0, 1), found=got is not None,
                  len=len(got) if got else 0,
                  off=len(model.offblocked), ill=len(model.illegal))
        log.append(ev)
        return got

    def settle(self, g, refused):
        if refused:
            log.append({"ev": "refused", "a": state["act"], "lvl": state["lvl"]})
        return orig_settle(self, g, refused)

    def propose(self, frames, obs):
        state["lvl"] = sv.levels_completed(obs) if sv.has_frame(obs) else state["lvl"]
        was = self._dead
        out = orig_propose(self, frames, obs)
        if self._dead and not was:
            log.append({"ev": "dead", "a": state["act"], "lvl": state["lvl"]})
        return out

    sv.plan = plan
    sv.SwivelArmTool._settle = settle
    sv.SwivelArmTool.propose = propose
    return log, state


def main() -> None:
    job = int(sys.argv[1])
    arm = dict(ARMS[((job - 1) % len(ARMS)) + 1])
    log, state = install(arm["free"], arm["joint"], arm["open"], arm["margin"])

    from arc_agi import Arcade, OperationMode

    # ⛔ `arcengine.GameAction` is the class the harness returns; `admorphiq.types`' GameAction
    # is a DIFFERENT class and an isinstance against it is False for every action.
    from arcengine import GameAction, GameState

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
    restart = bool(getattr(agent, "restart_on_game_over", False))

    who: dict[str, int] = {}
    per_level: list[list[int]] = []
    lvl = 0
    this_level = 0
    total = 0
    t0 = time.time()
    won = False
    # ⛔ MIRROR score_efficiency.py: EMPTY frames list, honour restart_on_game_over, break on WIN.
    while total < 4000:
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        if not isinstance(act, GameAction):
            break
        who[str(agent._current)] = who.get(str(agent._current), 0) + 1
        obs = (env.step(act, data=act.action_data.model_dump()) if act.is_complex()
               else env.step(act))
        if obs is None:
            break
        total += 1
        this_level += 1
        state["act"] = total
        now = int(obs.levels_completed)
        if now > lvl:                        # rule 7f — `>`, never `!=`, and print the number
            for _ in range(now - lvl):
                per_level.append([lvl + 1, this_level])
                this_level = 0
            lvl = now
        if obs.state == GameState.WIN:
            won = True
            break
        if obs.state == GameState.GAME_OVER:
            if not restart:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            this_level += 1
            if obs is None:
                break

    scores = []
    for n, acts in per_level:
        if acts <= 0 or n > len(HUMAN):
            continue
        scores.append(min(HUMAN[n - 1] / acts, 1.0) ** 2)
    weights = list(range(1, WIN_LEVELS + 1))
    game_score = sum(w * s for w, s in zip(weights, scores)) / sum(weights)

    plans = [e for e in log if e["ev"] == "plan"]
    print(json.dumps({
        "job": job, **arm,
        "levels_completed": lvl, "won": won,
        "game_score": round(game_score, 4),
        "actions": total, "wall_s": round(time.time() - t0, 1),
        "plan_s_total": round(sum(e.get("s", 0) for e in plans), 1),
        "n_plan_calls": len(plans), "n_plan_found": sum(1 for e in plans if e.get("found")),
        "n_refused": sum(1 for e in log if e["ev"] == "refused"),
        "per_level_actions": per_level, "who_acted": who,
        "events": [e for e in log if e["ev"] != "refused"][-14:],
    }))


if __name__ == "__main__":
    main()
