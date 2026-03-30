"""Admorphiq agent for ARC-AGI-3 interactive reasoning."""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

from .perception import PerceptionModel
from .types import ActionType, FrameData, GameAction, GameState
from .utils import ExperienceBuffer


def _frame_to_tensor(frame: np.ndarray) -> torch.Tensor:
    """One-hot encode a (64, 64) uint8 frame into (16, 64, 64) float tensor."""
    t = torch.from_numpy(frame.astype(np.int64))  # (64, 64)
    onehot = F.one_hot(t, num_classes=16)          # (64, 64, 16)
    return onehot.permute(2, 0, 1).float()         # (16, 64, 64)


# Maps ACTION1~5 to indices 0~4 in the logit vector
_ACTION_TO_IDX = {
    ActionType.ACTION1: 0,
    ActionType.ACTION2: 1,
    ActionType.ACTION3: 2,
    ActionType.ACTION4: 3,
    ActionType.ACTION5: 4,
}

_IDX_TO_ACTION = {v: k for k, v in _ACTION_TO_IDX.items()}


class AdmorphiqAgent:
    """ARC-AGI-3 agent with CNN perception, experience buffer, and online learning."""

    def __init__(
        self,
        device: str = "cpu",
        lr: float = 1e-4,
        batch_size: int = 64,
        train_frequency: int = 5,
        buffer_maxlen: int = 200_000,
        action_entropy_coeff: float = 1e-4,
        coord_entropy_coeff: float = 1e-5,
    ) -> None:
        self.device = torch.device(device)
        self.lr = lr
        self.batch_size = batch_size
        self.train_frequency = train_frequency
        self.action_entropy_coeff = action_entropy_coeff
        self.coord_entropy_coeff = coord_entropy_coeff

        self.model = PerceptionModel().to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        self.buffer = ExperienceBuffer(maxlen=buffer_maxlen)

        self._prev_frame: torch.Tensor | None = None
        self._prev_action_idx: int | None = None
        self._step_count: int = 0
        self._last_levels_completed: int = 0

    def _reset_for_new_level(self) -> None:
        """Reset buffer and reinitialize model/optimizer for a new level."""
        self.buffer.clear()
        self.model = PerceptionModel().to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        self._prev_frame = None
        self._prev_action_idx = None
        self._step_count = 0

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        """Check if the current game is complete."""
        return latest_frame.state == GameState.WIN

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction:
        """Select the next action given the current game state."""
        # Handle terminal / not-started states
        if latest_frame.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            return GameAction.reset()

        # Detect level transition via score
        levels_completed = latest_frame.score.get("levels_completed", 0)
        if levels_completed > self._last_levels_completed:
            self._last_levels_completed = levels_completed
            self._reset_for_new_level()

        # Encode current frame
        current_frame = _frame_to_tensor(latest_frame.frame).to(self.device)  # (16, 64, 64)

        # Record experience from previous step
        if self._prev_frame is not None and self._prev_action_idx is not None:
            frame_changed = not torch.equal(self._prev_frame, current_frame)
            self.buffer.add(self._prev_frame.cpu(), self._prev_action_idx, frame_changed)

        # Build available actions mask — (1, 5) bool
        available_mask = torch.zeros(1, 5, dtype=torch.bool, device=self.device)
        for action_type in latest_frame.available_actions:
            if action_type in _ACTION_TO_IDX:
                available_mask[0, _ACTION_TO_IDX[action_type]] = True
        action6_available = ActionType.ACTION6 in latest_frame.available_actions

        # If no simple actions and no ACTION6, just reset
        if not available_mask.any() and not action6_available:
            return GameAction.reset()

        # Forward pass
        self.model.eval()
        with torch.no_grad():
            x = current_frame.unsqueeze(0)  # (1, 16, 64, 64)
            logits = self.model(x, available_actions=available_mask)  # (1, 4101)

        # Hierarchical sampling: sigmoid → normalize → sample
        logits_np = logits[0].cpu().numpy()  # (4101,)
        probs = 1.0 / (1.0 + np.exp(-logits_np.clip(-20, 20)))

        # Mask unavailable actions
        mask_np = np.zeros(4101, dtype=bool)
        mask_np[:5] = available_mask[0].cpu().numpy()
        if action6_available:
            mask_np[5:] = True

        probs = probs * mask_np
        total = probs.sum()
        if total <= 0:
            return GameAction.reset()
        probs = probs / total

        idx = int(np.random.choice(4101, p=probs))

        # Store for next step's experience recording
        self._prev_frame = current_frame
        self._prev_action_idx = idx

        # Periodic training
        self._step_count += 1
        if self._step_count % self.train_frequency == 0 and len(self.buffer) >= self.batch_size:
            self._train_step()

        # Convert index to game action
        if idx < 5:
            return GameAction.simple(_IDX_TO_ACTION[idx])
        else:
            coord_idx = idx - 5
            x = coord_idx % 64
            y = coord_idx // 64
            return GameAction.coordinate(x, y)

    def _train_step(self) -> None:
        """One gradient step on a sampled batch from the experience buffer."""
        self.model.train()
        frames, actions, labels = self.buffer.sample(self.batch_size)
        frames = frames.to(self.device)    # (B, 16, 64, 64)
        actions = actions.to(self.device)  # (B,)
        labels = labels.to(self.device).float()  # (B,)

        logits = self.model(frames)  # (B, 4101)

        # Gather the logit for the chosen action
        chosen_logits = logits.gather(1, actions.unsqueeze(1)).squeeze(1)  # (B,)

        # BCE loss: predict whether the action caused a frame change
        loss = F.binary_cross_entropy_with_logits(chosen_logits, labels)

        # Entropy regularization to encourage exploration
        action_logits = logits[:, :5]   # (B, 5)
        coord_logits = logits[:, 5:]    # (B, 4096)

        action_probs = torch.sigmoid(action_logits)
        action_entropy = -(
            action_probs * torch.log(action_probs + 1e-8)
            + (1 - action_probs) * torch.log(1 - action_probs + 1e-8)
        ).mean()

        coord_probs = torch.sigmoid(coord_logits)
        coord_entropy = -(
            coord_probs * torch.log(coord_probs + 1e-8)
            + (1 - coord_probs) * torch.log(1 - coord_probs + 1e-8)
        ).mean()

        # Subtract entropy (maximize entropy = minimize negative entropy)
        total_loss = loss - self.action_entropy_coeff * action_entropy - self.coord_entropy_coeff * coord_entropy

        self.optimizer.zero_grad()
        total_loss.backward()
        self.optimizer.step()
