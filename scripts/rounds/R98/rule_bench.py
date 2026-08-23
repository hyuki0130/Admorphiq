"""R98: judge a propagation rule against FIXED evidence.

Re-running the depth walk after a rule change compares the new rule on a NEW layout,
because the compiler's choice moves with the model. Measured twice: a restriction that
should have removed four surplus cells instead produced a different plan and twenty-four.
A rule has to be judged against a board and a spill that do not move.

`depth_walk.py` with R98_CAPTURE=<path> freezes the board AS COMMITTED together with the
spill the engine produced on it. This replays that board under the current propagator and
reports the two numbers that matter: cells the model invents, and cells it misses.

NON-GATING diagnostic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from admorphiq.hypothesis_select.propagate_flow import ORACLE, Board, predict  # noqa: E402


def _board(payload: dict) -> Board:
    cells = lambda xs: frozenset(tuple(c) for c in xs)  # noqa: E731
    return Board(
        pieces=tuple(cells(p) for p in payload["pieces"]),
        sinks=tuple(cells(s) for s in payload["sinks"]),
        hazard_cells=cells(payload["hazard_cells"]),
        emitter_cells=cells(payload["emitter_cells"]),
        standing_flow=cells(payload["standing_flow"]),
        absorber_cells=cells(payload["absorber_cells"]),
        emergences=tuple((tuple(c), t) for c, t in payload["emergences"]),
        falling_sources=tuple(tuple(x) for x in payload["falling_sources"]),
        direction=tuple(payload["direction"]),
        size=payload["size"],
    )


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "scratchpad/r98_idx3.json"
    with open(path) as f:
        payload = json.load(f)

    board = _board(payload)
    observed = [{tuple(c) for c in layer} for layer in payload["observed"]]
    prediction = predict(board, ORACLE)
    predicted = [set(layer) for layer in prediction.frontier if layer]

    pred_cells = {c for layer in predicted for c in layer}
    obs_cells = {c for layer in observed for c in layer}
    named = [sorted(s)[0] for s in board.sinks]

    print(f"evidence: {path}")
    print(f"  predicted {len(predicted)} step(s) / {len(pred_cells)} cells "
          f"vs observed {len(observed)} / {len(obs_cells)}")
    print(f"  satisfies {[named[i] for i in sorted(prediction.satisfied) if i < len(named)]}")
    print(f"  INVENTED {sorted(pred_cells - obs_cells)}")
    print(f"  MISSED   {sorted(obs_cells - pred_cells)}")
    for i in range(max(len(predicted), len(observed))):
        a = sorted(predicted[i]) if i < len(predicted) else []
        b = sorted(observed[i]) if i < len(observed) else []
        if a != b:
            print(f"  first divergence at step {i}: predicted {a} | observed {b}")
            break
    else:
        print("  the trails agree cell for cell")
    if len(sys.argv) > 2 and sys.argv[2] == "--layers":
        for i in range(max(len(predicted), len(observed))):
            a = sorted(predicted[i]) if i < len(predicted) else []
            b = sorted(observed[i]) if i < len(observed) else []
            mark = "  " if a == b else "!!"
            print(f"  {mark} {i:2d}: predicted {a}")
            print(f"        observed  {b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
