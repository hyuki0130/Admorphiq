"""Tests for admorphiq.planner.explorer.SystematicExplorer."""

import torch

from admorphiq.planner.explorer import SystematicExplorer


def _dummy_hash() -> str:
    return "abcdef1234567890"


class TestExplorationBonus:
    def test_untried_action_bonus_is_1(self):
        explorer = SystematicExplorer()
        bonus = explorer.get_exploration_bonus(_dummy_hash(), 0, 5)
        assert bonus == 1.0

    def test_tried_action_bonus_is_0(self):
        explorer = SystematicExplorer()
        state_hash = _dummy_hash()
        explorer.record_action(state_hash, 0)
        bonus = explorer.get_exploration_bonus(state_hash, 0, 5)
        assert bonus == 0.0

    def test_different_action_still_untried(self):
        explorer = SystematicExplorer()
        state_hash = _dummy_hash()
        explorer.record_action(state_hash, 0)
        bonus = explorer.get_exploration_bonus(state_hash, 1, 5)
        assert bonus == 1.0


class TestRecordAction:
    def test_record_and_check(self):
        explorer = SystematicExplorer()
        state_hash = _dummy_hash()
        assert explorer.get_exploration_bonus(state_hash, 2, 5) == 1.0
        explorer.record_action(state_hash, 2)
        assert explorer.get_exploration_bonus(state_hash, 2, 5) == 0.0

    def test_different_states_independent(self):
        explorer = SystematicExplorer()
        explorer.record_action("state_a", 0)
        assert explorer.get_exploration_bonus("state_a", 0, 5) == 0.0
        assert explorer.get_exploration_bonus("state_b", 0, 5) == 1.0


class TestGetExplorationBonuses:
    def test_bonuses_array_shape(self):
        import numpy as np
        explorer = SystematicExplorer()
        mask = np.zeros(4101, dtype=bool)
        mask[:5] = True
        bonuses = explorer.get_exploration_bonuses(_dummy_hash(), 4101, mask)
        assert bonuses.shape == (4101,)
        # All 5 simple actions untried, so bonuses[:5] should be 1.0
        assert (bonuses[:5] == 1.0).all()
        assert (bonuses[5:] == 0.0).all()

    def test_bonuses_after_recording(self):
        import numpy as np
        explorer = SystematicExplorer()
        state_hash = _dummy_hash()
        explorer.record_action(state_hash, 0)
        explorer.record_action(state_hash, 2)
        mask = np.zeros(4101, dtype=bool)
        mask[:5] = True
        bonuses = explorer.get_exploration_bonuses(state_hash, 4101, mask)
        assert bonuses[0] == 0.0
        assert bonuses[1] == 1.0
        assert bonuses[2] == 0.0
        assert bonuses[3] == 1.0
        assert bonuses[4] == 1.0


class TestSuggestAction:
    def test_suggests_untried_simple_first(self):
        explorer = SystematicExplorer()
        state_hash = _dummy_hash()
        suggested = explorer.suggest_action(state_hash, [0, 1, 2], action6_available=True)
        assert suggested == 0  # first untried simple action

    def test_suggests_next_untried_simple(self):
        explorer = SystematicExplorer()
        state_hash = _dummy_hash()
        explorer.record_action(state_hash, 0)
        suggested = explorer.suggest_action(state_hash, [0, 1, 2], action6_available=True)
        assert suggested == 1

    def test_suggests_action6_grid_when_all_simple_tried(self):
        explorer = SystematicExplorer()
        state_hash = _dummy_hash()
        for idx in [0, 1, 2]:
            explorer.record_action(state_hash, idx)
        suggested = explorer.suggest_action(state_hash, [0, 1, 2], action6_available=True)
        # Should be a grid coordinate index (>= 5)
        assert suggested is not None
        assert suggested >= 5

    def test_returns_none_when_all_tried(self):
        explorer = SystematicExplorer()
        state_hash = _dummy_hash()
        # Mark all simple actions as tried
        for idx in [0, 1, 2]:
            explorer.record_action(state_hash, idx)
        # Mark all grid coords as tried (regular + forced)
        all_coords = set(SystematicExplorer.GRID_COORDS) | set(SystematicExplorer.FORCED_GRID_COORDS)
        for gx, gy in all_coords:
            coord_idx = 5 + gy * 64 + gx
            explorer.record_action(state_hash, coord_idx)
        suggested = explorer.suggest_action(state_hash, [0, 1, 2], action6_available=True)
        assert suggested is None

    def test_no_action6_skips_grid(self):
        explorer = SystematicExplorer()
        state_hash = _dummy_hash()
        for idx in [0, 1]:
            explorer.record_action(state_hash, idx)
        suggested = explorer.suggest_action(state_hash, [0, 1], action6_available=False)
        assert suggested is None


class TestClear:
    def test_clear_resets_state(self):
        explorer = SystematicExplorer()
        state_hash = _dummy_hash()
        explorer.record_action(state_hash, 0)
        assert explorer.get_exploration_bonus(state_hash, 0, 5) == 0.0
        explorer.clear()
        assert explorer.get_exploration_bonus(state_hash, 0, 5) == 1.0


class TestHashFrame:
    def test_deterministic(self):
        frame = torch.randn(16, 64, 64)
        h1 = SystematicExplorer.hash_frame(frame)
        h2 = SystematicExplorer.hash_frame(frame)
        assert h1 == h2

    def test_different_frames_different_hash(self):
        f1 = torch.zeros(16, 64, 64)
        f2 = torch.ones(16, 64, 64)
        assert SystematicExplorer.hash_frame(f1) != SystematicExplorer.hash_frame(f2)
