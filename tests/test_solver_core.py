"""Contract tests for the executable solver cores (``tools/solver_core.py``).

These prove the R93-min invariant that Codex made binding: the card the LLM
patches IS the code the tool executes (no drifting copies), and that card is
runnable inside the ``run_code`` sandbox. Two paths must agree bit-for-bit on the
same evidence — the tool's ``propose`` and the ``source_card`` text driven through
``run_code`` — and click coordinates must survive serialization into the sandbox.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field

import numpy as np
import pytest

from admorphiq.tools.code_agent import run_code
from admorphiq.tools.paint_flood import PaintFloodTool
from admorphiq.tools.solver_core import (
    arrangement_core,
    format_core_trace,
    paint_core,
    simdfs_skel_core,
    source_card,
    toggle_core,
)
from admorphiq.tools.toggle import ToggleTool
from admorphiq.types import FrameData


@dataclass
class _State:
    name: str = "NOT_FINISHED"


@dataclass
class _Obs:
    frame: np.ndarray
    available_actions: list[int] = field(default_factory=lambda: [6])
    levels_completed: int = 0
    state: _State = field(default_factory=_State)


@pytest.fixture
def bridge_on(monkeypatch):
    """Enable the kernel bridge so ``run_code`` exposes ``transitions`` (the cores
    and the xy field only reach the sandbox when HARNESS_KERNEL_API is set)."""
    monkeypatch.setenv("HARNESS_KERNEL_API", "1")


def _collect_act():
    """An ``act`` compatible with the sandbox contract that records CLICK Steps."""
    plan: list[tuple[int, tuple[int, int]]] = []

    def act(name: str, x: int | None = None, y: int | None = None) -> None:
        if x is not None and y is not None:
            plan.append((6, (int(x), int(y))))

    return plan, act


def _toggle_evidence():
    """A chained single-cell-flip lights-out: click (x, 0) flips board cell
    (row 0, col x). Returns (states, clicks, transition-dicts, tuple-transitions)."""
    clicks = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]  # (x, y)
    states = [np.zeros((8, 8), dtype=np.int64)]
    for (x, y) in clicks:
        nxt = states[-1].copy()
        nxt[y, x] ^= 1
        states.append(nxt)
    dict_trans = [
        {"action": "CLICK", "xy": [x, y], "before": states[i], "after": states[i + 1]}
        for i, (x, y) in enumerate(clicks)
    ]
    tuple_trans = [
        ("CLICK", [x, y], states[i], states[i + 1])
        for i, (x, y) in enumerate(clicks)
    ]
    return states, clicks, dict_trans, tuple_trans


def test_toggle_core_matches_tool_plan():
    """Purpose: on identical lights-out evidence, ``toggle_core``'s queued plan is
    the SAME as ``ToggleTool.propose`` — the tool genuinely delegates to the core
    (one implementation), so a patch to the card changes the tool's behaviour.

    Expected feedback: pass ⇒ card path == tool path (parity holds); fail ⇒ the
    tool and the code the LLM sees have drifted apart."""
    states, clicks, dict_trans, _ = _toggle_evidence()

    # Feed the tool the SAME transitions via its one-frame-delayed observe path.
    tool = ToggleTool()
    for i, (x, y) in enumerate(clicks):
        tool.observe(states[i], (6, (x, y)), True)
    tool.observe(states[-1], (6, (7, 7)), True)  # resolve the final click

    board = np.zeros((8, 8), dtype=np.int64)
    board[0, 1] = 1
    board[0, 3] = 1  # ON at cells covered by clicks (1,0) and (3,0)

    tool_plan = tool.propose([], _Obs(board))
    core_plan, act = _collect_act()
    toggle_core(board, dict_trans, act)

    assert tool_plan, "the tool must produce a non-empty solve plan"
    assert sorted(tool_plan) == sorted(core_plan)
    assert sorted(tool_plan) == [(6, (1, 0)), (6, (3, 0))]


def test_toggle_card_runs_in_sandbox(bridge_on):
    """Purpose: the assembled ``source_card('toggle')`` text plus a driver line is
    executable inside ``run_code`` and queues the expected solve clicks — proving
    the card is real, self-contained source the LLM can patch and run.

    Expected feedback: pass ⇒ the card runs offline in the sandbox and solves;
    fail ⇒ the LLM would be handed code that cannot execute (import/NameError)."""
    states, clicks, _, tuple_trans = _toggle_evidence()
    board = np.zeros((8, 8), dtype=np.int64)
    board[0, 1] = 1
    board[0, 3] = 1

    card = source_card("toggle")
    driver = card + "\n\ntoggle_core(current_frame, transitions, act)\n"
    res = run_code(driver, board, [], ["MOUSE"], transitions=tuple_trans)

    assert res.error == "", res.error
    assert sorted(res.actions) == [("ACTION6", (1, 0)), ("ACTION6", (3, 0))]


def test_click_xy_round_trips_into_sandbox(bridge_on):
    """Purpose: a click transition's (x, y) coordinates survive serialization into
    the sandbox ``transitions`` — the BUG-level gap this layer fixes (a solver core
    cannot rebuild stencils/fills from an action NAME alone).

    Expected feedback: pass ⇒ the sandbox sees the real click xy; fail ⇒ toggle /
    paint cores are blind to WHERE the agent clicked."""
    before = np.zeros((8, 8), dtype=np.int64)
    after = before.copy()
    after[3, 7] = 1
    res = run_code(
        "t = transitions[-1]\n"
        "print('xy', t['xy'])\n"
        "act('CLICK', t['xy'][0], t['xy'][1])\n",
        before, [], ["MOUSE"],
        transitions=[("CLICK", [7, 3], before, after)],
    )
    assert res.error == "", res.error
    assert "xy [7, 3]" in res.printed
    assert res.actions == [("ACTION6", (7, 3))]


def test_movement_transition_has_null_xy(bridge_on):
    """Purpose: a non-click (movement) transition serializes ``xy`` as None, so the
    cores correctly ignore it when rebuilding click stencils/fills.

    Expected feedback: pass ⇒ movement steps carry no phantom coordinates; fail ⇒
    the xy field is mis-populated for simple actions."""
    before = np.zeros((6, 6), dtype=np.int64)
    after = before.copy()
    after[1, 2] = 3
    res = run_code(
        "print('xy', transitions[-1]['xy'])\nact('UP')\n",
        before, [], ["UP"],
        transitions=[("UP", None, before, after)],
    )
    assert res.error == "", res.error
    assert "xy None" in res.printed


def _paint_evidence():
    """A click that flood-fills a 2x2 background block with colour 5."""
    before = np.zeros((8, 8), dtype=np.int16)
    after = before.copy()
    for y, x in ((1, 1), (1, 2), (2, 1), (2, 2)):
        after[y, x] = 5
    dict_trans = [{"action": "CLICK", "xy": [1, 1], "before": before, "after": after}]
    tuple_trans = [("CLICK", [1, 1], before, after)]
    return before, after, dict_trans, tuple_trans


def test_paint_core_matches_tool_plan():
    """Purpose: on identical fill evidence, ``paint_core``'s queued plan is the SAME
    as ``PaintFloodTool.propose`` — the tool delegates to the core (one impl).

    Expected feedback: pass ⇒ card path == tool path for paint; fail ⇒ the tool
    and the patchable core have diverged."""
    before, after, dict_trans, _ = _paint_evidence()

    tool = PaintFloodTool()
    tool.observe(before, (6, (1, 1)), changed=True)
    tool.detect([], FrameData(frame=after))  # absorbs the pending click transition

    board = np.full((8, 8), 5, dtype=np.int16)
    board[4:7, 4:7] = 0  # one 3x3 background block remaining

    tool_plan = tool.propose([], FrameData(frame=board))
    core_plan, act = _collect_act()
    paint_core(board, dict_trans, act)

    assert tool_plan, "the tool must produce a non-empty fill plan"
    assert tool_plan == core_plan
    # the single remaining background block's centroid is (x=5, y=5)
    assert tool_plan == [(6, (5, 5))]


def test_paint_card_runs_in_sandbox(bridge_on):
    """Purpose: ``source_card('paint')`` plus a driver line runs inside ``run_code``
    and queues the expected fill click — the paint core is real, self-contained,
    sandbox-runnable source.

    Expected feedback: pass ⇒ the paint card executes offline and fills; fail ⇒ the
    LLM would get un-runnable paint code."""
    before, after, _, tuple_trans = _paint_evidence()
    board = np.full((8, 8), 5, dtype=np.int16)
    board[4:7, 4:7] = 0

    card = source_card("paint")
    driver = card + "\n\npaint_core(current_frame, transitions, act)\n"
    res = run_code(driver, board, [], ["MOUSE"], transitions=tuple_trans)

    assert res.error == "", res.error
    assert res.actions == [("ACTION6", (5, 5))]


def test_source_card_is_the_real_source():
    """Purpose: the card is assembled from ``inspect.getsource`` of the live core +
    helpers — there is NO hand-maintained copy that could drift.

    Expected feedback: pass ⇒ the model sees exactly the executed code; fail ⇒ a
    parallel copy exists and the parity guarantee is void."""
    card = source_card("toggle")
    assert inspect.getsource(toggle_core) in card
    assert "def _gf2_solve" in card and "def _binarize" in card
    assert "from __future__ import annotations" in card
    paint_card = source_card("paint")
    assert inspect.getsource(paint_core) in paint_card
    arr_card = source_card("arrangement")
    assert inspect.getsource(arrangement_core) in arr_card
    # the distilled engine's two load-bearing primitives + a composed kernel
    assert "def arrangement_learn_button" in arr_card
    assert "def arrangement_plan" in arr_card
    assert "def plan_token_assignment" in arr_card
    with pytest.raises(KeyError):
        source_card("nonexistent")


def _arrangement_evidence():
    """A minimal ring-permutation board: two rotation buttons (colours 8/14), a
    4-cell colour ring, one solid marker (colour 5) and its hollow 4-corner target
    (colour 5). The single transition presses button A (click x=2,y=2) and rotates
    the ring one step (each ring cell's colour advances). Returns
    (current_frame, dict-transitions, tuple-transitions)."""
    def board(tiles):
        g = np.zeros((24, 24), dtype=np.int64)
        g[0, :] = 1  # chrome bar -> the 2nd-most-common colour (dropped as background)
        g[2:4, 2:4] = 8  # button A (rotation control)
        g[2:4, 20:22] = 14  # button B (a second, still-unpressed control)
        for (r, c), col in tiles.items():
            g[r, c] = col  # single-pixel ring tiles, distinct colours
        g[16:18, 8:10] = 5  # solid moving marker (colour 5)
        for (r, c) in ((16, 16), (16, 20), (20, 16), (20, 20)):
            g[r, c] = 5  # hollow 4-corner target frame (colour 5)
        return g

    before = board({(8, 8): 3, (8, 12): 4, (12, 12): 6, (12, 8): 7})
    after = board({(8, 8): 7, (8, 12): 3, (12, 12): 4, (12, 8): 6})  # rotated +1
    dict_trans = [{"action": "CLICK", "xy": [2, 2], "before": before, "after": after}]
    tuple_trans = [("CLICK", [2, 2], before, after)]
    return after, dict_trans, tuple_trans


def test_arrangement_core_learns_and_queues():
    """Purpose: the distilled ring-permutation engine, run directly, LEARNS a
    rotation control's per-click effect from an observed transition and QUEUES a
    sensible press sequence toward the target — the (a) learn + (b) plan halves
    the lp85 conquest delegates to.

    Expected feedback: pass ⇒ the core recovers the pressed control's ring and
    queues clicks; fail ⇒ the engine no longer learns effects / plans from raw
    frame + transition evidence."""
    current, dict_trans, _ = _arrangement_evidence()
    trace: list[str] = []
    plan, act = _collect_act()
    arrangement_core(current, dict_trans, act, trace)

    assert any("learned 1 effect-map" in line for line in trace), trace
    assert plan, "the core must queue at least one click"
    # every queued click targets a real button cell (x=col, y=row on the board).
    assert all(0 <= x < 24 and 0 <= y < 24 for _a, (x, y) in plan)


def test_arrangement_card_runs_in_sandbox(bridge_on):
    """Purpose: the assembled ``source_card('arrangement')`` — the stdlib-only
    kernel primitives + the distilled engine — is self-contained and executes
    inside ``run_code`` on a synthetic ring board, queuing the SAME clicks the
    direct core does. Proves the card the model patches IS runnable, real source.

    Expected feedback: pass ⇒ the arrangement card runs offline and drives the
    ring solver; fail ⇒ the LLM would be handed un-runnable code (import/NameError
    from an un-bundled kernel dependency)."""
    current, dict_trans, tuple_trans = _arrangement_evidence()

    direct_plan, act = _collect_act()
    arrangement_core(current, dict_trans, act)

    card = source_card("arrangement")
    driver = card + "\n\narrangement_core(current_frame, transitions, act)\n"
    res = run_code(driver, current, [], ["MOUSE"], transitions=tuple_trans)

    assert res.error == "", res.error
    assert res.actions, "the sandbox card must queue clicks"
    # card path == direct path (one implementation, no drift). ``_collect_act``
    # records (6, xy); the sandbox records ("ACTION6", xy) — same clicks.
    assert res.actions == [("ACTION6", xy) for _code, xy in direct_plan]


def _multipress_ring_evidence():
    """A 7-cell rotation ring with a RUN of three same-colour tiles, so ONE press
    under-determines it: the run's interior tiles stay same-colour (invisible in the
    diff) for two presses and only the THIRD press moves every ring cell at least
    once. A static rotation button (colour 8), a static solid mover (colour 9) and
    its hollow 4-corner target (colour 9) make a plannable board once the ring is
    learned. Returns ``(frame_fn, button_xy)`` where ``frame_fn(t)`` is the board
    after ``t`` presses and ``button_xy`` is the click ``(x=col, y=row)``."""
    import math

    n = 7
    base = [2, 2, 2, 3, 5, 6, 7]  # three adjacent colour-2 tiles → a length-3 run
    btn = (2, 2)  # (row, col) of the colour-8 rotation control
    mover_tl = (24, 10)  # solid 2x2 colour-9 mover (static, off-ring)
    target_c = (24, 20)  # hollow 4-corner colour-9 target centre
    cx, cy, rad = 13, 10, 6.0
    ring = [
        (
            int(round(cy + rad * math.sin(2 * math.pi * k / n))),
            int(round(cx + rad * math.cos(2 * math.pi * k / n))),
        )
        for k in range(n)
    ]

    def frame(t):
        g = np.zeros((32, 32), dtype=np.int64)
        g[0, :] = 1  # chrome bar -> the 2nd-most-common colour (dropped as background)
        for dr in (0, 1):
            for dc in (0, 1):
                g[btn[0] + dr, btn[1] + dc] = 8  # button (rotation control)
        for j, (r, c) in enumerate(ring):
            g[r, c] = base[(j - t) % n]  # occupants rotate one cell per press
        r, c = mover_tl
        for dr in (0, 1):
            for dc in (0, 1):
                g[r + dr, c + dc] = 9  # solid moving marker
        r, c = target_c
        for (dr, dc) in ((-2, -2), (-2, 2), (2, -2), (2, 2)):
            g[r + dr, c + dc] = 9  # hollow 4-corner target frame
        return g

    return frame, (btn[1], btn[0])


def test_arrangement_core_presses_the_same_button_until_certified_then_plans():
    """Purpose: the distilled PRESS-UNTIL-CERTIFY orchestration — the load-bearing
    adaptive-K policy the lp85 conquest needs and the bare single-press slice lacked.
    On a colour-duplicated ring that ONE press cannot fingerprint, the core must
    RE-press the SAME control across successive re-invocations (each on the growing
    transitions list) until its ring certifies, and only THEN queue a solving plan.

    Expected feedback: pass ⇒ the core accumulates evidence and presses-until-certify
    (3 presses here) before planning — the D3 upper-bound behaviour a token-slice core
    failed; fail ⇒ the core either certifies a partially-learned ring early (would
    plan on a wrong map) or never certifies (would never plan)."""
    frame, btn_xy = _multipress_ring_evidence()
    transitions: list[dict] = []
    presses = 0
    current = frame(0)

    # The ring needs three presses to reveal its full cycle. On each of the first
    # three invocations the control is uncertified, so the core queues exactly ONE
    # re-press of the SAME button and does NOT plan.
    for _ in range(3):
        plan, act = _collect_act()
        trace: list[str] = []
        arrangement_core(current, transitions, act, trace)
        assert plan == [(6, btn_xy)], (presses, plan, trace)
        assert not any(line.startswith("plan=") for line in trace), trace
        after = frame(presses + 1)
        transitions.append(
            {"action": "CLICK", "xy": [btn_xy[0], btn_xy[1]],
             "before": frame(presses), "after": after}
        )
        presses += 1
        current = after

    # After the third press every ring cell has been observed to move: the sole
    # control certifies and the core queues a real rotation plan (not another probe).
    plan, act = _collect_act()
    trace = []
    arrangement_core(current, transitions, act, trace)
    assert any("certified 1/1" in line for line in trace), trace
    assert any(line.startswith("plan=") for line in trace), trace
    assert len(plan) > 1 and all(a == 6 for a, _ in plan), plan


def test_simdfs_skel_card_size_is_compact():
    """Purpose: the D5-SKEL prereg's HARD CONSTRAINT — the assembled
    ``source_card('simdfs_skel')`` is a COMPACT family template (5000-10500 chars),
    size-comparable to the toggle control, so the D5-SKEL arm de-confounds template
    SIZE from FAMILY knowledge. Also asserts the card ast-parses.

    Expected feedback: pass ⇒ the skeleton stays a compact card the size experiment
    needs; fail ⇒ it drifted toward the 75KB engine (or shrank below the family-idea
    floor), re-confounding size with family and invalidating the D5-SKEL comparison."""
    import ast

    card = source_card("simdfs_skel")
    assert 5000 <= len(card) <= 10500, len(card)
    ast.parse(card)  # must be valid, sandbox-runnable source


def _skel_smoke_board():
    """A synthetic mini board: two small movable pieces (colours 2 and 3) and one
    larger fixed structure (a 3x3 colour-5 block = the target). Returns the board
    plus a single ``to_location`` click-move transition (a colour-2 piece moves
    toward the click at (2,2), foreground count preserved) as dict/tuple forms."""
    board = np.zeros((8, 8), dtype=np.int64)
    board[1, 1] = 2  # movable piece A (size 1)
    board[1, 3] = 3  # movable piece B (size 1)
    board[5:8, 5:8] = 5  # fixed structure / target (size 9 -> centroid (6, 6))

    before = np.zeros((8, 8), dtype=np.int64)
    before[1, 1] = 2
    after = np.zeros((8, 8), dtype=np.int64)
    after[2, 2] = 2  # the piece moved toward the click at (x=2, y=2)
    dict_trans = [{"action": "CLICK", "xy": [2, 2], "before": before, "after": after}]
    tuple_trans = [("CLICK", [2, 2], before, after)]
    return board, dict_trans, tuple_trans


def test_simdfs_skel_card_smoke_runs_in_sandbox(bridge_on):
    """Purpose: the D5-SKEL SMOKE GATE (prereg — replaces conquest-parity for the
    skeleton). The assembled ``source_card('simdfs_skel')`` runs inside ``run_code``
    on a synthetic 2-piece board whose one transition shows a click-move, and queues
    at least one non-(0,0) CLICK — proving the compact family card is real,
    self-contained, sandbox-executable source that learns and acts.

    Expected feedback: pass ⇒ the skeleton is a valid, runnable family arm for the
    holdout bench; fail ⇒ it is un-runnable (import/NameError) or learned nothing and
    emitted no action, so the arm cannot be measured."""
    board, dict_trans, tuple_trans = _skel_smoke_board()

    # direct path: the core learns 'to_location' and plans a click at the target.
    direct_plan, act = _collect_act()
    trace: list[str] = []
    simdfs_skel_core(board, dict_trans, act, trace)
    assert any("to_location" in line for line in trace), trace
    assert any(xy != (0, 0) for _c, xy in direct_plan), direct_plan

    # card-through-sandbox path: same, self-contained, offline.
    card = source_card("simdfs_skel")
    driver = card + "\n\nsimdfs_skel_core(current_frame, transitions, act)\n"
    res = run_code(driver, board, [], ["MOUSE"], transitions=tuple_trans)
    assert res.error == "", res.error
    assert res.actions, "the skeleton card must queue at least one action"
    assert any(xy != (0, 0) for _name, xy in res.actions), res.actions


def test_format_core_trace_reports_decisions():
    """Purpose: a core appends one-line localization decisions to a trace list, and
    ``format_core_trace`` renders them for prompt injection (patcher context).

    Expected feedback: pass ⇒ patchers get 'what the core decided and why'; fail ⇒
    the trace is missing or unformatted."""
    trace: list[str] = []
    _, act = _collect_act()
    # Too few stencils -> the core records a probe decision.
    toggle_core(np.zeros((8, 8), dtype=np.int64), [], act, trace)
    assert trace and any("probe" in line for line in trace)
    rendered = format_core_trace(trace)
    assert rendered.startswith("- ")
    assert format_core_trace([]) == "(no decisions)"
