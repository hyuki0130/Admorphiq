"""ROUTING loss or CAPABILITY loss? Compare every forced-alone tool against the harness.

    uv run python scripts/solo_report.py

⭐ THE QUESTION. Rule 7cj measured that removing a game's owner costs 0.9082 -> 0.1932, and
7cm measured that a signal saying "I am lost" is worth 0.0000 unless there is somewhere
better to send the board. *"There is nowhere better"* is currently an INFERENCE from rule
7ba — which measured "no tool alone beats the harness" on the FULL registry, on five games.
It has never been measured on an ABLATED board, which is the case that matters.

  ROUTING loss    — some SURVIVING tool alone clears more than the ablated harness managed,
                    and is simply never selected. Then detection + handoff is worth
                    something and 7cm's signal has a destination.
  CAPABILITY loss — no surviving tool can do better, whoever picks. Then no signal, no
                    router and no model fixes it, and the only lever is a fallback that can
                    do something genuinely new.

⚠️ WHAT THE SOLO MAXIMUM IS AND IS NOT. It is a LOWER BOUND on what perfect routing could
achieve, not an upper one: the harness can COMPOSE tools, and rule 7ba's sharpest row is
ls20, where the harness reaches level 7 and no single tool passes 6. So "no solo tool beats
the ablated harness" does not strictly prove that no ROUTE does. It does prove that the
single-tool handoff — the only kind 7cm's signal could trigger — has no destination.

⛔ THE SOLO RUNS GO THROUGH `score_efficiency.run_game`, exactly as every harness arm does
(`ablate_run.py --only`). `scripts/_solo_tool.py` hand-rolls its own loop and its numbers are
NOT comparable — rule 7aj clause 1.
"""

from __future__ import annotations

import glob
import json
import os
from typing import Any

ROUNDS = "scripts/rounds"
SOLO = f"{ROUNDS}/R101ABLATESOLOALL"
ABLATED = f"{ROUNDS}/R101ABLATEDROP1"
SHIPPED = f"{ROUNDS}/R101SHIPPED"
CONTROL = f"{ROUNDS}/R101ABLATEOWN"
CLASSES = f"{ROUNDS}/R101ABLATEDROP1B"
EPS = 1e-6


def _one(path: str) -> dict[str, Any]:
    blob = json.load(open(path))
    g = (blob.get("games") or [{}])[0]
    return {
        "score": round(float(blob.get("total_score") or 0.0), 6),
        "levels": g.get("levels_completed"),
        "win": g.get("win_levels"),
        "actions": g.get("total_actions"),
        "dropped": blob.get("dropped"),
        "own": g.get("ownership", {}),
    }


def load_dir(d: str) -> dict[str, dict[str, Any]]:
    return {os.path.basename(p)[:-5]: _one(p) for p in glob.glob(os.path.join(d, "games", "*.json"))}


def load_solo() -> dict[str, dict[str, dict[str, Any]]]:
    """Prefer the committed roll-up; fall back to the per-pair results when they are present.

    ⛔ WHY A ROLL-UP EXISTS. The sweep is 1175 result files and 12MB — a fifth of the whole
    repository's history for one measurement. `SOLO.jsonl` carries every field this round
    quotes (score, levels, actions, registry_size) at 127KB, so the numbers survive in the
    repo as rule 2 requires without the dump. It was verified to reproduce this report
    byte-for-byte against the raw files before those were dropped.
    """
    out: dict[str, dict[str, dict[str, Any]]] = {}
    roll = os.path.join(SOLO, "SOLO.jsonl")
    raw = glob.glob(os.path.join(SOLO, "games", "*.json"))
    if raw:
        for p in raw:
            stem = os.path.basename(p)[:-5]
            if "__" not in stem:
                continue
            game, tool = stem.split("__", 1)
            out.setdefault(game, {})[tool] = _one(p)
        return out
    if os.path.exists(roll):
        for line in open(roll):
            r = json.loads(line)
            out.setdefault(r["game"], {})[r["tool"]] = {
                "score": r["score"], "levels": r["levels"], "win": r["win"],
                "actions": r["actions"], "dropped": f"!only:{r['tool']}", "own": {},
            }
    return out


def owners(control: dict[str, dict[str, Any]]) -> dict[str, str]:
    """The tool that held the board while the CLEARED levels were cleared (rule 7cj).

    ⛔ NOT the action-plurality holder: that inverts on three of five multi-tool games, where
    a squatter spends hundreds of actions on a terminal level the game never clears.
    """
    res: dict[str, str] = {}
    for game, r in control.items():
        lv = r["levels"] or 0
        tally: dict[str, int] = {}
        for k, v in (r["own"].get("by_level") or {}).items():
            if int(k) < lv:
                for t, n in v.items():
                    tally[t] = tally.get(t, 0) + n
        res[game] = max(tally, key=tally.get) if tally else str(r["own"].get("owner"))
    return res


def main() -> int:
    solo, abl = load_solo(), load_dir(ABLATED)
    ship, ctrl = load_dir(SHIPPED), load_dir(CONTROL)
    if not solo:
        print(f"⛔ NO VERDICT: {SOLO} holds no results.")
        return 2
    own = owners(ctrl)

    # 7cj classes: did any surviving tool CLAIM the orphaned board (primary_owns at pick 1)?
    claimed: set[str] = set()
    for game, r in load_dir(CLASSES).items():
        picks = r["own"].get("picks") or []
        if picks and picks[0].get("primary_owns"):
            claimed.add(game)

    ntools = {len(v) for v in solo.values()}
    print(f"solo results: {len(solo)} games x {sorted(ntools)} tools = "
          f"{sum(len(v) for v in solo.values())} runs\n")

    print("=== ⛔ POSITIVE CONTROL — the OWNER forced alone must clear its own game ===")
    bad = []
    for game in sorted(solo):
        o = own.get(game)
        r = solo[game].get(o)
        if r is None or (r["levels"] or 0) < 1:
            bad.append((game, o, None if r is None else r["levels"]))
    print(f"  owners clearing >=1 level alone: {len(solo) - len(bad)} of {len(solo)}"
          + (f"   ⛔ FAILURES: {bad}" if bad else "   — control PASSES"))

    print("\n=== ⛔ NEGATIVE CONTROL — on the UNABLATED board, no single tool beats the "
          "harness (rule 7ba, now on all 25) ===")
    beats_full = []
    for game in sorted(solo):
        best_t = max(solo[game], key=lambda t: solo[game][t]["score"])
        if solo[game][best_t]["score"] > ship[game]["score"] + EPS:
            beats_full.append((game, best_t, ship[game]["score"], solo[game][best_t]["score"]))
    print(f"  games where some solo tool beats the FULL harness: {len(beats_full)} of {len(solo)}")
    for g, t, a, b in beats_full:
        print(f"    ⚠️ {g}: {t} {b:.4f} > harness {a:.4f}")
    if not beats_full:
        print("  — 7ba REPRODUCED on all 25: no single tool beats the full harness anywhere.")

    print("\n=== THE ABLATION TABLE — does any SURVIVING tool alone beat the ablated harness? ===")
    print(f"{'game':6s} {'cls':4s} {'ablHarness':>10s} {'bestSolo':>9s} {'delta':>8s}  "
          f"{'lv H':>4s} {'lv S':>4s}  best surviving tool")
    routing, capability = [], []
    for game in sorted(solo):
        o = own.get(game)
        surv = {t: r for t, r in solo[game].items() if t != o}
        if not surv:
            print(f"{game:6s} ⛔ NO VERDICT — no surviving tool measured")
            continue
        # ⛔ DETERMINISTIC tie-break, and no name at all when nothing clears. `max()` over a
        # dict returns whichever all-zero tool the filesystem happened to yield first, so the
        # same sweep read two ways named different "best" tools on the ten games where every
        # surviving tool scores 0.0000 — a name that reads as a finding and is an artefact.
        bt = sorted(surv, key=lambda t: (-surv[t]["score"], -(surv[t]["levels"] or 0), t))[0]
        none_clears = (surv[bt]["score"] <= EPS and not (surv[bt]["levels"] or 0))
        bs, ah = surv[bt]["score"], abl[game]["score"]
        cls = "CLM" if game in claimed else "unc"
        wins = bs > ah + EPS
        (routing if wins else capability).append(game)
        print(f"{game:6s} {cls:4s} {ah:10.4f} {bs:9.4f} {bs - ah:+8.4f}  "
              f"{str(abl[game]['levels']):>4s} {str(surv[bt]['levels']):>4s}  "
              f"{'— NOTHING CLEARS' if none_clears else bt}"
              f"{'   <- BEATS IT' if wins else ''}")

    print(f"\nROUTING-recoverable (a surviving tool alone beats the ablated harness): "
          f"{len(routing)} of {len(solo)}  {routing}")
    print(f"CAPABILITY-bound  (none does):                                    "
          f"{len(capability)} of {len(solo)}")

    print("\n=== SPLIT BY THE 7cj CLASSES ===")
    for label, group in (("CLAIMED (a 2nd tool took the board)", sorted(claimed & set(solo))),
                         ("UNCLAIMED (generic path alone)",
                          sorted(set(solo) - claimed))):
        rec = [g for g in group if g in routing]
        print(f"  {label:38s} n={len(group):2d}   routing-recoverable {len(rec):2d}  {rec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
