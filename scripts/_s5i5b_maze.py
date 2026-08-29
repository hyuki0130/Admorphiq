"""s5i5 level 7 — the engine's OWN winning sequence names the two things the planner cannot do.

⭐ THE WITNESS, recovered from `/tmp/pfan_s5i5final.jsonl` (not re-derived — it was already on the
box). An A* over the REAL ENGINE with collisions ON, a BFS-through-free-space heuristic and
NOTHING banned clears level 7 in **45 clicks**, and four configurations agree (length caps 16, 18,
20, 24). Its control histogram:

    grow c14 x12 · grow c11 x8 · grow c9 x7 · grow c12 x6 · turn c9 x3
    turn c11 x2  · turn c8 x2  · shrink c10 x2 · grow c10 x2 · shrink c9 x1
    first click:  shrink c10        opened: 2,985,510

⛔ AND THE 41 RUNS THAT FOUND NOTHING ARE THE OTHER HALF OF THE MEASUREMENT: every search with
`ban=[10]` or `ban=[10,8]` is EXHAUSTED, found=False, best gap 4-6, at every weight (2/4/8/20) and
every cap (8..24), up to 292,932 states. So the level is not merely hard without `c10` — it is
UNWINNABLE without it. `c10` is the slider of the arm whose rider is **already sitting on its
target**, and `c8` turns the loose bar that stands across the approach.

⛔ WHAT THAT SAYS ABOUT `swivel`, and it is structural rather than a constant:

  * `plan()` decomposes the board when no control moves more than one rider, solves the riders in
    sequence, and gives each subproblem `allowed = [n for n, t in enumerate(reach) if bar in t]`.
    `c10` touches the OTHER rider, so it is in NO subproblem. **The planner cannot move a rider
    that is already home out of the way** — and this board's answer opens by doing exactly that.
    (My earlier guess that the missing control was a no-rider one is REFUTED: the run prints
    `touches = [1]*13`, `n_free = 0`.)
  * `_joint` may use every control, but it is reached only when the decomposition FAILS, and the
    decomposition succeeds — with a plan the engine then refuses. When `_joint` finally runs it is
    from a poisoned state, and 120k and 400k both come back empty (measured, 386s and 416s).
  * `_joint`'s heuristic is Manhattan over `_distance`. `_s5i5_reach`'s own note: "Manhattan is a
    bad guide here: a vertical wall runs the full height of the board between the arm and its
    target". All four engine wins use the maze field; none of the Manhattan runs won.

THIS FAN TESTS THE TWO IMPLIED CHANGES, separately and together, so the credit is attributable:

    1  control (HEAD)
    2  all controls, Manhattan          open 400,000  w4    <- isolates "let it move c10"
    3  all controls, MAZE field         open 400,000  w4    <- isolates the heuristic
    4  all controls, MAZE field         open 1,500,000 w4
    5  all controls, MAZE + margin 3    open 1,500,000 w4   <- bounded off-grid, for wall clock
    6  all controls, MAZE + margin 6    open 1,500,000 w4

The maze field is a BFS from the destination over cells the model's own learned static furniture
does not occupy — the model already holds `static`, so this reads nothing new off the frame.

Every arm plays the WHOLE game, `levels_completed` is printed as a NUMBER and tested `>` (rule
7f), and WALL CLOCK is reported per arm because a search that costs ten minutes is not a repair.

Run:  bash scripts/pfan.sh s5i5bmaze scripts/_s5i5b_maze.py 6 "" 6
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
WIN_LEVELS = 8

ARMS = {
    1: dict(all_ctrl=False, maze=False, open=120_000, weight=2, margin=-1),
    2: dict(all_ctrl=True, maze=False, open=400_000, weight=4, margin=-1),
    3: dict(all_ctrl=True, maze=True, open=400_000, weight=4, margin=-1),
    4: dict(all_ctrl=True, maze=True, open=1_500_000, weight=4, margin=-1),
    5: dict(all_ctrl=True, maze=True, open=1_500_000, weight=4, margin=3),
    6: dict(all_ctrl=True, maze=True, open=1_500_000, weight=4, margin=6),
}


def _field(model, goal):
    """BFS distance to `goal` over cells the model's known static furniture does not occupy."""
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


def install(all_ctrl: bool, maze: bool, open_: int, weight: int, margin: int):
    import admorphiq.tools.swivel as sv

    sv._MAX_OPEN = open_
    sv._WEIGHT = weight
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

    def joint(model, start, moves, banned=None):
        """`_joint`, but the distance may be read off a BFS field instead of Manhattan."""
        fields = None
        if maze:
            fields = [_field(model, model.places[p]) for p, _b in model.pairing]

        def dist(cfg):
            total = 0
            for i, (place_i, bar) in enumerate(model.pairing):
                y, x = sv.rider_at(cfg, bar)
                gy, gx = model.places[place_i]
                fld = fields[i] if fields else None
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
        if all_ctrl:
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

    sv.plan = plan
    sv.SwivelArmTool._settle = settle
    sv.SwivelArmTool.propose = propose
    return log, state


def main() -> None:
    job = int(sys.argv[1])
    arm = dict(ARMS[((job - 1) % len(ARMS)) + 1])
    log, state = install(arm["all_ctrl"], arm["maze"], arm["open"], arm["weight"], arm["margin"])

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
    }))


if __name__ == "__main__":
    main()
