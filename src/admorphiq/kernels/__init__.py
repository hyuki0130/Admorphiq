"""Namespace-safe generic kernels (R56).

Pure computation primitives the LLM (or a quarantined public-game adapter
script) composes by supplying the semantics — roles, goals, rules, masks.
Kernels never touch the environment, never infer goals, and contain no
game-specific constants. See docs/r56_codex_toolbase_verdict_20260715.md.
"""

from admorphiq.kernels.canonical import (
    canonical_key,
    choose_canonicalization,
    key_table,
    stability_report,
)
from admorphiq.kernels.geometry import (
    axis_snap,
    closed_frames,
    connectors,
    covering_offsets,
    elongated_axis,
    point_toward,
    project_to_axis,
    recover_occluded_frame,
    split_fused_frame,
)
from admorphiq.kernels.gf2 import gf2_nullspace, gf2_solve
from admorphiq.kernels.motion import (
    changed_region_attribution,
    frame_diff,
    learn_point_operators,
    learn_reflection_operators,
    motion_vectors,
    plan_overwrites,
    plan_reflection_coverage,
    reflect_cells,
    reflection_orbit,
    track_objects,
)
from admorphiq.kernels.parse import (
    cluster_widths,
    color_mode,
    occupied_runs,
    split_runs_by_pitch,
)
from admorphiq.kernels.paths import (
    configuration_path,
    grid_distance_field,
    grid_shortest_path,
    path_to_moves,
    reachable_frontier,
    transition_shortest_path,
)
from admorphiq.kernels.regions import (
    find_regions,
    group_by_axis,
    multiset_signature,
    multisets_equal,
    region_relations,
    size_clusters,
    tile_bbox,
)
from admorphiq.kernels.rewrite import derive_rewrites, find_derivation, greedy_parse
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
    "configuration_path",
    "grid_distance_field",
    "grid_shortest_path",
    "path_to_moves",
    "reachable_frontier",
    "transition_shortest_path",
    "changed_region_attribution",
    "frame_diff",
    "learn_point_operators",
    "learn_reflection_operators",
    "motion_vectors",
    "plan_overwrites",
    "plan_reflection_coverage",
    "reflect_cells",
    "reflection_orbit",
    "track_objects",
    "find_regions",
    "region_relations",
    "group_by_axis",
    "multiset_signature",
    "multisets_equal",
    "size_clusters",
    "tile_bbox",
    "canonical_key",
    "choose_canonicalization",
    "key_table",
    "stability_report",
    "axis_snap",
    "closed_frames",
    "connectors",
    "covering_offsets",
    "elongated_axis",
    "point_toward",
    "project_to_axis",
    "recover_occluded_frame",
    "split_fused_frame",
    "cluster_widths",
    "color_mode",
    "occupied_runs",
    "split_runs_by_pitch",
    "greedy_parse",
    "gf2_nullspace",
    "gf2_solve",
]
