"""Unit tests for the R5 regression gate."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "regression_gate.py"
_SPEC = importlib.util.spec_from_file_location("regression_gate", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["regression_gate"] = _MOD
_SPEC.loader.exec_module(_MOD)


def _trace(results):
    return {"timestamp": "2026-04-21T00:00:00", "candidate": "x", "results": results}


def _res(game_id, title, levels):
    return {"game_id": game_id, "game_title": title, "best_levels": levels}


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------


def test_summarize_keeps_max_per_title_across_hashes():
    t = _trace(
        [
            _res("su15-v1", "SU15", 7),
            _res("su15-v2", "SU15", 0),
            _res("ar25-v1", "AR25", 2),
        ]
    )
    s = _MOD.summarize(t)
    assert s["by_title"]["SU15"] == 7
    assert s["by_title"]["AR25"] == 2
    assert s["by_game_id"]["su15-v1"]["levels"] == 7
    assert s["by_game_id"]["su15-v2"]["levels"] == 0


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def _summary(records):
    """records = [(game_id, title, levels), ...]"""
    by_gid = {gid: {"title": title, "levels": lvl} for gid, title, lvl in records}
    by_title = {}
    for _, title, lvl in records:
        by_title[title] = max(by_title.get(title, 0), lvl)
    return {"by_game_id": by_gid, "by_title": by_title}


def test_compare_pass_when_no_regression():
    old = _summary([("a-h1", "A", 2), ("b-h1", "B", 3)])
    new = _summary([("a-h1", "A", 2), ("b-h1", "B", 3)])
    diff = _MOD.compare(new, old)
    assert diff["verdict"] == "PASS"
    assert diff["regressions"] == []
    assert diff["held_stable"] == 2


def test_compare_flags_strict_regression():
    old = _summary([("su15-v1", "SU15", 7)])
    new = _summary([("su15-v1", "SU15", 5)])
    diff = _MOD.compare(new, old)
    assert diff["verdict"] == "FAIL"
    assert len(diff["regressions"]) == 1
    assert diff["regressions"][0]["delta"] == -2


def test_compare_improvements_do_not_fail():
    old = _summary([("a-h1", "A", 2)])
    new = _summary([("a-h1", "A", 5)])
    diff = _MOD.compare(new, old)
    assert diff["verdict"] == "PASS"
    assert len(diff["improvements"]) == 1
    assert diff["improvements"][0]["delta"] == 3


def test_compare_new_envs_do_not_fail():
    old = _summary([("a-h1", "A", 2)])
    new = _summary([("a-h1", "A", 2), ("b-h1", "B", 0)])
    diff = _MOD.compare(new, old)
    assert diff["verdict"] == "PASS"
    assert diff["new_envs"] == ["b-h1"]


def test_compare_missing_envs_do_not_fail_by_themselves():
    """API hash rotation removes envs. Not our regression — not a FAIL."""
    old = _summary([("a-h1", "A", 2), ("b-h1", "B", 3)])
    new = _summary([("a-h1", "A", 2)])
    diff = _MOD.compare(new, old)
    assert diff["verdict"] == "PASS"
    assert diff["missing_envs"] == ["b-h1"]


def test_compare_title_regression_is_informational_not_failing():
    """Title-level best drop without any matching game_id drop is informational."""
    # A was cleared as (a-old, 7). Now a-old is gone; a-new scores 0. Title A
    # best went from 7 -> 0, but since a-old isn't in the new trace it's
    # counted as `missing`, not a strict regression.
    old = _summary([("a-old", "A", 7)])
    new = _summary([("a-new", "A", 0)])
    diff = _MOD.compare(new, old)
    assert diff["verdict"] == "PASS"
    assert len(diff["title_regressions"]) == 1
    assert diff["title_regressions"][0]["title"] == "A"
    assert diff["title_regressions"][0]["delta"] == -7


def test_compare_ignores_envs_absent_from_baseline():
    """Fresh envs can be any score without triggering a regression."""
    old = _summary([])
    new = _summary([("x-h", "X", 0)])
    diff = _MOD.compare(new, old)
    assert diff["verdict"] == "PASS"


def test_compare_headline_totals():
    old = _summary([("a", "A", 1), ("b", "B", 2)])
    new = _summary([("a", "A", 3), ("b", "B", 2), ("c", "C", 1)])
    diff = _MOD.compare(new, old)
    h = diff["headline"]
    assert h["baseline_total_levels"] == 3
    assert h["new_total_levels"] == 6
    assert h["level_delta"] == 3
    assert h["baseline_envs_cleared"] == 2
    assert h["new_envs_cleared"] == 3


def test_compare_equal_levels_held_stable():
    old = _summary([("a", "A", 0)])
    new = _summary([("a", "A", 0)])
    diff = _MOD.compare(new, old)
    assert diff["held_stable"] == 1
    assert diff["verdict"] == "PASS"
