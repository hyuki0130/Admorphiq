"""Uniform-random and light-stochastic calibration baselines.

These agents exist purely to CALIBRATE ``scripts/score_efficiency.py`` against
the public ARC-AGI-3 leaderboard, which reports random ≈ 0.18 and
stochastic-sample ≈ 0.25 on the 0–100 % RHAE scale. Running the random baseline
on OUR harness/subset answers whether our subset sits on the same scale as the
public board (random ≈ 0.18) or on a harsher one (random ≈ 0.001). It is a
measurement instrument, NOT a competition agent — no learning, no perception,
no world model.

Harness contract: ``is_done(frames, latest_frame)`` /
``choose_action(frames, latest_frame)`` over the raw arcengine observation,
returning an official ``GameAction`` — identical to :class:`OnlineRLAgent` and
:class:`BCPolicyAgent`. Action plumbing (internal ``GameAction`` →
official ``GameAction`` with ``set_data`` for ACTION6) is reused verbatim from
:meth:`AdmorphiqAdapter._convert_action`, so ACTION6 coordinates round-trip
exactly the way every other agent's do.

Action selection:

* **random** — each step, read ``available_actions`` from the frame and pick
  ONE uniformly at random. If the pick is ACTION6, pick x, y each uniformly in
  ``0..63``. Reproducible via the ``RL_SEED`` env var (same knob the online RL
  agent honours). ``is_done`` returns True on WIN or once a per-game safety cap
  of ``MAX_ACTIONS`` steps is reached.

* **stochastic** — identical selection to *random* with two honest, minimal
  tweaks: (1) a fixed seed OFFSET so it is a different-but-reproducible draw,
  and (2) a light "stochastic sample" — avoid immediately re-issuing the exact
  same action that just produced a no-op (the frame did not change), resampling
  uniformly up to a few times. This is deliberately simple: the RANDOM baseline
  is the load-bearing calibration number; stochastic is a secondary reference
  and is documented as such.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

import numpy as np

# Per-game safety cap. The run loop (scripts/score_efficiency.py) also enforces
# its own --max-actions budget; this is an agent-side belt-and-braces so the
# baseline never spins forever if the runner cap were removed.
MAX_ACTIONS = 50_000

# Seed offset that distinguishes the "stochastic" draw from the "random" one so
# the two baselines are reproducible yet not identical sequences.
_STOCHASTIC_SEED_OFFSET = 10_000

# Times the stochastic agent will resample to avoid repeating a known no-op
# action at the current frame before giving up and taking whatever it drew.
_RESAMPLE_LIMIT = 4


class RandomAgent:
    """Uniformly-random action baseline (optionally with light no-op avoidance).

    Args:
        seed: RNG seed for reproducibility. ``None`` leaves the draw
            non-reproducible.
        avoid_repeat_noop: When True (the "stochastic" variant), resample to
            avoid immediately re-issuing an action that just produced a no-op at
            the current frame. When False (the pure "random" variant), every
            draw is an independent uniform pick.
        max_actions: Per-game safety cap after which :meth:`is_done` returns True.
    """

    def __init__(
        self,
        seed: int | None = None,
        avoid_repeat_noop: bool = False,
        max_actions: int = MAX_ACTIONS,
    ) -> None:
        from .adapter import AdmorphiqAdapter  # heavy import, kept lazy

        self._convert_action = AdmorphiqAdapter._convert_action
        self._rng = random.Random(seed)
        self._avoid_repeat_noop = avoid_repeat_noop
        self._max_actions = max_actions

        self._steps = 0
        # Light no-op memory: the last (frame_hash, action_id, x, y) we issued,
        # and the frame it was issued FROM. Only consulted by the stochastic
        # variant to notice a no-op and avoid re-issuing the same pick.
        self._prev_frame: np.ndarray | None = None
        self._last_pick: tuple[str, int, int, int] | None = None
        self._noop_picks: set[tuple[str, int, int, int]] = set()

    # ── harness contract ─────────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return _state_name(latest_frame) == "WIN" or self._steps >= self._max_actions

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        obs = latest_frame
        state = _state_name(obs)
        if state in ("GAME_OVER", "NOT_PLAYED"):
            self._prev_frame = None
            self._last_pick = None
            self._noop_picks.clear()
            return self._reset_action()
        if not _has_frame(obs):
            return self._reset_action()

        frame = _frame_2d(obs)

        # Stochastic variant: note whether the previous action was a no-op at the
        # frame it was issued from, so we can avoid re-issuing it.
        if self._avoid_repeat_noop and self._last_pick is not None:
            if self._prev_frame is not None and np.array_equal(self._prev_frame, frame):
                self._noop_picks.add(self._last_pick)

        simple_ids, action6_ok = _availability(obs)
        if not simple_ids and not action6_ok:
            return self._reset_action()

        fhash = _frame_hash(frame)
        pick = self._sample(simple_ids, action6_ok, fhash)

        self._prev_frame = frame
        self._last_pick = pick
        self._steps += 1
        return self._pick_to_action(pick)

    # ── selection ─────────────────────────────────────────────────────────────

    def _sample(
        self, simple_ids: list[int], action6_ok: bool, fhash: str
    ) -> tuple[str, int, int, int]:
        """Draw one action, uniformly over the whole available action space.

        Returns a ``(frame_hash, action_id, x, y)`` tuple. For simple actions x
        and y are 0. ACTION6 is treated as a single action in the id-level draw;
        its coordinate is then drawn uniformly in ``0..63`` for both axes, so the
        draw is uniform over {simple actions} ∪ {ACTION6} at the type level (NOT
        uniform over the 4096 coordinate cells — that would swamp the simple
        actions, which is not the "random action" baseline we want to calibrate).
        """
        attempts = _RESAMPLE_LIMIT if self._avoid_repeat_noop else 1
        pick = self._draw(simple_ids, action6_ok, fhash)
        for _ in range(attempts - 1):
            if pick not in self._noop_picks:
                break
            pick = self._draw(simple_ids, action6_ok, fhash)
        return pick

    def _draw(
        self, simple_ids: list[int], action6_ok: bool, fhash: str
    ) -> tuple[str, int, int, int]:
        choices: list[int] = list(simple_ids)
        if action6_ok:
            choices.append(6)
        action_id = self._rng.choice(choices)
        if action_id == 6:
            x = self._rng.randrange(64)
            y = self._rng.randrange(64)
            return (fhash, 6, x, y)
        return (fhash, action_id, 0, 0)

    # ── action plumbing ─────────────────────────────────────────────────────────

    def _pick_to_action(self, pick: tuple[str, int, int, int]) -> Any:
        from .types import ActionType, GameAction

        _fhash, action_id, x, y = pick
        if action_id == 6:
            internal = GameAction.coordinate(x, y)
        else:
            internal = GameAction.simple(ActionType(action_id))
        return self._convert_action(internal)

    def _reset_action(self) -> Any:
        from .types import GameAction

        return self._convert_action(GameAction.reset())


# ── observation helpers (tolerant of arcengine obs shape; mirror online_rl) ──


def _state_name(obs: Any) -> str:
    state = getattr(obs, "state", None)
    return getattr(state, "name", str(state) if state is not None else "")


def _has_frame(obs: Any) -> bool:
    fr = getattr(obs, "frame", None)
    return fr is not None and len(fr) > 0


def _frame_2d(obs: Any) -> np.ndarray:
    """Return a (64, 64) int array from the observation's first frame layer."""
    fr = getattr(obs, "frame", None)
    arr = np.asarray(fr)
    if arr.ndim >= 3:
        arr = arr[0]
    return arr.astype(np.int64)


def _frame_hash(frame: np.ndarray) -> str:
    return hashlib.md5(np.ascontiguousarray(frame).tobytes()).hexdigest()[:16]


def _availability(obs: Any) -> tuple[list[int], bool]:
    """Return (list of available simple action ids 1..5, action6_available)."""
    simple_ids: list[int] = []
    action6_ok = False
    for a in getattr(obs, "available_actions", []) or []:
        aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
        if aid is None:
            continue
        if 1 <= aid <= 5:
            simple_ids.append(aid)
        elif aid == 6:
            action6_ok = True
    return simple_ids, action6_ok
