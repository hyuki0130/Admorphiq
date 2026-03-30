"""Perception layer for ARC-AGI-3 frame encoding."""

from .cnn import ActionHead, CNNBackbone, CoordinateHead
from .model import PerceptionModel

__all__ = ["CNNBackbone", "ActionHead", "CoordinateHead", "PerceptionModel"]
