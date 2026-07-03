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
   few gradient steps off-policy from the buffer. The training target DIRECTS
   exploration via COUNT-BASED NOVELTY: a state-changing transition's target is
   ``1/sqrt(visit_count)`` of the resulting state (rarely-seen → ~1.0, often-seen
   → low, floored at ``NOVELTY_FLOOR``), a no-op gets 0.0, and a transition on
   the path to a level clear gets the maximum target (the last ``CREDIT_WINDOW``
   transitions before a ``+1`` reward are credit-trained directly). This makes
   the greedy policy seek the FRONTIER of unexplored states — the lever that
   lets the agent reach a sparse, distant reward within the action budget.
   (The earlier flat ``0.5 * changed`` target gave every move the same value and
   so no direction: the agent wandered the whole budget without reaching the
   reward.) The buffer is RESET between levels (a new level = new state space).

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

Measurement (R2c) — the agent is stochastic, so single-run clear/miss is
variance, not signal. Pass a fixed ``seed`` (or ``RL_SEED`` env via
``scripts/score_efficiency.py``) for a reproducible run; judge changes by the
K-seed CLEAR-RATE from ``scripts/online_rl_clearrate.sh``, never one run.

TRUSTWORTHY BASELINE (2026-06-30, K=3 seeds {1,2,3}, max_actions=1500, warm-start
BC v6). This is the bar all future learner changes are judged against:

    game   win  clear_rate  mean_levels  levels_by_seed
    AR25    8      0/3         0.00        [0, 0, 0]
    DC22    6      0/3         0.00        [0, 0, 0]
    FT09    6      1/3         0.33        [0, 0, 1]
    LP85    8      1/3         0.33        [0, 1, 0]
    M0R0    6      1/3         0.33        [0, 0, 1]
    TU93    9      0/3         0.00        [0, 0, 0]

Aggregate: 3/18 (game, seed) cells cleared >=1 level at the 1500-action budget.
NO learner change produced this — it is the as-committed (a550070) baseline.
"""

from __future__ import annotations

import datetime
import hashlib
import math
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


def _read_capacity() -> tuple[float, bool]:
    """Read the env-gated CNN capacity knob for the per-game policy net.

    Returns ``(width_mult, extra_block)``. Defaults (``1.0``, ``False``)
    reproduce the committed :class:`PerceptionModel` byte-for-byte, so an unset
    environment leaves the online learner unchanged. The knob only widens/deepens
    the net when explicitly set:

      * ``RL_CNN_WIDTH`` (alias ``RL_CNN_CAPACITY``) — float channel multiplier
        on the base plan (32,64,128,256). ``2.0`` => 64,128,256,512.
      * ``RL_CNN_EXTRA_BLOCK`` — truthy string appends one extra conv block.

    A malformed / non-positive width falls back to the 1.0 default rather than
    raising, so a typo in a measurement shell degrades to the regression net.
    """
    raw = (
        os.environ.get("RL_CNN_WIDTH")
        or os.environ.get("RL_CNN_CAPACITY")
        or ""
    ).strip()
    width = 1.0
    if raw:
        try:
            parsed = float(raw)
            if parsed > 0.0:
                width = parsed
        except ValueError:
            width = 1.0
    extra = os.environ.get("RL_CNN_EXTRA_BLOCK", "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    return width, extra


def _pick_device(device: str | None) -> torch.device:
    if device is not None:
        return torch.device(device)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _frame_hash(frame: np.ndarray) -> str:
    return hashlib.md5(np.ascontiguousarray(frame).tobytes()).hexdigest()[:16]


def _onehot_key(onehot_bool: np.ndarray) -> str:
    """Stable hash of a (16, 64, 64) bool one-hot frame, for visit counting.

    The same byte layout must be produced whether the array originates from
    :func:`frame_to_onehot` at store time or from a ``next_frames > 0.5`` mask
    recovered from the replay buffer at train time, so the novelty visit-count
    table can be keyed identically in both places.
    """
    return hashlib.md5(
        np.ascontiguousarray(onehot_bool, dtype=bool).tobytes()
    ).hexdigest()[:16]


def _seed_everything(seed: int) -> None:
    """Seed every RNG the agent draws from so a fixed seed = a reproducible run.

    The agent's stochasticity has three sources: (1) the agent's own
    :class:`random.Random` (action-type / coordinate exploration choices),
    (2) numpy (incidental), and (3) torch — both the per-game model's random
    weight initialisation and ``torch.multinomial`` coordinate sampling. The
    :class:`ExperienceBuffer` draws its replay minibatches from the *global*
    ``random`` module, so the global seed must be set too. Seeding must happen
    BEFORE the model is constructed so warm-start-disabled weight init is itself
    reproducible.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _append_progress(
    path: str,
    game_id: str,
    level: int,
    action_count: int,
    train_updates: int,
) -> None:
    """Append one timestamped TICK line to the per-game online-RL progress log.

    Format (one line, space-separated key=value pairs after the TICK token):
        TICK <iso8601> game=<id> level=<n> actions=<n> train_updates=<n>

    This is the lightweight learning-curve trace re-introduced so a long run can
    be inspected after the fact without re-instrumenting; it is opt-in via the
    ``RL_PROGRESS_LOG`` env var so unit tests and silent runs write nothing.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    line = (
        f"TICK {ts} game={game_id} level={level} "
        f"actions={action_count} train_updates={train_updates}\n"
    )
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)


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
    NOVELTY_FLOOR = 0.1          # min auxiliary target for a productive (state-changing) move
    SHAPE_COEF = 0.1             # potential-based shaping weight (0 => byte-identical prior)
    SHAPE_GAMMA = 0.99           # discount gamma in the shaping potential difference
    SHAPE_C = 1.0                # numerator constant of the novelty potential Phi(s)

    def __init__(
        self,
        warmstart_path: str | Path | None = DEFAULT_WARMSTART,
        device: str | None = None,
        warmstart: bool = True,
        seed: int | None = None,
        game_id: str | None = None,
    ) -> None:
        from .adapter import AdmorphiqAdapter  # heavy import, kept lazy
        from .agent_ensemble import get_frame

        self._get_frame = get_frame
        self._convert_action = AdmorphiqAdapter._convert_action

        self.device = _pick_device(device)
        # Seed every RNG (global random + numpy + torch) BEFORE building the
        # model so the run — including random weight init — is reproducible.
        # A None seed leaves the global RNGs untouched (non-reproducible, fine).
        if seed is not None:
            _seed_everything(seed)
        self._rng = random.Random(seed)

        # Per-game progress logging (opt-in via RL_PROGRESS_LOG). Tick every
        # RL_PROGRESS_EVERY env steps so a long run leaves a learning-curve trace.
        self.game_id = game_id or "unknown"
        self._progress_path = os.environ.get("RL_PROGRESS_LOG", "").strip() or None
        self._progress_every = int(os.environ.get("RL_PROGRESS_EVERY", "200"))
        self._train_updates = 0

        # env overrides for tuning without code edits
        self.EPSILON_START = float(os.environ.get("RL_EPS_START", self.EPSILON_START))
        self.EPSILON_END = float(os.environ.get("RL_EPS_END", self.EPSILON_END))
        self.EPSILON_DECAY_STEPS = int(
            os.environ.get("RL_EPS_DECAY", self.EPSILON_DECAY_STEPS)
        )
        self.TRAIN_EVERY = int(os.environ.get("RL_TRAIN_EVERY", self.TRAIN_EVERY))
        self.TRAIN_STEPS = int(os.environ.get("RL_TRAIN_STEPS", self.TRAIN_STEPS))
        self.LR = float(os.environ.get("RL_LR", self.LR))
        self.SHAPE_COEF = float(os.environ.get("RL_SHAPE_COEF", self.SHAPE_COEF))
        self.SHAPE_GAMMA = float(os.environ.get("RL_SHAPE_GAMMA", self.SHAPE_GAMMA))
        self._log = os.environ.get("RL_LOG", "").strip().lower() in (
            "1", "true", "yes", "on",
        )

        # Build the per-game working model at the env-gated capacity. Default
        # (1.0, False) reproduces the committed 34.3M-param net byte-for-byte;
        # RL_CNN_WIDTH / RL_CNN_EXTRA_BLOCK widen/deepen it (R24 capacity axis).
        # The model is fresh per game (a new agent instance per game), trained
        # online with the same Adam/LR — only the parameter count changes.
        self._cnn_width, self._cnn_extra_block = _read_capacity()
        self.model = PerceptionModel(
            width_mult=self._cnn_width, extra_block=self._cnn_extra_block
        ).to(self.device)
        # Warm-start weights are shaped for the default architecture; a widened /
        # deepened net cannot load them, so warm-start is skipped whenever the
        # capacity knob is active (the bigger net trains from scratch per game).
        self._warm_loaded = False
        _default_capacity = self._cnn_width == 1.0 and not self._cnn_extra_block
        if warmstart and warmstart_path is not None and _default_capacity:
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
        # count-based novelty: next-state one-hot hash -> times visited THIS level.
        # Drives the auxiliary training target so the greedy policy seeks the
        # frontier of unexplored states (directed exploration toward the reward).
        self._visit_counts: dict[str, int] = {}

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
        if self._progress_path and self._total_steps % self._progress_every == 0:
            self._progress_tick()
        return self._index_to_action(idx)

    def _progress_tick(self) -> None:
        """Emit one progress-log line capturing the current learning state."""
        _append_progress(
            self._progress_path,
            self.game_id,
            self._prev_levels or 0,
            self._total_steps,
            self._train_updates,
        )

    # ── transition bookkeeping ─────────────────────────────────────────────────

    def _close_transition(self, next_frame: np.ndarray, leveled_up: bool) -> None:
        """Store the previous (frame, action) -> next_frame transition.

        Reward is sparse: +1 only on a level clear (``leveled_up``); a mere frame
        change earns 0.0 reward (no wiggling reward). The state-change is instead
        tracked as a COUNT-BASED NOVELTY signal: every productive transition's
        next-state one-hot hash is counted in ``self._visit_counts``. The
        auxiliary training target (computed in :meth:`_train_step`) is then high
        for moves that reach rarely-seen states and low for revisits, so the
        greedy policy seeks the frontier of unexplored states — directed
        exploration that finds the sparse reward far faster than the previous
        flat ``0.5 * changed`` target (which gave every move the same value and so
        no direction at all).
        """
        if self._pending is None:
            return
        frame, idx = self._pending
        self._pending = None

        changed = self._prev_frame is None or not np.array_equal(frame, next_frame)
        reward = 1.0 if leveled_up else 0.0

        if leveled_up:
            self._actions_since_progress = 0
        elif not changed:
            # Cheap per-frame no-op memory for cycle avoidance.
            fhash = _frame_hash(frame)
            self._noop_seen[(fhash, idx)] = self._noop_seen.get((fhash, idx), 0) + 1
        else:
            # Productive move: count the visited next-state so novelty decays as
            # the state is re-seen, pushing the policy toward new territory.
            nkey = _onehot_key(frame_to_onehot(next_frame).numpy() > 0.5)
            self._visit_counts[nkey] = self._visit_counts.get(nkey, 0) + 1

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
        # Credit assignment: train the last CREDIT_WINDOW transitions toward the
        # MAX target (1.0) so the policy learns the run-up to the clear, not just
        # the single rewarding step. This trains directly off the recent tail —
        # NOT via re-adding to the buffer, because the buffer dedups on
        # (frame, action) and would silently reject every re-add (the path
        # transitions are already stored with their novelty target). Training
        # the tail directly is what actually reinforces the successful path.
        self._credit_train(self._recent[-self.CREDIT_WINDOW:])
        # New level = new state space / new mechanics: reset learning context.
        self.buffer.clear()
        self._recent.clear()
        self._noop_seen.clear()
        self._visit_counts.clear()
        self._step_in_level = 0
        self._actions_since_progress = 0

    def _credit_train(
        self, tail: list[tuple[np.ndarray, int, np.ndarray]]
    ) -> None:
        """Push the chosen-action logit of each path-to-clear transition toward 1.0.

        Builds one batch from the successful tail and runs a few gradient steps so
        the reward signal propagates to the whole run-up, bypassing the buffer's
        (frame, action) dedup that would otherwise drop these as duplicates.
        """
        if not tail:
            return
        frames = torch.from_numpy(
            np.stack([frame_to_onehot(f).numpy() for f, _, _ in tail]).astype(np.float32)
        ).to(self.device)
        actions = torch.tensor([idx for _, idx, _ in tail], dtype=torch.long, device=self.device)
        target = torch.ones(len(tail), device=self.device)
        self.model.train()
        for _ in range(self.TRAIN_STEPS * 3):
            self._train_updates += 1
            logits = self.model(frames)
            chosen = logits.gather(1, actions.view(-1, 1)).squeeze(1)
            loss = F.binary_cross_entropy_with_logits(chosen, target)
            self.opt.zero_grad()
            loss.backward()
            self.opt.step()
        self.model.eval()

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
        self._visit_counts.clear()
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

    def _novelty_target(self, visit_count: int) -> float:
        """Count-based novelty: ``1/sqrt(n)`` floored at :attr:`NOVELTY_FLOOR`.

        A first visit (n=1) yields 1.0; the value decays as the state is re-seen
        so the policy keeps seeking new states instead of looping in familiar
        ones. The floor keeps any productive (state-changing) move ranked above a
        no-op (target 0), so the agent never prefers wiggling-in-place.
        """
        return max(self.NOVELTY_FLOOR, 1.0 / math.sqrt(max(1, visit_count)))

    def _potential(self, visit_count: int) -> float:
        """Novelty potential ``Phi(s) = SHAPE_C / sqrt(visit_count(s) + 1)``.

        Rarer (less-visited) states have HIGHER potential: an unseen state
        (``visit_count == 0``) yields ``SHAPE_C / 1 = SHAPE_C``; the potential
        decays monotonically as the state is re-seen. This is the state-value
        function used by the potential-based shaping reward
        ``F(s, s') = gamma * Phi(s') - Phi(s)`` (Ng et al. 1999) — a policy-
        INVARIANT densifier of the sparse level-completion signal that cannot,
        in the limit, reward pointless wiggling because the shaping terms
        telescope to zero over any closed cycle.

        ``self._visit_counts`` is keyed by the same ``_onehot_key`` used at
        transition-store time, so a state never recorded as a productive
        next-state has count 0 and thus maximal potential — exactly the frontier
        bias we want.
        """
        return self.SHAPE_C / math.sqrt(visit_count + 1)

    def _train_step(self) -> None:
        """One off-policy gradient step: regress chosen-action logit toward an
        exploration target that DIRECTS the policy toward unexplored states.

        Target per sampled (frame, action):
          * 1.0 if the action earned reward (level-clear) — ``reward`` is the
            sparse buffer reward, +1 only on a level clear;
          * a COUNT-BASED NOVELTY value in ``[NOVELTY_FLOOR, 1.0]`` if it changed
            the frame, looked up from the live visit count of the resulting state
            (rarely-seen → high, often-seen → low);
          * 0.0 if it was a no-op.
        This replaces the previous flat ``0.5 * changed`` target, which gave every
        state-changing move the SAME value and therefore no directional gradient —
        the diagnosed cause of the agent wandering for the whole budget without
        reaching the reward.

        ON TOP of that target, a POTENTIAL-BASED SHAPING reward densifies the
        distant sparse signal so the agent can climb toward a level-completion
        reward it cannot yet reach (the measured R13 L2 plateau):

            F(s, s') = SHAPE_GAMMA * Phi(s') - Phi(s)

        with ``Phi(s) = SHAPE_C / sqrt(visit_count(s) + 1)`` from the SAME
        count-based visit table. It is added as ``SHAPE_COEF * F`` (Ng et al.
        1999): being a potential DIFFERENCE it is provably policy-invariant —
        the shaping terms telescope over any cycle, so it cannot reward
        wiggling-in-place in the limit, yet it fills in the gradient between
        sparse rewards. ``SHAPE_COEF == 0.0`` skips the branch entirely, leaving
        the target BYTE-IDENTICAL to the pre-shaping behaviour. The sparse +1
        level-clear reward remains the dominant term (``SHAPE_COEF`` default
        ~0.1, potentials in ``(0, SHAPE_C]``). The chosen-action logit is pushed
        toward the clamped target via per-sample BCE; the masking semantics of
        the other logits are untouched.
        """
        self._train_updates += 1
        sample = self.buffer.sample_with_next(min(self.TRAIN_BATCH, len(self.buffer)))
        if sample is None:
            # Not enough next_frame entries yet — fall back to reward-only sample
            # (novelty needs next_frame; until then the sparse reward is the target).
            frames, actions, rewards = self.buffer.sample(
                min(self.TRAIN_BATCH, len(self.buffer))
            )
            target = torch.clamp(rewards.to(self.device), 0.0, 1.0)
            frames = frames.to(self.device)
            actions = actions.to(self.device)
        else:
            frames, actions, rewards, next_frames = sample
            # Bool one-hot views on CPU, keyed identically to store-time so the
            # visit-count table (Phi) can be looked up for both s and s'.
            sf_bool = (frames > 0.5).numpy()                            # (B,16,64,64)
            nf_bool = (next_frames > 0.5).numpy()                       # (B,16,64,64)
            frames = frames.to(self.device)
            actions = actions.to(self.device)
            rewards = rewards.to(self.device)
            # Per-sample auxiliary novelty target from the live visit counts.
            changed = (frames != next_frames.to(self.device)).flatten(1).any(dim=1)  # (B,) bool
            nov = torch.zeros(len(actions), device=self.device)
            for i in range(len(actions)):
                if bool(changed[i]):
                    count = self._visit_counts.get(_onehot_key(nf_bool[i]), 1)
                    nov[i] = self._novelty_target(count)
            target = torch.clamp(rewards + nov, 0.0, 1.0)               # (B,)
            # Potential-based reward shaping (Ng et al. 1999), policy-invariant:
            #   F(s, s') = SHAPE_GAMMA * Phi(s') - Phi(s),   Phi = _potential
            # added on top of the sparse+novelty target, scaled by SHAPE_COEF.
            # SHAPE_COEF == 0.0 skips this branch entirely so the target stays
            # BYTE-IDENTICAL to the pre-shaping behaviour.
            if self.SHAPE_COEF != 0.0:
                shape = torch.zeros(len(actions), device=self.device)
                for i in range(len(actions)):
                    phi_s = self._potential(self._visit_counts.get(_onehot_key(sf_bool[i]), 0))
                    phi_sp = self._potential(self._visit_counts.get(_onehot_key(nf_bool[i]), 0))
                    shape[i] = self.SHAPE_GAMMA * phi_sp - phi_s
                target = torch.clamp(target + self.SHAPE_COEF * shape, 0.0, 1.0)

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
