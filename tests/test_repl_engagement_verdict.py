"""Tests for the engagement-flag ablation verdict (R55).

Purpose: prove scripts/repl_engagement_verdict aggregates {game}_{cell}_r{rep}
diagnostics by cell, detects a target-mechanism improvement + new clear on the
target walls (sb26 truncation, ft09 repeat), and flags any guard regression.

Expected feedback: a pass means the tool will correctly read the engagement run
and say which flag fixed which wall without breaking su15/r11l — so its output
can gate promotion. A failure means the ablation readout is wrong.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from repl_engagement_verdict import evaluate, load_runs  # noqa: E402


def _w(root, game, cell, rep, **kw):
    os.makedirs(os.path.join(root, "diagnostics"), exist_ok=True)
    d = {"game_id": game, "levels": 0, "actions": 100, "parse_failures": 0,
         "truncations": 0, "governor_rejections": 0, "inspections": 0}
    d.update(kw)
    with open(os.path.join(root, "diagnostics", f"{game}_{cell}_r{rep}.json"), "w") as fh:
        json.dump(d, fh)


def _build(root):
    for rep in (0, 1):
        # sb26: base truncation-broken (0 clears, pf 11); afirst fixes it (clears, pf 1)
        _w(root, "sb26", "base", rep, levels=0, parse_failures=11, truncations=11)
        _w(root, "sb26", "afirst", rep, levels=1, parse_failures=1, truncations=1)
        _w(root, "sb26", "rfb", rep, levels=0, parse_failures=11, truncations=11)
        _w(root, "sb26", "both", rep, levels=1, parse_failures=1, truncations=1)
        # ft09: base repeat-broken (0 clears, rej 55); rfb fixes it (clears, rej 20)
        _w(root, "ft09", "base", rep, levels=0, governor_rejections=55)
        _w(root, "ft09", "afirst", rep, levels=0, governor_rejections=55)
        _w(root, "ft09", "rfb", rep, levels=1, governor_rejections=20)
        _w(root, "ft09", "both", rep, levels=1, governor_rejections=20)
        # guards: all cells clear
        for g in ("su15", "r11l"):
            for c in ("base", "afirst", "rfb", "both"):
                _w(root, g, c, rep, levels=1)


def test_target_new_clear_and_metric_drop(tmp_path):
    """action-first must show a new clear + parse_failures drop on sb26;
    repeat-feedback the same on ft09 via governor_rejections."""
    root = str(tmp_path)
    _build(root)
    res = evaluate(root)
    sb = res["target_verdict"]["sb26"]["cells"]
    assert sb["afirst"]["new_clear"] is True
    assert sb["afirst"]["metric_delta"] < 0  # parse_failures fell
    ft = res["target_verdict"]["ft09"]["cells"]
    assert ft["rfb"]["new_clear"] is True
    assert ft["rfb"]["metric_delta"] < 0     # governor_rejections fell
    # a flag that does not target the wall should not manufacture a clear
    assert ft["afirst"]["new_clear"] is False


def test_guards_preserved(tmp_path):
    """No treatment cell may lose a guard clear it had at base."""
    root = str(tmp_path)
    _build(root)
    res = evaluate(root)
    assert res["guard_preservation"]["su15"]["ok"] is True
    assert res["guard_preservation"]["r11l"]["ok"] is True


def test_guard_regression_flagged(tmp_path):
    """If a cell loses a guard clear, it must be reported as a regression."""
    root = str(tmp_path)
    _build(root)
    # break r11l under 'both' (both reps lose the clear)
    for rep in (0, 1):
        _w(root, "r11l", "both", rep, levels=0)
    res = evaluate(root)
    gk = res["guard_preservation"]["r11l"]
    assert gk["ok"] is False and "both" in gk["regressions"]


def test_load_runs_parses_cell_tags(tmp_path):
    """Tag parsing recovers (game, cell, rep) for all four cells."""
    root = str(tmp_path)
    _build(root)
    runs = load_runs(root)
    assert len(runs) == 2 * 4 * 4  # reps x games x cells
    assert {r["cell"] for r in runs} == {"base", "afirst", "rfb", "both"}
