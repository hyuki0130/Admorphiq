"""R98 idx1 NON-GATING observation — how far does the harness carry to level 2?

Purpose
-------
The contract is criterion-level-ONLY (sp80 idx0), deliberately: R96's
"idx0 + idx1 in sequence" was a level-count coincidence, not a rule. But idx1 is
where the family's next burdens live — the board is rotated, so the per-action
deltas invert, and there is more than one movable piece — and knowing WHICH of
those the harness already absorbs is what makes the next expansion cheap.

This run gates nothing. It reports, per stage, whether the same pipeline that
cleared idx0 still grounds, verifies, plans and executes on idx1, and where it
stops.

Expected feedback
-----------------
A per-stage line. Any stage that fails names the next piece of work; a full clear
would be a bonus, not a contract result, and is recorded as such.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

from admorphiq.hypothesis_select import schema_flow as F  # noqa: E402
from admorphiq.hypothesis_select.compiler import PlanStatus  # noqa: E402
from admorphiq.hypothesis_select.compiler_flow import compile_flow_hypothesis  # noqa: E402
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding  # noqa: E402
from admorphiq.hypothesis_select.verifier_flow import verify_flow_instance  # noqa: E402

ACTIONS = {
    1: GameAction.ACTION1,
    2: GameAction.ACTION2,
    3: GameAction.ACTION3,
    4: GameAction.ACTION4,
    5: GameAction.ACTION5,
}


def _open_arcade():
    """Open the offline arcade, honouring ``ARC_ENVIRONMENTS_DIR``.

    The kwarg is passed ONLY when the variable is set: arc_agi treats an explicit
    ``environments_dir=None`` as "different from the default" and stops scanning
    altogether, so the tidy-looking ``or None`` form silently yields an arcade with
    zero environments.
    """
    envs_dir = os.environ.get("ARC_ENVIRONMENTS_DIR")
    return (
        Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=envs_dir)
        if envs_dir
        else Arcade(operation_mode=OperationMode.OFFLINE)
    )


def main() -> int:
    arcade = _open_arcade()
    gid = next(e.game_id for e in arcade.get_environments() if e.game_id.startswith("sp80"))
    env = arcade.make(gid)
    obs = env.step(GameAction.RESET)

    # clear idx0 with the certified path so idx1 is entered exactly as a live run
    # would enter it
    g0 = FlowGrounding()
    g0.observe(0, None, obs.frame)

    def act0(a: int):
        nonlocal obs
        obs = env.step(ACTIONS[a])
        g0.observe(a, None, obs.frame)

    for a in (1, 1, 2, 3, 4):
        act0(a)
    hint = g0.flow_origin_hint()
    if hint is not UNKNOWN and g0.tracked_region() is not UNKNOWN:
        target = max(c for _, c in hint.value)
        while max(c for _, c in g0.tracked_region().value) < target:
            act0(4)
    act0(5)
    plan0 = compile_flow_hypothesis(F.sp80_oracle_instance(), g0)
    for a in plan0.actions:
        act0(a)
        if obs.levels_completed >= 1:
            break
    if obs.levels_completed < 1:
        print("[setup] FAILED to reach idx1 — the idx0 path did not clear")
        return 1
    print("[setup] idx1 entered after clearing idx0\n")

    # a FRESH grounding for the new board: a level boundary replaces the layout
    g = FlowGrounding()
    g.observe(0, None, obs.frame)
    actions = 0
    commits = 0

    def act(a: int):
        nonlocal obs, actions, commits
        obs = env.step(ACTIONS[a])
        actions += 1
        if len(obs.frame) > 1:
            commits += 1
        g.observe(a, None, obs.frame)

    def act6(col: int, row: int):
        """Click the centre of a cell, in cell coordinates."""
        nonlocal obs, actions
        scale = g.scale()
        px = 4 if scale is UNKNOWN else scale.value
        obs = env.step(GameAction.ACTION6,
                       data={"x": col * px + px // 2, "y": row * px + px // 2})
        actions += 1
        g.observe(6, (col * px + px // 2, row * px + px // 2), obs.frame)

    for a in (1, 1, 2, 3, 4):
        act(a)

    # look for further movable pieces: click candidate regions until a selection
    # event fires, which reveals the idle appearance and with it the inventory
    probes = 0
    candidates = g.selection_candidates()
    if candidates is not UNKNOWN:
        for (cr, cc) in candidates.value[:4]:
            if g.idle_appearance_known():
                break
            act6(cc, cr)
            probes += 1

    # An unfamiliar board may run its flow in any direction, so the pre-commit
    # origin hint (which assumes the source is at the top) cannot be relied on.
    # Spend the FIRST commit unaimed: it reveals the flow's colour, its emitters
    # and its direction. Only then is aiming possible.
    act(5)
    aimed = False
    emitters = g.emitters()
    direction = g.initial_direction()
    if emitters is not UNKNOWN and direction is not UNKNOWN:
        dr, dc = direction.value
        lane = emitters.value[0][1] if dr != 0 else emitters.value[0][0]
        tracked = g.tracked_region()
        if tracked is not UNKNOWN:
            span = [c for _, c in tracked.value] if dr != 0 else [r for r, _ in tracked.value]
            step = 4 if lane > max(span) else 3
            guard = 0
            while guard < 16:
                cur = g.tracked_region().value
                have = [c for _, c in cur] if dr != 0 else [r for r, _ in cur]
                if min(have) <= lane <= max(have):
                    aimed = True
                    break
                act(step)
                guard += 1
        act(5)

    stages: list[tuple[str, bool, str]] = []

    deltas = g.piece_deltas()
    stages.append(("per-action deltas", deltas is not UNKNOWN,
                   str(sorted((a, (dr, dc)) for a, dr, dc in deltas.value))
                   if deltas is not UNKNOWN else "UNKNOWN"))

    pieces = g.pieces()
    stages.append(("piece inventory", pieces is not UNKNOWN and len(pieces.value) > 1,
                   f"{len(pieces.value)} piece(s), sizes "
                   f"{[len(cells) for _, cells in pieces.value]}"
                   if pieces is not UNKNOWN else "UNKNOWN"))
    stages.append(("idle appearance learned", g.idle_appearance_known(),
                   f"{probes} selection probe(s)"))
    stages.append(("flow direction learned", g.initial_direction() is not UNKNOWN,
                   f"{g.initial_direction().value if g.initial_direction() is not UNKNOWN else '-'}"
                   f", aimed={aimed}"))

    sinks = g.sink_candidates()
    stages.append(("target shortlist", sinks is not UNKNOWN and len(sinks.value) >= 3,
                   f"{len(sinks.value)} region(s)" if sinks is not UNKNOWN else "UNKNOWN"))

    board = g.board()
    stages.append(("board assembly", board is not UNKNOWN,
                   f"{len(board.value.sinks)} sinks, {len(board.value.piece_cells)} piece cells"
                   if board is not UNKNOWN else "UNKNOWN"))

    verdict = verify_flow_instance(F.sp80_oracle_instance(), g, False)
    stages.append((f"verifier ({verdict.verdict.value})",
                   verdict.verdict.value == "PASS", verdict.reason))

    plan = compile_flow_hypothesis(F.sp80_oracle_instance(), g)
    stages.append((f"compiler ({plan.status.value})",
                   plan.status is PlanStatus.SOLVABLE, plan.reason))

    cleared = False
    if plan.status is PlanStatus.SOLVABLE:
        for a in plan.actions:
            act(a)
            if obs.levels_completed >= 2:
                cleared = True
                break
    stages.append(("execution", cleared,
                   f"{actions} actions, {commits} commits, cleared={cleared}"))

    for name, ok, detail in stages:
        print(f"  {name:<24} {'ok  ' if ok else 'STOP'} {detail}")

    first_stop = next((n for n, ok, _ in stages if not ok), None)
    print("\n[idx1 observation] NON-GATING — "
          + ("the pipeline carries to idx1 and clears it (a bonus, not a contract result)"
             if cleared else f"the pipeline stops at: {first_stop}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
