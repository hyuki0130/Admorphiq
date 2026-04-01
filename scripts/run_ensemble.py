"""Run the EnsembleAgent on all 25 ARC-AGI-3 games.

Reports per-game results, per-strategy stats, and overall summary.
"""

import json
import time
import traceback
from pathlib import Path

from arc_agi import Arcade, OperationMode

from admorphiq.agent_ensemble import EnsembleAgent


def main():
    print("=" * 70)
    print("  ARC-AGI-3 Ensemble Agent — All 25 Games")
    print("=" * 70)

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    envs = arcade.get_environments()
    print(f"  Games: {len(envs)}\n")

    agent = EnsembleAgent(total_budget=20000)
    results = []
    total_start = time.time()

    for i, env_info in enumerate(envs):
        gid = env_info.game_id
        title = env_info.title or ""

        print(f"[{i+1:2d}/{len(envs)}] {gid} ({title}) ... ", end="", flush=True)

        try:
            env = arcade.make(gid)
            if env is None:
                print("ERROR: make() returned None")
                results.append({
                    "game_id": gid, "title": title, "error": "make() returned None",
                    "levels_completed": 0, "win_levels": 0, "cleared": False,
                })
                continue

            result = agent.solve_game(env, game_id=gid)
            result["title"] = title
            results.append(result)

            lvl = f"{result['levels_completed']}/{result['win_levels']}"
            status = "CLEARED!" if result["cleared"] else "no clear"
            strat = result.get("strategy", "")
            n_strats = len(result.get("strategies_tried", []))
            print(f"{lvl} lvl, {result['actions']} act, {n_strats} strats [{status}] {strat}")
        except Exception as e:
            print(f"ERROR: {e}")
            traceback.print_exc()
            results.append({
                "game_id": gid, "title": title,
                "error": str(e), "levels_completed": 0, "win_levels": 0, "cleared": False,
            })

    total_elapsed = time.time() - total_start

    # ─── Summary ─────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)

    print(f"\n  {'Game ID':<25} {'Title':<6} {'Levels':<10} {'Actions':<8} {'Strategy'}")
    print(f"  {'-'*25} {'-'*6} {'-'*10} {'-'*8} {'-'*30}")

    cleared_games = []
    for r in results:
        if "error" in r and "strategies_tried" not in r:
            print(f"  {r['game_id']:<25} {r.get('title',''):<6} {'ERR':<10}")
            continue
        lvl = f"{r['levels_completed']}/{r['win_levels']}"
        strat = r.get("strategy", "")[:30]
        print(f"  {r['game_id']:<25} {r.get('title',''):<6} {lvl:<10} {r['actions']:<8} {strat}")
        if r.get("cleared"):
            cleared_games.append(r)

    # Strategy effectiveness
    print(f"\n  --- Strategy Stats ---")
    strat_wins: dict[str, int] = {}
    strat_total: dict[str, int] = {}
    for r in results:
        for st in r.get("strategies_tried", []):
            sn = st["name"]
            strat_total[sn] = strat_total.get(sn, 0) + 1
            if st["levels"] > 0:
                strat_wins[sn] = strat_wins.get(sn, 0) + 1
    for sn in sorted(strat_total.keys()):
        wins = strat_wins.get(sn, 0)
        total = strat_total[sn]
        print(f"  {sn:<30}: {wins}/{total} wins")

    total_games = len(results)
    total_cleared = sum(1 for r in results if r.get("cleared"))
    total_levels = sum(r.get("levels_completed", 0) for r in results)
    total_win = sum(r.get("win_levels", 0) for r in results)

    print(f"\n  === OVERALL ===")
    print(f"  Games cleared (1+ level): {total_cleared}/{total_games}")
    print(f"  Total levels completed:   {total_levels}/{total_win}")
    print(f"  Total time:               {total_elapsed:.1f}s")

    if cleared_games:
        print(f"\n  Cleared games:")
        for r in cleared_games:
            print(f"    {r['game_id']} ({r.get('title','')}) - {r['levels_completed']}/{r['win_levels']} via {r.get('strategy','')}")

    output_path = Path(__file__).parent / "ensemble_results.json"
    serializable = []
    for r in results:
        sr = {}
        for k, v in r.items():
            if isinstance(v, set):
                sr[k] = list(v)
            else:
                sr[k] = v
        serializable.append(sr)
    with open(output_path, "w") as f:
        json.dump(serializable, f, indent=2, default=str)
    print(f"\n  Results saved to {output_path}")

    return results


if __name__ == "__main__":
    main()
