"""s5i5 level 7 — the search is not short of BUDGET, it is drowning in unobservable space.

MEASURED THIS SESSION, two fans, whole game per arm, control reproducing 0.5833 exactly:

  `_s5i5b_open`  open 120k/400k x weight 2/4 -> 0.5833 EVERY TIME. The firing record says the
                 arms fired: plans are FOUND in seconds (len 28 in 19.6s, len 21 in 1.9s); the
                 two that fail are exhausting an unreachable space, 386s and 416s, at 3.3x the
                 shipped cap. ⛔ A budget is a property of a problem AND A STARTING POINT — the
                 offline 324k-pop win started from the STAGED config with a CLEAN model.

  `_s5i5b_off`   off-grid banking union / none / exactly-one / intersection -> 0.5833 EVERY TIME.
                 Removing the ban does not free the tool, it makes it THRASH: 72 plans found and
                 76 refusals in one level, 70 configurations banned, dead at action 392.

⭐ WHAT THAT SECOND FAN ACTUALLY SHOWED, in a field nobody had printed: the refused configurations
carry **30 to 111 cells OUTSIDE the 64x64 frame**. The tool is not making a small excursion into
the margin — it is planning to swing a bar bodily off the board and bring it back, because the
model believes everything it cannot see is empty. The engine refuses all of it.

So the space the search is asked to cover is UNBOUNDED and almost entirely fantasy, and neither a
bigger budget nor a weaker ban can help: one enlarges the fantasy, the other stops pruning it.

⭐ THE HYPOTHESIS THIS FAN TESTS. A frame-only planner should not plan through space it cannot
observe at all — but it must not forbid the margin outright either, because `swivel`'s own
docstring records that the level BEFORE this one swings a bar off the top edge and is ALLOWED to,
and the offline in-grid search is EXHAUSTED with a best gap of 6, so no strictly-on-board win
exists. The answer is therefore a BOUND, not a ban: a bar may leave the frame by at most N cells.
`_UNIT` is 3 here, so the arms are whole units of the game's own geometry.

    1  unbounded (HEAD)      2  margin 0 cells      3  margin 3 (one unit)
    4  margin 6 (two)        5  margin 9 (three)    6  margin 3 + open 400,000

Every arm plays the WHOLE game, so levels 1-6 are re-measured and never inferred — they are all
at the 1.0 cap and level 6 is the one that needs the top-edge swing, so it is the arm's own
falsification test. Reported per arm: per-level actions, `levels_completed` as a NUMBER, every
plan call with its wall clock, every refusal with its off-grid cell count, and the total WALL
CLOCK — a search that costs ten minutes is not a repair.

Run:  bash scripts/pfan.sh s5i5bmargin scripts/_s5i5b_margin.py 6 "" 6
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
    1: dict(margin=-1, open=120_000),      # -1 = unbounded, i.e. HEAD
    2: dict(margin=0, open=120_000),
    3: dict(margin=3, open=120_000),
    4: dict(margin=6, open=120_000),
    5: dict(margin=9, open=120_000),
    6: dict(margin=3, open=400_000),
}


def install(margin: int, open_: int):
    import admorphiq.tools.swivel as sv

    sv._MAX_OPEN = open_
    log: list = []
    state = {"act": 0, "lvl": 0}

    orig_legal = sv.legal
    orig_plan = sv.plan
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
        t0 = time.time()
        got = orig_plan(model, start, moves, banned)
        log.append({"ev": "plan", "a": state["act"], "lvl": state["lvl"],
                    "s": round(time.time() - t0, 1),
                    "found": got is not None, "len": len(got) if got else 0,
                    "off": len(model.offblocked), "ill": len(model.illegal)})
        return got

    def settle(self, g, refused):
        model = self._model
        before = len(model.offblocked) if model is not None else 0
        ok = orig_settle(self, g, refused)
        if refused:
            after = len(model.offblocked) if model is not None else 0
            log.append({"ev": "refused", "a": state["act"], "lvl": state["lvl"],
                        "new_offgrid": after - before})
        return ok

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
    log, state = install(arm["margin"], arm["open"])

    # ⛔ `ENVIRONMENTS_DIR` is the variable the Arcade reads (`ARC_ENVIRONMENTS_DIR` is a probe
    # convention and is UNREAD by it). Point it at the archived re-render to measure transfer.
    arch = len(sys.argv) > 2 and sys.argv[2].strip() == "arch"
    if arch:
        import os
        os.environ["ENVIRONMENTS_DIR"] = os.path.expanduser(
            "~/admorphiq/environment_files_archive")

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
        "job": job, **arm, "arch": arch,
        "levels_completed": lvl, "won": won,
        "game_score": round(game_score, 4),
        "actions": total, "wall_s": round(time.time() - t0, 1),
        "plan_s_total": round(sum(e["s"] for e in plans), 1),
        "n_plan_calls": len(plans), "n_plan_found": sum(1 for e in plans if e["found"]),
        "n_refused": sum(1 for e in log if e["ev"] == "refused"),
        "per_level_actions": per_level, "who_acted": who,
        "events": log[-18:],
    }))


if __name__ == "__main__":
    main()
