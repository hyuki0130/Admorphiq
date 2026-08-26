"""Does the engine's spread stay WITHIN the obstacle it is spreading along?

Purpose: idx3's entire residual is three invented cells, and following it back showed the
cause — flow blocked by `piece1` (row 5, columns 9-11) spreads along its top face, the
engine's spread ends at column 11 (the obstacle's own extent) and ours continues to (4,12),
one cell past the edge, then falls down the empty column. `_beside` takes the nearest free
cell either side with no notion of the blocker's extent, so the overstep is structural.

This measures the fix WITHOUT shipping it: patch `_beside` so a candidate is accepted only
while the cell AHEAD of it is still blocked — i.e. the spread stays over the obstacle — and
replay every fixed capture under both rules.

Expected feedback: error falling to zero on idx3 while staying zero on idx0/idx1/idx2 makes
this the rule. Error rising anywhere means the obstacle-extent reading is wrong and the
overstep is doing work elsewhere. Anything else names which board disagrees.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[2] / "src"))

_spec = importlib.util.spec_from_file_location("_rule_bench", _HERE / "rule_bench.py")
_rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rb)

from admorphiq.hypothesis_select import propagate_flow as PF  # noqa: E402

_original_reach = PF.WALK_REACH


def _error(payload: dict) -> int:
    board = _rb._board(payload)
    pred = {c for layer in PF.predict(board, PF.ORACLE).frontier for c in layer}
    real = {tuple(c) for step in payload["observed"] for c in step}
    return len(pred - real) + len(real - pred)


def main() -> int:
    caps = sorted(_HERE.glob("evidence/walk_idx*.json"))
    reach = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    print(f"WALK_REACH {_original_reach} -> {reach}")
    print(f"{'capture':16s} {'current':>9s} {'patched':>14s}")
    worse = better = 0
    for path in caps:
        payload = json.load(open(path))
        PF.WALK_REACH = _original_reach
        now = _error(payload)
        PF.WALK_REACH = reach
        fixed = _error(payload)
        PF.WALK_REACH = _original_reach
        mark = ""
        if fixed < now:
            mark, better = "  <-- BETTER", better + 1
        elif fixed > now:
            mark, worse = "  <-- WORSE", worse + 1
        print(f"{path.stem:16s} {now:9d} {fixed:14d}{mark}")
    print(f"\nbetter on {better} capture(s), worse on {worse}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
