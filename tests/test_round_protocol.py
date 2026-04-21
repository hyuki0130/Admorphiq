"""R7d round-protocol tests. Every test carries a Purpose + Expected-feedback
docstring per the Implementation Discipline in CLAUDE.md."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "round.py"
_SPEC = importlib.util.spec_from_file_location("round_script", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["round_script"] = _MOD
_SPEC.loader.exec_module(_MOD)


def _trace(records):
    return {
        "timestamp": "2026-04-21T00:00:00",
        "candidate": "qwen_3_8b_q4",
        "results": [
            {"game_id": gid, "game_title": title, "best_levels": lvl}
            for gid, title, lvl in records
        ],
    }


# ---------------------------------------------------------------------------
# _summary_of_trace
# ---------------------------------------------------------------------------


def test_summary_of_trace_dedupes_by_game_id_taking_max():
    """Purpose: when the same game_id appears twice in a trace, the summary
    must keep the max levels — it's the best achievable, not the most
    recent.

    Expected feedback: if this fails, the round verdict will under-count
    cleared envs for any trace with duplicate game_ids (which every
    40-env WikiAgent run has).
    """
    trace = _trace([("A", "A", 2), ("A", "A", 5), ("B", "B", 0)])
    s = _MOD._summary_of_trace(trace)
    assert s["by_game_id"]["A"]["levels"] == 5
    assert s["envs_cleared"] == 1
    assert s["total_levels"] == 5


def test_summary_of_trace_computes_headline_counts():
    """Purpose: envs_cleared + total_levels + total_envs must match direct
    per-env aggregation.

    Expected feedback: failure means the round's before/after numbers
    drift from the regression gate's numbers and the two tools disagree.
    """
    trace = _trace([("A", "A", 2), ("B", "B", 0), ("C", "C", 3)])
    s = _MOD._summary_of_trace(trace)
    assert s["envs_cleared"] == 2
    assert s["total_envs"] == 3
    assert s["total_levels"] == 5


# ---------------------------------------------------------------------------
# _compute_verdict
# ---------------------------------------------------------------------------


def _before(records):
    by_gid = {gid: {"title": title, "levels": lvl} for gid, title, lvl in records}
    return {
        "by_game_id": by_gid,
        "by_title": {},
        "envs_cleared": sum(1 for r in by_gid.values() if r["levels"] > 0),
        "total_envs": len(by_gid),
        "total_levels": sum(r["levels"] for r in by_gid.values()),
    }


def test_verdict_pass_when_no_regression():
    """Purpose: equal or better on every shared game_id must verdict PASS.

    Expected feedback: failure flips pass/fail polarity — treats stable
    runs as regressions.
    """
    before = _before([("A", "A", 2), ("B", "B", 3)])
    after = _MOD._summary_of_trace(_trace([("A", "A", 2), ("B", "B", 3)]))
    v = _MOD._compute_verdict(before, after)
    assert v["status"] == "PASS"
    assert v["regressions"] == []


def test_verdict_fail_on_any_shared_gid_drop():
    """Purpose: a single cleared-env drop must produce FAIL, matching the
    R5 regression gate's strict stance.

    Expected feedback: failure means the round protocol disagrees with
    the regression gate and quietly promotes broken changes.
    """
    before = _before([("FT09", "FT09", 6)])
    after = _MOD._summary_of_trace(_trace([("FT09", "FT09", 0)]))
    v = _MOD._compute_verdict(before, after)
    assert v["status"] == "FAIL"
    assert len(v["regressions"]) == 1
    assert v["regressions"][0]["delta"] == -6


def test_verdict_counts_improvements_separately():
    """Purpose: net gains must be listed in `improvements`, not collapsed
    into the delta total only — Claude Code uses this list to describe
    which envs moved forward.

    Expected feedback: failure means the round notes lose per-env
    attribution for gains.
    """
    before = _before([("A", "A", 0)])
    after = _MOD._summary_of_trace(_trace([("A", "A", 2)]))
    v = _MOD._compute_verdict(before, after)
    assert v["status"] == "PASS"
    assert v["improvements"] == [{"game_id": "A", "title": "A", "delta": 2}]


def test_verdict_ignores_new_envs_not_in_baseline():
    """Purpose: when the API serves a never-before-seen game_id, it cannot
    be a regression. It joins the baseline at promotion time, not before.

    Expected feedback: failure would FAIL runs that simply picked up a
    new hash rotation.
    """
    before = _before([("A", "A", 1)])
    after = _MOD._summary_of_trace(_trace([("A", "A", 1), ("B_NEW", "B", 0)]))
    v = _MOD._compute_verdict(before, after)
    assert v["status"] == "PASS"


# ---------------------------------------------------------------------------
# _collect_prior_learnings
# ---------------------------------------------------------------------------


def test_prior_learnings_empty_when_no_rounds(monkeypatch, tmp_path):
    """Purpose: for round 1 the carryover is empty — WikiAgent's default
    placeholder ("first round, no prior learnings") must kick in.

    Expected feedback: failure means round 1 prompts would contain
    spurious history or crash on missing directory.
    """
    monkeypatch.setattr(_MOD, "ROUNDS_DIR", tmp_path / "nonexistent")
    assert _MOD._collect_prior_learnings(1) == ""


def test_prior_learnings_concatenates_earlier_takeaways(monkeypatch, tmp_path):
    """Purpose: when multiple prior rounds exist, their takeaways must be
    concatenated in numeric order so the LLM sees an accurate timeline.

    Expected feedback: failure means a later round's prompt shows
    takeaways out of order, confusing the carryover narrative.
    """
    rounds = tmp_path / "rounds"
    rounds.mkdir()
    for n, (status, levels, take) in enumerate(
        [("PASS", 2, "Graph retrieval landed."), ("PASS", 5, "Features expanded.")], start=1
    ):
        d = rounds / f"round_{n:03d}"
        d.mkdir()
        (d / "meta.json").write_text(
            '{"round_num": %d, "verdict": {"status": "%s", "levels_delta": %d}, "takeaway": "%s"}'
            % (n, status, levels, take)
        )
    monkeypatch.setattr(_MOD, "ROUNDS_DIR", rounds)
    text = _MOD._collect_prior_learnings(3)
    assert "Round 1" in text
    assert "Round 2" in text
    assert text.index("Round 1") < text.index("Round 2")
    assert "Graph retrieval" in text
    assert "Features expanded" in text


def test_prior_learnings_skips_rounds_without_takeaway(monkeypatch, tmp_path):
    """Purpose: incomplete round metadata (empty or missing takeaway) must
    be skipped silently — the whole point of takeaway is that only
    verbalized learnings feed the loop.

    Expected feedback: failure pollutes the carryover with blank
    ("Round N ()") entries.
    """
    rounds = tmp_path / "rounds"
    rounds.mkdir()
    d = rounds / "round_001"
    d.mkdir()
    (d / "meta.json").write_text(
        '{"round_num": 1, "verdict": {"status": "PASS", "levels_delta": 0}, "takeaway": ""}'
    )
    monkeypatch.setattr(_MOD, "ROUNDS_DIR", rounds)
    assert _MOD._collect_prior_learnings(2) == ""
