"""InferentialAgent — round-6 redesign of the generic strategies.

Implements the five-phase pipeline documented at
`.wiki/wiki/strategies/frame_only/inferential_agent.md`:

  Phase 1 — Observation      : probe every action; build action_profile.
  Phase 2 — Entity Detection : tag color clusters by role from probes.
  Phase 3 — Goal Inference   : infer level-clear condition from transitions.
  Phase 4 — Plan Synthesis   : pick a plan template and execute.
  Phase 5 — Learning Loop    : retry with expanded probes on failure.

Exported via `agent_ensemble` so the R3 introspector finds it.

This module reads ONLY the rendered frame and `available_actions` /
`levels_completed` / `state.name` from the env. No sprite tags, no
`game.*` attribute reads, no game-name branches.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from arcengine import GameAction

# ----- Low-level env helpers (duplicated from agent_ensemble to keep
#       this module free of cyclic imports during test discovery). --------

def _get_frame(obs: Any) -> np.ndarray:
    return np.array(obs.frame[0], dtype=np.int32)


def _reset(env: Any) -> Any:
    return env.step(GameAction.RESET)


# Round 15: multi-level cumulative prefix. When the outer loop clears
# level L, the winning action sequence is appended to this list. Every
# subsequent _reset_then_replay call resets then replays the prefix so
# the env returns to the LEVEL-L+1 START, not the game start. Plans
# that need reset should call _reset_then_replay instead of _reset.
_ACTIVE_PREFIX: list[tuple] = []
# Plans that clear a level append their winning sequence here. The
# outer loop consumes it after each plan call and may extend
# _ACTIVE_PREFIX with it.
_LAST_WIN_SEQUENCE: list[tuple] = []

# Round 16: last measured lights-out toggle stencil. Populated by
# _plan_lights_out on each call. Shape: {"cells": [(x,y), ...],
# "A": np.uint8 matrix, "base_classes": [int], "toggled_classes":
# [int]}. None when measurement was skipped (budget too tight).
_LAST_STENCIL: dict | None = None


def _replay_action(env: Any, action_tuple: tuple) -> Any:
    kind = action_tuple[0]
    if kind == "click":
        return _click(env, action_tuple[1], action_tuple[2])
    return _act(env, action_tuple[1])


def _reset_then_replay(env: Any) -> Any:
    """Reset, then replay every action in `_ACTIVE_PREFIX`. Used by
    every plan that needs to return to the current level's start state
    (not the game start). If the prefix is empty, equivalent to _reset.
    """
    obs = env.step(GameAction.RESET)  # intentionally not `_reset` to make
    # the global replace-all below safe (round 15 refactor).
    for action_tuple in _ACTIVE_PREFIX:
        obs = _replay_action(env, action_tuple)
    return obs


def _act(env: Any, aid: int) -> Any:
    if aid == 6:
        return env.step(GameAction.ACTION6, data={"x": 32, "y": 32})
    return env.step(GameAction.from_id(aid))


def _click(env: Any, x: int, y: int) -> Any:
    return env.step(GameAction.ACTION6, data={"x": int(x), "y": int(y)})


def _flood_clusters(frame: np.ndarray, min_size: int = 3) -> list[dict]:
    """Return list of {color, size, cx, cy, ymin..xmax, pixels} dicts."""
    h, w = frame.shape
    bg = int(frame[0, 0])
    visited = np.zeros((h, w), dtype=bool)
    clusters: list[dict] = []
    for y in range(h):
        for x in range(w):
            if visited[y, x]:
                continue
            c = int(frame[y, x])
            if c == bg or c == 0:
                visited[y, x] = True
                continue
            stack = [(y, x)]
            ys: list[int] = []
            xs: list[int] = []
            while stack:
                yy, xx = stack.pop()
                if yy < 0 or yy >= h or xx < 0 or xx >= w or visited[yy, xx]:
                    continue
                if int(frame[yy, xx]) != c:
                    continue
                visited[yy, xx] = True
                ys.append(yy)
                xs.append(xx)
                stack.append((yy + 1, xx))
                stack.append((yy - 1, xx))
                stack.append((yy, xx + 1))
                stack.append((yy, xx - 1))
            if len(ys) < min_size:
                continue
            clusters.append({
                "color": c,
                "size": len(ys),
                "cx": int(sum(xs) / len(xs)),
                "cy": int(sum(ys) / len(ys)),
                "ymin": min(ys),
                "ymax": max(ys),
                "xmin": min(xs),
                "xmax": max(xs),
            })
    return clusters


# ─── Phase 1: Observation ──────────────────────────────────────────────


def _classify_region(diff_mask: np.ndarray, total_pixels: int) -> str:
    """Categorize the size of a frame-diff region."""
    n = int(diff_mask.sum())
    if n == 0:
        return "inert"
    ratio = n / total_pixels
    if ratio > 0.30:
        return "global"
    if ratio > 0.05:
        return "regional"
    return "local"


def _bbox_and_centroid(mask: np.ndarray) -> tuple[tuple[int, int, int, int], tuple[int, int]]:
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return (0, 0, 0, 0), (0, 0)
    return (int(ys.min()), int(xs.min()), int(ys.max()), int(xs.max())), (int(xs.mean()), int(ys.mean()))


def observation_phase(env: Any, stride: int = 8, budget: int = 200) -> tuple[dict, int]:
    """Probe every available action once; build a per-action profile.

    Returns (action_profile, actions_used). `action_profile` is a dict:
      {
        "base_levels": int,
        "base_frame_hash": int,
        "scalar": {aid: ScalarProfile},  # aid ∈ 1..5, 7
        "click": list[ClickProfile],     # one per probed (x, y)
        "observed_transitions": list[TransitionRecord],
        "hud_mask": np.ndarray,          # round-12: pixels that changed under every probe
      }

    ScalarProfile and ClickProfile carry:
      diff_magnitude, bbox, centroid, region_kind, did_transition
    with HUD pixels already excluded from diff_magnitude / bbox /
    centroid / region_kind (round 12 — CD82 measured a step-counter
    at (63,63) incrementing under every probe, which previously
    made every click look "responsive-local" and mass-tagged cells
    as palettes).

    TransitionRecord carries (frame_before, frame_after, action).
    """
    used = 0
    obs = _reset_then_replay(env)
    used += 1
    base_frame = _get_frame(obs)
    avail = sorted(int(a) for a in obs.available_actions if int(a) != 0)
    base_levels = obs.levels_completed

    total_pixels = base_frame.size
    scalar: dict[int, dict] = {}
    click_probes: list[dict] = []
    transitions: list[dict] = []
    # Raw diff masks kept for HUD detection — pixels that changed
    # under EVERY probe are step counters / timers, not gameplay.
    raw_diff_masks: list[np.ndarray] = []

    def _record_transition(f_before: np.ndarray, f_after: np.ndarray, action_desc: dict) -> None:
        transitions.append({
            "frame_before": f_before.copy(),
            "frame_after": f_after.copy(),
            "action": dict(action_desc),
        })

    # Phase 1a: scalar actions (1..5, 7) — keep the post-frame so
    # entity detection can do proper before/after cluster matching.
    for aid in avail:
        if aid == 6 or used >= budget:
            continue
        obs = _reset_then_replay(env)
        used += 1
        f0 = _get_frame(obs)
        obs = _act(env, aid)
        used += 1
        f1 = _get_frame(obs)
        mask = (f0 != f1)
        did_trans = obs.levels_completed > base_levels
        raw_diff_masks.append(mask)
        scalar[aid] = {
            "aid": aid,
            "raw_mask": mask,
            "did_transition": did_trans,
            "frame_before": f0,
            "frame_after": f1,
        }
        if did_trans:
            _record_transition(f0, f1, {"kind": "scalar", "aid": aid})

    # Phase 1b: ACTION6 probes. Combine two sampling strategies:
    #   (i) a stride-K grid over the whole frame (catches clicks on
    #       empty cells that nonetheless affect state, e.g. bit panels)
    #   (ii) one probe per flood-filled cluster centroid (catches
    #       sparse interactive sprites that a coarse grid misses —
    #       critical for lights-out and rare-click games like FT09).
    # The union is deduplicated by coordinate.
    if 6 in avail and used < budget:
        h, w = base_frame.shape
        probe_coords: list[tuple[int, int]] = []
        seen_coord: set[tuple[int, int]] = set()
        for cluster in _flood_clusters(base_frame, min_size=2):
            key = (cluster["cx"], cluster["cy"])
            if key not in seen_coord:
                seen_coord.add(key)
                probe_coords.append(key)
        for y in range(stride // 2, h, stride):
            for x in range(stride // 2, w, stride):
                if (x, y) not in seen_coord:
                    seen_coord.add((x, y))
                    probe_coords.append((x, y))
        for (x, y) in probe_coords:
            if used >= budget:
                break
            obs = _reset_then_replay(env)
            used += 1
            f0 = _get_frame(obs)
            obs = _click(env, x, y)
            used += 1
            f1 = _get_frame(obs)
            mask = (f0 != f1)
            did_trans = obs.levels_completed > base_levels
            raw_diff_masks.append(mask)
            click_probes.append({
                "x": x,
                "y": y,
                "raw_mask": mask,
                "did_transition": did_trans,
            })
            if did_trans:
                _record_transition(f0, f1, {"kind": "click", "x": x, "y": y})

    # HUD derivation — pixels that changed under at least N-1 of N
    # probes are a step counter / timer / animated HUD element.
    # Subtract them from every probe's effective diff so entity
    # detection doesn't mass-tag cells as "palettes" just because
    # the HUD increments on every action.
    if raw_diff_masks:
        stack = np.stack(raw_diff_masks, axis=0)
        change_count = stack.sum(axis=0)
        # HUD ≡ pixels that changed under ≥ 80% of probes.
        threshold = max(1, int(0.8 * len(raw_diff_masks)))
        hud_mask = change_count >= threshold
    else:
        hud_mask = np.zeros_like(base_frame, dtype=bool)

    def _finalize(entry: dict) -> dict:
        mask = entry.pop("raw_mask")
        clean_mask = mask & ~hud_mask
        bbox, centroid = _bbox_and_centroid(clean_mask)
        entry["diff_magnitude"] = int(clean_mask.sum())
        entry["bbox"] = bbox
        entry["centroid"] = centroid
        entry["region_kind"] = _classify_region(clean_mask, total_pixels)
        return entry

    for aid in list(scalar.keys()):
        scalar[aid] = _finalize(scalar[aid])
    click_probes = [_finalize(p) for p in click_probes]

    return ({
        "base_levels": int(base_levels),
        "base_frame": base_frame,
        "avail": avail,
        "scalar": scalar,
        "click": click_probes,
        "observed_transitions": transitions,
        "hud_mask": hud_mask,
    }, used)


# ─── Phase 2: Entity Detection ─────────────────────────────────────────


def entity_phase(base_frame: np.ndarray, action_profile: dict) -> dict:
    """Tag color clusters with functional roles from Phase 1 data.

    Returns:
      {
        "clusters": [...],           # all flood-filled clusters
        "player": cluster | None,    # at most one player cluster
        "executors": [cluster],      # executor-cell-overlapping clusters
        "palettes": [cluster],       # palette-swatch clusters
        "goal_regions": [cluster],   # candidate goal regions
        "merge_items": [cluster],    # same-color-pair items
        "obstacles": [cluster],      # static, large, unmoving
      }
    """
    clusters = _flood_clusters(base_frame, min_size=3)

    entity: dict = {
        "clusters": clusters,
        "player": None,
        "executors": [],
        "palettes": [],
        "goal_regions": [],
        "merge_items": [],
        "obstacles": [],
    }
    if not clusters:
        return entity

    # Player detection: for each cluster in f0, measure how many
    # directional probes produced a before→after shift of its same-color
    # twin. The player is the cluster with the highest "mobility" —
    # consistent across multiple probes — breaking ties by total shift.
    # This is more robust than max-shift-across-any-one-probe, which
    # picked wrong clusters on multi-entity frames (M0R0).
    cluster_scores: dict[tuple[int, int, int], dict] = {}
    for aid, profile in action_profile.get("scalar", {}).items():
        if profile["region_kind"] not in ("local", "regional"):
            continue
        if "frame_before" not in profile or "frame_after" not in profile:
            continue
        c_before = _flood_clusters(profile["frame_before"], min_size=3)
        c_after = _flood_clusters(profile["frame_after"], min_size=3)
        by_color_after: dict[int, list[dict]] = {}
        for c in c_after:
            by_color_after.setdefault(c["color"], []).append(c)
        used_after: set[int] = set()
        for cb in c_before:
            candidates = by_color_after.get(cb["color"], [])
            if not candidates:
                continue
            best = None
            best_d = float("inf")
            best_idx = -1
            for idx, ca in enumerate(candidates):
                if idx in used_after:
                    continue
                if abs(ca["size"] - cb["size"]) > max(4, cb["size"] // 3):
                    continue
                d = (ca["cx"] - cb["cx"]) ** 2 + (ca["cy"] - cb["cy"]) ** 2
                if d < best_d:
                    best_d = d
                    best = ca
                    best_idx = idx
            if best is None or best_d == 0:
                continue
            shift = best_d ** 0.5
            # Filter out 1-pixel shifts — animation / HUD counter artifacts.
            # Real player moves are grid-aligned, typically ≥ 2 pixels.
            if shift < 2.0:
                continue
            used_after.add(best_idx)
            key = (cb["color"], cb["cx"], cb["cy"])
            if key not in cluster_scores:
                cluster_scores[key] = {
                    "cluster": cb,
                    "mobility": 0,
                    "total_shift": 0.0,
                    "steps": {},
                }
            cluster_scores[key]["mobility"] += 1
            cluster_scores[key]["total_shift"] += shift
            cluster_scores[key]["steps"][aid] = (best["cx"] - cb["cx"], best["cy"] - cb["cy"])
    # Pick the best-scoring candidate; require at least one shift.
    best_entry: dict | None = None
    for entry in cluster_scores.values():
        if entry["mobility"] < 1:
            continue
        if best_entry is None:
            best_entry = entry
            continue
        if (entry["mobility"], entry["total_shift"]) > (best_entry["mobility"], best_entry["total_shift"]):
            best_entry = entry
    if best_entry is not None:
        player_candidate = dict(best_entry["cluster"])
        player_candidate["mobility"] = best_entry["mobility"]
        player_candidate["steps_by_aid"] = best_entry["steps"]
        entity["player"] = player_candidate
        # Primary step = the non-zero shift under the first movement
        # action we observed. Used by navigation plan as a fallback
        # step vector.
        any_step = next(iter(best_entry["steps"].values()))
        entity["player_step"] = any_step

    # Executor cells (clicks causing > 30% frame change)
    for c_probe in action_profile.get("click", []):
        if c_probe["region_kind"] == "global":
            entity["executors"].append({
                "x": c_probe["x"],
                "y": c_probe["y"],
                "diff_magnitude": c_probe["diff_magnitude"],
            })

    # Palette swatches: click probes with small diff AND the diff
    # centroid is OUTSIDE the click location (the click recolored a
    # separate cursor region).
    for c_probe in action_profile.get("click", []):
        if c_probe["region_kind"] != "local":
            continue
        if c_probe["diff_magnitude"] > 60:
            continue
        cx, cy = c_probe["centroid"]
        if abs(cx - c_probe["x"]) > 10 or abs(cy - c_probe["y"]) > 10:
            entity["palettes"].append({"x": c_probe["x"], "y": c_probe["y"]})

    # Merge items: clusters in the fruit-size window OR same-color
    # pairs. Round 21: loosened from strict same-color-pair-only to
    # accept singletons in the small-fruit range (size 8..150). The
    # merge plan still picks same-color pairs for click midpoints; the
    # broader set helps goal_phase detect that the env is a merge
    # puzzle at all (previously SU15 L1 surfaced only 2 merge_items
    # because most fruit colors appeared once, so the rest were
    # dropped — routing fell back from merge to unknown).
    color_counts: dict[int, int] = {}
    for c in clusters:
        color_counts[c["color"]] = color_counts.get(c["color"], 0) + 1
    for c in clusters:
        same_color_pair = color_counts[c["color"]] >= 2 and c["size"] < 200
        fruit_shape = 8 <= c["size"] <= 150
        if same_color_pair or fruit_shape:
            entity["merge_items"].append(dict(c))

    # Goal regions: stable clusters with distinct border color that are
    # bordered by background (hollow rectangles). Heuristic: aspect ratio
    # close to 1, small body relative to bbox area.
    for c in clusters:
        w = c["xmax"] - c["xmin"] + 1
        h = c["ymax"] - c["ymin"] + 1
        bbox_area = w * h
        if bbox_area == 0:
            continue
        fill_ratio = c["size"] / bbox_area
        # Outlined rectangle: fill_ratio ≈ perimeter / area
        if fill_ratio < 0.35 and 8 <= w <= 40 and 8 <= h <= 40:
            entity["goal_regions"].append(dict(c))

    # Obstacles: large static clusters. Exclude the player + goal + items.
    reserved_colors = set()
    if entity["player"] is not None:
        reserved_colors.add(entity["player"]["color"])
    for c in entity["merge_items"]:
        reserved_colors.add(c["color"])
    for c in entity["goal_regions"]:
        reserved_colors.add(c["color"])
    for c in clusters:
        if c["color"] in reserved_colors:
            continue
        if c["size"] > 80:
            entity["obstacles"].append(dict(c))

    return entity


# ─── Phase 3: Goal Inference ───────────────────────────────────────────


def goal_phase(action_profile: dict, entity_map: dict) -> dict:
    """Classify the level-clear condition.

    Returns a dict:
      {"kind": "navigation"|"merge"|"paint_fill"|"toggle"|"unknown",
       "target_color": int | None,
       "target_region": (x0, y0, x1, y1) | None,
       "confidence": 0.0..1.0,
       "source": "observed" | "heuristic"}
    """
    # 3a. Use observed transitions if any.
    transitions = action_profile.get("observed_transitions", [])
    for tr in transitions:
        before = tr["frame_before"]
        after = tr["frame_after"]
        # Did the player end in a goal region?
        if entity_map.get("player") is not None and entity_map.get("goal_regions"):
            ys, xs = np.where(after == entity_map["player"]["color"])
            if len(ys):
                mean_x, mean_y = int(xs.mean()), int(ys.mean())
                for gr in entity_map["goal_regions"]:
                    if gr["xmin"] - 3 <= mean_x <= gr["xmax"] + 3 and gr["ymin"] - 3 <= mean_y <= gr["ymax"] + 3:
                        return {
                            "kind": "navigation",
                            "target_color": None,
                            "target_region": (gr["xmin"], gr["ymin"], gr["xmax"], gr["ymax"]),
                            "confidence": 0.9,
                            "source": "observed",
                        }
        # Did pair counts drop?
        clusters_before = _flood_clusters(before, min_size=3)
        clusters_after = _flood_clusters(after, min_size=3)
        if len(clusters_after) < len(clusters_before):
            return {
                "kind": "merge",
                "target_color": None,
                "target_region": None,
                "confidence": 0.85,
                "source": "observed",
            }
        # Did a dominant new color appear?
        hist_before = {int(c): int(n) for c, n in zip(*np.unique(before, return_counts=True))}
        hist_after = {int(c): int(n) for c, n in zip(*np.unique(after, return_counts=True))}
        grown = [(c, hist_after[c] - hist_before.get(c, 0)) for c in hist_after]
        grown.sort(key=lambda t: -t[1])
        if grown and grown[0][1] > before.size * 0.2:
            return {
                "kind": "paint_fill",
                "target_color": grown[0][0],
                "target_region": None,
                "confidence": 0.7,
                "source": "observed",
            }

    # 3b. Heuristic fallback from entity_map.
    # Player detected → navigation (preferred over merge even if no
    # explicit goal_region was found; the plan runner BFSes over player
    # centroid state until levels_completed advances).
    if entity_map.get("player") is not None:
        gr = entity_map["goal_regions"][0] if entity_map.get("goal_regions") else None
        target_region = (gr["xmin"], gr["ymin"], gr["xmax"], gr["ymax"]) if gr else None
        return {
            "kind": "navigation",
            "target_color": None,
            "target_region": target_region,
            "confidence": 0.6 if gr else 0.4,
            "source": "heuristic",
        }
    if entity_map.get("merge_items"):
        return {
            "kind": "merge",
            "target_color": None,
            "target_region": None,
            "confidence": 0.4,
            "source": "heuristic",
        }
    if entity_map.get("palettes") and entity_map.get("executors"):
        return {
            "kind": "paint_fill",
            "target_color": None,
            "target_region": None,
            "confidence": 0.4,
            "source": "heuristic",
        }
    if entity_map.get("executors"):
        return {
            "kind": "toggle",
            "target_color": None,
            "target_region": None,
            "confidence": 0.3,
            "source": "heuristic",
        }
    return {
        "kind": "unknown",
        "target_color": None,
        "target_region": None,
        "confidence": 0.1,
        "source": "heuristic",
    }


# ─── Phase 4: Plan Synthesis ───────────────────────────────────────────


def _plan_navigation(env: Any, action_profile: dict, entity_map: dict, goal: dict, budget: int) -> tuple[int, int]:
    """Delegate movement-game solving to BFSSolver with prefix awareness.

    Round 20: the prior implementation delegated to
    `strat_bfs_state_space`, which internally `reset(env)`s and ignores
    `_ACTIVE_PREFIX`. On multi-level games (CD82, every obs after L1)
    the BFS always re-solves the level-1 start and returns `levels=1`
    with the outer `best` already at 1, so no progress.

    Rewritten: call `BFSSolver.solve` directly with `prefix=_ACTIVE_PREFIX`
    (converted to BFSSolver format) so BFS starts from the CURRENT
    level state. Winning actions are written into `_LAST_WIN_SEQUENCE`
    so the outer loop can extend the prefix and move on to the next
    level.
    """
    from ..agent_ensemble import get_frame as _ae_get_frame  # noqa: F401
    from ..planner.bfs_solver import BFSSolver
    global _LAST_WIN_SEQUENCE

    used = 0
    avail_scalar = sorted(
        int(aid) for aid, p in action_profile.get("scalar", {}).items()
        if 1 <= int(aid) <= 5
    )
    has_click = any(
        int(aid) == 6 for aid in action_profile.get("avail", [])
    ) or bool(action_profile.get("click"))
    if not avail_scalar and not has_click:
        return 0, used

    # Convert _ACTIVE_PREFIX to BFSSolver format: int for dir, (x, y)
    # tuple for click.
    prefix_actions: list = []
    for item in _ACTIVE_PREFIX:
        if item[0] == "click":
            prefix_actions.append((int(item[1]), int(item[2])))
        else:
            prefix_actions.append(int(item[1]))

    # Gather click_coords from observation phase for hybrid games.
    click_coords: list[tuple[int, int]] | None = None
    if has_click:
        click_probes = [
            c for c in action_profile.get("click", [])
            if c.get("diff_magnitude", 0) >= 10
        ]
        click_probes.sort(key=lambda c: -int(c.get("diff_magnitude", 0)))
        click_coords = [(int(c["x"]), int(c["y"])) for c in click_probes[:20]]
        if not click_coords:
            click_coords = None

    nc = len(click_coords) if click_coords else 0
    if click_coords:
        max_depth = 25 if nc > 5 else 35
        max_states = 15000 if nc > 5 else 25000
        time_limit = 60.0
    else:
        max_depth = 50
        max_states = 40000
        time_limit = 90.0

    solver = BFSSolver(
        max_depth=max_depth, max_states=max_states, time_limit=time_limit,
    )
    base_levels = action_profile.get("base_levels", 0)

    # Round 22 fix: restore solve_all_levels-style internal chaining
    # inside the plan call. R20's single-solve variant regressed
    # AR25 / M0R0 from 2/2 → 1/2 because the outer loop's
    # observation_phase overhead and plan-budget-cap of 10 000
    # combined to stop forward progress after the first level was
    # cleared within one plan call. Repeat solve while we make
    # progress; the total returns as new_levels.
    cumulative_new: list = []
    levels_cleared = 0
    import time as _time_mod
    plan_start = _time_mod.time()
    soft_time_budget = max(time_limit, 90.0)
    while True:
        if _time_mod.time() - plan_start > soft_time_budget:
            break
        if used + len(prefix_actions) + len(cumulative_new) + 1 > budget:
            break
        result = solver.solve(
            env,
            GameAction.RESET,
            avail_scalar,
            lambda o: o.levels_completed,
            click_coords=click_coords,
            prefix=prefix_actions + cumulative_new,
            expected_base_levels=base_levels + levels_cleared,
        )
        if result is None:
            break
        cumulative_new.extend(result)
        levels_cleared += 1
        used += len(prefix_actions) + len(cumulative_new) + 1

    # Apply the full winning sequence once so the env is left at the
    # correct post-plan state for downstream plans.
    if cumulative_new:
        obs = solver._replay_prefix(
            env, GameAction.RESET, prefix_actions + cumulative_new
        )
        used += len(prefix_actions) + len(cumulative_new) + 1
        new_levels = obs.levels_completed if obs else base_levels + levels_cleared
        _LAST_WIN_SEQUENCE = [
            ("click", a[0], a[1]) if isinstance(a, tuple) else ("act", int(a))
            for a in cumulative_new
        ]
    else:
        new_levels = base_levels
    return int(new_levels), used


def _plan_merge(env: Any, action_profile: dict, entity_map: dict, goal: dict, budget: int) -> tuple[int, int]:
    """Merge same-color cluster pairs via click. Round 7 adds:
      1. Vacuum-radius calibration from the probe data — use the
         maximum observed cluster-shift under any single click as R.
         Clicks are only proposed for pairs whose distance ≤ 2R; for
         larger pairs we attempt "chaining" (click sequence that drags
         one cluster toward the other in multiple steps).
      2. Per-pair fallback click positions: midpoint → 1/3 → 2/3 →
         directly on each cluster. Covers small-radius vacuums (SU15)
         where the literal midpoint falls outside the pull range.
    """
    used = 0
    items = entity_map.get("merge_items", [])
    if not items:
        return 0, used

    # Calibrate vacuum radius R from observation-phase click probes.
    # R ≈ max displacement any cluster experienced under a single click.
    R = 0
    for c_probe in action_profile.get("click", []):
        bbox = c_probe.get("bbox", (0, 0, 0, 0))
        cx = c_probe.get("centroid", (0, 0))[0]
        cy = c_probe.get("centroid", (0, 0))[1]
        # Use the L∞ distance from click coord to the farthest-changed
        # pixel as a proxy for vacuum reach.
        if c_probe.get("diff_magnitude", 0) > 0:
            y0, x0, y1, x1 = bbox
            reach = max(
                abs(c_probe["x"] - x0),
                abs(c_probe["x"] - x1),
                abs(c_probe["y"] - y0),
                abs(c_probe["y"] - y1),
            )
            if reach > R:
                R = reach
    # Safety floor — at worst every click has radius 3 pixels.
    if R < 3:
        R = 8
    max_pair_distance = 2 * R

    obs = _reset_then_replay(env)
    used += 1
    base_levels = obs.levels_completed

    def _candidates(a: dict, b: dict) -> list[tuple[int, int]]:
        """Click positions in decreasing priority for a pair (a, b)."""
        ax, ay = a["cx"], a["cy"]
        bx, by = b["cx"], b["cy"]
        mx, my = (ax + bx) // 2, (ay + by) // 2
        t1x, t1y = (2 * ax + bx) // 3, (2 * ay + by) // 3
        t2x, t2y = (ax + 2 * bx) // 3, (ay + 2 * by) // 3
        return [
            (mx, my),
            (t1x, t1y),
            (t2x, t2y),
            (ax, ay),
            (bx, by),
        ]

    for attempt in range(40):
        if used >= budget:
            break
        f = _get_frame(obs)
        clusters = _flood_clusters(f, min_size=3)
        by_color: dict[int, list[dict]] = {}
        for c in clusters:
            if c["size"] < 200:
                by_color.setdefault(c["color"], []).append(c)
        pairs = []
        for lst in by_color.values():
            if len(lst) < 2:
                continue
            for i in range(len(lst)):
                for j in range(i + 1, len(lst)):
                    dx = lst[i]["cx"] - lst[j]["cx"]
                    dy = lst[i]["cy"] - lst[j]["cy"]
                    d = (dx * dx + dy * dy) ** 0.5
                    pairs.append((d, lst[i], lst[j]))
        pairs.sort(key=lambda t: t[0])
        if not pairs:
            break

        progress_this_attempt = False
        for d, a, b in pairs[:6]:
            if used >= budget:
                break
            for (cx, cy) in _candidates(a, b):
                if used >= budget:
                    break
                pre_frame = _get_frame(obs)
                obs = _click(env, cx, cy)
                used += 1
                if obs.levels_completed > base_levels:
                    return obs.levels_completed, used
                if obs.state.name == "GAME_OVER":
                    return base_levels, used
                post_frame = _get_frame(obs)
                if int(np.count_nonzero(pre_frame - post_frame)) > 0:
                    progress_this_attempt = True
                    break
            if progress_this_attempt:
                break
        if not progress_this_attempt:
            break
    return base_levels, used


def _plan_paint_fill(env: Any, action_profile: dict, entity_map: dict, goal: dict, budget: int) -> tuple[int, int]:
    """Palette → target cells → executor sequence. Uses click probes to
    find target cells of target_color."""
    used = 0
    palettes = entity_map.get("palettes", [])
    executors = entity_map.get("executors", [])
    target_color = goal.get("target_color")
    obs = _reset_then_replay(env)
    used += 1
    base_levels = obs.levels_completed
    f = _get_frame(obs)

    # If target color unknown, pick the executor-cell click color (often
    # the final expected fill color for paint games).
    if target_color is None:
        target_color = int(f[0, 0])  # harmless fallback

    # Cells to fill: flood-fill and pick clusters whose color != target_color.
    clusters = _flood_clusters(f, min_size=2)
    cells_to_fill = [
        (c["cx"], c["cy"]) for c in clusters
        if c["color"] != target_color and c["size"] < 100
    ]

    # Try palette 0 → each cell → executor.
    for palette in palettes[:3]:
        if used >= budget:
            break
        obs = _reset_then_replay(env)
        used += 1
        obs = _click(env, palette["x"], palette["y"])
        used += 1
        for cx, cy in cells_to_fill[:12]:
            if used >= budget:
                break
            obs = _click(env, cx, cy)
            used += 1
            if obs.levels_completed > base_levels:
                return obs.levels_completed, used
        for ex in executors[:2]:
            if used >= budget:
                break
            obs = _click(env, ex["x"], ex["y"])
            used += 1
            if obs.levels_completed > base_levels:
                return obs.levels_completed, used
    return base_levels, used


def _plan_toggle(env: Any, action_profile: dict, entity_map: dict, goal: dict, budget: int) -> tuple[int, int]:
    """Click-sequence search over candidate cells.

    Round-6 version filtered candidates to only cells whose single-probe
    caused a visible frame diff. FT09 measured 0/20 responsive on
    cluster centroids — yet the brittle solver clears 6/6, meaning
    clicks DO have effect but it's delayed (cumulative toggle state)
    or the probe landed off-sprite. Round-7 removes the responsiveness
    prerequisite and enlarges the candidate pool:

      1. Every flood-filled cluster centroid (not just responsive).
      2. Every responsive stride-8 probe (kept from round 6 if any).
      3. Four-corner sampling of each non-trivial cluster (catches
         lit-region sprites where the centroid sits between sub-cells).

    Candidates deduped by (x, y) and capped at 16 to keep depth-3
    enumeration tractable.

    Executor cell, if any, is appended to every candidate sequence.
    """
    used = 0
    executors = entity_map.get("executors", [])
    exec_cell = (executors[0]["x"], executors[0]["y"]) if executors else None
    palette_set = {(p["x"], p["y"]) for p in entity_map.get("palettes", [])}
    executor_set = {(e["x"], e["y"]) for e in executors}

    cand_coords: list[tuple[int, int]] = []
    seen_coord: set[tuple[int, int]] = set()

    def _add(xy: tuple[int, int]) -> None:
        if xy in seen_coord or xy in palette_set or xy in executor_set:
            return
        x, y = xy
        if x < 0 or y < 0 or x >= 64 or y >= 64:
            return
        seen_coord.add(xy)
        cand_coords.append(xy)

    for c in entity_map.get("clusters", []):
        _add((c["cx"], c["cy"]))
        if c["size"] >= 9:
            _add((c["xmin"] + 1, c["ymin"] + 1))
            _add((c["xmax"] - 1, c["ymin"] + 1))
            _add((c["xmin"] + 1, c["ymax"] - 1))
            _add((c["xmax"] - 1, c["ymax"] - 1))
    for c_probe in action_profile.get("click", []):
        if c_probe.get("diff_magnitude", 0) > 0:
            _add((c_probe["x"], c_probe["y"]))

    cand_coords = cand_coords[:16]

    obs = _reset_then_replay(env)
    used += 1
    base_levels = obs.levels_completed

    def _try(seq: list[tuple[int, int]]) -> int:
        nonlocal used
        if used >= budget:
            return base_levels
        obs_local = _reset_then_replay(env)
        used += 1
        for cx, cy in seq:
            if used >= budget:
                return base_levels
            obs_local = _click(env, cx, cy)
            used += 1
            if obs_local.levels_completed > base_levels:
                return int(obs_local.levels_completed)
            if obs_local.state.name == "GAME_OVER":
                return base_levels
        if exec_cell is not None and used < budget:
            obs_local = _click(env, *exec_cell)
            used += 1
            if obs_local.levels_completed > base_levels:
                return int(obs_local.levels_completed)
        return base_levels

    # Singletons.
    for c in cand_coords:
        result = _try([c])
        if result > base_levels:
            return result, used
        if used >= budget:
            return base_levels, used
    # Pairs.
    for i in range(len(cand_coords)):
        for j in range(i + 1, len(cand_coords)):
            if used >= budget:
                return base_levels, used
            result = _try([cand_coords[i], cand_coords[j]])
            if result > base_levels:
                return result, used
    # Triples (bounded — O(n³) gets costly).
    n3 = min(len(cand_coords), 10)
    for i in range(n3):
        for j in range(i + 1, n3):
            for k in range(j + 1, n3):
                if used >= budget:
                    return base_levels, used
                result = _try([cand_coords[i], cand_coords[j], cand_coords[k]])
                if result > base_levels:
                    return result, used
    # Quads — last resort, tiny enumeration (top 7 candidates).
    n4 = min(len(cand_coords), 7)
    for i in range(n4):
        for j in range(i + 1, n4):
            for k in range(j + 1, n4):
                for m in range(k + 1, n4):
                    if used >= budget:
                        return base_levels, used
                    result = _try([cand_coords[i], cand_coords[j], cand_coords[k], cand_coords[m]])
                    if result > base_levels:
                        return result, used
    return base_levels, used


def _extract_cell_class(frame: np.ndarray, cx: int, cy: int, r: int) -> int:
    """Mode color of a (2r+1)x(2r+1) patch centered at (cx, cy).

    Used to classify a cell's current toggle state without reading
    sprite tags — the cell's dominant color acts as its observable
    'state'. The patch is clipped to the frame boundary so cells near
    the edge still return a value.
    """
    h, w = frame.shape
    y0 = max(0, cy - r)
    y1 = min(h, cy + r + 1)
    x0 = max(0, cx - r)
    x1 = min(w, cx + r + 1)
    patch = frame[y0:y1, x0:x1]
    vals, counts = np.unique(patch, return_counts=True)
    return int(vals[int(np.argmax(counts))])


def _measure_toggle_stencil(
    env: Any,
    cells: list[tuple[int, int]],
    patch_radius: int = 2,
    budget: int = 200,
) -> tuple[np.ndarray, list[int], list[int], int]:
    """Round 16: measure the GF(2) stencil matrix A for a lights-out grid.

    For each cell j in `cells`, reset-then-replay then click cell j
    exactly once. Classify each cell i's dominant-color patch before
    and after. A[i][j] = 1 iff cell i's class changed under click j
    alone. Cells whose class is binary (two distinct observed classes
    across the measurement pass) are the usable ones; cells showing
    more than two classes are logged but flagged by excluding their
    row/column from the returned stencil (A row set to 0).

    Returns
    -------
    A : (n, n) uint8
        Stencil matrix — A[i][j] = 1 iff click j toggles cell i.
    base_classes : list[int]
        Each cell's base-state color class (mode of baseline patch).
    toggled_classes : list[int]
        Each cell's alternate-state color class (mode of the patch
        after the single click that flipped cell i, if any; else -1).
    used : int
        Action count spent on measurement.

    The caller supplies the candidate cells (usually from
    `action_profile["click"]` responsive entries). R17 will feed A and
    the inferred target vector b into GF(2) Gaussian elimination.
    """
    n = len(cells)
    A = np.zeros((n, n), dtype=np.uint8)
    toggled_classes: list[int] = [-1] * n
    used = 0
    obs = _reset_then_replay(env)
    used += 1 + len(_ACTIVE_PREFIX)
    base_frame = _get_frame(obs)
    base_classes = [
        _extract_cell_class(base_frame, x, y, patch_radius) for x, y in cells
    ]

    for j in range(n):
        if used >= budget:
            break
        obs = _reset_then_replay(env)
        used += 1 + len(_ACTIVE_PREFIX)
        cx, cy = cells[j]
        obs = _click(env, cx, cy)
        used += 1
        if obs.state.name == "GAME_OVER":
            continue
        frame_after = _get_frame(obs)
        for i in range(n):
            ix, iy = cells[i]
            cls_after = _extract_cell_class(frame_after, ix, iy, patch_radius)
            if cls_after != base_classes[i]:
                A[i, j] = 1
                if toggled_classes[i] == -1:
                    toggled_classes[i] = cls_after
    return A, base_classes, toggled_classes, used


def _gf2_solve(A: np.ndarray, b: np.ndarray) -> np.ndarray | None:
    """Solve A x = b over GF(2) via Gaussian elimination.

    Returns a particular solution x (uint8 n-vector) when one exists,
    else None. When the system is underdetermined, the returned x is
    the one produced by reduced row echelon; non-pivot variables are
    set to 0. R18 will enumerate the kernel to pick minimum-weight x.

    Parameters
    ----------
    A : (n, n) uint8
    b : (n,) uint8
    """
    n = A.shape[0]
    M = np.concatenate(
        [A.astype(np.uint8), b.reshape(-1, 1).astype(np.uint8)], axis=1
    )
    pivot_col = [-1] * n
    row = 0
    for col in range(n):
        pivot_row = -1
        for r in range(row, n):
            if M[r, col] == 1:
                pivot_row = r
                break
        if pivot_row == -1:
            continue
        if pivot_row != row:
            M[[row, pivot_row]] = M[[pivot_row, row]]
        for r in range(n):
            if r != row and M[r, col] == 1:
                M[r] ^= M[row]
        pivot_col[row] = col
        row += 1
    for r in range(row, n):
        if M[r, -1] == 1:
            return None
    x = np.zeros(n, dtype=np.uint8)
    for i, c in enumerate(pivot_col):
        if c != -1:
            x[c] = M[i, -1]
    return x


def _homogeneity_score(classes: list[int]) -> float:
    """Fraction of cells sharing the single most common class.

    Used as the goal-likelihood heuristic for predicted lights-out
    post-click states: 1.0 means all cells are the same color (likely
    'all solved' / 'all lit'); 1/n means every cell is different.
    """
    if not classes:
        return 0.0
    from collections import Counter
    counts = Counter(classes)
    return counts.most_common(1)[0][1] / len(classes)


def _rank_subsets_by_prediction(
    A: np.ndarray,
    base_classes: list[int],
    toggled_classes: list[int],
) -> list[tuple[np.ndarray, float]]:
    """Enumerate every x in {0,1}^n, predict the resulting cell-class
    vector using A, and rank by homogeneity.

    Returns (x, score) pairs sorted by descending score. For n ≤ 12
    this enumerates at most 4096 masks — cheap. Cells whose
    `toggled_classes[i] == -1` are treated as fixed at base (the
    measurement phase saw no click flip them, so they're indicator
    cells or unresponsive patches).
    """
    n = A.shape[0]
    results: list[tuple[np.ndarray, float]] = []
    for mask in range(1 << n):
        x = np.array([(mask >> i) & 1 for i in range(n)], dtype=np.uint8)
        flip = (A @ x) % 2
        predicted = [
            toggled_classes[i] if flip[i] and toggled_classes[i] != -1 else base_classes[i]
            for i in range(n)
        ]
        results.append((x, _homogeneity_score(predicted)))
    results.sort(key=lambda r: (-r[1], int(r[0].sum())))
    return results


def _plan_lights_out(env: Any, action_profile: dict, entity_map: dict, goal: dict, budget: int) -> tuple[int, int]:
    """Brute-force subset enumeration for lights-out style games.

    Round 14: FT09 trace revealed a 3x3 toggle grid at x=38,46,54 y=38,46,54
    (8-9 cells, each click diff=38). Within-cell commutativity of
    toggle clicks means ORDER doesn't matter — only which cells are
    clicked. That gives 2^n subsets to try, each costing reset + |subset|
    clicks.

    For n ≤ 10 cells and typical per-env budget 15000, we can exhaust
    the full subset space. We iterate subsets in ascending |subset| so
    level clears via minimum-click sequences are found fast.

    Round 16: before brute force, measure the per-cell toggle stencil
    (A[i][j] = 1 iff click j flips cell i) via `_measure_toggle_stencil`.
    The matrix is stored on `goal["stencil"]` so plan_synthesis and
    future GF(2) solvers (R17) can consume it. Measurement costs n+1
    resets + n clicks — cheap relative to the 2^n enumeration it
    precedes.

    Round 17: after measurement, run `_rank_subsets_by_prediction` to
    predict the post-click cell-class vector for every x in {0,1}^n
    and rank by homogeneity (fraction of cells sharing the most
    common color). Execute the top-K ranked subsets in the env and
    short-circuit on level advance. Only fall through to naive
    brute force if ranked trials exhaust without success.
    """
    import itertools
    global _LAST_WIN_SEQUENCE, _LAST_STENCIL
    _LAST_WIN_SEQUENCE = []
    used = 0
    clicks = action_profile.get("click", [])
    responsive = [c for c in clicks if c.get("diff_magnitude", 0) >= 10]
    if not responsive:
        return 0, used
    # Round 18: rank by diff_magnitude desc (tiebreak: distance to
    # center). Previously sort-by-distance picked up display / animation
    # cells that co-activate under every click (measured 91/100 stencil
    # density on FT09 L2 — buttons were elsewhere). Diff-magnitude
    # picks the strongest reactors first, which are more likely the
    # real toggle buttons.
    responsive.sort(
        key=lambda c: (
            -int(c.get("diff_magnitude", 0)),
            abs(c["x"] - 32) + abs(c["y"] - 32),
        )
    )
    cells = [(c["x"], c["y"]) for c in responsive[:10]]
    n = len(cells)

    # Round 18b: single-click sweep over ALL responsive cells (up to
    # 40) before expensive stencil measurement. For FT09 L2 the top-10
    # by diff_magnitude co-activate (stencil density = 100%), meaning
    # those cells are display / feedback regions, not buttons. The
    # real buttons may live lower in the responsive list. A cumulative
    # click sweep through 40 cells costs only ~50 actions and catches:
    #   (a) click-the-right-single-button games;
    #   (b) lights-out games where the first level's solution happens
    #       to be a contiguous subset of cells in the sweep order.
    obs = _reset_then_replay(env)
    used += 1 + len(_ACTIVE_PREFIX)
    base_levels_sweep = obs.levels_completed
    sweep_clicks: list[tuple] = []
    sweep_cells = [(c["x"], c["y"]) for c in responsive[:40]]
    for cx, cy in sweep_cells:
        if used >= budget:
            return base_levels_sweep, used
        obs = _click(env, cx, cy)
        used += 1
        sweep_clicks.append(("click", cx, cy))
        if obs.levels_completed > base_levels_sweep:
            _LAST_WIN_SEQUENCE = list(sweep_clicks)
            return int(obs.levels_completed), used
        if obs.state.name == "GAME_OVER":
            if used >= budget:
                return base_levels_sweep, used
            obs = _reset_then_replay(env)
            used += 1 + len(_ACTIVE_PREFIX)
            sweep_clicks = []

    # Round 16: measure the stencil before brute force.
    stencil_budget = min(budget // 10, 400)
    if stencil_budget > 0:
        A, base_cls, toggled_cls, m_used = _measure_toggle_stencil(
            env, cells, patch_radius=2, budget=stencil_budget,
        )
        used += m_used
        _LAST_STENCIL = {
            "cells": list(cells),
            "A": A,
            "base_classes": base_cls,
            "toggled_classes": toggled_cls,
        }
    else:
        A = None
        _LAST_STENCIL = None

    obs = _reset_then_replay(env)
    used += 1 + len(_ACTIVE_PREFIX)
    base_levels = obs.levels_completed

    # Round 17+18: predictive ranking with delta chaining. Enumerate
    # every subset virtually, rank by homogeneity, then traverse the
    # ranked list in the env via xor-deltas (click_toggle is commutative
    # and self-inverse in lights-out, so net-state = current_x and
    # trial-to-trial transitions cost only |x_next ⊕ x_prev| clicks).
    # This removes the per-trial reset_then_replay cost which, with a
    # long prefix (e.g., 374-click FT09 L1 winning sequence) dominates
    # the budget. Skipped when stencil measurement was skipped or
    # returned an all-zero matrix.
    if A is not None and int(A.sum()) > 0 and n <= 12:
        ranked = _rank_subsets_by_prediction(A, base_cls, toggled_cls)
        top_k = min(len(ranked), 1 << n)
        obs = _reset_then_replay(env)
        used += 1 + len(_ACTIVE_PREFIX)
        current_x = np.zeros(n, dtype=np.uint8)
        for x_vec, _score in ranked[:top_k]:
            if used >= budget:
                return base_levels, used
            if int(x_vec.sum()) == 0:
                continue
            delta = x_vec ^ current_x
            advanced = False
            game_over = False
            for j in range(n):
                if delta[j] == 0:
                    continue
                if used >= budget:
                    return base_levels, used
                cx, cy = cells[j]
                obs = _click(env, cx, cy)
                used += 1
                current_x[j] ^= 1
                if obs.levels_completed > base_levels:
                    _LAST_WIN_SEQUENCE = [
                        ("click", cells[k][0], cells[k][1])
                        for k in range(n) if int(current_x[k]) == 1
                    ]
                    return int(obs.levels_completed), used
                if obs.state.name == "GAME_OVER":
                    game_over = True
                    break
            if game_over:
                if used >= budget:
                    return base_levels, used
                obs = _reset_then_replay(env)
                used += 1 + len(_ACTIVE_PREFIX)
                current_x = np.zeros(n, dtype=np.uint8)
            if advanced:
                break

    for subset_size in range(1, n + 1):
        for combo in itertools.combinations(range(n), subset_size):
            if used >= budget:
                return base_levels, used
            obs = _reset_then_replay(env)
            used += 1 + len(_ACTIVE_PREFIX)
            for idx in combo:
                if used >= budget:
                    return base_levels, used
                cx, cy = cells[idx]
                obs = _click(env, cx, cy)
                used += 1
                if obs.levels_completed > base_levels:
                    _LAST_WIN_SEQUENCE = [("click", cells[i][0], cells[i][1]) for i in combo[:combo.index(idx) + 1]]
                    return int(obs.levels_completed), used
                if obs.state.name == "GAME_OVER":
                    break
    return base_levels, used


def _plan_click_then_move(env: Any, action_profile: dict, entity_map: dict, goal: dict, budget: int) -> tuple[int, int]:
    """Click a high-diff button then BFS movement.

    Round-13 plan for hybrids where a button press + player movement
    clears the level (CD82 pattern: clicking the top arrow at (37,4)
    advances game state, then left/right movement positions the
    player). HUD masking (round 12) is what makes this plan viable —
    without it every click looks responsive.

    Algorithm:
      1. Collect the top-K click probes by HUD-masked diff_magnitude
         (descending). Only keep those with diff ≥ 10.
      2. For each button: reset, click, then BFS 2-step movement
         (dir_actions × dir_actions) looking for a level advance.
      3. If none succeed, widen to 3-step movement.

    Works well when the game has 1-3 state-advancing buttons and a
    player that moves under directional actions.
    """
    used = 0
    clicks = action_profile.get("click", [])
    meaningful = [c for c in clicks if c.get("diff_magnitude", 0) >= 10]
    meaningful.sort(key=lambda c: -c["diff_magnitude"])
    meaningful = meaningful[:6]
    if not meaningful:
        return 0, used

    dir_actions = [a for a in action_profile["scalar"].keys() if 1 <= a <= 4]
    if not dir_actions:
        return 0, used

    obs = _reset_then_replay(env)
    used += 1
    base_levels = obs.levels_completed

    # Pass 1: each button alone + ≤ 2 movement steps.
    for c in meaningful:
        if used >= budget:
            break
        for d1 in dir_actions + [None]:
            if used >= budget:
                break
            for d2 in dir_actions + [None]:
                if used >= budget:
                    break
                obs = _reset_then_replay(env)
                used += 1
                obs = _click(env, c["x"], c["y"])
                used += 1
                if obs.levels_completed > base_levels:
                    return int(obs.levels_completed), used
                if obs.state.name == "GAME_OVER":
                    continue
                for d in (d1, d2):
                    if d is None or used >= budget:
                        continue
                    obs = _act(env, d)
                    used += 1
                    if obs.levels_completed > base_levels:
                        return int(obs.levels_completed), used
                    if obs.state.name == "GAME_OVER":
                        break

    # Pass 2: two-button sequences (click A → click B → movement).
    if used < budget:
        for i, a in enumerate(meaningful):
            if used >= budget:
                break
            for j, b in enumerate(meaningful):
                if i == j or used >= budget:
                    continue
                for d in dir_actions + [None]:
                    if used >= budget:
                        break
                    obs = _reset_then_replay(env)
                    used += 1
                    obs = _click(env, a["x"], a["y"])
                    used += 1
                    if obs.levels_completed > base_levels:
                        return int(obs.levels_completed), used
                    if obs.state.name == "GAME_OVER":
                        continue
                    obs = _click(env, b["x"], b["y"])
                    used += 1
                    if obs.levels_completed > base_levels:
                        return int(obs.levels_completed), used
                    if d is not None:
                        obs = _act(env, d)
                        used += 1
                        if obs.levels_completed > base_levels:
                            return int(obs.levels_completed), used
    return base_levels, used


PLAN_FNS = {
    "navigation": _plan_navigation,
    "merge": _plan_merge,
    "paint_fill": _plan_paint_fill,
    "toggle": _plan_toggle,
    "click_then_move": _plan_click_then_move,
    "lights_out": _plan_lights_out,
}


# ─── Phase 4+5: Plan Synthesis + Learning Loop ─────────────────────────


def strat_inferential_agent(env: Any, budget: int = 500000) -> tuple[int, str, int]:
    """Five-phase inferential agent.

    Runs Observation → Entity Detection → Goal Inference → Plan
    Synthesis per level, with learning-loop retries on plan failure.

    Round-15 addition: cumulative prefix chaining. `_reset(env)` on
    these environments goes back to LEVEL 1 START, not the current
    level. To make multi-level progression work, each plan that
    succeeds writes its action sequence into `_LAST_WIN_SEQUENCE`; the
    outer loop appends it to `_ACTIVE_PREFIX`. Every subsequent
    `_reset_then_replay(env)` call (used in place of `_reset` inside
    plans) then lands the env at the start of the current level,
    giving Phase-1 a fresh frame for the next level's observation.

    Returns (best_levels_cleared, label, actions_used). Label is
    "inferential_agent/<plan_kind>" on success or "" on no progress.
    """
    global _ACTIVE_PREFIX, _LAST_WIN_SEQUENCE
    _ACTIVE_PREFIX = []
    _LAST_WIN_SEQUENCE = []
    obs = _reset_then_replay(env)
    used = 1
    best = obs.levels_completed
    label = ""

    no_progress_streak = 0
    for level in range(1, 12):
        if used >= budget:
            break

        # Observation budget scales with remaining total budget so late
        # levels still get adequate probing.
        probe_budget = max(200, min(600, (budget - used) // 5))
        profile, p_used = observation_phase(env, stride=4, budget=probe_budget)
        used += p_used
        if used >= budget:
            break

        if profile["base_levels"] > best:
            best = profile["base_levels"]
            if not label:
                label = "inferential_agent/observed_clear"

        entity_map = entity_phase(profile["base_frame"], profile)
        goal = goal_phase(profile, entity_map)

        cleared_this_level = False
        attempted: set[str] = set()

        # Phase 4: try the inferred plan first; then try siblings.
        # Per-plan budget caps (round 7 — runtime fix):
        #   navigation  : 10_000 (BFS engine hits fast-bail when a level
        #                  is solved; unsolvable levels previously burned
        #                  the full 50 000 — 867 s for AR25 in round 6)
        #   toggle      : 15_000 (depth-4 click combinations)
        #   merge       : 12_000 (greedy midpoint loop; a few passes enough)
        #   paint_fill  : 12_000 (palette→targets→executor has few retries)
        # Round 19 bump: Sokoban-like games (navigation with multiple
        # merge_items = pushable blocks) need deeper BFS than simple
        # movement. Raise navigation cap to 30k when the signature
        # matches, else keep 10k so AR25-class games still fast-bail.
        sokoban_like = (
            goal.get("kind") == "navigation"
            and len(entity_map.get("merge_items", [])) >= 3
        )
        PLAN_BUDGET_CAP = {
            "navigation": 30_000 if sokoban_like else 10_000,
            "toggle": 15_000,
            "merge": 12_000,
            "paint_fill": 12_000,
            "click_then_move": 15_000,
            "lights_out": 20_000,
        }

        def _try_plan(kind: str) -> bool:
            nonlocal used, best, label, cleared_this_level
            global _ACTIVE_PREFIX, _LAST_WIN_SEQUENCE
            if kind in attempted or kind not in PLAN_FNS:
                return False
            plan_fn = PLAN_FNS[kind]
            cap = PLAN_BUDGET_CAP.get(kind, 10_000)
            remaining = min(budget - used, cap)
            if remaining <= 0:
                return False
            _LAST_WIN_SEQUENCE = []
            new_best, plan_used = plan_fn(env, profile, entity_map, goal, remaining)
            used += plan_used
            attempted.add(kind)
            if new_best > best:
                best = new_best
                label = f"inferential_agent/{kind}"
                cleared_this_level = True
                # Append winning actions to the prefix so future level
                # iterations resume from the cleared-level start.
                if _LAST_WIN_SEQUENCE:
                    _ACTIVE_PREFIX = list(_ACTIVE_PREFIX) + list(_LAST_WIN_SEQUENCE)
                return True
            return False

        # Round 1: inferred plan.
        _try_plan(goal["kind"])
        if not cleared_this_level:
            # Round 2: heuristic-ordered siblings.
            for alt in ("navigation", "lights_out", "click_then_move", "merge", "paint_fill", "toggle"):
                if cleared_this_level or used >= budget:
                    break
                _try_plan(alt)
        if not cleared_this_level and used < budget:
            # Phase 5: finer probe + retry (for sparse click games).
            probe_budget = max(150, min(500, (budget - used) // 6))
            profile, p_used = observation_phase(env, stride=4, budget=probe_budget)
            used += p_used
            entity_map = entity_phase(profile["base_frame"], profile)
            goal = goal_phase(profile, entity_map)
            attempted.clear()
            for alt in (goal["kind"], "navigation", "lights_out", "click_then_move", "merge", "paint_fill", "toggle"):
                if cleared_this_level or used >= budget:
                    break
                _try_plan(alt)

        if not cleared_this_level:
            no_progress_streak += 1
            if no_progress_streak >= 2:
                break
        else:
            no_progress_streak = 0

    return best, label, used
