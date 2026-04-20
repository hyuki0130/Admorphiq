"""Extract distilled solution traces from ensemble regression results into .wiki/raw/traces/.

Reads `scripts/ensemble_results.json` (latest 40-env regression including v1+v2 hashes)
and emits one JSONL file per game into `.wiki/raw/traces/`. Each trace records:
- winning strategy per version hash
- strategies attempted with their level counts
- whether the winning strategy relies on game internals (brittle) or frame observation (frame_only)

Inputs
------
scripts/ensemble_results.json — canonical regression output (list of per-env dicts).
scripts/ensemble_results.20260410.json — prior baseline for comparison (optional).

Output
------
.wiki/raw/traces/{title_lower}.jsonl — one line per version hash, JSON object per line.
.wiki/raw/traces/_summary.json — aggregate across games for quick lookup.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "scripts" / "ensemble_results.json"
TRACES_DIR = REPO_ROOT / ".wiki" / "raw" / "traces"
SUMMARY_FILE = TRACES_DIR / "_summary.json"

# Strategies known to rely on game internals (tag reads, attribute access, hardcoded
# level solutions). Keep this list in lockstep with .wiki/wiki/strategies/brittle/.
BRITTLE_STRATEGIES: dict[str, list[str]] = {
    "lights_out": ["sprite_tags: Hkx, NTi, bsT, ZkU"],
    "paint_game": ["hardcoded_positions: pqkenviek, ctwspzkygu"],
    "sb26_sort": ["game_internals: portal/slot state"],
    "su15_vacuum": ["game_attrs: hmeulfxgy, peiiyyzum, rqdsgrklq"],
    "tn36_puzzle": ["frame_method: zpzcmabenn"],
    "re86_analytical": ["sprite_tags: vzuwsebntu, vfaeucgcyr, ozhohpbjxz"],
    "wa30_analytical": ["sprite_tags: wbmdvjhthc, wyzquhjerd, pkbufziase"],
    "s5i5_slider": ["sprite_tags: myzmclysbl, zylvdxoiuq"],
    "ka59_sokoban": ["hardcoded_levels: L1-L4 push sequences"],
    "tu93_maze": ["hardcoded_levels: L1/L2 move sequences"],
    "tr87_rotation": ["hardcoded_levels: L1 rotation values"],
    "ls20_grid": ["hardcoded_levels: L1 move sequence"],
}

# Strategies confirmed to generalize on v2 hash versions.
FRAME_ONLY_STRATEGIES: set[str] = {
    "bfs_state_space",
    "seq_repeat",
    "seq_search",
    "click_rare",
    "spell_cast",
    "zig3_A2A4",
    "explore_interact",
    "bp35_platformer",
    "click_c8_(30,4)",
    "click_c9_(33,60)",
}


def classify_strategy(name: str) -> dict[str, Any]:
    """Return strategy metadata dict for a given strategy name."""
    if name in BRITTLE_STRATEGIES:
        return {"type": "brittle", "internals": BRITTLE_STRATEGIES[name]}
    # Bucket click_cN coordinate-click variants as frame-only.
    if name.startswith("click_c") and "(" in name:
        return {"type": "frame_only", "internals": []}
    if name in FRAME_ONLY_STRATEGIES:
        return {"type": "frame_only", "internals": []}
    return {"type": "unknown", "internals": []}


def main() -> None:
    TRACES_DIR.mkdir(parents=True, exist_ok=True)

    with RESULTS.open() as f:
        envs: list[dict[str, Any]] = json.load(f)

    per_title: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for env in envs:
        title = (env.get("title") or "unknown").upper()
        winning = env.get("strategy") or ""
        entry = {
            "game_id": env["game_id"],
            "title": title,
            "cleared": bool(env.get("cleared")),
            "levels_completed": int(env.get("levels_completed", 0)),
            "win_levels": int(env.get("win_levels", 0)),
            "total_actions": int(env.get("actions", 0)),
            "winning_strategy": winning,
            "winning_strategy_meta": classify_strategy(winning) if winning else None,
            "strategies_tried": [
                {
                    "name": s["name"],
                    "levels": s["levels"],
                    "actions": s["actions"],
                    "meta": classify_strategy(s["name"]),
                }
                for s in env.get("strategies_tried", [])
                if s.get("levels", 0) > 0 or s["name"] == winning
            ],
        }
        per_title[title].append(entry)

    summary: dict[str, Any] = {
        "total_games": len(per_title),
        "total_envs": len(envs),
        "v1_cleared": 0,
        "v2_cleared": 0,
        "perfect_games_v1": [],
        "brittle_winners_v1": [],
        "frame_only_winners_v1": [],
        "per_game": {},
    }

    for title, entries in sorted(per_title.items()):
        out_file = TRACES_DIR / f"{title.lower()}.jsonl"
        with out_file.open("w") as fh:
            for entry in entries:
                fh.write(json.dumps(entry) + "\n")

        # Label versions by order seen (v1 = first hash, v2 = subsequent).
        versions = {}
        for idx, entry in enumerate(entries):
            tag = f"v{idx + 1}"
            versions[tag] = {
                "game_id": entry["game_id"],
                "cleared": entry["cleared"],
                "levels": f"{entry['levels_completed']}/{entry['win_levels']}",
                "strategy": entry["winning_strategy"],
                "strategy_type": (
                    entry["winning_strategy_meta"]["type"]
                    if entry["winning_strategy_meta"]
                    else None
                ),
            }
            if tag == "v1":
                if entry["cleared"]:
                    summary["v1_cleared"] += 1
                if entry["win_levels"] and entry["levels_completed"] == entry["win_levels"]:
                    summary["perfect_games_v1"].append(title)
                meta = entry["winning_strategy_meta"]
                if meta and meta["type"] == "brittle":
                    summary["brittle_winners_v1"].append(title)
                elif meta and meta["type"] == "frame_only":
                    summary["frame_only_winners_v1"].append(title)
            elif tag == "v2" and entry["cleared"]:
                summary["v2_cleared"] += 1
        summary["per_game"][title] = versions

    with SUMMARY_FILE.open("w") as fh:
        json.dump(summary, fh, indent=2)

    print(f"Wrote {len(per_title)} per-game trace files to {TRACES_DIR}")
    print(f"Summary: {SUMMARY_FILE}")
    print(
        f"v1 cleared: {summary['v1_cleared']}/{len(per_title)}, "
        f"v2 cleared: {summary['v2_cleared']}"
    )
    print(f"v1 perfect: {summary['perfect_games_v1']}")
    print(f"v1 brittle winners ({len(summary['brittle_winners_v1'])}): {summary['brittle_winners_v1']}")
    print(
        f"v1 frame-only winners ({len(summary['frame_only_winners_v1'])}): "
        f"{summary['frame_only_winners_v1']}"
    )


if __name__ == "__main__":
    main()
