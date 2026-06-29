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


# The 10 GOLD-but-uncleared games (v2 baseline clears only 10/20 gold games).
# These are the DAgger targets: the policy has demonstrations for them but its
# argmax diverges from the gold path early and never recovers (classic BC
# compounding error). Titles match ``meta["title"]`` in the traces.
DEFAULT_DAGGER_TITLES: tuple[str, ...] = (
    "BP35", "CD82", "DC22", "G50T", "KA59", "LF52", "R11L", "RE86", "SC25", "TU93",
)


def compute_game_balance_weights(games: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Per-row multiplier that equalises total loss MASS across games.

    Behaviour-cloning on gold drowns games with few gold transitions (CD82 73,
    BP35 15, R11L 3, VC33 3 minimized rows) under the abundant ones (FT09 436,
    RE86 318, SB26 248). Without rebalancing, gradient descent optimises mainly
    the big-gold games and the small-gold games never get a sharp enough argmax
    to follow their own optimal path.

    This returns a per-row multiplier so that, after applying it to ``weights``,
    EVERY game contributes the same summed mass (``sum(weights) / n_games``)
    while the RELATIVE within-game efficiency/depth weights are preserved (every
    row of a game shares one multiplier = ``target / game_weight_sum``). It
    therefore balances ACROSS games but keeps efficiency-weighting WITHIN a game,
    exactly as the v5 coverage lever requires.

    Args:
        games: (N,) array of per-row game titles.
        weights: (N,) existing per-row efficiency/depth weights.

    Returns:
        (N,) float64 multipliers; rows of the same game share one value, and
        ``(weights * multiplier)`` sums to an equal mass for every game.
    """
    games = np.asarray(games)
    weights = np.asarray(weights, dtype=np.float64)
    n = games.shape[0]
    out = np.ones(n, dtype=np.float64)
    uniq = np.unique(games)
    if n == 0 or uniq.shape[0] == 0:
        return out
    target_mass = float(weights.sum()) / float(uniq.shape[0])
    for g in uniq:
        sel = games == g
        gsum = float(weights[sel].sum())
        if gsum > 0:
            out[sel] = target_mass / gsum
    return out


def _policy_argmax(model: PerceptionModel, frames: np.ndarray, device: torch.device,
                   batch: int) -> np.ndarray:
    """Argmax combined-logit class per frame under deploy-style availability.

    Mirrors deployment: every simple action AND the coordinate head are treated
    as available (the agent masks per-state at runtime, but the gold rows do not
    record availability, so the full mask is the honest proxy for "what would
    the policy pick here").
    """
    model.eval()
    preds: list[np.ndarray] = []
    with torch.no_grad():
        for s in range(0, frames.shape[0], batch):
            x = onehot_batch(frames[s:s + batch]).to(device)
            logits = model(x)
            preds.append(torch.argmax(logits, dim=1).cpu().numpy())
    return np.concatenate(preds) if preds else np.empty(0, dtype=np.int64)


def assemble_dagger_corrections(
    model: PerceptionModel,
    data: dict,
    target_titles: tuple[str, ...] | list[str],
    device: torch.device,
    batch: int = 64,
) -> dict:
    """DAgger correction set: gold (state, action) pairs the policy gets WRONG.

    For the target games, query the current policy's argmax at every gold state
    and keep the rows where it disagrees with the gold target. These are exactly
    the states on the optimal path that the policy mishandles — re-injecting them
    (up-weighted) into the next training round teaches the policy to recover onto
    the gold path instead of compounding its early divergence. This is the
    expert-state-distribution form of DAgger; the gold trace IS the expert, so
    the recorded gold action is the correct label at each visited state (the
    "re-run the solver from that state" step is unnecessary because the gold
    alignment already provides it).

    Args:
        model: current policy.
        data: ``load_gold()`` output (must carry ``games``/``frames``/``targets``).
        target_titles: game titles to mine corrections for.
        device / batch: inference config.

    Returns:
        dict with ``frames`` (M,64,64 uint8), ``targets`` (M,), ``games`` (M,),
        ``n_checked`` (gold rows in target games), ``n_wrong`` (M).
    """
    games = data["games"]
    in_target = np.isin(games, np.asarray(list(target_titles)))
    fr = data["frames"][in_target]
    tg = data["targets"][in_target]
    gm = games[in_target]
    if fr.shape[0] == 0:
        return {"frames": fr, "targets": tg, "games": gm, "n_checked": 0, "n_wrong": 0}
    preds = _policy_argmax(model, fr, device, batch)
    wrong = preds != tg
    return {
        "frames": fr[wrong],
        "targets": tg[wrong],
        "games": gm[wrong],
        "n_checked": int(fr.shape[0]),
        "n_wrong": int(wrong.sum()),
    }


def rollout_dagger_corrections(
    weights_path: str | Path,
    data: dict,
    target_titles: tuple[str, ...] | list[str],
    device: torch.device,
    max_steps: int = 400,
) -> dict:
    """On-policy DAgger: roll the policy out per game; label visited gold states.

    Loads the just-trained weights into a pure argmax policy (no ensemble
    fallback, no TTT — the honest on-policy state distribution), rolls it out in
    each target game's live offline env, and whenever a VISITED frame matches a
    gold state, records the gold action as the correction. This captures states
    the policy actually reaches under its own distribution (the DAgger property)
    that the static gold-mismatch miner cannot. Defensive: any arcengine failure
    returns whatever was collected so far so the trainer never hard-fails on the
    env layer.
    """
    try:
        from arc_agi import Arcade, OperationMode
        from arcengine import GameAction
    except Exception as exc:  # pragma: no cover - env optional in unit tests
        print(f"  [dagger-rollout] arcengine unavailable ({exc}); skipping rollout.",
              flush=True)
        return {"frames": np.empty((0, GRID, GRID), np.uint8),
                "targets": np.empty(0, np.int64), "n_visits": 0}

    # Per-title gold {frame_hash -> target_class}.
    import hashlib

    def fhash(fr: np.ndarray) -> str:
        return hashlib.md5(np.ascontiguousarray(fr.astype(np.uint8)).tobytes()).hexdigest()[:16]

    games = data["games"]
    gold_maps: dict[str, dict[str, int]] = {}
    for t in target_titles:
        sel = games == t
        gmap: dict[str, int] = {}
        for fr, tg in zip(data["frames"][sel], data["targets"][sel], strict=False):
            gmap[fhash(fr)] = int(tg)
        if gmap:
            gold_maps[t] = gmap

    model = PerceptionModel().to(device)
    state = torch.load(Path(weights_path), map_location=device)
    model.load_state_dict(state)
    model.eval()

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = arcade.get_environments()
    title_to_id: dict[str, str] = {}
    for e in envs:
        t = (e.title or "").upper()
        if t in gold_maps and t not in title_to_id:
            title_to_id[t] = e.game_id

    out_frames: list[np.ndarray] = []
    out_targets: list[int] = []
    for title, gmap in gold_maps.items():
        gid = title_to_id.get(title)
        if gid is None:
            continue
        env = arcade.make(gid)
        if env is None:
            continue
        obs = env.observation_space
        if obs is None:
            continue
        prev_hash: str | None = None
        stuck = 0
        for _ in range(max_steps):
            if obs is None or getattr(obs.state, "name", str(obs.state)) in ("WIN", "GAME_OVER"):
                break
            frame = np.asarray(obs.frame[0], dtype=np.uint8)
            h = fhash(frame)
            if h in gmap:
                out_frames.append(frame.copy())
                out_targets.append(gmap[h])
            # pure argmax over available actions
            simple = np.zeros(NUM_SIMPLE_ACTIONS, dtype=bool)
            a6 = False
            for a in getattr(obs, "available_actions", []) or []:
                aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
                if aid is None:
                    continue
                if 1 <= aid <= 5:
                    simple[aid - 1] = True
                elif aid == 6:
                    a6 = True
            mask = torch.zeros(1, TOTAL_LOGITS, dtype=torch.bool, device=device)
            mask[0, :NUM_SIMPLE_ACTIONS] = torch.from_numpy(simple).to(device)
            if a6:
                mask[0, NUM_SIMPLE_ACTIONS:] = True
            x = onehot_batch(frame[None]).to(device)
            with torch.no_grad():
                logits = model(x, available_actions=mask)[0]
            idx = int(torch.argmax(logits).item())
            if logits[idx].item() == float("-inf"):
                break
            if idx < NUM_SIMPLE_ACTIONS:
                action = GameAction.from_id(idx + 1)
                obs = env.step(action)
            else:
                coord = idx - COORD_OFFSET
                action = GameAction.from_id(6)
                action.set_data({"x": coord % GRID, "y": coord // GRID})
                obs = env.step(action, data={"x": coord % GRID, "y": coord // GRID})
            stuck = stuck + 1 if h == prev_hash else 0
            prev_hash = h
            if stuck >= 8:
                break
    if not out_frames:
        return {"frames": np.empty((0, GRID, GRID), np.uint8),
                "targets": np.empty(0, np.int64), "n_visits": 0}
    return {
        "frames": np.stack(out_frames).astype(np.uint8),
        "targets": np.asarray(out_targets, dtype=np.int64),
        "n_visits": len(out_frames),
    }


def load_gold(balance_game: bool = True, holdout: set[str] | None = None) -> dict:
    """Load all GOLD transitions across games into flat arrays.

    Args:
        balance_game: when True, multiply each row's efficiency/depth weight by
            :func:`compute_game_balance_weights` so every game contributes equal
            total loss mass (the v5 coverage lever).
        holdout: optional set of case-insensitive game titles/ids to EXCLUDE from
            the loaded gold. Used by the transfer test (train on a subset, score
            the held-out games the policy has never seen) to measure whether BC
            generalizes to unseen games or merely memorizes the training games.

    Returns a dict with: frames (G,64,64 uint8), actions (G,), coords_x/y (G,),
    targets (G,), weights (G,), is_action6 (G,), and per-game gold counts.
    """
    frames_l, actions_l, cx_l, cy_l, weights_l, game_l = [], [], [], [], [], []
    per_game: dict[str, int] = {}
    holdout_lc = {h.lower() for h in holdout} if holdout else set()

    for f in sorted(glob.glob(str(TRACES_DIR / "*.npz"))):
        d = np.load(f, allow_pickle=False)
        gold = d["is_gold"]
        if not gold.any():
            continue
        meta = json.loads(str(d["meta"]))
        title = meta.get("title", Path(f).stem.upper())
        # Transfer test: skip held-out games so they are never seen in training.
        if holdout_lc and (title.lower() in holdout_lc
                           or Path(f).stem.lower() in holdout_lc):
            continue
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
    games_all = np.concatenate(game_l)
    if balance_game:
        # Equalise per-game loss mass so small-gold games are not drowned (v5).
        weights = weights * compute_game_balance_weights(games_all, weights)
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
        "games": games_all,
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


def _augment_train(
    fr_tr: np.ndarray, cx_tr: np.ndarray, cy_tr: np.ndarray, act_tr: np.ndarray,
    w_tr: np.ndarray, augment: bool, balance_aug: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build (frames, targets, is_action6, weights) for a train split.

    Applies D4 ACTION6 augmentation (with the v4 mass-balance fix) when enabled.
    """
    a6_mask = act_tr == 6
    if augment and a6_mask.any():
        fr_s = fr_tr[~a6_mask]
        a6_fr, a6_cx, a6_cy, a6_w = d4_augment_action6(
            fr_tr[a6_mask], cx_tr[a6_mask], cy_tr[a6_mask], w_tr[a6_mask]
        )
        if balance_aug:
            a6_w = a6_w / float(len(D4_TRANSFORMS))
        n_a6_aug = a6_fr.shape[0]
        fr_out = np.concatenate([fr_s, a6_fr])
        act_out = np.concatenate([act_tr[~a6_mask], np.full(n_a6_aug, 6, np.int64)])
        cx_out = np.concatenate([cx_tr[~a6_mask], a6_cx])
        cy_out = np.concatenate([cy_tr[~a6_mask], a6_cy])
        w_out = np.concatenate([w_tr[~a6_mask], a6_w]).astype(np.float32)
    else:
        fr_out, act_out, cx_out, cy_out, w_out = fr_tr, act_tr, cx_tr, cy_tr, w_tr.astype(np.float32)
    tg_out = build_bc_targets(act_out, cx_out, cy_out)
    return fr_out, tg_out, act_out == 6, w_out


def _fit(
    fr_tr: np.ndarray, tg_tr: np.ndarray, w_tr: np.ndarray,
    fr_val: np.ndarray, tg_val: np.ndarray, a6_val: np.ndarray,
    args, device: torch.device, tag: str,
) -> tuple[PerceptionModel, dict, float]:
    """Train a fresh PerceptionModel and return (best-val model, val metrics, score)."""
    model = PerceptionModel().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(
        opt, T_max=args.epochs, eta_min=args.lr * 0.02)
    n_tr = fr_tr.shape[0]
    start = time.time()
    best_score = -1.0
    best_state: dict | None = None
    best_epoch = 0
    no_improve = 0
    epoch = 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        ep = np.random.permutation(n_tr)
        running = 0.0
        for s in range(0, n_tr, args.batch):
            sel = ep[s:s + args.batch]
            x = onehot_batch(fr_tr[sel]).to(device)
            tgt = torch.from_numpy(tg_tr[sel]).to(device)
            w = torch.from_numpy(w_tr[sel]).to(device)
            logits = model(x)
            loss = (F.cross_entropy(logits, tgt, reduction="none") * w).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            running += float(loss.item()) * len(sel)
        sched.step()
        if epoch % 2 == 0 or epoch == args.epochs:
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
                f"[{tag}] epoch {epoch:3d}  loss={running / n_tr:.4f}  "
                f"lr={sched.get_last_lr()[0]:.2e}  val[act={va_m['action_acc']:.3f} "
                f"c1={va_m['coord_top1']:.3f} c{args.topk}={va_m['coord_topk']:.3f}]{flag}",
                flush=True,
            )
            if no_improve >= args.patience:
                print(f"[{tag}] early stop @ epoch {epoch} (best {best_epoch}).", flush=True)
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    va_m = _metrics(model, fr_val, tg_val, a6_val, device, args.batch, args.topk)
    print(f"[{tag}] done {epoch} epochs in {time.time() - start:.1f}s "
          f"(best @ {best_epoch}) val={va_m}", flush=True)
    return model, va_m, best_score


def _checkpoint_path(out: Path, suffix: str) -> Path:
    return out.with_name(f"{out.stem}_{suffix}{out.suffix}")


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
    p.add_argument("--no-balance-aug", dest="balance_aug", action="store_false",
                   help="disable the v4 ACTION6 augmentation weight-balance fix "
                        "(default: enabled — preserves movement-game coverage)")
    p.add_argument("--no-balance-game", dest="balance_game", action="store_false",
                   help="disable the v5 per-game loss-mass balancing (default: enabled)")
    p.add_argument("--dagger-rounds", type=int, default=1,
                   help="DAgger correction rounds after the base fit (default: 1)")
    p.add_argument("--dagger-boost", type=float, default=3.0,
                   help="loss-weight multiplier applied to DAgger correction rows")
    p.add_argument("--no-dagger-rollout", dest="dagger_rollout", action="store_false",
                   help="skip the on-policy env rollout; mine gold mismatches only")
    p.add_argument("--dagger-max-steps", type=int, default=400,
                   help="per-game rollout step cap for on-policy DAgger")
    p.add_argument("--holdout", default=None,
                   help="comma-separated game titles/ids to EXCLUDE from training "
                        "(transfer test: train on the rest, score these unseen).")
    p.set_defaults(augment=True, balance_aug=True, balance_game=True, dagger_rollout=True)
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

    holdout = {h.strip() for h in args.holdout.split(",") if h.strip()} if args.holdout else None
    data = load_gold(balance_game=args.balance_game, holdout=holdout)
    n = data["frames"].shape[0]
    if holdout:
        print(f"HOLDOUT (excluded from training): {sorted(holdout)}", flush=True)
    print(f"Loaded {n} gold transitions across {len(data['per_game'])} games "
          f"({int(data['is_action6'].sum())} ACTION6). balance_game={args.balance_game}",
          flush=True)
    print(f"  per-game gold: {data['per_game']}", flush=True)

    # Fixed gold-only train/val split (val never sees augmentation or DAgger rows,
    # so val metrics stay directly comparable to the v2 baseline across rounds).
    perm = np.random.permutation(n)
    n_val = max(1, int(n * args.val_frac))
    val_idx, tr_idx = perm[:n_val], perm[n_val:]
    fr_val = data["frames"][val_idx]
    tg_val = data["targets"][val_idx]
    a6_val = data["is_action6"][val_idx]

    base_fr = data["frames"][tr_idx]
    base_cx, base_cy = data["coords_x"][tr_idx], data["coords_y"][tr_idx]
    base_act = data["actions"][tr_idx]
    base_w = data["weights"][tr_idx]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # ── base fit (balanced sampling) ──────────────────────────────────────────
    fr_tr, tg_tr, _a6_tr, w_tr = _augment_train(
        base_fr, base_cx, base_cy, base_act, base_w, args.augment, args.balance_aug)
    print(f"base train rows: {fr_tr.shape[0]} (val {n_val})", flush=True)
    model, va_m, best_score = _fit(
        fr_tr, tg_tr, w_tr, fr_val, tg_val, a6_val, args, device, "base")
    base_ckpt = _checkpoint_path(out, "base")
    torch.save(model.state_dict(), base_ckpt)
    print(f"  checkpoint -> {base_ckpt}", flush=True)

    best_model_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    best_overall = best_score
    best_tag = "base"

    # ── DAgger rounds ─────────────────────────────────────────────────────────
    dagger_titles = DEFAULT_DAGGER_TITLES
    acc_fr: list[np.ndarray] = []          # aggregated correction frames
    acc_tg: list[np.ndarray] = []          # aggregated correction targets
    mean_w = float(np.mean(w_tr))
    for r in range(1, args.dagger_rounds + 1):
        # Persist the round's *current* weights so the rollout policy reads them.
        torch.save(model.state_dict(), base_ckpt)
        gm = assemble_dagger_corrections(model, data, dagger_titles, device, args.batch)
        print(f"[dagger {r}] gold-mismatch: {gm['n_wrong']}/{gm['n_checked']} "
              f"states wrong across {len(dagger_titles)} games.", flush=True)
        round_fr = [gm["frames"]]
        round_tg = [gm["targets"]]
        if args.dagger_rollout:
            ro = rollout_dagger_corrections(
                base_ckpt, data, dagger_titles, device, args.dagger_max_steps)
            print(f"[dagger {r}] on-policy rollout: {ro['n_visits']} gold-state visits.",
                  flush=True)
            if ro["n_visits"]:
                round_fr.append(ro["frames"])
                round_tg.append(ro["targets"])
        acc_fr.extend(round_fr)
        acc_tg.extend(round_tg)
        corr_fr = np.concatenate(acc_fr) if acc_fr else np.empty((0, GRID, GRID), np.uint8)
        corr_tg = np.concatenate(acc_tg) if acc_tg else np.empty(0, np.int64)
        if corr_fr.shape[0] == 0:
            print(f"[dagger {r}] no corrections; stopping DAgger.", flush=True)
            break
        # Up-weighted correction rows appended to the augmented base train set.
        corr_w = np.full(corr_fr.shape[0], mean_w * args.dagger_boost, dtype=np.float32)
        fr_d = np.concatenate([fr_tr, corr_fr.astype(np.uint8)])
        tg_d = np.concatenate([tg_tr, corr_tg.astype(np.int64)])
        w_d = np.concatenate([w_tr, corr_w])
        print(f"[dagger {r}] train rows {fr_tr.shape[0]} + {corr_fr.shape[0]} "
              f"corrections (boost x{args.dagger_boost}).", flush=True)
        model, va_m, score = _fit(
            fr_d, tg_d, w_d, fr_val, tg_val, a6_val, args, device, f"dagger{r}")
        ckpt = _checkpoint_path(out, f"d{r}")
        torch.save(model.state_dict(), ckpt)
        print(f"  checkpoint -> {ckpt}", flush=True)
        if score >= best_overall:
            best_overall = score
            best_model_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            best_tag = f"dagger{r}"

    # ── persist best-val model as the v5 artifact ─────────────────────────────
    model.load_state_dict(best_model_state)
    torch.save(model.state_dict(), out)
    final_va = _metrics(model, fr_val, tg_val, a6_val, device, args.batch, args.topk)
    print(f"\nSaved best ({best_tag}, val_score={best_overall:.4f}) -> {out}", flush=True)
    print("  v2 baseline val: action_acc=0.59  coord_top1=0.42  coord_top5=0.65", flush=True)
    print(f"  final val: {final_va}", flush=True)


if __name__ == "__main__":
    main()
