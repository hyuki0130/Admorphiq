"""R32 neural forward (change-mask) model + action-plane encoding.

Reconstructed to the contract pinned by tests/test_forward_model.py and the R33
planner (planner/goal.py), after the original R33 worktree copy was lost.

Why a NEURAL forward model (30-round context):
- ARC frames are near-unique (counters / moving overlays), so a TABULAR
  ``(state-signature, action)`` transition table never has data for the current
  frame and never fires (R10, R27b measured planned=0). A small CONV model that
  predicts the per-cell CHANGE generalises across unseen frames, so planning can
  actually fire (R32 measured fwd_planned > 0).
- It stays SMALL (predicts a change-mask + per-cell colour, not full RGB) so it
  converges within the per-game online action budget where a bigger policy net
  did not (R24).

The model is trained online by :class:`admorphiq.online_rl_agent.OnlineRLAgent`
from its own stored ``(frame, action, next_frame)`` transitions, and rolled out
by the goal-directed planner (:mod:`admorphiq.planner.goal`).
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# ── Action / grid constants ──────────────────────────────────────────────────
NUM_SIMPLE_ACTIONS = 5           # ACTION1..5 (combined-logit slots 0..4)
COORD_OFFSET = NUM_SIMPLE_ACTIONS  # combined index >= this is an ACTION6 click
GRID = 64
N_COLORS = 16
ACTION_PLANES = 2                # plane 0 = action-type, plane 1 = click spike


def _action_planes(action_idx: int, device: torch.device) -> torch.Tensor:
    """Encode a combined-logit action index as ``(2, 64, 64)`` spatial planes.

    Plane 0 broadcasts a normalised action-type scalar over the whole grid so the
    conv model knows WHICH action was taken. Plane 1 is a coordinate spike: a
    single 1.0 at the ACTION6 click cell (``coord = idx - COORD_OFFSET``,
    ``(y, x) = divmod(coord, 64)``) and all-zero for simple actions — so the model
    can localise WHERE a click landed.
    """
    planes = torch.zeros(ACTION_PLANES, GRID, GRID, device=device)
    if action_idx < COORD_OFFSET:
        # simple action: type scalar in (0, 1], no coordinate spike
        planes[0] = float(action_idx + 1) / float(NUM_SIMPLE_ACTIONS + 1)
    else:
        planes[0] = 1.0  # ACTION6 marker
        coord = int(action_idx) - COORD_OFFSET
        coord = max(0, min(GRID * GRID - 1, coord))
        y, x = divmod(coord, GRID)
        planes[1, y, x] = 1.0
    return planes


class ForwardModel(nn.Module):
    """Conv net predicting the per-cell CHANGE-MASK + next colour of ``(frame, action)``.

    Input: a 16-channel one-hot frame ``(B, 16, 64, 64)`` concatenated with the
    action broadcast to ``ACTION_PLANES`` spatial planes ``(B, 2, 64, 64)``.
    Two heads: ``change_logits (B, 1, 64, 64)`` (per-cell P(change)) and
    ``colour_logits (B, 16, 64, 64)`` (predicted next colour where it changes).
    Deliberately small so it converges online within the per-game budget.
    """

    def __init__(self, hidden: int = 32) -> None:
        super().__init__()
        in_ch = N_COLORS + ACTION_PLANES
        self.trunk = nn.Sequential(
            nn.Conv2d(in_ch, hidden, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, hidden, 3, padding=1),
            nn.ReLU(inplace=True),
        )
        self.change_head = nn.Conv2d(hidden, 1, 1)
        self.colour_head = nn.Conv2d(hidden, N_COLORS, 1)

    def forward(
        self, frame: torch.Tensor, planes: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        x = torch.cat([frame, planes], dim=1)
        h = self.trunk(x)
        return self.change_head(h), self.colour_head(h)

    @torch.no_grad()
    def predict_next_frame(
        self, frame_int: np.ndarray, action_idx: int
    ) -> tuple[np.ndarray, float]:
        """Predict the next integer frame for ``(frame_int, action_idx)``.

        Returns ``(next_frame_int, confidence)``: cells whose predicted P(change)
        exceeds 0.5 take the argmax predicted colour, others keep their current
        colour. ``confidence`` in [0, 1] is the mean decisiveness of the
        change-mask (``mean(2*|p-0.5|)``) — used by the planner's fallback gate.
        """
        device = next(self.parameters()).device
        cur = torch.as_tensor(frame_int, dtype=torch.long, device=device)
        onehot = F.one_hot(cur.clamp(0, N_COLORS - 1), N_COLORS)
        onehot = onehot.permute(2, 0, 1).float().unsqueeze(0)  # (1,16,64,64)
        planes = _action_planes(int(action_idx), device).unsqueeze(0)
        change_logits, colour_logits = self.forward(onehot, planes)
        p_change = torch.sigmoid(change_logits.squeeze(1).squeeze(0))  # (64,64)
        pred_colour = colour_logits.squeeze(0).argmax(dim=0)           # (64,64)
        changed = p_change > 0.5
        nxt = torch.where(changed, pred_colour, cur)
        conf = float((2.0 * (p_change - 0.5).abs()).mean().item())
        return nxt.cpu().numpy().astype(frame_int.dtype), conf
