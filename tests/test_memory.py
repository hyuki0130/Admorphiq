"""Tests for admorphiq.planner.memory.GameMemory."""

from admorphiq.planner.memory import GameMemory


class TestRecordAndComplete:
    def test_record_action_and_complete(self):
        mem = GameMemory()
        mem.record_action(0)
        mem.record_action(1)
        mem.record_action(2)
        mem.on_level_complete()
        assert len(mem.success_sequences) == 1
        assert len(mem.success_sequences[0]) == 3
        assert mem.success_sequences[0][0].action_idx == 0

    def test_step_in_level_increments(self):
        mem = GameMemory()
        assert mem.step_in_level == 0
        mem.record_action(0)
        assert mem.step_in_level == 1
        mem.record_action(1)
        assert mem.step_in_level == 2

    def test_step_resets_on_complete(self):
        mem = GameMemory()
        mem.record_action(0)
        mem.on_level_complete()
        assert mem.step_in_level == 0

    def test_current_sequence_cleared_on_complete(self):
        mem = GameMemory()
        mem.record_action(0)
        mem.on_level_complete()
        assert len(mem.current_sequence) == 0


class TestSuggestFromMemory:
    def test_suggest_at_correct_step(self):
        mem = GameMemory()
        # Complete a level with actions [10, 20, 30]
        mem.record_action(10)
        mem.record_action(20)
        mem.record_action(30)
        mem.on_level_complete()

        # New level, step 0 should suggest action 10
        candidates = mem.suggest_from_memory()
        assert 10 in candidates

    def test_suggest_at_step_1(self):
        mem = GameMemory()
        mem.record_action(10)
        mem.record_action(20)
        mem.on_level_complete()

        # Advance to step 1
        mem.record_action(99)  # current level step 0
        candidates = mem.suggest_from_memory()
        assert 20 in candidates

    def test_no_suggestion_past_sequence_length(self):
        mem = GameMemory()
        mem.record_action(10)
        mem.on_level_complete()

        # Step 0 has a suggestion
        assert len(mem.suggest_from_memory()) == 1
        # Advance past the saved sequence length
        mem.record_action(99)
        assert len(mem.suggest_from_memory()) == 0

    def test_multiple_sequences(self):
        mem = GameMemory()
        # Sequence 1
        mem.record_action(10)
        mem.record_action(20)
        mem.on_level_complete()
        # Sequence 2
        mem.record_action(30)
        mem.record_action(40)
        mem.on_level_complete()

        # Step 0 should have suggestions from both sequences
        candidates = mem.suggest_from_memory()
        assert 10 in candidates
        assert 30 in candidates

    def test_empty_memory_returns_empty(self):
        mem = GameMemory()
        assert mem.suggest_from_memory() == []


class TestOnLevelReset:
    def test_reset_discards_current_sequence(self):
        mem = GameMemory()
        mem.record_action(0)
        mem.record_action(1)
        mem.on_level_reset()
        assert len(mem.current_sequence) == 0
        assert mem.step_in_level == 0
        # No sequence saved
        assert len(mem.success_sequences) == 0

    def test_reset_preserves_past_successes(self):
        mem = GameMemory()
        mem.record_action(10)
        mem.on_level_complete()
        # New level fails
        mem.record_action(99)
        mem.on_level_reset()
        # Past success should still be there
        assert len(mem.success_sequences) == 1


class TestMaxSequences:
    def test_exceeding_max_drops_oldest(self):
        mem = GameMemory(max_sequences=3)
        for i in range(5):
            mem.record_action(i * 10)
            mem.on_level_complete()
        assert len(mem.success_sequences) == 3
        # Oldest (0) and (10) should be gone, remaining: 20, 30, 40
        first_actions = [seq[0].action_idx for seq in mem.success_sequences]
        assert first_actions == [20, 30, 40]


class TestClear:
    def test_full_clear(self):
        mem = GameMemory()
        mem.record_action(0)
        mem.on_level_complete()
        mem.record_action(1)
        mem.clear()
        assert len(mem.success_sequences) == 0
        assert len(mem.current_sequence) == 0
        assert mem.step_in_level == 0
