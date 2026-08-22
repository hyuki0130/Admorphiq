"""R98 LIVE ORACLE GATE — the whole pipeline, end to end, on the real engine.

Purpose
-------
The contract's gate: with the hand-authored oracle hypothesis standing in for the
model, does discovery -> grounding -> verification -> compilation -> execution
actually clear the criterion level, inside the frozen budget, three times out of
three? Everything downstream of this (the paired model substages) is only
meaningful once the harness itself is proven to work.

Nothing game-specific is supplied. The harness earns the board from probes, the
verifier judges the hypothesis against the recovered trajectory, and the compiler
plans using the hypothesis's OWN response table as its simulator.

Expected feedback
-----------------
Three runs, each reporting the verdict, the plan, the action count and whether the
level advanced. 3/3 passes the gate. A failure attributable to grounding is the
pre-declared falsification and pivots the round to grounding work rather than to
schema or model changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

from admorphiq.hypothesis_select import schema_flow as F  # noqa: E402
from admorphiq.hypothesis_select.compiler import PlanStatus  # noqa: E402
from admorphiq.hypothesis_select.compiler_flow import compile_flow_hypothesis  # noqa: E402
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding  # noqa: E402
from admorphiq.hypothesis_select.schema import Verdict  # noqa: E402
from admorphiq.hypothesis_select.verifier_flow import (  # noqa: E402
    build_flow_evidence,
    verify_flow_instance,
)

ACTIONS = {
    1: GameAction.ACTION1,
    2: GameAction.ACTION2,
    3: GameAction.ACTION3,
    4: GameAction.ACTION4,
    5: GameAction.ACTION5,
}
ACTION_CAP = 20
COMMIT_CAP = 3


class Run:
    def __init__(self) -> None:
        arcade = Arcade(operation_mode=OperationMode.OFFLINE)
        gid = next(e.game_id for e in arcade.get_environments()
                   if e.game_id.startswith("sp80"))
        self.env = arcade.make(gid)
        self.obs = self.env.step(GameAction.RESET)
        self.g = FlowGrounding()
        self.g.observe(0, None, self.obs.frame)
        self.actions = 0
        self.commits = 0

    def act(self, a: int) -> None:
        self.obs = self.env.step(ACTIONS[a])
        self.actions += 1
        if len(self.obs.frame) > 1:
            self.commits += 1
        self.g.observe(a, None, self.obs.frame)

    @property
    def cleared(self) -> bool:
        return self.obs.levels_completed >= 1


def one_run(index: int) -> bool:
    r = Run()

    # discovery: probe the four directions with a blocked contrast, aim with the
    # pre-commit origin hint, then spend ONE sacrificial commit
    for a in (1, 1, 2, 3, 4):
        r.act(a)
    hint = r.g.flow_origin_hint()
    if hint is not UNKNOWN and r.g.tracked_region() is not UNKNOWN:
        target = max(c for _, c in hint.value)
        while max(c for _, c in r.g.tracked_region().value) < target:
            r.act(4)
    r.act(5)
    discovery_actions = r.actions

    oracle = F.sp80_oracle_instance()
    verdict = verify_flow_instance(oracle, r.g, r.cleared)
    evidence = build_flow_evidence(r.g, r.cleared)

    plan = compile_flow_hypothesis(oracle, r.g)
    executed = 0
    if plan.status is PlanStatus.SOLVABLE:
        for a in plan.actions:
            if r.actions >= ACTION_CAP or r.commits >= COMMIT_CAP:
                break
            r.act(a)
            executed += 1
            if r.cleared:
                break

    ok = (
        verdict.verdict is Verdict.PASS
        and plan.status is PlanStatus.SOLVABLE
        and r.cleared
        and r.actions <= ACTION_CAP
        and r.commits <= COMMIT_CAP
    )
    print(f"  run {index}: verdict={verdict.verdict.value} "
          f"plan={plan.status.value} offset={plan.offset} "
          f"actions={r.actions} (discovery {discovery_actions} + plan {executed}) "
          f"commits={r.commits} cleared={r.cleared} -> {'PASS' if ok else 'FAIL'}")
    if not ok:
        print(f"       verifier: {verdict.reason}")
        print(f"       compiler: {plan.reason}")
        print(f"       evidence: {len(evidence.trajectory)} steps, "
              f"{evidence.n_sinks} sinks")
    return ok


def main() -> int:
    print(f"contract: <= {ACTION_CAP} cumulative actions, <= {COMMIT_CAP} commits, "
          f"3/3 required\n")
    results = [one_run(i + 1) for i in range(3)]
    passed = sum(results)
    print(f"\n[oracle gate] {passed}/3 — "
          f"{'PASS' if passed == 3 else 'FAIL'}")
    return 0 if passed == 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
