"""WHY crag's window fails to align on bp35's sixth board — which of three causes, measured.

`_stitch` returns "lost" from exactly one place: `best is None or best[0][0] < _ALIGN_FIT`. Three
different faults hide behind that one word and they need different fixes:

  A  no candidate was even scored — every (reading, shift) pair was refused by `_admissible`
     (the physics window) or fell under `_ALIGN_MIN` comparable cells;
  B  candidates were scored and the best one is CLOSE to the 0.82 threshold — a threshold problem;
  C  candidates were scored and the best is FAR below — the window genuinely is not this board,
     or the map it is being matched against is already wrong.

⛔ Guessing between them is how the thirteen reverted repairs of R101SILENT happened; `alignment
threshold` and `admissibility bypass` are both on that list, so B and A have each been tried blind.
This measures the distribution instead: for every "lost" on the wall board it records the number of
(reading, shift) pairs considered, how many were refused by admissibility, how many by
`_ALIGN_MIN`, and the best score actually achieved.

⛔ Runs the scorer's own agent factory and its exact loop. `levels_completed` printed as a NUMBER.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.tools import crag as cragmod

    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(se)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = se._make_agent("unified", info.game_id)
    crag = agent.tools.get("crag")

    state = {"level": 0}
    reports: list[dict] = []
    raw_stitch = crag._stitch

    def stitch_spy(readings, allow):
        out = raw_stitch(readings, allow)
        if out[0] != "lost" or state["level"] < 5 or len(reports) >= 30:
            return out
        # Re-run the scoring loop as `_stitch` does, counting where each pair died.
        lo = min(r for r, _ in crag._world)
        hi = max(r for r, _ in crag._world)
        pairs = inadmissible = thin = 0
        scores: list[float] = []
        totals: list[int] = []
        for _idx, (_oy, _ox, board, _inks, body) in enumerate(readings):
            for shift in range(lo - crag._rows, hi + crag._rows + 1):
                pairs += 1
                if not crag._admissible(body[0] + shift, allow):
                    inadmissible += 1
                    continue
                agree = total = 0
                for (r, c), sg in board.items():
                    if (r, c) == body:
                        continue
                    was = crag._world.get((r + shift, c))
                    if was is None or was in crag._volatile or sg in crag._volatile:
                        continue
                    total += 1
                    agree += was == sg
                if total < cragmod._ALIGN_MIN:
                    thin += 1
                    totals.append(total)
                    continue
                scores.append(agree / total)
        reports.append({
            "readings": len(readings), "allow": allow, "pairs": pairs,
            "refused_by_physics": inadmissible, "refused_as_too_thin": thin,
            "scored": len(scores),
            "best_score": round(max(scores), 3) if scores else None,
            "threshold": cragmod._ALIGN_FIT,
            "top5": sorted((round(s, 3) for s in scores), reverse=True)[:5],
            "thin_totals_top": sorted(totals, reverse=True)[:5],
            "align_min": cragmod._ALIGN_MIN,
            "world_cells": len(crag._world), "volatile": len(crag._volatile),
            "at": list(crag._at) if crag._at else None,
        })
        return out

    crag._stitch = stitch_spy

    restart_on_game_over = bool(getattr(agent, "restart_on_game_over", False))
    levels = int(getattr(obs, "levels_completed", 0) or 0)
    start = levels
    step = 0
    for step in range(cap):
        state["level"] = levels
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        if obs is None:
            break
        levels = int(getattr(obs, "levels_completed", levels) or 0)
        if getattr(obs, "state", None) == GameState.WIN:
            break
        if getattr(obs, "state", None) == GameState.GAME_OVER:
            if not restart_on_game_over:
                break
            obs = env.step(GameAction.RESET)
            if obs is None:
                break

    print(json.dumps({
        "levels_completed_start": start, "levels_completed_end": levels,
        "greater_than_start": levels > start, "actions": step + 1,
        "lost_events_on_wall": len(reports), "detail": reports[:10],
    }))


if __name__ == "__main__":
    main()
