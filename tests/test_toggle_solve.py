"""Interactive GF(2) toggle-solve: indicator decode, locality filter, end-to-end.

These cover the round-7 ft09 fix: the toggle board's target is a *pattern*
dictated by a central indicator (not homogeneity), measured interactively and
solved within a move budget. The pure pieces are unit-tested; a synthetic env
proves the GeneralAgent clears a lights/indicator board end-to-end with no game
id / title and no internals.
"""

from __future__ import annotations

import numpy as np

from admorphiq.general_agent import GeneralAgent, _is_local_toggle
from admorphiq.primitives.pattern_match import (
    build_stencil,
    indicator_flip_sets,
)
from admorphiq.strategies.inferential import _gf2_solve

# ── indicator decode ──────────────────────────────────────────────────────────


def _ring_with_indicator(pitch: int = 16) -> tuple[np.ndarray, list[tuple[int, int]], set]:
    """Build a frame: 8-cell ring (color 9) around a central indicator.

    The indicator centre is colour 8; its 8 directional sub-cells carry marker 0
    (for the cells that must flip) or marker 2 (leave). Sub-cell spacing matches
    the decoder's ``pitch // 4`` sampling. Returns (layer, ring_cells, want_flip).
    """
    cx = cy = 32
    layer = np.full((64, 64), 5, dtype=np.int32)
    centres = [
        (cx + sx * pitch, cy + sy * pitch)
        for sy in (-1, 0, 1)
        for sx in (-1, 0, 1)
        if not (sx == 0 and sy == 0)
    ]
    for (x, y) in centres:
        layer[y - 3 : y + 3, x - 3 : x + 3] = 9
    off = pitch // 4
    # cells that must flip = the four with a non-positive x offset (left col + ...)
    want = {(x, y) for (x, y) in centres if x <= cx}
    layer[cx - 1 : cx + 1, cy - 1 : cy + 1] = 8  # indicator centre
    for (x, y) in centres:
        sx = (x > cx) - (x < cx)
        sy = (y > cy) - (y < cy)
        marker = 0 if (x, y) in want else 2
        my, mx = cy + sy * off, cx + sx * off
        layer[my - 1 : my + 1, mx - 1 : mx + 1] = marker
    return layer, centres, want


def test_indicator_flip_sets_partitions_ring_by_marker():
    """Purpose: indicator_flip_sets splits ring cells into the two marker groups,
    one of which is exactly the cells the indicator says to flip.

    Expected feedback: PASS proves the toggle solver can recover a pattern target
    (not just homogeneity) from the frame; FAIL means ft09-class boards have no
    correct candidate to try and cannot clear within budget.
    """
    layer, ring, want = _ring_with_indicator()
    groups = indicator_flip_sets(layer, ring)
    assert len(groups) == 2
    as_sets = [set(g) for g in groups]
    assert want in as_sets
    # The two groups partition the ring.
    assert as_sets[0] | as_sets[1] == set(ring)
    assert as_sets[0] & as_sets[1] == set()


def test_indicator_flip_sets_uniform_field_returns_empty():
    """Purpose: with a single marker value (no indicator pattern), the decoder
    declines so the caller falls back to the homogeneity planner.

    Expected feedback: PASS proves we do not fabricate a phantom pattern target
    on a plain lights-out board; FAIL means wasted budget on bogus candidates.
    """
    cx = cy = 32
    layer = np.full((64, 64), 5, dtype=np.int32)
    ring = [
        (cx + sx * 16, cy + sy * 16)
        for sy in (-1, 0, 1)
        for sx in (-1, 0, 1)
        if not (sx == 0 and sy == 0)
    ]
    for (x, y) in ring:
        layer[y - 3 : y + 3, x - 3 : x + 3] = 9
    # all directional markers identical (value 7) -> single group -> empty
    off = 4
    for (x, y) in ring:
        sx = (x > cx) - (x < cx)
        sy = (y > cy) - (y < cy)
        layer[cy + sy * off - 1 : cy + sy * off + 1, cx + sx * off - 1 : cx + sx * off + 1] = 7
    assert indicator_flip_sets(layer, ring) == []


# ── locality filter ───────────────────────────────────────────────────────────


def test_is_local_toggle_accepts_compact_change_at_click():
    """Purpose: a small flipped block centred on the click is a real toggle.

    Expected feedback: PASS proves interactive measurement keeps genuine buttons;
    FAIL means the solver would discard the cells it needs.
    """
    before = np.full((64, 64), 5, dtype=np.int32)
    after = before.copy()
    after[30:36, 30:36] = 8  # 36 px block centred ~ (32,32)
    assert _is_local_toggle(before, after, 32, 32) is True


def test_is_local_toggle_rejects_far_and_global_changes():
    """Purpose: a far-away counter tick or a whole-frame animation is NOT a cell
    toggle.

    Expected feedback: PASS proves HUD / first-level animation cannot inject
    phantom cells that pollute the indicator centroid and burn the move budget;
    FAIL means measurement is corrupted on games with on-screen timers.
    """
    before = np.full((64, 64), 5, dtype=np.int32)
    far = before.copy()
    far[2:5, 60:63] = 8  # change far from the click point
    assert _is_local_toggle(before, far, 32, 32) is False
    glob = before.copy()
    glob[:, :] = 8  # whole-frame flash
    assert _is_local_toggle(before, glob, 32, 32) is False
    assert _is_local_toggle(before, before.copy(), 32, 32) is False  # no change


# ── stencil-from-measurements feeding GF(2) ────────────────────────────────────


def test_build_stencil_then_gf2_solve_round_trips():
    """Purpose: a stencil reconstructed from self-inverse click probes feeds the
    GF(2) solver to recover the click subset for a target flip vector.

    Expected feedback: PASS proves the measure -> A -> solve(Ax=b) chain is sound
    on an identity board (each click flips only itself); FAIL means a measured
    board cannot be solved even when the maths is exercised in isolation.
    """
    cells = [(10, 10), (20, 10), (30, 10)]
    base = np.full((40, 40), 5, dtype=np.int32)
    for (x, y) in cells:
        base[y - 2 : y + 3, x - 2 : x + 3] = 9  # 5x5 fills the class patch
    probes = []
    for (x, y) in cells:
        after = base.copy()
        after[y - 2 : y + 3, x - 2 : x + 3] = 8  # this click flips only itself
        probes.append({"x": x, "y": y, "before": base, "after": after})
    stencil = build_stencil(cells, probes)
    A = np.asarray(stencil["A"])
    assert np.array_equal(A, np.eye(3, dtype=A.dtype))
    b = np.array([1, 0, 1], dtype=np.uint8)
    x = _gf2_solve(A, b)
    assert np.array_equal(x, b)  # identity: solution == target


# ── end-to-end agent on a synthetic indicator board ────────────────────────────


class _State:
    def __init__(self, name: str) -> None:
        self.name = name


class _ToggleBoard:
    """Minimal frame-emitting env: indicator board, click flips a tile 9<->8.

    Wins (levels_completed -> 1) when the four indicator-marked cells are colour
    8 and the rest are 9. No move budget (the agent must still clear it). Mirrors
    the ft09 mechanic from frame observations only.
    """

    def __init__(self) -> None:
        layer, ring, want = _ring_with_indicator()
        self._base = layer
        self.ring = ring
        self.want = want
        self.state = {c: 9 for c in ring}
        self.levels_completed = 0

    def _render(self) -> np.ndarray:
        layer = self._base.copy()
        for (x, y), col in self.state.items():
            layer[y - 3 : y + 3, x - 3 : x + 3] = col
        return layer

    @property
    def frame(self) -> np.ndarray:
        return self._render()[None, :, :]

    @property
    def available_actions(self) -> list[int]:
        return [6]

    def apply(self, action) -> None:
        data = getattr(action, "action_data", None)
        if data is None:
            return
        d = data.model_dump() if hasattr(data, "model_dump") else data
        x, y = int(d.get("x", -1)), int(d.get("y", -1))
        # nearest ring tile within 3 px
        for (cx, cy) in self.ring:
            if abs(cx - x) <= 3 and abs(cy - y) <= 3:
                self.state[(cx, cy)] = 8 if self.state[(cx, cy)] == 9 else 9
                break
        if all(self.state[c] == (8 if c in self.want else 9) for c in self.ring):
            self.levels_completed = 1

    def obs(self):
        board = self

        class _Obs:
            frame = board.frame
            available_actions = [6]
            levels_completed = board.levels_completed
            state = _State("WIN" if board.levels_completed else "NOT_FINISHED")

        return _Obs()


def test_general_agent_clears_indicator_toggle_board():
    """Purpose: the full GeneralAgent (discovery -> pattern -> measure -> solve)
    clears a synthetic indicator/lights board end-to-end, no game id, no
    internals.

    Expected feedback: PASS proves the ft09-class fix works through the real
    agent FSM (not just the helpers); FAIL means the wiring between measurement
    and the candidate-solve loop is broken.
    """
    agent = GeneralAgent(seed=0)
    board = _ToggleBoard()
    cleared = False
    for _ in range(agent.MAX_ACTIONS):
        frame = board.obs()
        if board.levels_completed >= 1:
            cleared = True
            break
        if agent.is_done([], frame):
            break
        action = agent.choose_action([], frame)
        board.apply(action)
    assert cleared, "agent failed to clear the indicator toggle board"
