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
    format_core_trace,
    paint_core,
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
    with pytest.raises(KeyError):
        source_card("nonexistent")


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
