"""Admorphiq agent for ARC-AGI-3 interactive reasoning.

Based on StochasticGoose approach: pure perception CNN with binary reward,
coordinate /4096 scaling, and frequent online training.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F

from .perception import PerceptionModel
from .planner import GameMemory, SystematicExplorer
from .types import ActionType, FrameData, GameAction, GameState
from .utils import ExperienceBuffer
from .world_model import WorldModel


def _frame_to_tensor(frame: np.ndarray, raw_layers: np.ndarray | None = None) -> torch.Tensor:
    """Convert frame data into (16, 64, 64) float one-hot tensor.

    If raw_layers is provided (multi-layer frame), each layer is one-hot encoded
    independently and merged via element-wise max. Otherwise, the single (64, 64)
    index frame is one-hot encoded directly.
    """
    if raw_layers is not None and raw_layers.ndim == 3 and raw_layers.shape[0] > 1:
        layers = []
        for i in range(raw_layers.shape[0]):
            t = torch.from_numpy(raw_layers[i].astype(np.int64))  # (64, 64)
            onehot = F.one_hot(t.clamp(0, 15), num_classes=16)    # (64, 64, 16)
            layers.append(onehot.permute(2, 0, 1).float())        # (16, 64, 64)
        stacked = torch.stack(layers)          # (num_layers, 16, 64, 64)
        return stacked.max(dim=0).values       # (16, 64, 64)

    t = torch.from_numpy(frame.astype(np.int64))       # (64, 64)
    onehot = F.one_hot(t.clamp(0, 15), num_classes=16)  # (64, 64, 16)
    return onehot.permute(2, 0, 1).float()               # (16, 64, 64)


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
    """ARC-AGI-3 agent with CNN perception and online learning.

    Uses StochasticGoose-style approach: binary reward, coordinate /4096 scaling,
    pure perception model for action selection.
    """

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
        self.world_model = WorldModel().to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        self.wm_optimizer = torch.optim.Adam(self.world_model.parameters(), lr=self.lr)
        self.buffer = ExperienceBuffer(maxlen=buffer_maxlen)
        self.explorer = SystematicExplorer()
        self.memory = GameMemory()

        self._prev_frame: torch.Tensor | None = None
        self._prev_action_idx: int | None = None
        self._step_count: int = 0
        self._last_levels_completed: int = 0

    def _reset_for_new_level(self, level_completed: bool = False) -> None:
        """Reset state for a new level."""
        self.buffer.clear()
        self.model = PerceptionModel().to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        self.explorer.clear()

        if level_completed:
            self.memory.on_level_complete()
        else:
            self.memory.on_level_reset()

        self._prev_frame = None
        self._prev_action_idx = None
        self._step_count = 0

    @staticmethod
    def _compute_reward(frame_changed: bool) -> float:
        """Binary reward: 1.0 if frame changed, 0.0 otherwise."""
        return 1.0 if frame_changed else 0.0

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        """Check if the current game is complete."""
        return latest_frame.state == GameState.WIN

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction:
        """Select the next action given the current game state.

        Uses pure perception model with coordinate /4096 scaling.
        """
        # Handle terminal / not-started states
        if latest_frame.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            if latest_frame.state == GameState.GAME_OVER:
                self.memory.on_level_reset()
            return GameAction.reset()

        # Detect level transition via score
        levels_completed = latest_frame.score.get("levels_completed", 0)
        if levels_completed > self._last_levels_completed:
            self._last_levels_completed = levels_completed
            self._reset_for_new_level(level_completed=True)

        # Encode current frame
        current_frame = _frame_to_tensor(latest_frame.frame, latest_frame.raw_layers).to(self.device)

        # Record experience from previous step with binary reward
        if self._prev_frame is not None and self._prev_action_idx is not None:
            frame_changed = not torch.equal(self._prev_frame, current_frame)
            reward = self._compute_reward(frame_changed)
            self.buffer.add(
                self._prev_frame.cpu(),
                self._prev_action_idx,
                reward,
                next_frame=current_frame.cpu(),
            )

        # Build available actions mask
        available_mask = torch.zeros(1, 5, dtype=torch.bool, device=self.device)
        for action_type in latest_frame.available_actions:
            if action_type in _ACTION_TO_IDX:
                available_mask[0, _ACTION_TO_IDX[action_type]] = True
        action6_available = ActionType.ACTION6 in latest_frame.available_actions

        if not available_mask.any() and not action6_available:
            return GameAction.reset()

        # Perception model forward pass
        self.model.eval()
        with torch.no_grad():
            x = current_frame.unsqueeze(0)
            logits = self.model(x, available_actions=available_mask)

        # Sigmoid → mask → coordinate /4096 scaling → normalize
        logits_np = logits[0].cpu().numpy()  # (4101,)
        perception_probs = 1.0 / (1.0 + np.exp(-logits_np.clip(-20, 20)))

        mask_np = np.zeros(4101, dtype=bool)
        mask_np[:5] = available_mask[0].cpu().numpy()
        if action6_available:
            mask_np[5:] = True

        perception_probs = perception_probs * mask_np

        # KEY: Scale coordinate probabilities by 1/4096 to prevent ACTION6 dominance
        perception_probs[5:] = perception_probs[5:] / 4096.0

        p_total = perception_probs.sum()
        if p_total > 0:
            perception_probs = perception_probs / p_total
        else:
            return GameAction.reset()

        # Pure perception sampling (no world model / exploration blending)
        idx = int(np.random.choice(4101, p=perception_probs))

        # Bookkeeping
        state_hash = self.explorer.hash_frame(current_frame)
        self._prev_frame = current_frame
        self._prev_action_idx = idx
        self.explorer.record_action(state_hash, idx)
        self.memory.record_action(idx)

        # Periodic training (perception only, no world model)
        self._step_count += 1
        if self._step_count % self.train_frequency == 0 and len(self.buffer) >= self.batch_size:
            self._train_step()

        # Convert index to game action
        return self._idx_to_game_action(idx)

    @staticmethod
    def _idx_to_game_action(idx: int) -> GameAction:
        """Convert a logit index to a GameAction."""
        if idx < 5:
            return GameAction.simple(_IDX_TO_ACTION[idx])
        coord_idx = idx - 5
        x = coord_idx % 64
        y = coord_idx // 64
        return GameAction.coordinate(x, y)

    def _train_step(self) -> None:
        """One gradient step for the perception model."""
        self.model.train()
        frames, actions, rewards = self.buffer.sample(self.batch_size)
        frames = frames.to(self.device)
        actions = actions.to(self.device)
        rewards = rewards.to(self.device).clamp(0.0, 1.0)

        logits = self.model(frames)
        chosen_logits = logits.gather(1, actions.unsqueeze(1)).squeeze(1)
        loss = F.binary_cross_entropy_with_logits(chosen_logits, rewards)

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
        """One gradient step for the world model. Currently disabled for performance."""
        pass
