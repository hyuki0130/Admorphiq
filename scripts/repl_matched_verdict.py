"""Evaluate the matched 12-game OFF/ON continuation gate (R55 Codex v8 ruling).

The matched experiment (``REPL_EXPERIMENT=matched12``) writes per-run outputs
tagged ``{title}_{arm}_r{rep}`` (arm in {off, on}; the replicate game gets 3
OFF/ON pairs). This script aggregates those runs by arm and adjudicates the
three standing continuation-gate conditions decided by Codex v8:

  C1  replicate: the ON arm clears the replicate game in >=2 of 3 reps AND
      materially beats the OFF arm on that game.
  C2  causality: a goal revision (an audit that fired, adopting a hypothesis)
      precedes the first level-up in EVERY ON run that cleared a level.
  C3  coverage: across the 12 games the ON arm clears at least +2 more games
      than OFF, WITHOUT a worse aggregate efficiency proxy.

RHAE is not computable in-harness (the kernel emits no per-level human
baseline), so C3's efficiency guard uses two transparent in-harness proxies —
total levels cleared per arm and mean actions-to-first-level-up on the games
BOTH arms cleared — and flags a regression on either. The faithful RHAE
comparison is a downstream ``scripts/score_efficiency.py`` follow-up.

Usage:
    uv run python scripts/repl_matched_verdict.py --dir <matched12_run_dir>
    uv run python scripts/repl_matched_verdict.py --dir <dir> --replicate su15
"""

from __future__ import annotations

import argparse
import json
import os
from glob import glob

from repl_bench_compare import _load_jsonl, action_phases  # sibling, same dir
from score_efficiency import game_score, level_score, total_score  # sibling

_ENV_DIR = os.path.join(os.path.dirname(__file__), "..", "environment_files")


def load_baselines(env_dir: str = _ENV_DIR) -> dict[str, list[int]]:
    """title (lowercase) -> per-level human baseline_actions, from metadata.json.

    Enables faithful RHAE offline: the per-level human upper-median action count
    lives in ``environment_files/{title}/*/metadata.json`` and never changes, so
    RHAE = level_score(baseline[i], agent_actions_on_level_i) needs no re-run.
    """
    out: dict[str, list[int]] = {}
    for mp in glob(os.path.join(env_dir, "*", "*", "metadata.json")):
        try:
            with open(mp) as fh:
                meta = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        title = str(meta.get("title", "")).lower()
        base = meta.get("baseline_actions")
        if title and isinstance(base, list) and base and title not in out:
            out[title] = [int(x) for x in base]
    return out


def per_level_actions(run_dir: str, tag: str) -> list[int]:
    """Agent action counts per cleared level, segmented by level_up boundaries.

    Returns one entry per level that was completed (actions spent reaching that
    level_up). The final, in-progress level is excluded — RHAE only scores
    cleared levels.
    """
    ep = os.path.join(run_dir, "events", f"{tag}.events.jsonl")
    if not os.path.exists(ep):
        return []
    events = _load_jsonl(ep)
    counts: list[int] = []
    n = 0
    for e in events:
        if e.get("type") == "action_executed":
            n += 1
        elif e.get("type") == "level_up":
            counts.append(n)
            n = 0
    return counts


def faithful_rhae(run_dir: str, tag: str, title: str,
                  baselines: dict[str, list[int]]) -> float | None:
    """Faithful per-game RHAE for one run (level-index weighted, all-levels
    denominator), or None when no baseline is known for the game."""
    base = baselines.get(title.lower())
    if not base:
        return None
    acts = per_level_actions(run_dir, tag)
    scores = [level_score(base[i], a) for i, a in enumerate(acts) if i < len(base)]
    return game_score(scores, win_levels=len(base))


def _split_tag(tag: str) -> tuple[str, str, int] | None:
    """``su15_on_r2`` -> (``su15``, ``on``, 2). Titles carry no underscores."""
    parts = tag.rsplit("_", 2)
    if len(parts) != 3 or not parts[2].startswith("r"):
        return None
    title, arm, rep = parts
    if arm not in ("off", "on"):
        return None
    try:
        return title, arm, int(rep[1:])
    except ValueError:
        return None


def load_runs(run_dir: str) -> list[dict]:
    """One record per matched run, read from ``diagnostics/{tag}.json``.

    The kernel writes ``arm``/``rep`` into each diagnostics file; the tag is the
    ground truth and is re-parsed defensively when those keys are absent.
    """
    runs: list[dict] = []
    for dp in sorted(glob(os.path.join(run_dir, "diagnostics", "*.json"))):
        tag = os.path.basename(dp)[:-5]
        with open(dp) as fh:
            rec = json.load(fh)
        arm, rep, title = rec.get("arm"), rec.get("rep"), None
        parsed = _split_tag(tag)
        if parsed is not None:
            title, p_arm, p_rep = parsed
            arm, rep = arm or p_arm, rep if rep is not None else p_rep
        if arm is None or title is None:
            continue
        runs.append({
            "tag": tag, "title": title, "arm": arm, "rep": int(rep or 0),
            "levels": int(rec.get("levels", 0)),
            "actions": int(rec.get("actions", 0)),
            "audits": int(rec.get("audits_triggered", 0)),
            "terminal": rec.get("terminal_reason", ""),
        })
    return runs


def _cleared_games(runs: list[dict], arm: str) -> set[str]:
    """Distinct games the arm cleared at least one level on (any rep counts)."""
    return {r["title"] for r in runs if r["arm"] == arm and r["levels"] >= 1}


def evaluate(run_dir: str, replicate: str = "su15") -> dict:
    runs = load_runs(run_dir)
    if not runs:
        return {"error": f"no diagnostics found under {run_dir}"}
    baselines = load_baselines()

    off_cleared = _cleared_games(runs, "off")
    on_cleared = _cleared_games(runs, "on")

    # C1 — replicate game, per-rep clear counts.
    rep_on = [r for r in runs if r["title"] == replicate and r["arm"] == "on"]
    rep_off = [r for r in runs if r["title"] == replicate and r["arm"] == "off"]
    on_clears = sum(1 for r in rep_on if r["levels"] >= 1)
    off_clears = sum(1 for r in rep_off if r["levels"] >= 1)
    c1 = (on_clears >= 2 and on_clears > off_clears)

    # C2 — a revision (audit that fired) precedes the first level-up in every ON
    # run that cleared. Uses the event-stream + transcript action-phase split.
    on_clear_runs = [r for r in runs if r["arm"] == "on" and r["levels"] >= 1]
    c2_details, c2 = [], True
    for r in on_clear_runs:
        ph = action_phases(run_dir, r["tag"])
        before = ph.get("actions_before_first_audit")
        precedes = bool(ph.get("cleared")) and before is not None
        c2 = c2 and precedes
        c2_details.append({
            "tag": r["tag"],
            "actions_to_first_level_up": ph.get("actions_to_first_level_up"),
            "actions_before_first_audit": before,
            "revision_precedes_clear": precedes,
        })
    if not on_clear_runs:
        c2 = False  # no ON clears at all -> the causal claim is unsupported

    # C3 — coverage +2 without worse efficiency proxy.
    coverage_gain = len(on_cleared) - len(off_cleared)
    on_levels = sum(r["levels"] for r in runs if r["arm"] == "on")
    off_levels = sum(r["levels"] for r in runs if r["arm"] == "off")
    # actions-to-first-clear on games BOTH arms cleared (lower = more efficient)
    shared = off_cleared & on_cleared
    eff = {"on": [], "off": []}
    for title in shared:
        for arm in ("on", "off"):
            tags = [r["tag"] for r in runs
                    if r["title"] == title and r["arm"] == arm and r["levels"] >= 1]
            for tag in tags:
                a = action_phases(run_dir, tag).get("actions_to_first_level_up")
                if a is not None:
                    eff[arm].append(a)
    mean_on = sum(eff["on"]) / len(eff["on"]) if eff["on"] else None
    mean_off = sum(eff["off"]) / len(eff["off"]) if eff["off"] else None
    levels_ok = on_levels >= off_levels
    # Faithful aggregate RHAE per arm: mean per-game RHAE (level-index weighted,
    # all-levels denominator) over the arm's runs. total_score averages the
    # present per-game scores, so games without a baseline simply drop out.
    rhae = {"on": [], "off": []}
    for r in runs:
        val = faithful_rhae(run_dir, r["tag"], r["title"], baselines)
        if val is not None:
            rhae[r["arm"]].append(val)
    rhae_on, rhae_off = total_score(rhae["on"]), total_score(rhae["off"])
    eff_ok = rhae_on >= rhae_off  # the efficiency guard is faithful RHAE
    c3 = coverage_gain >= 2 and levels_ok and eff_ok

    return {
        "run_dir": run_dir, "replicate": replicate, "n_runs": len(runs),
        "off_cleared_games": sorted(off_cleared),
        "on_cleared_games": sorted(on_cleared),
        "C1_replicate": {"pass": c1, "on_clears": on_clears,
                         "off_clears": off_clears,
                         "on_reps": len(rep_on), "off_reps": len(rep_off)},
        "C2_revision_precedes_clear": {"pass": c2, "on_clear_runs": len(on_clear_runs),
                                       "detail": c2_details},
        "C3_coverage": {"pass": c3, "coverage_gain": coverage_gain,
                        "on_levels": on_levels, "off_levels": off_levels,
                        "rhae_on": round(rhae_on, 4), "rhae_off": round(rhae_off, 4),
                        "mean_actions_to_clear_on": mean_on,
                        "mean_actions_to_clear_off": mean_off,
                        "levels_ok": levels_ok, "efficiency_ok": eff_ok},
        "GATE_PASS": bool(c1 and c2 and c3),
    }


def _fmt(v: object) -> str:
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def main() -> None:
    p = argparse.ArgumentParser(description="Matched12 OFF/ON continuation gate.")
    p.add_argument("--dir", required=True, help="matched12 run package directory")
    p.add_argument("--replicate", default="su15", help="replicate game id")
    p.add_argument("--json", action="store_true", help="emit raw JSON only")
    args = p.parse_args()

    res = evaluate(args.dir, args.replicate)
    if args.json or "error" in res:
        print(json.dumps(res, indent=2))
        return

    print(f"matched12 verdict  dir={res['run_dir']}  runs={res['n_runs']}")
    print(f"  cleared games  OFF={res['off_cleared_games']}")
    print(f"                 ON ={res['on_cleared_games']}")
    c1 = res["C1_replicate"]
    print(f"  [{'PASS' if c1['pass'] else 'FAIL'}] C1 replicate {res['replicate']}: "
          f"ON {c1['on_clears']}/{c1['on_reps']} vs OFF {c1['off_clears']}/{c1['off_reps']}")
    c2 = res["C2_revision_precedes_clear"]
    print(f"  [{'PASS' if c2['pass'] else 'FAIL'}] C2 revision precedes clear "
          f"({c2['on_clear_runs']} ON clears)")
    for d in c2["detail"]:
        print(f"       {d['tag']}: L1@{_fmt(d['actions_to_first_level_up'])} "
              f"audit@{_fmt(d['actions_before_first_audit'])} "
              f"precedes={d['revision_precedes_clear']}")
    c3 = res["C3_coverage"]
    print(f"  [{'PASS' if c3['pass'] else 'FAIL'}] C3 coverage: +{c3['coverage_gain']} games "
          f"(need +2); levels ON={c3['on_levels']} OFF={c3['off_levels']}; "
          f"RHAE ON={c3['rhae_on']} OFF={c3['rhae_off']}; "
          f"mean-actions-to-clear ON={_fmt(c3['mean_actions_to_clear_on'])} "
          f"OFF={_fmt(c3['mean_actions_to_clear_off'])}")
    print(f"  GATE: {'PASS' if res['GATE_PASS'] else 'FAIL'}")


if __name__ == "__main__":
    main()
