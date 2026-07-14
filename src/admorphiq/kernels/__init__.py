"""Namespace-safe generic kernels (R56).

Pure computation primitives the LLM (or a quarantined public-game adapter
script) composes by supplying the semantics — roles, goals, rules, masks.
Kernels never touch the environment, never infer goals, and contain no
game-specific constants. See docs/r56_codex_toolbase_verdict_20260715.md.
"""

from admorphiq.kernels.rewrite import derive_rewrites, find_derivation
from admorphiq.kernels.shapes import (
    assign_pairs,
    best_transform_match,
    crop_to_content,
    dihedral_transforms,
    iou,
)

__all__ = [
    "derive_rewrites",
    "find_derivation",
    "assign_pairs",
    "best_transform_match",
    "crop_to_content",
    "dihedral_transforms",
    "iou",
]
