"""s5i5 level 7 — the combination nobody ran: an ON-GRID model AND a search that may use c10.

⛔ WHY THE TWO SINGLE-FACTOR RESULTS DO NOT CLOSE THIS. The record has both halves measured alone
and both came back 0.5833, and each is confounded by the other:

  * `_s5i5b_maze` let the planner use every control (`_joint` over all moves, BFS heuristic, up to
    1.5M opens). Plans of 50, 28 and 20 clicks were FOUND and every one was REFUSED, with
    `offblocked` climbing 27 -> 33 -> 39 as it learned hidden cells one refusal at a time. A search
    that may use the right control still cannot execute a plan its geometry gets wrong.
  * the hidden-cell oracle handed the model all 291 off-grid cells and the score did not move —
    but that run's planner still could not propose `c10`, and an engine A* is EXHAUSTED without
    `c10` (reproduced here today: ban=[10], 289,920 states, best gap 4). So a run that cannot use
    `c10` cannot win however good its geometry is, and that oracle could never have shown anything.

⭐ AND THE THIRD FACT MAKES THE FIX SMALL. The level's frame (`0006`, 70x51 at (-3,-3)) is a maze
whose walls all sit INSIDE the visible grid — cols 39-41 down to row 29, cols 15-17 over rows
30-44, a band at rows 27-29 with gaps at cols 6-8 and 30-32, and a floor at rows 45-47. Its
off-grid part is furniture the tool can never see. So bounding the model to the grid does not
merely make the search cheaper: it removes every configuration whose legality the tool has no way
to know, which is exactly the class its plans keep dying on. `_s5i5b_margin` already measured
margin 0 over the whole game as score- and action-identical (0.5833, [13,30,47,39,32,31]).

⛔ AND THE DECOMPOSITION THEN GETS OUT OF THE WAY BY ITSELF. `plan()` only falls through to
`_joint` — the one branch that may use every control — when the per-rider decomposition FAILS.
Today it succeeds, with a plan the engine refuses, so `_joint` is reached only from a poisoned
state. Under an on-grid model the single-rider subproblem has no solution (no win exists without
`c10`), the decomposition fails honestly, and the existing fall-through does the rest.

ARMS (`bash scripts/pfan.sh s5i5cjoint scripts/_s5i5c_joint.py 8 "" 8`):

    1  HEAD                                             <- control: must reproduce 0.5833 exactly
    2  margin 0 only
    3  margin 0 + BFS-field `_joint`
    4  margin 0 + BFS-field `_joint`, 400k opens
    5  margin 3 + BFS-field `_joint`, 400k opens        <- isolates the margin from the heuristic
    6  margin 0 + BFS-field `_joint`, 400k, decomposition SKIPPED
    7  margin 0 + BFS-field `_joint`, 1.5M, decomposition SKIPPED
    8  margin 0 + BFS-field `_joint`, 400k, weight 2

Every arm plays the WHOLE game, prints `levels_completed` as a NUMBER and tests it with `>`
(rule 7f), mirrors `score_efficiency.run_game` (empty frames list, honour restart, break on WIN),
and reports WALL CLOCK because a search that costs ten minutes is not a repair.
"""
from __future__ import annotations

import heapq
import json
import sys
import time
from collections import deque

sys.path.insert(0, "src")

TITLE = "s5i5"
HUMAN = [20, 89, 106, 54, 162, 38, 86, 83]

ARMS = {
    1: dict(margin=None, maze=False, open=None, weight=None, force=False),
    2: dict(margin=0, maze=False, open=None, weight=None, force=False),
    3: dict(margin=0, maze=True, open=None, weight=None, force=False),
    4: dict(margin=0, maze=True, open=400_000, weight=None, force=False),
    5: dict(margin=3, maze=True, open=400_000, weight=None, force=False),
    6: dict(margin=0, maze=True, open=400_000, weight=None, force=True),
    7: dict(margin=0, maze=True, open=1_500_000, weight=None, force=True),
    8: dict(margin=0, maze=True, open=400_000, weight=2, force=False),
}


def _field(model, goal):
    """BFS to `goal` over cells the model's own learned static furniture does not occupy.

    ⛔ Manhattan is the wrong guide on this board and it is not a matter of degree: a wall runs
    from row 0 to row 29 between the arm and its destination, so the tip must go DOWN, LEFT
    through a three-cell gap and back UP, and every step of that route increases the Manhattan
    estimate. Nothing new is read off the frame — `model.static` is already held.
    """
    blocked = model.static or set()
    dist = [[-1] * 64 for _ in range(64)]
    gy, gx = goal
    if not (0 <= gy < 64 and 0 <= gx < 64):
        return None
    dist[gy][gx] = 0
    q = deque([(gy, gx)])
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < 64 and 0 <= nx < 64 and dist[ny][nx] < 0 and (ny, nx) not in blocked:
                dist[ny][nx] = dist[y][x] + 1
                q.append((ny, nx))
    return dist


def install(arm):
    import admorphiq.tools.swivel as sv

    if arm["margin"] is not None:
        sv._MARGIN = arm["margin"]
    if arm["open"]:
        sv._MAX_OPEN = arm["open"]
    weight = arm["weight"] or sv._WEIGHT
    log: list = []
    state = {"act": 0, "lvl": 0}

    orig_joint = sv._joint
    orig_plan = sv.plan
    orig_settle = sv.SwivelArmTool._settle
    orig_propose = sv.SwivelArmTool.propose

    def joint(model, start, moves, banned=None):
        if not arm["maze"]:
            return orig_joint(model, start, moves, banned)
        fields = [_field(model, model.places[p]) for p, _b in model.pairing]

        def dist(cfg):
            total = 0
            for i, (place_i, bar) in enumerate(model.pairing):
                y, x = sv.rider_at(cfg, bar)
                gy, gx = model.places[place_i]
                fld = fields[i]
                d = fld[y][x] if (fld and 0 <= y < 64 and 0 <= x < 64) else -1
                total += d if d >= 0 else abs(gy - y) + abs(gx - x)
            return total

        seen = {start.key(): 0}
        heap = [(dist(start), 0, 0, start, [])]
        tick = opened = 0
        while heap:
            _f, _d, _t, cfg, path = heapq.heappop(heap)
            opened += 1
            if opened > sv._MAX_OPEN or len(path) >= sv._MAX_PLAN:
                continue
            for n, (kind, colour, step) in enumerate(moves):
                if banned and (cfg.key(), n) in banned:
                    continue
                nxt = (sv.grow(model, cfg, colour, step) if kind == "grow"
                       else sv.swivel(model, cfg, colour))
                if nxt is None:
                    continue
                k = nxt.key()
                cost = len(path) + 1
                if seen.get(k, 1 << 30) <= cost or not sv.legal(model, nxt):
                    continue
                if sv.solved(model, nxt):
                    return [*path, n]
                seen[k] = cost
                tick += 1
                heapq.heappush(heap, (cost + weight * dist(nxt), cost, tick, nxt, [*path, n]))
        return None

    def plan(model, start, moves, banned=None):
        t0 = time.time()
        if arm["force"]:
            got = [] if sv.solved(model, start) else (
                joint(model, start, moves, banned) if model.pairing else None)
        else:
            got = orig_plan(model, start, moves, banned)
        log.append({"ev": "plan", "a": state["act"], "lvl": state["lvl"],
                    "s": round(time.time() - t0, 1), "found": got is not None,
                    "len": len(got) if got else 0,
                    "off": len(model.offblocked), "ill": len(model.illegal)})
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

    sv._joint = joint
    sv.plan = plan
    sv.SwivelArmTool._settle = settle
    sv.SwivelArmTool.propose = propose
    return log, state


def main() -> None:
    job = int(sys.argv[1])
    arm = dict(ARMS[job])
    log, state = install(arm)

    from arc_agi import Arcade, OperationMode
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
        scores.append(min(HUMAN[n - 1] / acts, 1.0) ** 2 if acts else 0.0)
    weights = list(range(1, len(HUMAN) + 1))
    got = sum(w * s for w, s in zip(weights[:len(scores)], scores))
    print(json.dumps({"job": job, **arm, "levels_completed": lvl, "won": won,
                      "game_score": round(got / sum(weights), 4),
                      "actions": total, "wall_s": round(time.time() - t0, 1),
                      "per_level_actions": per_level, "who_acted": who,
                      "events": log[-24:]}))


if __name__ == "__main__":
    main()
