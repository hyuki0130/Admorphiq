"""Dead-signature tool — skip action classes proven inert at a state (efficiency).

The squared-efficiency (RHAE) metric punishes wasted actions harshly: a level
cleared in 2x the human action count scores 0.25, not 0.5. An action that has
been tried repeatedly from the SAME observable state and never once changed
the frame is very unlikely to matter on the next try either. This tool tracks
that per ``(state_signature, action_class)`` pair and lets the orchestrator
skip proven-inert action classes, saving budget for actions that might matter.

This tool does not itself choose WHAT to do next (:meth:`propose` is an empty
augmentation, per the harness contract) — its value is exposed through
:meth:`is_dead` / :meth:`live_actions`, which the orchestrator (or another
tool's candidate-generation step) consults before spending an action.

Game-agnostic: it only ever sees a caller-supplied state signature (an opaque
hashable, e.g. :func:`admorphiq.tools.base.base_hash` of a frame) and an
action :data:`~admorphiq.tools.base.Step`. No game ids, titles, or internals.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from admorphiq.tools.base import Step, base_hash

__all__ = ["DeadSignatureTool"]

# Coordinate quantization block for ACTION6 clicks: two clicks landing in the
# same block are treated as the same action-class, so "dead" generalizes over
# a small pixel-jitter, not just the exact same (x, y).
_DEFAULT_BLOCK = 8

# An action-class is declared dead once it has been tried this many times at a
# given state signature and NEVER once changed the frame.
_DEFAULT_THRESHOLD = 6


class DeadSignatureTool:
    """Tracks (state_signature, action_class) -> (tried, changed) counters."""

    name = "deadsig"

    def __init__(self, threshold: int = _DEFAULT_THRESHOLD, block: int = _DEFAULT_BLOCK) -> None:
        self.threshold = threshold
        self.block = block
        # key: (state_sig, action_class) -> count
        self._tried: dict[tuple[Any, Any], int] = {}
        self._changed: dict[tuple[Any, Any], int] = {}

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Modest positive confidence: a frame-only efficiency augmentation.

        Useful whenever the action budget is tight (i.e. essentially always
        under the squared-efficiency metric), so it reports a flat, modest
        confidence rather than trying to read game-specific fit from frames.
        """
        return 0.4

    def reset(self) -> None:
        """Drop all per-level dead-signature memory (harness calls on level-up).

        A state signature and its action-class outcomes are level-specific
        (the graph/board resets), so stale counters would misclassify a fresh
        level's untried actions as already dead.
        """
        self._tried.clear()
        self._changed.clear()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Record whether ``action`` changed the frame when taken from ``prev``.

        The state signature is derived from ``prev`` via :func:`base_hash` so
        the caller never has to pass one in for bookkeeping; :meth:`is_dead`
        and :meth:`live_actions` take an explicit signature so they can be
        queried against a state that has not been observed FROM yet (e.g. the
        current live state, before any action from it has been tried).
        """
        key = (base_hash(prev), self._action_class(action))
        self._tried[key] = self._tried.get(key, 0) + 1
        if changed:
            self._changed[key] = self._changed.get(key, 0) + 1

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """Always empty: this tool augments candidate lists, it proposes nothing.

        Its effect is exposed entirely through :meth:`is_dead` /
        :meth:`live_actions`, which the orchestrator or another tool's
        candidate-generation step consults before spending an action.
        """
        return []

    # -- augmentation API (not part of the Tool protocol) --------------------

    def is_dead(self, state_sig: Any, action: Step) -> bool:
        """True once ``action``'s class has tried >= threshold times at
        ``state_sig`` and NEVER once changed the frame.

        Conservative: a single observed change permanently revives the class
        at this signature, so a genuinely useful action is never suppressed.
        """
        key = (state_sig, self._action_class(action))
        return (
            self._tried.get(key, 0) >= self.threshold
            and self._changed.get(key, 0) == 0
        )

    def live_actions(self, state_sig: Any, candidate_actions: list[Step]) -> list[Step]:
        """``candidate_actions`` with proven-dead classes filtered out.

        Never returns an empty list: if every candidate looks dead (e.g. the
        signature bookkeeping is stale or every class happened to self-loop
        during discovery), the original list is returned unfiltered so the
        agent never stalls with zero actions to try.
        """
        live = [a for a in candidate_actions if not self.is_dead(state_sig, a)]
        return live if live else list(candidate_actions)

    # -- internal --------------------------------------------------------

    def _action_class(self, action: Step) -> Any:
        """Coarse action-CLASS key: simple actions by id, clicks by id+block.

        Two clicks in the same ``block``x``block`` region of the frame are
        treated as the same class, so dead-signature memory generalizes over
        near-identical clicks instead of tracking every distinct pixel.
        """
        action_id, coord = action
        if coord is None:
            return ("s", int(action_id))
        x, y = coord
        return ("c", int(action_id), int(x) // self.block, int(y) // self.block)
