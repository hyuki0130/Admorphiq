"""R58 tuning round #3: validate the REBUILT GoalLedger (capped hypothesis
generator, evidence tiers, footprint-dependency adjudication) against the
SAME real-trace battery and SAME ground-truth table as
``scripts/_r58_ledger_validation.py`` (the committed v1/v2-scoring
benchmark, left UNCHANGED — this is a separate script, not an overwrite).

Per the Codex verdict (``docs/r58_codex_ledger_ranking_20260715.md``),
TOP1 is now SECONDARY — it is reported here only for continuity with the
prior two measurement rounds, computed from the new tier-then-margin
candidate ORDER (which is what ``goal_candidates[0]`` now means: highest
tier, highest margin within that tier — a deterministic presentation
order, NOT an elected "most true" answer). The PRIMARY metrics this round
are:

  - supported-type recall under the cap (renamed from "TOPK" — same
    computation, new name matching the verdict's own framing);
  - miss attribution: for each MISS, did the ground-truth type never FIRE
    at all (non_firing), or did it fire but get EVICTED by the cap
    (cap_eviction)? These need different fixes (a detector gap vs. a cap-
    policy tuning question) and were indistinguishable in the old script.
  - independent evidence footprint count: how many mutually-independent
    evidence clusters survive the cap per game (a coverage/diversity
    metric, not just raw candidate count — two candidates sharing a
    footprint should not count as two independent signals).
  - abstention quality: for the games with NO ground-truth type in this
    ledger's vocabulary (unsupported T4/T8 games, or R57's own
    unclassified game), what fraction show insufficient_evidence=True (an
    honestly humble ledger) vs. confidently produce >=2 candidates anyway
    (none of which can be correct, by construction) — reported
    descriptively, not judged pass/fail.

Two metrics from the verdict's "what to measure next" list are NOT
computed here and are reported as such rather than faked:
  - resolution after one or two safe probes — requires actually EXECUTING
    the generated ``unresolved_tests`` probes against a live environment;
    this script only reads static trace data offline.
  - eventual intent/playbook success citing each hypothesis — requires the
    full protocol + harness + LLM loop running against real games, not a
    pure-function offline validation of ``detect()`` in isolation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import admorphiq.explanation.goal_ledger as gl  # noqa: E402
from admorphiq.explanation.goal_ledger import compact_view, detect  # noqa: E402

TRACES_DIR = Path(__file__).resolve().parent.parent / "data" / "traces"

# IDENTICAL to scripts/_r58_ledger_validation.py's GROUND_TRUTH — same
# battery, same labels, so the two scripts' numbers are directly comparable.
GROUND_TRUTH: dict[str, dict[str, object]] = {
    "ar25": {"primary": "arrival", "secondary": None},
    "bp35": {"primary": "arrival", "secondary": None},
    "cd82": {"primary": "pattern_match", "secondary": "arrival"},
    "cn04": {"primary": "arrival", "secondary": None},
    "dc22": {"primary": "arrival", "secondary": "elimination"},
    "ft09": {"primary": "uniformity", "secondary": None},
    "g50t": {"primary": "unclassified", "secondary": None},
    "ka59": {"primary": "elimination", "secondary": "unsupported(T4 delivery)"},
    "lf52": {"primary": "containment", "secondary": None, "note": "R57 itself grades this LOW CONFIDENCE"},
    "lp85": {"primary": "arrival", "secondary": "threshold(ambiguous)"},
    "ls20": {"primary": "arrival", "secondary": None},
    "m0r0": {"primary": "arrival", "secondary": None},
    "r11l": {"primary": "threshold", "secondary": None, "note": "R57 grades LOW CONFIDENCE, ambiguous vs unsupported T8"},
    "re86": {"primary": "containment", "secondary": None},
    "s5i5": {"primary": "arrival", "secondary": None, "note": "axis-projected variant, ledger only does 2D bbox"},
    "sb26": {"primary": "containment", "secondary": None},
    "sc25": {"primary": "pattern_match", "secondary": "uniformity", "note": "R57 calls phase1/phase2 a hybrid; either type counts as a hit"},
    "sk48": {"primary": "arrival", "secondary": None},
    "sp80": {"primary": "arrival", "secondary": "pattern_match"},
    "su15": {"primary": "containment", "secondary": None},
    "tn36": {"primary": "unsupported(T8 programmatic)", "secondary": None},
    "tu93": {"primary": "arrival", "secondary": None},
    "vc33": {"primary": "arrival", "secondary": None},
    "wa30": {"primary": "unsupported(T4 delivery)", "secondary": None},
}


def _repeat_window(actions: np.ndarray, frames: np.ndarray, episode_id: np.ndarray, max_len: int = 6) -> list | None:
    """IDENTICAL logic to v1's _repeat_window — early-trace only, no label."""
    if len(actions) < 3:
        return None
    a0 = actions[0]
    ep0 = episode_id[0]
    run = 1
    while run < min(len(actions), max_len) and actions[run] == a0 and episode_id[run] == ep0:
        run += 1
    if run < 3:
        return None
    return [frames[i] for i in range(run + 1) if i < len(frames)]


def _observations_for(name: str) -> dict:
    path = TRACES_DIR / f"{name}.npz"
    d = np.load(path, allow_pickle=False)
    frames = d["frames"]
    next_frames = d["next_frames"]
    actions = d["actions"]
    episode_id = d["episode_id"] if "episode_id" in d.keys() else np.zeros(len(actions), dtype=int)

    observations: dict = {"frame": frames[0].tolist()}
    observations["before"] = frames[0].tolist()
    observations["after"] = next_frames[0].tolist()
    repeat = _repeat_window(actions, frames, episode_id)
    if repeat is not None:
        observations["action_repeat_frames"] = [f.tolist() for f in repeat]
    return observations


def _expected_types(name: str, gt: dict) -> set[str]:
    """IDENTICAL restriction to v1's inline logic: secondary only counts as
    an expected type for 'sc25' (R57's own documented pattern_match/
    uniformity hybrid) — every other game's secondary is informational
    only, never separately scored. Losing this restriction would silently
    inflate recall for every game that happens to have a non-null
    secondary (measured directly while building this script: without it,
    cd82/dc22/ka59/lp85/sp80 all scored as spurious hits)."""
    primary = gt["primary"]
    unsupported = isinstance(primary, str) and primary.startswith("unsupported")
    expected: set[str] = set()
    if not unsupported and primary != "unclassified":
        expected.add(primary)
    if (
        name == "sc25"
        and gt.get("secondary")
        and not str(gt["secondary"]).startswith("unsupported")
        and "ambiguous" not in str(gt["secondary"])
    ):
        expected.add(gt["secondary"])
    return expected


def _independent_footprint_groups(result: dict) -> int:
    """Cluster the (already-capped) goal_candidates by shared/subsumed
    dependency edges (same union-find rule as goal_ledger._cluster_ambiguity_groups)
    and count distinct clusters — the number of mutually INDEPENDENT
    evidence groups actually returned, not just the raw candidate count."""
    candidates = result["goal_candidates"]
    if not candidates:
        return 0
    ids = {c["id"] for c in candidates}
    parent = {i: i for i in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for dep in result["dependencies"]:
        if dep["relation"] in ("shared_evidence", "subsumed_evidence") and dep["a"] in ids and dep["b"] in ids:
            union(dep["a"], dep["b"])
    return len({find(i) for i in ids})


def validate_game(name: str) -> dict:
    observations = _observations_for(name)
    result = detect(observations)  # capped (real deployment shape)
    view = compact_view(result)
    candidate_types = [c["type"] for c in view["goal_candidates"]]

    original_cap = gl.MAX_CANDIDATES
    gl.MAX_CANDIDATES = 999
    try:
        uncapped_result = detect(observations)
    finally:
        gl.MAX_CANDIDATES = original_cap
    uncapped_types = [c["type"] for c in uncapped_result["goal_candidates"]]

    gt = GROUND_TRUTH[name]
    primary = gt["primary"]
    unsupported = isinstance(primary, str) and primary.startswith("unsupported")
    expected = _expected_types(name, gt)

    top1_legacy = bool(candidate_types) and candidate_types[0] in expected  # tier+margin order now, see module docstring
    recall_under_cap = any(t in expected for t in candidate_types)
    fired_uncapped = any(t in expected for t in uncapped_types)

    if unsupported or primary == "unclassified":
        verdict = "N/A(expected-unsupported)" if unsupported else "N/A(unclassified)"
        miss_attribution = None
    elif recall_under_cap:
        verdict = "TOP1(legacy)" if top1_legacy else "RECALLED"
        miss_attribution = None
    else:
        verdict = "MISS"
        miss_attribution = "cap_eviction" if fired_uncapped else "non_firing"

    return {
        "game": name,
        "gt_primary": primary,
        "verdict": verdict,
        "miss_attribution": miss_attribution,
        "candidates_capped": [(c["type"], c["tier"], round(c["strength"], 3)) for c in view["goal_candidates"]],
        "candidates_uncapped_types": uncapped_types,
        "independent_footprint_groups": _independent_footprint_groups(result),
        "insufficient_evidence": view["insufficient_evidence"],
        "unresolved_tests": view["unresolved_tests"],
    }


def main() -> None:
    rows = [validate_game(name) for name in sorted(GROUND_TRUTH.keys()) if (TRACES_DIR / f"{name}.npz").exists()]

    print(f"\n{'game':6s} {'gt_primary':16s} {'verdict':16s} {'attribution':13s} {'indep_fp':9s} {'candidates (type,tier,margin)'}")
    print("-" * 130)
    for r in rows:
        attr = r["miss_attribution"] or "-"
        print(
            f"{r['game']:6s} {r['gt_primary']:16s} {r['verdict']:16s} {attr:13s} "
            f"{r['independent_footprint_groups']:<9d} {r['candidates_capped']}"
        )

    scored = [r for r in rows if not r["verdict"].startswith("N/A")]
    n = len(scored)
    top1_n = sum(1 for r in scored if r["verdict"] == "TOP1(legacy)")
    recalled_n = sum(1 for r in scored if r["verdict"] in ("TOP1(legacy)", "RECALLED"))
    miss_n = sum(1 for r in scored if r["verdict"] == "MISS")
    cap_evicted = sum(1 for r in scored if r["miss_attribution"] == "cap_eviction")
    non_firing = sum(1 for r in scored if r["miss_attribution"] == "non_firing")

    print(f"\n=== PRIMARY METRICS (n={n} scored games) ===")
    print(f"Supported-type recall under cap: {recalled_n}/{n} ({100*recalled_n/n:.1f}%)")
    print(f"MISS: {miss_n}/{n} ({100*miss_n/n:.1f}%)  of which cap_eviction={cap_evicted}, non_firing={non_firing}")
    print("\n=== SECONDARY (legacy continuity) ===")
    print(f"TOP1 (legacy, tier+margin order — NOT an elected winner): {top1_n}/{n} ({100*top1_n/n:.1f}%)")

    avg_indep = sum(r["independent_footprint_groups"] for r in rows) / len(rows)
    print(f"\n=== Independent evidence footprint groups (avg per game, all {len(rows)} games): {avg_indep:.2f} ===")
    for r in rows:
        print(f"  {r['game']:6s} {r['independent_footprint_groups']} group(s), {len(r['candidates_capped'])} candidate(s)")

    unsupported_rows = [r for r in rows if r["verdict"].startswith("N/A")]
    n_insufficient = sum(1 for r in unsupported_rows if r["insufficient_evidence"])
    print(f"\n=== Abstention quality on unsupported/unclassified games (n={len(unsupported_rows)}) ===")
    print(f"insufficient_evidence=True: {n_insufficient}/{len(unsupported_rows)}")
    for r in unsupported_rows:
        print(f"  {r['game']:6s} insufficient={r['insufficient_evidence']} candidates={r['candidates_capped']}")

    print("\n=== NOT MEASURED this round (require live execution, see module docstring) ===")
    print("  - resolution after one or two safe probes")
    print("  - eventual intent/playbook success citing each hypothesis")

    with open(Path(__file__).resolve().parent / "_r58_ledger_validation_v2_results.json", "w") as fh:
        json.dump(rows, fh, indent=2, default=str)


if __name__ == "__main__":
    main()
