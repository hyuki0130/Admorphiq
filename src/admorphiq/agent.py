"""Admorphiq agent for ARC-AGI-3 interactive reasoning."""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

from .perception import PerceptionModel
from .types import ActionType, FrameData, GameAction, GameState
from .utils import ExperienceBuffer
from .world_model import WorldModel


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

# Maps ActionType enum to world model action index (0-based)
_ACTION_TYPE_TO_WM_IDX = {
    ActionType.ACTION1: 0,
    ActionType.ACTION2: 1,
    ActionType.ACTION3: 2,
    ActionType.ACTION4: 3,
    ActionType.ACTION5: 4,
    ActionType.ACTION6: 5,
    ActionType.ACTION7: 6,
    ActionType.RESET: 7,
}


class AdmorphiqAgent:
    """ARC-AGI-3 agent with CNN perception, world model, and online learning."""

    def __init__(
        self,
        device: str = "cpu",
        lr: float = 1e-4,
        batch_size: int = 64,
        train_frequency: int = 5,
        buffer_maxlen: int = 200_000,
        action_entropy_coeff: float = 1e-4,
        coord_entropy_coeff: float = 1e-5,
        alpha: float = 0.5,
    ) -> None:
        self.device = torch.device(device)
        self.lr = lr
        self.batch_size = batch_size
        self.train_frequency = train_frequency
        self.action_entropy_coeff = action_entropy_coeff
        self.coord_entropy_coeff = coord_entropy_coeff
        self.alpha = alpha  # perception vs world model blend

        self.model = PerceptionModel().to(self.device)
        self.world_model = WorldModel().to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        self.wm_optimizer = torch.optim.Adam(self.world_model.parameters(), lr=self.lr)
        self.buffer = ExperienceBuffer(maxlen=buffer_maxlen)

        self._prev_frame: torch.Tensor | None = None
        self._prev_action_idx: int | None = None
        self._step_count: int = 0
        self._last_levels_completed: int = 0

    def _reset_for_new_level(self) -> None:
        """Reset buffer and reinitialize models/optimizers for a new level."""
        self.buffer.clear()
        self.model = PerceptionModel().to(self.device)
        self.world_model = WorldModel().to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        self.wm_optimizer = torch.optim.Adam(self.world_model.parameters(), lr=self.lr)
        self._prev_frame = None
        self._prev_action_idx = None
        self._step_count = 0

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        """Check if the current game is complete."""
        return latest_frame.state == GameState.WIN

    def _get_world_model_probs(
        self,
        current_frame: torch.Tensor,
        available_mask: torch.Tensor,
        action6_available: bool,
    ) -> np.ndarray | None:
        """Get change-prediction-weighted probabilities from the world model.

        Returns None if the world model hasn't been trained yet.
        """
        if len(self.buffer) < self.batch_size:
            return None

        self.world_model.eval()
        with torch.no_grad():
            # Evaluate change probability for each available simple action
            wm_probs = np.zeros(4101, dtype=np.float64)

            # Simple actions (ACTION1~5)
            available_simple = []
            wm_action_indices = []
            logit_indices = []
            for action_type, logit_idx in _ACTION_TO_IDX.items():
                if available_mask[0, logit_idx]:
                    available_simple.append(action_type)
                    wm_action_indices.append(_ACTION_TYPE_TO_WM_IDX[action_type])
                    logit_indices.append(logit_idx)

            if available_simple:
                change_probs = self.world_model.predict_change_probs(
                    current_frame,
                    action_indices=wm_action_indices,
                    coord_x=[None] * len(available_simple),
                    coord_y=[None] * len(available_simple),
                )
                for i, logit_idx in enumerate(logit_indices):
                    wm_probs[logit_idx] = change_probs[i].item()

            # ACTION6 coordinates — sample a grid of candidate positions
            if action6_available:
                # Evaluate on a 8x8 grid (stride=8) then interpolate
                grid_coords_x = list(range(4, 64, 8))  # 8 points
                grid_coords_y = list(range(4, 64, 8))  # 8 points
                grid_x = []
                grid_y = []
                for gy in grid_coords_y:
                    for gx in grid_coords_x:
                        grid_x.append(gx)
                        grid_y.append(gy)

                n_grid = len(grid_x)
                grid_change_probs = self.world_model.predict_change_probs(
                    current_frame,
                    action_indices=[_ACTION_TYPE_TO_WM_IDX[ActionType.ACTION6]] * n_grid,
                    coord_x=grid_x,
                    coord_y=grid_y,
                )

                # Map grid probs to full 64x64 using nearest neighbor
                prob_grid = grid_change_probs.cpu().numpy().reshape(8, 8)
                for y in range(64):
                    for x in range(64):
                        gi = min(y // 8, 7)
                        gj = min(x // 8, 7)
                        wm_probs[5 + y * 64 + x] = prob_grid[gi, gj]

            total = wm_probs.sum()
            if total > 0:
                wm_probs = wm_probs / total
                return wm_probs

        return None

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

        # Record experience from previous step (with next_frame for world model)
        if self._prev_frame is not None and self._prev_action_idx is not None:
            frame_changed = not torch.equal(self._prev_frame, current_frame)
            self.buffer.add(
                self._prev_frame.cpu(),
                self._prev_action_idx,
                frame_changed,
                next_frame=current_frame.cpu(),
            )

        # Build available actions mask — (1, 5) bool
        available_mask = torch.zeros(1, 5, dtype=torch.bool, device=self.device)
        for action_type in latest_frame.available_actions:
            if action_type in _ACTION_TO_IDX:
                available_mask[0, _ACTION_TO_IDX[action_type]] = True
        action6_available = ActionType.ACTION6 in latest_frame.available_actions

        # If no simple actions and no ACTION6, just reset
        if not available_mask.any() and not action6_available:
            return GameAction.reset()

        # Perception model forward pass
        self.model.eval()
        with torch.no_grad():
            x = current_frame.unsqueeze(0)  # (1, 16, 64, 64)
            logits = self.model(x, available_actions=available_mask)  # (1, 4101)

        # Perception probabilities: sigmoid → mask → normalize
        logits_np = logits[0].cpu().numpy()  # (4101,)
        perception_probs = 1.0 / (1.0 + np.exp(-logits_np.clip(-20, 20)))

        mask_np = np.zeros(4101, dtype=bool)
        mask_np[:5] = available_mask[0].cpu().numpy()
        if action6_available:
            mask_np[5:] = True

        perception_probs = perception_probs * mask_np
        p_total = perception_probs.sum()
        if p_total > 0:
            perception_probs = perception_probs / p_total
        else:
            return GameAction.reset()

        # World model change prediction probabilities
        wm_probs = self._get_world_model_probs(current_frame, available_mask, action6_available)

        # Combine: alpha * perception + (1-alpha) * world_model
        if wm_probs is not None:
            combined = self.alpha * perception_probs + (1.0 - self.alpha) * wm_probs
            total = combined.sum()
            if total > 0:
                combined = combined / total
            else:
                combined = perception_probs
        else:
            combined = perception_probs

        idx = int(np.random.choice(4101, p=combined))

        # Store for next step's experience recording
        self._prev_frame = current_frame
        self._prev_action_idx = idx

        # Periodic training (both models)
        self._step_count += 1
        if self._step_count % self.train_frequency == 0 and len(self.buffer) >= self.batch_size:
            self._train_step()
            self._train_world_model_step()

        # Convert index to game action
        if idx < 5:
            return GameAction.simple(_IDX_TO_ACTION[idx])
        else:
            coord_idx = idx - 5
            x = coord_idx % 64
            y = coord_idx // 64
            return GameAction.coordinate(x, y)

    def _train_step(self) -> None:
        """One gradient step for the perception model."""
        self.model.train()
        frames, actions, labels = self.buffer.sample(self.batch_size)
        frames = frames.to(self.device)    # (B, 16, 64, 64)
        actions = actions.to(self.device)  # (B,)
        labels = labels.to(self.device).float()  # (B,)

        logits = self.model(frames)  # (B, 4101)

        chosen_logits = logits.gather(1, actions.unsqueeze(1)).squeeze(1)  # (B,)
        loss = F.binary_cross_entropy_with_logits(chosen_logits, labels)

        # Entropy regularization
        action_logits = logits[:, :5]
        coord_logits = logits[:, 5:]

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

        total_loss = loss - self.action_entropy_coeff * action_entropy - self.coord_entropy_coeff * coord_entropy

        self.optimizer.zero_grad()
        total_loss.backward()
        self.optimizer.step()

    def _train_world_model_step(self) -> None:
        """One gradient step for the world model."""
        result = self.buffer.sample_with_next(self.batch_size)
        if result is None:
            return

        self.world_model.train()
        frames, actions, labels, next_frames = result
        frames = frames.to(self.device)          # (B, 16, 64, 64)
        actions = actions.to(self.device)        # (B,)
        labels = labels.to(self.device).float()  # (B,)
        next_frames = next_frames.to(self.device)  # (B, 16, 64, 64)

        # Map buffer action indices to world model action indices
        # Buffer indices: 0-4 = ACTION1-5, 5+ = ACTION6 coordinates
        wm_action_idx = torch.where(actions < 5, actions, torch.tensor(5, device=self.device))  # (B,)
        coord_x = torch.where(actions >= 5, (actions - 5) % 64, torch.zeros_like(actions))
        coord_y = torch.where(actions >= 5, (actions - 5) // 64, torch.zeros_like(actions))

        predicted_next, change_logit = self.world_model(frames, wm_action_idx, coord_x, coord_y)

        # MSE loss for next frame prediction
        frame_loss = F.mse_loss(predicted_next, next_frames)

        # BCE loss for change prediction
        change_loss = F.binary_cross_entropy_with_logits(change_logit, labels)

        total_loss = frame_loss + change_loss

        self.wm_optimizer.zero_grad()
        total_loss.backward()
        self.wm_optimizer.step()
