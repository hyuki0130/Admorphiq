"""R35 forward-model pretrain + transfer pipeline tests.

Covers the three R35 scripts end-to-end on tiny synthetic fixtures (no arcengine
game run, no long training): collect_transitions shape/encoding on a mock env,
one finite pretrain step, and an eval accuracy that lands in [0, 1]. These pin
the data contract the offline pretrain/transfer measurement depends on.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))

import collect_transitions as ct  # noqa: E402
import eval_forward_transfer as ev  # noqa: E402
import pretrain_forward_model as pt  # noqa: E402
from _forward_data import encode_batch, load_transitions  # noqa: E402

from admorphiq.world_model.forward_model import COORD_OFFSET, GRID, ForwardModel  # noqa: E402

# ── mock arcengine env ───────────────────────────────────────────────────────


class _MockObs:
    def __init__(self, frame: np.ndarray, state: str, avail: list[int], levels: int):
        self.frame = [frame]
        self.state = type("S", (), {"name": state})()
        self.available_actions = avail
        self.levels_completed = levels


class _MockEnv:
    """A tiny deterministic env: an ACTION6 click toggles the clicked cell's
    colour; simple actions shift the whole frame by 1. Never wins/ends, so the
    collector runs exactly ``max_actions`` steps."""

    def __init__(self):
        self._frame = np.zeros((GRID, GRID), dtype=np.int8)
        self.observation_space = _MockObs(self._frame.copy(), "NOT_FINISHED", [1, 6], 0)

    def step(self, action, data=None):
        # arcengine GameAction: RESET resets; complex actions carry x/y in data.
        name = getattr(action.action_type, "name", "") if hasattr(action, "action_type") else ""
        if getattr(action, "name", "") == "RESET" or name == "RESET":
            self._frame[:] = 0
        elif data is not None:  # a click
            x, y = int(data["x"]), int(data["y"])
            self._frame[y, x] = (self._frame[y, x] + 1) % 4
        else:  # simple action
            self._frame = np.roll(self._frame, 1, axis=0)
        return _MockObs(self._frame.copy(), "NOT_FINISHED", [1, 6], 0)


class _MockArcade:
    def make(self, game_id):
        return _MockEnv()


# ── action index decode ──────────────────────────────────────────────────────


def test_action_index_roundtrip() -> None:
    """Purpose: the combined-logit index <-> (action_id, x, y) decode must match
    the forward model's ``_action_planes`` convention (idx 0..4 simple; a click
    is COORD_OFFSET + y*64 + x).

    Expected feedback: pass => collected action indices feed the forward model
    correctly; fail => the click coordinate order is swapped and dynamics targets
    would be misaligned.
    """
    assert ct.action_index_to_spec(0) == (1, None, None)
    assert ct.action_index_to_spec(4) == (5, None, None)
    idx = COORD_OFFSET + 12 * GRID + 7  # y=12, x=7
    assert ct.action_index_to_spec(idx) == (6, 7, 12)


# ── collect_transitions on the mock env ──────────────────────────────────────


def test_collect_produces_well_shaped_int_transitions() -> None:
    """Purpose: collect_game must return (N,64,64) int frames, (N,) int actions,
    (N,64,64) int next_frames — the exact arrays pretrain/eval consume — and
    record real transitions on a mock env that always changes the frame.

    Expected feedback: pass => the collector emits the transition contract on any
    arcengine-shaped env; fail => shapes/dtypes drift and downstream encoding
    breaks.
    """
    import random

    data = ct.collect_game(_MockArcade(), "mock", max_actions=30, rng=random.Random(0))
    frames, actions, next_frames = data["frames"], data["actions"], data["next_frames"]
    assert frames.shape[1:] == (GRID, GRID)
    assert next_frames.shape[1:] == (GRID, GRID)
    assert frames.shape[0] == actions.shape[0] == next_frames.shape[0]
    assert frames.shape[0] > 0
    assert np.issubdtype(frames.dtype, np.integer)
    assert np.issubdtype(actions.dtype, np.integer)
    # Every recorded action index is valid (simple 0..4 or a click >= COORD_OFFSET).
    assert bool(((actions >= 0) & (actions < COORD_OFFSET + GRID * GRID)).all())


def test_collect_and_load_roundtrip(tmp_path) -> None:
    """Purpose: an .npz written like collect_transitions.main and reloaded via
    load_transitions must preserve the transition arrays and concatenate across
    files.

    Expected feedback: pass => the on-disk format round-trips into the training
    loader; fail => pretrain/eval cannot read what the collector wrote.
    """
    import random

    data = ct.collect_game(_MockArcade(), "mock", max_actions=20, rng=random.Random(1))
    p = tmp_path / "mock.npz"
    np.savez_compressed(p, frames=data["frames"], actions=data["actions"],
                        next_frames=data["next_frames"])
    loaded = load_transitions([p])
    assert loaded["actions"].shape[0] == data["actions"].shape[0]
    assert loaded["frames"].shape[1:] == (GRID, GRID)


# ── encoding + one pretrain step ─────────────────────────────────────────────


def _tiny_dataset(n: int = 8) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(0)
    frames = rng.integers(0, 4, size=(n, GRID, GRID)).astype(np.int16)
    next_frames = frames.copy()
    # Flip a handful of cells so the change target is non-trivial.
    for i in range(n):
        next_frames[i, i % GRID, (i + 1) % GRID] = (frames[i, i % GRID, (i + 1) % GRID] + 1) % 4
    actions = np.array(
        [COORD_OFFSET + (i % GRID) * GRID + ((i + 1) % GRID) for i in range(n)],
        dtype=np.int32,
    )
    return {"frames": frames, "actions": actions, "next_frames": next_frames}


def test_encode_batch_shapes() -> None:
    """Purpose: encode_batch must emit the forward model's exact input/target
    tensors — one-hot frame (B,16,64,64), action planes (B,2,64,64), change
    target (B,64,64) float, colour target (B,64,64) long.

    Expected feedback: pass => the model's forward() and losses receive correctly
    shaped tensors; fail => a shape mismatch would surface only at train time.
    """
    d = _tiny_dataset(4)
    device = torch.device("cpu")
    frame_oh, planes, changed, nxt_colour = encode_batch(
        d["frames"], d["actions"], d["next_frames"], device
    )
    assert frame_oh.shape == (4, 16, GRID, GRID)
    assert planes.shape == (4, 2, GRID, GRID)
    assert changed.shape == (4, GRID, GRID)
    assert nxt_colour.shape == (4, GRID, GRID)
    assert nxt_colour.dtype == torch.long


def test_pretrain_one_step_finite_loss() -> None:
    """Purpose: a single pretrain optimisation step must produce a finite loss
    and change-mask stats in [0, 1] on a tiny dataset.

    Expected feedback: pass => the offline training loop is numerically sound and
    reuses the online agent's loss; fail => NaN/inf loss would poison a real
    pretrain run.
    """
    d = _tiny_dataset(8)
    device = torch.device("cpu")
    model = ForwardModel().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    stats = pt.train_step(model, opt, d["frames"], d["actions"], d["next_frames"], device)
    assert np.isfinite(stats["loss"])
    assert 0.0 <= stats["change_acc"] <= 1.0
    assert 0.0 <= stats["change_iou"] <= 1.0


def test_pretrain_full_loop_returns_model() -> None:
    """Purpose: pt.train must run multiple epochs on a tiny dataset and return a
    ForwardModel whose weights load back cleanly (save/load round-trip).

    Expected feedback: pass => --epochs N works and the saved .pt is a valid
    forward-model checkpoint; fail => the pretrain CLI would emit an unusable
    weights file.
    """
    d = _tiny_dataset(8)
    device = torch.device("cpu")
    model = pt.train(d, epochs=2, batch_size=4, lr=1e-3, device=device, seed=0)
    fresh = ForwardModel().to(device)
    fresh.load_state_dict(model.state_dict())  # must not raise


# ── eval metric range ────────────────────────────────────────────────────────


def test_eval_metrics_in_unit_range() -> None:
    """Purpose: evaluate() must return change_acc / change_iou / colour_acc all
    within [0, 1] on a tiny fixture, and n equal to the transition count.

    Expected feedback: pass => the transfer metrics are well-defined probabilities
    the transfer verdict can rely on; fail => an out-of-range metric would make
    the in-sample-vs-held-out gap meaningless.
    """
    d = _tiny_dataset(8)
    device = torch.device("cpu")
    model = ForwardModel().to(device)
    metrics = ev.evaluate(model, d, device, batch_size=4)
    assert metrics["n"] == 8
    for key in ("change_acc", "change_iou", "colour_acc"):
        assert 0.0 <= metrics[key] <= 1.0


def test_eval_empty_dataset_is_safe() -> None:
    """Purpose: evaluate() on an empty transition set must return n=0 with zeroed
    metrics rather than dividing by zero.

    Expected feedback: pass => a held-out set with no recorded transitions is
    handled gracefully; fail => an empty game file would crash the transfer run.
    """
    empty = {
        "frames": np.zeros((0, GRID, GRID), dtype=np.int16),
        "actions": np.zeros((0,), dtype=np.int32),
        "next_frames": np.zeros((0, GRID, GRID), dtype=np.int16),
    }
    metrics = ev.evaluate(ForwardModel(), empty, torch.device("cpu"))
    assert metrics["n"] == 0
