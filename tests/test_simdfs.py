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
from admorphiq.kernels.simdfs import simdfs_core, simdfs_plan
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
