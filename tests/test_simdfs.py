"""Contract tests for the R94 ``simdfs`` portal-sort family core.

These pin the R94 distillation invariant (Codex-frozen): the sb26 conquest's
load-bearing solving ENGINE (board parse -> faithful offline portal-DFS
simulator -> placement solve -> click plan) lives in ONE place
(``admorphiq.kernels.simdfs``), the live sb26 adapter DELEGATES to it (parity by
construction, no drifting copy), and that same engine assembles into a
self-contained, sandbox-runnable ``source_card("simdfs")`` the offline model can
patch. Every test is env-free on a synthetic mini portal-sort board — the engine
must be observation-driven with no game-id / internal reads.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from admorphiq.adapters25 import sb26
from admorphiq.kernels.simdfs import _plan_progress, simdfs_core, simdfs_plan
from admorphiq.tools.code_agent import run_code
from admorphiq.tools.solver_core import source_card


def _mini_portal_board() -> np.ndarray:
    """A minimal single-frame portal-sort board the engine can fully plan.

    Structure (32x32, background 0): one hollow colour-7 FRAME with two small
    empty SLOT markers (colour 3) inside its hole; a TARGET band above the frame
    (colours 4, 5 left-to-right) whose colours the pool supplies; a POOL band
    below the frame (colour-4 and colour-5 swatches). The engine reads the target
    order, DFS-visits the two slots, and pairs each with a pool pick — a full
    pick-then-place plan plus the verify action.
    """
    g = np.zeros((32, 32), dtype=np.int64)
    r0, c0, r1, c1 = 12, 10, 20, 22
    g[r0, c0 : c1 + 1] = 7
    g[r1, c0 : c1 + 1] = 7
    g[r0 : r1 + 1, c0] = 7
    g[r0 : r1 + 1, c1] = 7
    g[16, 13] = 3  # empty slot marker 0
    g[16, 19] = 3  # empty slot marker 1
    g[4, 12] = 4  # target band (colour 4, then 5)
    g[4, 18] = 5
    g[28, 11] = 4  # pool swatches
    g[28, 18] = 5
    return g


def _mini_portal_board_4slots() -> np.ndarray:
    """A pristine single-frame portal-sort board with FOUR empty slots — a
    9-step plan (4 pick+place click pairs + the verify action), big enough
    that the sandbox's ``run_code`` action cap (``queue[:8]``) truncates it
    mid-flight after exactly the 8 clicks, reproducing the real R94 D3
    scenario a live sandbox refill hit. Structure mirrors
    :func:`_mini_portal_board`, widened to four slots/targets/pool pairs
    (colours 4 and 5 alternating, two pool swatches of each)."""
    g = np.zeros((32, 32), dtype=np.int64)
    r0, c0, r1, c1 = 12, 8, 20, 26
    g[r0, c0 : c1 + 1] = 7
    g[r1, c0 : c1 + 1] = 7
    g[r0 : r1 + 1, c0] = 7
    g[r0 : r1 + 1, c1] = 7
    for c in (11, 15, 19, 23):
        g[16, c] = 3  # empty slot markers
    for c, color in zip((10, 14, 18, 22), (4, 5, 4, 5)):
        g[4, c] = color  # target band, left-to-right
    for color, pts in {4: [(28, 9), (28, 17)], 5: [(28, 13), (28, 21)]}.items():
        for r, c in pts:
            g[r, c] = color  # pool swatches
    return g


@dataclass
class _Obs:
    """A minimal observation the sb26 adapter's harness contract reads."""

    frame: list[Any]
    available_actions: list[int] = field(default_factory=lambda: [5, 6])
    levels_completed: int = 0
    state: Any = field(default_factory=lambda: type("S", (), {"name": "NOT_FINISHED"})())


def _collect_act():
    """An ``act`` compatible with the sandbox contract that records queued calls
    as ``(name, x, y)`` tuples (clicks and simple actions alike)."""
    rec: list[tuple[str, int | None, int | None]] = []

    def act(name: str, x: int | None = None, y: int | None = None) -> None:
        rec.append((str(name).upper(), x, y))

    return rec, act


def test_simdfs_card_is_real_source():
    """Purpose: ``source_card('simdfs')`` is assembled from ``inspect.getsource``
    of the live core + every helper it composes — no hand-maintained copy that
    could drift, and it ast-parses / self-contains under the sandbox whitelist.

    Expected feedback: pass ⇒ the model patches exactly the code the adapter's
    engine executes; fail ⇒ a parallel copy exists or a dependency is unbundled."""
    import ast

    card = source_card("simdfs")
    ast.parse(card)  # must compile
    assert "from __future__ import annotations" in card
    assert inspect.getsource(simdfs_core) in card
    assert inspect.getsource(simdfs_plan) in card
    # the distilled engine's load-bearing halves + the composed kernels
    for needle in (
        "def _recover_fused_frames",
        "def _simulate_portal_dfs",
        "def _dfs_traversal",
        "def closed_frames",
        "def split_fused_frame",
        "def recover_occluded_frame",
        "def connectors",
        "def find_regions",
        "def size_clusters",
    ):
        assert needle in card, needle
    with pytest.raises(KeyError):
        source_card("nonexistent")


def test_simdfs_core_parses_and_queues():
    """Purpose: the distilled engine, run directly, PARSES the board, SIMULATES the
    portal DFS, and QUEUES a sensible pick-then-place plan (paired pool/slot clicks
    plus the verify action) — the simulator + DFS + placement solver the sb26
    conquest delegates to.

    Expected feedback: pass ⇒ the core plans from raw frame evidence; fail ⇒ the
    engine no longer parses/simulates/queues from a portal-sort board."""
    board = _mini_portal_board()
    plan = simdfs_plan(tuple(tuple(int(v) for v in row) for row in board))
    assert plan is not None
    # 2 targets -> 2 pool-pick + 2 slot-click pairs, then the verify simple action.
    assert [step[0] for step in plan] == ["click", "click", "click", "click", "simple"]

    rec, act = _collect_act()
    trace: list[str] = []
    simdfs_core(board, [], act, trace)
    clicks = [(x, y) for name, x, y in rec if name == "CLICK"]
    assert len(clicks) == 4, rec
    # every queued click lands on the board; the verify is the ACTION5 == SPACE.
    assert all(0 <= x < 32 and 0 <= y < 32 for x, y in clicks)
    assert ("SPACE", None, None) in rec
    assert any("plan=" in line for line in trace), trace


def test_simdfs_card_runs_in_sandbox(monkeypatch):
    """Purpose: the assembled ``source_card('simdfs')`` plus a driver line executes
    inside the real ``run_code`` sandbox on a synthetic portal-sort board and
    queues the SAME clicks the direct core does — proving the card is real,
    self-contained, sandbox-runnable source (parity, no drift).

    Expected feedback: pass ⇒ the card runs offline and plans; fail ⇒ the LLM
    would be handed un-runnable code (import/NameError from an unbundled kernel)."""
    # The driver line references ``transitions``; the sandbox only injects it under
    # the kernel bridge (byte-identical default otherwise), same as the other cards.
    monkeypatch.setenv("HARNESS_KERNEL_API", "1")
    board = _mini_portal_board()

    direct, act = _collect_act()
    simdfs_core(board, [], act)
    direct_actions = [
        ("ACTION6", (x, y)) if name == "CLICK" else ("ACTION5", None)
        for name, x, y in direct
    ]

    card = source_card("simdfs")
    driver = card + "\n\nsimdfs_core(current_frame, transitions, act)\n"
    res = run_code(driver, board, [], ["MOUSE"], transitions=[])

    assert res.error == "", res.error
    assert res.actions, "the sandbox card must queue actions"
    assert res.actions == direct_actions


def test_simdfs_core_idle_settle_on_unplannable_board():
    """Purpose: on a board the planner cannot yet solve (a transient/empty board),
    the core QUEUES a single harmless idle corner click — the plan-or-settle
    orchestration that lets a transient board settle so the next refill re-plans
    (the load-bearing retry the D3 gate requires the core to carry, not omit).

    Expected feedback: pass ⇒ the core settles-and-retries instead of stalling;
    fail ⇒ the card omits the retry orchestration and never recovers a transient."""
    blank = np.zeros((16, 16), dtype=np.int64)
    assert simdfs_plan(tuple(tuple(int(v) for v in row) for row in blank)) is None
    rec, act = _collect_act()
    trace: list[str] = []
    simdfs_core(blank, [], act, trace)
    assert rec == [("CLICK", 0, 0)], rec
    assert any("idle-settle" in line for line in trace), trace


def test_simdfs_core_continues_inflight_plan_across_refills():
    """Purpose: R94 D3-2 regression test. A >8-step plan (4 slots -> 8 clicks + 1
    verify = 9 steps) gets truncated by the sandbox's own ``run_code`` action cap
    (``queue[:8]``) after its 8 clicks; the NEXT refill's ``current_frame`` is
    then a PARTIALLY-SORTED board (every slot filled, its pool swatches
    consumed) that :func:`simdfs_plan` genuinely cannot re-derive a plan from
    (proven below) — the exact permanent-idle failure mode a naive
    re-parse-every-refill core hits. The fix must instead reconstruct the
    in-flight plan from ``transitions`` (pristine-board re-derivation +
    progress matching) and queue only the un-executed tail (the verify action),
    NOT idle-settle.

    Expected feedback: pass ⇒ a plan spanning more than one sandbox refill
    resumes and completes correctly; fail ⇒ the core stalls forever the moment
    a plan exceeds the sandbox's per-refill action cap (the reported production
    bug — L1 never cleared)."""
    board = _mini_portal_board_4slots()
    grid = tuple(tuple(int(v) for v in row) for row in board)
    plan = simdfs_plan(grid)
    assert plan is not None and len(plan) == 9, plan  # 4 click pairs + verify
    assert plan[-1] == ("simple", 5)
    click_steps = [step for step in plan if step[0] == "click"]
    assert len(click_steps) == 8

    # Refill 1: the core queues the full 9-step plan; ``run_code``'s sandbox caps
    # the returned actions to 8 (``CodeResult(actions=queue[:8], ...)``), so only
    # the 8 clicks actually execute this refill (this mirrors that cap directly,
    # not through ``run_code``, to isolate the core's own in-flight logic).
    rec1, act1 = _collect_act()
    simdfs_core(board, [], act1)
    executed = rec1[:8]
    assert len(executed) == 8 and all(name == "CLICK" for name, _x, _y in executed)
    for (_kind, row, col), (_name, x, y) in zip(click_steps, executed):
        assert (x, y) == (col, row)

    # Build the resulting PARTIALLY-SORTED board (every slot filled, its pool
    # swatch consumed) and the observed transitions the sandbox driver would
    # have recorded (``xy = [x, y] = [col, row]``, matching the established
    # serialization convention).
    mutated = board.copy()
    transitions: list[dict[str, Any]] = []
    for i in range(0, 8, 2):
        _k1, prow, pcol = click_steps[i]
        _k2, srow, scol = click_steps[i + 1]
        color = int(board[prow, pcol])
        mutated[prow, pcol] = 0
        mutated[srow, scol] = color
    for i, (_kind, row, col) in enumerate(click_steps):
        transitions.append({
            "action": "CLICK", "xy": [col, row],
            "before": board if i == 0 else mutated, "after": mutated,
        })

    # Prove this really IS the regression scenario: re-parsing the mutated,
    # mid-plan board directly finds NO plan at all (the pool is exhausted, the
    # slots no longer look like empty markers) -- without the fix this is
    # exactly what sends the core into idle-settle forever.
    mutated_grid = tuple(tuple(int(v) for v in row) for row in mutated)
    assert simdfs_plan(mutated_grid) is None

    assert _plan_progress(plan, transitions) == 8

    rec2, act2 = _collect_act()
    trace2: list[str] = []
    simdfs_core(mutated, transitions, act2, trace2)
    assert rec2 == [("SPACE", None, None)], rec2
    assert not any("idle-settle" in line for line in trace2), trace2


def test_sb26_adapter_delegates_to_simdfs_plan(monkeypatch):
    """Purpose: the live sb26 adapter's planning DELEGATES to
    ``admorphiq.kernels.simdfs.simdfs_plan`` (structural delegation) — one
    implementation, so a change to the engine changes the adapter's behaviour.

    Expected feedback: pass ⇒ the adapter invokes the extracted engine (parity by
    construction); fail ⇒ the adapter carries its own drifting plan copy."""
    board = _mini_portal_board()
    calls: list[Any] = []
    sentinel = [("click", 16, 13), ("simple", 5)]

    def fake_plan(grid):
        calls.append(grid)
        return sentinel

    monkeypatch.setattr(sb26, "simdfs_plan", fake_plan)
    adapter = sb26.Adapter()
    obs = _Obs(frame=[board.tolist()])
    action = adapter.choose_action([], obs)

    assert len(calls) == 1, "the adapter must call the delegated engine exactly once"
    # the delegated plan was adopted and drained: the first drained step is the
    # sentinel's opening click (x=col=13, y=row=16), so the adapter is genuinely
    # driving the extracted engine's output, not its own copy.
    assert action.is_complex()
    assert (action.action_data.x, action.action_data.y) == (13, 16)
