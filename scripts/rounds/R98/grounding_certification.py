"""R98 grounding certification — can the harness earn the measured slots live?

Purpose
-------
Grounding was pre-declared the dominant risk of this round (~40%): every
downstream stage reasons about entities the harness must first recover from
observation alone. This script drives the CERTIFIED discovery sequence against the
live engine, feeds every observation to :class:`FlowGrounding`, and compares each
recovered slot to the decoded ground truth.

Nothing game-specific is passed in: no colours, no coordinates, no game id. The
scale, the flow colour, the piece, the per-action deltas, the emitters, the
initial direction, the sink shortlist and the trajectory are all earned from the
frames the discovery actions produce.

Expected feedback
-----------------
A PASS line per slot. A FAIL means the harness cannot supply that slot at the
criterion level, which is the pre-declared falsification: the round pivots to
grounding work rather than to schema or model changes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding  # noqa: E402
from admorphiq.hypothesis_select.schema_flow import sp80_oracle_instance  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_propagator import ORACLE, predict, read_board  # noqa: E402

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

    entry_layer = [[int(v) for v in row] for row in obs.frame[0]]
    g = FlowGrounding()
    g.observe(0, None, obs.frame)

    def act(a: int, xy=None):
        nonlocal obs
        obs = env.step(ACTIONS[a], data={"x": xy[0], "y": xy[1]}) if xy else env.step(ACTIONS[a])
        g.observe(a, xy, obs.frame)

    # the certified discovery sequence: probe the four directions (with a blocked
    # contrast at the bound), return to the entry placement, then aim the
    # sacrificial commit using the pre-commit origin hint
    for a in (1, 1, 2, 3, 4):
        act(a)

    hint = g.flow_origin_hint()
    tracked = g.tracked_region()
    aligned = 0
    if hint is not UNKNOWN and tracked is not UNKNOWN:
        target = max(c for _, c in hint.value)
        while aligned < 16 and max(c for _, c in g.tracked_region().value) < target:
            act(4)
            aligned += 1
    act(5)

    oracle = sp80_oracle_instance().transition_model
    checks: list[tuple[str, bool, str]] = []

    def show(v):
        return "UNKNOWN" if v is UNKNOWN else f"{v.value} ({v.confidence})"

    scale = g.scale()
    checks.append(("scale", scale is not UNKNOWN and scale.value == 4, show(scale)))

    commit = g.commit_action()
    checks.append(("commit_action", commit is not UNKNOWN
                   and commit.value == oracle.commit_action, show(commit)))

    # control_mode is an UNESTABLISHED PREMISE at this level: with a single
    # pre-selected piece a click produces no frame change, so the two modes are
    # behaviourally identical. The harness passes by SAYING SO, not by guessing.
    mode = g.control_mode()
    indistinguishable = g.control_mode_indistinguishable()
    mode_ok = (mode is not UNKNOWN and mode.value == oracle.control_mode) or (
        indistinguishable
        and mode is not UNKNOWN
        and mode.confidence == "low"
        and "control_mode" in oracle.unestablished_premises
    )
    checks.append(("control_mode", mode_ok,
                   f"{show(mode)}; indistinguishable at this level: {indistinguishable}"))

    deltas = g.piece_deltas()
    want = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
    got = {a: (dr, dc) for a, dr, dc in deltas.value} if deltas is not UNKNOWN else {}
    checks.append(("piece_deltas", got == want, str(sorted(got.items()))))

    pieces = g.pieces()
    piece_ok = pieces is not UNKNOWN and len(pieces.value) == 1 and len(pieces.value[0][1]) == 5
    checks.append(("piece footprint", piece_ok,
                   str(pieces.value[0][1]) if pieces is not UNKNOWN else "UNKNOWN"))

    emitters = g.emitters()
    checks.append(("emitters", emitters is not UNKNOWN and len(emitters.value) == 1,
                   show(emitters)))

    direction = g.initial_direction()
    checks.append(("initial_direction", direction is not UNKNOWN
                   and direction.value == oracle.initial_direction, show(direction)))

    sinks = g.sink_candidates()
    checks.append(("sink shortlist", sinks is not UNKNOWN and len(sinks.value) == 2,
                   str([name for name, _ in sinks.value]) if sinks is not UNKNOWN else "UNKNOWN"))

    # the strongest available check: the recovered trajectory must equal what the
    # oracle response table PREDICTS for the placement that was actually committed
    traj = g.trajectory()
    if traj is UNKNOWN:
        checks.append(("trajectory", False, "UNKNOWN"))
    else:
        board = read_board(entry_layer).moved(0, aligned)
        predicted = [f for f in predict(board, ORACLE).frontier if f]
        got = [list(f) for f in traj.value if f]
        n = min(len(predicted), len(got))
        same = [list(f) for f in predicted[:n]] == got[:n] and abs(len(predicted) - len(got)) <= 1
        checks.append(("trajectory vs prediction", same,
                       f"{len(got)} recovered vs {len(predicted)} predicted steps"))

    ev = g.placement_evidence()
    ev_ok = ev is not UNKNOWN and len(ev.value["blocked_contrasts"]) >= 1
    checks.append(("blocked contrast", ev_ok,
                   f"{len(ev.value['blocked_contrasts'])} contrast(s), "
                   f"{ev.value['unattributed_noops']} unattributed no-op(s)"
                   if ev is not UNKNOWN else "UNKNOWN"))

    for name, ok, detail in checks:
        print(f"  {name:<20} {'PASS' if ok else 'FAIL':<5} {detail}")
    all_ok = all(ok for _, ok, _ in checks)
    print(f"\n[grounding] {'PASS' if all_ok else 'FAIL'} — the harness "
          f"{'earns' if all_ok else 'CANNOT earn'} every measured slot from "
          f"observation alone at the criterion level")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
