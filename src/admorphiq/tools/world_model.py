"""Online world-model tool — learn per-game dynamics, plan toward progress.

This is the ONLINE, frame-only world model expressed as a harness ``Tool``. It
learns the game's transition dynamics from the agent's OWN probes — a compact
TABULAR model mapping ``(state_hash, action_key) -> observed effect`` (change
probability, changed-cell count, diff bbox, and the distribution of resulting
state hashes plus the frame-only PROGRESS gained) — and then PLANS greedily over
that learned model toward a progress measure. Because the model is rebuilt fresh
per game (nothing baked in from any specific title), its competence transfers to
unseen games by construction — the R27 lesson that behaviour cloned on public
gold does not transfer.

Design distilled from :mod:`admorphiq.world_model_agent` / ``world_model/`` but
kept intentionally lightweight: no torch, no learned encoder, no per-frame neural
predictor. A statistical online table + a scalar frame-only progress measure runs
comfortably inside the 9h Kaggle budget and is fully unit-testable.

Progress measure (frame-only): the number of foreground objects (non-background
4-connected colour components) in the frame, plus a large bonus for a transition
that raised ``levels_completed``. A transition's VALUE is the progress it gained,
so greedy exploitation drives the frame toward more structure / a level-up while
information-gaining probes fill in the parts of the model still unobserved.

Lifecycle (see :mod:`admorphiq.tools.base`):
    detect   frame-only confidence, HIGH when observed dynamics are deterministic
    reset    drop the learned per-level model
    observe  stage the transition just taken (authoritative "an action happened")
    propose  finalise the last transition, then exploit / probe the learned model
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from admorphiq.tools.base import (
    Step,
    availability,
    base_hash,
    connected_components,
    diff_bbox,
    diff_cells,
    frame_2d,
    has_frame,
    levels_completed,
)

__all__ = ["WorldModelTool", "Effect"]

# A transition that raised levels_completed is the strongest progress signal
# there is; this bonus makes any level-advancing action dominate the greedy pick.
_LEVEL_BONUS = 100.0
# Coarse ACTION6 click lattice (stride 16 → cell centres 8,24,40,56) enumerated
# as candidate click targets so a responsive cell anywhere on a 64×64 board is
# eventually probed while the click action space stays small and tabular.
_CLICK_STRIDE = 16
# A learned (state, action) needs at least this many finalised outcomes before it
# contributes to the determinism estimate (one sample cannot reveal variance).
_MIN_OUTCOMES_FOR_DETERMINISM = 2
# Dominant-outcome fraction of a perfectly deterministic key (used to normalise
# the determinism ratio: 1.0 = always the same next state, 0.5 = a coin flip).
_DETERMINISTIC_FRACTION = 1.0


@dataclass
class Effect:
    """Online statistics for one ``(state_hash, action_key)`` transition.

    ``count`` / ``changed`` are bumped the moment the action is observed;
    ``finalized`` and the effect fields (cells, value, bbox, next-state hashes)
    are filled once the resulting frame arrives on the next tick.
    """

    count: int = 0
    changed: int = 0
    finalized: int = 0
    cells_sum: int = 0
    value_sum: float = 0.0
    last_bbox: tuple[int, int, int, int] | None = None
    next_hashes: Counter = field(default_factory=Counter)

    def change_prob(self) -> float:
        """Laplace-smoothed ``P(frame changes | this action)`` (0.5 if untried)."""
        if self.count == 0:
            return 0.5
        return (self.changed + 1) / (self.count + 2)

    def mean_value(self) -> float | None:
        """Mean progress gained by this transition, or None if not yet finalised."""
        if self.finalized == 0:
            return None
        return self.value_sum / self.finalized

    def dominant_fraction(self) -> float | None:
        """Fraction of finalised outcomes that landed in the single most-common
        next state — 1.0 for a deterministic transition, ->0.5 for a coin flip."""
        total = sum(self.next_hashes.values())
        if total < _MIN_OUTCOMES_FOR_DETERMINISM:
            return None
        return max(self.next_hashes.values()) / total


@dataclass
class _Pending:
    """A transition observed but not yet finalised (awaiting the next frame)."""

    state_hash: str
    key: Any
    before: np.ndarray
    progress_before: int
    levels_before: int


class WorldModelTool:
    """Online, frame-only, tabular world-model tool (see module docstring)."""

    name = "world_model"

    def __init__(self) -> None:
        self._table: dict[tuple[str, Any], Effect] = {}
        self._pending: _Pending | None = None
        self._background: int | None = None
        # levels_completed observed at the most recent frame (the "before" level
        # count for a transition staged by observe between two propose calls).
        self._levels = 0

    # ── Tool protocol ─────────────────────────────────────────────────────────

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Frame-only confidence, HIGH when the learned dynamics are deterministic.

        Two multiplied factors, both in [0, 1]: a STRUCTURE score (is there a
        learnable object layout to model at all?) and a DETERMINISM score (do the
        transitions observed so far map a state+action to a single reliable
        outcome?). With no observations yet only structure is known, so a moderate
        prior is returned; once transitions accumulate, a near-deterministic game
        rises to ~0.7+ while a highly nondeterministic one is pulled well below.
        """
        layer = self._layer(frames, obs)
        struct = self._structure_score(layer)
        det = self._determinism_ratio()
        if det is None:
            # Model still empty — structure-only prior, capped LOW: this tool
            # measured 0/25 as a standalone clearer (r53), so an optimistic
            # empty prior would let it outrank / displace tools that actually
            # clear games. Evidence must be earned before confidence rises.
            return round(0.10 + 0.15 * struct, 4)
        det_component = float(
            np.clip(
                (det - 0.5) / (_DETERMINISTIC_FRACTION - 0.5),
                0.0,
                1.0,
            )
        )
        return round(struct * (0.2 + 0.7 * det_component), 4)

    def reset(self) -> None:
        """Drop the learned model for a new level (dynamics/layout may differ)."""
        self._table.clear()
        self._pending = None
        self._background = None

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Stage the transition just taken and bump its occurrence counters.

        This is the authoritative "an action happened" signal. The resulting
        frame is not available yet (it arrives on the next :meth:`propose`), so the
        effect is finalised there; here we record the occurrence and remember the
        before-frame + its progress so the next tick can credit the gain.
        """
        before = np.asarray(prev)
        key = self._key(action)
        entry = self._entry(base_hash(before), key)
        entry.count += 1
        if changed:
            entry.changed += 1
        self._pending = _Pending(
            state_hash=base_hash(before),
            key=key,
            before=before.copy(),
            progress_before=self._progress(before),
            levels_before=self._levels,
        )

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """Finalise the last transition, then exploit or probe the learned model.

        Greedy exploitation: among the currently available actions, pick the one
        whose learned mean value (progress gained, level-ups dominating) is
        highest AND positive. When no available action is known to make progress
        the model is too sparse here, so an information-gaining probe is proposed:
        an available (state, action) pair not yet observed, else the least-tried
        one. Always returns exactly one step (a propose→observe→propose loop).
        """
        layer = self._layer(frames, obs)
        self._ingest(layer, levels_completed(obs) if has_frame(obs) else self._levels)

        state_hash = base_hash(layer)
        candidates = self._candidates(obs)
        if not candidates:
            return []

        scored: list[tuple[float, Any]] = []
        unobserved: list[Any] = []
        for key in candidates:
            entry = self._table.get((state_hash, key))
            value = entry.mean_value() if entry is not None else None
            if value is None:
                unobserved.append(key)
            else:
                scored.append((value, key))

        # Exploit a learned progress-making action.
        if scored:
            best_value, best_key = max(scored, key=lambda sv: sv[0])
            if best_value > 0:
                return [self._step(best_key)]

        # Too sparse to exploit → information-gaining probe.
        if unobserved:
            return [self._step(unobserved[0])]

        # Everything observed but nothing helps: revisit the least-sampled key to
        # keep refining the model rather than looping the same dead action.
        least = min(
            candidates,
            key=lambda k: self._table[(state_hash, k)].finalized
            if (state_hash, k) in self._table
            else 0,
        )
        return [self._step(least)]

    # ── model update ──────────────────────────────────────────────────────────

    def _ingest(self, after: np.ndarray, levels: int) -> None:
        """Latch background, then finalise the staged transition against ``after``."""
        if self._background is None and after.size:
            vals, counts = np.unique(after, return_counts=True)
            self._background = int(vals[int(counts.argmax())])

        pending = self._pending
        if pending is not None and pending.before.shape == after.shape:
            entry = self._entry(pending.state_hash, pending.key)
            entry.finalized += 1
            entry.cells_sum += diff_cells(pending.before, after)
            bbox = diff_bbox(pending.before, after)
            if bbox is not None:
                entry.last_bbox = bbox
            entry.next_hashes[base_hash(after)] += 1
            gain = self._progress(after) - pending.progress_before
            if levels > pending.levels_before:
                gain += _LEVEL_BONUS
            entry.value_sum += float(gain)
            self._pending = None
        self._levels = levels

    def _entry(self, state_hash: str, key: Any) -> Effect:
        return self._table.setdefault((state_hash, key), Effect())

    # ── frame-only progress + structure ───────────────────────────────────────

    def _progress(self, frame: np.ndarray) -> int:
        """Frame-only progress: count of foreground (non-background) objects."""
        return len(connected_components(frame, self._background))

    def _structure_score(self, layer: np.ndarray) -> float:
        """Is there a learnable object layout? 0 objects → little to model."""
        if layer.size == 0:
            return 0.0
        n = len(connected_components(layer, self._background))
        if n == 0:
            return 0.2
        return float(min(1.0, 0.5 + 0.1 * n))

    def _determinism_ratio(self) -> float | None:
        """Mean dominant-outcome fraction over multiply-observed transitions."""
        fracs = [
            f
            for e in self._table.values()
            if (f := e.dominant_fraction()) is not None
        ]
        if not fracs:
            return None
        return float(np.mean(fracs))

    # ── action helpers ─────────────────────────────────────────────────────────

    def _candidates(self, obs: Any) -> list[Any]:
        """Available action keys: simple ids, then the coarse click lattice."""
        simple, action6 = availability(obs)
        keys: list[Any] = list(simple)
        if action6:
            half = _CLICK_STRIDE // 2
            keys.extend(
                (6, x, y)
                for y in range(half, 64, _CLICK_STRIDE)
                for x in range(half, 64, _CLICK_STRIDE)
            )
        return keys

    @staticmethod
    def _key(action: Step) -> Any:
        """Map a Step to its table key (click keys carry their coordinate)."""
        action_id, coord = action
        if coord is None:
            return int(action_id)
        return (int(action_id), int(coord[0]), int(coord[1]))

    @staticmethod
    def _step(key: Any) -> Step:
        """Inverse of :meth:`_key`: a table key back to an emittable Step."""
        if isinstance(key, tuple):
            _, x, y = key
            return (6, (int(x), int(y)))
        return (int(key), None)

    def _layer(self, frames: list[Any], obs: Any) -> np.ndarray:
        """The current 2D frame from the observation (empty grid if none)."""
        if has_frame(obs):
            return frame_2d(obs)
        return np.zeros((0, 0), dtype=np.int64)
