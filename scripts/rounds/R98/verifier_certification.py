"""R98 verifier certification — the frozen mutant table judged on LIVE evidence.

Purpose
-------
The mutant table was certified earlier against the reference propagator directly.
This closes the loop end to end: drive the certified discovery sequence against the
live engine, ground it, and let the REAL verifier judge the oracle and all nine
mutants using only what the harness recovered — no colour constants, no board
handed in.

Expected feedback
-----------------
The oracle must PASS, and every mutant's verdict must equal the frozen expectation.
A disagreement blocks the live oracle gate: the verifier is what stops a wrong
hypothesis from executing, so a verifier that mislabels a mutant would let one run.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

from admorphiq.hypothesis_select import schema_flow as F  # noqa: E402
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding  # noqa: E402
from admorphiq.hypothesis_select.verifier_flow import (  # noqa: E402
    build_flow_evidence,
    verify_with_evidence,
)

ACTIONS = {
    1: GameAction.ACTION1,
    2: GameAction.ACTION2,
    3: GameAction.ACTION3,
    4: GameAction.ACTION4,
    5: GameAction.ACTION5,
}


def run_discovery() -> tuple[FlowGrounding, bool]:
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=os.environ.get("ARC_ENVIRONMENTS_DIR") or None,
    )
    gid = next(e.game_id for e in arcade.get_environments() if e.game_id.startswith("sp80"))
    env = arcade.make(gid)
    obs = env.step(GameAction.RESET)
    g = FlowGrounding()
    g.observe(0, None, obs.frame)

    def act(a: int):
        nonlocal obs
        obs = env.step(ACTIONS[a])
        g.observe(a, None, obs.frame)

    for a in (1, 1, 2, 3, 4):
        act(a)
    hint = g.flow_origin_hint()
    if hint is not UNKNOWN and g.tracked_region() is not UNKNOWN:
        target = max(c for _, c in hint.value)
        while max(c for _, c in g.tracked_region().value) < target:
            act(4)
    act(5)
    return g, obs.levels_completed >= 1


def main() -> int:
    g, advanced = run_discovery()
    evidence = build_flow_evidence(g, advanced)
    if evidence.board is None:
        print("[verifier] FAIL — grounding produced no board to judge against")
        return 1

    print(f"evidence: {len(evidence.trajectory)} trajectory steps, "
          f"{evidence.n_sinks} sinks, level advanced: {evidence.advanced}\n")

    oracle_verdict = verify_with_evidence(F.sp80_oracle_instance(), evidence)
    ok = oracle_verdict.verdict.value == "PASS"
    print(f"  {'oracle':<30} expected PASS          got {oracle_verdict.verdict.value:<13} "
          f"{'PASS' if ok else 'FAIL'}")
    print(f"       {oracle_verdict.reason}")

    for m in F.MUTANTS_FLOW:
        got = verify_with_evidence(m.instance, evidence)
        good = got.verdict is m.expected_verdict
        ok &= good
        print(f"  {m.name:<30} expected {m.expected_verdict.value:<13} "
              f"got {got.verdict.value:<13} {'PASS' if good else 'FAIL'}")
        if not good:
            print(f"       {got.reason}")

    print(f"\n[verifier] {'PASS' if ok else 'FAIL'} — the verifier "
          f"{'reproduces' if ok else 'DISAGREES WITH'} the frozen table on live "
          f"grounded evidence")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
