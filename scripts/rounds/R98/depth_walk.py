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
# How many times to repeat a press the board appears to have dropped.
PRESS_RETRIES = 2


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


def _invariants_report(g: FlowGrounding, level: int) -> None:
    """Print the facts a level re-learns that a GAME cannot change, one line per level.

    Purpose: the walk spends a sacrificial commit per level to read the flow's
    direction, and a run has four failed commits for the whole GAME — which is how
    idx3 came to be reached with no lives left. Carrying the direction forward is
    only sound if it is genuinely invariant, and this line is the measurement that
    decides that. Observation only: nothing here changes what the walk does."""
    direction = g.initial_direction()
    colours = sorted({a.flow_colour for a in g._animations})
    emitters = g.emitters()
    print(f"    [invariant] idx{level} direction="
          f"{direction.value if direction is not UNKNOWN else 'UNKNOWN'} "
          f"flow_colours={colours} "
          f"emitters={emitters.value if emitters is not UNKNOWN else 'UNKNOWN'}",
          flush=True)


def play_level(w: Walker) -> tuple[bool, str]:
    """Ground, verify, plan and execute one level. Returns (cleared, stage note)."""
    entered = w.level
    spent = w.actions
    g = FlowGrounding()
    g.observe(0, None, w.obs.frame)

    phase = {"start": w.actions}
    for a in (1, 1, 2, 3, 4):
        w.act(a, g)
    phase["fixed probes"] = w.actions - phase["start"]
    # ⛔ A per-direction RETRY loop used to sit here, pressing each unmeasured direction up to
    # twice more. Measured on every level of a full walk: `deltas_of(g)` is EMPTY before it
    # runs and EMPTY after, so its own success condition is never met and it repaired nothing
    # — while costing exactly 8 actions a level, 32 across the walk, the largest single item
    # in the discovery bill. Removing it leaves the walk carrying the same three levels and
    # takes it from 138 actions to 106: idx0 23 -> 15, idx1 30 -> 22, idx2 55 -> 47. It was
    # added for a real measured reason (the engine does drop a press), so what has changed is
    # that the grounding no longer reports deltas at this point in the sequence at all; a
    # retry guarded on a signal that is always absent is not a safety net, it is a toll.

    # A direction can come back unmeasured simply because the piece was against a
    # bound when it was tried. Retry the missing ones from wherever it is now: an
    # unmeasured direction is not neutral, it removes every placement that needs it
    # from the planner's reach.

    phase["direction retries"] = w.actions - phase["start"] - phase["fixed probes"]
    probes = 0
    candidates = g.selection_candidates()
    if candidates is not UNKNOWN:
        for cell in candidates.value[:6]:
            w.click(cell, g)
            probes += 1

    phase["selection probes"] = (w.actions - phase["start"] - phase["fixed probes"]
                                 - phase["direction retries"])
    w.act(5, g)  # an UNAIMED commit: aiming first hides the direction (measured — idx3
                 # lost initial_direction and with it barriers, so the board would not
                 # assemble at all). The life it costs buys the only clean directional
                 # evidence there is.
    emitters, direction = g.emitters(), g.initial_direction()
    if emitters is not UNKNOWN and direction is not UNKNOWN:
        dr, _dc = direction.value
        lane = emitters.value[0][1] if dr != 0 else emitters.value[0][0]
        guard = 0
        moved = False
        while guard < 16 and g.tracked_region() is not UNKNOWN:
            cur = g.tracked_region().value
            have = [c for _, c in cur] if dr != 0 else [r for r, _ in cur]
            if min(have) <= lane <= max(have):
                break
            w.act(4 if lane > max(have) else 3, g)
            moved = True
            guard += 1
        # Only re-commit if the aiming actually moved something. A commit is not free:
        # a run has FOUR failed commits for the WHOLE GAME, and spending one to re-observe
        # a board that did not change is how idx3 came to be reached with no lives left —
        # its plan was executed on a game that was already over, which is what every
        # explanation this round built for that level was actually explaining.
        if moved:
            w.act(5, g)

    phase["commit + aiming"] = w.actions - phase["start"] - sum(
        v for k, v in phase.items() if k != "start")
    # Read AFTER the sacrificial commit and the aiming, which is where every later consumer
    # of the table sits: `_top_up` picks its press from it, and the plan driver checks a
    # refused press against it. Empty here would mean those paths are dead too.
    # The retry belongs HERE, not before the commit. Measured: `deltas_of(g)` is empty at the
    # old site, so the loop pressed all four directions twice for nothing visible; by this
    # point the table is filled by the probes and the commit, and only a genuinely missing
    # direction is retried. idx3 is the level that needs it — without any retry it plans with
    # three directions instead of four.
    for a in (1, 2, 3, 4):
        if a in deltas_of(g):
            continue
        w.act(a, g)
        if a not in deltas_of(g):
            # The engine drops a press now and then, measured three times out of three
            # elsewhere in this round. An unmeasured direction is not neutral: it removes
            # every placement that needs it from the planner's reach.
            w.act(a, g)
    print(f"    [deltas] idx{entered} at plan time: {sorted(deltas_of(g).items())}", flush=True)
    _invariants_report(g, entered)
    print("    [phases] idx%d " % entered + "  ".join(
        f"{k}={v}" for k, v in phase.items() if k != "start"), flush=True)
    # Where the level's actions go. The certified oracle path clears idx0 in 10 (8 discovery
    # + 2 plan) and the walk takes 23, and the scoring metric is the SQUARE of the action
    # ratio, so the difference is not bookkeeping. Printed per level because the discovery
    # half is what a deeper level would have to re-pay.
    print(f"    [cost] idx{entered} discovery so far {w.actions - spent} action(s) "
          f"({probes} selection probes)", flush=True)
    # What those probes BOUGHT. The selection appearances are a property of the game's
    # sprites, not of a layout, so if they read the same on every level the walk is paying
    # four to six actions a level for a fact it already had.
    sel, idle = g.piece_appearances()
    print(f"    [bought] idx{entered} selected={sel} idle={idle} "
          f"commit_action={g.commit_action().value if g.commit_action() is not UNKNOWN else '?'}",
          flush=True)

    if g.board() is UNKNOWN:
        return False, f"grounding incomplete (pieces={_count(g.pieces())}, " \
                      f"targets={_count(g.sink_candidates())})"

    if os.environ.get("R98_DUMP_BOARD") == "1":
        _tally_target_colour(g)

    hypothesis = F.sp80_oracle_instance()
    if os.environ.get("R98_CAPTURE_STUCK"):
        # The board AS VERIFIED, so a later capture can be compared against it WITHIN one
        # run. Comparing across runs is how "the inventory shrank" got asserted from two
        # boards that never coexisted.
        at_verify = g.board()
        if at_verify is not UNKNOWN:
            _capture(at_verify.value, g.trajectory(),
                     os.environ["R98_CAPTURE_STUCK"] + ".verify", g._prev_cells,
                     entered)
    verdict = verify_flow_instance(hypothesis, g, w.level > entered)
    if verdict.verdict.value == "CONTRADICTED":
        # Freeze the board that produced the contradiction. Without this the walk reports
        # a disagreement and then throws away the only evidence of it — the next run
        # plans differently and the board is gone.
        if os.environ.get("R98_CAPTURE"):
            _capture(g.board().value, g.trajectory(), os.environ["R98_CAPTURE"],
                     g._prev_cells, entered, _sink_sources(g))
        return False, f"verifier CONTRADICTED: {verdict.reason}"
    if verdict.verdict.value != "PASS":
        # UNKNOWN is "cannot judge", not "wrong". The measured cause here is a source
        # hidden under a piece, so the replay is missing flow the engine has — that
        # says the EVIDENCE is short, not that the hypothesis is. A walk that stops on
        # it throws away a level over a board it can still plan on; a walk that stops
        # on CONTRADICTED keeps the verifier's real power.
        print(f"    [verifier] {verdict.verdict.value} — proceeding: {verdict.reason}",
              flush=True)

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
            print(f"    [plan] absorbers: {sorted(g.absorbers())} | falling columns "
                  f"{g.falling_columns()}", flush=True)
            if plan.status is PlanStatus.SOLVABLE and plan.planned_board is not None:
                print(f"    [plan] chosen layout barrier hits "
                      f"{predict(plan.planned_board, ORACLE).barrier_hits}", flush=True)
            print(f"    [plan] targets known at plan time: "
                  f"{0 if known is UNKNOWN else len(known.value)} "
                  f"{[] if known is UNKNOWN else [sorted(c)[0] for _, c in known.value]}",
                  flush=True)
        if plan.status is not PlanStatus.SOLVABLE and g.falling_columns() is UNKNOWN:
            # A falling source reveals its COLUMN only when it has room to fall: a
            # stream landing on the piece directly beneath it spills off the ends at
            # once, and fall-off looks nothing like landing. So slide the cover, run
            # the spill, put it back and run it again — discovery is an ACTION here.
            #
            # Only when the model is already stuck, because the slide is not free:
            # doing it unconditionally cost idx0 its clear and left idx2 with a piece
            # that had no reachable placement.
            if os.environ.get("R98_CAPTURE_STUCK"):
                # BEFORE the slide as well: the slide presses actions and moves a piece,
                # so a board captured only after it cannot say whether an inventory the
                # compiler planned on was already short or was shortened here.
                pre_slide = g.board()
                if pre_slide is not UNKNOWN:
                    _capture(pre_slide.value, g.trajectory(),
                             os.environ["R98_CAPTURE_STUCK"] + ".preslide",
                             g._prev_cells, entered)
            _slide_a_cover(w, g)
            if os.environ.get("R98_DUMP_BOARD") == "1":
                print(f"    [discover] slid a cover; falling columns now "
                      f"{g.falling_columns()}", flush=True)
            plan = compile_flow_hypothesis(hypothesis, g)
        if plan.status is not PlanStatus.SOLVABLE:
            if os.environ.get("R98_DUMP_BOARD") == "1":
                b = g.board().value
                print(f"    [board] pieces={[(sorted(x)[0], len(x)) for x in b.pieces]} "
                      f"sinks={len(b.sinks)} hazards={sorted(b.hazard_cells)} "
                      f"emergences={sorted(b.emergences)} dir={b.direction} "
                      f"standing={len(b.standing_flow)}", flush=True)
            if os.environ.get("R98_CAPTURE_STUCK"):
                pre = g.board()
                if pre is not UNKNOWN:
                    _capture(pre.value, g.trajectory(), os.environ["R98_CAPTURE_STUCK"],
                             g._prev_cells, entered)
            pieces = g.pieces()
            held = "unknown" if pieces is UNKNOWN else str(len(pieces.value))
            return False, (f"compiler {plan.status.value}: {plan.reason} "
                           f"[board held {held} piece(s)]")
        knew = g.falling_sources()
        knew = () if knew is UNKNOWN else knew.value
        cleared, note, diverged = _execute(w, g, plan, entered, spent, probes)
        learned = g.falling_sources()
        learned = () if learned is UNKNOWN else learned.value
        if not cleared and not diverged and set(learned) - set(knew):
            # The commit taught the model something it did not have when it planned —
            # a spill exposes lanes that only fire on that layout. Planning again with
            # them is not a retry of the same plan, it is the first plan the model is
            # equipped to make.
            note = f"{note}; learned {sorted(set(learned) - set(knew))}"
            diverged = True
        if cleared:
            return True, note
        if not diverged:
            return False, note
        if w.actions - spent >= ACTION_BUDGET or not w.alive:
            return False, f"{note}; out of budget"
    return False, f"{note}; gave up after {attempts} plans"


def _slide_a_cover(w: Walker, g: FlowGrounding) -> None:
    """Move the piece a stream is spilling over, then commit again."""
    direction = g.initial_direction()
    trail = g.trajectory()
    pieces = g.pieces()
    if UNKNOWN in (direction, trail, pieces):
        return
    dr, dc = direction.value
    entries = {c for layer in trail.value[:1] for c in layer}
    for layer in trail.value:
        for (r, c) in layer:
            if (r - dr, c - dc) not in {x for lay in trail.value for x in lay}:
                entries.add((r, c))
    covers = [
        cells for _, cells in pieces.value
        if any((r + dr * k, c + dc * k) in entries or (r - dr * k, c - dc * k) in entries
               for (r, c) in cells for k in (0, 1))
        or any(abs(r - er) + abs(c - ec) == 1 for (r, c) in cells for (er, ec) in entries)
    ]
    if not covers:
        return
    target = min(covers, key=lambda cells: min(cells))
    step = next((a for a, (ar, ac) in sorted(deltas_of(g).items())
                 if (ar, ac) == (dr, dc)), None)
    if step is None:
        if os.environ.get("R98_DUMP_BOARD") == "1":
            print(f"    [discover] no measured action moves along {dr, dc}; "
                  f"measured {sorted(deltas_of(g).items())}", flush=True)
        return
    back = next((a for a, (ar, ac) in sorted(deltas_of(g).items())
                 if (ar, ac) == (-dr, -dc)), None)
    w.click(sorted(target)[len(target) // 2], g)
    w.act(step, g)
    w.act(5, g)
    if back is not None:
        # put it back: discovery must not cost the layout. Measured on idx2, where
        # leaving the cover where the probe put it left a piece with no reachable
        # placement and the level went from cleared to unplannable.
        w.click(sorted(target)[len(target) // 2], g)
        w.act(back, g)
        # and run the spill once more, so the evidence the verifier judges belongs to
        # the layout that is actually on the board
        w.act(5, g)


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
    pending_capture = None
    forecast = None
    forecast_sinks: tuple = ()
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
            # The board can change WHILE a plan executes — moving a piece uncovers
            # what it was standing on — so the forecast is taken again here, on the
            # board as it will actually be committed.
            pre = g.board()
            forecast = predict(pre.value, ORACLE) if pre is not UNKNOWN else None
            forecast_sinks = pre.value.sinks if pre is not UNKNOWN else ()
            if forecast is not None and os.environ.get("R98_DUMP_BOARD") == "1":
                print(f"    [forecast] as committed: {len(forecast.satisfied)} of "
                      f"{len(pre.value.sinks)} target(s), wins={forecast.wins}",
                      flush=True)
                _board_diff(plan.planned_board, pre.value)
            # the commit: the LAST piece has no successor to top it up, and a layout
            # that is one press short spills as a layout nobody chose
            arrived, note = _top_up(w, g, held, entered, spent)
            # The board AS IT WILL BE ACTED ON. Pairing it with the trajectory that the
            # action produces is the whole contract of a capture, and the first version
            # of this broke it twice over: it read `pre`, taken before the top-up AND
            # before the final step, against a spill that ran after both. Measured, that
            # board had the engine's flow passing through 1 of 1, 2 of 3 and 3 of 4 of
            # its own pieces, where every valid board in the corpus has zero.
            pending_capture = (g.board() if os.environ.get("R98_CAPTURE")
                               and forecast is not None else None)
            if w.level > entered:
                return True, f"cleared in {w.actions - spent} actions ({probes} probes)", False
            if not arrived:
                return False, note, True
        inventory = g.pieces()
        planned = len(plan.planned_board.pieces) if plan.planned_board else 0
        if inventory is not UNKNOWN and planned and len(inventory.value) < planned:
            # A piece the plan counts on is no longer on the board. Measured on idx3:
            # five pieces of nineteen cells became three of fourteen mid-plan, and the
            # driver went on pressing at one that was not there. What removes a piece is
            # not yet modelled; noticing it and planning again from what IS there costs
            # one action instead of the rest of the level.
            return False, (f"a piece is gone: {len(inventory.value)} on the board where "
                           f"the plan counts {planned}"), True
        before = g.tracked_region()
        w.run(step, g)
        if pending_capture is not None and pending_capture is not UNKNOWN:
            # AFTER the action and BEFORE the clear check: the trajectory the action
            # produced, against the board it was taken on. Capturing past the return is
            # why every board in the corpus used to come from a level that had just
            # FAILED, and pairing it with an earlier board is why the ones that did not
            # were unusable.
            _capture(pending_capture.value, g.trajectory(), os.environ["R98_CAPTURE"],
                     g._prev_cells, entered, _sink_sources(g))
            pending_capture = None
        if w.level > entered:
            return True, f"cleared in {w.actions - spent} actions ({probes} selection probes)", False
        if isinstance(step, int) and step in deltas_of(g) and before is not UNKNOWN:
            after = g.tracked_region()
            if after is not UNKNOWN and frozenset(after.value) == frozenset(before.value):
                # A press that lands nowhere is usually DROPPED, not refused: measured
                # on idx3, the same press repeated at once moves the piece from a
                # position where nothing occupies the cell ahead. The board still shows
                # the piece unmoved, so this is a lost press and not an observation
                # running a frame behind — repeating it cannot double the move.
                #
                # Two drops in a row happen: a probe at the point where one retry gave
                # up reported the very next press landing. So the press is repeated
                # while the piece is still where it was, up to PRESS_RETRIES times.
                expected = frozenset(
                    (r + deltas_of(g)[step][0], c + deltas_of(g)[step][1])
                    for (r, c) in before.value
                )
                landed = False
                for _ in range(PRESS_RETRIES):
                    w.act(step, g)
                    after = g.tracked_region()
                    if after is UNKNOWN:
                        break
                    if frozenset(after.value) == expected:
                        landed = True
                        break
                    if frozenset(after.value) != frozenset(before.value):
                        break  # it moved somewhere else; stop pressing and replan
                if landed:
                    continue
            if after is not UNKNOWN and frozenset(after.value) == frozenset(before.value):
                # A press in the plan's own path that does not land invalidates the
                # rest of it: every later press assumes this piece moved. Replanning
                # from the board as it IS beats pressing harder — the refusal is
                # information the compiler did not have.
                if os.environ.get("R98_DUMP_BOARD") == "1":
                    _identity_report(g, plan, held, frozenset(before.value))
                if os.environ.get("R98_PROBE") == "1":
                    # PRESSES ACTIONS: it perturbs the run it is diagnosing, so it is
                    # not part of the observational dump. Measured the hard way — a
                    # dumped run drifted where the same run without the dump executed
                    # its plan.
                    _refusal_probe(w, g, frozenset(before.value), step)
                inv = g.pieces()
                counts = ("?" if inv is UNKNOWN else len(inv.value),
                          len(plan.planned_board.pieces) if plan.planned_board else "?")
                return False, (f"planned press {step} did not land; pieces {counts[0]} vs "
                               f"planned {counts[1]}; "
                               f"{_what_blocks(g, frozenset(before.value), deltas_of(g)[step])}"), True

    if os.environ.get("R98_CAPTURE") and forecast is not None:
        _capture(pre.value, g.trajectory(), os.environ["R98_CAPTURE"], g._prev_cells,
                 entered)
    if os.environ.get("R98_DUMP_BOARD") == "1" and forecast is not None:  # noqa: SIM102
        _attribute_pre(g, forecast, forecast_sinks)
        want = frozenset(c for piece in plan.intended for c in piece)
        have = _all_pieces(g)
        print(f"    [layout] short by {len(want - have)} cell(s); missing "
              f"{sorted(want - have)}", flush=True)
        _region_fates(g)
        print(f"    [lanes] after the commit: {g.falling_sources()}", flush=True)
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
        for _ in range(PRESS_RETRIES + 1):
            w.act(action, g)
            if w.level > entered:
                return True, ""
            held = g.tracked_region()
            if held is UNKNOWN or frozenset(held.value) != current:
                break  # it moved; carry on from wherever it is
        held = g.tracked_region()
        if held is not UNKNOWN and frozenset(held.value) == current:
            return False, (f"press {action} refused {PRESS_RETRIES + 1} times while "
                           f"topping up; {_what_blocks(g, current, deltas.get(action))}")
    return False, "ran out of attempts topping a piece up to its place"


_CAPTURE_SEQ: dict[int, int] = {}


def _sink_sources(g: FlowGrounding) -> dict:
    """The region sizes each shortlist source proposes, recorded WITH the capture.

    `sink_candidates()` draws from four independent sources and filters afterwards, so a
    board carrying a wrong target cannot say which source named it. Probing them at
    grounding time does not answer it either: measured on idx2, no source proposes
    anything larger than five cells through the direction probes, the sacrificial commit
    and the selection probes, while the board captured at the commit carries a nineteen-
    cell one. Recording them beside the board is the only way to ask at the right moment."""
    changed: list = []
    for anim in g._animations:
        for region in anim.changed_regions:
            if region not in changed:
                changed.append(region)
    return {
        "changed_appearance": sorted(len(r) for r in changed),
        "obstruction": sorted(len(r) for r in g._obstruction_regions()),
        "matching_shape": sorted(len(r) for r in g._matching_shape_regions(changed)),
        "wearing_appearance": sorted(len(r) for r in g._appearance_regions(changed)),
    }


def _capture(board, observed, prefix: str, cells=None, level: int = -1, sources=None) -> None:
    """Freeze the board AS COMMITTED and the spill it produced.

    Rule changes alter what the compiler chooses, so re-running the whole walk compares
    a new rule on a new layout and says nothing about the rule — measured twice, where a
    restriction that should have removed four cells produced a different plan and
    twenty-four. A rule is judged against FIXED evidence or not at all.

    ``R98_CAPTURE`` is a PREFIX, not a path: every commit of every level writes its own
    ``{prefix}_idx{level}_{n}.json``. It used to be one path, overwritten at each commit
    of each level, so a walk that cleared four levels left evidence from the last one
    only — which is why every capture in the sweep came from idx3, the single level whose
    board the harness cannot read completely, and why the step-off question could not be
    settled from them."""
    import json

    if board is None or observed is UNKNOWN:
        return
    _CAPTURE_SEQ[level] = _CAPTURE_SEQ.get(level, 0) + 1
    path = f"{prefix}_idx{level}_{_CAPTURE_SEQ[level]}.json"
    payload = {
        "pieces": [sorted(p) for p in board.pieces],
        "sinks": [sorted(s) for s in board.sinks],
        "hazard_cells": sorted(board.hazard_cells),
        "emitter_cells": sorted(board.emitter_cells),
        "standing_flow": sorted(board.standing_flow),
        "absorber_cells": sorted(board.absorber_cells),
        "emergences": [[list(c), t] for c, t in board.emergences],
        "falling_sources": [list(x) for x in board.falling_sources],
        "direction": list(board.direction),
        "size": board.size,
        "observed": [sorted(layer) for layer in observed.value if layer],
        # the board's APPEARANCES, so a bench can ask why an entity was or was not seen
        "colours": ({f"{r},{c}": v for (r, c), v in cells.items()} if cells else {}),
        # WHICH shortlist source proposed each target-sized region. A capture that records
        # only the final sinks cannot say where a wrong one came from, and idx2's whole
        # replay error is one region no probe could attribute at grounding time.
        "sink_sources": sources or {},
    }
    with open(path, "w") as f:
        json.dump(payload, f)
    print(f"    [capture] wrote {path}", flush=True)


def _attribute_pre(g: FlowGrounding, forecast, sinks=()) -> None:
    """The prediction taken on the board AS COMMITTED against the spill that ran.

    Predicting on the post-commit board and comparing it to that same spill compares
    a forecast for one board with a run on another — a mistake this round already
    made once. The forecast here is taken in the action before the commit."""
    observed = g.trajectory()
    if observed is UNKNOWN:
        print("    [attribute] no observed spill", flush=True)
        return
    pred = [frozenset(layer) for layer in forecast.frontier if layer]
    obs = [frozenset(layer) for layer in observed.value if layer]
    named = [sorted(s)[0] for s in sinks]
    print(f"    [attribute] predicted {len(pred)} step(s)/{sum(len(x) for x in pred)} cells "
          f"vs observed {len(obs)}/{sum(len(x) for x in obs)}; forecast satisfies "
          f"{[named[i] for i in sorted(forecast.satisfied) if i < len(named)]}", flush=True)
    for i in range(max(len(pred), len(obs))):
        a = pred[i] if i < len(pred) else frozenset()
        b = obs[i] if i < len(obs) else frozenset()
        if a != b:
            print(f"    [attribute] first divergence at step {i}: "
                  f"invented {sorted(a - b)} missed {sorted(b - a)}", flush=True)
            for k in range(max(0, i - 1), min(max(len(pred), len(obs)), i + 4)):
                a = sorted(pred[k]) if k < len(pred) else []
                b = sorted(obs[k]) if k < len(obs) else []
                print(f"      step {k:2d}: predicted {a} | observed {b}", flush=True)
            _trail_surplus(forecast, observed.value)
            _entry_report(g, observed.value)
            return
    print("    [attribute] the trails agree cell for cell", flush=True)


def _entry_report(g: FlowGrounding, observed) -> None:
    """Where the committed spill ENTERED the board, against the emergences the model
    injected — which were observed under a different layout."""
    layers = [layer for layer in observed if layer]
    board = g.board()
    print(f"    [entry] observed first layers {[sorted(x) for x in layers[:2]]}", flush=True)
    for i, layer in enumerate(layers[:12]):
        print(f"      obs {i:2d}: {sorted(layer)}", flush=True)
    if board is not UNKNOWN:
        print(f"    [entry] injected emergences {sorted(board.value.emergences)} "
              f"standing {sorted(board.value.standing_flow)}", flush=True)
    cells = g._prev_cells
    if cells is not None:
        size = int(round(len(cells) ** 0.5))
        for r in range(size):
            print("      r%-2d " % r + " ".join(f"{cells[(r, c)]:2d}" for c in range(size)),
                  flush=True)


def _trail_surplus(forecast, observed) -> None:
    """Cells the forecast produces that the spill never shows, and the reverse."""
    pred = {c for layer in forecast.frontier for c in layer}
    obs = {c for layer in observed for c in layer}
    where = {}
    for i, layer in enumerate([x for x in forecast.frontier if x]):
        for c in layer:
            where.setdefault(c, i)
    print(f"    [surplus] predicted-only "
          f"{sorted((c, where.get(c)) for c in pred - obs)}", flush=True)
    print(f"    [surplus] observed-only  {sorted(obs - pred)}", flush=True)
    plist = [sorted(x) for x in forecast.frontier if x]
    olist = [sorted(x) for x in observed if x]
    for k in range(max(0, min(len(plist), len(olist)) - 4), max(len(plist), len(olist))):
        a = plist[k] if k < len(plist) else []
        b = olist[k] if k < len(olist) else []
        print(f"      tail {k:2d}: predicted {a} | observed {b}", flush=True)


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


def _board_diff(planned, actual) -> None:
    """Where the board the compiler predicted on differs from the board about to be
    committed. A plan is a forecast ABOUT a board; if that board is not the one that
    arrives, the forecast was never tested."""
    if planned is None:
        return
    for field in ("pieces", "sinks", "hazard_cells", "emitter_cells", "standing_flow",
                  "emergences", "direction", "size"):
        want, have = getattr(planned, field), getattr(actual, field)
        if want != have:
            if isinstance(want, (tuple, list, frozenset, set)) and isinstance(have, type(want)):
                print(f"    [board] {field}: planned {len(want)} vs actual {len(have)}; "
                      f"only-planned {sorted(set(want) - set(have))[:3]} "
                      f"only-actual {sorted(set(have) - set(want))[:3]}", flush=True)
            else:
                print(f"    [board] {field}: planned {want} vs actual {have}", flush=True)


def _region_fates(g: FlowGrounding) -> None:
    """For every region wearing the target appearance: its notch count, whether the
    spill ENTERED it, and whether it changed appearance while the spill ran.

    A change of appearance is this family's satisfied-target signal, so a region that
    changes is a target of SOME kind even when it has no notch to be flanked at."""
    sinks = g.sink_candidates()
    if sinks is UNKNOWN or g._prev_cells is None or not g._animations:
        return
    cells = g._prev_cells
    colours = {cells[c] for _, grp in sinks.value for c in grp if c in cells}
    anim = g._animations[-1]
    trail = {c for layer in anim.frontier for c in layer}
    changed = {c for grp in anim.changed_regions for c in grp}
    for colour in sorted(colours):
        for region in _regions(cells, colour):
            for part in g._by_mouth(region):
                print(f"    [fate] {sorted(part)[0]} {len(part)} cells "
                      f"{len(g._mouths(part))} notch(es): entered={bool(part & trail)} "
                      f"recoloured={bool(part & changed)}", flush=True)


def _refusal_probe(w: Walker, g: FlowGrounding, piece: frozenset, refused: int) -> None:
    """Try every measured direction from the refused state and report which ones the
    engine honours. A press refused at a cell nothing occupies is a constraint the
    board model does not carry; which directions survive says what kind."""
    deltas = deltas_of(g)
    sources = g.hidden_sources()
    print(f"    [refusal] piece {sorted(piece)}; hidden sources "
          f"{'UNKNOWN' if sources is UNKNOWN else sorted(sources.value)}", flush=True)
    cells = g._prev_cells
    if cells is not None:
        size = int(round(len(cells) ** 0.5))
        print("    [refusal] board:", flush=True)
        for r in range(size):
            print("      r%-2d " % r + " ".join(f"{cells[(r, c)]:2d}" for c in range(size)),
                  flush=True)
    # first: the SAME press again, immediately. A refusal that clears on a repeat is
    # not geometry at all.
    w.act(refused, g)
    now = g.tracked_region()
    print(f"    [refusal] press {refused} repeated immediately: "
          f"{'LANDS' if now is not UNKNOWN and frozenset(now.value) != piece else 'refused again'}",
          flush=True)
    if now is not UNKNOWN and frozenset(now.value) != piece:
        return
    for action in (1, 2, 3, 4):
        w.act(action, g)
        now = g.tracked_region()
        moved = now is not UNKNOWN and frozenset(now.value) != piece
        print(f"    [refusal] action {action} delta {deltas.get(action)}: "
              f"{'MOVED to ' + str(sorted(now.value)[0]) if moved else 'refused'}", flush=True)
        if moved:
            # the same press again from one cell over: if it lands now, what refused
            # it was the POSITION, not the piece
            w.act(refused, g)
            after = g.tracked_region()
            again = after is not UNKNOWN and frozenset(after.value) != frozenset(now.value)
            print(f"    [refusal] press {refused} retried one cell over: "
                  f"{'LANDS — the refusal was positional' if again else 'refused again'}",
                  flush=True)
            return


def _identity_report(g: FlowGrounding, plan, held, selected: frozenset) -> None:
    """Whether the piece the plan named is the piece the click selected.

    Touching pieces are read as ONE region, so a plan built on the entry inventory can
    address a piece the board no longer reports separately."""
    inventory = g.pieces()
    planned = plan.planned_board.pieces if plan.planned_board else ()
    print(f"    [identity] plan named {sorted(held.footprint)[0] if held else None} "
          f"({len(held.footprint) if held else 0} cells), "
          f"selected {sorted(selected)[0]} ({len(selected)} cells)", flush=True)
    print(f"    [identity] plan's pieces {[(sorted(p)[0], len(p)) for p in planned]}",
          flush=True)
    if inventory is not UNKNOWN:
        print(f"    [identity] board's pieces now "
              f"{[(sorted(c)[0], len(c)) for _, c in inventory.value]}", flush=True)
    cells = g._prev_cells
    if cells is not None:
        size = int(round(len(cells) ** 0.5))
        sel, idle = g.piece_appearances()
        print(f"    [identity] selected {sel}, idle {idle}, moving {g._moving_colour}, "
              f"flow {[a.flow_colour for a in g._animations[-2:]]}", flush=True)
        for r in range(size):
            print("      r%-2d " % r + " ".join(f"{cells[(r, c)]:2d}" for c in range(size)),
                  flush=True)


def _what_blocks(g: FlowGrounding, piece: frozenset, delta) -> str:
    """What occupies the cells a refused press would have moved this piece into.

    A refusal is evidence about the board, and the useful part of it is WHICH cells
    said no — the compiler computes reachable placements from the measured deltas
    alone, so anything found here is a constraint it does not yet model."""
    if delta is None:
        return "no measured delta for that action"
    ahead = {(r + delta[0], c + delta[1]) for (r, c) in piece} - piece
    board = g.board()
    if board is UNKNOWN:
        return f"would enter {sorted(ahead)}; the board is not grounded"
    b = board.value
    others = frozenset(c for p in b.pieces for c in p) - piece
    targets = frozenset(c for s in b.sinks for c in s)
    off = {c for c in ahead if not (0 <= c[0] < b.size and 0 <= c[1] < b.size)}
    colours = ({c: g._prev_cells[c] for c in sorted(ahead) if c in g._prev_cells}
               if g._prev_cells else {})
    return (f"would enter {sorted(ahead)}: "
            f"piece{sorted(ahead & others)} target{sorted(ahead & targets)} "
            f"hazard{sorted(ahead & b.hazard_cells)} flow{sorted(ahead & b.standing_flow)} "
            f"off-board{sorted(off)} colours{colours}")


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
