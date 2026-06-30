"""Test-time online CNN+RL agent — the StochasticGoose / Dries Smit recipe.

The genuinely GENERAL lever for the ARC-AGI-3 private leaderboard: the agent
learns FRESH inside each unseen game at TEST time, so nothing is memorised from
the public games. It transfers because the learning happens per game, within the
9h / 110-game budget.

Recipe (implemented exactly):

1. **CNN policy** — the existing :class:`PerceptionModel` (4101 logits = 5
   simple-action logits + 4096 ACTION6 coordinate logits, available-action
   masking). REUSED, not reinvented. Optionally warm-started from the BC v6
   weights as an *exploration prior* — the online learning still drives the
   policy, the prior only biases the first probes toward "actions that do
   something".

2. **Off-policy replay** — every ``(frame, action_idx, reward, next_frame)``
   transition is stored in the hash-deduped :class:`ExperienceBuffer`.

3. **Sparse reward** — ``reward = +1`` ONLY when ``levels_completed``
   increments. No frame-change shaping in the *reward* (that rewards wiggling).
   Frame-change is used purely as an *auxiliary learning target* to bias
   exploration toward productive actions, never as reward.

4. **Online retraining** — every ``TRAIN_EVERY`` env steps the policy takes a
   few gradient steps off-policy from the buffer. The training target is a
   "did this (frame, action) make PROGRESS" signal: a transition gets a high
   target if it changed the frame, and the maximum target if it was on the path
   to a level clear (the last ``CREDIT_WINDOW`` transitions before a ``+1``
   reward are credit-assigned). This is a 1-step productivity model the agent
   follows greedily-with-exploration. The buffer is RESET between levels (a new
   level is a new state space / new mechanics).

5. **Exploration** — epsilon-greedy over the productivity model. With prob
   ``epsilon`` take a semi-random available action (hierarchical: action type
   first, then a coordinate via the conv coord head's distribution); otherwise
   take the top productivity-ranked available action, skipping actions known to
   be no-ops at this exact frame (cheap per-frame cycle avoidance).

6. **No game_id / title / internals** — pure frame + available_actions +
   levels_completed. The whole point is per-game online learning.

Harness contract: ``is_done(frames, latest_frame)`` /
``choose_action(frames, latest_frame)`` over the raw arcengine observation,
returning an official ``GameAction`` — identical to ``BCPolicyAgent``. The
train-as-it-plays loop runs inside ``choose_action``.
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from .perception import PerceptionModel
from .utils.buffer import ExperienceBuffer

# ── Layout constants (mirror PerceptionModel / BCPolicyAgent) ─────────────────
NUM_SIMPLE_ACTIONS = 5          # ACTION1..5 -> combined indices 0..4
NUM_COORDS = 4096               # 64 * 64
COORD_OFFSET = NUM_SIMPLE_ACTIONS
TOTAL_LOGITS = NUM_SIMPLE_ACTIONS + NUM_COORDS  # 4101
GRID = 64

# Default exploration prior. The online learning is what matters; the prior only
# biases the first probes. Missing weights => train from scratch (still works).
DEFAULT_WARMSTART = (
    Path(__file__).resolve().parent.parent.parent / "models" / "bc_policy_v6.pt"
)


def frame_to_onehot(frame: np.ndarray) -> torch.Tensor:
    """Convert a (64, 64) colour-index frame to a (16, 64, 64) float one-hot tensor."""
    t = torch.from_numpy(np.asarray(frame).astype(np.int64))   # (64, 64)
    onehot = F.one_hot(t.clamp(0, 15), num_classes=16)          # (64, 64, 16)
    return onehot.permute(2, 0, 1).float()                      # (16, 64, 64)


def _pick_device(device: str | None) -> torch.device:
    if device is not None:
        return torch.device(device)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _frame_hash(frame: np.ndarray) -> str:
    import hashlib

    return hashlib.md5(np.ascontiguousarray(frame).tobytes()).hexdigest()[:16]


class OnlineRLAgent:
    """Test-time online CNN policy that learns per game from sparse level rewards.

    The policy is a per-game working copy (optionally warm-started); on-disk
    weights are never modified, so adaptation never leaks across games.
    """

    # ── exploration / learning knobs (env-overridable for tuning) ─────────────
    EPSILON_START = 0.9          # heavy exploration at the start of each level
    EPSILON_END = 0.15           # floor — always keep some exploration
    EPSILON_DECAY_STEPS = 400    # steps to decay from START to END within a level
    TRAIN_EVERY = 8              # env steps between online gradient passes
    TRAIN_BATCH = 32
    TRAIN_STEPS = 2              # gradient steps per online pass
    LR = 3e-4
    WARMUP_STEPS = 16            # min transitions before the first train pass
    CREDIT_WINDOW = 24           # transitions before a +1 reward that get credit
    GIVE_UP_NO_PROGRESS = 3000   # actions without a clear before bailing the game
    POLICY_TOPK = 12             # candidates considered when picking a productive action
    PER_FRAME_REPEAT_LIMIT = 1   # times a (frame, action) no-op may repeat before skipped

    def __init__(
        self,
        warmstart_path: str | Path | None = DEFAULT_WARMSTART,
        device: str | None = None,
        warmstart: bool = True,
        seed: int | None = None,
    ) -> None:
        from .adapter import AdmorphiqAdapter  # heavy import, kept lazy
        from .agent_ensemble import get_frame

        self._get_frame = get_frame
        self._convert_action = AdmorphiqAdapter._convert_action

        self.device = _pick_device(device)
        self._rng = random.Random(seed)

        # env overrides for tuning without code edits
        self.EPSILON_START = float(os.environ.get("RL_EPS_START", self.EPSILON_START))
        self.EPSILON_END = float(os.environ.get("RL_EPS_END", self.EPSILON_END))
        self.EPSILON_DECAY_STEPS = int(
            os.environ.get("RL_EPS_DECAY", self.EPSILON_DECAY_STEPS)
        )
        self.TRAIN_EVERY = int(os.environ.get("RL_TRAIN_EVERY", self.TRAIN_EVERY))
        self.TRAIN_STEPS = int(os.environ.get("RL_TRAIN_STEPS", self.TRAIN_STEPS))
        self.LR = float(os.environ.get("RL_LR", self.LR))
        self._log = os.environ.get("RL_LOG", "").strip().lower() in (
            "1", "true", "yes", "on",
        )

        # Build the per-game working model. Warm-start is an exploration prior.
        self.model = PerceptionModel().to(self.device)
        self._warm_loaded = False
        if warmstart and warmstart_path is not None:
            path = Path(warmstart_path)
            if path.exists():
                state = torch.load(path, map_location=self.device)
                self.model.load_state_dict(state)
                self._warm_loaded = True
        self.model.eval()
        self.opt = torch.optim.Adam(self.model.parameters(), lr=self.LR)

        self.buffer = ExperienceBuffer(maxlen=200_000)

        # The runner (scripts/score_efficiency.py) reads this flag: on GAME_OVER
        # it issues a RESET and keeps THIS agent instance (and its per-game
        # model + buffer) so online learning continues across death-restarts —
        # the multi-episode-per-game loop the StochasticGoose recipe needs.
        self.restart_on_game_over = True

        # per-game / per-level state
        self._prev_levels: int | None = None
        self._step_in_level = 0
        self._total_steps = 0
        self._actions_since_progress = 0
        self._give_up = False
        self._levels_cleared = 0

        # last (frame, action_idx) awaiting its next_frame to close the transition
        self._pending: tuple[np.ndarray, int] | None = None
        self._prev_frame: np.ndarray | None = None
        # recent transitions in THIS level for sparse-reward credit assignment
        self._recent: list[tuple[np.ndarray, int, np.ndarray]] = []
        # cheap per-frame no-op memory: (frame_hash, action_idx) -> no-op count
        self._noop_seen: dict[tuple[str, int], int] = {}

    # ── harness contract ─────────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return self._give_up or _state_name(latest_frame) == "WIN"

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        obs = latest_frame
        state = _state_name(obs)
        if state == "GAME_OVER":
            # The action that produced the pending transition was destructive
            # (it ended the attempt). Record it as a hard no-op so the
            # productivity model learns to avoid it, then drop the pending link
            # so the post-RESET frame is not mis-attributed. Buffer + model are
            # KEPT — death is a learning signal across restart attempts.
            self._penalise_pending_death()
            self._prev_frame = None
            self._step_in_level = 0
            return self._reset_action()
        if state == "NOT_PLAYED":
            self._reset_level_state()
            return self._reset_action()

        if not _has_frame(obs):
            return self._reset_action()

        frame = self._get_frame(obs)  # (64, 64) int — obs.frame[0]
        levels = _levels_completed(obs)

        # Close the pending transition now that we can see its next_frame and
        # whether a level just cleared. This is the off-policy store + sparse
        # reward + frame-change auxiliary target, all keyed on the real result.
        leveled_up = self._prev_levels is not None and levels > self._prev_levels
        self._close_transition(frame, leveled_up)

        if self._prev_levels is None:
            self._prev_levels = levels
        if leveled_up:
            self._on_level_cleared(levels)

        # Hard cap: bail a hopeless game rather than burning the budget.
        self._actions_since_progress += 1
        if self._actions_since_progress >= self.GIVE_UP_NO_PROGRESS:
            self._give_up = True
            return self._reset_action()

        simple_mask, action6_ok = _availability(obs)
        if not simple_mask.any() and not action6_ok:
            return self._reset_action()

        # Online retraining: a few off-policy gradient steps from the buffer.
        if (
            self._total_steps % self.TRAIN_EVERY == 0
            and len(self.buffer) >= self.WARMUP_STEPS
        ):
            self._train()

        idx = self._select_action_index(frame, simple_mask, action6_ok)

        # Open a new pending transition (frame, action) — closed on the next call.
        self._pending = (frame.astype(np.int64), idx)
        self._prev_frame = frame
        self._step_in_level += 1
        self._total_steps += 1
        return self._index_to_action(idx)

    # ── transition bookkeeping ─────────────────────────────────────────────────

    def _close_transition(self, next_frame: np.ndarray, leveled_up: bool) -> None:
        """Store the previous (frame, action) -> next_frame transition.

        Reward is sparse: +1 only on a level clear (``leveled_up``). The
        frame-change flag is recorded separately as an auxiliary learning target,
        NOT as reward.
        """
        if self._pending is None:
            return
        frame, idx = self._pending
        self._pending = None

        changed = self._prev_frame is None or not np.array_equal(frame, next_frame)
        reward = 1.0 if leveled_up else 0.0

        # Cheap per-frame no-op memory for cycle avoidance.
        if not changed:
            fhash = _frame_hash(frame)
            self._noop_seen[(fhash, idx)] = self._noop_seen.get((fhash, idx), 0) + 1
        elif reward > 0.0:
            self._actions_since_progress = 0

        self.buffer.add(
            (frame_to_onehot(frame).numpy() > 0.5),
            idx,
            reward,
            (frame_to_onehot(next_frame).numpy() > 0.5),
        )
        self._recent.append((frame, idx, next_frame))
        if len(self._recent) > self.CREDIT_WINDOW * 4:
            self._recent = self._recent[-self.CREDIT_WINDOW * 4:]

    def _on_level_cleared(self, levels: int) -> None:
        """Credit-assign the path to the clear, then RESET the buffer for the new level."""
        self._levels_cleared += 1
        self._prev_levels = levels
        # Credit assignment: re-add the last CREDIT_WINDOW transitions with a
        # strong positive reward so the productivity model learns the run-up to
        # the clear, not just the single rewarding step.
        tail = self._recent[-self.CREDIT_WINDOW:]
        for frame, idx, next_frame in tail:
            self.buffer.add(
                (frame_to_onehot(frame).numpy() > 0.5),
                idx,
                1.0,
                (frame_to_onehot(next_frame).numpy() > 0.5),
            )
        # Train hard on the freshly-credited buffer before the reset wipes it.
        if len(self.buffer) >= self.WARMUP_STEPS:
            for _ in range(self.TRAIN_STEPS * 3):
                self._train_step()
        # New level = new state space / new mechanics: reset learning context.
        self.buffer.clear()
        self._recent.clear()
        self._noop_seen.clear()
        self._step_in_level = 0
        self._actions_since_progress = 0

    def _penalise_pending_death(self) -> None:
        """Mark the action that caused GAME_OVER as a hard no-op (avoid).

        Stores the death transition with reward 0 and frame UNCHANGED (so the
        productivity target is 0), and records it in the per-frame no-op memory
        so the greedy pick skips it. Keeps the buffer — death teaches across
        attempts.
        """
        if self._pending is None:
            return
        frame, idx = self._pending
        self._pending = None
        fhash = _frame_hash(frame)
        # Force a strong avoid signal: exceed the repeat limit immediately.
        self._noop_seen[(fhash, idx)] = self.PER_FRAME_REPEAT_LIMIT + 2
        onehot = (frame_to_onehot(frame).numpy() > 0.5)
        self.buffer.add(onehot, idx, 0.0, onehot)  # next==frame => target 0

    def _reset_level_state(self) -> None:
        self.buffer.clear()
        self._recent.clear()
        self._noop_seen.clear()
        self._pending = None
        self._prev_frame = None
        self._step_in_level = 0
        self._actions_since_progress = 0

    # ── action selection ───────────────────────────────────────────────────────

    def _epsilon(self) -> float:
        frac = min(1.0, self._step_in_level / max(1, self.EPSILON_DECAY_STEPS))
        return self.EPSILON_START + (self.EPSILON_END - self.EPSILON_START) * frac

    def _select_action_index(
        self, frame: np.ndarray, simple_mask: np.ndarray, action6_ok: bool
    ) -> int:
        """Pick a combined-logit action index: epsilon-greedy over the productivity model.

        Greedy = top productivity logit among available actions, skipping per-frame
        known no-ops. Explore = semi-random hierarchical pick (action type first,
        then a coordinate sampled from the coord-head distribution for ACTION6).
        """
        fhash = _frame_hash(frame)
        if self._rng.random() < self._epsilon():
            return self._explore_index(frame, simple_mask, action6_ok)

        ranked = self._policy_ranked(frame, simple_mask, action6_ok, self.POLICY_TOPK)
        for cand in ranked:
            if self._noop_seen.get((fhash, cand), 0) > self.PER_FRAME_REPEAT_LIMIT:
                continue
            return cand
        if ranked:
            return ranked[0]
        return self._explore_index(frame, simple_mask, action6_ok)

    def _explore_index(
        self, frame: np.ndarray, simple_mask: np.ndarray, action6_ok: bool
    ) -> int:
        """Hierarchical semi-random pick: choose action type, then coord for ACTION6."""
        choices: list[str] = []
        if simple_mask.any():
            choices.append("simple")
        if action6_ok:
            choices.append("coord")
        if not choices:
            return 0
        kind = self._rng.choice(choices)
        if kind == "simple":
            avail = [i for i in range(NUM_SIMPLE_ACTIONS) if simple_mask[i]]
            return self._rng.choice(avail)
        # ACTION6: sample a coordinate from the coord-head distribution (with
        # temperature) so exploration concentrates where the model expects effect,
        # but stays stochastic. Falls back to uniform if the model is degenerate.
        x = frame_to_onehot(frame).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits = self.model(x)[0, COORD_OFFSET:]  # (4096,)
        probs = torch.softmax(logits / 2.0, dim=0)
        try:
            coord = int(torch.multinomial(probs, 1).item())
        except RuntimeError:
            coord = self._rng.randrange(NUM_COORDS)
        return COORD_OFFSET + coord

    def _policy_ranked(
        self, frame: np.ndarray, simple_mask: np.ndarray, action6_ok: bool, k: int
    ) -> list[int]:
        """Up-to-``k`` available combined-logit indices, best productivity logit first."""
        full_mask = torch.zeros(1, TOTAL_LOGITS, dtype=torch.bool, device=self.device)
        full_mask[0, :NUM_SIMPLE_ACTIONS] = torch.from_numpy(simple_mask).to(self.device)
        if action6_ok:
            full_mask[0, NUM_SIMPLE_ACTIONS:] = True
        x = frame_to_onehot(frame).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits = self.model(x, available_actions=full_mask)[0]
        k = min(k, logits.numel())
        vals, idxs = torch.topk(logits, k)
        return [
            int(i)
            for i, v in zip(idxs.tolist(), vals.tolist(), strict=False)
            if v != float("-inf")
        ]

    # ── online training ─────────────────────────────────────────────────────────

    def _train(self) -> None:
        for _ in range(self.TRAIN_STEPS):
            self._train_step()

    def _train_step(self) -> None:
        """One off-policy gradient step: regress chosen-action logit toward productivity.

        Target per sampled (frame, action): 1.0 if the action earned reward
        (level-clear credit), 0.5 if it merely changed the frame (productive
        probe), 0.0 if it was a no-op. The chosen-action logit is pushed toward
        that target via a per-sample BCE on the gathered logit — biasing the
        greedy pick toward productive / rewarding actions without disturbing the
        masking semantics of the other logits.
        """
        sample = self.buffer.sample_with_next(min(self.TRAIN_BATCH, len(self.buffer)))
        if sample is None:
            # Not enough next_frame entries yet — fall back to reward-only sample.
            frames, actions, rewards = self.buffer.sample(
                min(self.TRAIN_BATCH, len(self.buffer))
            )
            next_frames = None
        else:
            frames, actions, rewards, next_frames = sample

        frames = frames.to(self.device)        # (B, 16, 64, 64) float
        actions = actions.to(self.device)      # (B,)
        rewards = rewards.to(self.device)      # (B,)

        if next_frames is not None:
            next_frames = next_frames.to(self.device)
            changed = (frames != next_frames).flatten(1).any(dim=1).float()  # (B,)
        else:
            changed = torch.zeros_like(rewards)

        # Productivity target: rewarding > productive(frame change) > no-op.
        target = torch.clamp(rewards + 0.5 * changed, 0.0, 1.0)  # (B,)

        self.model.train()
        logits = self.model(frames)            # (B, 4101)
        chosen = logits.gather(1, actions.view(-1, 1)).squeeze(1)  # (B,)
        loss = F.binary_cross_entropy_with_logits(chosen, target)
        self.opt.zero_grad()
        loss.backward()
        self.opt.step()
        self.model.eval()
        if self._log:
            print(
                f"[RL] step={self._total_steps} buf={len(self.buffer)} "
                f"loss={float(loss.detach()):.4f} eps={self._epsilon():.3f} "
                f"cleared={self._levels_cleared}",
                file=sys.stderr,
                flush=True,
            )

    # ── action plumbing ──────────────────────────────────────────────────────────

    def _index_to_action(self, idx: int) -> Any:
        from .types import ActionType, GameAction

        if idx < NUM_SIMPLE_ACTIONS:
            internal = GameAction.simple(ActionType(idx + 1))
        else:
            coord = idx - COORD_OFFSET
            x = coord % GRID
            y = coord // GRID
            internal = GameAction.coordinate(x, y)
        return self._convert_action(internal)

    def _reset_action(self) -> Any:
        from .types import GameAction

        return self._convert_action(GameAction.reset())


# ── observation helpers (tolerant of arcengine obs shape) ────────────────────


def _state_name(obs: Any) -> str:
    state = getattr(obs, "state", None)
    return getattr(state, "name", str(state) if state is not None else "")


def _has_frame(obs: Any) -> bool:
    fr = getattr(obs, "frame", None)
    return fr is not None and len(fr) > 0


def _levels_completed(obs: Any) -> int:
    v = getattr(obs, "levels_completed", None)
    if v is None:
        score = getattr(obs, "score", None)
        if isinstance(score, dict):
            v = score.get("levels_completed")
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _availability(obs: Any) -> tuple[np.ndarray, bool]:
    """Return (simple-action bool mask of length 5, action6_available)."""
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
