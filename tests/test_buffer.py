"""Tests for admorphiq.utils.buffer.ExperienceBuffer."""

import pytest
import torch

from admorphiq.utils.buffer import ExperienceBuffer


def _make_frame(value: float = 0.0) -> torch.Tensor:
    """Create a dummy (16, 64, 64) frame tensor."""
    return torch.full((16, 64, 64), value)


class TestExperienceBufferAdd:
    def test_add_increases_len(self):
        buf = ExperienceBuffer()
        assert len(buf) == 0
        buf.add(_make_frame(0.0), 0, True)
        assert len(buf) == 1
        buf.add(_make_frame(1.0), 0, False)
        assert len(buf) == 2

    def test_duplicate_rejected(self):
        buf = ExperienceBuffer()
        frame = _make_frame(0.0)
        assert buf.add(frame, 0, True) is True
        assert buf.add(frame, 0, True) is False  # same frame + action
        assert len(buf) == 1

    def test_same_frame_different_action_accepted(self):
        buf = ExperienceBuffer()
        frame = _make_frame(0.0)
        buf.add(frame, 0, True)
        buf.add(frame, 1, True)
        assert len(buf) == 2

    def test_same_action_different_frame_accepted(self):
        buf = ExperienceBuffer()
        buf.add(_make_frame(0.0), 0, True)
        buf.add(_make_frame(1.0), 0, True)
        assert len(buf) == 2


class TestExperienceBufferSample:
    def test_sample_shape(self):
        buf = ExperienceBuffer()
        for i in range(10):
            buf.add(_make_frame(float(i)), i % 5, i % 2 == 0)
        frames, actions, labels = buf.sample(4)
        assert frames.shape == (4, 16, 64, 64)
        assert actions.shape == (4,)
        assert labels.shape == (4,)
        assert actions.dtype == torch.long
        assert labels.dtype == torch.bool

    def test_sample_larger_than_buffer(self):
        """sample(batch_size) with batch_size > len returns min(batch_size, len)."""
        buf = ExperienceBuffer()
        buf.add(_make_frame(0.0), 0, True)
        buf.add(_make_frame(1.0), 1, False)
        frames, actions, labels = buf.sample(100)
        assert frames.shape[0] == 2

    def test_sample_empty_buffer(self):
        """Sampling from an empty buffer should raise."""
        buf = ExperienceBuffer()
        with pytest.raises(RuntimeError):
            buf.sample(1)


class TestExperienceBufferClear:
    def test_clear(self):
        buf = ExperienceBuffer()
        for i in range(5):
            buf.add(_make_frame(float(i)), i, True)
        assert len(buf) == 5
        buf.clear()
        assert len(buf) == 0

    def test_can_add_after_clear(self):
        buf = ExperienceBuffer()
        frame = _make_frame(0.0)
        buf.add(frame, 0, True)
        buf.clear()
        # Same frame+action should be accepted after clear (hash set cleared)
        assert buf.add(frame, 0, True) is True
        assert len(buf) == 1


class TestExperienceBufferMaxlen:
    def test_maxlen_eviction(self):
        buf = ExperienceBuffer(maxlen=5)
        for i in range(10):
            buf.add(_make_frame(float(i)), 0, True)
        assert len(buf) == 5


class TestExperienceBufferNextFrame:
    def test_add_with_next_frame(self):
        buf = ExperienceBuffer()
        frame = _make_frame(0.0)
        next_frame = _make_frame(1.0)
        assert buf.add(frame, 0, True, next_frame=next_frame) is True
        assert len(buf) == 1

    def test_add_without_next_frame(self):
        """Backward compatible: next_frame defaults to None."""
        buf = ExperienceBuffer()
        buf.add(_make_frame(0.0), 0, True)
        assert len(buf) == 1

    def test_sample_still_works_with_next_frame(self):
        """Legacy sample() returns 3-tuple even when next_frame is stored."""
        buf = ExperienceBuffer()
        for i in range(5):
            buf.add(_make_frame(float(i)), i, True, next_frame=_make_frame(float(i + 1)))
        frames, actions, labels = buf.sample(3)
        assert frames.shape == (3, 16, 64, 64)
        assert actions.shape == (3,)
        assert labels.shape == (3,)

    def test_sample_with_next_shape(self):
        buf = ExperienceBuffer()
        for i in range(5):
            buf.add(_make_frame(float(i)), i, True, next_frame=_make_frame(float(i + 1)))
        result = buf.sample_with_next(3)
        assert result is not None
        frames, actions, labels, next_frames = result
        assert frames.shape == (3, 16, 64, 64)
        assert actions.shape == (3,)
        assert labels.shape == (3,)
        assert next_frames.shape == (3, 16, 64, 64)

    def test_sample_with_next_returns_none_if_not_enough(self):
        """Returns None if fewer entries have next_frame than batch_size."""
        buf = ExperienceBuffer()
        # Add entries without next_frame
        buf.add(_make_frame(0.0), 0, True)
        buf.add(_make_frame(1.0), 1, True)
        # Only 1 entry with next_frame
        buf.add(_make_frame(2.0), 2, True, next_frame=_make_frame(3.0))
        result = buf.sample_with_next(2)
        assert result is None

    def test_sample_with_next_filters_none_entries(self):
        """Only entries with next_frame are sampled."""
        buf = ExperienceBuffer()
        buf.add(_make_frame(0.0), 0, True)  # no next_frame
        buf.add(_make_frame(1.0), 1, True, next_frame=_make_frame(2.0))
        buf.add(_make_frame(3.0), 2, True, next_frame=_make_frame(4.0))
        result = buf.sample_with_next(2)
        assert result is not None
        frames, actions, labels, next_frames = result
        assert frames.shape[0] == 2
