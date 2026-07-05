"""R35: pretrain the neural ForwardModel OFFLINE on a TRAIN set of games.

Trains ForwardModel on ``(frame, action, next_frame)`` transitions collected by
``collect_transitions.py``, using the SAME loss the online RL agent uses
(``online_rl_agent._train_forward``): per-cell change-mask BCE + next-colour
cross-entropy masked to the cells that actually changed. Saves the weights to
``models/forward_model_pretrained.pt`` so ``eval_forward_transfer.py`` can test
whether the learned dynamics generalise to HELD-OUT games.

Logged per epoch: mean train loss, change-mask accuracy, and change-mask IoU
(intersection-over-union of predicted vs true changed cells) — the metric that
matters, since most cells never change so raw pixel accuracy is trivially high.

Usage:
  uv run python scripts/pretrain_forward_model.py \\
      --train-npz 'data/transitions/*.npz' --epochs 10 \\
      --out models/forward_model_pretrained.pt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _forward_data import (  # noqa: E402
    F,
    encode_batch,
    iter_minibatches,
    load_npz_files,
    load_transitions,
    pick_device,
)

from admorphiq.world_model.forward_model import ForwardModel  # noqa: E402


def train_step(
    model: ForwardModel,
    opt: torch.optim.Optimizer,
    frames_int: np.ndarray,
    actions: np.ndarray,
    next_frames_int: np.ndarray,
    device: torch.device,
) -> dict[str, float]:
    """Run one supervised optimisation step; return loss + change-mask stats.

    Returns ``{loss, change_acc, change_iou}``. The change/colour losses match
    ``online_rl_agent._train_forward`` exactly so a pretrained model is a valid
    warm-start for the online agent's forward model.
    """
    frame_oh, planes, changed, nxt_colour = encode_batch(
        frames_int, actions, next_frames_int, device
    )
    model.train()
    change_logits, colour_logits = model(frame_oh, planes)
    # Class-imbalance correction: changed cells are ~1-2% of the grid, so plain
    # BCE collapses to the trivial "no change anywhere" predictor (measured:
    # in-sample IoU 0.0000 at change_acc 0.99). Weight positives by the batch's
    # neg/pos ratio (clamped) so the change head actually learns change.
    pos = changed.sum().clamp(min=1.0)
    neg = float(changed.numel()) - changed.sum()
    pos_weight = (neg / pos).clamp(min=1.0, max=200.0)
    change_loss = F.binary_cross_entropy_with_logits(
        change_logits.squeeze(1), changed, pos_weight=pos_weight
    )
    colour_loss = F.cross_entropy(colour_logits, nxt_colour, reduction="none")
    denom = changed.sum().clamp(min=1.0)
    colour_loss = (colour_loss * changed).sum() / denom
    loss = change_loss + colour_loss
    opt.zero_grad()
    loss.backward()
    opt.step()

    with torch.no_grad():
        pred = (torch.sigmoid(change_logits.squeeze(1)) > 0.5).float()
        acc = (pred == changed).float().mean().item()
        inter = (pred * changed).sum().item()
        union = ((pred + changed) > 0).float().sum().item()
        iou = inter / union if union > 0 else 1.0
    model.eval()
    return {"loss": float(loss.item()), "change_acc": acc, "change_iou": iou}


def train(
    data: dict[str, np.ndarray],
    epochs: int,
    batch_size: int,
    lr: float,
    device: torch.device,
    seed: int,
) -> ForwardModel:
    """Train a fresh ForwardModel for ``epochs`` passes over ``data``.

    Prints one summary line per epoch. Returns the trained model (on ``device``).
    """
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = ForwardModel().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)

    frames = data["frames"]
    actions = data["actions"]
    next_frames = data["next_frames"]
    n = int(actions.shape[0])
    if n == 0:
        raise ValueError("No transitions to train on (empty --train-npz).")

    for epoch in range(1, epochs + 1):
        losses, accs, ious = [], [], []
        for idx in iter_minibatches(n, batch_size, rng):
            stats = train_step(
                model, opt, frames[idx], actions[idx], next_frames[idx], device
            )
            losses.append(stats["loss"])
            accs.append(stats["change_acc"])
            ious.append(stats["change_iou"])
        print(
            f"  epoch {epoch:>3}/{epochs}  loss={np.mean(losses):.4f}  "
            f"change_acc={np.mean(accs):.4f}  change_iou={np.mean(ious):.4f}",
            flush=True,
        )
    return model


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Pretrain the ForwardModel on collected transitions."
    )
    p.add_argument(
        "--train-npz",
        required=True,
        help="Glob (quote it) or single .npz path of TRAIN-set transitions.",
    )
    p.add_argument("--epochs", type=int, default=10, help="Epochs (default: 10).")
    p.add_argument(
        "--batch-size", type=int, default=64, help="Minibatch size (default: 64)."
    )
    p.add_argument("--lr", type=float, default=1e-3, help="Adam LR (default: 1e-3).")
    p.add_argument("--seed", type=int, default=0, help="Seed (default: 0).")
    p.add_argument("--device", default=None, help="torch device (default: auto).")
    p.add_argument(
        "--out",
        default="models/forward_model_pretrained.pt",
        help="Output weights path (default: models/forward_model_pretrained.pt).",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()
    paths = load_npz_files(args.train_npz)
    if not paths:
        print(f"No .npz files matched: {args.train_npz}", flush=True)
        return
    data = load_transitions(paths)
    device = pick_device(args.device)
    n = int(data["actions"].shape[0])
    print(
        f"Loaded {n} transitions from {len(paths)} file(s); "
        f"training on {device} for {args.epochs} epoch(s) …",
        flush=True,
    )

    model = train(
        data, args.epochs, args.batch_size, args.lr, device, args.seed
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_path)
    print(f"Saved pretrained forward model -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
