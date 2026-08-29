"""dc22: a control that "did nothing" is not inert — it was asked at ONE rail position.

MEASURED before this was written, and it is the whole diagnosis:

  * `scripts/_dc22_rail.py`, 4 runs x 167 presses, avatar held still at (49,28): the four crane
    drives (32,50) (36,46) (36,54) (40,50) are stone dead — 0 board changes — while (8,56) and
    (25,51) answer from the same cell.  So the instrument is attached and the drives really are
    refused there.
  * `/tmp/pfan_dc22pt17.jsonl`: the SAME (32,50) slides a 28-pixel body by (-4,0) when pressed
    from (55,34), twelve times.  The tool banks it in `_slid` at turn ~235 — and `_register_slide`
    needs a SECOND control on the same shape before it will believe a rail, so `_shape` stays
    None, `_kind` still reads (36,46) (36,54) (40,50) as "idle", and the tool retires at turn 269.
  * The game's own `step()` says why: a drive is refused unless the crane's own grid position
    admits that direction (`sjixewahg`/`uxtzlxsiq`, gated either by a drawn `vcha` track or by a
    hardcoded C).  Three of four directions are dead at any end of the rail.

`_confirm_probe` asks each idle control EXACTLY ONCE per level (`_gprobed` is a set of clicks), so
the three silent drives are condemned at a rail position where they could not possibly answer.

This arm clears that memory whenever the provisional body MOVES, capped, and logs whether a second
control is then found.  Rule 7x: driven by the scorer's own `run_game`.  Rule 7f: the level count
is printed as a number.

  arg 1 = repetition (deterministic; the game is not stochastic, this is a fan slot)
  arg 2 = rounds cap (0 = control arm, unchanged tool)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import score_efficiency as SE  # noqa: E402

LOG: list = []
S = {"rounds": 0}


def instrument(cap: int):
    from admorphiq.tools.gantry import GantryCraneTool

    orig_reg = GantryCraneTool._register_slide
    orig_conf = GantryCraneTool._confirm_probe
    orig_reset = GantryCraneTool.reset

    def reset(self):
        orig_reset(self)
        S["rounds"] = 0

    def _register_slide(self, click, before, board, slide):
        took = orig_reg(self, click, before, board, slide)
        if not took and self._shape is None and cap:
            # The body moved and the rail is still unproven: every "did nothing" recorded so far
            # was recorded at a DIFFERENT position of that body and says nothing about this one.
            if S["rounds"] < cap:
                S["rounds"] += 1
                self._gprobed = set()
                LOG.append({"REASK_ROUND": S["rounds"], "after": list(click),
                            "delta": [int(slide[0][0]), int(slide[0][1])],
                            "idle": sorted(f"{c[0]},{c[1]}" for c, k in self._kind.items()
                                           if k == "idle")})
        if took:
            LOG.append({"SHAPE_SET": list(click), "drives": len(self._drives()),
                        "delta": [int(slide[0][0]), int(slide[0][1])]})
        return took

    def _confirm_probe(self, geom, start):
        out = orig_conf(self, geom, start)
        if out:
            LOG.append({"ASK": list(out[0][1]), "from": list(start) if start else None,
                        "round": S["rounds"]})
        return out

    GantryCraneTool.reset = reset
    GantryCraneTool._register_slide = _register_slide
    GantryCraneTool._confirm_probe = _confirm_probe


def main():
    rep = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    instrument(cap)
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"result": "NO_GAME"}), flush=True)
        return
    ei = envs[0]
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="unified",
                      max_actions=4000)
    print(json.dumps({"rep": rep, "cap": cap,
                      "levels_completed": int(res.get("levels_completed") or 0),
                      "total_actions": res.get("total_actions"),
                      "game_score": res.get("game_score"),
                      "per_level": res.get("per_level"),
                      "reask_rounds": S["rounds"],
                      "shape_set": sum(1 for r in LOG if "SHAPE_SET" in r),
                      "asks": sum(1 for r in LOG if "ASK" in r)}), flush=True)
    for r in LOG[:120]:
        print(json.dumps(r), flush=True)


if __name__ == "__main__":
    main()
