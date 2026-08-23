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
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding, _regions  # noqa: E402
from admorphiq.hypothesis_select.propagate_flow import ORACLE, predict
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
# How many times a level may be re-planned after a move fails to land.
REPLAN_LIMIT = 3
# Presses allowed while driving one piece to its planned place.
MOVE_ATTEMPTS = 12


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
        if not isinstance(step, Select):
            self.act(step, g)
            return
        self.click(_unambiguous_anchor(step, g), g)


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

    if os.environ.get("R98_DUMP_BOARD") == "1":
        _tally_target_colour(g)

    hypothesis = F.sp80_oracle_instance()
    verdict = verify_flow_instance(hypothesis, g, w.level > entered)
    if verdict.verdict.value != "PASS":
        return False, f"verifier {verdict.verdict.value}: {verdict.reason}"

    # Plan, execute with per-move confirmation, and REPLAN when a move does not land.
    # The board disagreeing with the plan is information, not a dead end: the engine
    # refuses placements for reasons the measured constraints do not always capture,
    # and a piece coming to rest against a neighbour changes what the inventory can
    # tell apart. Re-reading the board and planning again from what is actually there
    # is what an agent has to do anyway.
    attempts = 0
    note = "no plan"
    while attempts < REPLAN_LIMIT:
        attempts += 1
        plan = compile_flow_hypothesis(hypothesis, g)
        if os.environ.get("R98_DUMP_BOARD") == "1":
            known = g.sink_candidates()
            print(f"    [plan] targets known at plan time: "
                  f"{0 if known is UNKNOWN else len(known.value)} "
                  f"{[] if known is UNKNOWN else [sorted(c)[0] for _, c in known.value]}",
                  flush=True)
        if plan.status is not PlanStatus.SOLVABLE:
            if os.environ.get("R98_DUMP_BOARD") == "1":
                b = g.board().value
                print(f"    [board] pieces={[(sorted(x)[0], len(x)) for x in b.pieces]} "
                      f"sinks={len(b.sinks)} hazards={sorted(b.hazard_cells)} "
                      f"emergences={sorted(b.emergences)} dir={b.direction} "
                      f"standing={len(b.standing_flow)}", flush=True)
            return False, f"compiler {plan.status.value}: {plan.reason}"
        cleared, note, diverged = _execute(w, g, plan, entered, spent, probes)
        if cleared:
            return True, note
        if not diverged:
            return False, note
        if w.actions - spent >= ACTION_BUDGET or not w.alive:
            return False, f"{note}; out of budget"
    return False, f"{note}; gave up after {attempts} plans"


def _execute(w: Walker, g: FlowGrounding, plan, entered: int, spent: int, probes: int):
    """Realise a plan's LAYOUT, not its list of presses. Returns (cleared, note,
    diverged).

    A plan is a set of intended piece positions; the presses are one route to them.
    Executing the list literally means a single refused press leaves a piece one
    cell short with no way to notice, and the spill that follows is the one for a
    layout nobody chose — measured on the fourth level, where the plan ran to
    completion three cells away from what it intended and the model correctly
    predicted the failure that followed.

    So each Select states where its piece must END UP, and the driver presses toward
    that goal, re-reading the board between presses and stopping the moment it
    arrives.
    """
    held: Select | None = None
    for index, step in enumerate(plan.steps):
        if w.actions - spent >= ACTION_BUDGET or not w.alive:
            return False, f"out of budget at step {index}", False
        if isinstance(step, Select):
            # the piece just finished has to be WHERE IT WAS SENT before the next
            # one starts, or the layout that spills is not the one that was chosen
            arrived, note = _top_up(w, g, held, entered, spent)
            if w.level > entered:
                return True, f"cleared in {w.actions - spent} actions ({probes} selection probes)", False
            if not arrived:
                return False, note, True
            held = step
        if index == len(plan.steps) - 1:
            # the commit: the LAST piece has no successor to top it up, and a layout
            # that is one press short spills as a layout nobody chose
            arrived, note = _top_up(w, g, held, entered, spent)
            if w.level > entered:
                return True, f"cleared in {w.actions - spent} actions ({probes} probes)", False
            if not arrived:
                return False, note, True
        w.run(step, g)
        if w.level > entered:
            return True, f"cleared in {w.actions - spent} actions ({probes} selection probes)", False

    if os.environ.get("R98_DUMP_BOARD") == "1":
        want = frozenset(c for piece in plan.intended for c in piece)
        have = _all_pieces(g)
        print(f"    [layout] short by {len(want - have)} cell(s); missing "
              f"{sorted(want - have)}", flush=True)
        _attribute(g, plan)
        late = g.sink_candidates()
        print(f"    [targets] after the commit: "
              f"{[(sorted(c)[0], len(c)) for _, c in late.value]}", flush=True)
    return False, f"executed the plan without clearing ({w.actions - spent} actions)", False


def _top_up(w: Walker, g: FlowGrounding, step: Select | None, entered: int, spent: int):
    """Press a piece the rest of the way if its planned run left it short.

    The plan's presses are the intended route; this only closes a gap the route did
    not, which is what a refused press leaves behind — measured on the fourth level,
    where the plan ran to completion three cells short of the layout it had chosen
    and the model correctly predicted the failure that followed.

    Which piece is being pressed is read off the board rather than matched by size:
    a piece that has come to rest against a neighbour is segmented differently from
    the one the plan named, and identity by cell count loses it exactly when the
    top-up is needed.
    """
    if step is None or not step.target:
        return True, ""
    if step.target <= _all_pieces(g):
        return True, ""
    deltas = deltas_of(g)
    w.run(step, g)  # re-select: the selection may have moved on
    for _ in range(MOVE_ATTEMPTS):
        if step.target <= _all_pieces(g):
            return True, ""
        held = g.tracked_region()
        if held is UNKNOWN:
            return False, "the selected piece cannot be read off the board"
        current = frozenset(held.value)
        if w.actions - spent >= ACTION_BUDGET or not w.alive:
            return False, "out of budget while topping a piece up to its place"
        dr = min(r for r, _ in step.target) - min(r for r, _ in current)
        dc = min(c for _, c in step.target) - min(c for _, c in current)
        action = next(
            (a for a, (ar, ac) in sorted(deltas.items())
             if (ar and dr and (ar > 0) == (dr > 0) and not ac)
             or (ac and dc and (ac > 0) == (dc > 0) and not ar)),
            None,
        )
        if action is None:
            return False, f"no measured action closes the gap {dr, dc}"
        w.act(action, g)
        if w.level > entered:
            return True, ""
        held = g.tracked_region()
        if held is not UNKNOWN and frozenset(held.value) == current:
            return False, f"press {action} refused while topping up to target"
    return False, "ran out of attempts topping a piece up to its place"


def _attribute(g: FlowGrounding, plan) -> None:
    """Name where the claimed table and the engine part company on the layout the
    plan actually built: the predicted trail against the observed one, cell by cell."""
    board = g.board()
    observed = g.trajectory()
    if board is UNKNOWN or observed is UNKNOWN:
        print("    [attribute] no board or no observed spill to compare", flush=True)
        return
    predicted = predict(board.value, ORACLE)
    pred = [frozenset(layer) for layer in predicted.frontier if layer]
    obs = [frozenset(layer) for layer in observed.value if layer]
    print(f"    [attribute] predicted {len(pred)} step(s) / {sum(len(x) for x in pred)} cells, "
          f"observed {len(obs)} / {sum(len(x) for x in obs)}; "
          f"satisfied {len(predicted.satisfied)} of {len(board.value.sinks)}", flush=True)
    for i in range(max(len(pred), len(obs))):
        a = pred[i] if i < len(pred) else frozenset()
        b = obs[i] if i < len(obs) else frozenset()
        if a != b:
            print(f"    [attribute] first divergence at step {i}: "
                  f"invented {sorted(a - b)} missed {sorted(b - a)}", flush=True)
            break
    else:
        print("    [attribute] trails agree — the disagreement is in what COUNTS "
              "as satisfying a target, not in where the flow went", flush=True)


def _tally_target_colour(g: FlowGrounding) -> None:
    """Every region wearing the target appearance, with its notch count — the count
    is what separates a target from a wall of the same colour."""
    sinks = g.sink_candidates()
    if sinks is UNKNOWN:
        return
    cells = g._prev_cells
    colours = {cells[c] for _, grp in sinks.value for c in grp if c in cells}
    rows = []
    for colour in sorted(colours):
        for region in _regions(cells, colour):
            for part in g._by_mouth(region):
                rows.append((sorted(part)[0], len(part), len(g._mouths(part))))
    print(f"    [colour {sorted(colours)}] regions (anchor, cells, notches): {rows}",
          flush=True)


def _all_pieces(g: FlowGrounding) -> frozenset:
    inventory = g.pieces()
    if inventory is UNKNOWN:
        return frozenset()
    return frozenset(c for _, cells in inventory.value for c in cells)


def _explained_by_one_move(before: list, after: list, delta) -> bool:
    """True when translating ONE piece by ``delta`` accounts for the board now shown.

    Compared by CELLS OCCUPIED, not by footprint identity. Two pieces that come to
    rest against each other merge into one region, and a piece that closes over an
    embedded cell absorbs it — both change the footprint list without changing where
    the pieces are. An identity comparison calls that a failed move, the walk
    replans on a board it wrongly believes is broken, and the replan is built on a
    worse reading than the plan it replaced.

    The expected cells must be PRESENT; extra cells are tolerated, because a bridged
    region legitimately reports cells that no piece footprint contained before.
    """
    occupied_after = set().union(*after) if after else set()
    for i in range(len(before)):
        moved = {(r + delta[0], c + delta[1]) for (r, c) in before[i]}
        expected = moved.union(*(before[:i] + before[i + 1:])) if len(before) > 1 else moved
        if expected <= occupied_after:
            return True
    return False


def _unambiguous_anchor(step: Select, g: FlowGrounding) -> tuple:
    """A cell that belongs to the intended piece and to nothing else, right now.

    Pieces pass through each other, so an anchor chosen when the plan was made can
    be covered by a different piece by the time the click happens — and the click
    then selects the wrong piece, after which every directional press in the plan
    moves the wrong thing. Locating the footprint on the CURRENT board and picking
    a cell only it occupies is what keeps the plan pointed at what it meant."""
    inventory = g.pieces()
    if inventory is UNKNOWN or not step.footprint:
        return step.cell
    others: set = set()
    mine: set = set()
    for _, cells in inventory.value:
        cells = set(cells)
        if cells & step.footprint:
            mine |= cells
        else:
            others |= cells
    exclusive = sorted((mine or set(step.footprint)) - others)
    return exclusive[len(exclusive) // 2] if exclusive else step.cell


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
