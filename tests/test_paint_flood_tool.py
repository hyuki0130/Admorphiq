"""Contract tests for the generic paint-flood tool (su15-class)."""

from __future__ import annotations

import numpy as np

from admorphiq.tools.paint_flood import (
    detect_flood_mechanic,
    propose_fill_clicks,
)


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
