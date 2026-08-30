"""Does a run KNOW it is lost? Test candidate signals against labelled level-segments.

    uv run python scripts/signal_report.py scripts/rounds/R101ABLATETELOWN \
                                           scripts/rounds/R101ABLATETELABL

⭐ THE QUESTION. Rule 7cj found the harness owns no signal meaning *"I do not understand
this board"*: a frontier explorer always proposes and always reaches a new state, so
`_EMPTY_TOLERANCE` and the 80-step stall are both satisfied by a tool clearing nothing.
That is a hypothesis about a SIGNAL. This measures whether such a signal exists before
anyone builds one.

⛔ THE CLASSES ARE DEFINED BY OUTCOME, NOT BY SHAPE. The obvious labelling — "the fourteen
latched runs are the negatives" — is wrong, and `m0r0` is the counterexample sitting in the
data: it latches (one tenure, 731 actions, never re-decided) and CLEARS FIVE LEVELS. A
signal trained on latch-shape would fire on it. So the unit is a LEVEL SEGMENT — a
contiguous stretch of actions at one level — and its label is simply whether that level was
cleared.

⛔ AND THE DECISION IS EVALUATED AT A PREFIX, because a signal that only fires at action 480
of 500 is worthless. At prefix k only segments that REACHED k actions are eligible: that is
the runtime framing (you can only decide at action k if you are still there), and it is
honest about the fact that short winners are already gone.

⛔ THE OPERATING POINT IS FPR = 0. Bailing on a level that would have cleared costs the
level. So the headline number is: of the doomed segments still running at action k, what
fraction can be flagged by a threshold that flags NONE of the winning segments still running
at action k. Anything else is a budget threshold in disguise, and rule 7ax already closed
budget thresholds.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from typing import Any, Callable

PREFIXES = (25, 50, 75, 100, 150, 200, 300, 400)
WINDOW = 50          # trailing window for "rate" style candidates


def segments(tel: dict[str, Any]) -> list[dict[str, Any]]:
    """Split one run's telemetry into level segments and label each by its outcome.

    Purpose: produce the labelled unit the whole round rests on. Expected feedback: a
    segment is CLEARED iff the level index goes UP immediately after it — a level that the
    run merely stopped on, or fell back from on a restart, is not cleared.
    """
    lv = tel["level"]
    if not lv:
        return []
    bounds: list[tuple[int, int]] = []
    s = 0
    for i in range(1, len(lv)):
        if lv[i] != lv[i - 1]:
            bounds.append((s, i))
            s = i
    bounds.append((s, len(lv)))
    out: list[dict[str, Any]] = []
    for j, (a, b) in enumerate(bounds):
        nxt = lv[bounds[j + 1][0]] if j + 1 < len(bounds) else None
        out.append({
            "start": a, "end": b, "level": lv[a], "n": b - a,
            "cleared": bool(nxt is not None and nxt > lv[a]),
        })
    return out


def _prefix(tel: dict[str, Any], seg: dict[str, Any], k: int) -> dict[str, Any]:
    a = seg["start"]
    b = min(seg["end"], a + k)
    return {
        "_prior": seg.get("prior"),
        "novel": tel["novel_raw"][a:b],
        "since": tel["since_progress"][a:b],
        "seen": tel["n_seen"][a:b],
        "nch": tel["nchanged"][a:b],
        "cx": tel["cx"][a:b],
        "cy": tel["cy"][a:b],
        "k": b - a,
    }


# --- the candidates. Each maps a prefix to a scalar where HIGHER means MORE LOST. ---

def c_novelty_rate(p: dict[str, Any]) -> float:
    """1 - (novel raw states in the trailing window / window). Saturation of exploration."""
    w = p["novel"][-WINDOW:]
    return 1.0 - (w.count("1") / len(w)) if w else 0.0


def c_novelty_decay(p: dict[str, Any]) -> float:
    """Trailing-window novelty rate MINUS the opening-window rate: how fast it saturated."""
    first = p["novel"][:WINDOW]
    last = p["novel"][-WINDOW:]
    if not first or not last:
        return 0.0
    return (first.count("1") / len(first)) - (last.count("1") / len(last))


def c_revisit(p: dict[str, Any]) -> float:
    """1 - distinct raw states / actions. A cycling explorer scores high."""
    return 1.0 - (p["novel"].count("1") / p["k"]) if p["k"] else 0.0


def c_since_max(p: dict[str, Any]) -> float:
    """Largest run of consecutive no-new-state steps the HARNESS itself counted."""
    return float(max(p["since"], default=0))


def c_tool_novelty_rate(p: dict[str, Any]) -> float:
    """Same as novelty rate but on the ACTIVE TOOL's own state identity (`_seen_states`)."""
    if p["k"] < 2:
        return 0.0
    grew = sum(1 for i in range(1, p["k"]) if p["seen"][i] > p["seen"][i - 1])
    return 1.0 - grew / (p["k"] - 1)


def c_coverage(p: dict[str, Any]) -> float:
    """1 - distinct 4x4-quantised change centroids / actions. Touching one spot scores high."""
    cells = {(x // 4, y // 4) for x, y in zip(p["cx"], p["cy"]) if x >= 0 and y >= 0}
    return 1.0 - (len(cells) / p["k"]) if p["k"] else 0.0


def c_change_uniformity(p: dict[str, Any]) -> float:
    """Fraction of actions whose changed-cell count equals the segment's modal value.

    A tool cycling a fixed widget changes the same number of cells every time; a tool
    making progress does not. 7cf found bp35's band is a pure counter at rate 1.000, so
    this is the shape that measurement suggests looking for.
    """
    vals = [v for v in p["nch"] if v >= 0]
    if not vals:
        return 0.0
    return max(vals.count(v) for v in set(vals)) / len(vals)


def c_inert_rate(p: dict[str, Any]) -> float:
    """Fraction of actions that changed NOTHING on the board."""
    vals = [v for v in p["nch"] if v >= 0]
    return (vals.count(0) / len(vals)) if vals else 0.0


def c_norm_clock(p: dict[str, Any]) -> float:
    """Segment length / median length of the levels THIS GAME has already cleared.

    ⚠️ This is the candidate flagged as close to the existing death clock. It differs in
    that its scale is learned FROM THE RUN — a game whose levels cost 20 actions and one
    whose levels cost 200 get different thresholds from the same rule, which a fixed
    `no_progress` cannot do. ⛔ It is UNDEFINED on a run that has cleared nothing, which is
    exactly the 13 games that score ~0 in rule 7cj, and that is the finding rather than a
    gap to paper over. `_prior` is injected by the caller.
    """
    prior = p.get("_prior")
    return p["k"] / prior if prior else float("nan")


CANDIDATES: dict[str, Callable[[dict[str, Any]], float]] = {
    "norm_clock": c_norm_clock,
    "novelty_rate": c_novelty_rate,
    "novelty_decay": c_novelty_decay,
    "revisit": c_revisit,
    "since_progress_max": c_since_max,
    "tool_novelty_rate": c_tool_novelty_rate,
    "coverage": c_coverage,
    "change_uniformity": c_change_uniformity,
    "inert_rate": c_inert_rate,
}


def auc(pos: list[float], neg: list[float]) -> float:
    """P(a doomed segment scores above a winning one), ties counted as half."""
    if not pos or not neg:
        return float("nan")
    wins = sum((1.0 if d > w else 0.5 if d == w else 0.0) for d in pos for w in neg)
    return wins / (len(pos) * len(neg))


def load(*dirs: str) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "games", "*.json"))):
            blob = json.load(open(path))
            g = (blob.get("games") or [{}])[0]
            tel = g.get("telemetry") or {}
            if not tel.get("level"):
                continue
            runs.append({
                "game": os.path.basename(path)[:-5],
                "arm": os.path.basename(d),
                "dropped": blob.get("dropped"),
                "score": float(blob.get("total_score") or 0.0),
                "levels": g.get("levels_completed"),
                "tel": tel,
            })
    return runs


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    runs = load(*sys.argv[1:])
    if not runs:
        print("⛔ NO VERDICT: no telemetry found. Was the arm run with TELEM=1?")
        return 2

    segs: list[dict[str, Any]] = []
    for r in runs:
        for s in segments(r["tel"]):
            s = dict(s, game=r["game"], arm=r["arm"], dropped=r["dropped"], tel=r["tel"])
            segs.append(s)
    for r in runs:
        done: list[int] = []
        for s in [x for x in segs if x["game"] == r["game"] and x["arm"] == r["arm"]]:
            s["prior"] = sorted(done)[len(done) // 2] if done else None
            if s["cleared"]:
                done.append(s["n"])
    pos = [s for s in segs if s["cleared"]]
    neg = [s for s in segs if not s["cleared"]]
    print(f"runs {len(runs)}   segments {len(segs)}   CLEARED {len(pos)}   DOOMED {len(neg)}")
    print(f"  cleared-segment lengths: min {min(s['n'] for s in pos)} "
          f"median {sorted(s['n'] for s in pos)[len(pos) // 2]} max {max(s['n'] for s in pos)}")
    print(f"  doomed-segment  lengths: min {min(s['n'] for s in neg)} "
          f"median {sorted(s['n'] for s in neg)[len(neg) // 2]} max {max(s['n'] for s in neg)}")

    print("\n=== separation by prefix. AUC, and CATCH@FPR0 = doomed flagged by a threshold "
          "that flags NO winner ===")
    hdr = f"{'candidate':20s}" + "".join(f"{k:>13d}" for k in PREFIXES)
    for label in ("AUC", "CATCH@FPR0"):
        print(f"\n-- {label} (eligible = segments still running at that action) --")
        print(hdr)
        print(f"{'(eligible pos/neg)':20s}" + "".join(
            f"{str(sum(1 for s in pos if s['n'] >= k)) + '/' + str(sum(1 for s in neg if s['n'] >= k)):>13s}"
            for k in PREFIXES))
        for name, fn in CANDIDATES.items():
            cells = []
            for k in PREFIXES:
                p = [fn(_prefix(s["tel"], s, k)) for s in pos if s["n"] >= k]
                n = [fn(_prefix(s["tel"], s, k)) for s in neg if s["n"] >= k]
                if not p or not n:
                    cells.append(f"{'-':>13s}")
                    continue
                p = [v for v in p if v == v]   # drop NaN (norm_clock with no prior)
                n = [v for v in n if v == v]
                if not p or not n:
                    cells.append(f"{'-':>13s}")
                    continue
                if label == "AUC":
                    cells.append(f"{auc(n, p):>13.3f}")
                else:
                    # Highest winner score is the only threshold that never fires on a winner.
                    thr = max(p)
                    caught = sum(1 for v in n if v > thr)
                    cells.append(f"{caught:>6d}/{len(n):<6d}")
            print(f"{name:20s}" + "".join(cells))

    print("\n=== BAIL-POLICY COMPARISON — what a policy actually costs and saves ===")
    print("⛔ ELAPSED TIME CARRIES ZERO INFORMATION AT A FIXED DECISION POINT: every segment")
    print("   still alive at action k has used exactly k actions, so the clock's AUC is 0.500")
    print("   BY CONSTRUCTION. A clock does not discriminate; it only decides WHEN to stop.")
    print("   So the honest baseline is the POLICY, not the ranking.\n")
    tot_doomed = sum(s["n"] for s in neg)
    print(f"{'policy':38s} {'levels lost':>11s} {'actions saved':>13s} {'of doomed':>10s}")
    for k in PREFIXES:
        killed = sum(1 for s in pos if s["n"] > k)
        saved = sum(max(0, s["n"] - k) for s in neg)
        print(f"{'clock: bail at ' + str(k) + ' on the level':38s} {killed:11d} "
              f"{saved:13d} {saved / tot_doomed:9.1%}")
    print()
    for name, fn in CANDIDATES.items():
        best = None
        for k in PREFIXES:
            elig_p = [s for s in pos if s["n"] >= k]
            elig_n = [s for s in neg if s["n"] >= k]
            vp = [(fn(_prefix(s["tel"], s, k)), s) for s in elig_p]
            vn = [(fn(_prefix(s["tel"], s, k)), s) for s in elig_n]
            vp = [(v, s) for v, s in vp if v == v]
            vn = [(v, s) for v, s in vn if v == v]
            if len(vp) < 5 or not vn:
                continue          # too few winners to define an FPR-0 threshold honestly
            thr = max(v for v, _ in vp)
            flagged = [s for v, s in vn if v > thr]
            saved = sum(s["n"] - k for s in flagged)
            if best is None or saved > best[1]:
                best = (k, saved, len(flagged), len(vn), len(vp))
        if best is None:
            print(f"{name:38s} — no prefix has >=5 eligible winners; NO VERDICT")
            continue
        k, saved, nf, nn, npv = best
        print(f"{'signal: ' + name + ' @' + str(k):38s} {0:11d} {saved:13d} "
              f"{saved / tot_doomed:9.1%}   (flags {nf}/{nn} doomed; {npv} winners alive)")

    print("\n=== ⛔ NEGATIVE CONTROL — the SLOW WINNERS must never be flagged ===")
    slow = sorted(pos, key=lambda s: -s["n"])[:8]
    print(f"{'game':6s} {'arm':22s} {'lvl':>3s} {'n':>5s}  " +
          "  ".join(f"{c[:9]:>9s}" for c in CANDIDATES))
    for s in slow:
        vals = [fn(_prefix(s["tel"], s, s["n"])) for fn in CANDIDATES.values()]
        print(f"{s['game']:6s} {s['arm'][:22]:22s} {s['level']:3d} {s['n']:5d}  " +
              "  ".join(f"{v:9.3f}" for v in vals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
