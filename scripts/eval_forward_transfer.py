"""R35: measure forward-model TRANSFER to held-out (unseen) games.

The decisive R35 experiment. A pretrained ForwardModel (weights from
``pretrain_forward_model.py``) is evaluated on transitions from games it was
NEVER trained on. If the change-mask/colour metrics on the HELD-OUT games are
close to the IN-SAMPLE (training-game) metrics, the model learned game-agnostic
core-knowledge dynamics that GENERALISE — the hypothesis that motivates the
whole forward-model pivot (BC policy had ~0% transfer). A large in-sample vs
held-out GAP means the dynamics are game-specific, like the BC policy.

Metric definitions (all in [0, 1], computed over ALL cells of ALL transitions):
  change_acc  — fraction of cells where predicted P(change)>0.5 matches the true
                changed mask (cur_colour != next_colour). Note most cells never
                change, so this floor is high; read it alongside IoU.
  change_iou  — intersection-over-union of predicted-changed vs truly-changed
                cells (|pred ∩ true| / |pred ∪ true|). The honest change metric:
                unaffected by the huge unchanged background. IoU=1.0 when no cell
                changed and none predicted (a valid "nothing happens" call).
  colour_acc  — among cells that TRULY changed, fraction whose argmax predicted
                colour equals the true next colour. Undefined (reported as 0.0)
                when a split has zero changed cells.

Usage:
  uv run python scripts/eval_forward_transfer.py \\
      --model models/forward_model_pretrained.pt \\
      --heldout-npz 'data/heldout/*.npz' --train-npz 'data/transitions/*.npz'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _forward_data import (  # noqa: E402
    encode_batch,
    iter_minibatches,
    load_npz_files,
    load_transitions,
    pick_device,
)

from admorphiq.world_model.forward_model import ForwardModel  # noqa: E402


@torch.no_grad()
def evaluate(
    model: ForwardModel,
    data: dict[str, np.ndarray],
    device: torch.device,
    batch_size: int = 64,
) -> dict[str, float]:
    """Return ``{n, change_acc, change_iou, colour_acc}`` over all transitions.

    Accumulates cell-level counts across minibatches so the reported metrics are
    exact (not a mean-of-batch-means). Returns zeros with ``n=0`` on empty data.
    """
    n = int(data["actions"].shape[0])
    if n == 0:
        return {"n": 0, "change_acc": 0.0, "change_iou": 0.0, "colour_acc": 0.0}

    frames = data["frames"]
    actions = data["actions"]
    next_frames = data["next_frames"]
    rng = np.random.default_rng(0)

    correct_cells = 0.0
    total_cells = 0.0
    inter = 0.0
    union = 0.0
    colour_correct = 0.0
    changed_cells = 0.0

    model.eval()
    for idx in iter_minibatches(n, batch_size, rng, shuffle=False):
        frame_oh, planes, changed, nxt_colour = encode_batch(
            frames[idx], actions[idx], next_frames[idx], device
        )
        change_logits, colour_logits = model(frame_oh, planes)
        pred_change = (torch.sigmoid(change_logits.squeeze(1)) > 0.5).float()

        correct_cells += (pred_change == changed).sum().item()
        total_cells += changed.numel()
        inter += (pred_change * changed).sum().item()
        union += ((pred_change + changed) > 0).float().sum().item()

        pred_colour = colour_logits.argmax(dim=1)  # (B,64,64)
        colour_hit = ((pred_colour == nxt_colour).float() * changed).sum().item()
        colour_correct += colour_hit
        changed_cells += changed.sum().item()

    change_acc = correct_cells / total_cells if total_cells > 0 else 0.0
    change_iou = inter / union if union > 0 else 1.0
    colour_acc = colour_correct / changed_cells if changed_cells > 0 else 0.0
    return {
        "n": n,
        "change_acc": float(change_acc),
        "change_iou": float(change_iou),
        "colour_acc": float(colour_acc),
    }


def _load_model(path: Path, device: torch.device) -> ForwardModel:
    model = ForwardModel().to(device)
    state = torch.load(path, map_location=device)
    model.load_state_dict(state)
    model.eval()
    return model


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Evaluate forward-model transfer to held-out games."
    )
    p.add_argument(
        "--model",
        required=True,
        help="Pretrained ForwardModel weights (.pt).",
    )
    p.add_argument(
        "--heldout-npz",
        required=True,
        help="Glob (quote it) of HELD-OUT (unseen) game transitions.",
    )
    p.add_argument(
        "--train-npz",
        default=None,
        help="Optional glob of TRAIN-set transitions for the in-sample "
        "comparison (the transfer gap).",
    )
    p.add_argument("--device", default=None, help="torch device (default: auto).")
    p.add_argument(
        "--out",
        default="scripts/forward_transfer.json",
        help="Output JSON path (default: scripts/forward_transfer.json).",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()
    device = pick_device(args.device)
    model = _load_model(Path(args.model), device)

    heldout_paths = load_npz_files(args.heldout_npz)
    heldout = load_transitions(heldout_paths)
    heldout_metrics = evaluate(model, heldout, device)

    result: dict[str, object] = {
        "model": args.model,
        "heldout": heldout_metrics,
        "heldout_files": [p.name for p in heldout_paths],
    }

    print("HELD-OUT (unseen games):", flush=True)
    print(
        f"  n={heldout_metrics['n']}  change_acc={heldout_metrics['change_acc']:.4f}  "
        f"change_iou={heldout_metrics['change_iou']:.4f}  "
        f"colour_acc={heldout_metrics['colour_acc']:.4f}",
        flush=True,
    )

    if args.train_npz:
        train_paths = load_npz_files(args.train_npz)
        train = load_transitions(train_paths)
        train_metrics = evaluate(model, train, device)
        result["train"] = train_metrics
        result["train_files"] = [p.name for p in train_paths]
        print("IN-SAMPLE (training games):", flush=True)
        print(
            f"  n={train_metrics['n']}  change_acc={train_metrics['change_acc']:.4f}  "
            f"change_iou={train_metrics['change_iou']:.4f}  "
            f"colour_acc={train_metrics['colour_acc']:.4f}",
            flush=True,
        )
        # Transfer ratio on the honest change metric (IoU). >~0.5 => the dynamics
        # generalise; near 0 => game-specific memorisation like the BC policy.
        t_iou = train_metrics["change_iou"]
        ratio = (heldout_metrics["change_iou"] / t_iou) if t_iou > 0 else 0.0
        result["transfer_ratio_iou"] = float(ratio)
        print(
            f"\nTRANSFER RATIO (held-out IoU / in-sample IoU) = {ratio:.2%}",
            flush=True,
        )
        print(
            "VERDICT: "
            + (
                "FORWARD MODEL TRANSFERS (dynamics generalise across games)"
                if ratio >= 0.5
                else "LOW TRANSFER (dynamics look game-specific)"
            ),
            flush=True,
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Output written to: {out_path}", flush=True)


if __name__ == "__main__":
    main()
