"""R58: validate GoalLedger detectors against REAL game frames (not synthetic).

Throwaway, offline, not committed. For each of the 24 games in
data/traces/*.npz with frame evidence (tr87 excluded — 0 captured events,
per docs/r57_win_condition_typology_20260715.md), builds ONE observations
dict from early trace data only (first observed frame, first transition,
and an early same-action repeat window when one exists) and runs
goal_ledger.detect(). No level-up labels, no gold rows, no per-game
special-casing of the detector logic itself — pre-clear input only,
matching the ledger's own design constraint.

Ground truth is R57's per-game typology assignment
(docs/r57_win_condition_typology_20260715.md), hand-transcribed below into
the ledger's vocabulary (arrival/elimination/containment/pattern_match/
uniformity/threshold), with T4 (delivery) and T8 (programmatic/rewrite)
games marked EXPECTED_UNSUPPORTED since the ledger explicitly ships no
detector for those types.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from admorphiq.explanation.goal_ledger import compact_view, detect  # noqa: E402

TRACES_DIR = Path(__file__).resolve().parent.parent / "data" / "traces"

# R57 doc -> ledger vocabulary. primary = the type R57 graded as the game's
# main win-condition signature; secondary = a noted co-occurring type (not
# scored separately here, just reported). "unsupported" marks T4/T8 games
# where the ledger has NO detector by design (R58 goal_ledger.py module
# docstring) — a MISS there is expected and not a detector defect.
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


def _mode_color(frame: np.ndarray) -> int:
    vals, counts = np.unique(frame, return_counts=True)
    return int(vals[np.argmax(counts)])


def _repeat_window(actions: np.ndarray, frames: np.ndarray, episode_id: np.ndarray, max_len: int = 6) -> list | None:
    """Longest prefix run (from row 0) of one repeated action id, within one
    episode. Returns a list of observed frames [frames[0], frames[1], ...,
    frames[run_len]] (i.e. run_len+1 frames) if the run is >=3 actions long,
    else None. Deliberately EARLY-TRACE only — no level-up label used."""
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


def validate_game(name: str) -> dict:
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

    result = detect(observations)
    view = compact_view(result)
    candidate_types = [c["type"] for c in view["goal_candidates"]]

    gt = GROUND_TRUTH[name]
    primary = gt["primary"]
    unsupported = isinstance(primary, str) and primary.startswith("unsupported")
    expected_types = set()
    if not unsupported and primary != "unclassified":
        expected_types.add(primary)
    if gt.get("secondary") and not str(gt["secondary"]).startswith("unsupported") and "ambiguous" not in str(gt["secondary"]):
        # secondary is informational only per team-lead's ask (not separately
        # scored) EXCEPT for sc25's genuine hybrid, where either counts.
        if name == "sc25":
            expected_types.add(gt["secondary"])

    top1 = bool(candidate_types) and candidate_types[0] in expected_types
    topk = any(t in expected_types for t in candidate_types)

    if unsupported or primary == "unclassified":
        verdict = "N/A(expected-unsupported)" if unsupported else "N/A(unclassified)"
    elif topk:
        verdict = "TOP1" if top1 else "TOPK"
    else:
        verdict = "MISS"

    return {
        "game": name,
        "gt_primary": primary,
        "gt_secondary": gt.get("secondary"),
        "gt_note": gt.get("note", ""),
        "repeat_window_available": repeat is not None,
        "candidates": candidate_types,
        "n_competing": len(candidate_types),
        "insufficient_evidence": view["insufficient_evidence"],
        "verdict": verdict,
        "unresolved_tests": view["unresolved_tests"],
        "full_result": view,
    }


def main() -> None:
    rows = []
    for name in sorted(GROUND_TRUTH.keys()):
        path = TRACES_DIR / f"{name}.npz"
        if not path.exists():
            print(f"SKIP {name}: no trace file")
            continue
        rows.append(validate_game(name))

    print(f"\n{'game':6s} {'gt_primary':16s} {'verdict':24s} {'n_cand':6s} {'insuff':7s} {'candidates'}")
    print("-" * 110)
    for r in rows:
        print(
            f"{r['game']:6s} {r['gt_primary']:16s} {r['verdict']:24s} "
            f"{r['n_competing']:<6d} {str(r['insufficient_evidence']):7s} {r['candidates']}"
        )

    scored = [r for r in rows if r["verdict"] not in ("N/A(expected-unsupported)", "N/A(unclassified)")]
    top1_n = sum(1 for r in scored if r["verdict"] == "TOP1")
    topk_n = sum(1 for r in scored if r["verdict"] in ("TOP1", "TOPK"))
    miss_n = sum(1 for r in scored if r["verdict"] == "MISS")
    print(f"\nScored games (excludes unsupported/unclassified): {len(scored)}")
    print(f"TOP1: {top1_n}/{len(scored)} ({100*top1_n/len(scored):.1f}%)")
    print(f"TOPK (TOP1 included): {topk_n}/{len(scored)} ({100*topk_n/len(scored):.1f}%)")
    print(f"MISS: {miss_n}/{len(scored)} ({100*miss_n/len(scored):.1f}%)")

    unsupported_rows = [r for r in rows if r["verdict"].startswith("N/A")]
    print(f"\nExpected-unsupported/unclassified games ({len(unsupported_rows)}):")
    for r in unsupported_rows:
        print(f"  {r['game']:6s} candidates={r['candidates']} insufficient={r['insufficient_evidence']}")

    ambiguous = [r for r in rows if r["n_competing"] >= 2]
    single = [r for r in rows if r["n_competing"] == 1]
    empty = [r for r in rows if r["n_competing"] == 0]
    print(f"\nAmbiguity distribution: {len(ambiguous)} games with >=2 competing candidates, "
          f"{len(single)} single-candidate, {len(empty)} zero-candidate (all games N={len(rows)})")
    print("  >=2 candidates:", [r["game"] for r in ambiguous])
    print("  1 candidate:   ", [r["game"] for r in single])
    print("  0 candidates:  ", [r["game"] for r in empty])

    with open(Path(__file__).resolve().parent / "_r58_ledger_validation_results.json", "w") as fh:
        json.dump(rows, fh, indent=2, default=str)


if __name__ == "__main__":
    main()
