"""Regression fixtures pinning the sk48 frame parse for agent levels 0-3.

Purpose: the L0-L3 parse (cells, heads/bodies, partner count, arena, gates,
obstacles, budget) is what the faithful-simulator A* clears super-human (the
4/8 @ 0.2778 floor). Any change to the delicate _parse_cells / _parse_walls
must keep these BYTE-IDENTICAL. This test forces each source level dev-time and
asserts the serialized parse matches the recorded snapshot.

Expected feedback: a green run means the parser still reconstructs L0-L3 exactly
as when the 4/8 floor was measured; a failure means a parser change perturbed a
floor level and must be reverted or scoped tighter before it can ship.
"""

from __future__ import annotations

import pytest

from admorphiq.adapters25.base import canonical_layer
from admorphiq.adapters25.sk48 import _parse_state

arc_agi = pytest.importorskip("arc_agi")
from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

# Serialized _parse_state snapshots captured at the 4/8 floor (R59, before the
# occluded-cell + wall parser changes). Format per level:
# cells: sorted (x, y, colour); heads: sorted (x, y, colour, rot, body_len);
# n_partner; arena (x, y, w, h); gates: sorted (x, y, w, h); obstacles; budget.
_EXPECTED = {
    0: {
        "cells": [(26, 56, 8), (32, 56, 14), (38, 56, 9), (41, 18, 8), (41, 24, 9), (41, 30, 14)],
        "heads": [(11, 36, 6, 0, 2), (20, 56, 6, 0, 4)],
        "n_partner": 1, "arena": (17, 12, 30, 30), "gates": [(13, 14, 2, 22)],
        "obstacles": [], "budget": 196,
    },
    1: {
        "cells": [(23, 56, 8), (29, 24, 14), (29, 56, 12), (35, 24, 9), (35, 56, 9),
                  (41, 24, 12), (41, 56, 14), (47, 24, 8)],
        "heads": [(5, 42, 6, 0, 2), (17, 56, 6, 0, 5)],
        "n_partner": 1, "arena": (11, 6, 42, 42), "gates": [(7, 8, 2, 34)],
        "obstacles": [], "budget": 196,
    },
    2: {
        "cells": [(23, 56, 8), (29, 6, 14), (29, 12, 9), (29, 18, 8), (29, 24, 12),
                  (29, 56, 12), (35, 56, 9), (41, 56, 14)],
        "heads": [(5, 42, 6, 0, 2), (17, 56, 6, 0, 5), (29, 0, 11, 90, 5)],
        "n_partner": 1, "arena": (11, 6, 42, 42), "gates": [(7, 8, 2, 34)],
        "obstacles": [], "budget": 196,
    },
    3: {
        "cells": [(11, 42, 9), (17, 42, 14), (17, 56, 8), (23, 42, 8), (23, 56, 12),
                  (29, 42, 12), (41, 56, 9), (47, 56, 14)],
        "heads": [(5, 42, 6, 0, 5), (11, 56, 11, 0, 3), (23, 0, 10, 90, 4),
                  (35, 0, 11, 90, 4), (35, 56, 10, 0, 3)],
        "n_partner": 2, "arena": (11, 6, 42, 42),
        "gates": [(7, 8, 2, 34), (25, 5, 2, 19), (37, 5, 2, 19)],
        "obstacles": [], "budget": 196,
    },
}


def _serial(state):
    cells = sorted((c.x, c.y, c.color) for c in state["cells"])
    heads = sorted(
        (h.x, h.y, h.color, h.rot, len(next(b for hh, b in state["bodies"] if hh is h)))
        for h in state["heads"]
    )
    ar = state["arena"]
    return {
        "cells": cells, "heads": heads, "n_partner": len(state["partner"]),
        "arena": (ar.x, ar.y, ar.w, ar.h),
        "gates": sorted((g.x, g.y, g.w, g.h) for g in state["gates"]),
        "obstacles": sorted((o.x, o.y, o.w, o.h) for o in state["obstacles"]),
        "budget": state["budget"],
    }


def test_sk48_sim_lockstep_l4_wall():
    """The sim's wall + move model must stay FAITHFUL to the live engine on
    agent-L4 (source Level 5, the wall level). Drives a maneuver that exercises
    the wall + side-gates on both the live game and the reconstructed sim and
    asserts the control body + cells match step-for-step.

    Expected feedback: green = the wall/side-push model still matches the engine
    (so the R59 topological verdict — L4 unsolvable-as-modelled — stands on a
    faithful sim, not a sim bug); a failure means a sim change broke fidelity and
    the wall handling must be re-derived against the live engine.
    """
    from admorphiq.adapters25.sk48 import _parse_state, _Sim

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    gid = next(e.game_id for e in arcade.get_environments() if "sk48" in e.game_id)
    penv = arcade.make(gid)
    penv._game.set_level(4)
    sim = _Sim(_parse_state(canonical_layer(penv.step(GameAction.ACTION7))))
    env = arcade.make(gid)
    g = env._game
    g.set_level(4)
    mm = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4}

    def live():
        top = next(t for t in g.xpmcmtbcv)
        body = sorted((s.x, s.y) for s in g.mwfajkguqx[top])
        cells = sorted((c.x, c.y, int(c.pixels[1, 1])) for c in g.vbelzuaian)
        return body, cells

    def simstate():
        c = next(h for h in sim.heads if id(h) in sim.partner)
        return sorted((s.x, s.y) for s in sim.bodies[id(c)]), sorted((cc.x, cc.y, cc.color) for cc in sim.cells)

    assert live() == simstate(), "L4 init parse != live"
    for mv in (3, 3, 3, 4, 4, 4, 4, 1, 1, 2, 2, 4, 3, 1, 2, 4):
        env.step(mm[mv])
        sim.step(mv)
        assert live() == simstate(), f"sim diverged from live after move {mv}"


@pytest.mark.parametrize("level", sorted(_EXPECTED))
def test_sk48_floor_parse_unchanged(level):
    """The L0-L3 (source 1-4) parse must stay byte-identical to the 4/8 floor
    snapshot; a diff means a parser change perturbed a floor level."""
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    gid = next(e.game_id for e in arcade.get_environments() if "sk48" in e.game_id)
    env = arcade.make(gid)
    env._game.set_level(level)
    grid = canonical_layer(env.step(GameAction.ACTION7))
    state = _parse_state(grid)
    assert state is not None, f"L{level} parse returned None"
    got = _serial(state)
    exp = {k: [tuple(x) for x in v] if isinstance(v, list) else v for k, v in _EXPECTED[level].items()}
    assert got == exp, f"L{level} parse changed:\n got={got}\n exp={exp}"
