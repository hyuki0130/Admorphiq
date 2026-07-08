"""Contract tests for the generic paint-flood tool (su15-class)."""

from __future__ import annotations

import numpy as np

from admorphiq.tools.base import Tool
from admorphiq.tools.paint_flood import (
    PaintFloodTool,
    detect_flood_mechanic,
    propose_fill_clicks,
)
from admorphiq.types import FrameData


def _click_transition(fill_region: list[tuple[int, int]], color: int, size: int = 8):
    """A synthetic click transition: a background region becomes `color`."""
    before = np.zeros((size, size), dtype=np.int16)
    after = before.copy()
    for y, x in fill_region:
        after[y, x] = color
    return before, after


def test_detect_flood_mechanic_from_click_transitions():
    """Purpose: the detector must recognize the 'click fills a background region
    with one color' mechanic and report the correct fill color, from click
    transitions only.

    Expected feedback: pass ⇒ the tool triggers on the right games and knows the
    fill color to plan with; fail ⇒ paint games are not recognized generically.
    """
    region = [(1, 1), (1, 2), (2, 1), (2, 2)]
    frames, nexts, acts = [], [], []
    for _ in range(5):
        b, a = _click_transition(region, color=5)
        frames.append(b)
        nexts.append(a)
        acts.append(6)  # ACTION6 click (idx >= 5)
    m = detect_flood_mechanic(np.array(frames), np.array(acts), np.array(nexts))
    assert m.detected is True
    assert m.fill_color == 5
    assert m.confidence == 1.0
    assert m.mean_fill_cells == 4.0


def test_detect_rejects_non_flood_games():
    """Purpose: a game where clicks do NOT paint background must NOT trigger the
    tool (no false positive → the orchestrator won't waste it).

    Expected feedback: pass ⇒ detected=False on non-paint dynamics; fail ⇒ the
    tool mis-fires on unrelated games.
    """
    frames, nexts, acts = [], [], []
    for _ in range(5):
        b = np.zeros((8, 8), dtype=np.int16)
        a = b.copy()  # click changes nothing
        frames.append(b)
        nexts.append(a)
        acts.append(6)
    m = detect_flood_mechanic(np.array(frames), np.array(acts), np.array(nexts))
    assert m.detected is False


def test_propose_fill_clicks_targets_largest_background_regions():
    """Purpose: given a frame with background regions, propose click points
    (x=col, y=row) at region centroids, largest first, on actual background
    cells — the plan to complete the fill.

    Expected feedback: pass ⇒ the proposed clicks land inside uncovered regions
    biggest-first (efficient fill); fail ⇒ clicks miss or waste actions.
    """
    f = np.full((8, 8), 5, dtype=np.int16)   # mostly filled
    f[0:3, 0:3] = 0                            # a 9-cell background block
    f[6, 6] = 0                                # a 1-cell background speck
    clicks = propose_fill_clicks(f, fill_color=5)
    assert clicks, "should propose at least one click"
    # first click targets the largest region (the 3x3 block) and is on background
    x0, y0 = clicks[0]
    assert f[y0, x0] == 0
    assert 0 <= x0 <= 2 and 0 <= y0 <= 2
    # the speck is also covered, later
    assert (6, 6) in clicks


def test_no_game_ids_in_tool():
    """Purpose: the tool must be game-agnostic (generality guard).

    Expected feedback: pass ⇒ transfers to unseen games; fail ⇒ a game-specific
    leak crept in.
    """
    import admorphiq.tools.paint_flood as mod
    src = open(mod.__file__).read().lower()
    for tok in ("su15\"", "su15'", "game_id", "game_title"):
        assert tok not in src


def _grid(size: int = 8) -> np.ndarray:
    return np.zeros((size, size), dtype=np.int16)


def test_paint_flood_tool_implements_base_protocol():
    """Purpose: PaintFloodTool must satisfy the base.Tool structural protocol
    (name + detect/reset/observe/propose) so the orchestrator can run it
    uniformly alongside every other tool.

    Expected feedback: pass ⇒ the harness can dispatch to this tool generically;
    fail ⇒ the lifecycle wiring is incomplete or mis-shaped.
    """
    tool = PaintFloodTool()
    assert isinstance(tool, Tool)
    assert tool.name == "paint"


def test_detect_is_high_after_observing_a_fill_click():
    """Purpose: after observe() records a click that flood-filled a background
    region, and the next frame confirming that fill arrives via detect()'s obs,
    confidence must be high -- this is the ONLY evidence the tool needs to
    self-select as the right tool for the game.

    Expected feedback: pass ⇒ the tool routes correctly on a genuine paint game;
    fail ⇒ the observe->detect evidence pipeline is broken.
    """
    tool = PaintFloodTool()
    before = _grid()
    after = before.copy()
    for y, x in ((1, 1), (1, 2), (2, 1), (2, 2)):
        after[y, x] = 5
    tool.observe(before, (6, (1, 1)), changed=True)
    confidence = tool.detect(frames=[], obs=FrameData(frame=after))
    assert confidence >= 0.9
    assert tool._fill_color == 5


def test_detect_is_low_with_no_fill_evidence():
    """Purpose: with no observed click-fill transitions (a fresh tool, or a
    click game where clicks don't paint background), detect() must stay at
    0.0 -- the measured caveat that paint is NOT a fit for every click game
    (su15 0/9) requires this to be conservative by default.

    Expected feedback: pass ⇒ no false-positive routing onto non-paint games;
    fail ⇒ the tool over-triggers and wastes the orchestrator's pick.
    """
    tool = PaintFloodTool()
    # No observe() calls at all -- nothing accumulated yet.
    assert tool.detect(frames=[], obs=FrameData(frame=_grid())) == 0.0

    # A click that recolours an existing FOREGROUND cell (not a background fill):
    # no changed cell's OLD colour is background, so there is no fill source.
    before = _grid()
    before[3, 3] = 3
    after = before.copy()
    after[3, 3] = 4
    tool.observe(before, (6, (3, 3)), changed=True)
    confidence = tool.detect(frames=[], obs=FrameData(frame=after))
    assert confidence == 0.0


def test_observe_ignores_non_click_and_no_change_actions():
    """Purpose: only ACTION6 clicks that actually changed the frame are
    candidate flood evidence -- a directional move (action 1-5) or a no-op
    click must never seed a pending transition.

    Expected feedback: pass ⇒ detect() stays conservative for movement/no-op
    actions; fail ⇒ unrelated actions could be mistaken for fills.
    """
    tool = PaintFloodTool()
    before = _grid()
    after = before.copy()
    after[1, 1] = 5
    tool.observe(before, (1, None), changed=True)  # directional move, not a click
    assert tool.detect(frames=[], obs=FrameData(frame=after)) == 0.0

    tool2 = PaintFloodTool()
    tool2.observe(before, (6, (1, 1)), changed=False)  # click, but nothing changed
    assert tool2.detect(frames=[], obs=FrameData(frame=after)) == 0.0


def test_reset_clears_accumulated_evidence():
    """Purpose: reset() (called by the harness on level transition) must drop
    all accumulated click evidence and the inferred fill colour, so a new
    level starts with the same conservative prior as a fresh tool.

    Expected feedback: pass ⇒ stale evidence from a prior level never leaks
    into the next level's routing decision; fail ⇒ a level-boundary bug.
    """
    tool = PaintFloodTool()
    before = _grid()
    after = before.copy()
    for y, x in ((1, 1), (1, 2), (2, 1), (2, 2)):
        after[y, x] = 5
    tool.observe(before, (6, (1, 1)), changed=True)
    tool.detect(frames=[], obs=FrameData(frame=after))
    assert tool._fill_color == 5

    tool.reset()
    assert tool._fill_color == -1
    assert tool.detect(frames=[], obs=FrameData(frame=after)) == 0.0


def test_propose_returns_click_steps_toward_the_fill():
    """Purpose: once the fill colour is known, propose() must return ACTION6
    click Steps ``(6, (x, y))`` targeting the largest remaining background
    region -- the actual plan the orchestrator executes.

    Expected feedback: pass ⇒ propose() emits harness-executable Steps that
    make fill progress; fail ⇒ the plan is malformed or targets nothing.
    """
    tool = PaintFloodTool()
    before = _grid()
    after = before.copy()
    for y, x in ((1, 1), (1, 2), (2, 1), (2, 2)):
        after[y, x] = 5
    tool.observe(before, (6, (1, 1)), changed=True)
    tool.detect(frames=[], obs=FrameData(frame=after))
    assert tool._fill_color == 5

    # A frame with one big remaining background block to fill.
    frame = np.full((8, 8), 5, dtype=np.int16)
    frame[4:7, 4:7] = 0
    steps = tool.propose(frames=[], obs=FrameData(frame=frame))
    assert steps, "should propose at least one click step"
    action_id, coord = steps[0]
    assert action_id == 6
    assert coord is not None
    x, y = coord
    assert frame[y, x] == 0


def test_propose_probes_when_mechanic_not_yet_confirmed():
    """Purpose: before any fill evidence has been observed, propose() must
    still return a probing click (targeting a background region) rather than
    an empty list -- the tool needs to elicit its own detection evidence.

    Expected feedback: pass ⇒ a fresh tool can bootstrap detection by acting;
    fail ⇒ the tool stalls with no plan until told externally what to do.
    """
    tool = PaintFloodTool()
    frame = np.full((8, 8), 5, dtype=np.int16)
    frame[0:2, 0:2] = 0
    steps = tool.propose(frames=[], obs=FrameData(frame=frame))
    assert steps
    action_id, coord = steps[0]
    assert action_id == 6
    assert coord is not None
