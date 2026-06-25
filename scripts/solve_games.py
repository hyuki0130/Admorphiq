"""Frame-diff based game solver for ARC-AGI-3.

Multi-strategy solver. Each strategy runs independently with its own budget.
Strategies are run sequentially, stopping early when a level is cleared.
"""

import itertools
import json
import time
import traceback
from pathlib import Path

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

CLASSIFY_PATH = Path(__file__).parent / "classify_results.json"


def load_classify_results():
    if CLASSIFY_PATH.exists():
        with open(CLASSIFY_PATH) as f:
            return {g["game_id"]: g for g in json.load(f)}
    return {}


def get_frame(obs):
    return np.array(obs.frame[0], dtype=np.int32)


def frame_diff(f1, f2):
    return int(np.count_nonzero(f1 - f2))


def rare_colors(frame, max_count=500):
    unique, counts = np.unique(frame, return_counts=True)
    return [(int(c), int(n)) for n, c in sorted(zip(counts, unique)) if c != 0 and n <= max_count]


def click(env, x, y):
    a6 = GameAction.ACTION6
    a6.set_data({"x": x, "y": y})
    return env.step(a6, data={"x": x, "y": y})


def act(env, aid):
    return env.step(GameAction.from_id(aid))


def reset(env):
    return env.step(GameAction.RESET)


# ─── Strategy functions ──────────────────────────────────────────────
# Each returns (best_levels, strategy_name, actions_used)

def strat_sustained(env, aid, steps=80):
    """Sustained single direction."""
    obs = reset(env)
    used = 1
    best = 0
    name = ""
    for s in range(steps):
        obs = act(env, aid)
        used += 1
        if obs.levels_completed > best:
            best = obs.levels_completed
            name = f"sustained_A{aid}"
        if obs.state.name in ("WIN", "GAME_OVER"):
            break
    return best, name, used


def strat_zigzag(env, a1, a2, length, cycles=25):
    """Zigzag between two actions."""
    obs = reset(env)
    used = 1
    best = 0
    name = ""
    for _ in range(cycles):
        done = False
        for _ in range(length):
            obs = act(env, a1)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"zig{length}_A{a1}A{a2}"
            if obs.state.name in ("WIN", "GAME_OVER"):
                done = True
                break
        if done:
            break
        for _ in range(length):
            obs = act(env, a2)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"zig{length}_A{a1}A{a2}"
            if obs.state.name in ("WIN", "GAME_OVER"):
                done = True
                break
        if done:
            break
    return best, name, used


def strat_click_rare(env, budget=300):
    """Click on every pixel of rare colors."""
    obs = reset(env)
    used = 1
    best = 0
    name = ""
    frame = get_frame(obs)
    unique, counts = np.unique(frame, return_counts=True)
    for cnt, color in sorted(zip(counts.tolist(), unique.tolist())):
        if color == 0 or cnt > 500:
            continue
        positions = np.argwhere(frame == color)
        for pos in positions:
            if used >= budget:
                return best, name, used
            cy, cx = int(pos[0]), int(pos[1])
            obs = click(env, cx, cy)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"click_c{color}_({cy},{cx})"
            if obs.state.name == "GAME_OVER":
                obs = reset(env)
                used += 1
                frame = get_frame(obs)
            if obs.state.name == "WIN":
                return best, name, used
    return best, name, used


def strat_raster(env, step_size=1, budget=4100):
    """Click every pixel in raster order."""
    obs = reset(env)
    used = 1
    best = 0
    name = ""
    for y in range(0, 64, step_size):
        for x in range(0, 64, step_size):
            if used >= budget:
                return best, name, used
            obs = click(env, x, y)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"raster_({y},{x})"
            if obs.state.name == "GAME_OVER":
                obs = reset(env)
                used += 1
            if obs.state.name == "WIN":
                return best, name, used
    return best, name, used


def strat_move_click(env, aid, budget=200):
    """Move then click on rarest color, alternating."""
    obs = reset(env)
    used = 1
    best = 0
    name = ""
    for s in range(budget // 3):
        if used >= budget or obs.state.name == "WIN":
            break
        if obs.state.name == "GAME_OVER":
            obs = reset(env)
            used += 1
            continue
        # Move
        obs = act(env, aid)
        used += 1
        if obs.levels_completed > best:
            best = obs.levels_completed
            name = f"moveclick_A{aid}"

        if obs.state.name in ("WIN", "GAME_OVER"):
            continue

        # Click on rarest color
        frame = get_frame(obs)
        rc = rare_colors(frame, max_count=300)
        for color, cnt in rc[:1]:
            positions = np.argwhere(frame == color)
            if len(positions) > 0:
                center = positions.mean(axis=0)
                cy = max(0, min(63, int(round(center[0]))))
                cx = max(0, min(63, int(round(center[1]))))
                obs = click(env, cx, cy)
                used += 1
                if obs.levels_completed > best:
                    best = obs.levels_completed
                    name = f"moveclick_A{aid}_c{color}"
                break
    return best, name, used


def strat_navigate(env, player_color, dir_to_act, target_color, budget=105):
    """Navigate player towards target color."""
    obs = reset(env)
    used = 1
    best = 0
    name = ""
    for step in range(budget - 1):
        if obs.state.name in ("WIN", "GAME_OVER"):
            break
        frame = get_frame(obs)
        pp = np.argwhere(frame == player_color)
        tp = np.argwhere(frame == target_color)

        if len(pp) == 0 or len(tp) == 0:
            aids = list(dir_to_act.values())
            if aids:
                obs = act(env, aids[step % len(aids)])
                used += 1
            continue

        pc = pp.mean(axis=0)
        tc = tp.mean(axis=0)
        dy, dx = tc[0] - pc[0], tc[1] - pc[1]

        aid = None
        if abs(dy) >= abs(dx):
            if dy < 0:
                aid = dir_to_act.get("UP")
            else:
                aid = dir_to_act.get("DOWN")
        if aid is None:
            if dx < 0:
                aid = dir_to_act.get("LEFT")
            else:
                aid = dir_to_act.get("RIGHT")
        if aid is None:
            aids = list(dir_to_act.values())
            aid = aids[step % len(aids)] if aids else None

        if aid is not None:
            obs = act(env, aid)
            used += 1
            if obs.levels_completed > best:
                best = obs.levels_completed
                name = f"nav_c{target_color}"
    return best, name, used


# ─── Main solver ─────────────────────────────────────────────────────

def solve_game(arcade, game_id, classify_info, total_budget=5000):
    """Solve a single game by trying multiple strategies."""
    env = arcade.make(game_id)
    if env is None:
        return {"game_id": game_id, "error": "make() returned None",
                "levels_completed": 0, "win_levels": 0, "cleared": False}

    obs = env.observation_space
    if obs is None:
        return {"game_id": game_id, "error": "No observation",
                "levels_completed": 0, "win_levels": 0, "cleared": False}

    ci = classify_info or {}
    avail = sorted(obs.available_actions)
    win_levels = obs.win_levels
    dir_actions = [a for a in avail if a not in (6, 7)]
    has_click = 6 in avail

    dmap = ci.get("details", {}).get("movement_mapping", {})
    pc_list = ci.get("details", {}).get("player_colors", [])
    player_color = pc_list[0] if pc_list else None
    dir_to_act = {}
    for aid_s, info in dmap.items():
        dir_to_act[info["direction"]] = int(aid_s)

    frame0 = get_frame(obs)
    target_colors = [c for c in np.unique(frame0).tolist() if c != 0 and c != player_color]

    best_levels = 0
    best_strategy = ""
    total_actions = 0

    def try_strat(fn, *args, **kwargs):
        nonlocal best_levels, best_strategy, total_actions
        if total_actions >= total_budget:
            return False
        levels, name, used = fn(env, *args, **kwargs)
        total_actions += used
        if levels > best_levels:
            best_levels = levels
            best_strategy = name
        return levels > 0

    # === Priority 1: Sustained directions ===
    for aid in dir_actions:
        if try_strat(strat_sustained, aid, steps=80):
            break

    # === Priority 2: Zigzag pairs ===
    if best_levels == 0 and len(dir_actions) >= 2:
        for length in [1, 2, 3, 5, 7, 10]:
            if best_levels > 0:
                break
            for a1, a2 in itertools.permutations(dir_actions, 2):
                if total_actions >= total_budget or best_levels > 0:
                    break
                try_strat(strat_zigzag, a1, a2, length, cycles=25)

    # === Priority 3: Click on rare colors ===
    if best_levels == 0 and has_click:
        try_strat(strat_click_rare, budget=min(500, total_budget - total_actions))

    # === Priority 4: Move + click combos ===
    if best_levels == 0 and has_click and dir_actions:
        for aid in dir_actions:
            if total_actions >= total_budget or best_levels > 0:
                break
            try_strat(strat_move_click, aid, budget=min(200, total_budget - total_actions))

    # === Priority 5: Navigate to colors ===
    if best_levels == 0 and dir_to_act and player_color is not None:
        for tc in target_colors:
            if total_actions >= total_budget or best_levels > 0:
                break
            try_strat(strat_navigate, player_color, dir_to_act, tc,
                      budget=min(105, total_budget - total_actions))

    # === Priority 6: Raster scan ===
    if best_levels == 0 and has_click:
        try_strat(strat_raster, step_size=1,
                  budget=min(4200, total_budget - total_actions))

    return {
        "game_id": game_id,
        "levels_completed": best_levels,
        "win_levels": win_levels,
        "actions": total_actions,
        "strategy": best_strategy,
        "cleared": best_levels > 0,
    }


def main():
    print("=" * 70)
    print("  ARC-AGI-3 Frame-Diff Solver v3 — All 25 Games")
    print("=" * 70)

    classify_data = load_classify_results()
    print(f"  Classifications: {len(classify_data)}")

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()
    print(f"  Games: {len(envs)}\n")

    results = []
    total_start = time.time()

    for i, env_info in enumerate(envs):
        gid = env_info.game_id
        title = env_info.title or ""
        ci = classify_data.get(gid)
        gtype = ci["type"] if ci else "?"

        print(f"[{i+1:2d}/{len(envs)}] {gid} ({title}) type={gtype} ... ", end="", flush=True)

        try:
            result = solve_game(arcade, gid, ci, total_budget=5000)
            result["title"] = title
            result["game_type"] = gtype
            results.append(result)
            lvl = f"{result['levels_completed']}/{result['win_levels']}"
            status = "CLEARED!" if result["cleared"] else "no clear"
            strat = result.get("strategy", "")
            print(f"{lvl} lvl, {result['actions']} act [{status}] {strat}")
        except Exception as e:
            print(f"ERROR: {e}")
            traceback.print_exc()
            results.append({
                "game_id": gid, "title": title, "game_type": gtype,
                "error": str(e), "levels_completed": 0, "win_levels": 0, "cleared": False,
            })

    total_elapsed = time.time() - total_start

    # ─── Summary ─────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)

    print(f"\n  {'Game ID':<25} {'Title':<6} {'Type':<10} {'Levels':<10} {'Actions':<8} {'Strategy'}")
    print(f"  {'-'*25} {'-'*6} {'-'*10} {'-'*10} {'-'*8} {'-'*30}")

    cleared_games = []
    for r in results:
        if "error" in r:
            print(f"  {r['game_id']:<25} {r.get('title',''):<6} {r.get('game_type','?'):<10} {'ERR':<10}")
            continue
        lvl = f"{r['levels_completed']}/{r['win_levels']}"
        strat = r.get("strategy", "")[:30]
        print(f"  {r['game_id']:<25} {r.get('title',''):<6} {r.get('game_type',''):<10} {lvl:<10} {r['actions']:<8} {strat}")
        if r["cleared"]:
            cleared_games.append(r)

    print("\n  --- By Game Type ---")
    by_type = {}
    for r in results:
        t = r.get("game_type", "?")
        by_type.setdefault(t, []).append(r)
    for gtype in ["movement", "click", "hybrid", "transform", "unknown"]:
        games = by_type.get(gtype, [])
        if not games:
            continue
        total = len(games)
        cleared = sum(1 for g in games if g.get("cleared"))
        total_levels = sum(g.get("levels_completed", 0) for g in games)
        total_win = sum(g.get("win_levels", 0) for g in games)
        print(f"  {gtype:<12}: {cleared}/{total} games cleared, {total_levels}/{total_win} levels")

    total_games = len(results)
    total_cleared = sum(1 for r in results if r.get("cleared"))
    total_levels = sum(r.get("levels_completed", 0) for r in results)
    total_win = sum(r.get("win_levels", 0) for r in results)

    print("\n  === OVERALL ===")
    print(f"  Games cleared (1+ level): {total_cleared}/{total_games}")
    print(f"  Total levels completed:   {total_levels}/{total_win}")
    print(f"  Total time:               {total_elapsed:.1f}s")

    if cleared_games:
        print("\n  Cleared games:")
        for r in cleared_games:
            print(f"    {r['game_id']} ({r.get('title','')}) - {r['levels_completed']}/{r['win_levels']} via {r.get('strategy','')}")

    output_path = Path(__file__).parent / "solve_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to {output_path}")

    return results


if __name__ == "__main__":
    main()
