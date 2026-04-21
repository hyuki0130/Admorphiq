"""Round-6 diagnostic: run `strat_inferential_agent` directly on the
target envs that G1-G4 (round 5) failed on.

Measures whether the five-phase inference pipeline
(observation → entity → goal → plan → learning loop) actually clears
levels on FT09 / CD82 / SB26 / SU15 / KA59 / WA30 / TN36. Acceptance:
≥ 8 unique levels cleared across the set. Anything less means the
phases need iteration before WikiAgent integration.

Output: `scripts/inferential_direct_results.json`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from admorphiq.strategies.inferential import strat_inferential_agent


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "scripts" / "inferential_direct_results.json"

TARGETS: list[str] = [
    "FT09",   # G1 target — lights-out
    "CD82",   # G1 target — paint
    "TN36",   # G1 target — bit panel
    "SB26",   # G2 target — sort
    "SU15",   # G2 target — merge
    "KA59",   # G3 target — sokoban
    "WA30",   # G3 target — pick-carry-drop
    "AR25",   # control — movement-hybrid
    "M0R0",   # control — movement-hybrid
    "DC22",   # control — movement
]

# Brittle baseline levels (round 1 verified, 2026-04-20 ensemble).
BASELINE: dict[str, int] = {
    "FT09": 6, "CD82": 6, "TN36": 7, "SB26": 8, "SU15": 9,
    "KA59": 4, "WA30": 2, "AR25": 2, "M0R0": 2, "DC22": 1,
}


def main() -> None:
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    env_infos = arcade.get_environments()
    title_to_gid: dict[str, str] = {}
    for info in env_infos:
        t = (info.title or "").upper()
        if t and t not in title_to_gid:
            title_to_gid[t] = info.game_id

    results: list[dict] = []
    t_all = time.time()
    total_cleared = 0

    for title in TARGETS:
        gid = title_to_gid.get(title)
        entry: dict = {
            "title": title,
            "game_id": gid,
            "baseline_brittle": BASELINE.get(title),
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
        print(f"[inferential_agent ] {title:<6s} ({gid}) running...", flush=True)
        t0 = time.time()
        try:
            best, label, used = strat_inferential_agent(env, 50000)
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
                round(int(best) / BASELINE[title], 2) if BASELINE.get(title) else None
            ),
        )
        print(
            f"    levels={best:>2d}  actions={used:>5d}  "
            f"label={label:<35s}  elapsed={elapsed:>5.1f}s  "
            f"ratio vs brittle={entry['baseline_ratio']}",
            flush=True,
        )
        total_cleared += int(best)
        results.append(entry)

    OUT.write_text(json.dumps({"results": results}, indent=2))
    total_elapsed = round(time.time() - t_all, 1)

    # Summary
    baseline_sum = sum(BASELINE[t] for t in TARGETS)
    print(
        f"\nInferentialAgent summary:  cleared {total_cleared}/{baseline_sum} "
        f"(ratio {total_cleared/baseline_sum:.2f}) in {total_elapsed}s",
        flush=True,
    )
    print("  Per-env:")
    for r in results:
        if r.get("status") == "ok":
            print(f"    {r['title']:<6s}  {r['levels']:>2d}/{r['baseline_brittle']:>2d}  "
                  f"[{r['label']}]  ({r['elapsed_s']}s)")


if __name__ == "__main__":
    main()
