"""agent25 kernel-bridge: the runtime code sandbox can CALL the r59 kernels.

Purpose: prove the bridge from script25 expressiveness to agent25 — a
model-written block can invoke curated kernels as ``K.<name>(...)`` inside
``run_code`` — while the sandbox's import block and the default (flag-off)
prompt stay intact.

Expected feedback: pass = kernels are reachable+bounded in-sandbox, escapes via
``import`` still fail, and enabling the bridge is opt-in (default prompt
byte-identical). A fail here means the bridge is broken or it silently changed
the deployed prompt.
"""

from __future__ import annotations

import numpy as np
import pytest

from admorphiq.tools import code_agent
from admorphiq.tools.code_agent import (
    _SYSTEM,
    _system_content,
    build_code_prompt,
    run_code,
)
from admorphiq.tools.kernel_api import DEFERRED, KERNEL_API, KERNEL_CARDS


@pytest.fixture
def bridge_on(monkeypatch):
    """Enable the kernel bridge (K injected + cards in the prompt)."""
    monkeypatch.setenv("HARNESS_KERNEL_API", "1")


def _grid() -> np.ndarray:
    g = np.zeros((8, 8), dtype=int)
    g[2:5, 2:5] = 3  # one 3x3 foreground region
    g[6, 6] = 4
    return g


def test_kernel_find_regions_callable_in_sandbox(bridge_on) -> None:
    """Purpose: K.find_regions runs in the sandbox and the block can act on it.
    Expected: no error, and the region-count-driven click is queued."""
    code = (
        "regs = K.find_regions(current_frame, background=0)\n"
        "print('n', len(regs))\n"
        "if regs:\n"
        "    r, c = regs[0]['centroid']\n"
        "    act('CLICK', int(c), int(r))\n"
    )
    res = run_code(code, _grid(), [], ["ACTION6"])
    assert res.error == "", res.error
    assert "n 2" in res.printed  # the 3x3 block + the single cell
    assert res.actions and res.actions[0][0] == "ACTION6"


def test_kernel_grid_shortest_path_in_sandbox(bridge_on) -> None:
    """Purpose: a pathing kernel composes in-sandbox and drives moves.
    Expected: K.grid_shortest_path returns a path, path_to_moves maps it, block
    queues the first move without error."""
    code = (
        "passable = [[1, 1, 1], [0, 1, 0], [1, 1, 1]]\n"
        "path = K.grid_shortest_path(passable, (0, 0), (2, 0))\n"
        "print('len', len(path) if path else 0)\n"
        "labels = {(1, 0): 'DOWN', (0, 1): 'RIGHT', (-1, 0): 'UP', (0, -1): 'LEFT'}\n"
        "moves = K.path_to_moves(path, labels)\n"
        "if moves:\n"
        "    act(moves[0])\n"
    )
    res = run_code(code, _grid(), [], ["ACTION1", "ACTION2", "ACTION3", "ACTION4"])
    assert res.error == "", res.error
    assert "len 5" in res.printed
    # (1,0) is a wall, so the shortest path detours right first:
    # (0,0)->(0,1)->(1,1)->(2,1)->(2,0); first move RIGHT -> ACTION4.
    assert res.actions and res.actions[0][0] == "ACTION4"


def test_import_still_blocked_with_bridge() -> None:
    """Purpose: the kernel bridge does not relax the import guard-rail.
    Expected: `import os` in a block yields an error, empty queue, no crash."""
    res = run_code("import os\nact('UP')", _grid(), [], ["ACTION1"])
    assert res.error != ""
    assert res.actions == []


def test_bounded_kernel_raises_are_caught(bridge_on) -> None:
    """Purpose: a combinatorial-guard breach degrades safely, never hangs.
    Expected: an over-limit assign_pairs raises inside the block; run_code
    catches it and returns an empty queue with an error string."""
    code = (
        "m = [[0.0] * 20 for _ in range(20)]\n"
        "K.assign_pairs(m)\n"
        "act('UP')\n"
    )
    res = run_code(code, _grid(), [], ["ACTION1"])
    assert res.error != ""  # the ValueError guard fired
    assert res.actions == []  # act('UP') never reached


def test_bridge_off_no_kernel_namespace() -> None:
    """Purpose: default (flag unset) sandbox is byte-identical — `K` is absent.
    Expected: a block referencing K raises NameError (caught), empty queue."""
    res = run_code("K.find_regions(current_frame)\nact('UP')", _grid(), [], ["ACTION1"])
    assert res.error != ""
    assert res.actions == []


def test_prompt_gate_default_off_is_byte_identical() -> None:
    """Purpose: the bridge is opt-in — default (flag unset) prompt is unchanged.
    Expected: _system_content() == _SYSTEM and the built prompt carries no cards."""
    assert _system_content() == _SYSTEM
    msgs = build_code_prompt(_grid(), [], ["ACTION1"])
    assert msgs[0]["content"] == _SYSTEM
    assert "KERNEL TOOLBOX" not in msgs[0]["content"]


def test_prompt_gate_on_appends_cards(monkeypatch) -> None:
    """Purpose: enabling HARNESS_KERNEL_API surfaces the toolbox to the model.
    Expected: the system prompt gains the KERNEL_CARDS block when the flag is on."""
    monkeypatch.setenv("HARNESS_KERNEL_API", "1")
    content = _system_content()
    assert content.startswith(_SYSTEM)
    assert "KERNEL TOOLBOX" in content
    assert KERNEL_CARDS in content
    # the model did not call kernels from the cards alone (measured); a worked
    # K.-using example is appended to drive usage.
    assert "EXAMPLE" in content and "K.grid_shortest_path" in content


def test_deferred_and_exposed_are_disjoint_and_documented() -> None:
    """Purpose: every curated name is either exposed or explicitly deferred with a
    reason — no silent drops.
    Expected: the two sets don't overlap and the exposed set is non-empty."""
    assert KERNEL_API
    assert not (set(KERNEL_API) & set(DEFERRED))
    assert code_agent._kernel_namespace().find_regions is KERNEL_API["find_regions"]
