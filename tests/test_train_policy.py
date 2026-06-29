"""Tests for the v5 coverage levers in ``scripts/train_policy.py``:
per-game balanced sampling and DAgger correction assembly.

These pin the two mechanisms that recover GOLD-but-uncleared games for the BC
policy, so a regression in either is caught before a multi-hour retrain.
"""

import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from train_policy import (  # noqa: E402
    assemble_dagger_corrections,
    compute_game_balance_weights,
)


def test_compute_game_balance_weights_equalises_mass():
    """Purpose: the per-game balance multiplier must give every game equal total
    loss mass while preserving the relative within-game efficiency weights.

    Expected feedback: PASS proves a big-gold game and a tiny-gold game end up
    with identical summed mass after the multiplier (so the abundant game no
    longer drowns the rare one), and that within a game the 2:1 efficiency ratio
    of two rows is untouched. FAIL means balanced sampling is not actually
    balancing — the v5 coverage lever would be inert.
    """
    games = np.array(["BIG"] * 8 + ["TINY"] * 2)
    weights = np.array([1.0] * 8 + [2.0, 1.0])  # TINY rows carry a 2:1 efficiency ratio

    mult = compute_game_balance_weights(games, weights)
    final = weights * mult

    big_mass = float(final[games == "BIG"].sum())
    tiny_mass = float(final[games == "TINY"].sum())
    assert np.isclose(big_mass, tiny_mass), (big_mass, tiny_mass)
    # Within-game relative weighting preserved: the TINY 2.0-row stays 2x its peer.
    tiny = final[games == "TINY"]
    assert np.isclose(tiny[0] / tiny[1], 2.0)


def test_compute_game_balance_weights_empty():
    """Purpose: the balancer must be a no-op safe on an empty input.

    Expected feedback: PASS proves no divide-by-zero / shape error on empty
    arrays (defensive contract for the trainer's edge paths). FAIL signals a
    crash risk if a game block is ever empty.
    """
    out = compute_game_balance_weights(np.array([]), np.array([]))
    assert out.shape == (0,)


class _ConstModel(torch.nn.Module):
    """Stub policy that always argmaxes class 0 (ignores the input frame)."""

    def forward(self, x, available_actions=None):  # noqa: D401, ANN001
        b = x.shape[0]
        logits = torch.zeros(b, 4101)
        logits[:, 0] = 1.0  # argmax is always class 0
        return logits


def test_assemble_dagger_corrections_selects_wrong_target_rows():
    """Purpose: DAgger correction assembly must return exactly the gold states in
    the target games where the current policy's argmax disagrees with the gold
    target — and must ignore non-target games and already-correct rows.

    Expected feedback: PASS proves the miner keeps target-game rows whose gold
    target != the policy pick (class 0 here) and drops both the correct rows and
    every non-target-game row, so retraining is fed only genuine corrections.
    FAIL means DAgger would either miss divergences or pollute the set with
    already-learned / off-target states.
    """
    # 4 rows: TU93 target 7 (wrong), TU93 target 0 (correct), CD82 target 9
    # (wrong), AR25 target 3 (wrong but NOT a target game -> must be ignored).
    frames = np.zeros((4, 64, 64), dtype=np.uint8)
    data = {
        "frames": frames,
        "targets": np.array([7, 0, 9, 3], dtype=np.int64),
        "games": np.array(["TU93", "TU93", "CD82", "AR25"]),
    }
    model = _ConstModel()
    out = assemble_dagger_corrections(
        model, data, ("TU93", "CD82"), torch.device("cpu"), batch=64
    )

    assert out["n_checked"] == 3            # 2 TU93 + 1 CD82 (AR25 excluded)
    assert out["n_wrong"] == 2              # TU93@7 and CD82@9
    assert sorted(out["targets"].tolist()) == [7, 9]
    assert set(out["games"].tolist()) == {"TU93", "CD82"}
