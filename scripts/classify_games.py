"""Classify all 25 ARC-AGI-3 games by type (movement, click, transform, hybrid, unknown)."""

import sys
import json
import time
import traceback

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction, GameState


def detect_movement(frame_before, frame_after):
    """Detect per-color centroid shifts between two frames.

    Returns dict of {color: {delta_y, delta_x}} for colors that moved.
    """
    movements = {}
    for color in range(1, 16):  # skip 0 (background)
        before_pos = np.argwhere(frame_before == color)
        after_pos = np.argwhere(frame_after == color)

        if len(before_pos) > 0 and len(after_pos) > 0:
            before_center = before_pos.mean(axis=0)
            after_center = after_pos.mean(axis=0)
            delta = after_center - before_center
            if np.any(np.abs(delta) > 0.5):
                movements[int(color)] = {
                    "delta_y": round(float(delta[0]), 2),
                    "delta_x": round(float(delta[1]), 2),
                }
    return movements


def detect_direction(delta_y, delta_x):
    """Convert delta to a direction label."""
    if abs(delta_y) > abs(delta_x):
        return "UP" if delta_y < 0 else "DOWN"
    elif abs(delta_x) > abs(delta_y):
        return "LEFT" if delta_x < 0 else "RIGHT"
    return "DIAG"


def analyze_game(arcade, game_id):
    """Analyze one game: initial state + action effects."""
    env = arcade.make(game_id)
    obs = env.observation_space

    frame_raw = np.array(obs.frame)
    initial_layer0 = np.array(obs.frame[0], dtype=np.int32)

    info = {
        "game_id": game_id,
        "num_layers": frame_raw.shape[0],
        "frame_shape": list(frame_raw.shape),
        "available_actions": sorted(obs.available_actions),
        "win_levels": obs.win_levels,
        "unique_colors": np.unique(initial_layer0).tolist(),
        "color_counts": {},
    }

    # Color distribution
    for c in info["unique_colors"]:
        info["color_counts"][int(c)] = int(np.sum(initial_layer0 == c))

    # Test each available action
    action_effects = {}
    for action_id in obs.available_actions:
        trials = []
        for trial_idx in range(3):
            # Reset to clean state
            obs_reset = env.step(GameAction.RESET)
            frame_before = np.array(obs_reset.frame[0], dtype=np.int32)

            if action_id == 6:
                # ACTION6: test different coordinates
                coords = [(32, 32), (16, 16), (48, 48)]
                cx, cy = coords[trial_idx]
                action = GameAction.ACTION6
                action.set_data({"x": cx, "y": cy})
                obs_after = env.step(action, data={"x": cx, "y": cy})
            else:
                action = GameAction.from_id(action_id)
                obs_after = env.step(action)

            frame_after = np.array(obs_after.frame[0], dtype=np.int32)

            diff = frame_after - frame_before
            changed_pixels = int(np.count_nonzero(diff))
            movement = detect_movement(frame_before, frame_after)

            trial_result = {
                "changed_pixels": changed_pixels,
                "movement": movement,
                "state_after": obs_after.state.name,
            }
            if action_id == 6:
                trial_result["coord"] = (cx, cy)

            trials.append(trial_result)

        action_effects[action_id] = trials

    # Classify
    game_type, details = classify_game_type(info, action_effects)
    info["type"] = game_type
    info["details"] = details
    info["action_effects_summary"] = summarize_effects(action_effects)

    return info


def summarize_effects(action_effects):
    """Create a compact summary of action effects."""
    summary = {}
    for action_id, trials in action_effects.items():
        avg_changed = np.mean([t["changed_pixels"] for t in trials])
        all_movements = {}
        for t in trials:
            for color, mv in t["movement"].items():
                all_movements.setdefault(color, []).append(mv)

        movement_summary = {}
        for color, mvs in all_movements.items():
            avg_dy = np.mean([m["delta_y"] for m in mvs])
            avg_dx = np.mean([m["delta_x"] for m in mvs])
            direction = detect_direction(avg_dy, avg_dx)
            movement_summary[color] = {
                "avg_delta_y": round(float(avg_dy), 2),
                "avg_delta_x": round(float(avg_dx), 2),
                "direction": direction,
            }

        summary[action_id] = {
            "avg_changed_pixels": round(float(avg_changed), 1),
            "movements": movement_summary,
        }
    return summary


def classify_game_type(info, action_effects):
    """Classify game into movement/click/transform/hybrid/unknown."""
    has_movement = False
    has_click = False
    has_transform = False
    movement_details = {}  # action_id -> direction mapping
    player_colors = set()

    for action_id, trials in action_effects.items():
        if action_id == 6:
            # Check if ACTION6 causes changes
            for t in trials:
                if t["changed_pixels"] > 0:
                    has_click = True
            continue

        # For ACTION1-5, ACTION7: check movement
        consistent_movements = {}
        for t in trials:
            if t["changed_pixels"] > 0 and t["movement"]:
                for color, mv in t["movement"].items():
                    direction = detect_direction(mv["delta_y"], mv["delta_x"])
                    consistent_movements.setdefault(color, []).append(direction)

        for color, directions in consistent_movements.items():
            # If all trials show the same direction for this color, it's movement
            if len(set(directions)) == 1 and len(directions) >= 2:
                has_movement = True
                player_colors.add(color)
                movement_details[action_id] = {
                    "direction": directions[0],
                    "player_color": color,
                }
            elif len(directions) > 0:
                # Some movement but inconsistent
                has_movement = True
                player_colors.add(color)
                movement_details[action_id] = {
                    "direction": directions[0],
                    "player_color": color,
                    "inconsistent": True,
                }

        # Check if action causes changes but no clear movement (transform)
        if not consistent_movements:
            any_change = any(t["changed_pixels"] > 0 for t in trials)
            if any_change:
                has_transform = True

    details = {
        "movement_mapping": movement_details,
        "player_colors": sorted(player_colors),
    }

    if has_movement and has_click:
        return "hybrid", details
    elif has_movement:
        return "movement", details
    elif has_click:
        return "click", details
    elif has_transform:
        return "transform", details
    else:
        return "unknown", details


def main():
    print("=" * 70)
    print("  ARC-AGI-3 Game Classifier — Analyzing all 25 games")
    print("=" * 70)

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()
    print(f"\n  Found {len(envs)} games\n")

    results = []
    for i, env_info in enumerate(envs):
        gid = env_info.game_id
        title = env_info.title or ""
        tags = env_info.tags or []
        print(f"[{i+1:2d}/{len(envs)}] {gid} ({title}) tags={tags}")

        t0 = time.time()
        try:
            result = analyze_game(arcade, gid)
            result["title"] = title
            result["tags"] = tags
            result["baseline_actions"] = env_info.baseline_actions
            results.append(result)
            elapsed = time.time() - t0
            print(f"  -> Type: {result['type']}, Layers: {result['num_layers']}, "
                  f"Actions: {result['available_actions']}, Win: {result['win_levels']}, "
                  f"Colors: {result['unique_colors']} ({elapsed:.1f}s)")
            if result["details"].get("movement_mapping"):
                for aid, md in result["details"]["movement_mapping"].items():
                    print(f"     ACTION{aid} -> {md['direction']} (player_color={md['player_color']})")
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  -> ERROR: {e} ({elapsed:.1f}s)")
            traceback.print_exc()
            results.append({
                "game_id": gid, "title": title, "tags": tags,
                "type": "error", "error": str(e),
            })

    # Summary table
    print("\n" + "=" * 70)
    print("  CLASSIFICATION SUMMARY")
    print("=" * 70)

    # Group by type
    by_type = {}
    for r in results:
        t = r["type"]
        by_type.setdefault(t, []).append(r)

    for game_type in ["movement", "click", "transform", "hybrid", "unknown", "error"]:
        games = by_type.get(game_type, [])
        if not games:
            continue
        print(f"\n  {game_type.upper()} ({len(games)} games):")
        print(f"  {'Game ID':<25} {'Title':<6} {'Layers':<7} {'Actions':<18} {'Win':<5} {'Colors':<30} {'Tags'}")
        print(f"  {'-'*25} {'-'*6} {'-'*7} {'-'*18} {'-'*5} {'-'*30} {'-'*15}")
        for r in games:
            if r["type"] == "error":
                print(f"  {r['game_id']:<25} {r.get('title',''):<6} ERROR: {r['error']}")
                continue
            actions_str = str(r["available_actions"])
            colors_str = str(r["unique_colors"])
            tags_str = str(r.get("tags", []))
            print(f"  {r['game_id']:<25} {r.get('title',''):<6} {r['num_layers']:<7} {actions_str:<18} {r['win_levels']:<5} {colors_str:<30} {tags_str}")

        # Movement details
        if game_type in ("movement", "hybrid"):
            for r in games:
                if r.get("details", {}).get("movement_mapping"):
                    print(f"\n    {r['game_id']} movement mapping:")
                    for aid, md in r["details"]["movement_mapping"].items():
                        inconsistent = " (inconsistent)" if md.get("inconsistent") else ""
                        print(f"      ACTION{aid} -> {md['direction']} (player_color={md['player_color']}){inconsistent}")
                    if r["details"].get("player_colors"):
                        print(f"      Player colors: {r['details']['player_colors']}")

    # Action effects details
    print("\n" + "=" * 70)
    print("  ACTION EFFECTS DETAIL")
    print("=" * 70)
    for r in results:
        if "action_effects_summary" not in r:
            continue
        print(f"\n  {r['game_id']} ({r.get('title','')}) [{r['type']}]:")
        for aid, eff in r["action_effects_summary"].items():
            mv_str = ""
            if eff["movements"]:
                parts = []
                for c, mv in eff["movements"].items():
                    parts.append(f"color{c}:{mv['direction']}(dy={mv['avg_delta_y']},dx={mv['avg_delta_x']})")
                mv_str = " | " + ", ".join(parts)
            print(f"    ACTION{aid}: avg_changed={eff['avg_changed_pixels']}{mv_str}")

    # Save JSON
    output_path = "scripts/classify_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to {output_path}")


if __name__ == "__main__":
    main()
