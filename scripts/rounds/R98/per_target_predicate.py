"""Is `sink_response_predicate` GLOBAL where one board needs it PER-TARGET?

Purpose: R98's closing measurement recorded that idx3's four notchless cells are exactly
`absorber_cells`, that `contact` would win 14033 layouts there, and that `contact` is
CONTRADICTED on idx0 — so the gap is not a missing rule but a predicate applied uniformly
where one board wants it per target. This replays the FIXED captures under each predicate
and reports the replay error, so the question is decided on evidence that does not move.

Expected feedback: if the two predicates give the SAME error on every capture, the axis is
data-indistinguishable here and "14033 layouts" was about a hypothetical the evidence never
exercises — per-target would be unfalsifiable and must not be added. If they differ, the
board and direction of the difference say exactly which target wants which predicate, and
that is the case for widening the schema.

Reuses `rule_bench._board` and `_error` rather than rebuilding them: the board assembly has
already been got wrong once by hand (falling_sources are (row, col0, col1) triples, not cell
lists), and one implementation is the rule.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[2] / "src"))

_spec = importlib.util.spec_from_file_location("_rule_bench", _HERE / "rule_bench.py")
_rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rb)

from admorphiq.hypothesis_select.propagate_flow import ORACLE, predict  # noqa: E402

_PREDICATES = ("same_sink_flanks", "contact")


def _replay_error(board, payload: dict, predicate: str) -> int:
    """Cells the model invents plus cells it misses, under one predicate."""
    table = replace(ORACLE, sink_predicate=predicate)
    pred = {c for layer in predict(board, table).frontier for c in layer}
    real = {tuple(c) for step in payload["observed"] for c in step}
    return len(pred - real) + len(real - pred)


def main() -> int:
    caps = sorted(_HERE.glob("evidence/walk_idx*.json"))
    if not caps:
        print("no captures — run depth_walk.py with R98_CAPTURE first")
        return 1
    print(f"{'capture':16s} {'sinks':>5s} " + "  ".join(f"{p:>16s}" for p in _PREDICATES))
    differing = 0
    for path in caps:
        payload = json.load(open(path))
        board = _rb._board(payload)
        errs = [_replay_error(board, payload, p) for p in _PREDICATES]
        mark = "  <-- DIFFER" if len(set(errs)) > 1 else ""
        differing += len(set(errs)) > 1
        print(f"{path.stem:16s} {len(payload['sinks']):5d} "
              + "  ".join(f"{e:16d}" for e in errs) + mark)
    print(f"\ncaptures where the predicate CHANGES the replay: {differing}/{len(caps)}")
    if differing == 0:
        print("=> the two predicates are data-indistinguishable on every captured board;")
        print("   per-target would be unfalsifiable here and must not be added.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
