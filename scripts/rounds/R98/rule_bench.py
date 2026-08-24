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

`--rows` breaks the physics column down by board row and `--where` by what the surplus
cell is, how far it sits from the real trail and which way it lies from it. Between them
the residual gets attributed to a mechanism rather than left as a total.

Measured 2026-08-25: 209 as-known, 108 physics — half the error the bench used to charge
propagation rules for was never propagation at all. (An earlier reading of 211/139 is
superseded by the rules adopted since.) The 108 is ENTIRELY invented cells, zero missed,
so the model's trail is a strict superset of the engine's on every capture: it never
fails to reach something the engine reaches, it only adds.

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


def _where() -> int:
    """What the surplus IS: the cell it occupies, how far it sits from the real trail,
    and whether it lies along the flow or across it.

    Purpose: a row breakdown says where the residual is on the board; this says which
    MECHANISM could produce it. Over-running a stream and over-spreading one are
    different rules with different fixes, and a total cannot tell them apart.

    Expected feedback: surplus hugging the trail across the flow accuses the spread
    rules; surplus along the flow accuses the run length; surplus far from any
    observed cell accuses an invented source."""
    kind: dict[str, int] = {}
    dist: dict[int, int] = {}
    axis: dict[str, int] = {}
    for path in _captures():
        with open(path) as f:
            payload = json.load(f)
        board = _union_board(_board(payload), payload)
        pred = {c for layer in predict(board, ORACLE).frontier for c in layer}
        obs = {tuple(c) for layer in payload["observed"] for c in layer}
        dr, dc = board.direction
        for cell in pred - obs:
            if board.sink_of(cell) is not None:
                name = "sink cell"
            elif cell in board.absorber_cells:
                name = "absorber cell"
            elif board.piece_at(cell) is not None:
                name = "piece cell"
            elif cell in board.hazard_cells:
                name = "hazard cell"
            else:
                name = "empty cell"
            kind[name] = kind.get(name, 0) + 1
            if not obs:
                continue
            near = min(obs, key=lambda o: abs(cell[0] - o[0]) + abs(cell[1] - o[1]))
            d = abs(cell[0] - near[0]) + abs(cell[1] - near[1])
            dist[d] = dist.get(d, 0) + 1
            along = abs((cell[0] - near[0]) * dr + (cell[1] - near[1]) * dc)
            across = abs((cell[0] - near[0]) * dc + (cell[1] - near[1]) * dr)
            where = ("across the flow" if across and not along else
                     "along the flow" if along and not across else
                     "diagonal" if along and across else "on it")
            axis[where] = axis.get(where, 0) + 1
    print("what the surplus cell is")
    for name, n in sorted(kind.items(), key=lambda kv: -kv[1]):
        print(f"  {name:16s} {n:4d}")
    print("manhattan distance to the nearest observed cell")
    for d in sorted(dist):
        print(f"  d={d:<3d}{'':11s} {dist[d]:4d}")
    print("which way it lies from that cell")
    for where, n in sorted(axis.items(), key=lambda kv: -kv[1]):
        print(f"  {where:16s} {n:4d}")
    return 0


def _rows() -> int:
    """The physics column broken down by board row.

    Purpose: a total cannot say WHERE a propagation rule is wrong. idx3's frame is a
    window onto a taller level, so an error clustered against the window's truncated
    edge would be a perception artefact rather than a propagation one; an error spread
    across the trail would be the propagator. This decides between them.

    Expected feedback: rows 0-3 are the truncated edge. Cells there mean the residual
    is the window; cells elsewhere mean it is the propagation."""
    invented: dict[int, int] = {}
    missed: dict[int, int] = {}
    for path in _captures():
        with open(path) as f:
            payload = json.load(f)
        board = _union_board(_board(payload), payload)
        pred = {c for layer in predict(board, ORACLE).frontier for c in layer}
        obs = {tuple(c) for layer in payload["observed"] for c in layer}
        for r, _ in pred - obs:
            invented[r] = invented.get(r, 0) + 1
        for r, _ in obs - pred:
            missed[r] = missed.get(r, 0) + 1
    print(f"{'row':>4} {'invented':>9} {'missed':>7}")
    for r in sorted(set(invented) | set(missed)):
        print(f"{r:>4} {invented.get(r, 0):>9} {missed.get(r, 0):>7}")
    total = sum(invented.values()) + sum(missed.values())
    edge = sum(invented.get(r, 0) + missed.get(r, 0) for r in range(4))
    print(f"{'sum':>4} {sum(invented.values()):>9} {sum(missed.values()):>7}")
    print(f"the window's truncated edge (rows 0-3): {edge} of {total}")
    return 0


def _captures() -> list[Path]:
    """idx0 FIRST, and it is the one that matters: it is the level the contract, the
    oracle gate and the mutant table are all built on, and the model reproduces its
    spill cell for cell. A rule was once adopted for halving the rest of this sweep and
    took the live gate to 0/3 — the sweep could not see it, because idx0 was not in it.
    idx0's capture lives WITH the round, not in the scratchpad, because the scratchpad
    is ignored and a contract board that does not survive the session guards nothing."""
    here = Path(__file__).resolve().parent / "evidence"
    # idx0 first, then the CROSS-LEVEL boards, then the idx3 family. Until the capture
    # hook was fixed every board here came from idx3 and only from a level that had just
    # failed, so a rule could be judged on one level's geometry and reported as judged on
    # the game. idx1 and idx2 are levels the walk CLEARS, and they live with the round
    # rather than in the scratchpad because evidence that does not survive the session
    # cannot be re-measured against.
    # ⛔ evidence/cross_idx*.json are EXCLUDED and must stay excluded until the capture
    # site is corrected. They pair a board with a spill that ran on a different layout:
    # measured, the engine's flow passes through 1 of 1, 2 of 3 and 3 of 4 of their pieces,
    # while across the contract board and all seventeen idx3 boards it passes through ZERO
    # of five. The clearing-level capture is taken before the final plan step executes, so
    # the layout that spilled is not the layout recorded. The files stay in the round so
    # the next attempt starts from the known state instead of rediscovering it.
    return (sorted(here.glob("idx0.json"))
            + sorted(Path("scratchpad").glob("r98_idx3_*.json")))


def _union_board(board: Board, payload: dict) -> Board:
    """The board with the sources the spill itself admits unioned onto what the
    grounding already knew — the physics column's input."""
    own = _own_spill_sources(payload)
    # the scan counts ticks from the spill's own first layer; the frozen sources
    # count from the replay's. Line them up on the earliest source they share.
    offset = (min(t for _, t, _ in board.falling_sources) - min(own.values())
              if board.falling_sources and own else 0)
    merged = {(lane, line): t for lane, t, line in board.falling_sources}
    for key, t in own.items():
        merged.setdefault(key, t + offset)
    return replace(board, falling_sources=tuple(
        (lane, t, line) for (lane, line), t in sorted(merged.items())))


def _sweep() -> int:
    # idx0 FIRST, and it is the one that matters: it is the level the contract, the oracle
    # gate and the mutant table are all built on, and the model reproduces its spill cell
    # for cell. A rule was once adopted for halving the rest of this sweep and took the
    # live gate to 0/3 — the sweep could not see it, because idx0 was not in it.
    # idx0's capture lives WITH the round, not in the scratchpad, because the scratchpad
    # is ignored and a contract board that does not survive the session guards nothing.
    captures = _captures()
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
        b = _error(_union_board(board, payload), payload)
        known += a
        physics += b
        # ONLY evidence/idx0.json is the contract board. The cross-level captures are
        # also idx0 in part, and marking them would put the contract's name on boards the
        # gate has never been run against.
        mark = "  <- CONTRACT, must stay 0" if path.stem == "idx0" and (a or b) else ""
        print(f"{path.stem.split('_')[-1]:8s} {a:9d} {b:8d}{mark}")
    print(f"{'sum':8s} {known:9d} {physics:8d}")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--where":
        return _where()
    if len(sys.argv) > 1 and sys.argv[1] == "--rows":
        return _rows()
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
