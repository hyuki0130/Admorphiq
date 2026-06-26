"""Train a frame->action behavior-cloning policy on gold solution traces.

The proven ARC-AGI-3 lever (DriesSmit CNN action predictor): supervise
``PerceptionModel`` on the GOLD (efficient level-clear) transitions across all
games, then deploy it as ``BCPolicyAgent``.

Targets are the single combined-logit class (see ``admorphiq.bc_agent``):
simple action -> ``a-1``; ACTION6 -> ``5 + y*64 + x``. A single cross-entropy
trains the action portion on simple-action demos and the coordinate portion on
ACTION6 demos. Samples are weighted by demonstration EFFICIENCY (shorter clears
relative to the human baseline get more weight) because the competition metric
is efficiency-squared.

Usage:
  uv run python scripts/train_policy.py [--epochs 30] [--batch 64] [--lr 1e-3] \\
      [--val-frac 0.1] [--device mps] [--out models/bc_policy.pt]
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from admorphiq.bc_agent import (  # noqa: E402
    COORD_OFFSET,
    NUM_SIMPLE_ACTIONS,
    TOTAL_LOGITS,
    build_bc_targets,
    onehot_batch,
)
from admorphiq.perception import PerceptionModel  # noqa: E402

TRACES_DIR = Path(__file__).resolve().parent.parent / "data" / "traces"


def load_gold() -> dict:
    """Load all GOLD transitions across games into flat arrays.

    Returns a dict with: frames (G,64,64 uint8), actions (G,), coords_x/y (G,),
    targets (G,), weights (G,), is_action6 (G,), and per-game gold counts.
    """
    frames_l, actions_l, cx_l, cy_l, weights_l, game_l = [], [], [], [], [], []
    per_game: dict[str, int] = {}

    for f in sorted(glob.glob(str(TRACES_DIR / "*.npz"))):
        d = np.load(f, allow_pickle=False)
        gold = d["is_gold"]
        if not gold.any():
            continue
        meta = json.loads(str(d["meta"]))
        title = meta.get("title", Path(f).stem.upper())
        baseline = meta.get("baseline_actions") or []

        actions = d["actions"][gold].astype(np.int64)
        cx = d["coords_x"][gold].astype(np.int64)
        cy = d["coords_y"][gold].astype(np.int64)
        frames = d["frames"][gold].astype(np.uint8)
        level_idx = d["level_index"][gold].astype(np.int64)
        episode = d["episode_id"][gold].astype(np.int64)

        # Per gold block = (episode, level cleared). Block length = agent actions
        # used for that clear. weight ~ (human / agent)^2 => efficient (short)
        # clears weigh more; metric is efficiency-squared. We additionally scale
        # by the 1-indexed level depth because the competition metric weights
        # level k by k: without this, the efficiency term alone over-rewards the
        # abundant, easy level-0 demos and starves the rarer deep-level demos,
        # which measurably collapsed multi-level clears (AR25/M0R0 lost level 2).
        w = np.ones(actions.shape[0], dtype=np.float64)
        for ep in np.unique(episode):
            for lvl in np.unique(level_idx[episode == ep]):
                sel = (episode == ep) & (level_idx == lvl)
                block_len = int(sel.sum())
                human = baseline[lvl] if 0 <= lvl < len(baseline) else block_len
                eff = human / max(block_len, 1)
                # Gentle depth bias: full (level+1) weighting protects deep nav
                # levels but starves the abundant level-0 ACTION6 demos and
                # collapses click games (CD82/LF52). sqrt keeps a deep-level
                # nudge while preserving coordinate-head learning.
                depth = float(np.sqrt(lvl + 1))
                w[sel] = float(np.clip(eff * eff, 0.25, 4.0) * depth)

        frames_l.append(frames)
        actions_l.append(actions)
        cx_l.append(cx)
        cy_l.append(cy)
        weights_l.append(w)
        game_l.append(np.array([title] * actions.shape[0]))
        per_game[title] = int(actions.shape[0])

    frames = np.concatenate(frames_l)
    actions = np.concatenate(actions_l)
    cx = np.concatenate(cx_l)
    cy = np.concatenate(cy_l)
    weights = np.concatenate(weights_l)
    weights = weights / weights.mean()  # normalise mean weight to 1.0
    targets = build_bc_targets(actions, cx, cy)

    return {
        "frames": frames,
        "actions": actions,
        "targets": targets,
        "weights": weights.astype(np.float32),
        "is_action6": actions == 6,
        "games": np.concatenate(game_l),
        "per_game": per_game,
    }


def _metrics(model: PerceptionModel, frames: np.ndarray, targets: np.ndarray,
             is_a6: np.ndarray, device: torch.device, batch: int, topk: int = 5) -> dict:
    """Action accuracy over all rows + coord top-1/top-k over ACTION6 rows."""
    model.eval()
    n = frames.shape[0]
    correct = 0
    coord_top1 = 0
    coord_topk = 0
    n_a6 = 0
    with torch.no_grad():
        for s in range(0, n, batch):
            e = min(s + batch, n)
            x = onehot_batch(frames[s:e]).to(device)
            logits = model(x)  # (b, 4101)
            pred = torch.argmax(logits, dim=1).cpu().numpy()
            tgt = targets[s:e]
            correct += int((pred == tgt).sum())

            a6 = is_a6[s:e]
            if a6.any():
                coord_logits = logits[:, NUM_SIMPLE_ACTIONS:]  # (b, 4096)
                coord_tgt = tgt[a6] - COORD_OFFSET
                cl = coord_logits[torch.from_numpy(a6).to(device)]
                ck = torch.topk(cl, k=topk, dim=1).indices.cpu().numpy()  # (m, k)
                coord_top1 += int((ck[:, 0] == coord_tgt).sum())
                coord_topk += int((ck == coord_tgt[:, None]).any(axis=1).sum())
                n_a6 += int(a6.sum())
    return {
        "action_acc": correct / max(n, 1),
        "coord_top1": coord_top1 / max(n_a6, 1),
        "coord_topk": coord_topk / max(n_a6, 1),
        "n": n,
        "n_action6": n_a6,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--val-frac", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--device", default=None, help="cpu / mps / cuda (default: auto)")
    p.add_argument("--out", default="models/bc_policy.pt")
    p.add_argument("--topk", type=int, default=5)
    args = p.parse_args()

    if args.device:
        device = torch.device(args.device)
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    data = load_gold()
    n = data["frames"].shape[0]
    print(f"Loaded {n} gold transitions across {len(data['per_game'])} games "
          f"({int(data['is_action6'].sum())} ACTION6).", flush=True)
    print(f"  per-game gold: {data['per_game']}", flush=True)

    # Shuffle + train/val split.
    perm = np.random.permutation(n)
    n_val = max(1, int(n * args.val_frac))
    val_idx, tr_idx = perm[:n_val], perm[n_val:]

    fr_tr, fr_val = data["frames"][tr_idx], data["frames"][val_idx]
    tg_tr, tg_val = data["targets"][tr_idx], data["targets"][val_idx]
    w_tr = data["weights"][tr_idx]
    a6_tr, a6_val = data["is_action6"][tr_idx], data["is_action6"][val_idx]

    model = PerceptionModel().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)

    start = time.time()
    n_tr = fr_tr.shape[0]
    for epoch in range(1, args.epochs + 1):
        model.train()
        ep = np.random.permutation(n_tr)
        running = 0.0
        for s in range(0, n_tr, args.batch):
            sel = ep[s:s + args.batch]
            x = onehot_batch(fr_tr[sel]).to(device)
            tgt = torch.from_numpy(tg_tr[sel]).to(device)
            w = torch.from_numpy(w_tr[sel]).to(device)
            logits = model(x)  # (b, 4101)
            loss = (F.cross_entropy(logits, tgt, reduction="none") * w).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            running += float(loss.item()) * len(sel)
        if epoch % 5 == 0 or epoch == args.epochs:
            tr_m = _metrics(model, fr_tr, tg_tr, a6_tr, device, args.batch, args.topk)
            va_m = _metrics(model, fr_val, tg_val, a6_val, device, args.batch, args.topk)
            print(
                f"epoch {epoch:3d}  loss={running / n_tr:.4f}  "
                f"train[act={tr_m['action_acc']:.3f} c1={tr_m['coord_top1']:.3f} "
                f"c{args.topk}={tr_m['coord_topk']:.3f}]  "
                f"val[act={va_m['action_acc']:.3f} c1={va_m['coord_top1']:.3f} "
                f"c{args.topk}={va_m['coord_topk']:.3f}]",
                flush=True,
            )

    elapsed = time.time() - start
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out)

    tr_m = _metrics(model, fr_tr, tg_tr, a6_tr, device, args.batch, args.topk)
    va_m = _metrics(model, fr_val, tg_val, a6_val, device, args.batch, args.topk)
    print(f"\nTrained {args.epochs} epochs in {elapsed:.1f}s on {device}.", flush=True)
    print(f"  TOTAL_LOGITS={TOTAL_LOGITS}", flush=True)
    print(f"  final train: {tr_m}", flush=True)
    print(f"  final val  : {va_m}", flush=True)
    print(f"  saved -> {out}", flush=True)


if __name__ == "__main__":
    main()
