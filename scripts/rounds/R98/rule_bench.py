"""R98: judge a propagation rule against FIXED evidence.

Re-running the depth walk after a rule change compares the new rule on a NEW layout,
because the compiler's choice moves with the model. Measured twice: a restriction that
should have removed four surplus cells instead produced a different plan and twenty-four.
A rule has to be judged against a board and a spill that do not move.

`depth_walk.py` with R98_CAPTURE=<path> freezes the board AS COMMITTED together with the
spill the engine produced on it. This replays that board under the current propagator and
reports the two numbers that matter: cells the model invents, and cells it misses.

`--all` sweeps every capture and reports TWO totals, because they answer different
questions and only one of them judges a propagation rule:

  as-known   the sources the grounding held when the board was committed. This is what
             the agent actually predicts with, and it is dominated by evidence TIMING:
             three captures were taken before enough spills had accumulated, and their
             missed cells sit in lanes the model was never told about. 83 of the 211.
  physics    the same boards with the sources the grounding admits from the spill
             itself, unioned onto what it already knew. Given the sources, does the
             propagator reproduce the trail? Judge a rule on THIS one.

Measured 2026-08-24: 211 as-known, 139 physics — so a third of the error the bench used
to charge propagation rules for was never propagation at all.

NON-GATING diagnostic.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
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


def _own_spill_sources(payload: dict) -> dict[tuple[int, int], int]:
    """Sources the grounding admits from THIS spill, by its own rule.

    A deliberate copy of the scan in `grounding_flow.falling_sources`, kept here rather
    than imported because the captures freeze the grounding's OUTPUT, not the animations
    it read — so a capture cannot be re-grounded, only re-scanned."""
    pieces = {tuple(c) for p in payload["pieces"] for c in p}
    dr, dc = payload["direction"]
    seen: set[tuple[int, int]] = set()
    tick = -1
    out: dict[tuple[int, int], int] = {}
    for layer in ([tuple(c) for c in raw] for raw in payload["observed"]):
        if not layer:
            continue
        tick += 1
        kept_here: set[tuple[int, int]] = set()
        deferred: list[tuple[int, int]] = []
        for (r, c) in layer:
            behind = (r - dr, c - dc)
            flanks = ((r - dc, c - dr), (r + dc, c + dr))
            if behind in seen or any(f in seen for f in flanks):
                continue
            if behind in pieces:
                deferred.append((r, c))
                continue
            out[(c if dr else r, r if dr else c)] = tick
            kept_here.add((r, c))
        for (r, c) in deferred:
            if any(f in kept_here for f in ((r - dc, c - dr), (r + dc, c + dr))):
                out[(c if dr else r, r if dr else c)] = tick
        seen |= set(layer)
    return out


def _error(board: Board, payload: dict) -> int:
    pred = {c for layer in predict(board, ORACLE).frontier for c in layer}
    obs = {tuple(c) for layer in payload["observed"] for c in layer}
    return len(pred - obs) + len(obs - pred)


def _sweep() -> int:
    # idx0 FIRST, and it is the one that matters: it is the level the contract, the oracle
    # gate and the mutant table are all built on, and the model reproduces its spill cell
    # for cell. A rule was once adopted for halving the rest of this sweep and took the
    # live gate to 0/3 — the sweep could not see it, because idx0 was not in it.
    # idx0's capture lives WITH the round, not in the scratchpad, because the scratchpad
    # is ignored and a contract board that does not survive the session guards nothing.
    here = Path(__file__).resolve().parent / "evidence"
    captures = (sorted(here.glob("idx0*.json"))
                + sorted(Path("scratchpad").glob("r98_idx3_*.json")))
    if not captures:
        print("no captures under scratchpad/r98_idx3_*.json")
        return 1
    known = physics = 0
    print(f"{'board':8s} {'as-known':>9s} {'physics':>8s}")
    for path in captures:
        with open(path) as f:
            payload = json.load(f)
        board = _board(payload)
        a = _error(board, payload)
        own = _own_spill_sources(payload)
        # the scan counts ticks from the spill's own first layer; the frozen sources
        # count from the replay's. Line them up on the earliest source they share.
        offset = (min(t for _, t, _ in board.falling_sources) - min(own.values())
                  if board.falling_sources and own else 0)
        merged = {(lane, line): t for lane, t, line in board.falling_sources}
        for key, t in own.items():
            merged.setdefault(key, t + offset)
        union = replace(board, falling_sources=tuple(
            (lane, t, line) for (lane, line), t in sorted(merged.items())))
        b = _error(union, payload)
        known += a
        physics += b
        mark = "  <- CONTRACT, must stay 0" if "idx0" in path.stem and (a or b) else ""
        print(f"{path.stem.split('_')[-1]:8s} {a:9d} {b:8d}{mark}")
    print(f"{'sum':8s} {known:9d} {physics:8d}")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        return _sweep()
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
