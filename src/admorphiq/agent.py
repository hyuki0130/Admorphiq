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
from .utils import ExperienceBuffer, GameLogger
from .world_model import WorldModel


def _frame_to_tensor(frame: np.ndarray) -> torch.Tensor:
    """Convert (64, 64) canonical frame to (16, 64, 64) float one-hot tensor."""
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
        lr: float = 3e-4,
        batch_size: int = 64,
        train_frequency: int = 10,
        buffer_maxlen: int = 50_000,
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
        self._prev_raw_frame: np.ndarray | None = None
        self._prev_action_idx: int | None = None
        self._step_count: int = 0
        self._last_levels_completed: int = 0
        self._logger: GameLogger | None = None
        self._last_loss: float | None = None
        self._is_click_game: bool | None = None  # auto-detect: True if only ACTION6 available
        self._effective_coords: list[int] = []  # coord indices that caused frame changes
        self._no_change_streak: int = 0  # consecutive steps with no frame change
        # Momentum tracking for movement games
        self._action_change_counts: np.ndarray = np.zeros(5, dtype=np.float64)  # pixel change sum per simple action
        self._action_try_counts: np.ndarray = np.zeros(5, dtype=np.float64)  # times each simple action was tried
        self._last_big_change_action: int | None = None  # action that caused the biggest change
        self._repeat_count: int = 0  # how many times we've repeated the current momentum action
        self._max_repeat: int = 20  # max consecutive repeats before switching
        # State novelty tracking
        self._visited_states: set[str] = set()  # hashes of visited frames
        self._novelty_bonus: float = 0.3  # extra reward for reaching a new state

    def _reset_for_new_level(self, level_completed: bool = False) -> None:
        """Reset state for a new level. Preserves model weights for transfer."""
        self.buffer.clear()
        # Keep model weights — transfer learning across levels
        self.explorer.clear()

        if level_completed:
            self.memory.on_level_complete()
        else:
            self.memory.on_level_reset()

        self._prev_frame = None
        self._prev_raw_frame = None
        self._prev_action_idx = None
        self._step_count = 0
        self._effective_coords.clear()
        self._no_change_streak = 0
        self._action_change_counts = np.zeros(5, dtype=np.float64)
        self._action_try_counts = np.zeros(5, dtype=np.float64)
        self._last_big_change_action = None
        self._repeat_count = 0
        self._visited_states.clear()

    def set_logger(self, logger: GameLogger) -> None:
        """Attach a GameLogger for structured JSONL logging."""
        self._logger = logger

    @staticmethod
    def _compute_reward(frame_changed: bool, prev_raw: np.ndarray | None = None, curr_raw: np.ndarray | None = None) -> float:
        """Magnitude-scaled reward: proportional to pixel change count.

        Returns 0.0 for no change, scales up to 1.0 for large changes.
        This helps the agent prefer actions with bigger impact.
        """
        if not frame_changed:
            return 0.0
        if prev_raw is not None and curr_raw is not None:
            diff_count = int(np.count_nonzero(prev_raw.astype(int) - curr_raw.astype(int)))
            # Scale: 1 pixel -> 0.1, 10+ pixels -> 0.5, 50+ -> 0.8, 100+ -> ~1.0
            return min(1.0, 0.1 + 0.9 * (1.0 - np.exp(-diff_count / 30.0)))
        return 1.0

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
                if self._logger is not None:
                    self._logger.log_event("reset", {"reason": "game_over"})
            return GameAction.reset()

        # Detect level transition via score
        levels_completed = latest_frame.score.get("levels_completed", 0)
        if levels_completed > self._last_levels_completed:
            if self._logger is not None:
                self._logger.log_event("level_up", {"from": self._last_levels_completed, "to": levels_completed})
            self._last_levels_completed = levels_completed
            self._reset_for_new_level(level_completed=True)

        # Encode current frame
        current_frame = _frame_to_tensor(latest_frame.frame).to(self.device)

        # Record experience from previous step with magnitude-scaled reward + novelty bonus
        frame_changed = False
        reward = 0.0
        if self._prev_frame is not None and self._prev_action_idx is not None:
            frame_changed = not torch.equal(self._prev_frame, current_frame)
            reward = self._compute_reward(frame_changed, self._prev_raw_frame, latest_frame.frame)

            # Novelty bonus: extra reward for reaching a never-seen state
            state_hash = self.explorer.hash_frame(current_frame)
            if state_hash not in self._visited_states:
                self._visited_states.add(state_hash)
                reward = min(1.0, reward + self._novelty_bonus)

            self.buffer.add(
                self._prev_frame.cpu().numpy().astype(bool),
                self._prev_action_idx,
                reward,
                next_frame=current_frame.cpu().numpy().astype(bool),
            )
            # Track effective coords for click games
            if frame_changed and self._prev_action_idx >= 5:
                self._effective_coords.append(self._prev_action_idx)
                self._no_change_streak = 0
            elif not frame_changed:
                self._no_change_streak += 1
            else:
                self._no_change_streak = 0

            # Track pixel change magnitude per simple action (for momentum)
            if self._prev_action_idx < 5 and self._prev_raw_frame is not None:
                diff_count = int(np.count_nonzero(
                    latest_frame.frame.astype(int) - self._prev_raw_frame.astype(int)
                ))
                self._action_change_counts[self._prev_action_idx] += diff_count
                self._action_try_counts[self._prev_action_idx] += 1

            if self._logger is not None and self._prev_raw_frame is not None:
                self._logger.log_frame_diff(
                    self._step_count, self._prev_raw_frame,
                    latest_frame.frame, self._prev_action_idx,
                )

        # Build available actions mask
        available_mask = torch.zeros(1, 5, dtype=torch.bool, device=self.device)
        for action_type in latest_frame.available_actions:
            if action_type in _ACTION_TO_IDX:
                available_mask[0, _ACTION_TO_IDX[action_type]] = True
        action6_available = ActionType.ACTION6 in latest_frame.available_actions

        if not available_mask.any() and not action6_available:
            return GameAction.reset()

        # Auto-detect click-only games (like LP85)
        if self._is_click_game is None:
            has_simple = available_mask[0].any().item()
            self._is_click_game = not has_simple and action6_available

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

        # For click games: bias coords toward non-background pixels
        if self._is_click_game:
            coord_bias = self._get_coord_bias(latest_frame.frame)
            perception_probs[5:] = perception_probs[5:] * (1.0 + coord_bias * 9.0)

        # KEY: Scale coordinate probabilities by 1/4096 to prevent ACTION6 dominance
        perception_probs[5:] = perception_probs[5:] / 4096.0

        p_total = perception_probs.sum()
        if p_total > 0:
            perception_probs = perception_probs / p_total
        else:
            return GameAction.reset()

        # Action selection: momentum for movement games, perception for click games
        idx = self._select_action(perception_probs, available_mask[0].cpu().numpy())

        # Bookkeeping
        state_hash = self.explorer.hash_frame(current_frame)
        self._prev_frame = current_frame
        self._prev_raw_frame = latest_frame.frame
        self._prev_action_idx = idx
        self.explorer.record_action(state_hash, idx)
        self.memory.record_action(idx)
        if idx == self._last_big_change_action:
            self._repeat_count += 1

        # Periodic training (perception only, no world model)
        self._step_count += 1
        if self._step_count % self.train_frequency == 0 and len(self.buffer) >= self.batch_size:
            self._train_step()

        # Log step
        if self._logger is not None:
            action_name = f"coord({idx - 5})" if idx >= 5 else f"A{idx + 1}"
            top5_idx = np.argsort(perception_probs)[-5:][::-1]
            top5 = {(f"coord({i - 5})" if i >= 5 else f"A{i + 1}"): round(float(perception_probs[i]), 4) for i in top5_idx}
            self._logger.log_step(
                self._step_count, action_name, extra={
                    "action_idx": idx,
                    "frame_changed": frame_changed,
                    "reward": reward,
                    "top5_probs": top5,
                    "loss": self._last_loss,
                    "buffer_size": len(self.buffer),
                    "levels_completed": levels_completed,
                },
            )

        # Convert index to game action
        return self._idx_to_game_action(idx)

    def _select_action(self, perception_probs: np.ndarray, simple_mask: np.ndarray) -> int:
        """Select action using momentum for movement games, perception for click games.

        For movement games: after initial exploration (50 steps), use momentum strategy
        that repeats the most effective action direction. This helps navigate toward goals
        instead of random wandering.
        """
        has_simple = simple_mask.any()

        # Click games or early exploration: use pure perception
        if self._is_click_game or self._step_count < 50 or not has_simple:
            return int(np.random.choice(4101, p=perception_probs))

        # Momentum strategy for movement games
        # Every max_repeat steps or when stuck, pick a new direction
        if (self._last_big_change_action is not None
                and self._repeat_count < self._max_repeat
                and self._no_change_streak < 3):
            # Continue momentum: 70% repeat best action, 30% sample from perception
            if np.random.random() < 0.7:
                return self._last_big_change_action
            return int(np.random.choice(4101, p=perception_probs))

        # Pick new direction: choose the simple action with highest avg pixel change
        avg_changes = np.zeros(5, dtype=np.float64)
        for i in range(5):
            if self._action_try_counts[i] > 0 and simple_mask[i]:
                avg_changes[i] = self._action_change_counts[i] / self._action_try_counts[i]

        if avg_changes.max() > 0:
            # Softmax selection biased toward high-change actions
            temp = 2.0
            exp_vals = np.exp(avg_changes / max(avg_changes.max(), 1.0) * temp)
            exp_vals *= simple_mask[:5].astype(float)
            if exp_vals.sum() > 0:
                probs = exp_vals / exp_vals.sum()
                best = int(np.random.choice(5, p=probs))
                self._last_big_change_action = best
                self._repeat_count = 0
                return best

        # Fallback: perception sampling
        self._repeat_count = 0
        self._last_big_change_action = None
        return int(np.random.choice(4101, p=perception_probs))

    @staticmethod
    def _get_coord_bias(frame: np.ndarray) -> np.ndarray:
        """Generate a 4096-element bias array favoring non-background pixels.

        Pixels with color != 0 (background) get a boost, so click games
        target colored objects rather than empty space.
        """
        # frame is (64, 64) with values 0-15
        non_bg = (frame != 0).astype(np.float32)  # (64, 64)

        # Dilate with 5x5 kernel using numpy (boost neighbors too)
        padded = np.pad(non_bg, 2, mode="constant")
        dilated = np.zeros_like(non_bg)
        for dy in range(5):
            for dx in range(5):
                dilated = np.maximum(dilated, padded[dy:dy+64, dx:dx+64])

        # Flatten to 4096 (y * 64 + x ordering)
        return dilated.flatten()

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
        action_entropy = action_probs.mean()

        coord_probs = torch.sigmoid(coord_logits)
        coord_entropy = coord_probs.mean()

        total_loss = loss - self.action_entropy_coeff * action_entropy - self.coord_entropy_coeff * coord_entropy

        self.optimizer.zero_grad()
        total_loss.backward()
        self.optimizer.step()
        self._last_loss = round(float(total_loss.item()), 5)

    def _train_world_model_step(self) -> None:
        """One gradient step for the world model. Currently disabled for performance."""
        pass
