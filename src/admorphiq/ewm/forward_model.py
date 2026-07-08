"""Adapt an LLM-synthesized transition function to the goal-planner interface.

R52 measured that using the world model only to deprioritize no-change actions
is redundant with the graph agent's empirical self-loop learning (score delta
+0.0000). The model's real value is FORWARD PLANNING: rolling it out toward an
inferred goal to choose a move the agent would not reach by novelty alone.

``planner.goal.goal_directed_plan`` expects a forward model exposing
``predict_next_frame(frame_int, action_idx) -> (next_frame_int, confidence)``.
The synthesized function has the different, LLM-facing signature
``predict_next_frame(frame, action_str, xy) -> next_frame`` and no confidence.
This adapter bridges the two: combined-logit ``action_idx`` -> ``(action_str,
xy)`` via the shared decoder, sandboxed execution with a timeout, a no-op
(unchanged frame) on any error, and a scalar confidence equal to the model's
measured train-fit (its only honest self-estimate).

Game-agnostic: frame arrays and action indices only.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from .core import GRID, action_call_args


class EWMForwardModel:
    """Wrap a synthesized ``predict_next_frame`` as a goal-planner forward model.

    Args:
        fn: the synthesized callable ``(frame_list, action_str, xy) -> frame_list``.
        train_fit: the model's measured exact-frame fit over observations; used
            as the per-prediction confidence the planner gates on.
        timeout: per-prediction wall-clock cap (seconds); a slow generation
            degrades to a no-op rather than stalling the game loop.
    """

    def __init__(
        self,
        fn: Callable[..., Any],
        train_fit: float,
        timeout: float = 0.05,
    ) -> None:
        self._fn = fn
        self._confidence = float(train_fit)
        self._timeout = timeout

    def predict_next_frame(
        self, frame_int: np.ndarray, action_idx: int
    ) -> tuple[np.ndarray, float]:
        """Predict the next frame for ``action_idx``; no-op + conf on any failure.

        Coordinates: ``action_idx`` decodes to ``(action_str, xy)`` exactly as
        the synthesis prompt presented them, so the model sees the action shape
        it was trained on. A wrong-shape or erroring generation returns the
        input frame unchanged (a safe, planner-neutral prediction) with the same
        confidence, so a single bad rollout step cannot crash planning.
        """
        # Local import: _run_with_timeout uses SIGALRM on the main thread and a
        # daemon-thread join elsewhere (kept in core so the sandbox stays in one
        # place).
        from .core import _run_with_timeout

        action, xy = action_call_args(int(action_idx))
        try:
            pred = _run_with_timeout(
                self._fn, (frame_int.tolist(), action, xy), self._timeout
            )
            arr = np.asarray(pred, dtype=np.int16)
        except Exception:  # noqa: BLE001 - any failure => no-op prediction
            return frame_int, self._confidence
        if arr.shape != frame_int.shape:
            return frame_int, self._confidence
        return arr, self._confidence


# Re-export so callers need one symbol name regardless of GRID origin.
__all__ = ["EWMForwardModel", "GRID"]
