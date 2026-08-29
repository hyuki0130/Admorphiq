"""s5i5 level 7 — WHY does `swivel` stop, and which single change would let it through?

Level 7 read off the game's own source (`environment_files/s5i5/18d95033/s5i5.py`, `levels[6]`,
StepCounter **200**, human baseline 86):

    arms (0001)  0006 wall 70x51 @(-3,-3) · 0007 c10 (carries the PARKED rider) · 0008 c8 (loose)
                 0059 c11 -> 0060 c14 -> 0061 c9 -> 0062 c12 -> the rider that must move
    riders(0064) (54,15) on the c11 chain     · (21,6) already ON its target at level start
    targets(0087)(24,15) UNCOVERED            · (21,6) covered
    controls     turn c14 c11 c9 c8   ·   slide c14 c11 c9 c12 c10

ALREADY MEASURED on the engine (`/tmp/pfan_s5i5final.jsonl`, four independent A* configs agreeing):

  * a winning click sequence EXISTS with collisions ON and is **45 clicks** — inside both the
    200-action allowance and the 86-action human baseline's ballpark;
  * it needs `shrink c10` (which lifts the ALREADY-PARKED rider off its target) and `turn c8`
    (which moves a bar carrying no rider at all), restoring both at the end;
  * banning c10 EXHAUSTS the space at gap 4 — so the two riders are NOT independent here;
  * a Manhattan heuristic did not find it in 1800 s; an obstacle-aware BFS heuristic did.

`swivel` scores this game 0.5833 (6/8, every cleared level at 1.0000) and burns the rest of the
budget on level 7 until the engine's own 200-step counter kills the attempt.

HYPOTHESES, ALL TESTED HERE TOGETHER (rule 7h):

  H1 the model is misread on this board (bars, colours, tree, riders, places) — job 1
  H2 the move alphabet is short: a control was never characterised                  — job 1
  H3 `plan()` takes the ONE-RIDER-AT-A-TIME branch, whose `allowed` set drops every
     control that moves no rider, so `turn c8` is not even in the search              — job 1
  H4 the joint fallback's `_MAX_OPEN` (120k pops) is too small                      — jobs 3+
  H5 `_distance` is Manhattan and a wall stands between the rider and its target     — jobs 3+
  H6 unbounded bar growth makes the space too wide                                   — jobs 3+
  H7 nothing is wrong with the search and the model simply cannot express the answer — refuted
     if any job returns a plan

Run:  bash scripts/pfan.sh s5i5swiv scripts/_s5i5_swiv.py 16 "" 8
"""
from __future__ import annotations

import json
import sys
import time
from collections import deque

sys.path.insert(0, "src")

TITLE = "s5i5"
STUCK = 6          # levels_completed while playing level 7


def reach_stuck(cap: int = 700):
    """Play the real harness until level 7 is on the board and swivel has probed its controls."""
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(TITLE))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    sw = agent.tools.get("swivel")
    frames = [obs]
    who: dict[str, int] = {}
    arrived = None
    for step in range(cap):
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl >= STUCK:
            if arrived is None:
                arrived = step
            # ⛔ WAIT FOR THE TOOL TO HAVE RE-READ THIS LEVEL. `swivel` resets inside `propose`,
            # so the moment the level number moves its model is still the PREVIOUS level's — and
            # dumping it there reports a board the game is no longer on. Measured: the first run
            # of this probe reported three bars, one rider and a one-click win, which is level 6.
            if (sw is not None and getattr(sw, "_level", None) == lvl
                    and getattr(sw, "_moves", None)):
                break
            if step - arrived > 120:
                break
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        who[str(agent._current)] = who.get(str(agent._current), 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    return agent, sw, obs, who, arrived


def describe(sw, obs, who, arrived) -> dict:
    from admorphiq.tools.swivel import rider_at, touches
    lvl = int(getattr(obs, "levels_completed", 0) or 0)
    out: dict = {"levels_completed": lvl, "reached_level7": lvl >= STUCK,
                 "swivel_level": getattr(sw, "_level", None),
                 "model_is_for_this_level": getattr(sw, "_level", None) == lvl,
                 "actions_to_level7": arrived, "who_acted": who,
                 "swivel_dead": bool(getattr(sw, "_dead", None)),
                 "delegating": sw._delegate is not None if sw is not None else None}
    m = getattr(sw, "_model", None)
    cfg = getattr(sw, "_cfg", None)
    if m is None or cfg is None:
        out["model"] = None
        return out
    out["bars"] = [{"i": i, "colour": m.colours[i], "box": list(cfg.bars[i][0]),
                    "edge": cfg.bars[i][1], "kids": m.kids[i], "parent": m.parent[i],
                    "load": m.load[i]} for i in range(len(cfg.bars))]
    out["riders"] = [{"bar": b, "at": list(rider_at(cfg, b))} for b in m.riders]
    out["places"] = [list(p) for p in m.places]
    out["pairing"] = [list(p) for p in (m.pairing or [])]
    out["moves"] = [list(mv) for mv in sw._moves]
    out["n_controls"] = len(sw._controls)
    out["controls_unread"] = [i for i in range(len(sw._controls))
                              if i not in sw._driven]
    out["named_colours"] = list(sw._named)
    reach = [sorted(touches(m, colour)) for _k, colour, _s in sw._moves]
    out["reach_per_move"] = reach
    out["moves_touching_no_rider"] = [i for i, t in enumerate(reach) if not t]
    out["decomposable"] = bool(len(m.pairing or ()) > 1 and all(len(t) <= 1 for t in reach))
    out["n_static_cells"] = len(m.static)
    out["plan_len_now"] = len(sw._plan)
    return out


# --- the variants -------------------------------------------------------------


def maze_field(model, places):
    """BFS distance to each destination over cells the immovable furniture does not fill.

    Generic: `model.static` is what `swivel` already computes as the leftover solid cells, so
    nothing game-specific enters here. It exists because Manhattan walks straight through the
    wall that stands between this board's rider and its target.
    """
    blocked = [[False] * 64 for _ in range(64)]
    for y, x in model.static:
        if 0 <= y < 64 and 0 <= x < 64:
            blocked[y][x] = True
    fields = []
    for gy, gx in places:
        dist = [[-1] * 64 for _ in range(64)]
        q: deque = deque()
        if 0 <= gy < 64 and 0 <= gx < 64:
            dist[gy][gx] = 0
            q.append((gy, gx))
        while q:
            y, x = q.popleft()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < 64 and 0 <= nx < 64 and dist[ny][nx] < 0 and not blocked[ny][nx]:
                    dist[ny][nx] = dist[y][x] + 1
                    q.append((ny, nx))
        fields.append(dist)
    return fields


def joint(model, start, moves, *, max_open: int, weight: int, hmaze: bool,
          cap_units: int, deadline: float, allowed=None) -> dict:
    """`swivel._joint` with the four levers exposed, so which one matters is measured."""
    import heapq

    from admorphiq.tools.swivel import _UNIT, _length, grow, legal, rider_at, solved, swivel

    fields = maze_field(model, model.places) if hmaze else None
    order = {p: k for k, (p, _b) in enumerate(model.pairing)}

    def dist(cfg) -> int:
        total = 0
        for place_i, bar in model.pairing:
            y, x = rider_at(cfg, bar)
            gy, gx = model.places[place_i]
            if fields is None:
                total += abs(gy - y) + abs(gx - x)
            else:
                d = fields[order[place_i]][y][x] if 0 <= y < 64 and 0 <= x < 64 else -1
                total += d if d >= 0 else (abs(gy - y) + abs(gx - x) + 64)
        return total

    def too_long(cfg) -> bool:
        return any(_length(b, e) > cap_units * _UNIT for b, e in cfg.bars)

    idx = list(range(len(moves))) if allowed is None else list(allowed)
    seen = {start.key(): 0}
    heap = [(dist(start), 0, 0, start, [])]
    tick = opened = 0
    best = dist(start)
    t0 = time.time()
    while heap:
        if time.time() > deadline:
            return {"found": False, "reason": "deadline", "opened": opened, "best": best,
                    "seconds": round(time.time() - t0, 1), "seen": len(seen)}
        _f, _d, _t, cfg, path = heapq.heappop(heap)
        opened += 1
        if opened > max_open or len(path) >= 60:
            if opened > max_open:
                return {"found": False, "reason": "max_open", "opened": opened, "best": best,
                        "seconds": round(time.time() - t0, 1), "seen": len(seen)}
            continue
        for n in idx:
            kind, colour, step = moves[n]
            nxt = grow(model, cfg, colour, step) if kind == "grow" else swivel(model, cfg, colour)
            if nxt is None:
                continue
            key = nxt.key()
            cost = len(path) + 1
            if seen.get(key, 1 << 30) <= cost:
                continue
            if too_long(nxt) or not legal(model, nxt):
                continue
            if solved(model, nxt):
                return {"found": True, "plan": [*path, n], "plan_len": cost, "opened": opened,
                        "seconds": round(time.time() - t0, 1), "seen": len(seen),
                        "clicks": [list(moves[i]) for i in [*path, n]]}
            seen[key] = cost
            tick += 1
            gg = dist(nxt)
            best = min(best, gg)
            heapq.heappush(heap, (cost + weight * gg, cost, tick, nxt, [*path, n]))
        if opened % 20000 == 0:
            print(f"# opened={opened} best={best} heap={len(heap)}", file=sys.stderr, flush=True)
    return {"found": False, "reason": "exhausted", "opened": opened, "best": best,
            "seconds": round(time.time() - t0, 1), "seen": len(seen)}


VARIANTS = [
    # (hmaze, max_open, weight, cap_units)
    (False, 120_000, 2, 99),      # 3  what swivel does today, in the joint fallback
    (True, 120_000, 2, 99),       # 4  + obstacle-aware heuristic only
    (True, 120_000, 4, 21),       # 5  + length cap and a harder lean
    (True, 400_000, 4, 21),       # 6
    (True, 1_500_000, 4, 21),     # 7
    (True, 1_500_000, 8, 21),     # 8
    (False, 1_500_000, 4, 21),    # 9  maze off, everything else on — isolates the heuristic
    (True, 1_500_000, 4, 12),     # 10 tighter cap
    (True, 1_500_000, 2, 21),     # 11
    (True, 6_000_000, 4, 21),     # 12
    (True, 6_000_000, 4, 16),     # 13
    (True, 6_000_000, 8, 16),     # 14
]


def main() -> None:
    job = int(sys.argv[1])
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    deadline = time.time() + budget
    print(f"# job {job} start", file=sys.stderr, flush=True)
    agent, sw, obs, who, arrived = reach_stuck()
    d = describe(sw, obs, who, arrived)
    if job == 1:
        print(json.dumps({"job": 1, **d}))
        return
    if job == 2:
        # H3 in isolation: the per-rider branch, but admitting the controls that move NO rider.
        from admorphiq.tools.swivel import _seek, solved, touches
        m, cfg = sw._model, sw._cfg
        reach = [touches(m, c) for _k, c, _s in sw._moves]
        free = [n for n, t in enumerate(reach) if not t]
        got = []
        for place_i, bar in (m.pairing or ()):
            allowed = [n for n, t in enumerate(reach) if bar in t] + free
            r = _seek(m, cfg, sw._moves, allowed, place_i, bar, sw._banned)
            got.append({"place": place_i, "bar": bar, "found": r is not None,
                        "len": len(r[0]) if r else None,
                        "solved_after": bool(r and solved(m, r[1]))})
        print(json.dumps({"job": 2, "per_rider_with_free_controls": got,
                          "n_free_controls": len(free)}))
        return
    v = VARIANTS[(job - 3) % len(VARIANTS)]
    hmaze, max_open, weight, cap_units = v
    m, cfg = sw._model, sw._cfg
    if m is None or not sw._moves:
        print(json.dumps({"job": job, "error": "no model", **d}))
        return
    if m.pairing is None:
        from admorphiq.tools.swivel import choose_pairing
        choose_pairing(m, cfg)
    r = joint(m, cfg, sw._moves, max_open=max_open, weight=weight, hmaze=hmaze,
              cap_units=cap_units, deadline=deadline)
    print(json.dumps({"job": job, "hmaze": hmaze, "max_open": max_open, "weight": weight,
                      "cap_units": cap_units, "pairing": [list(p) for p in (m.pairing or [])],
                      **r}))


if __name__ == "__main__":
    main()
