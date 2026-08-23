"""R98 feasibility probe — does a winning layout EXIST under the verified model?

Purpose
-------
Three search strategies have failed to find a winning layout on the three-source
level, together examining tens of thousands of candidates. Before making the search
cleverer, it is worth knowing whether the thing being searched for is there: the
model is VERIFIED against the engine on this board, so a large sample of layouts
answers the question directly.

The alternative reading — that the model is faithful, the layout exists, and the
search is simply not reaching it — is only worth acting on if a sample of this size
finds at least one winner, or gets closer than the structured searches did.

Expected feedback
-----------------
The best score found, how often each coverage level occurs, and whether any layout
reaches full coverage with zero barrier contacts. A sample that finds a winner says
"search harder"; a sample that never does says "the objective may be unreachable
under this piece set", which is a different and more interesting claim.
"""

from __future__ import annotations

import importlib.util
import os
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from admorphiq.hypothesis_select import compiler_flow as CF  # noqa: E402
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding  # noqa: E402
from admorphiq.hypothesis_select.propagate_flow import ORACLE, predict  # noqa: E402
from admorphiq.hypothesis_select.verifier_flow import build_flow_evidence  # noqa: E402

SAMPLES = int(os.environ.get("R98_FEASIBILITY_SAMPLES", "40000"))
SEED = 98


def _walker_module():
    spec = importlib.util.spec_from_file_location(
        "dw", str(Path(__file__).resolve().parent / "depth_walk.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    dw = _walker_module()
    w = dw.Walker()
    for _ in range(2):
        dw.play_level(w)

    g = FlowGrounding()
    g.observe(0, None, w.obs.frame)
    for a in (1, 1, 2, 3, 4):
        w.act(a, g)
    candidates = g.selection_candidates()
    if candidates is not UNKNOWN:
        for cell in candidates.value[:6]:
            w.click(cell, g)
    w.act(5, g)
    emitters, direction = g.emitters(), g.initial_direction()
    if emitters is not UNKNOWN and direction is not UNKNOWN:
        dr, _dc = direction.value
        lane = emitters.value[0][1] if dr != 0 else emitters.value[0][0]
        guard = 0
        while guard < 16 and g.tracked_region() is not UNKNOWN:
            cur = g.tracked_region().value
            have = [c for _, c in cur] if dr != 0 else [r for r, _ in cur]
            if min(have) <= lane <= max(have):
                break
            w.act(4 if lane > max(have) else 3, g)
            guard += 1
        w.act(5, g)

    board = build_flow_evidence(g, False).board
    if board is None:
        print("[feasibility] grounding produced no board")
        return 1
    deltas = {a: (dr, dc) for a, dr, dc in g.piece_deltas().value}
    sink_cells = {c for s in board.sinks for c in s}
    options = [
        CF._piece_options(board, i, deltas, sink_cells) for i in range(len(board.pieces))
    ]
    print(f"pieces={len(board.pieces)} targets={len(board.sinks)} "
          f"placements per piece={[len(o) for o in options]}")
    print(f"sampling {SAMPLES} random layouts (seed {SEED})\n")

    rng = random.Random(SEED)
    tally: Counter = Counter()
    best = (-1, -99)
    best_offsets = None
    winners = 0
    for _ in range(SAMPLES):
        offsets = tuple(rng.choice(o)[0] for o in options)
        prediction = predict(board.with_offsets(offsets), ORACLE)
        satisfied = len(prediction.satisfied)
        tally[(satisfied, prediction.barrier_hits)] += 1
        score = (satisfied, -prediction.barrier_hits)
        if score > best:
            best, best_offsets = score, offsets
        if satisfied == len(board.sinks) and prediction.barrier_hits == 0:
            winners += 1

    print("(targets satisfied, barrier contacts) -> count, most common first:")
    for key, count in tally.most_common(12):
        print(f"  {key}: {count}")
    print(f"\nbest sampled: {best[0]} target(s), {-best[1]} barrier contact(s) "
          f"at offsets {best_offsets}")
    print(f"layouts reaching full coverage with ZERO barrier contacts: {winners}")
    verdict = (
        "a winner EXISTS — the wall is search"
        if winners
        else "no winner in this sample — the objective may be unreachable with this "
             "piece set under the verified model"
    )
    print(f"\n[feasibility] {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
