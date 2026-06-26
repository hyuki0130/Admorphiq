"""Behavior-cloning policy: frame -> action, trained on gold solution traces.

This is the DriesSmit-style CNN action predictor (the proven ARC-AGI-3 approach).
``PerceptionModel`` emits 4101 logits = 5 simple-action logits (ACTION1..5) +
4096 coordinate logits (ACTION6, index ``y*64 + x``). Behavior cloning treats
the whole 4101 vector as a single softmax policy:

  * simple action a in 1..5  ->  target class  ``a - 1``           (0..4)
  * ACTION6 click (x, y)     ->  target class  ``5 + y*64 + x``    (5..4100)

A single cross-entropy over the 4101 classes therefore lands on the action
portion for simple-action demonstrations and on the coordinate portion for
ACTION6 demonstrations — and it matches deployment exactly, where the agent
picks ``argmax`` over the same masked 4101 logits.

The pure helpers (``frame_to_onehot`` / ``build_bc_targets``) are kept at module
level with only numpy + torch deps so the trainer and tests import them cheaply;
the agent's runtime conversion/fallback deps are imported lazily.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from .perception import PerceptionModel

# ── Layout constants (mirror PerceptionModel) ────────────────────────────────
NUM_SIMPLE_ACTIONS = 5          # ACTION1..5 occupy combined indices 0..4
NUM_COORDS = 4096               # 64 * 64
COORD_OFFSET = NUM_SIMPLE_ACTIONS
TOTAL_LOGITS = NUM_SIMPLE_ACTIONS + NUM_COORDS  # 4101
GRID = 64

DEFAULT_WEIGHTS = Path(__file__).resolve().parent.parent.parent / "models" / "bc_policy.pt"


def frame_to_onehot(frame: np.ndarray) -> torch.Tensor:
    """Convert a (64, 64) colour-index frame to a (16, 64, 64) float one-hot tensor.

    Matches the trace convention (``obs.frame[0]``, values 0-15) and the model's
    16-channel input. Axis 0 of ``frame`` is treated as ``y`` and axis 1 as ``x``,
    consistent with the coordinate decode ``coord = y*64 + x``.
    """
    t = torch.from_numpy(np.asarray(frame).astype(np.int64))   # (64, 64)
    onehot = F.one_hot(t.clamp(0, 15), num_classes=16)          # (64, 64, 16)
    return onehot.permute(2, 0, 1).float()                      # (16, 64, 64)


def onehot_batch(frames: np.ndarray) -> torch.Tensor:
    """One-hot a batch of (N, 64, 64) colour-index frames to (N, 16, 64, 64)."""
    t = torch.from_numpy(np.asarray(frames).astype(np.int64))   # (N, 64, 64)
    onehot = F.one_hot(t.clamp(0, 15), num_classes=16)          # (N, 64, 64, 16)
    return onehot.permute(0, 3, 1, 2).float()                   # (N, 16, 64, 64)


def coord_to_index(x: int, y: int) -> int:
    """Combined-logit index for an ACTION6 click at (x, y): ``5 + y*64 + x``."""
    return COORD_OFFSET + int(y) * GRID + int(x)


def build_bc_targets(
    actions: np.ndarray,
    coords_x: np.ndarray,
    coords_y: np.ndarray,
) -> np.ndarray:
    """Build the (N,) combined-logit class targets for a batch of gold rows.

    Args:
        actions: (N,) action ids in 1..6 (RESET/ACTION7 are not demonstrated in gold).
        coords_x / coords_y: (N,) ACTION6 click coords (0-63); ignored for non-ACTION6.

    Returns:
        (N,) int64 array of class indices in ``[0, 4101)``.

    Raises:
        ValueError: if any action is outside 1..6 (BC has no slot for RESET/ACTION7).
    """
    actions = np.asarray(actions).astype(np.int64)
    coords_x = np.asarray(coords_x).astype(np.int64)
    coords_y = np.asarray(coords_y).astype(np.int64)

    if actions.min(initial=1) < 1 or actions.max(initial=1) > 6:
        bad = sorted(set(actions[(actions < 1) | (actions > 6)].tolist()))
        raise ValueError(f"BC targets require actions in 1..6; got out-of-range ids {bad}")

    targets = np.empty(actions.shape[0], dtype=np.int64)
    is_a6 = actions == 6
    # Simple actions ACTION1..5 -> class 0..4.
    targets[~is_a6] = actions[~is_a6] - 1
    # ACTION6 -> 5 + y*64 + x.
    targets[is_a6] = COORD_OFFSET + coords_y[is_a6] * GRID + coords_x[is_a6]
    return targets


def _pick_device(device: str | None) -> torch.device:
    if device is not None:
        return torch.device(device)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class BCPolicyAgent:
    """Deploys the trained BC policy against the official harness contract.

    Exposes ``is_done(frames, latest_frame)`` / ``choose_action(frames, latest_frame)``
    over the raw arcengine observation (same contract as ``AdmorphiqAdapter`` and
    ``GeneralAgent``), returning an official ``GameAction``. On a stuck streak
    (repeated no-op frames) it falls back to the existing exploration agent.
    """

    STUCK_THRESHOLD = 4  # consecutive unchanged frames before falling back

    def __init__(self, weights_path: str | Path = DEFAULT_WEIGHTS, device: str | None = None) -> None:
        from .adapter import AdmorphiqAdapter  # heavy import, kept lazy
        from .agent_ensemble import get_frame

        self._get_frame = get_frame
        self._convert_action = AdmorphiqAdapter._convert_action
        self._AdapterCls = AdmorphiqAdapter

        self.device = _pick_device(device)
        self.model = PerceptionModel().to(self.device)
        path = Path(weights_path)
        if path.exists():
            state = torch.load(path, map_location=self.device)
            self.model.load_state_dict(state)
            self._loaded = True
        else:
            self._loaded = False
        self.model.eval()

        self._prev_frame: np.ndarray | None = None
        self._no_change_streak = 0
        self._fallback: Any = None  # lazily constructed AdmorphiqAdapter

    # ── harness contract ─────────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return _state_name(latest_frame) == "WIN"

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        obs = latest_frame
        state = _state_name(obs)
        if state in ("NOT_PLAYED", "GAME_OVER"):
            self._prev_frame = None
            self._no_change_streak = 0
            return self._reset_action()

        if not _has_frame(obs):
            return self._reset_action()

        frame = self._get_frame(obs)  # (64, 64) int — same as training (obs.frame[0])

        # Track stuck-ness: identical frame to the previous step means the last
        # action was a no-op.
        if self._prev_frame is not None and np.array_equal(frame, self._prev_frame):
            self._no_change_streak += 1
        else:
            self._no_change_streak = 0

        simple_mask, action6_ok = _availability(obs)
        if not simple_mask.any() and not action6_ok:
            return self._reset_action()

        if self._no_change_streak >= self.STUCK_THRESHOLD:
            self._prev_frame = frame
            return self._fallback_action(obs)

        idx = self._policy_index(frame, simple_mask, action6_ok)
        self._prev_frame = frame
        return self._index_to_action(idx)

    # ── internals ────────────────────────────────────────────────────────────

    def _policy_index(self, frame: np.ndarray, simple_mask: np.ndarray, action6_ok: bool) -> int:
        full_mask = torch.zeros(1, TOTAL_LOGITS, dtype=torch.bool, device=self.device)
        full_mask[0, :NUM_SIMPLE_ACTIONS] = torch.from_numpy(simple_mask).to(self.device)
        if action6_ok:
            full_mask[0, NUM_SIMPLE_ACTIONS:] = True

        x = frame_to_onehot(frame).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits = self.model(x, available_actions=full_mask)
        return int(torch.argmax(logits[0]).item())

    def _index_to_action(self, idx: int) -> Any:
        from .types import ActionType, GameAction

        if idx < NUM_SIMPLE_ACTIONS:
            internal = GameAction.simple(ActionType(idx + 1))
        else:
            coord = idx - COORD_OFFSET
            x = coord % GRID
            y = coord // GRID
            internal = GameAction.coordinate(x, y)
        return self._convert_action(internal)

    def _reset_action(self) -> Any:
        from .types import GameAction

        return self._convert_action(GameAction.reset())

    def _fallback_action(self, obs: Any) -> Any:
        if self._fallback is None:
            self._fallback = self._AdapterCls()
        return self._fallback.choose_action([], obs)


# ── observation helpers (tolerant of arcengine obs shape) ────────────────────


def _state_name(obs: Any) -> str:
    state = getattr(obs, "state", None)
    return getattr(state, "name", str(state) if state is not None else "")


def _has_frame(obs: Any) -> bool:
    fr = getattr(obs, "frame", None)
    return fr is not None and len(fr) > 0


def _availability(obs: Any) -> tuple[np.ndarray, bool]:
    """Return (simple-action bool mask of length 5, action6_available)."""
    simple_mask = np.zeros(NUM_SIMPLE_ACTIONS, dtype=bool)
    action6_ok = False
    for a in getattr(obs, "available_actions", []) or []:
        aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
        if aid is None:
            continue
        if 1 <= aid <= 5:
            simple_mask[aid - 1] = True
        elif aid == 6:
            action6_ok = True
    return simple_mask, action6_ok
