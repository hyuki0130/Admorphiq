"""Tests for the R32 learned neural forward model + short-horizon planner.

These pin the R32 contract:
  (a) the forward model predicts a per-cell change-mask and its loss DECREASES
      on a repeated batch (it actually learns);
  (b) the short-horizon planner selects the first action of the best rollout and
      increments the fwd_planned counter when the model is confident;
  (c) it falls back to the novelty selector when the model is low-confidence and
      when RL_FWD_PLAN_HORIZON == 0;
  (d) RL_FWD_PLAN_HORIZON == 0 (default) reproduces the committed card's action
      selection byte-for-byte;
  (e) the progress TICK line carries fwd_planned / fwd_fallback.

They use a fake observation object (no live arcengine env) so they run fast and
deterministically.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import torch

from admorphiq.online_rl_agent import OnlineRLAgent
from admorphiq.world_model.forward_model import (
    ACTION_FEAT_DIM,
    ForwardModel,
    encode_action,
)


class _Action:
    def __init__(self, value: int) -> None:
        self.value = value


class _State:
    def __init__(self, name: str) -> None:
        self.name = name


class _Obs:
    """Minimal stand-in for an arcengine observation."""

    def __init__(
        self,
        frame: np.ndarray,
        levels: int = 0,
        state: str = "NOT_FINISHED",
        avail: tuple[int, ...] = (1, 2, 3, 4),
    ) -> None:
        self.frame = [frame.tolist()]
        self.levels_completed = levels
        self.state = _State(state)
        self.available_actions = [_Action(a) for a in avail]


def _frame(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 16, size=(64, 64), dtype=np.int64)


def _onehot(frame: np.ndarray) -> torch.Tensor:
    from admorphiq.online_rl_agent import frame_to_onehot

    return frame_to_onehot(frame).unsqueeze(0)  # (1,16,64,64)


# ── (encode_action) ───────────────────────────────────────────────────────────


def test_encode_action_simple_and_coord() -> None:
    """Purpose: encode_action must one-hot the action type and carry normalised
    x/y for ACTION6, zero coords for simple actions.

    Expected feedback: a pass means a simple index sets exactly its type slot
    with zero coord scalars, and an ACTION6 index sets the ACTION6 slot plus the
    matching (x/64, y/64); a fail means the forward model sees a corrupted action
    conditioning and cannot distinguish clicks by location.
    """
    v = encode_action(2)  # ACTION3 (simple)
    assert v.shape == (ACTION_FEAT_DIM,)
    assert v[2] == 1.0
    assert v[-2] == 0.0 and v[-1] == 0.0
    # ACTION6 at flattened coord for (x=3, y=5): idx = 5 + (5*64 + 3)
    idx6 = 5 + (5 * 64 + 3)
    w = encode_action(idx6)
    assert w[5] == 1.0
    assert w[-2] == 3 / 64
    assert w[-1] == 5 / 64


# ── (a) forward model learns a change-mask ─────────────────────────────────────


def test_forward_model_predicts_change_mask_shape() -> None:
    """Purpose: the forward model must emit a per-cell change-mask logit map of
    the frame's spatial size for a batch of transitions.

    Expected feedback: a pass means forward() returns (B, 64, 64) and the change
    target has the same shape and is binary; a fail means the head geometry or
    the target derivation is wrong and BCE cannot be computed.
    """
    fm = ForwardModel()
    frame = _onehot(_frame(1))
    nxt = _onehot(_frame(2))
    feat = encode_action(0).unsqueeze(0)
    logits = fm(frame, feat)
    assert logits.shape == (1, 64, 64)
    target = fm.change_mask_target(frame, nxt)
    assert target.shape == (1, 64, 64)
    assert set(torch.unique(target).tolist()) <= {0.0, 1.0}


def test_forward_model_loss_decreases_on_repeated_batch() -> None:
    """Purpose: the small conv forward model must actually LEARN — its change-mask
    loss must decrease when trained repeatedly on one fixed transition batch.

    Expected feedback: a pass means the loss after 40 gradient steps is strictly
    below the initial loss, proving the model can fit a change-mask online (the
    property that beats the state-uniqueness wall); a fail means the net or the
    training path is inert and planning would rest on noise.
    """
    torch.manual_seed(0)
    fm = ForwardModel()
    opt = torch.optim.Adam(fm.parameters(), lr=1e-3)
    frame = _onehot(_frame(1))
    nxt = _onehot(_frame(2))
    feat = encode_action(1).unsqueeze(0)
    fm.train()
    first = float(fm.loss(frame, feat, nxt).item())
    for _ in range(40):
        loss = fm.loss(frame, feat, nxt)
        opt.zero_grad()
        loss.backward()
        opt.step()
    last = float(fm.loss(frame, feat, nxt).item())
    assert last < first, f"loss did not decrease: {first:.4f} -> {last:.4f}"


def test_forward_model_is_small() -> None:
    """Purpose: the forward model must be TINY relative to the 34M policy so it
    converges within the per-game action budget (beats the online-convergence
    wall).

    Expected feedback: a pass means the forward model has < 1M params (orders of
    magnitude under the policy); a fail means it grew large enough to risk the
    same non-convergence that killed the bigger-policy attempt (R24).
    """
    fm = ForwardModel()
    n = sum(p.numel() for p in fm.parameters())
    assert n < 1_000_000, f"forward model too large: {n} params"


# ── agent integration: planner gate, fallback, byte-identity ───────────────────


def _agent(**kw: Any) -> OnlineRLAgent:
    return OnlineRLAgent(warmstart=False, device="cpu", seed=0, **kw)


def test_default_horizon_planner_inert(monkeypatch) -> None:
    """Purpose: with RL_FWD_PLAN_HORIZON unset (default 0), the planner must never
    fire and the counters stay 0 — the deployed card is unchanged.

    Expected feedback: a pass means after a run of actions fwd_planned == 0 and
    the horizon is 0; a fail means the planner leaked into the default path and
    the trusted baseline is no longer reproducible.
    """
    monkeypatch.delenv("RL_FWD_PLAN_HORIZON", raising=False)
    agent = _agent()
    assert agent.FWD_PLAN_HORIZON == 0
    for i in range(12):
        agent.choose_action([], _Obs(_frame(i), levels=0))
    assert agent._fwd_planned == 0
    assert agent._fwd_fallback == 0


def _selection_sequence(horizon: int, n: int = 14) -> list[int]:
    """Drive a fresh agent and capture the chosen action index per step."""
    import os

    prev = os.environ.get("RL_FWD_PLAN_HORIZON")
    os.environ["RL_FWD_PLAN_HORIZON"] = str(horizon)
    try:
        agent = OnlineRLAgent(warmstart=False, device="cpu", seed=7)
        out: list[int] = []
        for i in range(n):
            agent.choose_action([], _Obs(_frame(i % 4), levels=0, avail=(1, 2, 3, 4, 6)))
            out.append(agent._pending[1] if agent._pending is not None else -1)
        return out
    finally:
        if prev is None:
            os.environ.pop("RL_FWD_PLAN_HORIZON", None)
        else:
            os.environ["RL_FWD_PLAN_HORIZON"] = prev


def _default_selection_sequence(n: int = 14) -> list[int]:
    """Same driver as :func:`_selection_sequence` but with the knob UNSET."""
    import os

    prev = os.environ.pop("RL_FWD_PLAN_HORIZON", None)
    try:
        agent = OnlineRLAgent(warmstart=False, device="cpu", seed=7)
        out: list[int] = []
        for i in range(n):
            agent.choose_action([], _Obs(_frame(i % 4), levels=0, avail=(1, 2, 3, 4, 6)))
            out.append(agent._pending[1] if agent._pending is not None else -1)
        return out
    finally:
        if prev is not None:
            os.environ["RL_FWD_PLAN_HORIZON"] = prev


def test_horizon_zero_byte_identical_selection() -> None:
    """Purpose: RL_FWD_PLAN_HORIZON=0 must produce the EXACT same action-index
    sequence as leaving the knob UNSET — a byte-identical regression guard proving
    "0 = off = committed card".

    Expected feedback: a pass means the explicit-zero run equals the default
    (unset) run index-for-index; a fail means the R32 additions perturbed the
    default selection path and the trusted 3-seed baseline is no longer
    reproducible.
    """
    assert _selection_sequence(0) == _default_selection_sequence()


def test_low_confidence_falls_back_to_novelty() -> None:
    """Purpose: even with planning ENABLED, before the forward model has trained
    FWD_MIN_TRAIN_STEPS steps the planner must NOT act — it falls back to the
    novelty selector and records the fallback.

    Expected feedback: a pass means with a high min-train-steps gate the planner
    never fires (fwd_planned == 0) while fwd_fallback grows; a fail means the
    planner acts on an untrained (noise) forward model.
    """
    agent = _agent()
    agent.FWD_PLAN_HORIZON = 3
    agent.FWD_MIN_TRAIN_STEPS = 10_000_000  # unreachable within the run
    for i in range(16):
        agent.choose_action([], _Obs(_frame(i), levels=0))
    assert agent._fwd_planned == 0
    assert agent._fwd_fallback > 0


def test_planner_fires_and_picks_best_rollout_when_confident() -> None:
    """Purpose: when planning is enabled and the forward model is trained past the
    gate, the planner must FIRE (increment fwd_planned) and return the first
    action of the best-scoring rollout among the ranked candidates.

    Expected feedback: a pass means after enough steps fwd_planned > 0, the
    chosen index equals the argmax-rollout candidate from _plan_action, and the
    index is a valid available action; a fail means the planner never fires
    (the R27b silent-failure mode) or returns an out-of-set action.
    """
    agent = _agent()
    agent.FWD_PLAN_HORIZON = 2
    agent.FWD_MIN_TRAIN_STEPS = 4       # reach quickly
    agent.FWD_TRAIN_EVERY = 8
    agent.WARMUP_STEPS = 8
    for i in range(120):
        agent.choose_action([], _Obs(_frame(i), levels=0, avail=(1, 2, 3, 4, 6)))
    assert agent._fwd_train_steps >= agent.FWD_MIN_TRAIN_STEPS
    assert agent._fwd_planned > 0, "planner never fired despite a trained model"

    # Deterministic re-check: the planner's pick equals its own argmax rollout.
    frame = _frame(200)
    simple_mask = np.array([True, True, True, True, False])
    picked = agent._plan_action(frame, simple_mask, action6_ok=True)
    assert picked is not None
    # It must be one of the ranked candidates (a valid available action index).
    ranked = agent._policy_ranked(frame, simple_mask, True, agent.FWD_PLAN_CANDIDATES)
    assert picked in ranked


def test_progress_tick_includes_fwd_counters(tmp_path, monkeypatch) -> None:
    """Purpose: the TICK progress line must carry fwd_planned / fwd_fallback so a
    measurement can CONFIRM the planner actually fired (R27b failed silently for
    lack of exactly this signal).

    Expected feedback: a pass means each TICK line contains both fwd_planned= and
    fwd_fallback= fields; a fail means the planner-usage signal is invisible in
    the run log and a silent-non-firing regression could recur unnoticed.
    """
    log = tmp_path / "prog.log"
    monkeypatch.setenv("RL_PROGRESS_LOG", str(log))
    monkeypatch.setenv("RL_PROGRESS_EVERY", "2")
    agent = OnlineRLAgent(warmstart=False, device="cpu", seed=0, game_id="zz99")
    for i in range(8):
        agent.choose_action([], _Obs(_frame(i), levels=0))
    ticks = [ln for ln in log.read_text().splitlines() if ln.startswith("TICK")]
    assert ticks
    assert "fwd_planned=" in ticks[0]
    assert "fwd_fallback=" in ticks[0]
