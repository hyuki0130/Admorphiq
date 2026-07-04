"""Small NEURAL forward model for the test-time online RL agent (R32).

Two structural walls killed every prior world-model attempt on ARC-AGI-3:

1. **State-uniqueness** — ARC frames are near-unique (step counters, motion,
   animated overlays), so a TABULAR ``(state-signature, action)`` transition
   table never has a row for the *current* frame and never fires (R10, R27b both
   dead-on-arrival).
2. **Online-convergence** — a BIGGER net does not converge inside the per-game
   action budget (R24, 1.5x policy collapsed).

This model beats both:

* It is **neural and convolutional**, so it GENERALISES across unseen frames
  (a conv predicts per-pixel change from local structure, not from an exact
  state hash) — beating wall 1.
* It predicts the **CHANGE-MASK** (which cells change), a single 64x64 binary
  map, NOT full RGB / one-hot pixels. That target is far easier and faster to
  learn than reconstructing a frame, so the net is TINY (a few conv layers,
  ``<< the 34M policy``) and converges within the per-game budget — beating
  wall 2.

It is SEPARATE from the policy net: the policy is never touched. The agent
trains this model online from its own stored ``(frame, action, next_frame)``
transitions and — only when ``RL_FWD_PLAN_HORIZON > 0`` and the model has
trained enough to be trusted — uses it for short-horizon planning
(:mod:`admorphiq.online_rl_agent`). The default horizon 0 makes the whole
planner inert, so the deployed card is reproduced byte-for-byte.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

# Action encoding layout (mirrors the agent's combined-index space).
#   * 5 simple actions (ACTION1..5) -> one-hot slots 0..4.
#   * 1 ACTION6 (coordinate click)  -> one-hot slot 5.
#   * (slots 6,7 reserved: RESET / ACTION7, never used as a policy action here,
#     kept so the "8 action types" contract in the design is exact.)
#   * + 2 normalised coordinate scalars (x/64, y/64), zero for non-ACTION6.
NUM_ACTION_SLOTS = 8
ACTION_FEAT_DIM = NUM_ACTION_SLOTS + 2  # one-hot type + (x_norm, y_norm)
ACTION6_SLOT = 5
NUM_SIMPLE_ACTIONS = 5
GRID = 64


def encode_action(action_idx: int, action_feat_dim: int = ACTION_FEAT_DIM) -> torch.Tensor:
    """Encode a combined-logit action index as an ``(ACTION_FEAT_DIM,)`` vector.

    ``action_idx < 5`` is a simple action (ACTION1..5) -> one-hot in slots 0..4,
    coordinate scalars zero. ``action_idx >= 5`` is an ACTION6 click whose
    combined index carries the flattened 64x64 coordinate: slot 5 is set and the
    two trailing scalars hold the normalised ``(x/64, y/64)`` so the model can
    condition its change prediction on WHERE the click landed.
    """
    vec = torch.zeros(action_feat_dim)
    if action_idx < NUM_SIMPLE_ACTIONS:  # simple actions occupy slots 0..4
        vec[action_idx] = 1.0
    else:
        vec[ACTION6_SLOT] = 1.0
        coord = action_idx - NUM_SIMPLE_ACTIONS
        x = (coord % GRID) / GRID
        y = (coord // GRID) / GRID
        vec[NUM_ACTION_SLOTS] = x
        vec[NUM_ACTION_SLOTS + 1] = y
    return vec


class ForwardModel(nn.Module):
    """Conv net predicting the per-cell CHANGE-MASK of ``(frame, action)``.

    Input: a 16-channel one-hot frame ``(B, 16, 64, 64)`` concatenated with the
    action broadcast to ``action_planes`` spatial planes ``(B, action_planes,
    64, 64)``. Output: a single change-mask logit map ``(B, 64, 64)`` — the
    predicted probability (pre-sigmoid) that each cell's colour changes under the
    action. Deliberately small (default ~0.06M params) so it converges online.
    """

    def __init__(self, hidden: int = 32, action_planes: int = 16) -> None:
        super().__init__()
        self.action_planes = action_planes
        # Project the compact action feature to ``action_planes`` scalars that are
        # broadcast across the 64x64 grid and concatenated with the frame.
        self.action_proj = nn.Linear(ACTION_FEAT_DIM, action_planes)
        in_ch = 16 + action_planes
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, hidden, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, hidden, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, 1, kernel_size=1),
        )

    def forward(self, frame: torch.Tensor, action_feat: torch.Tensor) -> torch.Tensor:
        """Predict change-mask logits.

        Args:
            frame: One-hot frames ``(B, 16, 64, 64)`` (float).
            action_feat: Action features ``(B, ACTION_FEAT_DIM)`` from
                :func:`encode_action`.

        Returns:
            Change-mask logits ``(B, 64, 64)`` (pre-sigmoid).
        """
        b = frame.shape[0]
        planes = self.action_proj(action_feat)                 # (B, action_planes)
        planes = planes.view(b, self.action_planes, 1, 1)
        planes = planes.expand(b, self.action_planes, GRID, GRID)
        x = torch.cat([frame, planes], dim=1)                  # (B, 16+ap, 64, 64)
        return self.net(x).squeeze(1)                          # (B, 64, 64)

    @staticmethod
    def change_mask_target(frame: torch.Tensor, next_frame: torch.Tensor) -> torch.Tensor:
        """Per-cell binary change target: 1 where the one-hot colour differs.

        Both inputs are one-hot ``(B, 16, 64, 64)``; a cell changed iff its
        16-channel colour vector differs between frame and next_frame. Returns a
        float ``(B, 64, 64)`` mask suitable for BCE-with-logits against
        :meth:`forward`.
        """
        diff = (frame != next_frame).any(dim=1)                # (B, 64, 64) bool
        return diff.float()

    def loss(
        self, frame: torch.Tensor, action_feat: torch.Tensor, next_frame: torch.Tensor
    ) -> torch.Tensor:
        """BCE-with-logits between the predicted and the true change-mask."""
        logits = self.forward(frame, action_feat)
        target = self.change_mask_target(frame, next_frame)
        return F.binary_cross_entropy_with_logits(logits, target)

    def predicted_change(
        self, frame: torch.Tensor, action_feat: torch.Tensor
    ) -> torch.Tensor:
        """Per-sample expected number of changed cells (sum of sigmoid probs).

        Used by the planner as a cheap scalar "how much does this action do"
        score. Shape ``(B,)``.
        """
        with torch.no_grad():
            probs = torch.sigmoid(self.forward(frame, action_feat))  # (B,64,64)
        return probs.flatten(1).sum(dim=1)                            # (B,)
