"""Shared data helpers for the R35 forward-model pretrain / transfer-eval scripts.

Reconstructed to the contract pinned by tests/test_forward_transfer.py and the
import blocks of pretrain_forward_model.py / eval_forward_transfer.py (the
original worktree copy was lost before it could be salvaged).

Contract:
- ``F`` — re-export of ``torch.nn.functional`` (the pretrain loss code uses it).
- ``pick_device()`` — mps > cuda > cpu.
- ``load_npz_files(pattern)`` — glob (or single path) -> sorted list of paths.
- ``load_transitions(paths)`` — read ``frames`` / ``actions`` / ``next_frames``
  arrays from each .npz and concatenate across files.
- ``iter_minibatches(n, batch_size, rng)`` — shuffled index-array minibatches.
- ``encode_batch(frames_int, actions, next_frames_int, device)`` — the forward
  model's exact input/target tensors: one-hot frame ``(B,16,64,64)`` float,
  action planes ``(B,2,64,64)``, change target ``(B,64,64)`` float, next-colour
  target ``(B,64,64)`` long. Matches ``online_rl_agent._train_forward``.
"""

from __future__ import annotations

import glob as _glob
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F  # noqa: F401  (re-exported for the scripts)

# Make the package importable when run as a script from the repo root.
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from admorphiq.world_model.forward_model import (  # noqa: E402
    GRID,
    N_COLORS,
    _action_planes,
)


def pick_device() -> torch.device:
    """mps > cuda > cpu — same preference as the online agent."""
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def load_npz_files(pattern: str) -> list[str]:
    """Expand a glob (quote it in the shell) or accept a single .npz path."""
    matches = sorted(_glob.glob(pattern))
    if not matches and Path(pattern).exists():
        matches = [pattern]
    return matches


def load_transitions(paths: list) -> dict[str, np.ndarray]:
    """Load + concatenate ``frames``/``actions``/``next_frames`` across .npz files."""
    frames, actions, next_frames = [], [], []
    for p in paths:
        with np.load(p) as z:
            frames.append(np.asarray(z["frames"]))
            actions.append(np.asarray(z["actions"]))
            next_frames.append(np.asarray(z["next_frames"]))
    if not frames:
        empty_f = np.zeros((0, GRID, GRID), dtype=np.int16)
        return {
            "frames": empty_f,
            "actions": np.zeros((0,), dtype=np.int32),
            "next_frames": empty_f.copy(),
        }
    return {
        "frames": np.concatenate(frames, axis=0),
        "actions": np.concatenate(actions, axis=0),
        "next_frames": np.concatenate(next_frames, axis=0),
    }


def iter_minibatches(
    n: int, batch_size: int, rng: np.random.Generator, shuffle: bool = True
):
    """Yield index arrays covering ``range(n)`` in ``batch_size`` chunks.

    ``shuffle=True`` (training) permutes the order per pass; ``shuffle=False``
    (evaluation) walks sequentially so metrics are deterministic.
    """
    order = rng.permutation(n) if shuffle else np.arange(n)
    for start in range(0, n, batch_size):
        yield order[start : start + batch_size]


def encode_batch(
    frames_int: np.ndarray,
    actions: np.ndarray,
    next_frames_int: np.ndarray,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Build the ForwardModel's input/target tensors for one minibatch.

    Returns ``(frame_oh (B,16,64,64) float, planes (B,2,64,64), changed
    (B,64,64) float, nxt_colour (B,64,64) long)`` — the exact tensors
    ``online_rl_agent._train_forward`` feeds the model, so a pretrained model is
    a drop-in warm-start for the online agent's forward model.
    """
    cur = torch.as_tensor(np.asarray(frames_int), dtype=torch.long, device=device)
    nxt = torch.as_tensor(np.asarray(next_frames_int), dtype=torch.long, device=device)
    frame_oh = (
        torch.nn.functional.one_hot(cur.clamp(0, N_COLORS - 1), N_COLORS)
        .permute(0, 3, 1, 2)
        .float()
    )
    planes = torch.stack([_action_planes(int(a), device) for a in np.asarray(actions)])
    changed = (cur != nxt).float()
    nxt_colour = nxt.clamp(0, N_COLORS - 1)
    return frame_oh, planes, changed, nxt_colour
