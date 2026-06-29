"""RL fine-tuning of the ARC-AGI-3 BC policy (StochasticGoose #1 recipe).

Warm-starts the proven behavior-cloning ``PerceptionModel`` and continues it with
on-policy reinforcement learning against the real ``arc_agi`` offline env. The BC
policy already clears ~10 games; RL is the StochasticGoose lever that pushes the
*efficiency* of those clears up (the competition metric is ``min(human/agent,1)²``)
and discovers a few more from sparse level-completion reward.

Algorithm — REINFORCE with a baseline (advantage whitening), kept deliberately
simple and robust:

  * Roll the *stochastic* masked policy out in the live env: at each step the
    logits are masked to ``available_actions`` (and the full 4096 coord grid for
    ACTION6), then an action is SAMPLED (not argmax) so RL actually explores.
  * Reward is sparse and matches StochasticGoose's signal:
      +``level_reward``      per level cleared          (the real objective)
      +``change_reward``     per frame-changing action  (tiny shaping)
      −``game_over_penalty`` on GAME_OVER
      −``step_penalty``      per step                   (optional; default 0)
    Discounted returns (γ≈0.99) already reward SHORTER solutions, which is what
    the squared-efficiency metric wants.
  * The update recomputes log-probs over the collected (frame, action) pairs,
    multiplies by whitened returns, and adds two anti-collapse regularizers:
      − an ENTROPY bonus (keep exploring), and
      − a KL anchor to the FROZEN BC reference policy (don't catastrophically
        forget the BC priors that already clear 10 games).

The saved checkpoint is a plain ``PerceptionModel.state_dict()`` — byte-identical
in shape to what ``scripts/train_policy.py`` writes — so ``BCPolicyAgent`` /
``KaggleBCAgent`` load the RL-tuned weights unchanged.

This is OFFLINE RL fine-tuning. (Online test-time training is a separate,
deploy-time mechanism inside ``bc_agent.py`` and is intentionally not done here.)

Usage:
  uv run python scripts/train_rl.py --init models/bc_policy_v6.pt \\
      --out models/bc_policy_v6_rl.pt --max-env-steps 50000 [--games tu93,ft09]
"""

from __future__ import annotations

import argparse
import copy
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from admorphiq.bc_agent import (  # noqa: E402
    COORD_OFFSET,
    GRID,
    NUM_SIMPLE_ACTIONS,
    TOTAL_LOGITS,
    _pick_device,
    frame_to_onehot,
    onehot_batch,
)
from admorphiq.perception import PerceptionModel  # noqa: E402

# Masked logits are filled with a large finite negative (NOT -inf): softmax /
# log_softmax over -inf produces NaN on the MPS backend. exp(-1e9) underflows to
# exactly 0, so masked actions still get probability 0 — without the NaN.
_MASK_FILL = -1e9


# ── reward / return maths (pure, unit-tested) ────────────────────────────────


@dataclass
class RewardConfig:
    """Sparse level-completion reward with light shaping (StochasticGoose)."""

    level_reward: float = 1.0       # +1 per level cleared — the real objective
    change_reward: float = 0.02     # tiny shaping for frame-changing actions
    game_over_penalty: float = 0.5  # −0.5 on GAME_OVER
    step_penalty: float = 0.0       # optional per-step cost (discount already helps)


def compute_step_reward(
    level_delta: int,
    frame_changed: bool,
    is_game_over: bool,
    cfg: RewardConfig,
) -> float:
    """Reward for a single env step.

    Args:
        level_delta: ``levels_completed`` increase this step (clamped at 0 below).
        frame_changed: whether the action changed the frame (no-op detector).
        is_game_over: whether the resulting state is GAME_OVER.
        cfg: reward coefficients.

    Returns:
        Scalar step reward.
    """
    r = cfg.level_reward * max(int(level_delta), 0)
    if frame_changed:
        r += cfg.change_reward
    if is_game_over:
        r -= cfg.game_over_penalty
    r -= cfg.step_penalty
    return float(r)


def compute_returns(rewards: list[float], gamma: float) -> list[float]:
    """Discounted returns-to-go ``G_t = r_t + γ r_{t+1} + γ² r_{t+2} + …``.

    Args:
        rewards: per-step rewards in temporal order.
        gamma: discount factor in [0, 1].

    Returns:
        List of the same length, ``G_t`` at each index.
    """
    returns = [0.0] * len(rewards)
    g = 0.0
    for t in reversed(range(len(rewards))):
        g = float(rewards[t]) + gamma * g
        returns[t] = g
    return returns


# ── action masking / sampling (pure, unit-tested) ────────────────────────────


def build_full_mask(
    simple_mask: np.ndarray,
    action6_ok: bool,
    device: torch.device | None = None,
) -> torch.Tensor:
    """Combined-logit availability mask of length ``TOTAL_LOGITS`` (4101).

    The first 5 entries follow ``simple_mask`` (ACTION1..5); the 4096 coordinate
    entries are all available iff ACTION6 is available (the coord head is free to
    pick any cell), matching ``BCPolicyAgent`` deploy masking.
    """
    mask = torch.zeros(TOTAL_LOGITS, dtype=torch.bool, device=device)
    mask[:NUM_SIMPLE_ACTIONS] = torch.as_tensor(
        np.asarray(simple_mask, dtype=bool), device=device
    )
    if action6_ok:
        mask[NUM_SIMPLE_ACTIONS:] = True
    return mask


def build_full_mask_batch(
    simple_masks: np.ndarray,
    action6_oks: np.ndarray,
    device: torch.device | None = None,
) -> torch.Tensor:
    """Batched :func:`build_full_mask` → bool tensor ``(B, TOTAL_LOGITS)``."""
    sm = torch.as_tensor(np.asarray(simple_masks, dtype=bool), device=device)
    a6 = torch.as_tensor(np.asarray(action6_oks, dtype=bool), device=device)
    b = a6.shape[0]
    mask = torch.zeros(b, TOTAL_LOGITS, dtype=torch.bool, device=device)
    mask[:, :NUM_SIMPLE_ACTIONS] = sm
    mask[a6, NUM_SIMPLE_ACTIONS:] = True
    return mask


def sample_action_index(
    logits: torch.Tensor,
    mask: torch.Tensor,
    generator: torch.Generator | None = None,
) -> int:
    """Sample a combined-logit index from the masked policy distribution.

    Unavailable logits are filled with ``_MASK_FILL`` (probability ~0 after
    softmax underflow), so the sample is guaranteed to be an available action.

    Args:
        logits: ``(TOTAL_LOGITS,)`` raw policy logits.
        mask: ``(TOTAL_LOGITS,)`` bool availability mask.
        generator: optional torch RNG for deterministic tests.

    Returns:
        Sampled index in ``[0, TOTAL_LOGITS)``.
    """
    masked = logits.masked_fill(~mask, _MASK_FILL)
    probs = torch.softmax(masked, dim=-1)
    idx = torch.multinomial(probs, 1, generator=generator)
    return int(idx.item())


def index_to_action_parts(idx: int) -> tuple[int, int | None, int | None]:
    """Map a combined-logit index to ``(action_id, x, y)``.

    Simple actions (idx 0..4) → ``(idx+1, None, None)``; coordinate indices
    (idx 5..4100) → ``(6, x, y)`` with ``coord = idx-5``, ``x = coord%64``,
    ``y = coord//64`` (mirrors ``bc_agent`` / ``train_policy`` decode).
    """
    if idx < NUM_SIMPLE_ACTIONS:
        return idx + 1, None, None
    coord = idx - COORD_OFFSET
    return 6, coord % GRID, coord // GRID


# ── env interaction helpers ──────────────────────────────────────────────────


def _state_name(obs: Any) -> str:
    state = getattr(obs, "state", None)
    return getattr(state, "name", str(state) if state is not None else "")


def _has_frame(obs: Any) -> bool:
    fr = getattr(obs, "frame", None)
    return fr is not None and len(fr) > 0


def _levels(obs: Any) -> int:
    try:
        return int(getattr(obs, "levels_completed", 0))
    except (TypeError, ValueError):
        return 0


def _availability(obs: Any) -> tuple[np.ndarray, bool]:
    """Return (simple-action bool mask length 5, action6_available)."""
    simple_mask = np.zeros(NUM_SIMPLE_ACTIONS, dtype=bool)
    action6_ok = False
    for a in getattr(obs, "available_actions", []) or []:
        aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
        if aid is None:
            continue
        if 1 <= aid <= 5:
            simple_mask[aid - 1] = True
        elif aid == 6:
            action6_ok = True
    return simple_mask, action6_ok


def _env_step(env: Any, idx: int) -> Any:
    """Decode a combined-logit index to a ``GameAction`` and step the env."""
    from arcengine import GameAction

    action_id, x, y = index_to_action_parts(idx)
    if action_id == 6:
        action = GameAction.from_id(6)
        action.set_data({"x": x, "y": y})
        return env.step(action, data={"x": x, "y": y})
    return env.step(GameAction.from_id(action_id))


# A rolled-out transition: (frame uint8 (64,64), chosen idx, simple_mask, a6, reward).
Transition = tuple[np.ndarray, int, np.ndarray, bool, float]


def run_episode(
    env: Any,
    model: PerceptionModel,
    device: torch.device,
    cfg: RewardConfig,
    max_steps: int,
) -> tuple[list[Transition], int]:
    """Roll the stochastic policy out for one episode; return transitions + clears.

    Terminates on WIN, GAME_OVER, exhausted availability, or ``max_steps``.
    """
    from arcengine import GameAction

    obs = env.observation_space
    if obs is None:
        return [], 0
    if _state_name(obs) in ("NOT_PLAYED", "GAME_OVER"):
        obs = env.step(GameAction.RESET)
    if obs is None:
        return [], 0

    transitions: list[Transition] = []
    prev_levels = _levels(obs)
    levels_cleared = 0

    for _ in range(max_steps):
        if obs is None or _state_name(obs) in ("WIN", "GAME_OVER"):
            break
        if not _has_frame(obs):
            obs = env.step(GameAction.RESET)
            continue

        frame = np.asarray(obs.frame[0], dtype=np.uint8)
        simple_mask, a6 = _availability(obs)
        if not simple_mask.any() and not a6:
            break

        full_mask = build_full_mask(simple_mask, a6, device)
        x = frame_to_onehot(frame).unsqueeze(0).to(device)
        with torch.no_grad():
            logits = model(x)[0]
        idx = sample_action_index(logits, full_mask)

        nobs = _env_step(env, idx)
        if nobs is None:
            transitions.append(
                (frame, idx, simple_mask, a6, -cfg.game_over_penalty)
            )
            break

        nstate = _state_name(nobs)
        nlevels = _levels(nobs)
        level_delta = nlevels - prev_levels
        nframe = np.asarray(nobs.frame[0], dtype=np.uint8) if _has_frame(nobs) else None
        frame_changed = nframe is not None and not np.array_equal(nframe, frame)
        reward = compute_step_reward(
            level_delta, frame_changed, nstate == "GAME_OVER", cfg
        )
        transitions.append((frame, idx, simple_mask, a6, reward))
        levels_cleared += max(level_delta, 0)
        prev_levels = nlevels
        obs = nobs

    return transitions, levels_cleared


# ── policy-gradient update ───────────────────────────────────────────────────


def policy_update(
    model: PerceptionModel,
    ref_model: PerceptionModel,
    episodes: list[list[Transition]],
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    *,
    gamma: float,
    minibatch: int,
    ent_coef: float,
    kl_coef: float,
    grad_clip: float,
) -> dict[str, float]:
    """One REINFORCE-with-baseline update over a batch of collected episodes."""
    frames: list[np.ndarray] = []
    idxs: list[int] = []
    simple: list[np.ndarray] = []
    a6: list[bool] = []
    returns: list[float] = []
    for ep in episodes:
        ep_returns = compute_returns([t[4] for t in ep], gamma)
        for (f, i, sm, a, _r), g in zip(ep, ep_returns, strict=True):
            frames.append(f)
            idxs.append(i)
            simple.append(sm)
            a6.append(a)
            returns.append(g)

    n = len(frames)
    if n == 0:
        return {"pg_loss": 0.0, "entropy": 0.0, "kl": 0.0, "n": 0}

    ret_t = torch.tensor(returns, dtype=torch.float32, device=device)
    adv = (ret_t - ret_t.mean()) / (ret_t.std() + 1e-6)  # baseline + whitening
    idx_t = torch.tensor(idxs, dtype=torch.long, device=device)
    masks = build_full_mask_batch(np.stack(simple), np.asarray(a6), device)
    fr_arr = np.stack(frames)

    model.train()
    order = np.random.permutation(n)
    pg_sum = ent_sum = kl_sum = 0.0
    nb = 0
    for s in range(0, n, minibatch):
        sel = order[s:s + minibatch]
        sel_t = torch.from_numpy(sel).to(device)
        x = onehot_batch(fr_arr[sel]).to(device)
        mb_mask = masks[sel_t]

        logits = model(x)
        masked = logits.masked_fill(~mb_mask, _MASK_FILL)
        logp = torch.log_softmax(masked, dim=-1)
        probs = torch.softmax(masked, dim=-1)

        chosen = logp.gather(1, idx_t[sel_t].unsqueeze(1)).squeeze(1)
        pg_loss = -(adv[sel_t] * chosen).mean()

        # Entropy bonus (zero out masked -inf*0 nans via the mask).
        plogp = torch.where(mb_mask, probs * logp, torch.zeros_like(logp))
        entropy = -(plogp.sum(dim=-1)).mean()

        # KL anchor to the frozen BC reference: KL(ref || current).
        with torch.no_grad():
            ref_logits = ref_model(x)
            ref_masked = ref_logits.masked_fill(~mb_mask, _MASK_FILL)
            ref_logp = torch.log_softmax(ref_masked, dim=-1)
            ref_probs = torch.softmax(ref_masked, dim=-1)
        kl_terms = torch.where(
            mb_mask, ref_probs * (ref_logp - logp), torch.zeros_like(logp)
        )
        kl = kl_terms.sum(dim=-1).mean()

        loss = pg_loss - ent_coef * entropy + kl_coef * kl
        optimizer.zero_grad()
        loss.backward()
        if grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()

        pg_sum += float(pg_loss.detach())
        ent_sum += float(entropy.detach())
        kl_sum += float(kl.detach())
        nb += 1

    model.eval()
    return {
        "pg_loss": pg_sum / max(nb, 1),
        "entropy": ent_sum / max(nb, 1),
        "kl": kl_sum / max(nb, 1),
        "n": n,
    }


# ── game selection ───────────────────────────────────────────────────────────


def select_envs(envs: list[Any], games_filter: str | None) -> list[Any]:
    """Filter discovered envs by a comma-separated id/title substring list.

    No filter → every env (all served game/version hashes, the gold games among
    them). Matching mirrors ``score_efficiency.py`` so ``--games tu93,ft09``
    behaves identically across the two tools.
    """
    if not games_filter:
        return list(envs)
    wanted = [w.strip().lower() for w in games_filter.split(",") if w.strip()]
    seen: set[str] = set()
    out: list[Any] = []
    for e in envs:
        hay = f"{e.game_id} {getattr(e, 'title', '') or ''}".lower()
        if any(w in hay for w in wanted) and e.game_id not in seen:
            seen.add(e.game_id)
            out.append(e)
    return out


# ── CLI ──────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--init", default="models/bc_policy_v6.pt",
                   help="BC checkpoint to warm-start from (PerceptionModel state_dict).")
    p.add_argument("--out", default="models/bc_policy_v6_rl.pt",
                   help="Output checkpoint (same format BC uses; loads in BCPolicyAgent).")
    p.add_argument("--games", default=None,
                   help="Comma-separated id/title substrings (e.g. 'tu93,ft09'); "
                        "default: all available games.")
    p.add_argument("--mode", default="offline", choices=["offline", "normal"],
                   help="arc_agi Arcade operation mode (default: offline).")
    p.add_argument("--max-env-steps", type=int, default=50_000,
                   help="Total env steps before stopping (bounded run).")
    p.add_argument("--episode-max-steps", type=int, default=200,
                   help="Per-episode step cap before forcing a reset.")
    p.add_argument("--update-every", type=int, default=8,
                   help="Run a gradient update after this many collected episodes.")
    p.add_argument("--minibatch", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--gamma", type=float, default=0.99)
    p.add_argument("--ent-coef", type=float, default=0.01,
                   help="Entropy bonus coefficient (exploration).")
    p.add_argument("--kl-coef", type=float, default=0.1,
                   help="KL-to-BC-reference coefficient (anti-forgetting anchor).")
    p.add_argument("--grad-clip", type=float, default=1.0)
    p.add_argument("--level-reward", type=float, default=1.0)
    p.add_argument("--change-reward", type=float, default=0.02)
    p.add_argument("--game-over-penalty", type=float, default=0.5)
    p.add_argument("--step-penalty", type=float, default=0.0)
    p.add_argument("--ckpt-every", type=int, default=10_000,
                   help="Save a checkpoint every N env steps.")
    p.add_argument("--device", default=None, help="cpu / mps / cuda (default: auto).")
    p.add_argument("--seed", type=int, default=0)
    return p


def main() -> None:
    args = _build_parser().parse_args()
    device = _pick_device(args.device)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    cfg = RewardConfig(
        level_reward=args.level_reward,
        change_reward=args.change_reward,
        game_over_penalty=args.game_over_penalty,
        step_penalty=args.step_penalty,
    )

    # Warm-start the policy from BC; keep a FROZEN copy as the KL anchor.
    model = PerceptionModel().to(device)
    init_path = Path(args.init)
    if not init_path.exists():
        raise FileNotFoundError(f"--init checkpoint not found: {init_path}")
    model.load_state_dict(torch.load(init_path, map_location=device))
    model.eval()
    ref_model = copy.deepcopy(model).to(device)
    ref_model.eval()
    for prm in ref_model.parameters():
        prm.requires_grad_(False)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    from arc_agi import Arcade, OperationMode

    mode = OperationMode.OFFLINE if args.mode == "offline" else OperationMode.NORMAL
    arcade = Arcade(operation_mode=mode)
    envs = select_envs(arcade.get_environments(), args.games)
    if not envs:
        raise SystemExit(f"No envs matched --games={args.games!r}")
    print(f"RL fine-tune from {init_path} on {len(envs)} env(s), device={device}, "
          f"max_env_steps={args.max_env_steps}", flush=True)
    print(f"  games: {[e.game_id for e in envs]}", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    env_steps = 0
    episodes_done = 0
    total_levels = 0
    last_ckpt = 0
    batch: list[list[Transition]] = []
    ret_hist: list[float] = []
    lvl_hist: list[int] = []
    start = time.time()
    gi = 0

    while env_steps < args.max_env_steps:
        env_info = envs[gi % len(envs)]
        gi += 1
        env = arcade.make(env_info.game_id)
        if env is None:
            continue
        steps_left = args.max_env_steps - env_steps
        ep_cap = min(args.episode_max_steps, steps_left)
        transitions, levels = run_episode(env, model, device, cfg, ep_cap)
        if not transitions:
            continue

        env_steps += len(transitions)
        episodes_done += 1
        total_levels += levels
        ep_return = sum(t[4] for t in transitions)
        ret_hist.append(ep_return)
        lvl_hist.append(levels)
        batch.append(transitions)

        if len(batch) >= args.update_every:
            stats = policy_update(
                model, ref_model, batch, optimizer, device,
                gamma=args.gamma, minibatch=args.minibatch,
                ent_coef=args.ent_coef, kl_coef=args.kl_coef,
                grad_clip=args.grad_clip,
            )
            batch = []
            window = ret_hist[-args.update_every:]
            print(
                f"[step {env_steps:>7d}/{args.max_env_steps}] ep={episodes_done} "
                f"ret(mean last {len(window)})={np.mean(window):+.3f} "
                f"levels_total={total_levels} "
                f"pg={stats['pg_loss']:+.4f} ent={stats['entropy']:.3f} "
                f"kl={stats['kl']:.4f} n={stats['n']}",
                flush=True,
            )

        if env_steps - last_ckpt >= args.ckpt_every:
            ckpt = out.with_name(f"{out.stem}_step{env_steps}{out.suffix}")
            torch.save(model.state_dict(), ckpt)
            last_ckpt = env_steps
            print(f"  checkpoint -> {ckpt}", flush=True)

    # Flush any tail batch so the last episodes contribute a gradient step.
    if batch:
        policy_update(
            model, ref_model, batch, optimizer, device,
            gamma=args.gamma, minibatch=args.minibatch,
            ent_coef=args.ent_coef, kl_coef=args.kl_coef,
            grad_clip=args.grad_clip,
        )

    torch.save(model.state_dict(), out)
    elapsed = time.time() - start
    mean_ret = float(np.mean(ret_hist)) if ret_hist else 0.0
    print(
        f"\nDone: {episodes_done} episodes, {env_steps} env steps in {elapsed:.1f}s. "
        f"levels_cleared_total={total_levels} mean_episode_return={mean_ret:+.3f}",
        flush=True,
    )
    print(f"Saved RL-tuned policy -> {out}", flush=True)


if __name__ == "__main__":
    main()
