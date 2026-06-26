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

import os
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


def _frame_hash(frame: np.ndarray) -> str:
    """Stable short hash of a (64, 64) frame for cycle detection."""
    import hashlib

    return hashlib.md5(np.ascontiguousarray(frame).tobytes()).hexdigest()[:16]


class BCPolicyAgent:
    """Deploys the trained BC policy against the official harness contract.

    Exposes ``is_done(frames, latest_frame)`` / ``choose_action(frames, latest_frame)``
    over the raw arcengine observation (same contract as ``AdmorphiqAdapter`` and
    ``GeneralAgent``), returning an official ``GameAction``.

    Two robustness layers sit on top of the raw argmax policy:

    * **Cycle / stuck detector** — the argmax policy is deterministic, so on a
      game it cannot solve it can loop forever on a (state, action) pair that
      never changes the frame (this is what burned SB26's full 50k budget). We
      track recent ``(frame_hash, action)`` pairs; once a pick repeats past
      ``REPEAT_LIMIT`` we skip to the next-best logit, and on a sustained
      identical-frame streak we fall back to the exploration agent. A hard
      no-progress cap (``GIVE_UP_NO_PROGRESS`` actions without a level clear)
      flips ``is_done`` to ``True`` so the runner bails instead of grinding to
      the action budget.
    * **Test-time training (TTT)** — when the policy clears a level on the
      current game, the ``(frame -> action)`` transitions that produced the
      clear are fine-tuned into the per-game working model with a handful of
      gradient steps (Jack Cole's ARC TTT technique). The working model is a
      fresh per-game copy of the on-disk base weights, so adaptation is
      isolated to this game and never written back to disk. Gated behind a
      flag (default on; ``ttt=False`` or env ``BC_TTT=0`` disables it).
    """

    STUCK_THRESHOLD = 4          # consecutive unchanged frames before falling back
    REPEAT_LIMIT = 2             # times a (frame_hash, action) may repeat before it is skipped
    POLICY_TOPK = 8             # next-best candidates considered when escaping a cycle
    GIVE_UP_NO_PROGRESS = 2500  # actions on a level without progress before bailing out

    # TTT hyperparameters — kept tiny so the per-game cost fits the
    # ~5min/game (9h / 110 games) Kaggle budget.
    TTT_LR = 1e-4
    TTT_STEPS = 8
    TTT_MAX_SAMPLES = 48
    TTT_MIN_SAMPLES = 4
    TTT_BUFFER_CAP = 512

    def __init__(
        self,
        weights_path: str | Path = DEFAULT_WEIGHTS,
        device: str | None = None,
        ttt: bool = True,
    ) -> None:
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

        # TTT flag: constructor arg AND env override (BC_TTT=0/false disables).
        env_ttt = os.environ.get("BC_TTT", "").strip().lower()
        self._ttt_enabled = bool(ttt) and env_ttt not in ("0", "false", "no", "off")

        # Per-game mutable thresholds (instance copies so tests can tune them).
        self._give_up_no_progress = self.GIVE_UP_NO_PROGRESS

        self._prev_frame: np.ndarray | None = None
        self._no_change_streak = 0
        self._fallback: Any = None  # lazily constructed AdmorphiqAdapter

        # Cycle detector + hard-cap state.
        self._seen_state_action: dict[tuple[str, int], int] = {}
        self._prev_levels: int | None = None
        self._actions_since_progress = 0
        self._give_up = False

        # TTT buffers: pending = this level's transitions; buffer = accumulated
        # successful (level-clearing) transitions for this game.
        self._ttt_pending: list[tuple[np.ndarray, int]] = []
        self._ttt_buffer: list[tuple[np.ndarray, int]] = []

    # ── harness contract ─────────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        # ``_give_up`` hard-caps a hopeless loop (e.g. SB26) so the runner stops
        # instead of grinding through the full action budget.
        return self._give_up or _state_name(latest_frame) == "WIN"

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        obs = latest_frame
        state = _state_name(obs)
        if state in ("NOT_PLAYED", "GAME_OVER"):
            self._prev_frame = None
            self._no_change_streak = 0
            return self._reset_action()

        if not _has_frame(obs):
            return self._reset_action()

        # Detect level transitions: a level clear is the supervision signal for
        # TTT and resets the cycle/progress trackers (new level = new state space).
        levels = _levels_completed(obs)
        if self._prev_levels is None:
            self._prev_levels = levels
        elif levels > self._prev_levels:
            self._on_level_cleared()
            self._prev_levels = levels

        frame = self._get_frame(obs)  # (64, 64) int — same as training (obs.frame[0])

        # Track stuck-ness: identical frame to the previous step means the last
        # action was a no-op.
        if self._prev_frame is not None and np.array_equal(frame, self._prev_frame):
            self._no_change_streak += 1
        else:
            self._no_change_streak = 0

        # Hard cap: bail out of a hopeless game rather than burning the budget.
        self._actions_since_progress += 1
        if self._actions_since_progress >= self._give_up_no_progress:
            self._give_up = True
            self._prev_frame = frame
            return self._reset_action()

        simple_mask, action6_ok = _availability(obs)
        if not simple_mask.any() and not action6_ok:
            return self._reset_action()

        if self._no_change_streak >= self.STUCK_THRESHOLD:
            self._prev_frame = frame
            return self._fallback_action(obs)

        fhash = _frame_hash(frame)
        idx = self._pick_noncycling_index(frame, fhash, simple_mask, action6_ok)
        if idx is None:
            # Every top candidate at this state is a known cycle → explore.
            self._prev_frame = frame
            return self._fallback_action(obs)

        self._seen_state_action[(fhash, idx)] = (
            self._seen_state_action.get((fhash, idx), 0) + 1
        )
        if self._ttt_enabled:
            self._ttt_pending.append((frame.astype(np.int64), idx))
        self._prev_frame = frame
        return self._index_to_action(idx)

    # ── internals ────────────────────────────────────────────────────────────

    def _policy_ranked(
        self, frame: np.ndarray, simple_mask: np.ndarray, action6_ok: bool, k: int
    ) -> list[int]:
        """Return up-to-``k`` available combined-logit indices, best logit first."""
        full_mask = torch.zeros(1, TOTAL_LOGITS, dtype=torch.bool, device=self.device)
        full_mask[0, :NUM_SIMPLE_ACTIONS] = torch.from_numpy(simple_mask).to(self.device)
        if action6_ok:
            full_mask[0, NUM_SIMPLE_ACTIONS:] = True

        x = frame_to_onehot(frame).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits = self.model(x, available_actions=full_mask)[0]
        k = min(k, logits.numel())
        vals, idxs = torch.topk(logits, k)
        return [
            int(i)
            for i, v in zip(idxs.tolist(), vals.tolist(), strict=False)
            if v != float("-inf")
        ]

    def _pick_noncycling_index(
        self, frame: np.ndarray, fhash: str, simple_mask: np.ndarray, action6_ok: bool
    ) -> int | None:
        """Best policy index whose (frame, action) hasn't already cycled."""
        for cand in self._policy_ranked(frame, simple_mask, action6_ok, self.POLICY_TOPK):
            if self._seen_state_action.get((fhash, cand), 0) >= self.REPEAT_LIMIT:
                continue
            return cand
        return None

    def _on_level_cleared(self) -> None:
        """Fine-tune on the just-cleared level's transitions and reset trackers."""
        if self._ttt_enabled and self._ttt_pending:
            self._ttt_buffer.extend(self._ttt_pending)
            if len(self._ttt_buffer) > self.TTT_BUFFER_CAP:
                self._ttt_buffer = self._ttt_buffer[-self.TTT_BUFFER_CAP:]
            self._ttt_finetune()
        self._ttt_pending = []
        # New level → stale cycle memory and progress budget are irrelevant.
        self._seen_state_action.clear()
        self._no_change_streak = 0
        self._actions_since_progress = 0

    def _ttt_finetune(self) -> None:
        """A few gradient steps adapting the per-game model to its own successes.

        Trains the in-memory working model only — the on-disk base weights are
        never modified, and each game gets a fresh working model, so adaptation
        does not leak across games.
        """
        buf = self._ttt_buffer
        if len(buf) < self.TTT_MIN_SAMPLES:
            return
        samples = buf[-self.TTT_MAX_SAMPLES:]
        frames = np.stack([f for f, _ in samples])  # (N, 64, 64)
        targets = torch.tensor(
            [t for _, t in samples], dtype=torch.long, device=self.device
        )
        x = onehot_batch(frames).to(self.device)

        self.model.train()
        opt = torch.optim.Adam(self.model.parameters(), lr=self.TTT_LR)
        for _ in range(self.TTT_STEPS):
            opt.zero_grad()
            logits = self.model(x)  # unmasked: learn the demonstrated class
            loss = F.cross_entropy(logits, targets)
            loss.backward()
            opt.step()
        self.model.eval()

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


def _levels_completed(obs: Any) -> int:
    """Number of levels cleared so far, tolerant of obs/score shape."""
    v = getattr(obs, "levels_completed", None)
    if v is None:
        score = getattr(obs, "score", None)
        if isinstance(score, dict):
            v = score.get("levels_completed")
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


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
