"""Admorphiq agent for ARC-AGI-3 interactive reasoning."""

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


# --- Reward constants ---
REWARD_NO_CHANGE = 0.0
REWARD_FRAME_CHANGED = 0.3
REWARD_LEVEL_UP = 1.0
REWARD_GAME_OVER = -0.5

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
    """ARC-AGI-3 agent with CNN perception, world model, exploration, and memory."""

    def __init__(
        self,
        device: str = "cpu",
        lr: float = 1e-4,
        batch_size: int = 64,
        train_frequency: int = 20,
        buffer_maxlen: int = 200_000,
        action_entropy_coeff: float = 1e-4,
        coord_entropy_coeff: float = 1e-5,
        alpha: float = 0.4,
        beta: float = 0.3,
        gamma: float = 0.3,
        exploration_steps: int = 20,
        memory_replay_prob: float = 0.5,
    ) -> None:
        self.device = torch.device(device)
        self.lr = lr
        self.batch_size = batch_size
        self.train_frequency = train_frequency
        self.action_entropy_coeff = action_entropy_coeff
        self.coord_entropy_coeff = coord_entropy_coeff

        # Blending weights: perception / world_model / exploration
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.exploration_steps = exploration_steps
        self.memory_replay_prob = memory_replay_prob

        self.model = PerceptionModel().to(self.device)
        self.world_model = WorldModel().to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        self.wm_optimizer = torch.optim.Adam(self.world_model.parameters(), lr=self.lr)
        self.buffer = ExperienceBuffer(maxlen=buffer_maxlen)
        self.explorer = SystematicExplorer()
        self.memory = GameMemory()

        self._prev_frame: torch.Tensor | None = None
        self._prev_action_idx: int | None = None
        self._prev_levels_completed: int = 0
        self._step_count: int = 0
        self._last_levels_completed: int = 0

    def _reset_for_new_level(self, level_completed: bool = False) -> None:
        """Reset state for a new level. Optionally preserves memory on success."""
        self.buffer.clear()
        self.model = PerceptionModel().to(self.device)
        self.world_model = WorldModel().to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        self.wm_optimizer = torch.optim.Adam(self.world_model.parameters(), lr=self.lr)
        self.explorer.clear()

        if level_completed:
            self.memory.on_level_complete()
        else:
            self.memory.on_level_reset()

        self._prev_frame = None
        self._prev_action_idx = None
        self._step_count = 0

    def _compute_reward(
        self,
        frame_changed: bool,
        prev_levels: int,
        curr_levels: int,
        state: GameState,
    ) -> float:
        """Compute reward based on frame change, level progress, and game state."""
        if curr_levels > prev_levels:
            return REWARD_LEVEL_UP
        if state == GameState.GAME_OVER:
            return max(REWARD_GAME_OVER, 0.0)  # clamp to 0 for BCE target
        if frame_changed:
            return REWARD_FRAME_CHANGED
        return REWARD_NO_CHANGE

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        """Check if the current game is complete."""
        return latest_frame.state == GameState.WIN

    def _get_world_model_probs(
        self,
        current_frame: torch.Tensor,
        available_mask: torch.Tensor,
        action6_available: bool,
    ) -> np.ndarray | None:
        """Get change-prediction-weighted probabilities from the world model."""
        if len(self.buffer) < self.batch_size:
            return None

        self.world_model.eval()
        with torch.no_grad():
            wm_probs = np.zeros(4101, dtype=np.float64)

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

            if action6_available:
                grid_x = []
                grid_y = []
                for gy in range(4, 64, 8):
                    for gx in range(4, 64, 8):
                        grid_x.append(gx)
                        grid_y.append(gy)

                n_grid = len(grid_x)
                grid_change_probs = self.world_model.predict_change_probs(
                    current_frame,
                    action_indices=[_ACTION_TYPE_TO_WM_IDX[ActionType.ACTION6]] * n_grid,
                    coord_x=grid_x,
                    coord_y=grid_y,
                )

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
        """Select the next action given the current game state.

        Flow:
        1. GameState check (NOT_PLAYED/GAME_OVER -> RESET)
        2. Level transition detection
        3. Record previous experience with reward
        4. Memory replay check
        5. Systematic exploration (early steps)
        6. Model-based selection (perception + world model + exploration bonus)
        7. Train periodically
        """
        # 1. Handle terminal / not-started states
        if latest_frame.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            if latest_frame.state == GameState.GAME_OVER:
                self.memory.on_level_reset()
            return GameAction.reset()

        # 2. Detect level transition via score
        levels_completed = latest_frame.score.get("levels_completed", 0)
        if levels_completed > self._last_levels_completed:
            self._prev_levels_completed = self._last_levels_completed
            self._last_levels_completed = levels_completed
            self._reset_for_new_level(level_completed=True)

        # Encode current frame
        current_frame = _frame_to_tensor(latest_frame.frame, latest_frame.raw_layers).to(self.device)

        # 3. Record experience from previous step with computed reward
        if self._prev_frame is not None and self._prev_action_idx is not None:
            frame_changed = not torch.equal(self._prev_frame, current_frame)
            reward = self._compute_reward(
                frame_changed,
                self._prev_levels_completed,
                levels_completed,
                latest_frame.state,
            )
            self.buffer.add(
                self._prev_frame.cpu(),
                self._prev_action_idx,
                reward,
                next_frame=current_frame.cpu(),
            )

        # Build available actions info
        available_mask = torch.zeros(1, 5, dtype=torch.bool, device=self.device)
        available_simple_indices: list[int] = []
        for action_type in latest_frame.available_actions:
            if action_type in _ACTION_TO_IDX:
                idx = _ACTION_TO_IDX[action_type]
                available_mask[0, idx] = True
                available_simple_indices.append(idx)
        action6_available = ActionType.ACTION6 in latest_frame.available_actions

        if not available_mask.any() and not action6_available:
            return GameAction.reset()

        # State hash for explorer
        state_hash = self.explorer.hash_frame(current_frame)

        # 4. Memory replay — if we have successful sequences, replay with some probability
        memory_candidates = self.memory.suggest_from_memory()
        if memory_candidates and np.random.random() < self.memory_replay_prob:
            idx = np.random.choice(memory_candidates)
            self._finalize_action(idx, current_frame, state_hash)
            return self._idx_to_game_action(idx)

        # 5. Systematic exploration — during early steps, try untried actions
        if self._step_count < self.exploration_steps:
            suggested = self.explorer.suggest_action(state_hash, available_simple_indices, action6_available)
            if suggested is not None:
                self._finalize_action(suggested, current_frame, state_hash)
                return self._idx_to_game_action(suggested)

        # 6. Model-based selection with blended probabilities

        # Perception model
        self.model.eval()
        with torch.no_grad():
            x = current_frame.unsqueeze(0)
            logits = self.model(x, available_actions=available_mask)

        logits_np = logits[0].cpu().numpy()
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

        # World model
        wm_probs = self._get_world_model_probs(current_frame, available_mask, action6_available)

        # Exploration bonus
        exploration_bonus = self.explorer.get_exploration_bonuses(state_hash, 4101, mask_np)
        e_total = exploration_bonus.sum()
        if e_total > 0:
            exploration_bonus = exploration_bonus / e_total

        # Combine
        combined = self.alpha * perception_probs
        if wm_probs is not None:
            combined = combined + self.beta * wm_probs
        else:
            combined = combined + self.beta * perception_probs  # fallback to perception
        if e_total > 0:
            combined = combined + self.gamma * exploration_bonus

        total = combined.sum()
        if total > 0:
            combined = combined / total
        else:
            return GameAction.reset()

        idx = int(np.random.choice(4101, p=combined))
        self._finalize_action(idx, current_frame, state_hash)
        return self._idx_to_game_action(idx)

    def _finalize_action(self, idx: int, current_frame: torch.Tensor, state_hash: str) -> None:
        """Common post-action bookkeeping."""
        self._prev_frame = current_frame
        self._prev_action_idx = idx
        self._prev_levels_completed = self._last_levels_completed

        self.explorer.record_action(state_hash, idx)
        self.memory.record_action(idx)

        self._step_count += 1
        if self._step_count % self.train_frequency == 0 and len(self.buffer) >= self.batch_size:
            self._train_step()
            self._train_world_model_step()

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
        rewards = rewards.to(self.device).clamp(0.0, 1.0)  # clamp for BCE

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
        """One gradient step for the world model."""
        result = self.buffer.sample_with_next(self.batch_size)
        if result is None:
            return

        self.world_model.train()
        frames, actions, rewards, next_frames = result
        frames = frames.to(self.device)
        actions = actions.to(self.device)
        rewards = rewards.to(self.device).clamp(0.0, 1.0)
        next_frames = next_frames.to(self.device)

        wm_action_idx = torch.where(actions < 5, actions, torch.tensor(5, device=self.device))
        coord_x = torch.where(actions >= 5, (actions - 5) % 64, torch.zeros_like(actions))
        coord_y = torch.where(actions >= 5, (actions - 5) // 64, torch.zeros_like(actions))

        predicted_next, change_logit = self.world_model(frames, wm_action_idx, coord_x, coord_y)

        frame_loss = F.mse_loss(predicted_next, next_frames)
        change_loss = F.binary_cross_entropy_with_logits(change_logit, rewards)

        total_loss = frame_loss + change_loss

        self.wm_optimizer.zero_grad()
        total_loss.backward()
        self.wm_optimizer.step()
