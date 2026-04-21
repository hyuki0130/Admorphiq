"""Round-6 diagnostic: run G1-G4 generic strategies directly on their
target envs, bypassing the WikiAgent routing layer.

Round 5 found that Qwen 3 8B picks only `bfs_state_space` or
`click_rare` — G1-G4 were never executed during the live-env bench.
This script separates implementation-correctness from routing-failure:
if G1-G4 clear ≥ some fraction of what the brittle predecessors did
when run directly, the implementations are fine and round-6 work is
routing. If they clear 0, the implementations are broken and need
refining first.

Target map (strategy → target envs → brittle baseline levels):
  interactive_grid_toggle    ← FT09 (6), CD82 (6), TN36 (7)
  sprite_cluster_interaction ← SB26 (8), SU15 (9)
  push_bfs_grid              ← KA59 (4), WA30 (2)
  bfs_framehash              ← FT09 (fallback check), CD82 (fallback)

Run: `uv run python scripts/probe_generics_direct.py`
Output: `scripts/g1_g4_direct_results.json`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from admorphiq.agent_ensemble import (
    strat_bfs_framehash,
    strat_interactive_grid_toggle,
    strat_push_bfs_grid,
    strat_sprite_cluster_interaction,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "scripts" / "g1_g4_direct_results.json"

# Round-5 baseline (R1 verified 2026-04-20 via brittle strategies,
# before round 5 purged them from the whitelist).
BASELINE_BRITTLE: dict[str, int] = {
    "FT09": 6,
    "CD82": 6,
    "TN36": 7,
    "SB26": 8,
    "SU15": 9,
    "KA59": 4,
    "WA30": 2,
}

# Strategy → target titles. Each target env gets one strategy execution.
TARGET_MATRIX: dict[str, list[str]] = {
    "interactive_grid_toggle": ["FT09", "CD82", "TN36"],
    "sprite_cluster_interaction": ["SB26", "SU15"],
    "push_bfs_grid": ["KA59", "WA30"],
    "bfs_framehash": ["FT09", "CD82", "SB26", "SU15", "KA59"],
}

STRATEGIES = {
    "interactive_grid_toggle": strat_interactive_grid_toggle,
    "sprite_cluster_interaction": strat_sprite_cluster_interaction,
    "push_bfs_grid": strat_push_bfs_grid,
    "bfs_framehash": strat_bfs_framehash,
}


def main() -> None:
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    env_infos = arcade.get_environments()
    # Title → first-encountered game_id (v1 hash). Titles are not unique
    # across hash rotations so we pin to the first one we see.
    title_to_gid: dict[str, str] = {}
    for info in env_infos:
        t = (info.title or "").upper()
        if t and t not in title_to_gid:
            title_to_gid[t] = info.game_id

    results: list[dict] = []
    t_all = time.time()

    for strategy_name, target_titles in TARGET_MATRIX.items():
        strat_fn = STRATEGIES[strategy_name]
        for title in target_titles:
            gid = title_to_gid.get(title)
            entry: dict = {
                "strategy": strategy_name,
                "title": title,
                "game_id": gid,
                "baseline_brittle": BASELINE_BRITTLE.get(title),
            }
            if gid is None:
                entry["status"] = "env_not_found"
                results.append(entry)
                continue
            try:
                env = arcade.make(gid)
            except Exception as exc:  # noqa: BLE001
                entry.update(status="make_error", error=str(exc))
                results.append(entry)
                continue
            if env is None:
                entry["status"] = "make_none"
                results.append(entry)
                continue
            print(
                f"[{strategy_name:<30s}] {title:<6s} ({gid}) running...",
                flush=True,
            )
            t0 = time.time()
            try:
                best, label, used = strat_fn(env, 50000)
            except Exception as exc:  # noqa: BLE001
                entry.update(status="run_error", error=str(exc))
                results.append(entry)
                continue
            elapsed = round(time.time() - t0, 1)
            entry.update(
                status="ok",
                levels=int(best),
                actions=int(used),
                label=label,
                elapsed_s=elapsed,
                baseline_ratio=(
                    round(int(best) / BASELINE_BRITTLE[title], 2)
                    if BASELINE_BRITTLE.get(title)
                    else None
                ),
            )
            print(
                f"    levels={best:>2d}  actions={used:>5d}  "
                f"label={label:<25s}  elapsed={elapsed:>5.1f}s  "
                f"ratio vs brittle={entry['baseline_ratio']}",
                flush=True,
            )
            results.append(entry)

    OUT.write_text(json.dumps({"results": results}, indent=2))
    total_elapsed = round(time.time() - t_all, 1)
    print(f"\nDone. Wrote {OUT.name} in {total_elapsed}s", flush=True)

    # Per-strategy summary
    print("\nPer-strategy summary:", flush=True)
    for strategy_name in TARGET_MATRIX:
        rows = [r for r in results if r["strategy"] == strategy_name and r.get("status") == "ok"]
        if not rows:
            print(f"  {strategy_name:<30s}  no runs", flush=True)
            continue
        got = sum(r["levels"] for r in rows)
        baseline = sum(r["baseline_brittle"] for r in rows if r["baseline_brittle"])
        ratio = f"{got}/{baseline}" if baseline else f"{got}/0"
        print(
            f"  {strategy_name:<30s}  cleared {got:>3d} levels "
            f"(brittle baseline {baseline:>3d}, ratio {ratio})",
            flush=True,
        )


if __name__ == "__main__":
    main()
