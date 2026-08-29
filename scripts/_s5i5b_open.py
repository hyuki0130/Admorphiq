"""s5i5 level 7 — is the shipped search CUT OFF short of the answer? Every arm at once (rule 7h).

MEASURED by the previous agent (`/tmp/pfan_s5i5ingrid.jsonl`, 2026-08-29), offline over swivel's
OWN model of the seventh board, one job per configuration:

    in_grid=TRUE   weight 2 / 4 / 8, open 400k and 1.5M, length caps 0 / 12 / 21
                   -> EXHAUSTED every time, 254k-334k pops, best gap 6.  NO WIN EXISTS
                      that keeps every bar inside the visible 64x64 frame.
    in_grid=FALSE  weight 4, open 400k
                   -> FOUND, 28 clicks, **324,237 pops, 75.9 s**.

The shipped `_MAX_OPEN` is **120,000**. So the winning plan lies at roughly 2.7x the budget the
tool is allowed to spend looking for it, and every previous "no plan" was the cutoff talking.

⚠️ WHAT THE OFFLINE NUMBER DOES NOT SETTLE, and this probe does (rule 7o — a measurement of a
MECHANISM does not license a change of BEHAVIOUR):
  * the offline search ran at weight 4; the tool ships weight 2, which orders expansions
    differently and may need a different number of pops to reach the same goal;
  * it ran from the level's STAGED config with a clean model; in play the tool has probed its
    controls first and has learned off-grid cells from refusals;
  * a plan that exists in the model can still be REFUSED by the engine on an off-grid cell the
    frame cannot show — and the win is only reachable off-grid, so this is the live risk.

Arms (all six run together; each plays the WHOLE game so levels 1-6 are re-measured, never
inferred — they are all at the 1.0 cap and have zero headroom):

    1  control            open   120,000  weight 2   (HEAD)
    2  budget only        open   400,000  weight 2
    3  budget only        open 1,000,000  weight 2
    4  budget + weight    open   400,000  weight 4
    5  budget + weight    open 1,000,000  weight 4
    6  budget + weight    open 2,500,000  weight 4

Instrumented at the FIRING, not the outcome (rule 7g): every `plan()` call with its wall clock,
whether it returned, how long the plan was and at which level; every refusal; and the action at
which `_dead` is set. WALL CLOCK is reported per arm because a search that costs ten minutes is
not a repair.

Run:  bash scripts/pfan.sh s5i5bopen scripts/_s5i5b_open.py 6 "" 6
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
    1: dict(open=120_000, weight=2),
    2: dict(open=400_000, weight=2),
    3: dict(open=1_000_000, weight=2),
    4: dict(open=400_000, weight=4),
    5: dict(open=1_000_000, weight=4),
    6: dict(open=2_500_000, weight=4),
}


def install(open_: int, weight: int) -> list:
    """Set the two constants and tap plan / refusal / death. Returns the shared event log."""
    import admorphiq.tools.swivel as sv

    sv._MAX_OPEN = open_
    sv._WEIGHT = weight
    log: list = []
    state = {"act": 0, "lvl": 0}

    orig_plan = sv.plan
    orig_settle = sv.SwivelArmTool._settle
    orig_propose = sv.SwivelArmTool.propose

    def plan(model, start, moves, banned=None):
        t0 = time.time()
        got = orig_plan(model, start, moves, banned)
        log.append({"ev": "plan", "a": state["act"], "lvl": state["lvl"],
                    "s": round(time.time() - t0, 1),
                    "found": got is not None, "len": len(got) if got else 0,
                    "moves": len(moves), "banned": len(banned or ())})
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
    log, state = install(arm["open"], arm["weight"])

    # ⛔ `ENVIRONMENTS_DIR` is the variable the Arcade reads (CLAUDE.md; `ARC_ENVIRONMENTS_DIR`
    # is a convention of the probe scripts and is UNREAD by it). Point it at the archived
    # re-render to measure the same arms against different sprite tags and coordinates.
    arch = len(sys.argv) > 2 and sys.argv[2].strip() == "arch"
    if arch:
        import os
        os.environ["ENVIRONMENTS_DIR"] = os.path.expanduser(
            "~/admorphiq/environment_files_archive")

    from arc_agi import Arcade, OperationMode

    # ⛔ `arcengine.GameAction` is the class the harness returns; `admorphiq.types`'
    # GameAction is a DIFFERENT class, and an isinstance against it is False for every
    # action — the first version of this probe broke at step 0 in all six arms.
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
        "events": log[-24:],
    }))


if __name__ == "__main__":
    main()
