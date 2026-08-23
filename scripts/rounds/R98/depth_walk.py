"""R98 depth walk — how far does one hypothesis carry, and where does it stop?

Purpose
-------
The contract's criterion level is idx0 alone, and idx1 already clears as a bonus.
This walks consecutive levels with the SAME hypothesis and the same harness,
reporting per level whether grounding, verification, planning and execution
succeed. It gates nothing; its job is to name the next wall precisely rather than
to claim depth.

Each level is entered fresh: a level boundary replaces the layout, so grounding is
rebuilt from scratch, the pieces are re-inventoried, and the flow's direction is
re-learned. Nothing is carried across except the hypothesis itself.

Expected feedback
-----------------
A line per level ending in the stage that stopped it. A level that clears is a
bonus; a level that stops names the next piece of work. Either is usable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction, GameState  # noqa: E402

from admorphiq.hypothesis_select import schema_flow as F  # noqa: E402
from admorphiq.hypothesis_select.compiler import PlanStatus  # noqa: E402
from admorphiq.hypothesis_select.compiler_flow import (  # noqa: E402
    Select,
    compile_flow_hypothesis,
)
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding  # noqa: E402
from admorphiq.hypothesis_select.verifier_flow import verify_flow_instance  # noqa: E402

ACTIONS = {
    1: GameAction.ACTION1,
    2: GameAction.ACTION2,
    3: GameAction.ACTION3,
    4: GameAction.ACTION4,
    5: GameAction.ACTION5,
}
MAX_LEVELS = 6
# Per level, deliberately generous: this walk measures REACH, not efficiency. A
# layout that needs four pieces moved ten cells each costs dozens of actions and
# would score badly on the efficiency metric — that is a separate question from
# whether the pipeline can solve the board at all.
ACTION_BUDGET = 250


def _open_arcade():
    envs_dir = os.environ.get("ARC_ENVIRONMENTS_DIR")
    return (
        Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=envs_dir)
        if envs_dir
        else Arcade(operation_mode=OperationMode.OFFLINE)
    )


class Walker:
    def __init__(self) -> None:
        arcade = _open_arcade()
        gid = next(e.game_id for e in arcade.get_environments()
                   if e.game_id.startswith("sp80"))
        self.env = arcade.make(gid)
        self.obs = self.env.step(GameAction.RESET)
        self.actions = 0

    @property
    def level(self) -> int:
        return self.obs.levels_completed

    @property
    def alive(self) -> bool:
        return self.obs.state is not GameState.GAME_OVER

    def act(self, a: int, g: FlowGrounding) -> None:
        self.obs = self.env.step(ACTIONS[a])
        self.actions += 1
        g.observe(a, None, self.obs.frame)

    def click(self, cell, g: FlowGrounding) -> None:
        scale = g.scale()
        px = 4 if scale is UNKNOWN else scale.value
        row, col = cell
        xy = (col * px + px // 2, row * px + px // 2)
        self.obs = self.env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
        self.actions += 1
        g.observe(6, xy, self.obs.frame)

    def run(self, step, g: FlowGrounding) -> None:
        self.click(step.cell, g) if isinstance(step, Select) else self.act(step, g)


def describe_board(g: FlowGrounding) -> str:
    """A one-line summary of the board grounding is actually looking at.

    Reads through grounding rather than off a raw frame: a level boundary arrives
    as a multi-layer observation whose first layers still show the PREVIOUS board,
    so a diagnostic that reaches for layer zero describes the wrong level with
    complete confidence."""
    view = g.board_view()
    if view is UNKNOWN:
        return "no board yet"
    cells = view.value
    size = int(round(len(cells) ** 0.5))
    return f"{size}x{size}, {len(set(cells.values()))} distinct appearances"


def play_level(w: Walker) -> tuple[bool, str]:
    """Ground, verify, plan and execute one level. Returns (cleared, stage note)."""
    entered = w.level
    spent = w.actions
    g = FlowGrounding()
    g.observe(0, None, w.obs.frame)

    for a in (1, 1, 2, 3, 4):
        w.act(a, g)

    # A direction can come back unmeasured simply because the piece was against a
    # bound when it was tried. Retry the missing ones from wherever it is now: an
    # unmeasured direction is not neutral, it removes every placement that needs it
    # from the planner's reach.
    for a in (1, 2, 3, 4):
        if a in deltas_of(g):
            continue
        w.act(a, g)

    # Probe until the idle appearance is known, then keep probing the remaining
    # candidates: selecting a piece is what separates it from a neighbour it touches,
    # and a planner that can only move a merged pair cannot solve a board that needs
    # them placed independently.
    probes = 0
    candidates = g.selection_candidates()
    if candidates is not UNKNOWN:
        for cell in candidates.value[:6]:
            w.click(cell, g)
            probes += 1

    w.act(5, g)  # an unaimed commit reveals the flow's colour, source and direction
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

    if g.board() is UNKNOWN:
        return False, f"grounding incomplete (pieces={_count(g.pieces())}, " \
                      f"targets={_count(g.sink_candidates())})"

    hypothesis = F.sp80_oracle_instance()
    verdict = verify_flow_instance(hypothesis, g, w.level > entered)
    if verdict.verdict.value != "PASS":
        return False, f"verifier {verdict.verdict.value}: {verdict.reason}"

    plan = compile_flow_hypothesis(hypothesis, g)
    if plan.status is not PlanStatus.SOLVABLE:
        return False, f"compiler {plan.status.value}: {plan.reason}"

    # Every emitted move is CONFIRMED against the next frame. A plan that keeps
    # going after a move failed to land builds a layout nobody planned, and the
    # spill that follows tells you nothing about the hypothesis — the R96 rule,
    # applied here because idx3 was silently ending up cells away from its plan.
    # Compared as an unordered MULTISET of footprints, never by name: pieces are
    # reported in board order, so moving one renames several and an identity-based
    # check reports phantom movement.
    expected = _footprints(g)
    for index, step in enumerate(plan.steps):
        if w.actions - spent >= ACTION_BUDGET or not w.alive:
            break
        w.run(step, g)
        if w.level > entered:
            return True, f"cleared in {w.actions - spent} actions ({probes} selection probes)"
        if isinstance(step, Select) or index == len(plan.steps) - 1:
            continue
        delta = deltas_of(g).get(step)
        if delta is None:
            continue
        actual = _footprints(g)
        if actual == expected:
            return False, f"move {index} ({step}) did not land: the board is unchanged"
        # A moved piece can come to rest against a neighbour and MERGE with it, so a
        # footprint-for-footprint comparison sees more than one change. The question
        # that survives that is simpler: does translating exactly one of the pieces
        # by the measured delta reproduce the board we now see?
        if not _explained_by_one_move(expected, actual, delta):
            return False, (
                f"move {index} ({step}) is not explained by moving one piece by "
                f"{delta}: {len(expected)} footprint(s) before, {len(actual)} after"
            )
        expected = actual
    return False, f"executed the plan without clearing ({w.actions - spent} actions)"


def _explained_by_one_move(before: list, after: list, delta) -> bool:
    """True when translating ONE piece by ``delta`` turns ``before`` into ``after``.

    Compared as multisets of cell sets, so merges and renames do not matter — what
    matters is whether the board that appeared is the board the move should have
    produced."""
    target = sorted(after, key=min)
    for i in range(len(before)):
        moved = frozenset((r + delta[0], c + delta[1]) for (r, c) in before[i])
        candidate = sorted(before[:i] + [moved] + before[i + 1:], key=min)
        if candidate == target:
            return True
        # the moved piece may now share a region with a neighbour
        merged = set()
        for piece in candidate:
            merged |= set(piece)
        if merged == set().union(*target) if target else False:
            return True
    return False


def _footprints(g: FlowGrounding) -> list:
    """Every piece as a bare footprint, order and naming discarded."""
    inventory = g.pieces()
    if inventory is UNKNOWN:
        return []
    return sorted((frozenset(cells) for _, cells in inventory.value), key=min)


def deltas_of(g: FlowGrounding) -> dict:
    table = g.piece_deltas()
    return {} if table is UNKNOWN else {a: (dr, dc) for a, dr, dc in table.value}


def _count(q) -> str:
    return "?" if q is UNKNOWN else str(len(q.value))


def main() -> int:
    w = Walker()
    print(f"budget {ACTION_BUDGET} actions/level, up to {MAX_LEVELS} levels\n")
    cleared = 0
    for i in range(MAX_LEVELS):
        if not w.alive:
            print(f"  idx{i}: game over before the level could be played")
            break
        entered = w.level
        ok, note = play_level(w)
        print(f"  idx{i}: {'CLEARED' if ok else 'stopped'} — {note}")
        if not ok:
            break
        cleared += 1
        if w.level == entered:
            break
    print(f"\n[depth walk] NON-GATING — one hypothesis carried {cleared} level(s); "
          f"{w.actions} actions total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
