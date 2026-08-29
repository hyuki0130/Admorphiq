"""s5i5 level 7 — the budget is NOT the lever. Is the OFF-GRID SUPERSET the lever? (rule 7h)

⛔ MEASURED FIRST, and it refutes the obvious repair (`/tmp/pfan_s5i5bopen.jsonl`, this session):

    open 120,000 w2   plan@204 len 26 in 9.3s -> refused@221 -> len 20 -> refused@223
                      -> plan NOT FOUND, 91.0s + 91.2s -> dead.        0.5833
    open 400,000 w2   same shape, the two dead searches cost 390s each. NOT FOUND.  0.5833
    open 400,000 w4   same shape, 386.5s + 416.3s.                    NOT FOUND.  0.5833

Three arms, two weights, 3.3x the budget, 4x the wall clock, and the search from the state the
tool has walked into finds nothing. The offline `_s5i5_ingrid` measurement that found a 28-click
win at 324k pops ran from the level's STAGED config with a CLEAN model — not from here.

WHAT IS DIFFERENT ABOUT HERE. `_settle` banks, per refusal, EVERY off-grid cell the refused
configuration would have occupied, because at least one of them must be solid and a frame-only
tool cannot tell which. Its own comment calls this "a superset". By the time the tool dies it
holds **45 cells and 2 illegal configurations**, and `legal()` rejects any configuration touching
ANY banked cell. The win is only reachable OFF the grid (measured: no fully in-grid win exists,
254k-334k pops, exhausted at every weight and cap). So a superset banked from two refusals can
close the only corridor to the goal — and no budget reopens it.

Arms — every one keeps the CONFIGURATION ban (`model.illegal`), which is sound; they differ only
in what is inferred about the off-grid CELLS:

    1  union    bank every off-grid cell of the refused configuration   (HEAD)
    2  off      bank nothing; learn by configuration alone
    3  certain  bank only when the refused configuration has EXACTLY ONE off-grid cell,
                which is the only case where "at least one is solid" names a cell
    4  inter    bank the intersection of every refusal's off-grid set
    5  off      + open 400,000
    6  certain  + open 400,000

Instrumented at the FIRING (rule 7g): the raw off-grid cell count of every refusal, what the
policy kept, every plan call with its wall clock, and the action at which `_dead` is set. WALL
CLOCK is reported per arm.

Run:  bash scripts/pfan.sh s5i5boff scripts/_s5i5b_off.py 6 "" 6
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
    1: dict(mode="union", open=120_000),
    2: dict(mode="off", open=120_000),
    3: dict(mode="certain", open=120_000),
    4: dict(mode="inter", open=120_000),
    5: dict(mode="off", open=400_000),
    6: dict(mode="certain", open=400_000),
}


def install(mode: str, open_: int):
    import admorphiq.tools.swivel as sv

    sv._MAX_OPEN = open_
    log: list = []
    state = {"act": 0, "lvl": 0}
    hist: list[set] = []

    orig_plan = sv.plan
    orig_settle = sv.SwivelArmTool._settle
    orig_propose = sv.SwivelArmTool.propose

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
        if not refused or model is None:
            return orig_settle(self, g, refused)
        # ⛔ Empty the set FIRST so what comes back is exactly THIS refusal's off-grid cells,
        # not the running union — the policy has to see the raw evidence to act on it.
        saved = set(model.offblocked)
        model.offblocked.clear()
        ok = orig_settle(self, g, refused)
        raw = set(model.offblocked)
        model.offblocked.clear()
        if raw:
            hist.append(raw)
        if mode == "union":
            model.offblocked |= saved | raw
        elif mode == "off":
            pass
        elif mode == "certain":
            model.offblocked |= saved | (raw if len(raw) == 1 else set())
        elif mode == "inter":
            model.offblocked |= set.intersection(*hist) if hist else set()
        log.append({"ev": "refused", "a": state["act"], "lvl": state["lvl"],
                    "raw": len(raw), "kept": len(model.offblocked)})
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
    log, state = install(arm["mode"], arm["open"])

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
        "plan_s_total": round(sum(e["s"] for e in plans), 1),
        "n_plan_calls": len(plans), "n_plan_found": sum(1 for e in plans if e["found"]),
        "n_refused": sum(1 for e in log if e["ev"] == "refused"),
        "per_level_actions": per_level, "who_acted": who,
        "events": [e for e in log if e["ev"] != "refused"][-14:],
        "refusals": [e for e in log if e["ev"] == "refused"][-14:],
    }))


if __name__ == "__main__":
    main()
