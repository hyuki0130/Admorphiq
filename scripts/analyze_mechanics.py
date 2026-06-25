"""Deep mechanics analysis for unsolved games.

For each game:
1. Get initial frame and analyze structure
2. Try each action 3 times and record diffs
3. Infer game rules from diffs
"""

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

TARGET_GAMES = ["dc22", "re86", "sk48"]


def analyze_frame(frame: np.ndarray) -> dict:
    """Analyze frame structure."""
    if frame.ndim == 3:
        flat = frame[0]
        n_layers = frame.shape[0]
    else:
        flat = frame
        n_layers = 1

    colors, counts = np.unique(flat, return_counts=True)
    total = flat.size
    color_info = {}
    for c, cnt in zip(colors, counts):
        pct = cnt / total * 100
        color_info[int(c)] = {"count": int(cnt), "pct": round(pct, 1)}

    # Find connected components for each color
    bg_color = int(colors[counts.argmax()])

    # Detect rectangular regions
    regions = []
    for c in colors:
        if c == bg_color:
            continue
        mask = flat == c
        ys, xs = np.where(mask)
        if len(ys) == 0:
            continue
        regions.append({
            "color": int(c),
            "count": int(len(ys)),
            "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
            "center": [round(float(xs.mean()), 1), round(float(ys.mean()), 1)],
        })

    return {
        "shape": list(flat.shape),
        "n_layers": n_layers,
        "bg_color": bg_color,
        "n_colors": len(colors),
        "colors": color_info,
        "regions": sorted(regions, key=lambda r: r["count"], reverse=True),
    }


def analyze_diff(before: np.ndarray, after: np.ndarray) -> dict:
    """Analyze what changed between two frames."""
    if before.ndim == 3:
        before = before[0]
    if after.ndim == 3:
        after = after[0]

    diff_mask = before != after
    n_changed = int(diff_mask.sum())

    if n_changed == 0:
        return {"changed": 0, "movements": [], "appears": [], "disappears": []}

    ys, xs = np.where(diff_mask)

    # What colors appeared/disappeared
    before_colors = set(before[diff_mask].tolist())
    after_colors = set(after[diff_mask].tolist())

    # Per-color movement analysis
    movements = []
    for color in range(16):
        before_mask = before == color
        after_mask = after == color
        b_count = int(before_mask.sum())
        a_count = int(after_mask.sum())

        if b_count > 0 and a_count > 0:
            b_center = np.array(np.where(before_mask)).mean(axis=1)
            a_center = np.array(np.where(after_mask)).mean(axis=1)
            dy = float(a_center[0] - b_center[0])
            dx = float(a_center[1] - b_center[1])
            if abs(dy) > 0.3 or abs(dx) > 0.3:
                movements.append({
                    "color": color,
                    "dy": round(dy, 2),
                    "dx": round(dx, 2),
                    "before_count": b_count,
                    "after_count": a_count,
                })

    # Detect appearing/disappearing pixels
    appears = []
    disappears = []
    for color in after_colors - before_colors:
        mask = (after == color) & diff_mask
        if mask.any():
            appears.append({"color": int(color), "count": int(mask.sum())})
    for color in before_colors - after_colors:
        mask = (before == color) & diff_mask
        if mask.any():
            disappears.append({"color": int(color), "count": int(mask.sum())})

    return {
        "changed": n_changed,
        "change_bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
        "movements": movements,
        "appears": appears,
        "disappears": disappears,
        "before_colors_at_diff": sorted(before_colors),
        "after_colors_at_diff": sorted(after_colors),
    }


def analyze_game(arcade, game_id_full):
    env = arcade.make(game_id_full)
    if env is None:
        print("  ERROR: make() returned None")
        return

    obs = env.observation_space
    if obs is None:
        print("  ERROR: no observation")
        return

    # Initial frame analysis
    frame0 = np.array(obs.frame)
    info = analyze_frame(frame0)
    available = list(obs.available_actions)

    print(f"  Initial frame: {info['shape']}, {info['n_layers']} layers")
    print(f"  Background: color {info['bg_color']}")
    print(f"  Colors ({info['n_colors']}): ", end="")
    for c, ci in sorted(info['colors'].items()):
        print(f"c{c}={ci['pct']}% ", end="")
    print()
    print(f"  Non-bg regions ({len(info['regions'])}):")
    for r in info['regions'][:10]:
        print(f"    color={r['color']}, pixels={r['count']}, bbox={r['bbox']}, center={r['center']}")
    print(f"  Available actions: {available}")
    print(f"  Win levels: {obs.win_levels}")

    # Try each action 3 times
    print("\n  === Action Effects ===")
    for action_id in available:
        print(f"\n  ACTION{action_id}:")
        for trial in range(3):
            try:
                obs = env.step(GameAction.RESET)
                if obs is None:
                    continue
                frame_before = np.array(obs.frame)

                action = GameAction.from_id(action_id)
                if action_id == 6:
                    # Try different coords
                    coords_list = [(32, 32), (16, 16), (48, 48)]
                    cx, cy = coords_list[trial]
                    action.set_data({"x": cx, "y": cy})
                    obs = env.step(action, data={"x": cx, "y": cy})
                    coord_str = f" at ({cx},{cy})"
                else:
                    obs = env.step(action)
                    coord_str = ""

                if obs is None:
                    print(f"    Trial {trial+1}{coord_str}: obs=None")
                    continue

                frame_after = np.array(obs.frame)
                diff = analyze_diff(frame_before, frame_after)

                if diff["changed"] == 0:
                    print(f"    Trial {trial+1}{coord_str}: NO CHANGE")
                else:
                    print(f"    Trial {trial+1}{coord_str}: {diff['changed']} pixels changed", end="")
                    if diff.get("change_bbox"):
                        print(f", bbox={diff['change_bbox']}", end="")
                    print()
                    for m in diff["movements"]:
                        print(f"      color {m['color']} moved dy={m['dy']}, dx={m['dx']} (n={m['before_count']}->{m['after_count']})")
                    for a in diff.get("appears", []):
                        print(f"      APPEARED: color {a['color']} ({a['count']} px)")
                    for d in diff.get("disappears", []):
                        print(f"      DISAPPEARED: color {d['color']} ({d['count']} px)")

                    # Also try doing the action again to see cumulative effect
                    if trial == 0 and action_id != 6:
                        frame_mid = frame_after.copy()
                        obs2 = env.step(GameAction.from_id(action_id))
                        if obs2 is not None:
                            frame_after2 = np.array(obs2.frame)
                            diff2 = analyze_diff(frame_mid, frame_after2)
                            if diff2["changed"] > 0:
                                print(f"      2nd press: {diff2['changed']} more pixels changed")
                                for m in diff2["movements"]:
                                    print(f"        color {m['color']} moved dy={m['dy']}, dx={m['dx']}")
                            else:
                                print("      2nd press: NO additional change")

                # Check state after action
                print(f"      State: {obs.state.name}, levels={obs.levels_completed}/{obs.win_levels}")

            except Exception as e:
                print(f"    Trial {trial+1}: ERROR {e}")


def main():
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()

    for env_info in envs:
        game_prefix = env_info.game_id.split("-")[0]
        if game_prefix in TARGET_GAMES:
            print(f"\n{'='*60}")
            print(f"GAME: {env_info.game_id} ({env_info.title})")
            print(f"{'='*60}")
            analyze_game(arcade, env_info.game_id)


if __name__ == "__main__":
    main()
