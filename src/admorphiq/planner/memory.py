"""Game state memory — remembers successful action sequences for replay."""

from __future__ import annotations

from .._types_internal import GameActionRecord


class GameMemory:
    """Remembers action sequences that led to level completion.

    On level clear, the current action sequence is saved. On subsequent levels
    (which may share similar structure), the memory can suggest actions based
    on what worked before at the same step position.
    """

    def __init__(self, max_sequences: int = 50) -> None:
        self.success_sequences: list[list[GameActionRecord]] = []
        self.current_sequence: list[GameActionRecord] = []
        self._max_sequences = max_sequences
        self._step_in_level: int = 0

    def record_action(self, action_idx: int) -> None:
        """Record an action taken in the current level."""
        self.current_sequence.append(GameActionRecord(action_idx=action_idx))
        self._step_in_level += 1

    def on_level_complete(self) -> None:
        """Level completed — save current sequence as a success pattern."""
        if self.current_sequence:
            self.success_sequences.append(self.current_sequence.copy())
            if len(self.success_sequences) > self._max_sequences:
                self.success_sequences.pop(0)
        self.current_sequence.clear()
        self._step_in_level = 0

    def on_level_reset(self) -> None:
        """Level failed or reset — discard current sequence."""
        self.current_sequence.clear()
        self._step_in_level = 0

    @property
    def step_in_level(self) -> int:
        return self._step_in_level

    def suggest_from_memory(self) -> list[int]:
        """Suggest action indices from successful sequences at the current step.

        Returns a list of action indices that worked at this step position
        in previous successful runs. Empty list if no memory applies.
        """
        candidates: list[int] = []
        for seq in self.success_sequences:
            if self._step_in_level < len(seq):
                candidates.append(seq[self._step_in_level].action_idx)
        return candidates

    def clear(self) -> None:
        """Full reset — clear all memory (e.g. new game)."""
        self.success_sequences.clear()
        self.current_sequence.clear()
        self._step_in_level = 0
