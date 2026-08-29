"""How many cells does the phase-family floor rule condemn for ONE pixel — and on which games?

⛔ THE DEFECT, found on dc22 and generalised here. `phase.py`'s floor rule rejects an
avatar-sized tile if ANY pixel in it is a condemned colour, and `_learn_refusal` condemns
COLOURS, board-wide, from a single refusal. A flat tile of a genuinely lethal colour is a correct
rejection. A DRAWN SPRITE that merely contains one pixel of that colour is not — and on dc22 level
6 every `njvd-rolo` pressure plate is a 2x2 sprite drawn `[[1,0],[0,C]]`, so colour 0 condemns the
exact four cells the crane's drives require, and `_plan_full` returns a plan of length ZERO
between them while a raw two-move walk works every time.

⚠️ SCOPE CORRECTION, measured before this was written: `sluice.py` does NOT import `phase.py` — it
carries its OWN module-level `_standable(board, cells, barred)` over a `Board` object. The only
importers of `PhaseGridTool` are `phase.py` itself and `gantry.py`. So the shared-file blast radius
is `PhaseGridTool` + `GantryCraneTool`, and this census instruments exactly those two.

What is counted, once per turn, on the tool's OWN current world:

  window_has_bg          rejected for background — the rule working, not counted
  window_has_nf          rejected for a condemned colour
  window_uniform_nf      ... and the whole tile IS that colour: a correct rejection
  MIXED-REJECTED         has a condemned pixel, no background pixel, and is NOT uniform
                         <- the defect shape: a drawn thing condemned for one pixel

⭐ And the proof that needs no interpretation: a cell that was MIXED-REJECTED on some turn and
that the avatar LATER STANDS IN. The rejection cannot have been right.

  arg 1 = 1-based index into the sorted game list (a fan slot; 25 games, one per slot).
Rule 7x: the scorer's own `run_game` drives it.  Rule 7f: the level count prints as a number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402

ST: dict = {"turns": 0, "turns_with_nf": 0, "condemned_at": {}, "occupied_at": {},
            "mixed": 0, "uniform": 0, "bg": 0, "nf_colours": set(), "tools": {}}


def _boxsum(mask: np.ndarray, side: int) -> np.ndarray:
    acc = np.zeros((mask.shape[0] + 1, mask.shape[1] + 1), dtype=np.int32)
    acc[1:, 1:] = mask.astype(np.int32).cumsum(0).cumsum(1)
    return (acc[side:, side:] - acc[:-side, side:] - acc[side:, :-side] + acc[:-side, :-side])


def census(self, geom, name):
    board = np.asarray(geom["board"], dtype=int)
    bg = int(geom["bg"])
    side = max(1, int(self._side or 2))
    ST["turns"] += 1
    ST["tools"][name] = ST["tools"].get(name, 0) + 1
    if self._avatar >= 0:
        at = self._at(board, self._avatar)
        if at is not None:
            ST["occupied_at"].setdefault(at, ST["turns"])
    nf = set(self._not_floor)
    if not nf:
        return
    ST["turns_with_nf"] += 1
    ST["nf_colours"] |= {int(c) for c in nf}
    layout = board
    if board.shape[0] < side or board.shape[1] < side:
        return
    has_bg = _boxsum(layout == bg, side) > 0
    nf_mask = np.zeros(layout.shape, dtype=bool)
    uniform = np.zeros(has_bg.shape, dtype=bool)
    for c in nf:
        eq = layout == c
        nf_mask |= eq
        uniform |= _boxsum(eq, side) == side * side
    has_nf = _boxsum(nf_mask, side) > 0
    ST["bg"] += int(has_bg.sum())
    ST["uniform"] += int((~has_bg & uniform).sum())
    mixed = (~has_bg) & has_nf & (~uniform)
    ST["mixed"] += int(mixed.sum())
    for y, x in np.argwhere(mixed):
        ST["condemned_at"].setdefault((int(y), int(x)), ST["turns"])


def instrument():
    from admorphiq.tools.base import frame_2d
    from admorphiq.tools.gantry import GantryCraneTool
    from admorphiq.tools.phase import PhaseGridTool

    for cls, name in ((PhaseGridTool, "phase_grid"), (GantryCraneTool, "gantry")):
        orig = cls.propose

        def make(orig=orig, name=name):
            def propose(self, frames, obs):
                out = orig(self, frames, obs)
                try:
                    g = frame_2d(obs)
                    geom = self._read(np.asarray(g, dtype=int)) if g is not None else None
                    if geom is not None:
                        census(self, geom, name)
                except Exception as exc:  # a census must never change what is measured
                    ST.setdefault("errors", []).append(repr(exc)[:120])
                return out
            return propose

        cls.propose = make()


def main():
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    instrument()
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = sorted(arcade.get_environments(), key=lambda e: e.game_id)
    if idx < 1 or idx > len(envs):
        print(json.dumps({"result": "NO_SLOT", "idx": idx, "games": len(envs)}), flush=True)
        return
    ei = envs[idx - 1]
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="unified",
                      max_actions=4000)
    proof = {c: (ST["condemned_at"][c], ST["occupied_at"][c])
             for c in set(ST["condemned_at"]) & set(ST["occupied_at"])
             if ST["occupied_at"][c] > ST["condemned_at"][c]}
    print(json.dumps({
        "idx": idx, "game": ei.game_id,
        "levels_completed": int(res.get("levels_completed") or 0),
        "total_actions": res.get("total_actions"), "game_score": res.get("game_score"),
        "tool_turns": ST["tools"], "turns_with_not_floor": ST["turns_with_nf"],
        "not_floor_colours": sorted(ST["nf_colours"]),
        "rejections_bg": ST["bg"], "rejections_uniform_nf": ST["uniform"],
        "rejections_MIXED": ST["mixed"],
        "distinct_mixed_cells": len(ST["condemned_at"]),
        "PROOF_condemned_then_occupied": len(proof),
        "proof_cells": [[list(c), v[0], v[1]] for c, v in sorted(proof.items())][:20],
        "errors": ST.get("errors", [])[:3],
    }), flush=True)


if __name__ == "__main__":
    main()
