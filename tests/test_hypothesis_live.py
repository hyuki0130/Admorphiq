"""R95b step (vi) tests: the live-driver's PURE helpers (no env, no LLM).

The env-driving path (LiveEnv / run_once) is exercised only under the real gate;
here we pin the cycle-discovery loop (with an offline simulator), the discovery
cell selection, and the gate verdict aggregation.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from admorphiq.hypothesis_select.grounding import UNKNOWN, GroundingService

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_hypothesis_live.py"
_SPEC = importlib.util.spec_from_file_location("probe_hypothesis_live", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["probe_hypothesis_live"] = _MOD
_SPEC.loader.exec_module(_MOD)

discover_cycle = _MOD.discover_cycle
gate_verdict = _MOD.gate_verdict
discover_deltas = _MOD.discover_deltas
movement_edges_confirmed = _MOD.movement_edges_confirmed
unconfirmed_directions = _MOD.unconfirmed_directions
clean_block_wall = _MOD.clean_block_wall
noop_block_walls = _MOD.noop_block_walls
joint_reset_hazards = _MOD.joint_reset_hazards
walls_to_unlearn = _MOD.walls_to_unlearn
block_learn_decision = _MOD.block_learn_decision
refresh_blocks = _MOD.refresh_blocks
decay_blocks = _MOD.decay_blocks
flip_flop_cells = _MOD.flip_flop_cells


def _lattice(overrides=None):
    """A 3x3 lattice of 2x2 cells, all colour 2 unless overridden."""
    overrides = overrides or {}
    g = [[0] * 20 for _ in range(20)]
    for r0 in (4, 8, 12):
        for c0 in (6, 10, 14):
            colour = overrides.get((r0, c0), 2)
            for dr in (0, 1):
                for dc in (0, 1):
                    g[r0 + dr][c0 + dc] = colour
    return tuple(tuple(row) for row in g)


def test_discover_cycle_closes_a_two_colour_cycle_via_bidirectional_probe():
    """Purpose: the discovery loop closes a 2-colour cycle by clicking a cell
    REPEATEDLY (forward + reverse edges), the honest fix for gold's
    one-directionality — driven here by an offline flip simulator.

    Expected feedback: pass proves the live driver can acquire the cycle gold
    cannot, within budget. Fail means discovery never closes the cycle and every
    ft09 run would report GROUNDING_INCOMPLETE."""
    start = _lattice()
    gs = GroundingService()
    gs.feed(start)
    assert gs.get_ordered_cycle() is UNKNOWN  # nothing observed yet

    def probe(x, y):
        # Flip the clicked lattice cell between colours 2 and 7, return the frame.
        grid = [list(r) for r in gs._prev_grid]
        cur = grid[y][x]
        new = 7 if cur == 2 else 2
        # repaint the whole 2x2 cell the click landed in
        r0, c0 = (y // 4) * 4 + (0 if y % 4 < 2 else 2), (x // 4) * 4 + (0 if x % 4 < 2 else 2)
        for dr in (0, 1):
            for dc in (0, 1):
                grid[r0 + dr][c0 + dc] = new
        return tuple(tuple(r) for r in grid)

    closed, actions = discover_cycle(gs, probe, budget=30)
    assert closed is True
    assert 0 < actions <= 30
    cycle = gs.get_ordered_cycle()
    assert cycle is not UNKNOWN and set(cycle.value) == {2, 7}


def test_discover_cycle_gives_up_within_budget_when_it_cannot_close():
    """Purpose: when a probe never produces a reverse edge (the board is inert),
    discovery stops at the budget and reports not-closed — never loops forever.

    Expected feedback: pass proves the honest GROUNDING_INCOMPLETE path is
    budget-bounded. Fail means an unclosable cycle would hang the gate."""
    gs = GroundingService()
    gs.feed(_lattice())

    def inert(x, y):
        return gs._prev_grid  # nothing ever changes

    closed, actions = discover_cycle(gs, inert, budget=6)
    assert closed is False
    assert actions <= 6


def test_gate_verdict_pass_only_on_all_runs_clearing_the_target():
    """Purpose: the ft09 gate PASSes only when every run cleared idx0+idx1.

    Expected feedback: pass proves the 3/3 gate rule is enforced and a single
    non-clear (or a GROUNDING_INCOMPLETE) fails the gate. Fail means the verdict
    would over-report."""
    ft09_pass = [{"plan_outcome": "CLEARED", "levels_cleared": 2} for _ in range(3)]
    assert gate_verdict(ft09_pass, "ft09") == "PASS"

    one_short = ft09_pass[:2] + [{"plan_outcome": "CLEARED", "levels_cleared": 1}]
    assert gate_verdict(one_short, "ft09") == "FAIL"  # a run reached only idx0

    incomplete = ft09_pass[:2] + [{"plan_outcome": "GROUNDING_INCOMPLETE", "levels_cleared": 0}]
    assert gate_verdict(incomplete, "ft09") == "FAIL"
    assert gate_verdict([], "ft09") == "FAIL"  # no runs


def test_sc25_gate_scores_the_cast_handover_not_levels():
    """Purpose: per the FROZEN contract (sc25 idx0 pattern phase, navigation
    excluded), the sc25 gate scores ``cast_and_handover`` — NOT levels_cleared,
    which is honestly 0 for a genuine cast (the level does not clear without the
    out-of-scope exit navigation).

    Expected feedback: pass proves a 3/3 genuine-cast run PASSes with levels 0,
    while a plan-DONE that never cast (cast_and_handover False) FAILs even though
    it 'finished'. Fail means the gate reverted to a level-clear criterion the
    contract forbids for sc25."""
    cast_runs = [{"plan_outcome": "CAST_HANDOVER", "levels_cleared": 0, "cast_and_handover": True} for _ in range(3)]
    assert gate_verdict(cast_runs, "sc25") == "PASS"  # levels 0 is correct + expected

    no_cast = cast_runs[:2] + [{"plan_outcome": "DIVERGED", "levels_cleared": 0, "cast_and_handover": False}]
    assert gate_verdict(no_cast, "sc25") == "FAIL"  # a plan-DONE with no cast fails

    # A level-clear-shaped record without the cast flag must NOT pass sc25.
    level_shaped = [{"plan_outcome": "CLEARED", "levels_cleared": 1} for _ in range(3)]
    assert gate_verdict(level_shaped, "sc25") == "FAIL"


# ── movement-family (m0r0) discovery helpers ─────────────────────────────────
_MV_SCALE = 4
_MV_BG = 0
_MV_ACTOR = 9
# a consistent mirror scheme: rows symmetric (1 up / 2 down both), columns
# antisymmetric (3 diverges, 4 converges) — the m0r0 decoded structure
_MV_DELTAS = {1: ((-1, 0), (-1, 0)), 2: ((1, 0), (1, 0)), 3: ((0, -1), (0, 1)), 4: ((0, 1), (0, -1))}


def _mv_frame(a, b):
    """A 48x48 grid (each cell a 4x4 block) with two colour-9 actor cells at ``a``
    and ``b`` on an empty background."""
    g = [[_MV_BG] * 48 for _ in range(48)]
    for (r, c) in (a, b):
        for dr in range(_MV_SCALE):
            for dc in range(_MV_SCALE):
                g[r * _MV_SCALE + dr][c * _MV_SCALE + dc] = _MV_ACTOR
    return tuple(tuple(row) for row in g)


class _MoveSim:
    """An offline two-actor movement simulator applying the mirror deltas — the
    directional-probe analogue of the cycle flip simulator above. Actors start far
    apart with room to sweep without colliding, so every edge is cleanly observable."""

    def __init__(self, a=(5, 3), b=(5, 8)):
        self.a, self.b = a, b

    def frame(self):
        return _mv_frame(self.a, self.b)

    def probe(self, action):
        da, db = _MV_DELTAS[action]
        self.a = (self.a[0] + da[0], self.a[1] + da[1])
        self.b = (self.b[0] + db[0], self.b[1] + db[1])
        return self.frame()


def test_discover_deltas_confirms_all_eight_edges_via_directional_sweep():
    """Purpose: the directional-probe sweep acquires every (actor, direction) delta
    edge under the min-probe rule, reproducing the mirror structure (columns
    antisymmetric), within budget and with no spurious hazards.

    Expected feedback: pass proves the movement driver builds the complete transition
    table the compiler needs from live probes. Fail means discovery leaves edges open
    and every m0r0 run would report GROUNDING_INCOMPLETE."""
    sim = _MoveSim()
    gs = GroundingService()
    assert movement_edges_confirmed(gs) is False  # nothing observed yet
    closed, used, hazards = discover_deltas(gs, sim.frame(), sim.probe, budget=30)
    assert closed is True
    assert 0 < used <= 30
    assert hazards == 0
    d = gs.movement_deltas()
    assert d is not UNKNOWN
    need = {(aid, a) for aid in ("actor_a", "actor_b") for a in (1, 2, 3, 4)}
    assert set(d.value.keys()) == need
    assert d.value[("actor_a", 3)][1] == -d.value[("actor_b", 3)][1]  # columns antisymmetric


def test_discover_deltas_gives_up_within_budget_on_an_inert_board():
    """Purpose: when probes never move the actors (an inert board), discovery stops
    at the budget and reports not-confirmed — never loops forever.

    Expected feedback: pass proves the honest GROUNDING_INCOMPLETE path is
    budget-bounded for movement as for the cycle. Fail means an unresponsive board
    would hang the gate."""
    gs = GroundingService()
    start = _mv_frame((5, 3), (5, 8))

    def inert(_action):
        return start  # nothing ever changes

    closed, used, hazards = discover_deltas(gs, start, inert, budget=12)
    assert closed is False
    assert used <= 12
    assert hazards == 0


def test_movement_gate_scores_idx0_plus_idx1_clears():
    """Purpose: the m0r0 gate PASSes only when every run cleared idx0+idx1 with a
    CLEARED outcome.

    Expected feedback: pass proves the 3/3 two-level rule is enforced — a run that
    reached only idx0, or one that DIVERGED, fails the gate. Fail means the movement
    verdict would over-report."""
    passed = [{"plan_outcome": "CLEARED", "levels_cleared": 2} for _ in range(3)]
    assert gate_verdict(passed, "m0r0") == "PASS"

    one_short = passed[:2] + [{"plan_outcome": "CLEARED", "levels_cleared": 1}]
    assert gate_verdict(one_short, "m0r0") == "FAIL"  # reached only idx0

    diverged = passed[:2] + [{"plan_outcome": "DIVERGED", "levels_cleared": 1}]
    assert gate_verdict(diverged, "m0r0") == "FAIL"
    assert gate_verdict([], "m0r0") == "FAIL"


def test_clean_block_wall_learns_only_on_a_single_clean_block():
    """Purpose: clean_block_wall returns a wall ONLY for a clean independent_stay block
    (one actor stayed, its partner reached its predicted cell) and returns None for
    ambiguous divergences — the fix for the false-positive learned walls.

    Expected feedback: pass proves the reliable-learning rule learns the genuine wall
    (actor_b blocked into its target while actor_a advanced) and refuses to invent a
    wall when both actors are off-prediction, when a predicted merge didn't happen, or
    when nothing moved (the settle case). Fail means the noisy predicted-minus-observed
    behaviour that over-constrained the board into UNSATISFIABLE has returned."""
    # clean block: actor_a advanced (3,3)->(3,2) as predicted; actor_b stayed at (3,10),
    # blocked from its predicted (3,11) -> that cell is the wall.
    assert clean_block_wall(((3, 2), (3, 11)), [(3, 3), (3, 10)], [(3, 2), (3, 10)]) == (3, 11)
    # ambiguous: neither predicted cell reached -> learn nothing
    assert clean_block_wall(((3, 2), (3, 11)), [(3, 3), (3, 10)], [(4, 4), (5, 5)]) is None
    # predicted merge that didn't happen -> ambiguous
    assert clean_block_wall(((2, 6), (2, 6)), [(2, 5), (2, 7)], [(2, 5), (2, 7)]) is None
    # total no-op (both stayed = the settle case) -> not a clean single block
    assert clean_block_wall(((3, 5), (3, 8)), [(2, 5), (2, 8)], [(2, 5), (2, 8)]) is None


def test_noop_block_walls_learns_planned_stay_and_double_block_uniformly():
    """Purpose: on a TOTAL NO-OP frame (obs == prev), noop_block_walls learns every
    unreached predicted target that is not actor-occupied — 1 wall for a planned-stay +
    partner-block, 2 walls for a double independent_stay block, uniformly.

    Expected feedback: pass proves the period-N recompile loop (both actors stationary,
    nothing learned) is broken whether one or both actors are blocked. Fail means a
    planned-stay case (which double-block-only missed) learns nothing and loops."""
    # double block: both stayed at (6,2)/(6,10); predicted (7,2)/(7,10) both unreached
    assert noop_block_walls(((7, 2), (7, 10)), [(6, 2), (6, 10)], [(6, 2), (6, 10)]) == {(7, 2), (7, 10)}
    # planned-stay: actor_a's predicted target IS its current cell (6,4); actor_b blocked
    # entering (6,8) -> only (6,8) is a wall (the crack the v6 loop fell into)
    assert noop_block_walls(((6, 4), (6, 8)), [(6, 4), (6, 9)], [(6, 4), (6, 9)]) == {(6, 8)}
    # one actor actually moved -> not a total no-op (clean_block_wall's job)
    assert noop_block_walls(((7, 2), (7, 10)), [(6, 2), (6, 10)], [(6, 2), (7, 10)]) == set()


def test_walls_to_unlearn_invalidates_a_learned_wall_an_actor_occupies():
    """Purpose: walls_to_unlearn returns any learned wall an actor is currently standing
    on — observation trumps inference, so a false-positive wall (a stay misattributed to
    a cell the actor later enters) is invalidated.

    Expected feedback: pass proves the (6,9)-contradiction loop is broken: once actor_b
    is observed on the wrongly-learned (6,9), it is removed so the plan can route through
    it. Fail means a false wall persists and the plan mispredicts forever."""
    assert walls_to_unlearn({(3, 11), (6, 9), (7, 2)}, [(6, 4), (6, 9)]) == {(6, 9)}
    assert walls_to_unlearn({(3, 11)}, [(6, 4), (6, 9)]) == set()  # nothing occupied is a wall
    assert walls_to_unlearn({(6, 9)}, None) == set()  # no observation


def test_refresh_blocks_stamps_adds_and_clears_on_occupancy():
    """Purpose: refresh_blocks STAMPS a just-blocked target with the current recompile (route
    around it now), REFRESHES on re-block, and DROPS any cell an actor currently occupies
    (observation trumps inference) — the timestamped primary transient sensor.

    Expected feedback: pass proves block→route-around, re-block→refresh, and observe-on→clear
    all work, so a patroller cell is temporarily walled without being learned or unwallably
    fictionalised. Fail means the block is ignored (v10 hammer) or stays walled after clearing."""
    # a fresh block of (3,9) at recompile 5: actor_b was blocked entering it (reached (3,10))
    ba = refresh_blocks({}, ((3, 3), (3, 9)), [(3, 3), (3, 10)], 5)
    assert ba == {(3, 9): 5}
    # a re-block of (3,9) at recompile 6 (actor_a reached (3,3), actor_b blocked) refreshes it
    ba = refresh_blocks(ba, ((3, 3), (3, 9)), [(3, 3), (3, 10)], 6)
    assert ba == {(3, 9): 6}  # refreshed to 6
    # observation trumps inference: an actor now standing ON (3,9) clears it (passable)
    ba = refresh_blocks(ba, ((5, 9), (5, 5)), [(3, 9), (5, 5)], 7)
    assert (3, 9) not in ba


def test_decay_blocks_expires_stale_entries_only():
    """Purpose: decay_blocks EXPIRES block entries not re-confirmed within the TTL and KEEPS
    fresh ones — a one-off patroller position an actor can never observe-clear must not
    accumulate into permanent fiction (the self-sealing trap).

    Expected feedback: pass proves stale transient evidence decays to its epistemic weight
    (a block is evidence about NOW). Fail means accumulated one-offs wall the map into a
    false UNSATISFIABLE."""
    # ttl default 4: at recompile 10, a block from 5 (age 5 > 4) expires; one from 7 (age 3) stays
    kept, expired = decay_blocks({(1, 7): 5, (2, 9): 7}, 10, ttl=4)
    assert kept == {(2, 9): 7}
    assert expired == {(1, 7)}
    # nothing expires when all within ttl
    kept, expired = decay_blocks({(3, 3): 9}, 10, ttl=4)
    assert kept == {(3, 3): 9} and expired == set()


def test_flip_flop_cells_detects_a_recently_cleared_bounce_only():
    """Purpose: flip_flop_cells flags a just-blocked cell ONLY when it was CLEARED from the
    route-around set within the last `window` recompiles (a periodic-obstacle bounce), and
    ignores a first-time block or a stale clear.

    Expected feedback: pass proves the commit-and-wait trigger fires on a genuine
    chase (the (6,9)/(6,10) bounce) but not on ordinary blocks — so a static wall is still
    routed around and only a periodic obstacle is waited on. Fail means either the chase is
    missed (endless flip-flop) or every block is mistaken for a chase (never routes around)."""
    # (6,9) was cleared at recompile 10; a fresh block of it at recompile 11 is a bounce
    assert flip_flop_cells({(6, 9)}, {(6, 9): 10}, 11) == {(6, 9)}
    # a first-time block (never cleared) is NOT a flip-flop
    assert flip_flop_cells({(6, 9)}, {}, 11) == set()
    # a STALE clear (outside the window) is NOT a flip-flop
    assert flip_flop_cells({(6, 9)}, {(6, 9): 3}, 11) == set()
    # only the bounced cell of a mixed block set is flagged
    assert flip_flop_cells({(6, 9), (2, 2)}, {(6, 9): 10}, 11) == {(6, 9)}


def test_block_learn_decision_retries_once_before_learning_a_wall():
    """Purpose: a candidate cell is RETRIED on its first block (transient-obstacle
    tolerance) and only LEARNED once it has blocked more than the retry count; an
    already-learned cell is ignored.

    Expected feedback: pass proves a MOVING obstacle (e.g. the (6,9) patroller) is not
    frozen into the wall set on a single block — the retry gives it a step to clear. Fail
    means transient blocks pollute the static wall model (learn->unlearn churn / false
    walls)."""
    block_count = {}
    # first block of (6,8): retry, not learned
    to_learn, to_retry = block_learn_decision({(6, 8)}, set(), block_count)
    assert to_learn == set() and to_retry == {(6, 8)} and block_count[(6, 8)] == 1
    # second block of the SAME cell: now learned
    to_learn, to_retry = block_learn_decision({(6, 8)}, set(), block_count)
    assert to_learn == {(6, 8)} and to_retry == set()
    # a cell already in learned_walls is skipped entirely
    to_learn, to_retry = block_learn_decision({(7, 2)}, {(7, 2)}, block_count)
    assert to_learn == set() and to_retry == set()


def test_joint_reset_hazards_detects_the_teleport_and_names_the_targets():
    """Purpose: a JOINT soft-reset (both actors teleport to a home far from their
    previous positions AND their predicted targets) is detected, and the cells the plan
    tried to ENTER (the predicted targets) are returned as hazards.

    Expected feedback: pass proves the hazard the grounding never saw (gold avoided it)
    is learned online and routed around on recompile. Fail means the reset is treated as
    a wall (wrong) or as ordinary motion (loops)."""
    # predicted a downward move to (9,2)/(9,10); observed a teleport to home (3,5)/(3,8)
    assert joint_reset_hazards(((9, 2), (9, 10)), [(8, 2), (8, 10)], [(3, 5), (3, 8)]) == {(9, 2), (9, 10)}
    # ordinary one-cell motion toward the predicted cells -> NOT a reset
    assert joint_reset_hazards(((9, 2), (9, 10)), [(8, 2), (8, 10)], [(9, 2), (9, 10)]) == set()
    # nobody moved -> not a reset
    assert joint_reset_hazards(((9, 2), (9, 10)), [(8, 2), (8, 10)], [(8, 2), (8, 10)]) == set()


def test_unconfirmed_directions_lists_the_missing_actor_edges():
    """Purpose: after a partial sweep, unconfirmed_directions reports exactly the
    (actor, direction) edges not yet acquired — the re-probe targets when a plan over
    the confirmed subset does not reach the goal.

    Expected feedback: pass proves the driver can name which edges are missing (so a
    partial table is planned over, not rejected). Fail means the driver cannot tell a
    confirmed subset from a complete one."""
    gs = GroundingService()
    assert unconfirmed_directions(gs) == {(aid, a) for aid in ("actor_a", "actor_b") for a in (1, 2, 3, 4)}
    # confirm the down/column edges for both actors, leaving both actors' up (1) open
    sim = _MoveSim()
    discover_deltas(gs, sim.frame(), sim.probe, budget=30, directions=(2, 3, 4))
    missing = unconfirmed_directions(gs)
    assert missing == {("actor_a", 1), ("actor_b", 1)}  # only the un-swept direction remains
