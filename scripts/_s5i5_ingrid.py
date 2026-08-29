"""s5i5 level 7 — is there a win that NEVER leaves the visible grid?

Why the question decides the repair. This board is framed by a wall placed at (-3,-3), so part of
it lies OUTSIDE the 64x64 frame and a frame-only tool cannot see it at all. `swivel` therefore
cannot tell whether a move that swings a bar past the edge is legal, and learns the margin only by
being REFUSED — banking, per refusal, every off-grid cell the move would have touched (45 cells and
2 banned configurations by the time it dies on level 7).

That learning is a superset in one direction and a blind spot in the other, and MEASURED
(`scripts/_s5i5_arm.py`) it does not recover: after two refusals no search up to 400k pops finds a
way out of the state the tool has walked into.

But if a winning sequence exists in which no bar ever leaves the grid, the tool never has to guess
about the margin at all — it can simply refuse to plan through cells it cannot verify, which is a
generic prior for any frame-only planner and not a fact about this game.

⚠️ It is NOT free: `swivel`'s own docstring records that the level before this one swings a bar off
the TOP edge and is allowed to, so treating the margin as solid by default loses that level. The
question here is only whether the option EXISTS on the board that needs it.

Jobs vary the open budget, the length cap and whether the margin is banned, so the ban's cost is
measured against the same search rather than asserted.

Run:  bash scripts/pfan.sh s5i5ingrid scripts/_s5i5_ingrid.py 8 "" 4
"""
from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, "src")

TITLE = "s5i5"
STUCK = 6


def reach_level7():
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
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=700, stall=80, ctx_budget=6000)
    sw = agent.tools.get("swivel")
    frames = [obs]
    arrived = None
    for step in range(700):
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl >= STUCK:
            if arrived is None:
                arrived = step
            if getattr(sw, "_level", None) == lvl and getattr(sw, "_moves", None):
                break
            if step - arrived > 120:
                break
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    return sw, arrived


def search(model, start, moves, *, max_open: int, weight: int, cap_units: int,
           in_grid: bool, deadline: float) -> dict:
    import heapq

    import admorphiq.tools.swivel as sv

    lim = cap_units * sv._UNIT if cap_units else 10 ** 9

    def ok(cfg) -> bool:
        for box, edge in cfg.bars:
            if sv._length(box, edge) > lim:
                return False
            if in_grid and (box[0] < 0 or box[1] < 0 or box[2] > 63 or box[3] > 63):
                return False
        return sv.legal(model, cfg)

    def dist(cfg) -> int:
        total = 0
        for place_i, bar in model.pairing:
            y, x = sv.rider_at(cfg, bar)
            gy, gx = model.places[place_i]
            total += abs(gy - y) + abs(gx - x)
        return total

    seen = {start.key(): 0}
    heap = [(dist(start), 0, 0, start, [])]
    tick = opened = 0
    best = dist(start)
    t0 = time.time()
    while heap:
        if time.time() > deadline:
            return {"found": False, "reason": "deadline", "opened": opened, "best": best,
                    "s": round(time.time() - t0, 1)}
        _f, _d, _t, cfg, path = heapq.heappop(heap)
        opened += 1
        if opened > max_open:
            return {"found": False, "reason": "max_open", "opened": opened, "best": best,
                    "s": round(time.time() - t0, 1)}
        if len(path) >= 60:
            continue
        for n, (kind, colour, step) in enumerate(moves):
            nxt = (sv.grow(model, cfg, colour, step) if kind == "grow"
                   else sv.swivel(model, cfg, colour))
            if nxt is None:
                continue
            key = nxt.key()
            cost = len(path) + 1
            if seen.get(key, 1 << 30) <= cost or not ok(nxt):
                continue
            if sv.solved(model, nxt):
                return {"found": True, "plan_len": cost, "opened": opened,
                        "s": round(time.time() - t0, 1),
                        "clicks": [list(moves[i]) for i in [*path, n]]}
            seen[key] = cost
            tick += 1
            gg = dist(nxt)
            best = min(best, gg)
            heapq.heappush(heap, (cost + weight * gg, cost, tick, nxt, [*path, n]))
    return {"found": False, "reason": "exhausted", "opened": opened, "best": best,
            "s": round(time.time() - t0, 1)}


VARIANTS = [
    dict(max_open=400_000, weight=4, cap_units=21, in_grid=True),
    dict(max_open=400_000, weight=4, cap_units=21, in_grid=False),
    dict(max_open=400_000, weight=2, cap_units=21, in_grid=True),
    dict(max_open=1_500_000, weight=4, cap_units=21, in_grid=True),
    dict(max_open=400_000, weight=4, cap_units=12, in_grid=True),
    dict(max_open=400_000, weight=8, cap_units=21, in_grid=True),
    dict(max_open=1_500_000, weight=2, cap_units=21, in_grid=True),
    dict(max_open=400_000, weight=4, cap_units=0, in_grid=True),
]


def main() -> None:
    job = int(sys.argv[1])
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    deadline = time.time() + budget
    v = VARIANTS[(job - 1) % len(VARIANTS)]
    sw, arrived = reach_level7()
    if sw is None or sw._model is None or not sw._moves:
        print(json.dumps({"job": job, "error": "no model", "arrived": arrived}))
        return
    import admorphiq.tools.swivel as sv
    m, cfg = sw._model, sw._cfg
    if m.pairing is None:
        sv.choose_pairing(m, cfg)
    n_offgrid_now = sum(1 for b, _e in cfg.bars
                        if b[0] < 0 or b[1] < 0 or b[2] > 63 or b[3] > 63)
    r = search(m, cfg, sw._moves, deadline=deadline, **v)
    print(json.dumps({"job": job, **v, "arrived": arrived,
                      "bars_offgrid_at_start": n_offgrid_now,
                      "n_moves": len(sw._moves), **r}))


if __name__ == "__main__":
    main()
