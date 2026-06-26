"""Unit tests for the D4 (dihedral) augmentation used by BC-policy v3 training.

These pin the single correctness property the whole augmentation rests on: the
FRAME transform and the COORDINATE remap agree, so a click that was correct on
the original frame is still correct on every symmetry. If this drifts, v3 would
train the coordinate head on systematically wrong (x, y) labels — silently
degrading coord accuracy instead of 8x-ing it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "train_policy.py"
_SPEC = importlib.util.spec_from_file_location("train_policy", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["train_policy"] = _MOD
_SPEC.loader.exec_module(_MOD)

D4_TRANSFORMS = _MOD.D4_TRANSFORMS
d4_augment_action6 = _MOD.d4_augment_action6
GRID_MAX = _MOD.GRID_MAX  # 63


def _marked_frame(x: int, y: int) -> np.ndarray:
    """A blank 64x64 frame with a unique marker at the click cell (row=y, col=x)."""
    fr = np.zeros((64, 64), dtype=np.uint8)
    fr[y, x] = 7  # axis 0 = y, axis 1 = x (bc_agent convention)
    return fr


def test_rot90_then_flip_explicit_cell():
    """Purpose: pin the exact landing cell for a known (x, y) under rot90 and fliplr.

    Expected feedback: a failure means the hand-derived coord formulas in
    D4_TRANSFORMS are wrong for the two transforms the task explicitly calls out
    (a 90 degree rotation and a flip) — every augmented ACTION6 label would be
    mislabelled, so this must be green before trusting v3's coord numbers.
    """
    by_name = {name: coord_fn for name, _f, coord_fn in D4_TRANSFORMS}
    # rot90 (counter-clockwise): (x, y) -> (y, 63 - x).
    assert by_name["rot90"](10, 3, GRID_MAX) == (3, 53)
    # fliplr (mirror x): (x, y) -> (63 - x, y).
    assert by_name["fliplr"](10, 3, GRID_MAX) == (53, 3)
    # Compose rot90 then fliplr on a corner to catch sign errors.
    x, y = 0, 0
    x, y = by_name["rot90"](x, y, GRID_MAX)
    x, y = by_name["fliplr"](x, y, GRID_MAX)
    assert (x, y) == (63, 63)


def test_frame_and_coord_transforms_agree():
    """Purpose: prove every D4 frame op and its coord op move the SAME pixel together.

    Expected feedback: for each of the 8 symmetries, the marker placed at (x, y)
    must reappear at the coord-remapped (x', y') in the transformed frame. A
    failure flags a mismatched (frame_fn, coord_fn) pair — the exact bug that
    would feed the model wrong click labels while looking superficially fine.
    """
    x0, y0 = 11, 40  # asymmetric point so every transform lands somewhere distinct
    fr = _marked_frame(x0, y0)[None]  # (1, 64, 64) batch
    for name, frame_fn, coord_fn in D4_TRANSFORMS:
        nf = frame_fn(fr)
        nx, ny = coord_fn(x0, y0, GRID_MAX)
        assert nf.shape == (1, 64, 64), name
        assert nf[0, ny, nx] == 7, f"{name}: marker not at remapped cell"
        assert int(nf.sum()) == 7, f"{name}: marker count changed"


def test_d4_augment_action6_8x_and_labels():
    """Purpose: verify d4_augment_action6 yields exactly 8x rows with consistent labels.

    Expected feedback: failure means the batch augmentation (not just the single
    transforms) is broken — either the row multiplier or the per-symmetry coord
    arrays are wrong, which would corrupt the v3 training set wholesale.
    """
    frames = np.stack([_marked_frame(5, 9), _marked_frame(60, 2)]).astype(np.uint8)
    cx = np.array([5, 60], dtype=np.int64)
    cy = np.array([9, 2], dtype=np.int64)
    w = np.array([1.0, 2.0], dtype=np.float32)

    fr8, cx8, cy8, w8 = d4_augment_action6(frames, cx, cy, w)
    assert fr8.shape == (16, 64, 64)
    assert cx8.shape == cy8.shape == w8.shape == (16,)
    # Each augmented frame's marker sits at its own remapped (cx8, cy8).
    for i in range(16):
        assert fr8[i, cy8[i], cx8[i]] == 7
    # Identity block (first transform) reproduces the originals untouched.
    assert cx8[0] == 5 and cy8[0] == 9
    assert cx8[1] == 60 and cy8[1] == 2
