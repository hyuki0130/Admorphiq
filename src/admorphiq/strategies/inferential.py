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

from collections import deque
from typing import Any

import numpy as np

from arcengine import GameAction


# ----- Low-level env helpers (duplicated from agent_ensemble to keep
#       this module free of cyclic imports during test discovery). --------

def _get_frame(obs: Any) -> np.ndarray:
    return np.array(obs.frame[0], dtype=np.int32)


def _reset(env: Any) -> Any:
    return env.step(GameAction.RESET)


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
      }

    ScalarProfile and ClickProfile carry:
      diff_magnitude, bbox, centroid, region_kind, did_transition.
    TransitionRecord carries (frame_before, frame_after, action).
    """
    used = 0
    obs = _reset(env)
    used += 1
    base_frame = _get_frame(obs)
    avail = sorted(int(a) for a in obs.available_actions if int(a) != 0)
    base_levels = obs.levels_completed

    total_pixels = base_frame.size
    scalar: dict[int, dict] = {}
    click_probes: list[dict] = []
    transitions: list[dict] = []

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
        obs = _reset(env)
        used += 1
        f0 = _get_frame(obs)
        obs = _act(env, aid)
        used += 1
        f1 = _get_frame(obs)
        mask = (f0 != f1)
        bbox, centroid = _bbox_and_centroid(mask)
        did_trans = obs.levels_completed > base_levels
        scalar[aid] = {
            "aid": aid,
            "diff_magnitude": int(mask.sum()),
            "bbox": bbox,
            "centroid": centroid,
            "region_kind": _classify_region(mask, total_pixels),
            "did_transition": did_trans,
            # Save both frames so Phase 2 can match clusters across the
            # probe — needed to identify the player as "cluster whose
            # centroid shifted between f0 and f1", not just "centroid of
            # the diff_mask" (which lands between old and new position).
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
            obs = _reset(env)
            used += 1
            f0 = _get_frame(obs)
            obs = _click(env, x, y)
            used += 1
            f1 = _get_frame(obs)
            mask = (f0 != f1)
            bbox, centroid = _bbox_and_centroid(mask)
            did_trans = obs.levels_completed > base_levels
            click_probes.append({
                "x": x,
                "y": y,
                "diff_magnitude": int(mask.sum()),
                "bbox": bbox,
                "centroid": centroid,
                "region_kind": _classify_region(mask, total_pixels),
                "did_transition": did_trans,
            })
            if did_trans:
                _record_transition(f0, f1, {"kind": "click", "x": x, "y": y})

    return ({
        "base_levels": int(base_levels),
        "base_frame": base_frame,
        "avail": avail,
        "scalar": scalar,
        "click": click_probes,
        "observed_transitions": transitions,
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

    # Merge items: clusters whose color appears ≥ 2 times.
    color_counts: dict[int, int] = {}
    for c in clusters:
        color_counts[c["color"]] = color_counts.get(c["color"], 0) + 1
    for c in clusters:
        if color_counts[c["color"]] >= 2 and c["size"] < 200:
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
    """Delegate movement-game solving to the proven generic BFS.

    `strat_bfs_state_space` (in `agent_ensemble`) is already a tuned
    reset-replay BFS that clears M0R0 / AR25 L1-L2 in ~2000 actions.
    Rather than re-implement BFS in the plan layer (which round-6
    iterations 4-7 showed is error-prone), delegate here. The
    InferentialAgent's job is to DECIDE this is a navigation game;
    the BFS engine executes.
    """
    from ..agent_ensemble import strat_bfs_state_space
    best, _label, used = strat_bfs_state_space(env, budget)
    return best, used


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

    obs = _reset(env)
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
    obs = _reset(env)
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
        obs = _reset(env)
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

    obs = _reset(env)
    used += 1
    base_levels = obs.levels_completed

    def _try(seq: list[tuple[int, int]]) -> int:
        nonlocal used
        if used >= budget:
            return base_levels
        obs_local = _reset(env)
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


PLAN_FNS = {
    "navigation": _plan_navigation,
    "merge": _plan_merge,
    "paint_fill": _plan_paint_fill,
    "toggle": _plan_toggle,
}


# ─── Phase 4+5: Plan Synthesis + Learning Loop ─────────────────────────


def strat_inferential_agent(env: Any, budget: int = 500000) -> tuple[int, str, int]:
    """Five-phase inferential agent.

    Runs Observation → Entity Detection → Goal Inference → Plan
    Synthesis per level, with learning-loop retries on plan failure.
    Multi-level games rely on the env's own state progression: once a
    plan clears a level, the env advances, and subsequent Phase-1
    observations run against the new level's frame.

    Returns (best_levels_cleared, label, actions_used). Label is
    "inferential_agent/<plan_kind>" on success or "" on no progress.
    """
    obs = _reset(env)
    used = 1
    best = obs.levels_completed
    label = ""

    no_progress_streak = 0
    for level in range(1, 12):
        if used >= budget:
            break

        # Observation budget scales with remaining total budget so late
        # levels still get adequate probing.
        probe_budget = max(150, min(400, (budget - used) // 6))
        profile, p_used = observation_phase(env, stride=8, budget=probe_budget)
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
        PLAN_BUDGET_CAP = {
            "navigation": 10_000,
            "toggle": 15_000,
            "merge": 12_000,
            "paint_fill": 12_000,
        }

        def _try_plan(kind: str) -> bool:
            nonlocal used, best, label, cleared_this_level
            if kind in attempted or kind not in PLAN_FNS:
                return False
            plan_fn = PLAN_FNS[kind]
            cap = PLAN_BUDGET_CAP.get(kind, 10_000)
            remaining = min(budget - used, cap)
            if remaining <= 0:
                return False
            new_best, plan_used = plan_fn(env, profile, entity_map, goal, remaining)
            used += plan_used
            attempted.add(kind)
            if new_best > best:
                best = new_best
                label = f"inferential_agent/{kind}"
                cleared_this_level = True
                return True
            return False

        # Round 1: inferred plan.
        _try_plan(goal["kind"])
        if not cleared_this_level:
            # Round 2: heuristic-ordered siblings.
            for alt in ("navigation", "merge", "paint_fill", "toggle"):
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
            for alt in (goal["kind"], "navigation", "merge", "paint_fill", "toggle"):
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
