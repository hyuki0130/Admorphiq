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

GRID = 64
GRID_MAX = GRID - 1  # 63 — last valid row/col index


# ── D4 (dihedral) augmentation ───────────────────────────────────────────────
# Each entry pairs a FRAME op on a (N, 64, 64) batch with the matching COORDINATE
# remap (x, y) -> (x', y'). Convention (mirrors bc_agent.frame_to_onehot): array
# axis 0 = y (row), axis 1 = x (col); a click at (x, y) is the cell (row=y, col=x).
# The frame op and coord op are derived together so the pixel that sat at (x, y)
# lands at (x', y') after the transform — this is what `tests/test_d4_remap.py`
# pins. ``m`` is the max index (63). coord fns are pure arithmetic so they
# vectorise over numpy arrays unchanged.
D4_TRANSFORMS: list[tuple] = [
    ("identity", lambda b: b, lambda x, y, m: (x, y)),
    ("rot90", lambda b: np.rot90(b, 1, axes=(1, 2)), lambda x, y, m: (y, m - x)),
    ("rot180", lambda b: np.rot90(b, 2, axes=(1, 2)), lambda x, y, m: (m - x, m - y)),
    ("rot270", lambda b: np.rot90(b, 3, axes=(1, 2)), lambda x, y, m: (m - y, x)),
    ("fliplr", lambda b: b[:, :, ::-1], lambda x, y, m: (m - x, y)),
    ("flipud", lambda b: b[:, ::-1, :], lambda x, y, m: (x, m - y)),
    ("transpose", lambda b: np.transpose(b, (0, 2, 1)), lambda x, y, m: (y, x)),
    (
        "antitranspose",
        lambda b: np.transpose(np.rot90(b, 2, axes=(1, 2)), (0, 2, 1)),
        lambda x, y, m: (m - y, m - x),
    ),
]


def d4_augment_action6(
    frames: np.ndarray,
    coords_x: np.ndarray,
    coords_y: np.ndarray,
    weights: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """8x the ACTION6 rows via the dihedral group, remapping the click coord.

    DESIGN CHOICE (documented per the task): we apply D4 ONLY to ACTION6
    (coordinate) demonstrations, where the geometric meaning of the label is the
    click pixel and transforms deterministically under D4 — this is the key
    lever for the weak coord head (v2 top-1 0.42). We deliberately do NOT
    augment simple ACTION1-5 rows: their directional semantics are game-specific
    and unknown, so rotating/flipping the frame while keeping the same action id
    would teach the policy a WRONG frame->direction mapping. Simple rows pass
    through unchanged (caller concatenates them back).

    Args:
        frames: (M, 64, 64) uint8 ACTION6 frames.
        coords_x / coords_y: (M,) int click coords (0-63).
        weights: (M,) float per-row loss weights (inherited by every symmetry).

    Returns:
        (frames8, cx8, cy8, w8) with 8*M rows (the identity copy is included).
    """
    fr_out, cx_out, cy_out, w_out = [], [], [], []
    for _name, frame_fn, coord_fn in D4_TRANSFORMS:
        nx, ny = coord_fn(coords_x, coords_y, GRID_MAX)
        fr_out.append(np.ascontiguousarray(frame_fn(frames)))
        cx_out.append(np.asarray(nx, dtype=coords_x.dtype))
        cy_out.append(np.asarray(ny, dtype=coords_y.dtype))
        w_out.append(weights)
    return (
        np.concatenate(fr_out),
        np.concatenate(cx_out),
        np.concatenate(cy_out),
        np.concatenate(w_out),
    )


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
        "coords_x": cx,
        "coords_y": cy,
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
    p.add_argument("--weights-out", dest="out", help="alias for --out")
    p.add_argument("--topk", type=int, default=5)
    p.add_argument("--patience", type=int, default=12,
                   help="early-stop after this many evals without val improvement")
    p.add_argument("--no-augment", dest="augment", action="store_false",
                   help="disable D4 ACTION6 augmentation (default: enabled)")
    p.set_defaults(augment=True)
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

    # Shuffle + train/val split on the FLAT rows. Augmentation is applied only
    # to the train split below, so no symmetry of a val frame leaks into train
    # and val metrics stay directly comparable to the v2 baseline.
    perm = np.random.permutation(n)
    n_val = max(1, int(n * args.val_frac))
    val_idx, tr_idx = perm[:n_val], perm[n_val:]

    fr_tr = data["frames"][tr_idx]
    cx_tr, cy_tr = data["coords_x"][tr_idx], data["coords_y"][tr_idx]
    act_tr = data["actions"][tr_idx]
    w_tr = data["weights"][tr_idx]
    a6_tr_mask = act_tr == 6

    if args.augment and a6_tr_mask.any():
        # Simple rows pass through unchanged; ACTION6 rows are 8x'd with coord
        # remap. Simple-row coords are -1 sentinels but build_bc_targets ignores
        # them for non-ACTION6, so they can ride along untouched.
        fr_s = fr_tr[~a6_tr_mask]
        a6_fr, a6_cx, a6_cy, a6_w = d4_augment_action6(
            fr_tr[a6_tr_mask], cx_tr[a6_tr_mask], cy_tr[a6_tr_mask], w_tr[a6_tr_mask]
        )
        n_a6_aug = a6_fr.shape[0]
        fr_tr = np.concatenate([fr_s, a6_fr])
        act_tr = np.concatenate([act_tr[~a6_tr_mask], np.full(n_a6_aug, 6, np.int64)])
        cx_tr = np.concatenate([cx_tr[~a6_tr_mask], a6_cx])
        cy_tr = np.concatenate([cy_tr[~a6_tr_mask], a6_cy])
        w_tr = np.concatenate([w_tr[~a6_tr_mask], a6_w]).astype(np.float32)
        print(f"D4 augmentation: ACTION6 {int(a6_tr_mask.sum())} -> {n_a6_aug} rows "
              f"(8x); train total {n} -> {fr_tr.shape[0]}.", flush=True)

    tg_tr = build_bc_targets(act_tr, cx_tr, cy_tr)
    a6_tr = act_tr == 6
    fr_val = data["frames"][val_idx]
    tg_val = data["targets"][val_idx]
    a6_val = data["is_action6"][val_idx]

    model = PerceptionModel().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    # Cosine LR schedule: high LR early to escape the v2 plateau, annealed to a
    # small value so the sharper minimum is settled into rather than oscillated.
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=args.lr * 0.02)

    start = time.time()
    n_tr = fr_tr.shape[0]
    # Early stopping on the combined val signal (action-acc + coord-top1): both
    # heads matter for a sharp, efficient policy, so neither is allowed to coast.
    best_score = -1.0
    best_state: dict | None = None
    best_epoch = 0
    no_improve = 0
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
        sched.step()
        if epoch % 2 == 0 or epoch == args.epochs:
            # Only val metrics drive early stopping; train metrics over the 8x'd
            # set are expensive and reported once at the end.
            va_m = _metrics(model, fr_val, tg_val, a6_val, device, args.batch, args.topk)
            score = va_m["action_acc"] + va_m["coord_top1"]
            flag = ""
            if score > best_score:
                best_score = score
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
                best_epoch = epoch
                no_improve = 0
                flag = " *best"
            else:
                no_improve += 1
            print(
                f"epoch {epoch:3d}  loss={running / n_tr:.4f}  lr={sched.get_last_lr()[0]:.2e}  "
                f"val[act={va_m['action_acc']:.3f} c1={va_m['coord_top1']:.3f} "
                f"c{args.topk}={va_m['coord_topk']:.3f}]{flag}",
                flush=True,
            )
            if no_improve >= args.patience:
                print(f"early stop: no val improvement for {args.patience} evals "
                      f"(best epoch {best_epoch}).", flush=True)
                break

    elapsed = time.time() - start
    if best_state is not None:
        model.load_state_dict(best_state)  # restore best-val checkpoint
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out)

    tr_m = _metrics(model, fr_tr, tg_tr, a6_tr, device, args.batch, args.topk)
    va_m = _metrics(model, fr_val, tg_val, a6_val, device, args.batch, args.topk)
    print(f"\nTrained up to {epoch} epochs in {elapsed:.1f}s on {device} "
          f"(best val @ epoch {best_epoch}).", flush=True)
    print(f"  TOTAL_LOGITS={TOTAL_LOGITS}", flush=True)
    print("  v2 baseline val: action_acc=0.59  coord_top1=0.42  coord_top5=0.65", flush=True)
    print(f"  final train: {tr_m}", flush=True)
    print(f"  final val  : {va_m}", flush=True)
    print(f"  saved -> {out}", flush=True)


if __name__ == "__main__":
    main()
