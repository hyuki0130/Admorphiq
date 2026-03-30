"""World Model: predicts next state and change probability from (state, action)."""

import torch
import torch.nn as nn

from .encoder import StateEncoder
from .transition import ActionEmbedding, ChangePredictor, TransitionPredictor


class WorldModel(nn.Module):
    """Predicts next frame and change probability given current frame and action.

    Architecture:
        1. StateEncoder: frame → state features (256, 64, 64)
        2. ActionEmbedding: action → spatial embedding (33, 64, 64)
        3. TransitionPredictor: (state, action) → frame delta (16, 64, 64)
        4. ChangePredictor: (state, action) → change logit (scalar)

    Next frame prediction is residual: next_frame = current_frame + delta.
    """

    def __init__(self) -> None:
        super().__init__()
        self.encoder = StateEncoder()
        self.action_embedding = ActionEmbedding()
        self.transition = TransitionPredictor()
        self.change_predictor = ChangePredictor()

    def forward(
        self,
        frame: torch.Tensor,
        action_idx: torch.Tensor,
        coord_x: torch.Tensor | None = None,
        coord_y: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Predict next frame and change probability.

        Args:
            frame: Current one-hot frame of shape (batch, 16, 64, 64).
            action_idx: Action type indices of shape (batch,), values 0-7.
            coord_x: X coordinates of shape (batch,), 0-63. None for non-ACTION6.
            coord_y: Y coordinates of shape (batch,), 0-63. None for non-ACTION6.

        Returns:
            Tuple of:
                - predicted_next_frame: (batch, 16, 64, 64)
                - change_logit: (batch,)
        """
        state_features = self.encoder(frame)  # (B, 256, 64, 64)
        action_features = self.action_embedding(action_idx, coord_x, coord_y)  # (B, 33, 64, 64)

        delta = self.transition(state_features, action_features)  # (B, 16, 64, 64)
        predicted_next = frame + delta  # residual prediction

        change_logit = self.change_predictor(state_features, action_features)  # (B,)

        return predicted_next, change_logit

    def predict_change_probs(
        self,
        frame: torch.Tensor,
        action_indices: list[int],
        coord_x: list[int | None] | None = None,
        coord_y: list[int | None] | None = None,
    ) -> torch.Tensor:
        """Predict change probability for multiple actions on the same frame.

        Args:
            frame: Single frame of shape (16, 64, 64).
            action_indices: List of N action type indices to evaluate.
            coord_x: List of N x coordinates (None for non-ACTION6).
            coord_y: List of N y coordinates (None for non-ACTION6).

        Returns:
            Change probabilities of shape (N,).
        """
        n = len(action_indices)
        device = frame.device

        # Repeat frame for each candidate action
        frames = frame.unsqueeze(0).expand(n, -1, -1, -1)  # (N, 16, 64, 64)
        act_idx = torch.tensor(action_indices, dtype=torch.long, device=device)  # (N,)

        cx = None
        cy = None
        if coord_x is not None:
            cx = torch.tensor([x if x is not None else 0 for x in coord_x], dtype=torch.long, device=device)
        if coord_y is not None:
            cy = torch.tensor([y if y is not None else 0 for y in coord_y], dtype=torch.long, device=device)

        _, change_logits = self(frames, act_idx, cx, cy)
        return torch.sigmoid(change_logits)  # (N,)
