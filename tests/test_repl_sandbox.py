"""Tests for the code-REPL Python sandbox + inspection API (R55 module 4).

These lock the two contracts the design doc demands of the sandbox: the
inspection API returns correct structured views of the scene/frames (so model
code reasons on truth), and the subprocess executor is safe — bounded output,
stdlib-only imports rejected, syntax/runtime errors reported (not crashing), a
hard timeout killing runaway loops, and actions RECORDED for explicit accounting
rather than executed.
"""

from __future__ import annotations

import numpy as np

from admorphiq.repl_agent.sandbox import (
    Inspector,
    ObservationStore,
    default_timeout,
    run_code,
)
from admorphiq.repl_agent.segmentation import SceneTracker


def _store_two_frames() -> ObservationStore:
    tracker = SceneTracker(background=0)
    store = ObservationStore()
    f1 = np.zeros((8, 8), dtype=np.int64)
    f1[2, 2] = 2
    f1[2, 3] = 2
    store.add(f1, tracker.update(f1))
    f2 = np.zeros((8, 8), dtype=np.int64)
    f2[2, 1] = 2
    f2[2, 2] = 2  # moved left
    store.add(f2, tracker.update(f2))
    return store


# ----- Inspector (in-process, fast) ------------------------------------------
def test_inspector_objects_and_relations():
    """Purpose: objects()/relations() expose the tracked scene at a given frame.

    Feedback: failure means model code reasons on a wrong object list.
    """
    insp = Inspector(_store_two_frames().to_payload())
    objs = insp.objects(-1)
    assert objs and objs[0]["id"].startswith("o")
    rel = insp.relations(objs[0]["id"], -1)
    assert "contained_by" in rel and "adjacent" in rel


def test_inspector_crop_mask_compare():
    """Purpose: crop returns the sub-grid, mask marks object cells, compare diffs
    two frames with a correct changed count.

    Feedback: failure means geometric/transition inspection is wrong.
    """
    insp = Inspector(_store_two_frames().to_payload())
    crop = insp.crop((2, 1, 2, 3), t=-1)
    assert crop == [[2, 2, 0]]
    oid = insp.objects(-1)[0]["id"]
    m = insp.mask(oid, -1)
    assert m[2][1] == 1 and m[2][2] == 1
    cmp = insp.compare(0, 1)
    assert cmp["cells_changed"] == 2  # one cell vacated, one filled


def test_inspector_ascii_shape():
    """Purpose: ascii() renders the frame as base-16 rows of the right size.

    Feedback: failure means the textual local view is malformed.
    """
    insp = Inspector(_store_two_frames().to_payload())
    art = insp.ascii(t=0)
    lines = art.splitlines()
    assert len(lines) == 8 and all(len(row) == 8 for row in lines)


def test_inspector_action_accounting():
    """Purpose: action() records requests (does not execute) with MOUSE coords.

    Feedback: failure means action accounting — the sandbox/env boundary — leaks.
    """
    insp = Inspector(_store_two_frames().to_payload())
    insp.action("LEFT")
    insp.action("MOUSE", row=3, col=4)
    assert insp.actions == [
        {"action": "LEFT"},
        {"action": "MOUSE", "row": 3, "col": 4},
    ]


# ----- subprocess executor ---------------------------------------------------
def test_run_code_records_actions():
    """Purpose: model code running in the subprocess can inspect and request an
    action, returned to the parent.

    Feedback: failure means the whole code-REPL loop is non-functional.
    """
    code = (
        "objs = objects(-1)\n"
        "print('n', len(objs))\n"
        "action('MOUSE', row=objs[0]['safe_click'][0], col=objs[0]['safe_click'][1])\n"
    )
    res = run_code(code, _store_two_frames(), timeout=10)
    assert res.ok
    assert "n 1" in res.stdout
    assert res.actions and res.actions[0]["action"] == "MOUSE"


def test_run_code_reports_syntax_error():
    """Purpose: malformed code returns an error, never crashes the harness.

    Feedback: failure means one bad model output could kill a game run.
    """
    res = run_code("x = = 5", _store_two_frames(), timeout=10)
    assert not res.ok
    assert "syntax" in res.error.lower()


def test_run_code_blocks_disallowed_import():
    """Purpose: importing outside the stdlib allowlist (e.g. os) is rejected.

    Feedback: failure means the sandbox is not actually sandboxed.
    """
    res = run_code("import os\nos.system('echo hi')\n", _store_two_frames(), timeout=10)
    assert not res.ok
    assert "import" in res.error.lower() or "not allowed" in res.error.lower()


def test_default_timeout_env_configurable(monkeypatch):
    """Purpose: the sandbox timeout defaults to 30s (winner-validated for in-REPL
    search) and is overridable via REPL_SANDBOX_TIMEOUT.

    Feedback: failure means in-REPL action-sequence search is starved or the
    Kaggle bench can't tune the ceiling.
    """
    monkeypatch.delenv("REPL_SANDBOX_TIMEOUT", raising=False)
    assert default_timeout() == 30.0
    monkeypatch.setenv("REPL_SANDBOX_TIMEOUT", "12.5")
    assert default_timeout() == 12.5
    monkeypatch.setenv("REPL_SANDBOX_TIMEOUT", "garbage")
    assert default_timeout() == 30.0  # invalid falls back


def test_run_code_hard_timeout_kills_loop():
    """Purpose: an infinite loop is killed by the subprocess-level timeout.

    Feedback: failure means one hung generation could starve all 110 games.
    """
    res = run_code("while True:\n    pass\n", _store_two_frames(), timeout=1.0)
    assert res.timed_out is True
    assert not res.ok
