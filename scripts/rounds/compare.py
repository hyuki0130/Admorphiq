"""Compare two full-25 rounds, per game and in the mean.

⛔ This is the gate a tool passes before it is kept (`OPERATING_RULES.md` rule 8). A tool's author
cannot see the cost its `detect` imposes on the other twenty-four games — measured 2026-08-27, a
tool that solved its own game perfectly took an untouched game from 0.4762 to 0.0476 — so the
decision is made here, on the per-game column, never on the mean alone and never on the agent's
own report.

Usage: `uv run python scripts/rounds/compare.py <new-round-dir> <old-round-dir>`

⛔ Before trusting a verdict, check the deltas against the PREVIOUS round's. Measured 2026-08-27:
a gate reported three regressions whose values matched a reverted experiment's to four decimals,
because that experiment had been reverted in the tree and not on the measurement box. A tool that
touches none of those games cannot reproduce another change's deltas exactly — identical deltas
across unrelated changes mean the two runs share a cause, and the shared cause is the box.

⛔ It lived on the measurement box as an untracked file for a whole session, which is exactly what
rule 2 forbids. It is in the repo now.
"""

from __future__ import annotations

import glob
import json
import os
import sys


def card(directory: str) -> dict[str, float]:
    rows: dict[str, float] = {}
    for path in glob.glob(os.path.join(directory, "games", "*.json")):
        game = os.path.basename(path)[:-5]
        try:
            with open(path) as handle:
                blob = json.load(handle)
        except Exception:  # noqa: BLE001
            continue
        score = blob.get("total_score")
        if score is None and isinstance(blob.get("games"), list) and blob["games"]:
            score = blob["games"][0].get("game_score")
        rows[game] = float(score or 0.0)
    return rows


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    new, old = card(sys.argv[1]), card(sys.argv[2])
    regressed: list[str] = []
    print(f"{'game':6s} {'old':>9s} {'new':>9s}  delta")
    for game in sorted(set(new) | set(old)):
        before, after = old.get(game), new.get(game)
        if before is None or after is None:
            print(f"{game:6s} {'-' if before is None else f'{before:.4f}':>9s} "
                  f"{'-' if after is None else f'{after:.4f}':>9s}  (missing)")
            continue
        if abs(after - before) < 1e-9:
            continue
        print(f"{game:6s} {before:9.4f} {after:9.4f}  {after - before:+.4f}")
        if after < before - 1e-9:
            regressed.append(game)
    for label, rows in (("new", new), ("old", old)):
        if rows:
            print(f"MEAN {label} = {sum(rows.values()) / len(rows):.4f} over {len(rows)}")
    if regressed:
        print(f"⛔ REGRESSED: {', '.join(regressed)} — do not keep the change")
        return 1

    # ⛔ A COMPARISON WITH NOTHING TO COMPARE IS NOT A PASS. Measured 2026-08-29: a gate whose 25
    # runs all died on an import printed every row as "(missing)" and then "no game regressed",
    # which reads exactly like a clean verdict. That is the same fail-open shape as the bash-3.2
    # `wait -n` throttle that reported success while throttling nothing, and as the audit script
    # that reused stale frames. A guard that cannot see must SAY SO, not stay quiet.
    missing = sorted(g for g in old if new.get(g) is None)
    if missing:
        print(
            f"⛔ NO VERDICT: {len(missing)} of {len(old)} games produced no result "
            f"({', '.join(missing[:6])}{' …' if len(missing) > 6 else ''}). "
            "This is not a pass — find out why they are missing."
        )
        return 1

    # ⛔ THE CANARIES. Five capped levels sit at EXACTLY the human action count — re86 L2 42/42 and
    # L6 139/139, sc25 L2 6/6, tu93 L7 14/14 and L8 23/23 — so ONE extra action drops that game off
    # the 1.0 cap. Measured 2026-08-30: sc25 L2 costs 0.00101 of the mean for a single action, which
    # ROUNDS AWAY in a four-decimal summary while the game itself falls from 1.0000. The score
    # comparison above cannot see a change that has not yet crossed the cliff, so name them.
    canaries = ("re86", "sc25", "tu93", "sb26")
    at_risk = [g for g in canaries if g in new and g in old and abs(new[g] - old[g]) < 1e-9
               and new[g] > 0.9999]
    if at_risk:
        print(f"canaries hold at 1.0000: {', '.join(at_risk)} "
              f"(zero-margin levels — one extra action would drop them)")

    print(f"no game regressed ({len(new)} games compared)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
