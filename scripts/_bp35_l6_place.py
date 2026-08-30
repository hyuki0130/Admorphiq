"""Is bp35's board-6 window REFUSED, or does it genuinely share nothing with the map?

`_bp35_l6_stitch.py` measured the refusal: five windows are absorbed, the sixth scores 0.60 over
twenty cells and every later one is refused. Twenty cells is one row plus a bit of a ten-column
board, so "0.60" may be describing a spurious alignment rather than a misread one. The two readings
are opposite repairs — a rejected-but-correct shift is an admissibility bug; no correct shift at all
is a REACH problem, and no threshold fixes it.

This dumps, for every refused window, the full shift curve: every (reading, shift) pair with its
agreement, its overlap size and whether the physics filter allowed it. It also reports the engine's
own camera row, which is not available to the tool and is used ONLY to say where the window truly is.

⛔ CONTROL: the same dump is taken on board 5, which is absorbed every frame. A curve with a clean
peak there and none on board 6 is evidence about board 6; two flat curves are evidence about the
dump.

Usage: _bp35_l6_place.py <seed>
"""
from __future__ import annotations

import json
import sys


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools import crag as cragmod

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    env = arcade.make(info.game_id)
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=8000, stall=80, ctx_budget=6000)
    obs = env.observation_space

    dumps: list[dict] = []
    state = {"level": 0, "step": 0}
    real = cragmod.CragTool._stitch

    def cam_row():
        """The engine's own camera row — DIAGNOSTIC ONLY, never available to the tool."""
        try:
            g = env._game if hasattr(env, "_game") else None
            inner = getattr(g, "oztjzzyqoek", None)
            return None if inner is None else int(inner.camera.rczgvgfsfb[1])
        except Exception:
            return None

    def traced(self, readings, allow):
        world = dict(self._world)
        rows = self._rows
        out = real(self, readings, allow)
        lvl = state["level"]
        if not world or lvl not in (4, 5):
            return out
        lo = min(r for r, _ in world)
        hi = max(r for r, _ in world)
        curve = []
        for idx, (oy, ox, board, _inks, body) in enumerate(readings):
            for shift in range(lo - rows, hi + rows + 1):
                agree = total = 0
                for (r, c), sg in board.items():
                    if (r, c) == body:
                        continue
                    was = world.get((r + shift, c))
                    if was is None or was in self._volatile or sg in self._volatile:
                        continue
                    total += 1
                    agree += was == sg
                if total:
                    curve.append({"i": idx, "oy": oy, "ox": ox, "shift": shift,
                                  "fit": round(agree / max(total, 1), 3), "n": total,
                                  "adm": self._admissible(body[0] + shift, allow)})
        curve.sort(key=lambda d: (-d["fit"], -d["n"]))
        dumps.append({"step": state["step"], "level": lvl, "outcome": out[0], "allow": allow,
                      "world_rows": [lo, hi], "world": len(world), "rows": rows,
                      "cam": cam_row(), "at": self._at, "g": self._gdir,
                      "top": curve[:8],
                      "best_over_floor": next((d for d in curve
                                               if d["n"] >= cragmod._ALIGN_MIN), None)})
        return out

    cragmod.CragTool._stitch = traced

    restart = bool(getattr(agent, "restart_on_game_over", False))
    total_actions = 0
    while total_actions < 4000:
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        if not isinstance(act, GameAction):
            break
        state["step"] = total_actions
        state["level"] = int(getattr(obs, "levels_completed", 0) or 0)
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
        if state["level"] == 5 and len([d for d in dumps if d["level"] == 5]) >= 10:
            break

    ctrl = [d for d in dumps if d["level"] == 4]
    six = [d for d in dumps if d["level"] == 5]
    print(json.dumps({
        "seed": seed, "actions": total_actions,
        "control_l5_n": len(ctrl), "control_l5_sample": ctrl[-3:],
        "l6_n": len(six), "l6": six,
    }))


if __name__ == "__main__":
    main()
