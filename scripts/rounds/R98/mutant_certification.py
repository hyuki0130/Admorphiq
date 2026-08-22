"""R98 mutant certification — the schema's verdict table vs the measured engine.

Purpose
-------
Codex binding correction 5 asked that every mutant be pre-certified against exact
observed transitions rather than asserted. The schema ships a frozen table of
expected verdicts; this script proves each one by running the mutant's response
table through the reference propagator and comparing its predictions to the
oracle's across every reachable placement:

* a mutant the schema calls CONTRADICTED must diverge somewhere;
* a mutant the schema calls UNKNOWN must diverge NOWHERE — otherwise the schema
  is understating what the criterion level can separate, which is its own defect.

Objective-axis mutants are checked against the recorded live outcomes instead,
since they change the win predicate rather than the trajectory.

Expected feedback
-----------------
A per-mutant PASS/FAIL line. Any FAIL blocks the freeze: it means the frozen
verdict table and the measured mechanics disagree, and the table is the thing the
model will be scored against.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402
from reference_propagator import ORACLE, ResponseTable, predict, read_board  # noqa: E402

from admorphiq.hypothesis_select import schema_flow as F  # noqa: E402
from admorphiq.hypothesis_select.schema import Verdict  # noqa: E402

PLACEMENTS = range(-3, 9)


def _table_from_schema(inst: F.FlowHypothesis) -> ResponseTable:
    """Project a schema instance onto the propagator's response table."""
    tm = inst.transition_model
    (_, piece), = tm.responses.piece_by_class
    own_flow = tm.responses.own_flow
    boundary = tm.responses.boundary
    return ResponseTable(
        piece_spawn=piece.spawn,
        piece_direction=piece.direction,
        piece_propagation=piece.propagation,
        sink_predicate=tm.responses.sink.predicate,
        sink_miss=tm.responses.sink.miss,
        hazard=tm.responses.hazard,
        own_flow=ORACLE.own_flow if own_flow == F.UNKNOWN else own_flow,
        boundary=ORACLE.boundary if boundary == F.UNKNOWN else boundary,
    )


def main() -> int:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    gid = next(e.game_id for e in arcade.get_environments() if e.game_id.startswith("sp80"))
    env = arcade.make(gid)
    entry = read_board(env.step(GameAction.RESET).frame[0])

    base = {dx: predict(entry.moved(0, dx), ORACLE) for dx in PLACEMENTS}

    def traj(p):
        return [f for f in p.frontier if f]

    ok = True
    print("mutant                          axis        expected      measured    result")
    for m in F.MUTANTS_FLOW:
        if m.axis == "objective":
            # the objective changes the win predicate, not the trajectory
            if isinstance(m.instance.objective, F.AnySinkCovered):
                # would any reachable placement satisfy `any` but not `all`?
                separates = any(0 < len(base[dx].satisfied) < len(entry.sinks)
                                for dx in PLACEMENTS)
            else:  # hazard policy neutral
                separates = any(base[dx].fatal and len(base[dx].satisfied) == len(entry.sinks)
                                for dx in PLACEMENTS)
        else:
            table = _table_from_schema(m.instance)
            separates = any(
                traj(predict(entry.moved(0, dx), table)) != traj(base[dx])
                or (predict(entry.moved(0, dx), table).wins != base[dx].wins)
                for dx in PLACEMENTS
            )

        measured = Verdict.CONTRADICTED if separates else Verdict.UNKNOWN
        good = measured is m.expected_verdict
        ok &= good
        print(f"  {m.name:<30} {m.axis:<11} {m.expected_verdict.value:<13} "
              f"{measured.value:<11} {'PASS' if good else 'FAIL'}")

    print(f"\n[mutant certification] {'PASS' if ok else 'FAIL'} — the frozen verdict "
          f"table {'matches' if ok else 'DISAGREES WITH'} the measured mechanics")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
