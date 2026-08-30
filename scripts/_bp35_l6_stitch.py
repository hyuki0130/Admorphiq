"""Why can crag not place bp35's level-6 window — dump the stitch, with level 5 as the control.

crag clears boards 1-5 of bp35 and then reports "window does not belong to this board" on board 6,
where `graph` inherits 500 actions and clears nothing. Three cheap causes were measured out already
(moving terrain, a horizontal pan, a transitional frame); what was left unexamined is the stitch
itself. This wraps `CragTool._stitch` and records, for EVERY call: the outcome, the best shift, the
best agreement, how many cells that agreement was computed over, the window shape, and — when the
window is refused — which signature pairs disagree and how often.

⛔ TWO CONTROLS IN ONE RUN (rule 7aj.3). The same instrument records boards 1-5, where the stitch is
known to work: a log showing high agreement there and 0.60 on board 6 is evidence about board 6. A
log that is empty, or low everywhere, is evidence about the instrument.

Expected feedback: if the refused windows disagree on a handful of cells that MOVE, the world needs
them volatile. If they disagree across static rock at every shift, the shift search is looking in
the wrong place. If agreement is high but `total` is under the floor, the window simply does not
overlap the map and the refusal is a reach problem, not a reading one.

Usage: _bp35_l6_stitch.py <seed>   (seed is ignored; the run is deterministic. It exists so the
probe can be fanned and so a repeat proves determinism.)
"""
from __future__ import annotations

import json
import sys
from collections import Counter


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools import crag as cragmod

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    log: list[dict] = []
    state = {"level": 0, "step": 0}
    real_stitch = cragmod.CragTool._stitch

    def traced(self, readings, allow):
        world_before = dict(self._world)
        rows_before, cols_before = self._rows, self._cols
        out = real_stitch(self, readings, allow)
        outcome = out[0]
        rec = {
            "step": state["step"], "level": state["level"], "outcome": outcome,
            "allow": allow, "world": len(world_before), "rows": rows_before,
            "cols": cols_before, "at": self._at, "g": self._gdir,
            "origin": self._origin, "note": self._note,
        }
        # Re-run the shift search ourselves so the refused windows can be described. This is the
        # SAME arithmetic as `_stitch`, deliberately duplicated: reading it out of the tool would
        # need the tool to keep it, and a probe must not change what it measures.
        if world_before and outcome == "lost":
            lo = min(r for r, _ in world_before)
            hi = max(r for r, _ in world_before)
            best = None
            for idx, (_oy, _ox, board, _inks, body) in enumerate(readings):
                for shift in range(lo - rows_before, hi + rows_before + 1):
                    adm = self._admissible(body[0] + shift, allow)
                    agree = total = 0
                    clash: Counter = Counter()
                    for (r, c), sg in board.items():
                        if (r, c) == body:
                            continue
                        was = world_before.get((r + shift, c))
                        if was is None or was in self._volatile or sg in self._volatile:
                            continue
                        total += 1
                        if was == sg:
                            agree += 1
                        else:
                            clash[(len(was), len(sg))] += 1
                    if total < cragmod._ALIGN_MIN:
                        continue
                    score = agree / total
                    cand = (score, total, shift, idx, adm, dict(clash))
                    if best is None or (score, total) > (best[0], best[1]):
                        best = cand
            if best is not None:
                rec["best_fit"] = round(best[0], 3)
                rec["best_total"] = best[1]
                rec["best_shift"] = best[2]
                rec["best_admissible"] = best[4]
                rec["clash_shapes"] = {str(k): v for k, v in sorted(best[5].items())}
            else:
                rec["best_fit"] = None
                rec["overlap_floor"] = cragmod._ALIGN_MIN
            rec["readings"] = len(readings)
            rec["window_cells"] = len(readings[0][2])
        log.append(rec)
        return out

    cragmod.CragTool._stitch = traced

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    env = arcade.make(info.game_id)
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=8000, stall=80, ctx_budget=6000)
    obs = env.observation_space
    restart = bool(getattr(agent, "restart_on_game_over", False))
    holders: Counter = Counter()
    total_actions = 0
    while total_actions < budget:
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        if not isinstance(act, GameAction):
            break
        state["step"] = total_actions
        state["level"] = int(getattr(obs, "levels_completed", 0) or 0)
        holders[(state["level"], agent._current)] += 1
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        if obs is None:
            break
        total_actions += 1
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart:
                break
            obs = env.step(GameAction.RESET)
            total_actions += 1
            if obs is None:
                break

    crag = agent.tools.get("crag")
    per_level: dict[int, Counter] = {}
    for r in log:
        per_level.setdefault(r["level"], Counter())[r["outcome"]] += 1
    lost6 = [r for r in log if r["level"] == 5 and r["outcome"] == "lost"]
    lost5 = [r for r in log if r["level"] == 4 and r["outcome"] == "lost"]
    print(json.dumps({
        "seed": seed, "actions": total_actions,
        "levels": int(getattr(obs, "levels_completed", 0) or 0),
        "holders": {f"L{lv}:{tl}": n for (lv, tl), n
                    in sorted(holders.items(), key=lambda kv: (kv[0][0], str(kv[0][1])))},
        "stitch_by_level": {str(k): dict(v) for k, v in sorted(per_level.items())},
        "crag": {"refuted": crag._refuted, "mute": crag._mute, "idle": crag._idle,
                 "note": crag._note, "world": len(crag._world), "rows": crag._rows,
                 "pitch": crag._pitch, "bands": {str(k): v for k, v in crag._bands.items()},
                 "vocab": {"open": len(crag._open), "solid": len(crag._solid),
                           "lethal": len(crag._lethal), "vanish": len(crag._vanish),
                           "swap": len(crag._swap), "flip": len(crag._flip),
                           "inert": len(crag._inert)}},
        "first_lost_on_l6": lost6[:6],
        "n_lost_on_l6": len(lost6),
        "control_lost_on_l5": lost5[:3], "n_lost_on_l5": len(lost5),
        "l6_notes": dict(__import__("collections").Counter(r["note"] for r in log if r["level"] == 5)),
    }))


if __name__ == "__main__":
    main()
