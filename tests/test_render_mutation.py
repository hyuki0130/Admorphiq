"""Contract tests for the render-mutation transfer instrument.

⛔ WHY THESE EXIST IN THIS SHAPE. Rule 7q and the "instrument that lies toward nothing
here" family: every checker is run on input whose verdict is already known, in BOTH
directions. So the suite carries a colour-BLIND fake agent (must be unaffected) and a
colour-KEYED fake agent (must be affected) and asserts the instrument separates them.
An instrument that only ever sees clean input cannot be distinguished from one that
measures nothing.
"""

from __future__ import annotations

import numpy as np
import pytest
from arcengine import GameAction
from arcengine.enums import FrameDataRaw

from admorphiq.render_mutation import (
    N_COLOURS,
    ColourPermutation,
    MutantAgent,
    RenderMutation,
    Translate,
    build,
    derangement,
    fixing,
)


def _obs(layer: np.ndarray) -> FrameDataRaw:
    obs = FrameDataRaw()
    obs.frame = [layer]
    return obs


class _BlindAgent:
    """Reads STRUCTURE only: clicks the centroid of the largest non-background region.

    Purpose: the instrument's POSITIVE control for "a mechanic-reading tool is
    unaffected". Its decision is invariant under any bijective relabelling of colours,
    so if the instrument reports a difference for this agent the instrument is wrong.
    """

    def __init__(self) -> None:
        self.seen: list[tuple[int, int]] = []

    def is_done(self, frames, obs) -> bool:  # noqa: ANN001
        return False

    def choose_action(self, frames, obs):  # noqa: ANN001
        g = np.asarray(obs.frame[0])
        bg = int(np.bincount(g.reshape(-1), minlength=N_COLOURS).argmax())
        ys, xs = np.nonzero(g != bg)
        act = GameAction.ACTION6
        act.set_data({"game_id": "", "x": int(xs.mean()), "y": int(ys.mean())})
        self.seen.append((int(xs.mean()), int(ys.mean())))
        return act


class _ColourKeyedAgent:
    """Reads the LITERAL colour 4: clicks the first cell whose value is 4.

    Purpose: the instrument's NEGATIVE control. Under a colour permutation this agent
    must click somewhere else (or nowhere), because the cells labelled 4 have moved.
    A clean result from the blind agent means nothing unless this one is dirty.
    """

    def __init__(self) -> None:
        self.seen: list[tuple[int, int]] = []

    def is_done(self, frames, obs) -> bool:  # noqa: ANN001
        return False

    def choose_action(self, frames, obs):  # noqa: ANN001
        g = np.asarray(obs.frame[0])
        ys, xs = np.nonzero(g == 4)
        x, y = (int(xs[0]), int(ys[0])) if len(xs) else (0, 0)
        act = GameAction.ACTION6
        act.set_data({"game_id": "", "x": x, "y": y})
        self.seen.append((x, y))
        return act


def _board() -> np.ndarray:
    g = np.zeros((64, 64), dtype=np.int8)
    g[10:20, 10:20] = 4
    g[40:44, 50:54] = 7
    return g


def test_derangement_is_a_fixed_point_free_bijection() -> None:
    """Purpose: the colour arm must move EVERY colour, or "identical" is unreadable.

    Expected feedback: a failure means the permutation leaves some colour alone, so a
    game using only those colours would score identically for a reason that has
    nothing to do with the tools — the exact false-negative rule 7q warns about.
    """
    perm = derangement()
    assert sorted(perm) == list(range(N_COLOURS))
    assert all(perm[c] != c for c in range(N_COLOURS))


def test_fixing_preserves_the_bijection_and_pins_the_background() -> None:
    """Purpose: the background-preserving arm must still be a bijection.

    Expected feedback: a failure means the two colour arms are not comparable, so the
    "does the tool key on the background literal specifically" question cannot be
    answered from them.
    """
    perm = derangement()
    for bg in range(N_COLOURS):
        out = fixing(perm, bg)
        assert sorted(out) == list(range(N_COLOURS))
        assert out[bg] == bg
        assert sum(out[c] == c for c in range(N_COLOURS)) == 1


def test_colour_permutation_preserves_structure_exactly() -> None:
    """Purpose: prove the mutation is meaning-preserving, not merely different.

    Expected feedback: the equality pattern of the board (which cells match which)
    must be identical before and after. If it is not, the mutation changed the picture
    rather than its labels, and every number the instrument produces is void.
    """
    g = _board()
    mut = ColourPermutation(derangement())
    out = mut.apply([g], {"violations": []})[0]
    assert not np.array_equal(out, g)
    same_before = (g.reshape(-1)[:, None] == g.reshape(-1)[None, ::97])
    same_after = (out.reshape(-1)[:, None] == out.reshape(-1)[None, ::97])
    assert np.array_equal(same_before, same_after)


def test_mutant_agent_reports_applied_and_counts_what_changed() -> None:
    """Purpose: the instrument must be able to say the mutation actually happened.

    Expected feedback: ``verdict == "applied"`` with a non-zero cell count is the only
    state in which a score comparison is readable.
    """
    agent = MutantAgent(_BlindAgent(), build("cperm"))
    agent.choose_action([], _obs(_board()))
    rep = agent.close()
    assert rep["verdict"] == "applied"
    assert rep["frames_changed"] == 1
    assert rep["cells_changed"] == 64 * 64
    assert rep["background_first_frame"] == 0


def test_mutant_agent_reports_INERT_rather_than_passing_silently() -> None:
    """Purpose: the refusal path. An inert mutation must not read as a clean transfer.

    A uniform board under the background-fixing arm changes nothing, which would score
    identically for a reason that says nothing about the tools. This is the fail-open
    shape that has cost this campaign eight instruments.

    Expected feedback: ``verdict == "inert"`` — the game is excluded from the verdict,
    not counted as a pass.
    """
    agent = MutantAgent(_BlindAgent(), build("cpermbg"))
    agent.is_done([], _obs(np.full((64, 64), 3, dtype=np.int8)))
    rep = agent.close()
    assert rep["verdict"] == "inert"
    assert rep["frames_changed"] == 0


def test_the_blind_agent_is_UNAFFECTED_and_the_colour_keyed_one_IS() -> None:
    """Purpose: both directions of the instrument's own control (rule 7ai).

    Expected feedback: the structure-reading agent must issue the identical click
    under the mutation, and the colour-keyed agent must not. If the first fails the
    instrument corrupts good tools; if the second fails the instrument measures
    nothing and every "identical" it prints is empty.
    """
    board = _board()
    blind_plain, blind_mut = _BlindAgent(), _BlindAgent()
    blind_plain.choose_action([], _obs(board))
    MutantAgent(blind_mut, build("cperm")).choose_action([], _obs(board))
    assert blind_plain.seen == blind_mut.seen

    keyed_plain, keyed_mut = _ColourKeyedAgent(), _ColourKeyedAgent()
    keyed_plain.choose_action([], _obs(board))
    MutantAgent(keyed_mut, build("cperm")).choose_action([], _obs(board))
    assert keyed_plain.seen != keyed_mut.seen


def test_the_game_never_sees_a_mutated_frame_or_a_mutated_click() -> None:
    """Purpose: the validity argument, asserted rather than asserted-in-prose.

    The wrapper must (a) leave the caller's own observation object untouched, so the
    scorer reads the real ``levels_completed`` and the engine the real board, and
    (b) hand back a click in GAME coordinates under a translation.

    Expected feedback: a failure here means the mutation reached the game, at which
    point the level structure and the human baseline are no longer the right
    denominator and no number from the instrument is valid.
    """
    board = np.zeros((64, 64), dtype=np.int8)
    board[10:20, 10:20] = 4
    obs = _obs(board)
    agent = MutantAgent(_ColourKeyedAgent(), Translate(3, 3))
    action = agent.choose_action([], obs)

    assert np.array_equal(np.asarray(obs.frame[0]), board)  # caller's frame untouched
    # The agent saw the block at (13,13); the engine must receive (10,10).
    assert (action.action_data.x, action.action_data.y) == (10, 10)
    assert agent.close()["verdict"] == "applied"


def test_translate_REFUSES_when_it_would_destroy_board_content() -> None:
    """Purpose: a translation that pushes content off the canvas changes the MEANING.

    Expected feedback: ``verdict == "invalid"`` with a named violation. Reporting such
    a game's lower score as a transfer failure would be the instrument's worst error —
    a broken mutation and a brittle tool produce the same number.
    """
    board = np.zeros((64, 64), dtype=np.int8)
    board[63, :] = 5  # a bottom edge that a downward shift would delete
    agent = MutantAgent(_BlindAgent(), Translate(1, 0))
    agent.is_done([], _obs(board))
    rep = agent.close()
    assert rep["verdict"] == "invalid"
    assert "destroy board content" in rep["violations"][0]


def test_translate_round_trips_the_click_when_valid() -> None:
    """Purpose: the conjugation is exact, so the agent's intent survives the mutation.

    Expected feedback: forward-then-inverse must be the identity on every in-range
    coordinate; a failure means clicks land somewhere the agent did not choose and the
    run measures a different agent.
    """
    mut = Translate(2, -3)
    rep = {"violations": []}
    for y in range(0, 64, 7):
        for x in range(0, 64, 7):
            ax, ay = mut.to_agent_xy(x, y)
            if 0 <= ax < 64 and 0 <= ay < 64:
                assert mut.to_game_xy(ax, ay, rep) == (x, y)
    assert rep["violations"] == []


def test_build_refuses_an_unknown_arm() -> None:
    """Purpose: no silent default. An unrecognised arm must not fall back to identity.

    Expected feedback: a KeyError naming the real arms. A silent identity fallback
    would report a perfect transfer over a mutation that never ran.
    """
    with pytest.raises(KeyError):
        build("cprem")
    assert isinstance(build("identity"), RenderMutation)


def test_identity_arm_is_labelled_control_not_applied() -> None:
    """Purpose: the control arm must be distinguishable from a real mutation.

    Expected feedback: ``verdict == "control"``. If the control were labelled
    "applied", a run whose mutation silently failed to build would look like a
    successful transfer measurement.
    """
    agent = MutantAgent(_BlindAgent(), build("identity"))
    agent.is_done([], _obs(_board()))
    assert agent.close()["verdict"] == "control"
